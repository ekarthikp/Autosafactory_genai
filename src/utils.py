"""
Multi-Provider LLM Utilities
============================
Unified interface for multiple AI providers (Gemini, OpenAI, Anthropic).
Maintains backward compatibility with existing generate_content() interface.
"""

import os
import sys

# Add parent directory to path for provider imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Handle potential import failures gracefully
genai = None
GENAI_AVAILABLE = False
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except Exception:
    pass

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        pass

# Try to import the provider factory
PROVIDERS_AVAILABLE = False
try:
    from providers.factory import AIProviderFactory, get_provider
    from providers.base import AIProviderError, AIResponse
    PROVIDERS_AVAILABLE = True
except Exception:
    pass


# ==================== Mock Classes for Fallback ====================

class MockResponse:
    """Mock response for testing without API key."""
    def __init__(self, text):
        self.text = text


class MockModel:
    """Mock model for testing without API key."""
    def __init__(self, model_name="mock"):
        self.model_name = model_name
        self.provider_name = "mock"

    def generate_content(self, prompt):
        prompt = str(prompt).lower()

        # Logic to distinguish prompts
        if "architecture planner" in prompt:
            return MockResponse("""
```json
{
  "description": "Create a CAN System with Rx/Tx frames and signal routing.",
  "checklist": [
    "Create file 'output.arxml' with default package 'System'.",
    "Create ARPackages: 'Cluster', 'Frames', 'Signals', 'ECUs', 'Components'.",
    "Create CAN Cluster 'HS_CAN'.",
    "Create CanClusterVariant 'HS_CAN_Variant' and set baudrate to 500000.",
    "Create CanPhysicalChannel 'CAN_Channel' on the variant.",
    "Create EcuInstance 'MainECU'.",
    "Create ISignal 'RoutedSignal' (8 bits).",
    "Create ISignalIPdu 'RxPdu' and 'TxPdu'.",
    "Create CanFrame 'RxFrame' (length 8) and map 'RxPdu' to it.",
    "Create CanFrame 'TxFrame' (length 8) and map 'TxPdu' to it.",
    "Create CanFrameTriggering for RxFrame (ID 0x100) and TxFrame (ID 0x200) on the channel.",
    "Create ApplicationSwComponentType 'SignalRouter_SWC'.",
    "Save the file."
  ]
}
```
            """)
        elif "code generator" in prompt or "python script" in prompt or "fix the code" in prompt:
            return MockResponse("""
```python
import autosarfactory.autosarfactory as autosarfactory

# 1. Create file
root = autosarfactory.new_file("output.arxml", defaultArPackage="System", overWrite=True)

# 2. Packages
pkg_cluster = root.new_ARPackage("Cluster")
pkg_frames = root.new_ARPackage("Frames")
pkg_signals = root.new_ARPackage("Signals")
pkg_ecus = root.new_ARPackage("ECUs")
pkg_swc = root.new_ARPackage("Components")

# 3. Cluster
cluster = pkg_cluster.new_CanCluster("HS_CAN")
variant = cluster.new_CanClusterVariant("HS_CAN_Variant")
# set_baudrate is on the Conditional/Variant
variant.set_baudrate(500000)

# 4. Channel
channel = variant.new_CanPhysicalChannel("CAN_Channel")

# 5. ECU
ecu = pkg_ecus.new_EcuInstance("MainECU")

# 6. Signals
signal = pkg_signals.new_ISignal("RoutedSignal")
signal.set_length(8)

# 7. PDUs
rx_pdu = pkg_signals.new_ISignalIPdu("RxPdu")
rx_pdu.set_length(8)
tx_pdu = pkg_signals.new_ISignalIPdu("TxPdu")
tx_pdu.set_length(8)

# 8. Frames
rx_frame = pkg_frames.new_CanFrame("RxFrame")
rx_frame.set_frameLength(8)
# Map PDU to Frame
rx_map = rx_frame.new_PduToFrameMapping("RxMap")
rx_map.set_pdu(rx_pdu)

tx_frame = pkg_frames.new_CanFrame("TxFrame")
tx_frame.set_frameLength(8)
# Map PDU to Frame
tx_map = tx_frame.new_PduToFrameMapping("TxMap")
tx_map.set_pdu(tx_pdu)

# 9. Triggerings
rx_trig = channel.new_CanFrameTriggering("RxTrig")
rx_trig.set_frame(rx_frame)
rx_trig.set_identifier(0x100)

tx_trig = channel.new_CanFrameTriggering("TxTrig")
tx_trig.set_frame(tx_frame)
tx_trig.set_identifier(0x200)

# 10. Component
swc = pkg_swc.new_ApplicationSwComponentType("SignalRouter_SWC")

autosarfactory.save()
print("Done")
```
            """)
        else:
            # Fallback
            return MockResponse("Error: Unknown prompt type")


# ==================== Unified Model Wrapper ====================

class UnifiedModelWrapper:
    """
    Wraps any AI provider to provide a consistent generate_content() interface.
    This maintains backward compatibility with existing code that uses Gemini's API.
    """

    def __init__(self, provider_instance, provider_name="unknown", model_name="unknown"):
        """
        Initialize the wrapper with a provider instance.

        Args:
            provider_instance: An AIProvider instance from the factory
            provider_name: Name of the provider (for display)
            model_name: Name of the model (for display)
        """
        self._provider = provider_instance
        self.provider_name = provider_name
        self.model_name = model_name

    def generate_content(self, prompt):
        """
        Generate content using the wrapped provider.
        Returns a response object with a .text attribute for compatibility.

        Args:
            prompt: The prompt to send to the model

        Returns:
            An object with a .text attribute containing the response
        """
        try:
            response = self._provider.generate(prompt)
            return MockResponse(response.content)
        except Exception as e:
            print(f"   Error from {self.provider_name}: {e}")
            raise


class GeminiModelWrapper:
    """
    Wrapper for native Gemini model to maintain consistent interface.
    """

    def __init__(self, model, model_name="gemini-2.5-pro"):
        self._model = model
        self.provider_name = "gemini"
        self.model_name = model_name

    def generate_content(self, prompt):
        """Pass through to native Gemini model."""
        return self._model.generate_content(prompt)


# ==================== Provider Configuration ====================

# Supported providers and their default models
SUPPORTED_PROVIDERS = {
    'gemini': {
        'models': ['gemini-2.5-pro', 'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro'],
        'default': 'gemini-2.5-pro',
        'env_key': 'GEMINI_API_KEY'
    },
    'openai': {
        'models': ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo', 'o1-preview', 'o1-mini'],
        'default': 'gpt-4o',
        'env_key': 'OPENAI_API_KEY'
    },
    'anthropic': {
        'models': ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-haiku-20240307'],
        'default': 'claude-sonnet-4-20250514',
        'env_key': 'ANTHROPIC_API_KEY'
    }
}

# Global state for selected provider
_current_provider = None
_current_model = None


def get_available_providers():
    """
    Get list of providers that have API keys configured.

    Returns:
        Dict mapping provider names to their availability status and available models
    """
    load_dotenv()
    available = {}

    for provider, config in SUPPORTED_PROVIDERS.items():
        api_key = os.getenv(config['env_key'])
        available[provider] = {
            'available': bool(api_key),
            'models': config['models'],
            'default': config['default'],
            'env_key': config['env_key']
        }

    return available


def set_provider(provider_name, model_name=None):
    """
    Set the provider and model to use for all LLM operations.

    Args:
        provider_name: One of 'gemini', 'openai', 'anthropic'
        model_name: Specific model to use (optional, uses default if not specified)
    """
    global _current_provider, _current_model

    provider_name = provider_name.lower()
    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: {list(SUPPORTED_PROVIDERS.keys())}")

    _current_provider = provider_name
    _current_model = model_name or SUPPORTED_PROVIDERS[provider_name]['default']

    print(f"   Provider set to: {_current_provider} ({_current_model})")


def get_current_provider():
    """Get the currently selected provider and model."""
    return _current_provider, _current_model


def load_api_key(provider=None):
    """
    Load API key for the specified provider.

    Args:
        provider: Provider name (optional, uses current provider if not specified)

    Returns:
        The API key if found, or "MOCK_KEY" if not available
    """
    global _current_provider

    load_dotenv()

    # Determine which provider to use
    target_provider = provider or _current_provider or 'gemini'

    if target_provider not in SUPPORTED_PROVIDERS:
        print(f"WARNING: Unknown provider {target_provider}. Using mock LLM.")
        return "MOCK_KEY"

    env_key = SUPPORTED_PROVIDERS[target_provider]['env_key']
    api_key = os.getenv(env_key) or os.environ.get(env_key)

    if not api_key:
        print(f"WARNING: {env_key} not found. Using Mock LLM for demonstration.")
        return "MOCK_KEY"

    # For Gemini, configure the library
    if target_provider == 'gemini' and GENAI_AVAILABLE:
        genai.configure(api_key=api_key)

    return api_key


def get_llm_model(model_name=None, provider=None):
    """
    Get an LLM model instance with unified interface.

    Supports multiple providers (Gemini, OpenAI, Anthropic) while maintaining
    backward compatibility with the generate_content() interface.

    Args:
        model_name: Specific model to use (optional)
        provider: Provider to use (optional, auto-detects if not specified)

    Returns:
        A model wrapper with generate_content() method
    """
    global _current_provider, _current_model

    # Use provided values or fall back to current settings or defaults
    target_provider = provider or _current_provider
    target_model = model_name or _current_model

    # If no provider specified, try to auto-detect based on available keys
    if not target_provider:
        available = get_available_providers()

        # Priority order: gemini, openai, anthropic
        for prov in ['gemini', 'openai', 'anthropic']:
            if available[prov]['available']:
                target_provider = prov
                target_model = target_model or available[prov]['default']
                break

    # Still no provider? Use mock
    if not target_provider:
        print("WARNING: No API keys found. Using Mock LLM for demonstration.")
        return MockModel()

    # Set default model if not specified
    if not target_model:
        target_model = SUPPORTED_PROVIDERS[target_provider]['default']

    # Load API key
    api_key = load_api_key(target_provider)
    if api_key == "MOCK_KEY":
        return MockModel()

    # Create the appropriate model
    if target_provider == 'gemini':
        # Use native Gemini SDK for best performance
        if not GENAI_AVAILABLE:
            print("WARNING: google.generativeai not available. Using Mock LLM.")
            return MockModel()

        model = genai.GenerativeModel(model_name=target_model)
        return GeminiModelWrapper(model, target_model)

    elif target_provider in ['openai', 'anthropic']:
        # Use the provider factory for OpenAI and Anthropic
        if not PROVIDERS_AVAILABLE:
            print(f"WARNING: Provider factory not available. Using Mock LLM.")
            return MockModel()

        try:
            provider_instance = AIProviderFactory.create(
                provider=target_provider,
                api_key=api_key,
                model=target_model
            )
            return UnifiedModelWrapper(provider_instance, target_provider, target_model)
        except Exception as e:
            print(f"WARNING: Failed to create {target_provider} provider: {e}. Using Mock LLM.")
            return MockModel()

    else:
        print(f"WARNING: Unknown provider {target_provider}. Using Mock LLM.")
        return MockModel()


# ==================== Convenience Functions ====================

def list_available_models():
    """
    List all available models across all providers.

    Returns:
        Dict with provider info and availability status
    """
    available = get_available_providers()

    print("\n=== Available AI Providers ===")
    for provider, info in available.items():
        status = "✓ Available" if info['available'] else "✗ No API Key"
        print(f"\n{provider.upper()} ({status})")
        if info['available']:
            print(f"  Default: {info['default']}")
            print(f"  Models: {', '.join(info['models'])}")
        else:
            print(f"  Set {info['env_key']} to enable")

    return available


def quick_test_provider(provider, model=None):
    """
    Quick test to verify a provider is working.

    Args:
        provider: Provider name
        model: Model name (optional)

    Returns:
        True if provider is working, False otherwise
    """
    try:
        set_provider(provider, model)
        llm = get_llm_model()
        response = llm.generate_content("Say 'Hello' and nothing else.")
        print(f"   Response: {response.text[:100]}...")
        return True
    except Exception as e:
        print(f"   Error: {e}")
        return False
