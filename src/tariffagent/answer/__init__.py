"""Cited answers: verified source excerpts attached to rule-engine results."""

from .citations import Citation, CitationError, load_verified
from .compose import CitedAnswer, compose

__all__ = ["Citation", "CitationError", "CitedAnswer", "compose", "load_verified"]
