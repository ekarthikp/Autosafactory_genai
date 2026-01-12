# Multi-Protocol Support for AUTOSAR

## Overview

The Autosafactory GenAI system now has **comprehensive support** for multiple AUTOSAR communication protocols and advanced features. All APIs are present in the 1.8MB knowledge_graph.json, and the system has been enhanced to automatically select the correct classes based on your requirements.

## Supported Protocols & Features

### ✅ 1. **CAN (Controller Area Network)**
**Status**: Fully Supported ✓

**Available Classes**: 30+
- `CanCluster`, `CanClusterVariant`, `CanClusterConditional`
- `CanPhysicalChannel`, `CanFrame`, `CanFrameTriggering`
- `CanCommunicationController`, `CanCommunicationConnector`

**Use Cases**:
- Standard CAN networks (125kbps - 1Mbps)
- Frame configuration with DLC
- Signal mapping to frames
- ECU communication setup

**Example Request**:
```
"Create CAN cluster at 500kbps with frame ID 0x100 containing uint16 signal"
```

---

### ✅ 2. **CAN-FD (CAN with Flexible Data-Rate)**
**Status**: Configuration Support ✓

**Available Classes**: 2
- `CanControllerFdConfiguration`
- `CanControllerFdConfigurationRequirements`

**Use Cases**:
- High-speed CAN with data rates up to 8Mbps
- Extended payload (up to 64 bytes)
- FD configuration for CAN controllers

**Example Request**:
```
"Configure CAN-FD controller with 2Mbps data rate and 64-byte payload"
```

**Note**: Basic CAN-FD controller configuration supported. Full frame/signal support uses standard CAN classes.

---

### ✅ 3. **LIN (Local Interconnect Network)**
**Status**: Fully Supported ✓

**Available Classes**: 30+
- `LinCluster`, `LinClusterConditional`, `LinPhysicalChannel`
- `LinFrame`, `LinUnconditionalFrame`, `LinEventTriggeredFrame`
- `LinFrameTriggering`, `LinScheduleTable`
- `LinMaster`, `LinMasterConditional`, `LinSlave`, `LinSlaveConfig`

**Use Cases**:
- LIN 2.x networks (typically 19.2kbps)
- Master-slave topology configuration
- Schedule table setup
- Unconditional and event-triggered frames
- Slave node configuration

**Example Request**:
```
"Create LIN cluster at 19.2kbps with master ECU and 3 slave nodes.
 Configure schedule table with unconditional frame containing temperature signal."
```

---

### ✅ 4. **Ethernet & SOME/IP**
**Status**: Fully Supported ✓

**Available Classes**: 79+
- **Ethernet**: `EthernetCluster`, `EthernetClusterConditional`, `EthernetPhysicalChannel`
- **Frames**: `EthernetFrame`, `EthernetFrameTriggering`
- **SOME/IP**: `SomeipServiceInterface`, `SomeipServiceInterfaceDeployment`
- **Service Instances**: `ProvidedSomeipServiceInstance`, `RequiredSomeipServiceInstance`
- **Events**: `SomeipEventDeployment`, `SomeipEventGroup`

**Use Cases**:
- Ethernet-based automotive networks (100Mbps/1Gbps)
- SOME/IP service-oriented communication
- Event-based communication
- Method calls and field notifications
- Service discovery

**Example Request**:
```
"Create Ethernet cluster with SOME/IP service interface.
 Service provides temperature event at 100ms period.
 Consumer SWC subscribes to this event."
```

---

### ✅ 5. **FlexRay**
**Status**: Fully Supported ✓

**Available Classes**: 40+
- `FlexrayCluster`, `FlexrayClusterConditional`
- `FlexrayPhysicalChannel`
- `FlexrayFrame`, `FlexrayFrameTriggering`

**Use Cases**:
- High-speed deterministic communication (10Mbps)
- Static and dynamic segments
- Dual-channel redundancy
- Time-triggered frames

**Example Request**:
```
"Create FlexRay cluster with 10Mbps, static segment frame with ID 5"
```

---

### ✅ 6. **Signal-to-Service Translation** 🔥
**Status**: Fully Supported ✓

**Available Classes**: 56+
- `SignalServiceTranslationProps`
- `SignalServiceTranslationEventProps`
- `SignalServiceTranslationElementProps`
- `SignalServiceTranslationControlEnum`
- `ServiceInstanceToSignalMapping`

**Use Cases**:
- **Signal → Service**: CAN/LIN signals translated to SOME/IP service events
- **Service → Signal**: SOME/IP service events translated to CAN/LIN signals
- Gateway ECU bridging Classic and Adaptive platforms
- Safety/security transformations during translation
- PNC (Partial Networking) control

**Example Request**:
```
"Create gateway ECU that receives CAN signal 'VehicleSpeed' at 500kbps
 and translates it to SOME/IP service event on Ethernet.
 Include signal-to-service translation with safe transformation."
```

**Key Features**:
- One-to-one or complex element mappings
- Safe translation mode
- Secure translation mode
- Service control (automatic, translation-start, etc.)
- PNC mapping for service availability

**From AUTOSAR TPS Documentation** (domain_knowledge.txt):
```
Signal/service translation is used to alter the serialization representation
of data to be compatible with the respective transport network. On Ethernet,
SOME/IP serialized data is suitable, while on CAN, packed signal-based
representation is required due to low payload size.

The implementation is done in an Application Software Component above the RTE.
For signal-based side, full COM-Stack functionality is available (CAN, LIN,
FlexRay sources). For service-oriented side, SOME/IP compatibility with
Adaptive platform is guaranteed.
```

---

## How It Works

### 1. **Automatic Class Detection**

When you request a protocol, the system automatically identifies relevant classes:

```python
# User request: "LIN cluster with master and slave"
# System automatically identifies:
- LinCluster
- LinClusterConditional
- LinPhysicalChannel
- LinMaster
- LinMasterConditional
- LinSlave
- LinSlaveConditional
# + all related signal/frame classes
```

### 2. **API Validation**

The APIValidator ensures correct method usage for each protocol:

```python
# Validates that:
lin_cluster.new_LinPhysicalChannel()  # ✓ Valid
lin_cluster.new_CanPhysicalChannel()  # ✗ Wrong protocol!
ethernet_cluster.new_SomeipServiceInterface()  # ✓ Valid
```

### 3. **Precise API Context**

For each protocol, you get exact API signatures:

```
## LinCluster
   Factory Methods:
      new_LinPhysicalChannel(name: str) -> LinPhysicalChannel

## LinPhysicalChannel
   Factory Methods:
      new_LinFrame(name: str) -> LinFrame
      new_LinUnconditionalFrame(name: str) -> LinUnconditionalFrame
      new_LinFrameTriggering(name: str) -> LinFrameTriggering
```

---

## Usage Examples

### Example 1: Multi-Protocol Gateway

```
"Create a gateway ECU with:
- CAN cluster at 500kbps receiving 'EngineSpeed' signal
- LIN cluster at 19.2kbps receiving 'DoorStatus' signal
- Ethernet cluster at 100Mbps
- Signal-to-service translation for both signals to SOME/IP events
- Application SWC that processes translated data"
```

**System will create**:
- 3 clusters (CAN, LIN, Ethernet)
- 2 signal paths (CAN signal, LIN signal)
- Signal-to-service translation configuration
- SOME/IP service interface with 2 events
- Application SWC with service consumer port
- Complete routing and mapping

---

### Example 2: Advanced LIN Network

```
"Create LIN master with schedule table:
- 19.2kbps baudrate
- 3 slave nodes (Node1, Node2, Node3)
- Unconditional frame 'StatusFrame' every 10ms with 8 signals
- Event-triggered frame 'ErrorFrame' from slaves
- Master publishes consolidated status via P-port"
```

**System will create**:
- LinCluster with LinMaster
- 3 LinSlave configurations
- LinScheduleTable with timing
- LinUnconditionalFrame with 8 signals
- LinEventTriggeredFrame
- ApplicationSwComponentType with P-port
- Internal behavior to process LIN data

---

### Example 3: Ethernet SOME/IP Service

```
"Create SOME/IP temperature monitoring service:
- Ethernet cluster at 100Mbps
- Service interface 'TemperatureService' with:
  * Event 'TemperatureChanged' (float32)
  * Method 'GetCurrentTemp' returns float32
- Provider SWC that publishes temperature at 100ms
- Consumer SWC that subscribes to temperature events"
```

**System will create**:
- EthernetCluster and EthernetPhysicalChannel
- SomeipServiceInterface with event and method
- SomeipServiceInterfaceDeployment
- ProvidedSomeipServiceInstance (provider side)
- RequiredSomeipServiceInstance (consumer side)
- Provider ApplicationSwComponentType with P-port
- Consumer ApplicationSwComponentType with R-port
- Runnable with 100ms TimingEvent

---

## Protocol Comparison

| Protocol | Speed | Topology | Use Case | Complexity |
|----------|-------|----------|----------|------------|
| **CAN** | 125Kbps-1Mbps | Bus | Body, powertrain | Low |
| **CAN-FD** | Up to 8Mbps | Bus | High-speed body/chassis | Medium |
| **LIN** | 2.4-19.2Kbps | Master-Slave | Low-cost sensors/actuators | Low |
| **FlexRay** | 10Mbps | Star/Bus | Safety-critical, X-by-wire | High |
| **Ethernet** | 100Mbps-1Gbps | Switched | Infotainment, ADAS | Medium |
| **SOME/IP** | (over Ethernet) | Service-Oriented | Adaptive platform services | High |

---

## Signal-to-Service Translation Details

### Architecture

```
┌─────────────────┐
│   CAN Signal    │ "VehicleSpeed" (uint16)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Signal-Service Translation SWC      │
│ • SignalServiceTranslationProps     │
│ • ServiceInstanceToSignalMapping    │
│ • SignalServiceTranslationEventProps│
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ SOME/IP Event   │ "VehicleSpeedEvent"
│ (Ethernet)      │
└─────────────────┘
```

### Translation Modes

1. **Signal-to-Service** (Classic → Adaptive):
   - Input: CAN/LIN/FlexRay ISignals
   - Output: SOME/IP Service Events
   - Use: Gateway ECU bridging Classic to Adaptive

2. **Service-to-Signal** (Adaptive → Classic):
   - Input: SOME/IP Service Events
   - Output: CAN/LIN/FlexRay ISignals
   - Use: Gateway ECU bridging Adaptive to Classic

### Properties

- **safeTranslation**: E2E protection during translation
- **secureTranslation**: SecOC protection during translation
- **serviceControl**: Automatic offer/subscribe behavior
- **controlPnc**: PNC-based service availability

---

## Testing Protocol Support

### Quick Test

```bash
# Test LIN support
python src/main.py
# Enter: "LIN cluster at 19.2kbps with master and 2 slaves"

# Test Ethernet/SOME-IP
python src/main.py
# Enter: "Ethernet cluster with SOME/IP temperature service"

# Test Signal-to-Service
python src/main.py
# Enter: "CAN signal translated to SOME/IP service event"
```

### Check Available Classes

```python
from src import get_api_validator

validator = get_api_validator()

# Check LIN support
lin_methods = validator.get_all_methods_for_class('LinCluster')
print(lin_methods)

# Check SOME/IP support
someip_methods = validator.get_all_methods_for_class('SomeipServiceInterface')
print(someip_methods)

# Check translation support
translation_methods = validator.get_all_methods_for_class('SignalServiceTranslationProps')
print(translation_methods)
```

---

## Current Limitations

### CAN-FD
- ⚠️ Only controller configuration classes available
- ⚠️ Frame/signal handling uses standard CAN classes
- ✅ Baudrate configuration supported
- ✅ Extended payload configuration supported

### All Other Protocols
- ✅ Full class hierarchy available
- ✅ Complete factory methods
- ✅ All setter methods
- ✅ Reference handling

---

## Future Enhancements

1. **CAN-FD Frame Support**: Dedicated CAN-FD frame classes (if added to autosarfactory)
2. **Pattern Library**: Protocol-specific code patterns for common use cases
3. **Multi-Protocol Templates**: Pre-built templates for gateway ECUs
4. **Validation Rules**: Protocol-specific validation (e.g., LIN schedule timing checks)

---

## Summary

| Feature | Status | Classes | Notes |
|---------|--------|---------|-------|
| **CAN** | ✅ Full | 30+ | Complete support |
| **CAN-FD** | ⚠️ Config | 2 | Controller config only |
| **LIN** | ✅ Full | 30+ | Complete support |
| **FlexRay** | ✅ Full | 40+ | Complete support |
| **Ethernet** | ✅ Full | 79+ | Complete support |
| **SOME/IP** | ✅ Full | 50+ | Complete support |
| **Signal↔Service** | ✅ Full | 56+ | Complete support |

**Bottom Line**: The system has **all APIs** for these protocols in the knowledge_graph.json, and now has **intelligent keyword detection** to automatically use the right classes based on your request!

---

## Getting Help

If the system doesn't recognize your protocol request:
1. Use explicit keywords: "LIN", "Ethernet", "SOME/IP", "signal-to-service"
2. Be specific about protocol features: "LIN schedule table", "SOME/IP event"
3. Check the generated plan to verify correct classes are identified
4. Review API_VALIDATION_IMPROVEMENTS.md for validation details

For questions or issues: Check the main README.md or open a GitHub issue.
