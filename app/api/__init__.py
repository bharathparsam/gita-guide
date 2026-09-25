"""HTTP ingress for the Gita Guide application."""

from app.api.application import app, create_app

__all__ = ["app", "create_app"]
