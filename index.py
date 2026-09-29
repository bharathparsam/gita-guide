"""Vercel's zero-configuration FastAPI entrypoint."""

from app.api.application import app


__all__ = ["app"]
