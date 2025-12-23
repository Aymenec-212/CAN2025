# app/core/llm.py
import logging
from typing import Any, Dict, List, Literal, Optional, Union, AsyncGenerator

from litellm import acompletion, ModelResponse
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

# Structured logger for LLM interactions
logger = logging.getLogger("llm_gateway")

# Type definitions
ModelType = Literal["fast", "smart"]


class LLMGateway:
    """
    Centralized Gateway for LLM interactions using LiteLLM.

    - All agents/services must go through this gateway (no direct provider SDK calls).
    - Handles routing between 'fast' and 'smart' models.
    - Adds logging, retries, and (optionally) observability hooks.
    """

    def __init__(self) -> None:
        # Future: Initialize observability tools (e.g. Langfuse, Helicone) here.
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model_type: ModelType = "fast",
        stream: bool = False,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = "auto",
        json_mode: bool = False,
    ) -> Union[ModelResponse, AsyncGenerator[Any, None]]:
        """
        Unified interface for chat completions.

        Args:
            messages: List of {"role": "...", "content": "..."}.
            model_type: "fast" (routing/simple) or "smart" (reasoning/RAG).
            stream: If True, returns an async generator of chunks.
            temperature: Creativity / randomness control.
            max_tokens: Optional max tokens for completion.
            tools: Optional tool definitions for tool calling.
            tool_choice: "auto" or specific tool choice.
            json_mode: If True, requests JSON-formatted output (provider-dependent).

        Returns:
            - If stream is False: a ModelResponse object
              (with .choices, .usage, etc.).
            - If stream is True: an AsyncGenerator yielding streamed chunks.
        """

        # 1. Route to specific model based on "fast" vs "smart"
        model = (
            settings.LLM_MODEL_SMART
            if model_type == "smart"
            else settings.LLM_MODEL_FAST
        )

        # 2. Prepare parameters for LiteLLM
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "api_key": settings.LLM_API_KEY,
            "temperature": temperature,
        }

        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # 3. Log request (sanitized)
        logger.info(
            "LLM Request: model=%s type=%s stream=%s msg_count=%d tool_count=%d",
            model,
            model_type,
            stream,
            len(messages),
            len(tools) if tools else 0,
        )

        try:
            # 4. Execute call via LiteLLM (async)
            response = await acompletion(**kwargs)

            # 5. Handle response shape
            if stream:
                # Streaming mode: caller is responsible for iterating the generator
                return response

            # Non-streaming: log usage if available
            usage = getattr(response, "usage", None)
            if usage:
                logger.info(
                    "LLM Usage: model=%s prompt=%s completion=%s total=%s",
                    model,
                    getattr(usage, "prompt_tokens", None),
                    getattr(usage, "completion_tokens", None),
                    getattr(usage, "total_tokens", None),
                )

            return response

        except Exception as e:
            logger.error(
                "LLM Gateway Failed: %s (model=%s, type=%s)",
                str(e),
                model,
                model_type,
                exc_info=True,
            )
            # Retry is handled by tenacity; if all attempts fail, we re-raise
            raise e


# Singleton instance to be imported by agents/services
llm_gateway = LLMGateway()
