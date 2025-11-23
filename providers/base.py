"""
Base AI Provider Interface
===========================
Abstract base class for all AI providers with common interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import time


class AIProviderError(Exception):
    """Base exception for AI provider errors"""

    def __init__(self, message: str, provider: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.provider = provider
        self.retry_after = retry_after


class RateLimitError(AIProviderError):
    """Rate limit exceeded"""
    pass


class AuthenticationError(AIProviderError):
    """Authentication failed"""
    pass


class ModelNotFoundError(AIProviderError):
    """Model not found or not accessible"""
    pass


class ProviderType(Enum):
    """Supported AI providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    CUSTOM = "custom"


@dataclass
class AIResponse:
    """Standardized response from AI providers"""
    content: str
    model: str
    provider: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    latency_ms: float = 0.0
    raw_response: Optional[Any] = None

    @property
    def token_count(self) -> int:
        """Total tokens used"""
        return self.usage.get('total_tokens', 0)

    @property
    def prompt_tokens(self) -> int:
        """Prompt tokens used"""
        return self.usage.get('prompt_tokens', 0)

    @property
    def completion_tokens(self) -> int:
        """Completion tokens used"""
        return self.usage.get('completion_tokens', 0)


@dataclass
class ProviderConfig:
    """Configuration for AI providers"""
    api_key: str
    model: str
    max_tokens: int = 8192
    temperature: float = 0.1
    timeout_seconds: int = 60
    retry_count: int = 3
    retry_delay: float = 1.0
    base_url: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    All AI providers must implement this interface to ensure
    consistent behavior across different LLM services.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._initialized = False
        self._client = None

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-readable provider name"""
        pass

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the provider client"""
        pass

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> AIResponse:
        """
        Generate a response from the AI model.

        Args:
            prompt: The input prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            AIResponse with the generated content
        """
        pass

    @abstractmethod
    def generate_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> AIResponse:
        """
        Generate a response with a system prompt.

        Args:
            system_prompt: The system/instruction prompt
            user_prompt: The user's input
            **kwargs: Additional provider-specific parameters

        Returns:
            AIResponse with the generated content
        """
        pass

    def health_check(self) -> bool:
        """Check if the provider is healthy and responsive"""
        try:
            response = self.generate("Reply with 'ok'")
            return len(response.content) > 0
        except Exception:
            return False

    def _measure_latency(self, func, *args, **kwargs) -> tuple:
        """Measure latency of a function call"""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        latency = (time.perf_counter() - start) * 1000
        return result, latency

    def _validate_config(self) -> None:
        """Validate provider configuration"""
        if not self.config.api_key:
            raise AuthenticationError(
                f"API key not provided for {self.name}",
                provider=self.name
            )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(model={self.config.model})>"
