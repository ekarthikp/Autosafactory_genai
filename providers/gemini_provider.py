"""
Google Gemini AI Provider
==========================
Implementation for Google's Gemini models.
"""

import logging
from typing import Optional, Dict, Any

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


class GeminiProvider(AIProvider):
    """
    Google Gemini AI Provider.

    Supports models:
    - gemini-2.5-pro (latest)
    - gemini-1.5-pro
    - gemini-1.5-flash
    - gemini-pro
    """

    DEFAULT_MODEL = "gemini-2.5-pro"

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GEMINI

    @property
    def name(self) -> str:
        return "Google Gemini"

    def initialize(self) -> None:
        """Initialize the Gemini client"""
        self._validate_config()

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.config.api_key)

            generation_config = {
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens,
            }

            self._client = genai.GenerativeModel(
                model_name=self.config.model or self.DEFAULT_MODEL,
                generation_config=generation_config
            )
            self._chat = None
            self._initialized = True

            logger.info(f"Gemini provider initialized with model: {self.config.model}")

        except ImportError:
            raise AIProviderError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai",
                provider=self.name
            )
        except Exception as e:
            self._handle_error(e)

    def generate(self, prompt: str, **kwargs) -> AIResponse:
        """Generate content using Gemini"""
        if not self._initialized:
            self.initialize()

        try:
            response, latency = self._measure_latency(
                self._client.generate_content,
                prompt
            )

            return self._parse_response(response, latency)

        except Exception as e:
            self._handle_error(e)

    def generate_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> AIResponse:
        """Generate with system prompt (combined for Gemini)"""
        if not self._initialized:
            self.initialize()

        # Gemini handles system prompts differently
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"

        try:
            response, latency = self._measure_latency(
                self._client.generate_content,
                combined_prompt
            )

            return self._parse_response(response, latency)

        except Exception as e:
            self._handle_error(e)

    def start_chat(self, history: list = None) -> 'GeminiProvider':
        """Start a chat session"""
        if not self._initialized:
            self.initialize()

        self._chat = self._client.start_chat(history=history or [])
        return self

    def send_message(self, message: str) -> AIResponse:
        """Send a message in chat mode"""
        if self._chat is None:
            self.start_chat()

        try:
            response, latency = self._measure_latency(
                self._chat.send_message,
                message
            )

            return self._parse_response(response, latency)

        except Exception as e:
            self._handle_error(e)

    def _parse_response(self, response, latency: float) -> AIResponse:
        """Parse Gemini response to standard format"""
        content = ""
        finish_reason = None

        if hasattr(response, 'text'):
            content = response.text
        elif hasattr(response, 'parts'):
            content = "".join(part.text for part in response.parts if hasattr(part, 'text'))

        # Extract usage info if available
        usage = {}
        if hasattr(response, 'usage_metadata'):
            usage = {
                'prompt_tokens': getattr(response.usage_metadata, 'prompt_token_count', 0),
                'completion_tokens': getattr(response.usage_metadata, 'candidates_token_count', 0),
                'total_tokens': getattr(response.usage_metadata, 'total_token_count', 0),
            }

        if hasattr(response, 'candidates') and response.candidates:
            finish_reason = str(response.candidates[0].finish_reason) if hasattr(response.candidates[0], 'finish_reason') else None

        return AIResponse(
            content=content,
            model=self.config.model or self.DEFAULT_MODEL,
            provider=self.name,
            usage=usage,
            finish_reason=finish_reason,
            latency_ms=latency,
            raw_response=response
        )

    def _handle_error(self, error: Exception) -> None:
        """Handle Gemini-specific errors"""
        error_str = str(error).lower()

        if 'quota' in error_str or 'rate' in error_str:
            raise RateLimitError(
                f"Gemini rate limit exceeded: {error}",
                provider=self.name,
                retry_after=60.0
            )
        elif 'api key' in error_str or 'authentication' in error_str or 'invalid' in error_str:
            raise AuthenticationError(
                f"Gemini authentication failed: {error}",
                provider=self.name
            )
        elif 'model' in error_str and 'not found' in error_str:
            raise ModelNotFoundError(
                f"Gemini model not found: {error}",
                provider=self.name
            )
        else:
            raise AIProviderError(
                f"Gemini error: {error}",
                provider=self.name
            )
