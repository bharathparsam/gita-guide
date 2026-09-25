import json
import re
from enum import Enum
from time import perf_counter
from typing import Protocol

import requests
from pydantic import BaseModel, ConfigDict

from app.config import Settings, get_settings
from app.observability.logging import current_request_id, get_logger, prompt_log_fields
from app.observability.metrics import NoOpMetricSink, PhaseOneMetrics
from app.reliability import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    RetryPolicy,
    call_with_resilience,
)


logger = get_logger("guardrails")


class InputSafetyAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"


class GuardrailDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: InputSafetyAction
    categories: tuple[str, ...] = ()
    reason: str | None = None
    provider: str


class InputGuardrail(Protocol):
    def check(self, message: str) -> GuardrailDecision: ...


class InputSafetyRejection(ValueError):
    def __init__(self, decision: GuardrailDecision) -> None:
        super().__init__(decision.reason or "The message was blocked by the input safety policy")
        self.decision = decision


class InputSafetyEscalation(ValueError):
    def __init__(self, decision: GuardrailDecision) -> None:
        super().__init__(decision.reason or "The message requires immediate safety support")
        self.decision = decision


class GuardrailUnavailableError(RuntimeError):
    pass


class LexicalInputGuardrail:
    """Fast local safety layer; it is not a replacement for a safety model."""

    _crisis_patterns = (
        re.compile(r"\b(?:kill|hurt)\s+myself\b", re.IGNORECASE),
        re.compile(r"\bend\s+my\s+life\b", re.IGNORECASE),
        re.compile(r"\b(?:suicide|suicidal)\b", re.IGNORECASE),
    )
    _explicit_patterns = (
        re.compile(r"\bf[\W_]*u[\W_]*c[\W_]*k(?:ing|ed|er|s)?\b", re.IGNORECASE),
        re.compile(r"\bf[\W_]{2,}(?:ing|ed|er|s)?\b", re.IGNORECASE),
        re.compile(r"\bc[\W_]*u[\W_]*n[\W_]*t(?:s)?\b", re.IGNORECASE),
        re.compile(r"\bp[\W_]*o[\W_]*r[\W_]*n(?:ography|ographic)?\b", re.IGNORECASE),
        re.compile(
            r"\b(?:graphic|explicit)\s+sexual\s+(?:content|description|material)\b",
            re.IGNORECASE,
        ),
    )

    def check(self, message: str) -> GuardrailDecision:
        if any(pattern.search(message) for pattern in self._crisis_patterns):
            return GuardrailDecision(
                action=InputSafetyAction.ESCALATE,
                categories=("self_harm_risk",),
                reason="The message may indicate an immediate risk of self-harm.",
                provider="local-policy",
            )

        if any(pattern.search(message) for pattern in self._explicit_patterns):
            return GuardrailDecision(
                action=InputSafetyAction.BLOCK,
                categories=("explicit_language",),
                reason="The message contains language restricted by the input policy.",
                provider="local-policy",
            )

        return GuardrailDecision(action=InputSafetyAction.ALLOW, provider="local-policy")


class NvidiaSafetyGuardrail:
    """Client for NVIDIA's hosted or self-hosted Nemotron content-safety model."""

    def __init__(
        self,
        settings: Settings,
        session: requests.Session | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        metrics: PhaseOneMetrics | None = None,
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_seconds=settings.circuit_breaker_recovery_seconds,
        )
        self.metrics = metrics or PhaseOneMetrics(NoOpMetricSink())

    def check(self, message: str) -> GuardrailDecision:
        return self._check(
            message,
            stage="nvidia_input_guardrail",
            operation="input_guardrail",
        )

    def check_output(self, message: str) -> GuardrailDecision:
        """Apply the same hosted safety policy to generated model output."""
        return self._check(
            message,
            stage="nvidia_output_guardrail",
            operation="output_guardrail",
        )

    def _check(
        self,
        message: str,
        *,
        stage: str,
        operation: str,
    ) -> GuardrailDecision:
        if not self.settings.nvidia_guardrail_url:
            if self.settings.nvidia_guardrail_required:
                raise GuardrailUnavailableError(
                    "NVIDIA_GUARDRAIL_REQUIRED is enabled but NVIDIA_GUARDRAIL_URL is not set"
                )
            return GuardrailDecision(action=InputSafetyAction.ALLOW, provider="nvidia-disabled")

        endpoint = f"{self.settings.nvidia_guardrail_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.settings.nvidia_guardrail_model,
            "messages": [{"role": "user", "content": message}],
            "temperature": 0.01,
            "top_p": 0.95,
            "max_tokens": 100,
            "chat_template_kwargs": {"request_categories": "/categories"},
        }

        logger.info(
            "model.prompt.prepared",
            extra={
                "request_id": current_request_id(),
                "stage": stage,
                "provider": "nvidia",
                "model": self.settings.nvidia_guardrail_model,
                "prompt_kind": "content_safety",
                **prompt_log_fields(payload),
            },
        )

        def send_request() -> requests.Response:
            response = self.session.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.settings.nvidia_guardrail_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.openrouter_timeout_seconds,
            )
            response.raise_for_status()
            return response

        provider_started = perf_counter()
        provider_status = "error"
        try:
            response = call_with_resilience(
                send_request,
                retry_on=(requests.Timeout, requests.ConnectionError),
                retry_policy=RetryPolicy(
                    max_attempts=self.settings.provider_max_attempts
                ),
                circuit_breaker=self.circuit_breaker,
            )
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            provider_status = "success"
        except CircuitBreakerOpenError as exc:
            provider_status = "circuit_open"
            raise GuardrailUnavailableError(
                f"NVIDIA guardrail request failed: {exc}"
            ) from exc
        except (
            requests.RequestException,
            CircuitBreakerOpenError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise GuardrailUnavailableError(f"NVIDIA guardrail request failed: {exc}") from exc
        finally:
            self.metrics.provider_call(
                provider="nvidia",
                operation=operation,
                status=provider_status,
                duration_seconds=perf_counter() - provider_started,
            )

        if not isinstance(content, str):
            raise GuardrailUnavailableError("NVIDIA guardrail returned non-text content")

        normalized = content.lower().strip()
        categories: tuple[str, ...] = ()
        try:
            verdict = json.loads(content)
        except json.JSONDecodeError:
            verdict = None

        if isinstance(verdict, dict):
            user_safety = str(verdict.get("User Safety", "")).strip().lower()
            raw_categories = str(verdict.get("Safety Categories", ""))
        else:
            safety_match = re.search(
                r"user\s+safety\s*:\s*(safe|unsafe)\b", normalized
            )
            user_safety = safety_match.group(1) if safety_match else ""
            category_match = re.search(
                r"safety\s+categories\s*:\s*(.+)", content, re.IGNORECASE
            )
            raw_categories = category_match.group(1) if category_match else ""

        if raw_categories:
            categories = tuple(
                category.strip() for category in raw_categories.split(",") if category.strip()
            )

        if user_safety == "safe" or "prompt harm: unharmful" in normalized:
            return GuardrailDecision(
                action=InputSafetyAction.ALLOW,
                provider="nvidia-nemotron-content-safety",
            )

        if user_safety == "unsafe" or "prompt harm: harmful" in normalized:
            normalized_categories = " ".join(categories).lower()
            if "suicide" in normalized_categories or "self harm" in normalized_categories:
                return GuardrailDecision(
                    action=InputSafetyAction.ESCALATE,
                    categories=categories or ("self_harm_risk",),
                    reason="The message may indicate an immediate risk of self-harm.",
                    provider="nvidia-nemotron-content-safety",
                )
            return GuardrailDecision(
                action=InputSafetyAction.BLOCK,
                categories=categories or ("nvidia_content_safety",),
                reason="The message violates the configured content-safety policy.",
                provider="nvidia-nemotron-content-safety",
            )

        raise GuardrailUnavailableError("NVIDIA guardrail returned an unrecognized verdict")


class CompositeInputGuardrail:
    def __init__(self, guardrails: tuple[InputGuardrail, ...]) -> None:
        self.guardrails = guardrails

    def check(self, message: str) -> GuardrailDecision:
        for guardrail in self.guardrails:
            decision = guardrail.check(message)
            if decision.action is not InputSafetyAction.ALLOW:
                return decision
        return GuardrailDecision(action=InputSafetyAction.ALLOW, provider="composite")


def build_input_guardrail(settings: Settings | None = None) -> CompositeInputGuardrail:
    settings = settings or get_settings()
    return CompositeInputGuardrail(
        (LexicalInputGuardrail(), NvidiaSafetyGuardrail(settings))
    )
