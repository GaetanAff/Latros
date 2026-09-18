"""Local-only research interface; no medical logic lives in this package."""

from latros.ui.server import create_app

__all__ = ["create_app"]
