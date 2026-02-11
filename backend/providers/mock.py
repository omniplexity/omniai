"""Deterministic mock provider for CI/E2E."""

from collections.abc import AsyncIterator
from typing import Any

from backend.providers.base import (
    BaseProvider,
    ChatChunk,
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ProviderCapabilities,
    ProviderType,
)


class MockProvider(BaseProvider):
    """Simple deterministic provider for tests and CI."""

    provider_type = ProviderType.LMSTUDIO

    async def healthcheck(self) -> bool:
        return True

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                id="mock-model",
                name="Mock Model",
                provider=ProviderType.LMSTUDIO,
                context_length=8192,
                supports_streaming=True,
            )
        ]

    async def capabilities(self, model: str | None = None) -> ProviderCapabilities:
        return ProviderCapabilities(streaming=True)

    def _extract_prompt_and_model(
        self,
        request: ChatRequest | None = None,
        **kwargs: Any,
    ) -> tuple[str, str]:
        """Support both ChatRequest calls and kwargs-style calls used by ProviderAgent."""
        if request is not None:
            prompt = request.messages[-1].content if request.messages else ""
            return prompt, request.model or "mock-model"

        messages = kwargs.get("messages") or []
        model = kwargs.get("model") or "mock-model"
        prompt = ""
        if messages:
            last = messages[-1]
            prompt = getattr(last, "content", None) or last.get("content", "")
        return prompt, model

    async def chat_once(
        self,
        request: ChatRequest | None = None,
        **kwargs: Any,
    ) -> ChatResponse | dict[str, Any]:
        prompt, model = self._extract_prompt_and_model(request=request, **kwargs)
        content = f"[mock] {prompt}".strip()

        if request is not None:
            return ChatResponse(
                content=content,
                model=model,
                finish_reason="stop",
                prompt_tokens=8,
                completion_tokens=8,
                total_tokens=16,
            )

        return {
            "content": content,
            "model": model,
            "tokens_prompt": 8,
            "tokens_completion": 8,
            "finish_reason": "stop",
        }

    async def chat_stream(
        self,
        request: ChatRequest | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk | dict[str, Any]]:
        prompt, model = self._extract_prompt_and_model(request=request, **kwargs)
        text = f"[mock] {prompt}".strip()
        for token in text.split(" "):
            if request is not None:
                yield ChatChunk(content=f"{token} ", model=model)
            else:
                yield {"content": f"{token} ", "model": model}

        if request is not None:
            yield ChatChunk(content="", finish_reason="stop", model=model)
        else:
            yield {"content": "", "finish_reason": "stop", "model": model}
