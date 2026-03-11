from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


class ProviderError(RuntimeError):
    pass


class LLMProvider(Protocol):
    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        ...


def _compose_prompt(prompt: str, context: list[str] | None = None) -> str:
    history = context or []
    if not history:
        return prompt.strip()
    relevant = [item.strip() for item in history[-12:] if item and item.strip()]
    if not relevant:
        return prompt.strip()
    return f"Conversation context:\n" + "\n".join(relevant) + f"\n\nUser message:\n{prompt.strip()}"


def _safe_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


@dataclass
class LocalReasoningProvider:
    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        text = prompt.strip()
        history = [item.strip() for item in (context or []) if item and item.strip()]
        if not text and not history:
            return "No input received."

        if text.lower().startswith("question:") and "context:" in text.lower():
            question_part, _, context_part = text.partition("Context:")
            question = question_part.replace("Question:", "", 1).strip()
            chunks = [chunk.strip() for chunk in context_part.split("|") if chunk.strip()]
            if chunks:
                top = chunks[0]
                return f"Answer based on retrieved context: {top}\nQuestion: {question}"
            return f"No indexed context available yet for: {question}"

        if history:
            memory_tail = " | ".join(history[-4:])
            return f"{text}\n\nContext-aware summary: {memory_tail}"
        return text


@dataclass
class OpenAIProvider:
    api_key: str
    model: str
    base_url: str
    timeout: float

    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        if not self.api_key.strip():
            raise ProviderError("OPENAI_API_KEY is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an accurate backend AI agent. Keep outputs concise and factual.",
                },
                {
                    "role": "user",
                    "content": _compose_prompt(prompt, context),
                },
            ],
            "temperature": 0.2,
        }
        url = self.base_url.rstrip("/") + "/chat/completions"
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=max(1.0, self.timeout),
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"OpenAI request failed: {exc}") from exc

        choices = data.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise ProviderError("OpenAI response missing choices")
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    txt = _safe_text(item.get("text"))
                    if txt:
                        parts.append(txt)
            if parts:
                return "\n".join(parts)
        raise ProviderError("OpenAI response missing content")


@dataclass
class AnthropicProvider:
    api_key: str
    model: str
    base_url: str
    timeout: float

    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        if not self.api_key.strip():
            raise ProviderError("ANTHROPIC_API_KEY is not configured")

        payload = {
            "model": self.model,
            "max_tokens": 512,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": _compose_prompt(prompt, context),
                }
            ],
        }
        url = self.base_url.rstrip("/") + "/v1/messages"
        try:
            response = httpx.post(
                url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=max(1.0, self.timeout),
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        content = data.get("content", [])
        if not isinstance(content, list):
            raise ProviderError("Anthropic response missing content")
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            txt = _safe_text(item.get("text"))
            if txt:
                parts.append(txt)
        if parts:
            return "\n".join(parts)
        raise ProviderError("Anthropic response had no text blocks")


@dataclass
class GoogleGeminiProvider:
    api_key: str
    model: str
    base_url: str
    timeout: float

    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        if not self.api_key.strip():
            raise ProviderError("GOOGLE_API_KEY is not configured")

        url = self.base_url.rstrip("/") + f"/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": _compose_prompt(prompt, context),
                        }
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.2},
        }

        try:
            response = httpx.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=max(1.0, self.timeout),
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"Google request failed: {exc}") from exc

        candidates = data.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            raise ProviderError("Google response missing candidates")
        content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        if not isinstance(parts, list):
            raise ProviderError("Google response missing content parts")
        texts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            txt = _safe_text(part.get("text"))
            if txt:
                texts.append(txt)
        if texts:
            return "\n".join(texts)
        raise ProviderError("Google response had no text parts")


@dataclass
class OllamaProvider:
    model: str
    base_url: str
    timeout: float

    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an accurate backend AI agent. Keep outputs concise and factual.",
                },
                {
                    "role": "user",
                    "content": _compose_prompt(prompt, context),
                },
            ],
            "stream": False,
        }
        url = self.base_url.rstrip("/") + "/api/chat"
        try:
            response = httpx.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=max(1.0, self.timeout),
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc

        message = data.get("message", {})
        content = message.get("content") if isinstance(message, dict) else ""
        text = _safe_text(content)
        if text:
            return text
        raise ProviderError("Ollama response missing content")

