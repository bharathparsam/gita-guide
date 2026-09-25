import argparse

from app.config import get_settings
from app.guardrails.input_safety import NvidiaSafetyGuardrail
from app.observability.logging import configure_logging


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Check one synthetic message with the configured NVIDIA safety endpoint"
    )
    parser.add_argument("message")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.nvidia_guardrail_url:
        parser.error("NVIDIA_API_KEY or NVIDIA_GUARDRAIL_URL is not configured")

    decision = NvidiaSafetyGuardrail(settings).check(args.message)
    print(decision.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
