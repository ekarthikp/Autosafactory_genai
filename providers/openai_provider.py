"""
OpenAI AI Provider
===================
Implementation for OpenAI models (GPT-4, GPT-3.5, etc.)
"""

import logging
from typing import Optional, List, Dict, Any

from .base import (
    AIProvider,
    AIResponse,
    ProviderConfig,
    ProviderType,
    AIProviderError,
    RateLimitError,
    AuthenticationError,
    ModelNotFoundError
)

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """
    OpenAI AI Provider.

    Supports models:
    - gpt-4o (latest)
    - gpt-4-turbo
    - gpt-4
    - gpt-3.5-turbo
    - o1-preview
    - o1-mini
    """

    DEFAULT_MODEL = "gpt-4o"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI

    @property
    def name(self) -> str:
        return "OpenAI"

    def initialize(self) -> None:
        """Initialize the OpenAI client"""
        self._validate_config()

        try:
            from openai import OpenAI

            client_kwargs = {
                "api_key": self.config.api_key,
                "timeout": self.config.timeout_seconds,
            }

            if self.config.base_url:
                client_kwargs["base_url"] = self.config.base_url

            self._client = OpenAI(**client_kwargs)
            self._initialized = True

            logger.info(f"OpenAI provider initialized with model: {self.config.model}")

        except ImportError:
            raise AIProviderError(
                "openai package not installed. "
                "Install with: pip install openai",
                provider=self.name
            )
        except Exception as e:
            self._handle_error(e)

    def generate(self, prompt: str, **kwargs) -> AIResponse:
        """Generate content using OpenAI"""
        if not self._initialized:
            self.initialize()

        messages = [{"role": "user", "content": prompt}]
        return self._create_completion(messages, **kwargs)

    def generate_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> AIResponse:
        """Generate with system prompt"""
        if not self._initialized:
            self.initialize()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return self._create_completion(messages, **kwargs)

    def _create_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AIResponse:
        """Create a chat completion"""
        try:
            model = kwargs.get('model', self.config.model or self.DEFAULT_MODEL)

            completion_kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": kwargs.get('max_tokens', self.config.max_tokens),
                "temperature": kwargs.get('temperature', self.config.temperature),
            }

            # Add any extra parameters
            completion_kwargs.update(self.config.extra_params)

            response, latency = self._measure_latency(
                self._client.chat.completions.create,
                **completion_kwargs
            )

            return self._parse_response(response, latency)

        except Exception as e:
            self._handle_error(e)

    def _parse_response(self, response, latency: float) -> AIResponse:
        """Parse OpenAI response to standard format"""
        choice = response.choices[0] if response.choices else None

        content = choice.message.content if choice else ""
        finish_reason = choice.finish_reason if choice else None

        usage = {}
        if response.usage:
            usage = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens,
            }

        return AIResponse(
            content=content,
            model=response.model,
            provider=self.name,
            usage=usage,
            finish_reason=finish_reason,
            latency_ms=latency,
            raw_response=response
        )

    def _handle_error(self, error: Exception) -> None:
        """Handle OpenAI-specific errors"""
        error_type = type(error).__name__
        error_str = str(error).lower()

        if 'ratelimit' in error_type.lower() or 'rate_limit' in error_str:
            raise RateLimitError(
                f"OpenAI rate limit exceeded: {error}",
                provider=self.name,
                retry_after=60.0
            )
        elif 'authentication' in error_type.lower() or 'api key' in error_str:
            raise AuthenticationError(
                f"OpenAI authentication failed: {error}",
                provider=self.name
            )
        elif 'notfound' in error_type.lower() or 'model' in error_str:
            raise ModelNotFoundError(
                f"OpenAI model not found: {error}",
                provider=self.name
            )
        else:
            raise AIProviderError(
                f"OpenAI error: {error}",
                provider=self.name
            )
