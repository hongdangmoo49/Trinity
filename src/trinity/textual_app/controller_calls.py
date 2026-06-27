"""Compatibility helpers for Textual workflow controller calls."""

from __future__ import annotations

from inspect import Parameter, signature
from typing import Any, Callable


def call_controller_method(method: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a controller method while tolerating older test doubles."""
    try:
        parameters = signature(method).parameters
    except (TypeError, ValueError):
        return method(*args, **kwargs)

    accepts_kwargs = any(
        parameter.kind == Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    if accepts_kwargs:
        return method(*args, **kwargs)

    supported_kwargs = {
        key: value
        for key, value in kwargs.items()
        if key in parameters
    }
    return method(*args, **supported_kwargs)
