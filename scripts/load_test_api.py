from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean
from time import perf_counter
from uuid import uuid4

import requests


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * quantile) - 1))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded HTTP load smoke test")
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/classifications")
    parser.add_argument("--api-key")
    parser.add_argument("--message", default="I am anxious about an exam result.")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=30)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")

    def call(_: int) -> dict[str, object]:
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": f"load-{uuid4()}",
        }
        if args.api_key:
            headers["X-API-Key"] = args.api_key
        started = perf_counter()
        try:
            response = requests.post(
                args.url,
                headers=headers,
                json={"message": args.message},
                timeout=args.timeout_seconds,
            )
            return {
                "status_code": response.status_code,
                "latency": perf_counter() - started,
                "request_id": response.headers.get("X-Request-ID"),
            }
        except requests.RequestException as exc:
            return {
                "status_code": 0,
                "latency": perf_counter() - started,
                "error": type(exc).__name__,
            }

    results = []
    wall_started = perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(call, index) for index in range(args.requests)]
        for future in as_completed(futures):
            results.append(future.result())
    wall_seconds = perf_counter() - wall_started
    latencies = [float(item["latency"]) for item in results]
    successes = [item for item in results if int(item["status_code"]) < 400]
    report = {
        "requests": len(results),
        "concurrency": args.concurrency,
        "successes": len(successes),
        "error_rate": round(1 - len(successes) / len(results), 4),
        "throughput_per_second": round(len(results) / wall_seconds, 2),
        "latency_seconds": {
            "mean": round(mean(latencies), 4),
            "p50": round(percentile(latencies, 0.50), 4),
            "p95": round(percentile(latencies, 0.95), 4),
            "max": round(max(latencies), 4),
        },
        "status_counts": {
            str(code): sum(int(item["status_code"]) == code for item in results)
            for code in sorted({int(item["status_code"]) for item in results})
        },
    }
    print(json.dumps(report, indent=2))
    return int(
        report["error_rate"] > args.max_error_rate
        or report["latency_seconds"]["p95"] > args.max_p95_seconds
    )


if __name__ == "__main__":
    raise SystemExit(main())
