"""LLM circuit breaker — backwards compatibility shim.

The canonical implementation now lives at
``app.core.providers.circuit_breaker``.  This module re-exports the
legacy names so existing imports keep working.
"""
from app.core.providers.circuit_breaker import (
    LLMCircuitBreaker,
    LLMCircuitBreakerOpen,
)

__all__ = ["LLMCircuitBreaker", "LLMCircuitBreakerOpen"]
