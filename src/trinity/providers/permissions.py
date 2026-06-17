"""Provider CLI permission argument policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from trinity.models import Provider
from trinity.providers.policy import InvocationAccess


@dataclass(frozen=True)
class ProviderPermissionPlan:
    """Provider-specific argv fragment plus sanitized user extras."""

    args: tuple[str, ...] = ()
    extra_args: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


class ProviderPermissionPolicy:
    """Translate Trinity access levels into provider CLI permission args."""

    CLAUDE_DANGEROUS_FLAGS = frozenset(
        {
            "--allow-dangerously-skip-permissions",
            "--dangerously-skip-permissions",
        }
    )
    CLAUDE_CONTROLLED_VALUE_FLAGS = frozenset(
        {
            "--permission-mode",
        }
    )
    CLAUDE_READ_ONLY_CONTROLLED_VALUE_FLAGS = frozenset(
        {
            "--allowedTools",
            "--allowed-tools",
            "--disallowedTools",
            "--disallowed-tools",
            "--tools",
        }
    )

    CODEX_DANGEROUS_FLAGS = frozenset(
        {
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-bypass-hook-trust",
        }
    )
    CODEX_CONTROLLED_VALUE_FLAGS = frozenset(
        {
            "--add-dir",
            "--cd",
            "--sandbox",
            "-C",
            "-s",
        }
    )

    ANTIGRAVITY_DANGEROUS_FLAGS = frozenset(
        {
            "--dangerously-skip-permissions",
        }
    )
    ANTIGRAVITY_CONTROLLED_VALUE_FLAGS = frozenset(
        {
            "--add-dir",
        }
    )

    def plan(
        self,
        *,
        provider: Provider,
        access: InvocationAccess,
        cwd: Path,
        extra_args: tuple[str, ...] = (),
    ) -> ProviderPermissionPlan:
        """Return provider permission args and sanitized extra args."""
        if provider == Provider.CLAUDE_CODE:
            return self._claude_plan(access, extra_args)
        if provider == Provider.CODEX:
            return self._codex_plan(access, cwd, extra_args)
        if provider == Provider.ANTIGRAVITY_CLI:
            return self._antigravity_plan(access, extra_args)
        return ProviderPermissionPlan(extra_args=tuple(extra_args))

    def _claude_plan(
        self,
        access: InvocationAccess,
        extra_args: tuple[str, ...],
    ) -> ProviderPermissionPlan:
        value_flags = set(self.CLAUDE_CONTROLLED_VALUE_FLAGS)
        if access == InvocationAccess.READ_ONLY:
            value_flags.update(self.CLAUDE_READ_ONLY_CONTROLLED_VALUE_FLAGS)
        sanitized, diagnostics = self._strip_controlled_args(
            extra_args,
            flag_names=self.CLAUDE_DANGEROUS_FLAGS,
            value_flag_names=frozenset(value_flags),
        )
        if access == InvocationAccess.READ_ONLY:
            args = (
                "--permission-mode",
                "plan",
                "--tools",
                "Read,LS,Grep,Glob",
            )
        else:
            args = ("--permission-mode", "acceptEdits")
        return ProviderPermissionPlan(
            args=args,
            extra_args=sanitized,
            diagnostics=tuple(diagnostics),
        )

    def _codex_plan(
        self,
        access: InvocationAccess,
        cwd: Path,
        extra_args: tuple[str, ...],
    ) -> ProviderPermissionPlan:
        sanitized, diagnostics = self._strip_controlled_args(
            extra_args,
            flag_names=self.CODEX_DANGEROUS_FLAGS,
            value_flag_names=self.CODEX_CONTROLLED_VALUE_FLAGS,
        )
        return ProviderPermissionPlan(
            args=("--sandbox", access.value, "--cd", str(cwd)),
            extra_args=sanitized,
            diagnostics=tuple(diagnostics),
        )

    def _antigravity_plan(
        self,
        access: InvocationAccess,
        extra_args: tuple[str, ...],
    ) -> ProviderPermissionPlan:
        flag_names = set(self.ANTIGRAVITY_DANGEROUS_FLAGS)
        if access == InvocationAccess.WORKSPACE_WRITE:
            flag_names.add("--sandbox")
        sanitized, diagnostics = self._strip_controlled_args(
            extra_args,
            flag_names=frozenset(flag_names),
            value_flag_names=self.ANTIGRAVITY_CONTROLLED_VALUE_FLAGS,
        )
        args = ("--sandbox",) if access == InvocationAccess.READ_ONLY else ()
        return ProviderPermissionPlan(
            args=args,
            extra_args=sanitized,
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _strip_controlled_args(
        args: tuple[str, ...],
        *,
        flag_names: frozenset[str],
        value_flag_names: frozenset[str],
    ) -> tuple[tuple[str, ...], list[str]]:
        """Remove dangerous or policy-owned args from user extra args."""
        sanitized: list[str] = []
        diagnostics: list[str] = []
        skip_next = False

        for item in args:
            text = str(item)
            if skip_next:
                diagnostics.append(f"removed_controlled_arg_value:{text}")
                skip_next = False
                continue

            name = text.split("=", 1)[0]
            if text in flag_names or name in flag_names:
                diagnostics.append(f"removed_dangerous_arg:{name}")
                continue
            if name in value_flag_names:
                diagnostics.append(f"removed_controlled_arg:{name}")
                if "=" not in text:
                    skip_next = True
                continue

            sanitized.append(text)

        return tuple(sanitized), diagnostics
