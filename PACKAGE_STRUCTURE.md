# Package Structure Documentation

## Overview

This document describes the Python package structure for the Autosafactory GenAI project. All packages now have comprehensive `__init__.py` files with proper exports and documentation.

## Package Hierarchy

```
Autosafactory_genai/
├── src/                    # Core AUTOSAR agent functionality
│   ├── __init__.py        # ✅ Comprehensive exports
│   ├── main.py            # CLI entry point
│   ├── planner.py         # Architecture planning
│   ├── generator.py       # Code generation
│   ├── executor.py        # Code execution & verification
│   ├── fixer.py           # Error fixing
│   ├── utils.py           # Multi-provider LLM utilities
│   └── ...                # Additional modules
├── providers/             # AI provider abstractions
│   ├── __init__.py        # ✅ Well-structured exports
│   ├── base.py            # Base provider interface
│   ├── factory.py         # Provider factory
│   ├── openai_provider.py # OpenAI implementation
│   ├── anthropic_provider.py # Anthropic implementation
│   └── gemini_provider.py # Google Gemini implementation
├── autosarfactory/        # AUTOSAR ARXML library
│   ├── __init__.py        # ✅ Core function exports
│   ├── autosarfactory.py  # Main ARXML manipulation code
│   └── datatype_utils.py  # Data type utilities
└── app.py                 # Streamlit web UI entry point
```

## Package Details

### 1. `src` Package

**Purpose**: Core functionality for AUTOSAR ARXML generation using AI models.

**Key Exports**:
```python
from src import (
    # Core classes
    Planner,      # Architecture planning
    Generator,    # Code generation
    Executor,     # Code execution
    Fixer,        # Error fixing

    # Utilities
    get_llm_model,           # Get LLM instance
    load_api_key,            # Load API credentials
    get_available_providers, # Check available providers
    set_provider,            # Set active provider
    list_available_models,   # List available models
    SUPPORTED_PROVIDERS,     # Provider configuration

    # Knowledge management
    KnowledgeManager,              # API knowledge management
    get_error_feedback_manager,    # Error tracking
)
```

**Usage Example**:
```python
from src import Planner, Generator, set_provider

# Set provider
set_provider('gemini', 'gemini-2.5-pro')

# Create components
planner = Planner()
generator = Generator()

# Use them
plan = planner.create_plan("Create a CAN cluster")
code = generator.generate_code(plan)
```

### 2. `providers` Package

**Purpose**: Multi-AI provider support with unified interface.

**Key Exports**:
```python
from providers import (
    # Base classes
    AIProvider,        # Abstract provider interface
    AIResponse,        # Response wrapper
    AIProviderError,   # Error class

    # Factory
    AIProviderFactory,  # Create providers
    get_provider,       # Quick provider access

    # Implementations
    OpenAIProvider,     # OpenAI/GPT
    AnthropicProvider,  # Claude
    GeminiProvider,     # Google Gemini
)
```

**Usage Example**:
```python
from providers import AIProviderFactory

# Create provider
provider = AIProviderFactory.create(
    provider='anthropic',
    api_key='sk-...',
    model='claude-sonnet-4-20250514'
)

# Use provider
response = provider.generate("Hello, world!")
print(response.content)
```

### 3. `autosarfactory` Package

**Purpose**: AUTOSAR ARXML file creation and manipulation.

**Key Exports**:
```python
from autosarfactory import (
    # Core file operations
    read,            # Read existing ARXML
    new_file,        # Create new ARXML
    save,            # Save changes
    saveAs,          # Save to new file
    get_root,        # Get root node
    export_to_file,  # Export elements

    # Utilities
    reinit,           # Reinitialize
    get_node,         # Get node by path
    get_all_instances, # Get all instances
)
```

**Usage Example**:
```python
import autosarfactory

# Create new file
root = autosarfactory.new_file("output.arxml", defaultArPackage="Root")

# Create elements
pkg = root.new_ARPackage("System")
cluster = pkg.new_CanCluster("CAN1")

# Save
autosarfactory.save()
```

## Import Styles

### Direct Module Import
```python
# Import entire module
import src
from src import Planner, Generator

# Use it
planner = src.Planner()
generator = Generator()
```

### Submodule Import
```python
# Import from submodule
from src.planner import Planner
from src.utils import get_llm_model

# Use it
model = get_llm_model()
planner = Planner()
```

### Wildcard Import (Not Recommended)
```python
# Import everything (not recommended for production)
from src import *

# All exports from __all__ are now available
planner = Planner()
```

## Benefits of Proper Package Structure

1. **Explicit Exports**: `__all__` clearly defines public API
2. **Better IDE Support**: Autocomplete works correctly
3. **Clear Documentation**: Docstrings describe package purpose
4. **Easier Imports**: Import from package root instead of submodules
5. **Namespace Control**: Only intended exports are public
6. **Better Testing**: Easy to mock and test individual components

## Testing Imports

To verify all packages import correctly, run:

```bash
python test_imports.py
```

This will test:
- ✓ `src` package exports
- ✓ `providers` package exports
- ✓ `autosarfactory` package exports
- ✓ Individual module imports

## Dependencies

Install all dependencies with:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `google-generativeai` - For Gemini models
- `openai` - For OpenAI/GPT models
- `anthropic` - For Claude models
- `lxml` - For ARXML parsing
- `langchain` - For RAG functionality

## Migration Guide

### Before (Old Style)
```python
# Had to import from submodules
from src.planner import Planner
from src.generator import Generator
from src.executor import Executor
from src.utils import get_llm_model, set_provider
```

### After (New Style)
```python
# Can import from package root
from src import Planner, Generator, Executor, get_llm_model, set_provider
```

Both styles still work, but the new style is cleaner and more convenient.

## Best Practices

1. **Use Package-Level Imports**: Import from package root when possible
2. **Check `__all__`**: Only use exports listed in `__all__`
3. **Follow Type Hints**: Use type annotations for better IDE support
4. **Read Docstrings**: Each package has comprehensive documentation
5. **Handle Imports Gracefully**: Check for optional dependencies

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'lxml'`

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

**Problem**: `ImportError: cannot import name 'Planner' from 'src'`

**Solution**: Check that `__init__.py` exists and is not corrupted
```bash
ls -la src/__init__.py
cat src/__init__.py
```

**Problem**: IDE doesn't show autocomplete for imports

**Solution**: Reload your IDE's Python interpreter or restart the IDE

## Version History

- **2025-01-12**: Comprehensive `__init__.py` files added to all packages
  - `src/__init__.py`: Added complete exports and documentation
  - `autosarfactory/__init__.py`: Enhanced with function exports
  - `providers/__init__.py`: Already well-structured
  - Added `test_imports.py` for validation
  - Added this documentation

---

For questions or issues, please refer to the main README.md or open a GitHub issue.
