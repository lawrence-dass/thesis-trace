"""Constrained LLM rewrite of an already-correct explanation (FR-12, AD-7, AD-21).

The LLM is NEVER in the numeric loop. It may only polish already-correct
deterministic text — it must not introduce a claim, number, or citation. If no
LLM key is configured (or rewrite is disabled), the deterministic text is returned
unchanged, so the feature degrades safely to deterministic-only.

Default model: Anthropic Claude Haiku 4.5, key from env (AD-21). The live call is
gated behind the key and is not exercised by the test suite.
"""

from __future__ import annotations

from app.config import get_settings

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

REWRITE_SYSTEM_PROMPT = (
    "You rewrite financial-score explanations to read more fluently. You must NOT "
    "add, remove, or change any number, claim, ticker, or citation. You may only "
    "reword for clarity. If unsure, return the text unchanged."
)


def rewrite_enabled() -> bool:
    return bool(get_settings().llm_api_key)


async def polish(text: str, *, model: str = DEFAULT_MODEL) -> str:
    """Return a fluency-polished version of `text`, or `text` unchanged if disabled.

    Guardrail: the LLM receives already-correct text and a constraining system
    prompt; it originates nothing. When no key is present this is a no-op, so the
    deterministic explanation always stands on its own.
    """
    if not rewrite_enabled():
        return text
    return await _call_anthropic(text, model)  # pragma: no cover — live path, gated


async def _call_anthropic(text: str, model: str) -> str:  # pragma: no cover — live path, gated
    import anthropic  # imported lazily so the dependency is only needed when rewrite runs

    client = anthropic.AsyncAnthropic(api_key=get_settings().llm_api_key)
    message = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=REWRITE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return "".join(block.text for block in message.content if getattr(block, "type", None) == "text") or text
