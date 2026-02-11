"""
Smart API Index - Runtime introspection of autosarfactory
==========================================================
Builds a compact, accurate index of all classes, factory methods,
setters, and getters by introspecting the actual autosarfactory module.

This replaces the 48MB symbol_table.json + 27MB code_graph_cache.json
with a compact ~1-2MB index that has accurate return types.

Based on: https://github.com/girishchandranc/autosarfactory usage patterns.
"""

import os
import sys
import json
import inspect
import hashlib
from typing import Dict, List, Optional, Set, Tuple

# Ensure autosarfactory is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import autosarfactory.autosarfactory as asf
except ImportError:
    asf = None

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_index_cache.json")


def _get_module_hash() -> str:
    """Get hash of autosarfactory module to detect changes."""
    if asf is None:
        return ""
    try:
        path = inspect.getfile(asf)
        stat = os.stat(path)
        return hashlib.md5(f"{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()
    except Exception:
        return ""


def _infer_return_type(cls, method_name: str, method) -> Optional[str]:
    """
    Infer the return type of a factory method by inspecting the actual code.

    Strategy:
    1. Check return annotation
    2. Try to find the class matching the method name suffix
    3. Look at the method source for class instantiation patterns
    """
    # Strategy 1: Check annotations
    try:
        hints = getattr(method, '__annotations__', {})
        ret = hints.get('return')
        if ret:
            if hasattr(ret, '__name__'):
                return ret.__name__
            return str(ret).split("'")[-2].split(".")[-1] if "'" in str(ret) else str(ret)
    except Exception:
        pass

    # Strategy 2: Method name mapping
    # new_X usually returns X, but sometimes names differ
    suffix = method_name[4:]  # Remove 'new_'

    # Known mappings where factory name differs from return type
    FACTORY_RETURN_OVERRIDES = {
        'new_InternalBehavior': 'SwcInternalBehavior',
        'new_Runnable': 'RunnableEntity',
        'new_DataElement': 'VariableDataPrototype',
        'new_Event': 'ServiceEvent',
        'new_Component': 'SwComponentPrototype',
        'new_CanClusterVariant': 'CanClusterConditional',
        'new_EthernetClusterVariant': 'EthernetClusterConditional',
        'new_FlexrayClusterVariant': 'FlexrayClusterConditional',
        'new_LinClusterVariant': 'LinClusterConditional',
        'new_DataReadAcces': 'VariableAccess',
        'new_DataWriteAcces': 'VariableAccess',
        'new_DataSendPoint': 'VariableAccess',
        'new_DataReceivePointByArgument': 'VariableAccess',
        'new_DataReceivePointByValue': 'VariableAccess',
        'new_SwMapping': 'SwcToEcuMapping',
        'new_Data': 'RVariableInAtomicSwcInstanceRef',
        'new_Provider': 'SwConnectorProviderComSpec' if 'Connector' in cls.__name__
            else 'PortInCompositionTypeInstanceRef',
        'new_Requester': 'SwConnectorRequesterComSpec' if 'Connector' in cls.__name__
            else 'PortInCompositionTypeInstanceRef',
        'new_AccessedVariable': 'AutosarVariableRef',
        'new_AutosarVariable': 'VariableInAtomicSWCTypeInstanceRef',
        'new_Mapping': 'SystemMapping',
    }

    if method_name in FACTORY_RETURN_OVERRIDES:
        override = FACTORY_RETURN_OVERRIDES[method_name]
        # Handle callable overrides
        if callable(override) if not isinstance(override, str) else False:
            return override
        return override

    # Check if exact suffix class exists
    if hasattr(asf, suffix):
        obj = getattr(asf, suffix)
        if inspect.isclass(obj):
            return suffix

    # Strategy 3: Try calling with a dummy to see what it returns
    # (too risky, skip)

    return suffix  # Best guess


def _get_setter_param_type(cls, method_name: str, method) -> Optional[str]:
    """Infer what type a setter accepts."""
    try:
        sig = inspect.signature(method)
        params = list(sig.parameters.values())
        # Skip 'self'
        real_params = [p for p in params if p.name != 'self']
        if real_params:
            param = real_params[0]
            ann = param.annotation
            if ann != inspect.Parameter.empty:
                if hasattr(ann, '__name__'):
                    return ann.__name__
                s = str(ann)
                if 'autosarfactory' in s:
                    return s.split('.')[-1].rstrip("'>")
                return s
    except Exception:
        pass
    return None


def build_api_index(force_rebuild: bool = False) -> dict:
    """
    Build or load a compact API index of all autosarfactory classes.

    Returns dict:
    {
        "module_hash": "...",
        "module_functions": {
            "new_file": {"params": [...], "returns": "ARPackage"},
            "read": {"params": [...], "returns": "tuple(AUTOSAR, bool)"},
            ...
        },
        "classes": {
            "ClassName": {
                "bases": ["ParentClass"],
                "factory": {"new_Child": "ReturnType", ...},
                "setters": {"set_prop": "ParamType", ...},
                "getters": ["get_prop", ...]
            }
        },
        "enums": {"EnumName": ["VALUE_1", "VALUE_2"]}
    }
    """
    if asf is None:
        raise ImportError("autosarfactory module not available")

    # Check cache
    mod_hash = _get_module_hash()
    if not force_rebuild and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cached = json.load(f)
            if cached.get('module_hash') == mod_hash:
                return cached
        except Exception:
            pass

    print("Building API index from autosarfactory (this may take a moment)...")

    index = {
        "module_hash": mod_hash,
        "module_functions": {},
        "classes": {},
        "enums": {},
    }

    # 1. Module-level functions
    for name in ['new_file', 'read', 'get_root', 'get_node', 'get_all_instances',
                 'save', 'saveAs', 'reinit', 'export_to_file']:
        fn = getattr(asf, name, None)
        if fn and callable(fn):
            try:
                sig = inspect.signature(fn)
                params = []
                for pname, param in sig.parameters.items():
                    p = {"name": pname}
                    if param.default != inspect.Parameter.empty:
                        p["default"] = repr(param.default)
                    params.append(p)
                index["module_functions"][name] = {"params": params}
            except Exception:
                index["module_functions"][name] = {"params": []}

    # Add known return types for module functions
    index["module_functions"].setdefault("new_file", {})["returns"] = "ARPackage"
    index["module_functions"].setdefault("read", {})["returns"] = "tuple(AUTOSAR, bool)"
    index["module_functions"].setdefault("get_root", {})["returns"] = "AUTOSAR"
    index["module_functions"].setdefault("get_node", {})["returns"] = "AutosarNode"
    index["module_functions"].setdefault("get_all_instances", {})["returns"] = "list"

    # 2. Enums
    from enum import Enum as PyEnum
    for name, obj in inspect.getmembers(asf):
        if inspect.isclass(obj) and issubclass(obj, PyEnum) and obj is not PyEnum:
            members = [m.name for m in obj]
            index["enums"][name] = members

    # 3. Classes
    class_count = 0
    for name, cls_obj in inspect.getmembers(asf, inspect.isclass):
        if not hasattr(cls_obj, '__module__'):
            continue
        mod = cls_obj.__module__ or ''
        if not mod.startswith('autosarfactory'):
            continue
        if issubclass(cls_obj, PyEnum):
            continue

        class_count += 1
        entry = {
            "bases": [],
            "factory": {},
            "setters": {},
            "getters": [],
        }

        # Bases
        for base in cls_obj.__bases__:
            bmod = getattr(base, '__module__', '') or ''
            if bmod.startswith('autosarfactory'):
                entry["bases"].append(base.__name__)

        # Methods
        for mname, member in inspect.getmembers(cls_obj):
            if not callable(member):
                continue
            if mname.startswith('__'):
                continue

            if mname.startswith('new_'):
                ret_type = _infer_return_type(cls_obj, mname, member)
                entry["factory"][mname] = ret_type
            elif mname.startswith('set_'):
                param_type = _get_setter_param_type(cls_obj, mname, member)
                entry["setters"][mname] = param_type
            elif mname.startswith('get_'):
                entry["getters"].append(mname)

        index["classes"][name] = entry

    print(f"  Indexed {class_count} classes, {len(index['enums'])} enums, "
          f"{len(index['module_functions'])} module functions")

    # Save cache
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(index, f, separators=(',', ':'))
        cache_size = os.path.getsize(CACHE_FILE)
        print(f"  Cache saved: {CACHE_FILE} ({cache_size / 1024 / 1024:.1f} MB)")
    except Exception as e:
        print(f"  Warning: Could not save cache: {e}")

    return index


class APIIndex:
    """
    Fast, compact API index for autosarfactory.

    Provides:
    - Method existence checks
    - Return type lookups
    - Relevant method enumeration for prompt generation
    - Compact context generation (minimal tokens)
    """

    _instance = None

    def __new__(cls, force_rebuild=False):
        if cls._instance is None or force_rebuild:
            inst = super().__new__(cls)
            inst._data = build_api_index(force_rebuild)
            inst._method_to_classes = inst._build_method_index()
            cls._instance = inst
        return cls._instance

    def _build_method_index(self) -> Dict[str, List[str]]:
        """Build reverse index: method_name -> [class_names]."""
        idx = {}
        for cls_name, info in self._data.get("classes", {}).items():
            for method in list(info.get("factory", {}).keys()) + list(info.get("setters", {}).keys()):
                idx.setdefault(method, []).append(cls_name)
        return idx

    @property
    def classes(self) -> dict:
        return self._data.get("classes", {})

    @property
    def enums(self) -> dict:
        return self._data.get("enums", {})

    @property
    def module_functions(self) -> dict:
        return self._data.get("module_functions", {})

    def class_exists(self, name: str) -> bool:
        return name in self.classes

    def method_exists(self, method: str, class_name: str = None) -> bool:
        """Check if a method exists, optionally scoped to a class."""
        if class_name:
            info = self.classes.get(class_name, {})
            return (method in info.get("factory", {}) or
                    method in info.get("setters", {}) or
                    method in info.get("getters", []))
        return method in self._method_to_classes

    def get_factory_return_type(self, class_name: str, method: str) -> Optional[str]:
        info = self.classes.get(class_name, {})
        return info.get("factory", {}).get(method)

    def get_setter_type(self, class_name: str, method: str) -> Optional[str]:
        info = self.classes.get(class_name, {})
        return info.get("setters", {}).get(method)

    def get_methods_for_class(self, class_name: str) -> Dict[str, list]:
        """Get all methods for a class, including inherited."""
        info = self.classes.get(class_name, {})
        if not info:
            return {"factory": [], "setters": [], "getters": []}

        factory = list(info.get("factory", {}).keys())
        setters = list(info.get("setters", {}).keys())
        getters = info.get("getters", [])

        # Include inherited methods
        for base in info.get("bases", []):
            base_methods = self.get_methods_for_class(base)
            factory.extend(m for m in base_methods["factory"] if m not in factory)
            setters.extend(m for m in base_methods["setters"] if m not in setters)
            getters.extend(m for m in base_methods["getters"] if m not in getters)

        return {"factory": factory, "setters": setters, "getters": getters}

    def find_similar_method(self, method: str, class_name: str = None, limit: int = 3) -> List[str]:
        """Find methods similar to the given name."""
        import difflib
        if class_name:
            methods = self.get_methods_for_class(class_name)
            candidates = methods["factory"] + methods["setters"]
        else:
            candidates = list(self._method_to_classes.keys())
        return difflib.get_close_matches(method, candidates, n=limit, cutoff=0.6)

    def get_classes_for_keywords(self, text: str) -> Set[str]:
        """Extract relevant classes from task text using keyword matching."""
        text_lower = text.lower()
        classes = {"ARPackage"}

        KEYWORD_MAP = {
            "can": ["CanCluster", "CanPhysicalChannel", "CanFrame", "CanFrameTriggering"],
            "cluster": ["CanCluster"],
            "baudrate": ["CanClusterConditional"],
            "frame": ["CanFrame", "CanFrameTriggering", "PduToFrameMapping"],
            "signal": ["ISignal", "ISignalIPdu", "ISignalToPduMapping", "SystemSignal"],
            "pdu": ["ISignalIPdu", "PduToFrameMapping", "ISignalToPduMapping"],
            "ecu": ["EcuInstance"],
            "component": ["ApplicationSwComponentType", "CompositionSwComponentType"],
            "swc": ["ApplicationSwComponentType"],
            "port": ["PPortPrototype", "RPortPrototype"],
            "interface": ["SenderReceiverInterface", "ClientServerInterface"],
            "sender": ["SenderReceiverInterface"],
            "behavior": ["SwcInternalBehavior"],
            "runnable": ["RunnableEntity"],
            "event": ["TimingEvent", "DataReceivedEvent"],
            "timing": ["TimingEvent"],
            "type": ["SwBaseType", "ImplementationDataType"],
            "datatype": ["SwBaseType", "ImplementationDataType", "SwDataDefProps"],
            "composition": ["CompositionSwComponentType"],
            "connector": ["AssemblySwConnector"],
            "ethernet": ["EthernetCluster"],
            "someip": ["SomeipServiceInterfaceDeployment"],
            "system": ["System", "SystemMapping"],
            "mapping": ["SystemMapping"],
        }

        for keyword, cls_list in KEYWORD_MAP.items():
            if keyword in text_lower:
                classes.update(cls_list)

        return classes

    def get_compact_context(self, class_names: List[str], max_per_class: int = 30) -> str:
        """
        Generate a compact API context string for prompt injection.
        Optimized for minimal token usage while preserving accuracy.
        """
        lines = []
        seen_classes = set()

        for cls_name in sorted(class_names):
            if cls_name in seen_classes:
                continue
            seen_classes.add(cls_name)

            info = self.classes.get(cls_name)
            if not info:
                continue

            factory = info.get("factory", {})
            setters = info.get("setters", {})

            # Skip classes with no relevant methods
            if not factory and not setters:
                continue

            lines.append(f"\n{cls_name}:")

            # Factory methods (most important)
            if factory:
                items = list(factory.items())[:max_per_class]
                for method, ret_type in items:
                    lines.append(f"  {method}(name) -> {ret_type or '?'}")

            # Setters
            if setters:
                items = list(setters.items())[:max_per_class]
                for method, param_type in items:
                    type_hint = f"({param_type})" if param_type else "()"
                    lines.append(f"  {method}{type_hint}")

        return "\n".join(lines)

    def get_relevant_context(self, task_text: str, max_classes: int = 20) -> str:
        """
        Get compact API context relevant to a task description.
        Uses keyword matching to select only relevant classes.
        """
        relevant = self.get_classes_for_keywords(task_text)

        # Expand with direct parents/children
        expanded = set(relevant)
        for cls_name in list(relevant):
            info = self.classes.get(cls_name, {})
            # Add parent classes
            for base in info.get("bases", []):
                expanded.add(base)
            # Add factory return types
            for ret_type in info.get("factory", {}).values():
                if ret_type and ret_type in self.classes:
                    expanded.add(ret_type)

        # Limit
        class_list = sorted(expanded)[:max_classes]
        return self.get_compact_context(class_list)


def get_api_index(force_rebuild: bool = False) -> APIIndex:
    """Get the singleton API index."""
    return APIIndex(force_rebuild)


if __name__ == "__main__":
    idx = get_api_index(force_rebuild=True)
    print(f"\nTotal classes: {len(idx.classes)}")
    print(f"Total enums: {len(idx.enums)}")

    # Test some lookups
    print(f"\nCanCluster.new_CanClusterVariant returns: "
          f"{idx.get_factory_return_type('CanCluster', 'new_CanClusterVariant')}")
    print(f"\nApplicationSwComponentType methods:")
    m = idx.get_methods_for_class("ApplicationSwComponentType")
    print(f"  Factory: {m['factory'][:10]}")
    print(f"  Setters: {m['setters'][:10]}")

    # Test context generation
    context = idx.get_relevant_context("Create a CAN cluster with frames and signals")
    print(f"\nRelevant context ({len(context)} chars):")
    print(context[:2000])
