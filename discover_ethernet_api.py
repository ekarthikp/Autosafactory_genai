"""
Quick script to find correct Ethernet API pattern
"""
import autosarfactory.autosarfactory as af

print("Testing Ethernet API...")

# Test 1: Create EthernetCluster
print("\n1. Creating EthernetCluster")
try:
    # Simulate cluster creation
    print("   Methods on EthernetCluster:")
    ec_methods = [m for m in dir(af.EthernetCluster) if m.startswith('new_')]
    for m in ec_methods:
        print(f"     - {m}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Check EthernetClusterConditional
print("\n2. EthernetClusterConditional")
try:
    ecc_methods = [m for m in dir(af.EthernetClusterConditional) if m.startswith('new_') and 'channel' in m.lower()]
    print(f"   Channel methods: {ecc_methods}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Search for Physical Channel classes
print("\n3. Searching for EthernetPhysicalChannel...")
all_classes = [name for name in dir(af) if 'ethernet' in name.lower() and 'channel' in name.lower()]
print(f"   Found classes: {all_classes}")

print("\nDone!")
