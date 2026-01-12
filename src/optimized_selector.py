"""
Optimized API Selection Engine
==============================
Improved version with:
1. Comprehensive protocol support (CAN, CAN FD, LIN, Ethernet, SOME/IP)
2. Signal-to-Service translation support
3. Performance optimizations (caching, memoization, batch operations)
4. Better API selection through semantic matching
"""

import os
import json
import re
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, FrozenSet
from enum import Enum

# Import knowledge base
from src.knowledge_base import get_knowledge_base, HALLUCINATION_FIXES


# ============================================================================
# Protocol-Specific API Mappings (Comprehensive)
# ============================================================================

class ProtocolType(Enum):
    """Supported communication protocols."""
    CAN = "can"
    CAN_FD = "canfd"
    LIN = "lin"
    ETHERNET = "ethernet"
    SOMEIP = "someip"
    FLEXRAY = "flexray"


# Comprehensive keyword-to-class mapping for ALL protocols
PROTOCOL_CLASS_MAPPING: Dict[str, List[str]] = {
    # =========================================================================
    # CAN (Classic)
    # =========================================================================
    "can": [
        "CanCluster", "CanClusterVariant", "CanClusterConditional",
        "CanPhysicalChannel", "CanFrame", "CanFrameTriggering",
        "CanCommunicationController", "CanCommunicationConnector",
    ],
    "cancluster": ["CanCluster", "CanClusterVariant", "CanClusterConditional"],
    "canframe": ["CanFrame", "CanFrameTriggering", "PduToFrameMapping"],
    "cantriggering": ["CanFrameTriggering", "ISignalTriggering"],

    # =========================================================================
    # CAN FD (Flexible Data-rate)
    # =========================================================================
    "canfd": [
        "CanCluster", "CanClusterVariant", "CanClusterConditional",
        "CanPhysicalChannel", "CanFrame", "CanFrameTriggering",
        "CanCommunicationController",
        # CAN FD specific
        "CanFdCluster", "CanFdFrame",
    ],
    "flexibledata": ["CanCluster", "CanClusterConditional"],
    "fdbaudrate": ["CanClusterConditional"],  # set_canFdBaudrate

    # =========================================================================
    # LIN (Local Interconnect Network)
    # =========================================================================
    "lin": [
        "LinCluster", "LinClusterVariant", "LinClusterConditional",
        "LinPhysicalChannel", "LinFrame", "LinFrameTriggering",
        "LinCommunicationController", "LinCommunicationConnector",
        "LinMaster", "LinSlave", "LinUnconditionalFrame",
        "LinScheduleTable", "LinScheduleTableEntry",
    ],
    "lincluster": ["LinCluster", "LinClusterVariant", "LinClusterConditional"],
    "linframe": ["LinFrame", "LinFrameTriggering", "LinUnconditionalFrame"],
    "linmaster": ["LinMaster", "LinCommunicationController"],
    "linslave": ["LinSlave", "LinCommunicationController"],
    "linschedule": ["LinScheduleTable", "LinScheduleTableEntry"],

    # =========================================================================
    # FlexRay
    # =========================================================================
    "flexray": [
        "FlexrayCluster", "FlexrayClusterVariant", "FlexrayClusterConditional",
        "FlexrayPhysicalChannel", "FlexrayFrame", "FlexrayFrameTriggering",
        "FlexrayCommunicationController", "FlexrayCommunicationConnector",
    ],
    "flexraycluster": ["FlexrayCluster", "FlexrayClusterVariant"],
    "flexrayframe": ["FlexrayFrame", "FlexrayFrameTriggering"],

    # =========================================================================
    # Ethernet
    # =========================================================================
    "ethernet": [
        "EthernetCluster", "EthernetClusterVariant", "EthernetClusterConditional",
        "EthernetPhysicalChannel", "EthernetCommunicationController",
        "EthernetCommunicationConnector", "SocketAddress", "NetworkEndpoint",
    ],
    "ethernetcluster": ["EthernetCluster", "EthernetClusterVariant"],
    "socket": ["SocketAddress", "SocketConnection", "TcpIp"],
    "vlan": ["EthernetPhysicalChannel", "VlanConfig"],

    # =========================================================================
    # SOME/IP (Service-Oriented Middleware over IP)
    # =========================================================================
    "someip": [
        "SomeipServiceInterfaceDeployment", "SomeipEventDeployment",
        "SomeipMethodDeployment", "SomeipFieldDeployment",
        "SomeipProvidedEventGroup", "SomeipSdClientServiceInstanceConfig",
        "SomeipSdServerServiceInstanceConfig", "SomeipTransformationProps",
    ],
    "serviceinterface": [
        "SomeipServiceInterfaceDeployment", "ServiceInterface",
        "ClientServerInterface", "ProvidedServiceInstance", "ConsumedServiceInstance",
    ],
    "eventgroup": ["SomeipProvidedEventGroup", "SomeipEventDeployment"],
    "sd": ["SomeipSdClientServiceInstanceConfig", "SomeipSdServerServiceInstanceConfig"],

    # =========================================================================
    # Signal-to-Service Translation (COM to SOME/IP)
    # =========================================================================
    "signalservice": [
        "SignalServiceTranslationEventProps", "SignalServiceTranslationProps",
        "SignalServiceTranslationProp", "ComISignalToPduMapping",
        "ISignalGroup", "SystemSignal", "SystemSignalGroup",
    ],
    "translation": [
        "SignalServiceTranslationEventProps", "SignalServiceTranslationProps",
        "SignalServiceTranslationProp", "DataTransformation",
    ],
    "signaltranslation": [
        "SignalServiceTranslationEventProps", "SignalServiceTranslationProp",
        "ISignal", "SystemSignal", "SomeipEventDeployment",
    ],
    "comtosomeip": [
        "SignalServiceTranslationProps", "SignalServiceTranslationEventProps",
        "ISignalGroup", "SomeipEventDeployment",
    ],

    # =========================================================================
    # Signals and PDUs (Common to all protocols)
    # =========================================================================
    "signal": [
        "ISignal", "ISignalIPdu", "ISignalGroup", "ISignalToPduMapping",
        "SystemSignal", "SystemSignalGroup", "ISignalTriggering",
    ],
    "isignal": ["ISignal", "ISignalIPdu", "ISignalToPduMapping"],
    "pdu": ["ISignalIPdu", "PduToFrameMapping", "ISignalToPduMapping", "Pdu"],
    "systemsignal": ["SystemSignal", "SystemSignalGroup"],
    "signalgroup": ["ISignalGroup", "SystemSignalGroup"],

    # =========================================================================
    # ECU and System
    # =========================================================================
    "ecu": ["EcuInstance", "EcuMapping", "SwMapping"],
    "controller": [
        "CommunicationController", "CanCommunicationController",
        "LinCommunicationController", "EthernetCommunicationController",
    ],
    "connector": [
        "CommunicationConnector", "CanCommunicationConnector",
        "LinCommunicationConnector", "EthernetCommunicationConnector",
    ],
    "system": ["System", "SystemMapping", "RootSoftwareComposition"],
    "mapping": [
        "SystemMapping", "SenderReceiverToSignalMapping", "SwMapping",
        "ISignalToPduMapping", "PduToFrameMapping", "DataMapping",
    ],

    # =========================================================================
    # Software Components
    # =========================================================================
    "component": [
        "ApplicationSwComponentType", "CompositionSwComponentType",
        "ServiceSwComponentType", "SensorActuatorSwComponentType",
        "SwComponentPrototype",
    ],
    "swc": ["ApplicationSwComponentType", "SwcInternalBehavior"],
    "serviceswc": ["ServiceSwComponentType", "ServiceInterface"],
    "composition": ["CompositionSwComponentType", "RootSoftwareComposition"],
    "port": ["PPortPrototype", "RPortPrototype", "PRPortPrototype"],
    "interface": [
        "SenderReceiverInterface", "ClientServerInterface",
        "ModeSwitchInterface", "ServiceInterface",
    ],
    "behavior": ["SwcInternalBehavior", "RunnableEntity", "TimingEvent"],
    "runnable": ["RunnableEntity", "DataSendPoint", "DataReceivePointByArgument"],
    "event": ["TimingEvent", "DataReceivedEvent", "OperationInvokedEvent"],
    "connector": ["AssemblySwConnector", "DelegationSwConnector"],

    # =========================================================================
    # Data Types
    # =========================================================================
    "type": ["SwBaseType", "ImplementationDataType", "ApplicationDataType"],
    "datatype": ["SwBaseType", "ImplementationDataType", "SwDataDefProps"],
    "basetype": ["SwBaseType", "BaseTypeDirectDefinition"],
    "impltype": ["ImplementationDataType", "SwDataDefProps", "SwDataDefPropsVariant"],
    "array": ["StdCppImplementationDataType", "ArrayType"],

    # =========================================================================
    # Compu Methods and Constraints
    # =========================================================================
    "compu": ["CompuMethod", "CompuInternalToPhys", "CompuScales", "CompuScale"],
    "scale": ["CompuScale", "CompuScaleConstantContents", "CompuScaleRationalFormula"],
    "constraint": ["DataConstr", "DataConstrRule", "InternalConstrs"],
    "limit": ["LowerLimit", "UpperLimit"],

    # =========================================================================
    # Timing and Modes
    # =========================================================================
    "timing": ["TimingEvent", "TimingExtension", "ExecutionTime"],
    "mode": ["ModeDeclarationGroup", "ModeDeclaration", "ModeSwitchInterface"],

    # =========================================================================
    # Admin and Documentation
    # =========================================================================
    "admin": ["AdminData", "Sdg", "Sd"],
    "doc": ["Documentation", "Annotation", "Desc"],
}


# ============================================================================
# Protocol-Specific Patterns (What methods to use for each protocol)
# ============================================================================

PROTOCOL_PATTERNS: Dict[str, Dict[str, str]] = {
    "can": {
        "cluster": "new_CanCluster",
        "variant": "new_CanClusterVariant",  # Returns CanClusterConditional
        "channel": "new_CanPhysicalChannel",
        "frame": "new_CanFrame",
        "triggering": "new_CanFrameTriggering",
        "baudrate_setter": "set_baudrate",  # On CanClusterConditional
    },
    "canfd": {
        "cluster": "new_CanCluster",
        "variant": "new_CanClusterVariant",
        "channel": "new_CanPhysicalChannel",
        "frame": "new_CanFrame",  # With larger DLC
        "triggering": "new_CanFrameTriggering",
        "baudrate_setter": "set_baudrate",
        "fd_baudrate_setter": "set_canFdBaudrate",  # For FD data phase
    },
    "lin": {
        "cluster": "new_LinCluster",
        "variant": "new_LinClusterVariant",
        "channel": "new_LinPhysicalChannel",
        "frame": "new_LinUnconditionalFrame",
        "triggering": "new_LinFrameTriggering",
        "schedule": "new_LinScheduleTable",
        "master": "new_LinMaster",
        "slave": "new_LinSlave",
    },
    "ethernet": {
        "cluster": "new_EthernetCluster",
        "variant": "new_EthernetClusterVariant",
        "channel": "new_EthernetPhysicalChannel",
        "socket": "new_SocketAddress",
    },
    "someip": {
        "service_deployment": "new_SomeipServiceInterfaceDeployment",
        "event_deployment": "new_SomeipEventDeployment",
        "method_deployment": "new_SomeipMethodDeployment",
        "event_group": "new_SomeipProvidedEventGroup",
    },
}


# ============================================================================
# Optimized API Selector with Caching
# ============================================================================

class OptimizedAPISelector:
    """
    High-performance API selector with:
    - LRU caching for repeated queries
    - Batch class extraction
    - Protocol-aware selection
    - Memoized dependency traversal
    """

    def __init__(self):
        self.kb = get_knowledge_base()
        self._class_cache: Dict[str, Set[str]] = {}
        self._dependency_cache: Dict[str, Set[str]] = {}

    @lru_cache(maxsize=256)
    def extract_classes_cached(self, text_tuple: Tuple[str, ...]) -> FrozenSet[str]:
        """
        Cached class extraction from text.
        Uses tuple for hashability.
        """
        text = " ".join(text_tuple).lower()
        classes = set()
        classes.add("ARPackage")  # Always needed

        # Match against all protocol mappings
        for keyword, class_list in PROTOCOL_CLASS_MAPPING.items():
            if keyword in text:
                classes.update(class_list)

        return frozenset(classes)

    def extract_classes(self, text: str) -> List[str]:
        """Extract relevant classes from text."""
        # Convert to tuple for caching
        words = tuple(text.lower().split()[:50])  # Limit for cache key
        cached = self.extract_classes_cached(words)
        return list(cached)

    @lru_cache(maxsize=128)
    def get_protocol_type(self, text: str) -> Optional[ProtocolType]:
        """Detect the primary protocol from text."""
        text_lower = text.lower()

        # Check for specific protocols
        if "canfd" in text_lower or "can fd" in text_lower or "flexible" in text_lower:
            return ProtocolType.CAN_FD
        elif "lin" in text_lower:
            return ProtocolType.LIN
        elif "someip" in text_lower or "some/ip" in text_lower or "service" in text_lower:
            return ProtocolType.SOMEIP
        elif "ethernet" in text_lower or "socket" in text_lower:
            return ProtocolType.ETHERNET
        elif "flexray" in text_lower:
            return ProtocolType.FLEXRAY
        elif "can" in text_lower:
            return ProtocolType.CAN

        return None

    def get_protocol_patterns(self, protocol: ProtocolType) -> Dict[str, str]:
        """Get method patterns for a protocol."""
        return PROTOCOL_PATTERNS.get(protocol.value, {})

    def get_expanded_classes(self, initial_classes: List[str],
                             max_depth: int = 2) -> Set[str]:
        """
        Expand classes with dependencies using memoization.
        Avoids N+1 pattern through batch processing.
        """
        expanded = set(initial_classes)
        processed = set()

        # BFS expansion with depth limit
        current_depth = 0
        frontier = set(initial_classes)

        while frontier and current_depth < max_depth:
            next_frontier = set()

            for class_name in frontier:
                if class_name in processed:
                    continue

                processed.add(class_name)

                # Check cache first
                cache_key = class_name
                if cache_key in self._dependency_cache:
                    deps = self._dependency_cache[cache_key]
                else:
                    deps = self._get_single_class_deps(class_name)
                    self._dependency_cache[cache_key] = deps

                new_deps = deps - expanded
                next_frontier.update(new_deps)
                expanded.update(new_deps)

            frontier = next_frontier
            current_depth += 1

        return expanded

    def _get_single_class_deps(self, class_name: str) -> Set[str]:
        """Get immediate dependencies for a single class."""
        deps = set()

        if not self.kb.class_exists(class_name):
            return deps

        # Get from code graph if available
        try:
            related = self.kb.get_related_classes(class_name, depth=1)
            deps.update(related)
        except:
            pass

        return deps

    def extract_parameters(self, text: str) -> Dict[str, any]:
        """Extract configuration parameters from text."""
        params = {}

        # Baudrate patterns
        baudrate_patterns = [
            (r'(\d+)\s*kbps', 1000),
            (r'(\d+)\s*mbps', 1000000),
            (r'(\d+)\s*baud', 1),
        ]
        for pattern, multiplier in baudrate_patterns:
            match = re.search(pattern, text.lower())
            if match:
                params["baudrate"] = int(match.group(1)) * multiplier
                break

        # CAN FD data baudrate
        fd_match = re.search(r'data\s*(?:rate|baudrate)?\s*(\d+)\s*(mbps|kbps)', text.lower())
        if fd_match:
            multiplier = 1000000 if 'mbps' in fd_match.group(2) else 1000
            params["fd_baudrate"] = int(fd_match.group(1)) * multiplier

        # CAN ID
        can_id_match = re.search(r'(?:can\s*)?id\s*(?:=\s*)?(?:0x)?([0-9a-fA-F]+)', text.lower())
        if can_id_match:
            params["can_id"] = int(can_id_match.group(1), 16)

        # Frame length / DLC
        dlc_match = re.search(r'(\d+)\s*(?:byte|dlc)', text.lower())
        if dlc_match:
            params["frame_length"] = int(dlc_match.group(1))

        # Signal length
        sig_len_match = re.search(r'(\d+)\s*bit', text.lower())
        if sig_len_match:
            params["signal_length"] = int(sig_len_match.group(1))

        # Period (timing)
        period_patterns = [
            (r'(\d+)\s*ms', 0.001),
            (r'(\d+)\s*s(?:ec)?', 1.0),
            (r'(\d+)\s*us', 0.000001),
        ]
        for pattern, multiplier in period_patterns:
            match = re.search(pattern, text.lower())
            if match:
                params["period"] = float(match.group(1)) * multiplier
                break

        # Service ID (SOME/IP)
        service_match = re.search(r'service\s*id\s*(?:=\s*)?(?:0x)?([0-9a-fA-F]+)', text.lower())
        if service_match:
            params["service_id"] = int(service_match.group(1), 16)

        # Method ID (SOME/IP)
        method_match = re.search(r'method\s*id\s*(?:=\s*)?(?:0x)?([0-9a-fA-F]+)', text.lower())
        if method_match:
            params["method_id"] = int(method_match.group(1), 16)

        return params

    def generate_optimized_prompt(self, task: str,
                                  classes: List[str] = None,
                                  max_classes: int = 30) -> str:
        """
        Generate an optimized prompt with only relevant classes.
        """
        if classes is None:
            classes = self.extract_classes(task)

        # Expand with dependencies
        expanded = self.get_expanded_classes(classes, max_depth=1)

        # Limit to most relevant
        if len(expanded) > max_classes:
            # Prioritize directly mentioned classes
            direct = set(classes)
            deps = expanded - direct
            expanded = direct | set(list(deps)[:max_classes - len(direct)])

        # Detect protocol
        protocol = self.get_protocol_type(task)
        protocol_hint = ""
        if protocol:
            patterns = self.get_protocol_patterns(protocol)
            if patterns:
                protocol_hint = f"\nPROTOCOL: {protocol.value.upper()}\n"
                protocol_hint += "Key methods for this protocol:\n"
                for purpose, method in patterns.items():
                    protocol_hint += f"  - {purpose}: {method}()\n"

        # Extract parameters
        params = self.extract_parameters(task)
        param_hint = ""
        if params:
            param_hint = "\nDETECTED PARAMETERS:\n"
            for name, value in params.items():
                param_hint += f"  - {name}: {value}\n"

        # Generate constraint prompt
        constraint_prompt = self.kb.generate_constraint_prompt(list(expanded), max_methods_per_class=15)

        return f"""
{protocol_hint}
{param_hint}
{constraint_prompt}
"""

    def clear_cache(self):
        """Clear all caches."""
        self._class_cache.clear()
        self._dependency_cache.clear()
        self.extract_classes_cached.cache_clear()
        self.get_protocol_type.cache_clear()


# ============================================================================
# Singleton Access
# ============================================================================

_selector_instance: Optional[OptimizedAPISelector] = None


def get_optimized_selector() -> OptimizedAPISelector:
    """Get the global optimized selector instance."""
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = OptimizedAPISelector()
    return _selector_instance


# ============================================================================
# Performance-Optimized Batch Operations
# ============================================================================

def batch_validate_methods(methods: List[str], kb=None) -> Dict[str, Tuple[bool, Optional[str]]]:
    """
    Validate multiple methods in a single pass.
    Returns dict of method_name -> (is_valid, suggested_fix)
    """
    if kb is None:
        kb = get_knowledge_base()

    results = {}
    for method in methods:
        # Check hallucination first (O(1))
        if method in HALLUCINATION_FIXES:
            results[method] = (False, HALLUCINATION_FIXES[method])
        elif kb.method_exists(method):
            results[method] = (True, None)
        else:
            # Find similar
            similar = kb.find_similar_method(method, limit=1)
            results[method] = (False, similar[0] if similar else None)

    return results


def batch_fix_code(code: str) -> Tuple[str, List[str]]:
    """
    Apply all fixes in a single pass for performance.
    Returns (fixed_code, list_of_applied_fixes)
    """
    fixes_applied = []

    # Build combined regex pattern for all hallucinations
    if HALLUCINATION_FIXES:
        # Sort by length descending to fix longer patterns first
        sorted_fixes = sorted(HALLUCINATION_FIXES.items(), key=lambda x: -len(x[0]))

        for wrong, correct in sorted_fixes:
            if wrong in code:
                code = code.replace(wrong, correct)
                fixes_applied.append(f"{wrong} -> {correct}")

    # Fix reference patterns in single pass
    ref_pattern = r'\.new_(\w+)Ref\(\)\.set_value\(([^)]+)\)'
    matches = list(re.finditer(ref_pattern, code))
    if matches:
        # Process in reverse to preserve positions
        for match in reversed(matches):
            ref_type = match.group(1)
            value = match.group(2)
            setter_name = ref_type[0].lower() + ref_type[1:]
            replacement = f'.set_{setter_name}({value})'
            code = code[:match.start()] + replacement + code[match.end():]
            fixes_applied.append(f"Reference pattern: new_{ref_type}Ref -> set_{setter_name}")

    # Fix save() signature
    code, n = re.subn(r'autosarfactory\.save\([^)]+\)', 'autosarfactory.save()', code)
    if n > 0:
        fixes_applied.append("save() signature")

    # Fix ByteOrder enums
    byte_order_fixes = [
        (r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-LAST["\']\)',
         'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)'),
        (r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-FIRST["\']\)',
         'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_FIRST)'),
    ]
    for pattern, replacement in byte_order_fixes:
        code, n = re.subn(pattern, replacement, code)
        if n > 0:
            fixes_applied.append("ByteOrder enum")

    return code, fixes_applied


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing Optimized API Selector...")

    selector = get_optimized_selector()

    # Test class extraction
    test_queries = [
        "Create a CAN FD cluster with 500kbps and data rate 2mbps",
        "Create a LIN master with schedule table",
        "Set up SOME/IP service interface deployment",
        "Create signal to service translation for COM to SOME/IP",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        classes = selector.extract_classes(query)
        protocol = selector.get_protocol_type(query)
        params = selector.extract_parameters(query)

        print(f"  Protocol: {protocol}")
        print(f"  Classes: {classes[:10]}...")
        print(f"  Parameters: {params}")
