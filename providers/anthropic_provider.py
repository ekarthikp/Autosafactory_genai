"""
Anthropic Claude AI Provider
=============================
Implementation for Anthropic's Claude models.
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


class AnthropicProvider(AIProvider):
    """
    Anthropic Claude AI Provider.

    Supports models:
    - claude-sonnet-4-20250514 (latest)
    - claude-3-5-sonnet-20241022
    - claude-3-5-haiku-20241022
    - claude-3-opus-20240229
    - claude-3-sonnet-20240229
    - claude-3-haiku-20240307
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC

    @property
    def name(self) -> str:
        return "Anthropic Claude"

    def initialize(self) -> None:
        """Initialize the Anthropic client"""
        self._validate_config()

        try:
            import anthropic

            client_kwargs = {
                "api_key": self.config.api_key,
                "timeout": self.config.timeout_seconds,
            }

            if self.config.base_url:
                client_kwargs["base_url"] = self.config.base_url

            self._client = anthropic.Anthropic(**client_kwargs)
            self._initialized = True

            logger.info(f"Anthropic provider initialized with model: {self.config.model}")

        except ImportError:
            raise AIProviderError(
                "anthropic package not installed. "
                "Install with: pip install anthropic",
                provider=self.name
            )
        except Exception as e:
            self._handle_error(e)

    def generate(self, prompt: str, **kwargs) -> AIResponse:
        """Generate content using Claude"""
        if not self._initialized:
            self.initialize()

        messages = [{"role": "user", "content": prompt}]
        return self._create_message(messages, **kwargs)

    def generate_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> AIResponse:
        """Generate with system prompt"""
        if not self._initialized:
            self.initialize()

        messages = [{"role": "user", "content": user_prompt}]
        return self._create_message(messages, system=system_prompt, **kwargs)

    def _create_message(
        self,
        messages: List[Dict[str, str]],
        system: str = None,
        **kwargs
    ) -> AIResponse:
        """Create a message using Claude"""
        try:
            model = kwargs.get('model', self.config.model or self.DEFAULT_MODEL)

            message_kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": kwargs.get('max_tokens', self.config.max_tokens),
            }

            # Add system prompt if provided
            if system:
                message_kwargs["system"] = system

            # Temperature (Claude uses 0-1 range)
            temperature = kwargs.get('temperature', self.config.temperature)
            if temperature is not None:
                message_kwargs["temperature"] = temperature

            # Add any extra parameters
            message_kwargs.update(self.config.extra_params)

            response, latency = self._measure_latency(
                self._client.messages.create,
                **message_kwargs
            )

            return self._parse_response(response, latency)

        except Exception as e:
            self._handle_error(e)

    def _parse_response(self, response, latency: float) -> AIResponse:
        """Parse Claude response to standard format"""
        # Extract content from response
        content = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text

        usage = {}
        if response.usage:
            usage = {
                'prompt_tokens': response.usage.input_tokens,
                'completion_tokens': response.usage.output_tokens,
                'total_tokens': response.usage.input_tokens + response.usage.output_tokens,
            }

        return AIResponse(
            content=content,
            model=response.model,
            provider=self.name,
            usage=usage,
            finish_reason=response.stop_reason,
            latency_ms=latency,
            raw_response=response
        )

    def _handle_error(self, error: Exception) -> None:
        """Handle Anthropic-specific errors"""
        error_type = type(error).__name__
        error_str = str(error).lower()

        if 'ratelimit' in error_type.lower() or 'rate' in error_str:
            raise RateLimitError(
                f"Anthropic rate limit exceeded: {error}",
                provider=self.name,
                retry_after=60.0
            )
        elif 'authentication' in error_type.lower() or 'api key' in error_str or 'invalid' in error_str:
            raise AuthenticationError(
                f"Anthropic authentication failed: {error}",
                provider=self.name
            )
        elif 'notfound' in error_type.lower() or 'model' in error_str:
            raise ModelNotFoundError(
                f"Anthropic model not found: {error}",
                provider=self.name
            )
        else:
            raise AIProviderError(
                f"Anthropic error: {error}",
                provider=self.name
            )
