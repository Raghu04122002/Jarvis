"""AI chat service supporting Anthropic and Ollama (cloud or local) backends."""

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import anthropic
import httpx

from jarvis.config import AIConfig
from jarvis.services.chat_tools import Toolbox

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Jarvis, a local AI assistant. You have no tools in this mode: no web "
    "search, no live data, no access to the user's files. Never make up news, "
    "sources, URLs, prices or timestamps; if a request needs live data, say so in "
    "one line and offer what you can do instead. Lead with the answer, no filler, "
    "no emojis, Markdown formatting, short by default."
)

# Anthropic's default base URL when not using a proxy
_ANTHROPIC_DEFAULT_URL = "https://api.anthropic.com"

_OLLAMA_CLOUD_HOST = "ollama.com"


class AIServiceError(Exception):
    """An AI call failed; the message is safe to show to the user."""


class AIService:
    """Conversational chat over the configured LLM provider."""

    def __init__(self, config: AIConfig) -> None:
        self._pxpipe_url_override: str | None = None
        self._pxpipe_url_resolved = False
        self._configure(config)

    def reconfigure(self, config: AIConfig) -> None:
        """Apply new settings (provider, model, keys) without a restart."""
        self._configure(config)
        if self._pxpipe_enabled and self._pxpipe_url_resolved:
            self.set_pxpipe_base_url(self._pxpipe_url_override)

    def _configure(self, config: AIConfig) -> None:
        self._provider = config.provider
        self._max_tokens = config.max_tokens
        self._pxpipe_enabled = config.pxpipe_enabled and self._provider == "anthropic"

        # --- Anthropic ---
        api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        base_url: str | None = config.base_url if self._pxpipe_enabled else None
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or "not-set",
            base_url=base_url,
        )
        self._model = config.model
        self._api_key_set = bool(api_key)

        # --- Ollama ---
        self._ollama_base_url = config.ollama_base_url.rstrip("/")
        self._ollama_api_key = config.ollama_api_key
        self._ollama_model = config.ollama_model
        self._ollama_timeout = config.ollama_timeout
        self._ollama_think = _parse_think(config.ollama_think)

        if self._provider == "anthropic" and not api_key:
            logger.warning("No ANTHROPIC_API_KEY configured — AI chat will be unavailable")
        if self._provider == "ollama" and self._ollama_requires_key and not self._ollama_api_key:
            logger.warning("No OLLAMA_API_KEY configured — Ollama Cloud chat will be unavailable")

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        """The model chat currently uses."""
        return self._ollama_model if self._provider == "ollama" else self._model

    @property
    def _ollama_requires_key(self) -> bool:
        """Ollama Cloud needs an API key; a local daemon does not."""
        return _OLLAMA_CLOUD_HOST in self._ollama_base_url

    @property
    def available(self) -> bool:
        if self._provider == "ollama":
            return bool(self._ollama_api_key) or not self._ollama_requires_key
        return self._api_key_set

    def set_pxpipe_base_url(self, base_url: str | None) -> None:
        """Update the base URL (e.g., after pxpipe health check resolves)."""
        self._pxpipe_url_override = base_url
        self._pxpipe_url_resolved = True
        self._client = anthropic.AsyncAnthropic(
            api_key=self._client.api_key,
            base_url=base_url,
        )

    async def chat(self, message: str, context: str | None = None) -> str:
        """Send a message to the configured provider and return the response text."""
        if not self.available:
            if self._provider == "ollama":
                return (
                    "AI chat is not configured. Set the OLLAMA_API_KEY "
                    "environment variable to enable Ollama Cloud responses."
                )
            return (
                "AI chat is not configured. Set the ANTHROPIC_API_KEY "
                "environment variable to enable intelligent responses."
            )

        system = SYSTEM_PROMPT
        if context:
            system = f"{SYSTEM_PROMPT}\n\nAdditional context:\n{context}"

        try:
            return await self.complete(system, message)
        except AIServiceError as e:
            return str(e)

    async def complete(
        self,
        system: str,
        message: str,
        *,
        model: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Run one completion with a custom system prompt.

        Unlike chat(), failures raise AIServiceError instead of returning text,
        so callers can tell a real answer from an error message.
        """
        if not self.available:
            raise AIServiceError(f"AI service ({self._provider}) is not configured.")
        if self._provider == "ollama":
            return await self._chat_ollama(message, system, model=model, json_mode=json_mode)
        return await self._chat_anthropic(message, system, model=model)

    async def _chat_anthropic(self, message: str, system: str, *, model: str | None = None) -> str:
        try:
            response = await self._client.messages.create(
                model=model or self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": message}],
            )
            # Extract text from the response
            text_parts = [block.text for block in response.content if block.type == "text"]
            if not text_parts:
                raise AIServiceError("No response generated.")
            return "\n".join(text_parts)

        except anthropic.AuthenticationError:
            logger.error("Anthropic API authentication failed")
            raise AIServiceError(
                "AI authentication failed. Please check your ANTHROPIC_API_KEY."
            ) from None

        except anthropic.APIConnectionError as e:
            logger.warning("Anthropic API connection error: %s", e)
            raise AIServiceError(
                "Could not connect to the AI service. "
                "Check that pxpipe proxy or the Anthropic API is reachable."
            ) from e

        except anthropic.APIError as e:
            logger.error("Anthropic API error: %s", e)
            raise AIServiceError(f"AI service error: {e.message}") from e

    async def _chat_ollama(
        self,
        message: str,
        system: str,
        *,
        model: str | None = None,
        json_mode: bool = False,
    ) -> str:
        headers: dict[str, str] = {}
        if self._ollama_api_key:
            headers["Authorization"] = f"Bearer {self._ollama_api_key}"

        payload: dict[str, object] = {
            "model": model or self._ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            "stream": False,
            "options": {"num_predict": self._max_tokens},
        }
        if self._ollama_think is not None:
            payload["think"] = self._ollama_think
        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(
                base_url=self._ollama_base_url, timeout=self._ollama_timeout
            ) as client:
                resp = await client.post("/api/chat", json=payload, headers=headers)

            if resp.status_code in (401, 403):
                logger.error("Ollama API authentication failed")
                raise AIServiceError("AI authentication failed. Please check your OLLAMA_API_KEY.")
            if resp.status_code == 429:
                logger.warning("Ollama usage limit reached")
                raise AIServiceError(
                    "Ollama Cloud usage limit reached for now. "
                    "Free-tier limits reset periodically — please try again later."
                )
            if resp.status_code >= 400:
                detail = _ollama_error_detail(resp)
                logger.error("Ollama API error %s: %s", resp.status_code, detail)
                raise AIServiceError(f"AI service error: {detail}")

            data = resp.json()
            content = (data.get("message") or {}).get("content", "")
            if not content.strip():
                raise AIServiceError("No response generated.")
            return str(content).strip()

        except httpx.TimeoutException:
            logger.warning("Ollama API request timed out")
            raise AIServiceError("The AI service timed out. Please try again.") from None

        except httpx.HTTPError as e:
            logger.warning("Ollama API connection error: %s", e)
            raise AIServiceError(
                "Could not connect to the AI service. "
                f"Check that Ollama is reachable at {self._ollama_base_url}."
            ) from e

        except ValueError as e:
            logger.error("Invalid JSON from Ollama API: %s", e)
            raise AIServiceError("AI service returned an invalid response.") from e

    # ------------------------------------------------------------------
    # Streaming chat with tools
    # ------------------------------------------------------------------

    async def stream_chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        toolbox: Toolbox | None = None,
        max_rounds: int = 5,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a reply, running tool calls as the model asks for them.

        ``messages`` is the conversation as ``[{"role": "user"|"assistant",
        "content": str}]``. Yields events:

        - ``{"type": "token", "text": str}``
        - ``{"type": "tool_start", "id", "name", "label", "args"}``
        - ``{"type": "tool_end", "id", "name", "ok", "output"}``

        Raises :class:`AIServiceError` with a user-safe message on failure.
        """
        if not self.available:
            key = "OLLAMA_API_KEY" if self._provider == "ollama" else "ANTHROPIC_API_KEY"
            raise AIServiceError(f"AI chat is not configured. Set the {key}.")
        toolbox = toolbox or Toolbox()
        if self._provider == "ollama":
            gen = self._stream_ollama(system, messages, toolbox, max_rounds)
        else:
            gen = self._stream_anthropic(system, messages, toolbox, max_rounds)
        async for event in gen:
            yield event

    async def _stream_ollama(
        self,
        system: str,
        messages: list[dict[str, str]],
        toolbox: Toolbox,
        max_rounds: int,
    ) -> AsyncIterator[dict[str, Any]]:
        headers: dict[str, str] = {}
        if self._ollama_api_key:
            headers["Authorization"] = f"Bearer {self._ollama_api_key}"
        convo: list[dict[str, Any]] = [{"role": "system", "content": system}, *messages]
        call_seq = 0

        for round_no in range(max_rounds + 1):
            # On the last round, withhold tools so the model must answer.
            offer_tools = bool(toolbox.tools) and round_no < max_rounds
            payload: dict[str, Any] = {
                "model": self._ollama_model,
                "messages": convo,
                "stream": True,
                "options": {"num_predict": self._max_tokens},
            }
            if offer_tools:
                payload["tools"] = toolbox.ollama_schemas()
            if self._ollama_think is not None:
                payload["think"] = self._ollama_think

            content_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            try:
                async with (
                    httpx.AsyncClient(
                        base_url=self._ollama_base_url, timeout=self._ollama_timeout
                    ) as client,
                    client.stream("POST", "/api/chat", json=payload, headers=headers) as resp,
                ):
                    if resp.status_code >= 400:
                        await resp.aread()
                        raise self._ollama_http_error(resp)
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except ValueError:
                            continue
                        if chunk.get("error"):
                            raise AIServiceError(f"AI service error: {chunk['error']}")
                        msg = chunk.get("message") or {}
                        text = msg.get("content") or ""
                        if text:
                            content_parts.append(text)
                            yield {"type": "token", "text": text}
                        tool_calls.extend(msg.get("tool_calls") or [])
            except httpx.TimeoutException as e:
                logger.warning("Ollama stream timed out")
                raise AIServiceError("The AI service timed out. Please try again.") from e
            except httpx.HTTPError as e:
                logger.warning("Ollama connection error: %s", e)
                raise AIServiceError(
                    "Could not connect to the AI service. "
                    f"Check that Ollama is reachable at {self._ollama_base_url}."
                ) from e

            if not tool_calls:
                if not "".join(content_parts).strip():
                    raise AIServiceError("No response generated.")
                return

            convo.append(
                {"role": "assistant", "content": "".join(content_parts), "tool_calls": tool_calls}
            )
            for call in tool_calls:
                fn = call.get("function") or {}
                name = str(fn.get("name", ""))
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {}
                call_seq += 1
                call_id = str(call.get("id") or f"call_{call_seq}")
                tool = toolbox.get(name)
                yield {
                    "type": "tool_start",
                    "id": call_id,
                    "name": name,
                    "label": (tool.label if tool and tool.label else name),
                    "args": args,
                }
                ok, output = await toolbox.run(name, args)
                yield {"type": "tool_end", "id": call_id, "name": name, "ok": ok, "output": output}
                convo.append({"role": "tool", "tool_name": name, "content": output})

    def _ollama_http_error(self, resp: httpx.Response) -> AIServiceError:
        if resp.status_code in (401, 403):
            logger.error("Ollama API authentication failed")
            return AIServiceError("AI authentication failed. Please check your OLLAMA_API_KEY.")
        if resp.status_code == 429:
            logger.warning("Ollama usage limit reached")
            return AIServiceError(
                "Ollama Cloud usage limit reached for now. "
                "Free-tier limits reset periodically - please try again later."
            )
        detail = _ollama_error_detail(resp)
        logger.error("Ollama API error %s: %s", resp.status_code, detail)
        return AIServiceError(f"AI service error: {detail}")

    async def _stream_anthropic(
        self,
        system: str,
        messages: list[dict[str, str]],
        toolbox: Toolbox,
        max_rounds: int,
    ) -> AsyncIterator[dict[str, Any]]:
        convo: list[dict[str, Any]] = list(messages)
        for round_no in range(max_rounds + 1):
            kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": self._max_tokens,
                "system": system,
                "messages": convo,
            }
            if toolbox.tools and round_no < max_rounds:
                kwargs["tools"] = toolbox.anthropic_schemas()
            try:
                async with self._client.messages.stream(**kwargs) as stream:
                    async for text in stream.text_stream:
                        yield {"type": "token", "text": text}
                    final = await stream.get_final_message()
            except anthropic.AuthenticationError as e:
                raise AIServiceError(
                    "AI authentication failed. Please check your ANTHROPIC_API_KEY."
                ) from e
            except anthropic.APIConnectionError as e:
                raise AIServiceError(
                    "Could not connect to the AI service. "
                    "Check that pxpipe proxy or the Anthropic API is reachable."
                ) from e
            except anthropic.APIError as e:
                raise AIServiceError(f"AI service error: {e.message}") from e

            uses = [b for b in final.content if b.type == "tool_use"]
            if not uses:
                return
            convo.append({"role": "assistant", "content": [b.model_dump() for b in final.content]})
            results: list[dict[str, Any]] = []
            for block in uses:
                args = dict(block.input) if isinstance(block.input, dict) else {}
                tool = toolbox.get(block.name)
                yield {
                    "type": "tool_start",
                    "id": block.id,
                    "name": block.name,
                    "label": (tool.label if tool and tool.label else block.name),
                    "args": args,
                }
                ok, output = await toolbox.run(block.name, args)
                yield {
                    "type": "tool_end",
                    "id": block.id,
                    "name": block.name,
                    "ok": ok,
                    "output": output,
                }
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                        "is_error": not ok,
                    }
                )
            convo.append({"role": "user", "content": results})


def _parse_think(value: str) -> bool | str | None:
    """Map the config string to Ollama's `think` field (bool, level, or omitted)."""
    v = value.strip().lower()
    if not v:
        return None
    if v in ("true", "false"):
        return v == "true"
    return v


def _ollama_error_detail(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error")
        if err:
            return str(err)
    except ValueError:
        pass
    return f"HTTP {resp.status_code}"
