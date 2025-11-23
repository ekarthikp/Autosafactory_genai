"""
AI Provider Factory
====================
Factory for creating AI provider instances with unified interface.
"""

import os
import logging
from typing import Optional, Dict, Any, Type

from .base import AIProvider, ProviderConfig, ProviderType, AIProviderError
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


class AIProviderFactory:
    """
    Factory for creating AI provider instances.

    Supports automatic configuration from environment variables.
    """

    # Provider registry
    _providers: Dict[str, Type[AIProvider]] = {
        'openai': OpenAIProvider,
        'anthropic': AnthropicProvider,
        'claude': AnthropicProvider,  # Alias
        'gemini': GeminiProvider,
        'google': GeminiProvider,  # Alias
    }

    # Environment variable names for API keys
    _env_keys: Dict[str, str] = {
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'claude': 'ANTHROPIC_API_KEY',
        'gemini': 'GEMINI_API_KEY',
        'google': 'GEMINI_API_KEY',
    }

    # Default models for each provider
    _default_models: Dict[str, str] = {
        'openai': 'gpt-4o',
        'anthropic': 'claude-sonnet-4-20250514',
        'claude': 'claude-sonnet-4-20250514',
        'gemini': 'gemini-2.5-pro',
        'google': 'gemini-2.5-pro',
    }

    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_class: Type[AIProvider],
        env_key: str = None,
        default_model: str = None
    ) -> None:
        """
        Register a custom AI provider.

        Args:
            name: Provider name (used in configuration)
            provider_class: The provider class
            env_key: Environment variable name for API key
            default_model: Default model name
        """
        cls._providers[name.lower()] = provider_class
        if env_key:
            cls._env_keys[name.lower()] = env_key
        if default_model:
            cls._default_models[name.lower()] = default_model

        logger.info(f"Registered custom provider: {name}")

    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str = None,
        model: str = None,
        **kwargs
    ) -> AIProvider:
        """
        Create an AI provider instance.

        Args:
            provider: Provider name ('openai', 'anthropic', 'gemini')
            api_key: API key (optional, will use env var if not provided)
            model: Model name (optional, will use default if not provided)
            **kwargs: Additional configuration parameters

        Returns:
            Configured AIProvider instance
        """
        provider_lower = provider.lower()

        if provider_lower not in cls._providers:
            available = ', '.join(cls._providers.keys())
            raise AIProviderError(
                f"Unknown provider: {provider}. Available: {available}",
                provider=provider
            )

        # Get API key from environment if not provided
        if not api_key:
            env_var = cls._env_keys.get(provider_lower)
            if env_var:
                api_key = os.getenv(env_var)

            if not api_key:
                raise AIProviderError(
                    f"API key not provided for {provider}. "
                    f"Set {env_var} environment variable or pass api_key parameter.",
                    provider=provider
                )

        # Get default model if not provided
        if not model:
            model = cls._default_models.get(provider_lower)

        # Build configuration
        config = ProviderConfig(
            api_key=api_key,
            model=model,
            max_tokens=kwargs.get('max_tokens', 8192),
            temperature=kwargs.get('temperature', 0.1),
            timeout_seconds=kwargs.get('timeout_seconds', 60),
            retry_count=kwargs.get('retry_count', 3),
            retry_delay=kwargs.get('retry_delay', 1.0),
            base_url=kwargs.get('base_url'),
            extra_params=kwargs.get('extra_params', {})
        )

        # Create and initialize provider
        provider_class = cls._providers[provider_lower]
        provider_instance = provider_class(config)
        provider_instance.initialize()

        logger.info(f"Created {provider} provider with model: {model}")
        return provider_instance

    @classmethod
    def create_from_env(cls, prefer: str = None) -> AIProvider:
        """
        Create a provider using available environment variables.

        Will try providers in order of preference until one succeeds.

        Args:
            prefer: Preferred provider (will try first)

        Returns:
            First successfully created provider
        """
        # Order of preference
        providers_to_try = ['gemini', 'openai', 'anthropic']

        if prefer and prefer.lower() in cls._providers:
            providers_to_try.insert(0, prefer.lower())
            # Remove duplicate if present
            providers_to_try = list(dict.fromkeys(providers_to_try))

        errors = []

        for provider_name in providers_to_try:
            env_var = cls._env_keys.get(provider_name)
            if env_var and os.getenv(env_var):
                try:
                    return cls.create(provider_name)
                except AIProviderError as e:
                    errors.append(f"{provider_name}: {e}")
                    continue

        # No provider available
        error_details = '\n'.join(errors) if errors else "No API keys found in environment"
        raise AIProviderError(
            f"Could not create any AI provider.\n{error_details}",
            provider="factory"
        )

    @classmethod
    def list_providers(cls) -> Dict[str, Dict[str, Any]]:
        """List all available providers with their configuration"""
        providers = {}
        for name, provider_class in cls._providers.items():
            providers[name] = {
                'class': provider_class.__name__,
                'env_key': cls._env_keys.get(name),
                'default_model': cls._default_models.get(name),
                'available': bool(os.getenv(cls._env_keys.get(name, '')))
            }
        return providers


def get_provider(
    provider: str = None,
    api_key: str = None,
    model: str = None,
    **kwargs
) -> AIProvider:
    """
    Convenience function to get an AI provider.

    If provider is not specified, will auto-detect from environment.

    Args:
        provider: Provider name (optional)
        api_key: API key (optional)
        model: Model name (optional)
        **kwargs: Additional configuration

    Returns:
        Configured AIProvider instance
    """
    if provider:
        return AIProviderFactory.create(provider, api_key, model, **kwargs)
    else:
        return AIProviderFactory.create_from_env()
