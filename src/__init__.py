"""
AUTOSAR Architecture Agent - Core Module
=========================================
Core functionality for ARXML generation using AI models.

This module provides:
- Planning: AUTOSAR architecture planning and task decomposition
- Generation: Python code generation for ARXML creation
- Execution: Code execution and ARXML verification
- Fixing: Automated error detection and code repair
- Utilities: Multi-provider LLM support and configuration
"""

# Core components
from .planner import Planner
from .generator import Generator
from .executor import Executor
from .fixer import Fixer

# Utilities
from .utils import (
    get_llm_model,
    load_api_key,
    get_available_providers,
    set_provider,
    get_current_provider,
    list_available_models,
    SUPPORTED_PROVIDERS,
)

# Knowledge management
from .knowledge_manager import KnowledgeManager

# Error feedback system
from .error_feedback_manager import get_error_feedback_manager

# API validation
from .api_validator import APIValidator, get_api_validator

__all__ = [
    # Core classes
    'Planner',
    'Generator',
    'Executor',
    'Fixer',

    # Utilities
    'get_llm_model',
    'load_api_key',
    'get_available_providers',
    'set_provider',
    'get_current_provider',
    'list_available_models',
    'SUPPORTED_PROVIDERS',

    # Knowledge management
    'KnowledgeManager',
    'get_error_feedback_manager',

    # API validation
    'APIValidator',
    'get_api_validator',
]
