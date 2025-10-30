"""Backwards-compatible import for the renamed admin CLI."""

from __future__ import annotations

from i4g.cli.admin import *  # noqa: F401,F403
from i4g.cli.admin import main

__all__ = ["main"]

