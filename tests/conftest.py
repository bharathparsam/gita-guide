import os


# Unit tests must never export prompts or traces to an external service. Explicit
# LangSmith integration checks run in a separate process with tracing enabled.
os.environ["LANGSMITH_TRACING"] = "false"
