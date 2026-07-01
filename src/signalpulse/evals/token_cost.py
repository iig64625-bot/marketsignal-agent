"""Token cost: approximate USD cost given token count and a known model price table."""
from __future__ import annotations

from contextlib import contextmanager

from langchain_core.callbacks import BaseCallbackHandler

# USD per 1K tokens (input, output). Prices approximate as of 2024-Q4.
_PRICE_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.005, 0.015),
    "gpt-4-turbo": (0.01, 0.03),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "deepseek-chat": (0.00014, 0.00028),
}

_DEFAULT_PRICE: tuple[float, float] = (0.001, 0.002)


def token_cost(tokens_in: int, tokens_out: int, model: str) -> float:
    """Return approximate USD cost for ``tokens_in`` input + ``tokens_out`` output."""
    p_in, p_out = _PRICE_TABLE.get(model, _DEFAULT_PRICE)
    return (tokens_in / 1000.0) * p_in + (tokens_out / 1000.0) * p_out



class TokenUsageAccumulator(BaseCallbackHandler):
    """LangChain callback that accumulates token usage across invocations.

    Inherits :class:`BaseCallbackHandler` (langchain-core 1.x) so the framework
    gets all the ``on_*`` no-op hook methods (``on_chain_start``,
    ``on_chat_model_start``, ``on_llm_error``...) and bool attrs
    (``ignore_chain``, ``ignore_chat_model``, ``ignore_llm``...) it expects.

    We override ``run_inline`` to fix the langchain-core 1.x quirk where the
    base class declares ``run_inline = False`` as a class attribute, but the
    framework calls ``cb.run_inline()`` expecting a context manager — a bool
    is not callable. ``@contextmanager`` makes ours a real context manager,
    which (per MRO) shadows the inherited bool attribute.

    Usage::

        cb = TokenUsageAccumulator()
        llm.invoke(prompt, config={"callbacks": [cb]})
        print(cb.tokens_in, cb.tokens_out, cb.cost_for_model("gpt-4o-mini"))
    """

    def __init__(self) -> None:
        super().__init__()  # initializes ignore_chain/raise_error/etc.
        self.tokens_in = 0
        self.tokens_out = 0
        self.n_calls = 0

    @contextmanager
    def run_inline(self):
        """Override the base class's ``run_inline = False`` bool with a
        real context manager (framework calls ``cb.run_inline()`` and uses
        the returned ctx mgr to scope the ainvoke)."""
        yield self

    def on_llm_end(self, response: object, **_kwargs: object) -> None:
        """LangChain callback hook. Best-effort: handle a few response shapes."""
        # The OpenAI response object has usage.prompt_tokens / completion_tokens
        usage = getattr(response, "llm_output", None) or {}
        if isinstance(usage, dict):
            tok = usage.get("token_usage") or usage.get("usage") or {}
            self.tokens_in += int(tok.get("prompt_tokens") or 0)
            self.tokens_out += int(tok.get("completion_tokens") or 0)
        self.n_calls += 1

    def cost_for_model(self, model: str) -> float:
        return token_cost(self.tokens_in, self.tokens_out, model)

    def reset(self) -> None:
        self.tokens_in = 0
        self.tokens_out = 0
        self.n_calls = 0
