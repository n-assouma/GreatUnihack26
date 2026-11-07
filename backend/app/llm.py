"""LiteLLM wrapper: one tool-calling format for every provider.

CONTRACTS §8 picks LiteLLM so the team can swap Claude for Gemini by changing
`LLM_MODEL` with no code change. Everything provider-specific stays in this file.

Every call is wrapped: any exception, timeout or missing key returns
`LlmResult(ok=False)` and the caller falls back to the D6 sentence templates, so a
flaky network on demo day can never produce a 500 or an empty chat bubble.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

DEFAULT_MODEL = "anthropic/claude-sonnet-5"
DEFAULT_GUARD_MODEL = "anthropic/claude-haiku-4-5"
TIMEOUT_S = 20
MAX_TOKENS = 1024  # replies are 1-3 spoken sentences; tool-call turns are tiny

# Reported by /api/health so the judges (and we) can see what is real.
_llm_ever_failed = False


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class LlmResult:
    ok: bool
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    error: str | None = None


def main_model() -> str:
    return os.getenv("LLM_MODEL") or DEFAULT_MODEL


def guard_model() -> str:
    return os.getenv("GUARD_MODEL") or DEFAULT_GUARD_MODEL


def available() -> bool:
    """False when we must not even try a network call."""
    if os.getenv("MOCK_LLM") == "1":
        return False
    model = main_model()
    if model.startswith("gemini/"):
        return bool(os.getenv("GEMINI_API_KEY"))
    return bool(os.getenv("ANTHROPIC_API_KEY"))


# litellm imports these only when completion() actually runs, so a missing one is
# invisible until the first real call — which, with the key arriving last, means
# during the demo. A3 hit exactly this on a fresh venv: every call died with
# ModuleNotFoundError and we silently served templates while health said "real".
LAZY_DEPENDENCIES = ("mcp",)


def missing_dependencies() -> list[str]:
    """litellm dependencies that are absent and would break calls at call time."""
    import importlib.util

    return [name for name in LAZY_DEPENDENCIES if importlib.util.find_spec(name) is None]


def status() -> str:
    """"real" | "degraded" | "mock" — for /api/health."""
    if not available():
        return "mock"
    if _llm_ever_failed or missing_dependencies():
        return "degraded"
    return "real"


def _parse_tool_calls(message: object) -> list[ToolCall]:
    raw = getattr(message, "tool_calls", None) or []
    calls: list[ToolCall] = []
    for item in raw:
        fn = getattr(item, "function", None)
        if fn is None:
            continue
        # Arguments arrive as a JSON *string*. Models differ in how they escape it,
        # so always json.loads — never pattern-match the serialised form.
        try:
            args = json.loads(fn.arguments or "{}")
        except (json.JSONDecodeError, TypeError):
            args = {}
        if not isinstance(args, dict):
            args = {}
        calls.append(ToolCall(id=getattr(item, "id", "") or "", name=fn.name or "", args=args))
    return calls


def chat(
    model: str,
    system: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    timeout: int = TIMEOUT_S,
) -> LlmResult:
    """One LLM round. `messages` is already in OpenAI/LiteLLM format."""
    global _llm_ever_failed

    if not available():
        return LlmResult(ok=False, error="llm disabled (MOCK_LLM=1 or no API key)")

    try:
        import litellm  # imported lazily: a slow or broken import must not stop the server

        litellm.drop_params = True  # ignore params a swapped-in provider does not support

        kwargs: dict = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
            "timeout": timeout,
            "max_tokens": MAX_TOKENS,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = litellm.completion(**kwargs)
        message = response.choices[0].message
        text = (getattr(message, "content", None) or "").strip() or None
        return LlmResult(ok=True, text=text, tool_calls=_parse_tool_calls(message))
    except Exception as exc:  # noqa: BLE001 - the whole point is to never raise
        _llm_ever_failed = True
        print(f"[llm] call failed, falling back to templates ({type(exc).__name__}: {exc})")
        return LlmResult(ok=False, error=f"{type(exc).__name__}: {exc}")


def classify(system: str, text: str) -> dict | None:
    """Small JSON classification on the cheap guard model. None if unavailable."""
    result = chat(
        model=guard_model(),
        system=system,
        messages=[{"role": "user", "content": text}],
        timeout=8,
    )
    if not result.ok or not result.text:
        return None
    body = result.text.strip()
    if body.startswith("```"):  # tolerate a fenced JSON block
        body = body.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        parsed = json.loads(body[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
