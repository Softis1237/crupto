"""Генератор кандидатов стратегий (заглушка)."""

from __future__ import annotations

from hashlib import sha256

from brain_orchestrator.tools.base import ToolContext, ToolSpec


class CandidateGeneratorTool:
    """Псевдодетерминированно генерирует стратегию из промпта."""

    spec = ToolSpec(
        capability="generate_candidate",
        agent="research",
        read_only=True,
        safety_tags=("deterministic", "sandbox_only"),
        cost_hint_ms=50,
    )

    def execute(self, context: ToolContext, **kwargs) -> dict[str, str]:
        prompt: str = kwargs["prompt"]
        digest = sha256(prompt.encode("utf-8")).hexdigest()[:8]
        return {
            "id": f"cand-{digest}",
            "description": prompt[:80],
            "parameters": {"ema_fast": 12, "ema_slow": 36, "atr": 14},
        }


def register_tools(registry) -> None:
    registry.register(CandidateGeneratorTool())
