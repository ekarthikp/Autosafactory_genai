"""
Discovery script for Composition and S2S methods
"""
import autosarfactory.autosarfactory as af

print("="*50)
print("COMPOSITION METHODS")
print("="*50)
try:
    c = af.CompositionSwComponentType
    methods = [m for m in dir(c) if m.startswith('new_')]
    print(f"new_* methods on CompositionSwComponentType:\n{methods}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*50)
print("S2S METHODS")
print("="*50)
try:
    sste = af.SignalServiceTranslationEventProps
    methods = [m for m in dir(sste) if 'create_ref' in m]
    print(f"create_ref_* methods on SignalServiceTranslationEventProps:\n{methods}")
except Exception as e:
    print(f"Error: {e}")

try:
    srtos = af.SenderReceiverToSignalMapping
    methods = [m for m in dir(srtos) if 'create_ref' in m]
    print(f"create_ref_* methods on SenderReceiverToSignalMapping:\n{methods}")
except Exception as e:
    print(f"Error: {e}")
    
print("\n" + "="*50)
print("INSTANCE REF METHODS")
print("="*50)
try:
    # Check if there's a generic InstanceRef class
    print("Checking for InstanceRef classes...")
    instance_refs = [c for c in dir(af) if 'InstanceRef' in c]
    print(f"Found classes: {instance_refs[:10]}...")
except Exception as e:
    print(f"Error: {e}")
