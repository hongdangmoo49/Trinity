from __future__ import annotations

from trinity.textual_app.controller_calls import call_controller_method


def test_call_controller_method_passes_supported_kwargs() -> None:
    def method(prompt: str, *, target_agents: tuple[str, ...]) -> tuple[object, ...]:
        return prompt, target_agents

    result = call_controller_method(
        method,
        "build",
        target_agents=("claude",),
        agent_model_overrides={"claude": "sonnet"},
    )

    assert result == ("build", ("claude",))


def test_call_controller_method_preserves_var_keyword_methods() -> None:
    def method(prompt: str, **kwargs: object) -> tuple[object, ...]:
        return prompt, kwargs

    result = call_controller_method(
        method,
        "build",
        target_agents=("claude",),
        agent_model_overrides={"claude": "sonnet"},
    )

    assert result == (
        "build",
        {
            "target_agents": ("claude",),
            "agent_model_overrides": {"claude": "sonnet"},
        },
    )


def test_call_controller_method_falls_back_when_signature_is_unavailable() -> None:
    class SignatureBlocked:
        __signature__ = "invalid"

        def __call__(self, prompt: str, **kwargs: object) -> tuple[object, ...]:
            return prompt, kwargs

    result = call_controller_method(
        SignatureBlocked(),
        "build",
        target_agents=("claude",),
    )

    assert result == ("build", {"target_agents": ("claude",)})
