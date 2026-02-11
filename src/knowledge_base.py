"""
Unified Code Knowledge Base - Uses APIIndex for ground truth.
==============================================================
Simplified wrapper around api_index.py and api_fixes.py.
Provides backward-compatible interface for neuro_generator.py
and validation_engine.py.
"""

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
from enum import Enum, auto

from src.api_fixes import HALLUCINATION_FIXES
from src.api_index import get_api_index, APIIndex


class OperationType(Enum):
    CREATE_FILE = auto()
    CREATE_PACKAGE = auto()
    CREATE_ELEMENT = auto()
    SET_ATTRIBUTE = auto()
    SET_REFERENCE = auto()
    READ_FILE = auto()
    SAVE_FILE = auto()
    ITERATE = auto()


@dataclass
class ValidationError:
    error_type: str
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    severity: str = "error"


@dataclass
class ValidOperation:
    operation_type: OperationType
    source_class: str
    method_name: str
    parameters: list = field(default_factory=list)
    return_type: Optional[str] = None
    creates_type: Optional[str] = None
    accepts_type: Optional[str] = None
    is_validated: bool = True


# Re-export for backward compatibility
CORRECT_TO_WRONG: Dict[str, List[str]] = {}
for wrong, correct in HALLUCINATION_FIXES.items():
    CORRECT_TO_WRONG.setdefault(correct, []).append(wrong)


class UnifiedKnowledgeBase:
    """
    Unified source of truth backed by APIIndex.
    Provides the same interface as the old knowledge_base.py
    but uses the compact, accurate API index underneath.
    """

    def __init__(self, force_rebuild: bool = False):
        print("Initializing Unified Knowledge Base (APIIndex-backed)...")
        self._idx = get_api_index(force_rebuild)
        # Compatibility: expose a symbol_table-like object
        self.symbol_table = _SymbolTableCompat(self._idx)
        self.code_graph = _CodeGraphCompat(self._idx)
        print(f"Knowledge Base initialized: {len(self._idx.classes)} classes")

    def class_exists(self, name: str) -> bool:
        return self._idx.class_exists(name)

    def method_exists(self, method: str, class_name: str = None) -> bool:
        return self._idx.method_exists(method, class_name)

    def get_valid_methods(self, class_name: str, include_inherited: bool = True,
                          method_type: str = None) -> List[str]:
        methods = self._idx.get_methods_for_class(class_name)
        if method_type == 'factory':
            return sorted(methods.get("factory", []))
        elif method_type == 'setter':
            return sorted(methods.get("setters", []))
        elif method_type == 'getter':
            return sorted(methods.get("getters", []))
        return sorted(methods.get("factory", []) + methods.get("setters", []) + methods.get("getters", []))

    def get_method_signature(self, method_name: str, class_name: str = None):
        return None  # Simplified - signatures not tracked in compact index

    def get_factory_return_type(self, class_name: str, factory_method: str) -> Optional[str]:
        return self._idx.get_factory_return_type(class_name, factory_method)

    def is_abstract(self, class_name: str) -> bool:
        return False  # Simplified

    def can_instantiate(self, class_name: str) -> bool:
        return self._idx.class_exists(class_name)

    def fix_hallucinated_method(self, method_name: str) -> Tuple[str, bool]:
        if method_name in HALLUCINATION_FIXES:
            return HALLUCINATION_FIXES[method_name], True
        return method_name, False

    def get_correct_method(self, hallucinated: str) -> Optional[str]:
        return HALLUCINATION_FIXES.get(hallucinated)

    def find_similar_method(self, method: str, class_name: str = None, limit: int = 3) -> List[str]:
        return self._idx.find_similar_method(method, class_name, limit)

    def validate_method_call(self, class_name: str, method_name: str,
                            arguments: Dict = None) -> Tuple[bool, List[ValidationError]]:
        errors = []
        corrected, was_fixed = self.fix_hallucinated_method(method_name)
        if was_fixed:
            errors.append(ValidationError("hallucination_fixed",
                f"'{method_name}' corrected to '{corrected}'", severity="warning"))
            method_name = corrected

        if not self.class_exists(class_name):
            errors.append(ValidationError("class_not_found", f"Class '{class_name}' not found"))
            return False, errors

        if not self.method_exists(method_name, class_name):
            similar = self.find_similar_method(method_name, class_name)
            suggestion = f"Did you mean: {', '.join(similar)}?" if similar else None
            errors.append(ValidationError("method_not_found",
                f"'{method_name}' not found on '{class_name}'", suggestion=suggestion))
            return False, errors

        return True, errors

    def build_constraint_set(self, class_names: List[str]) -> Dict:
        constraints = {}
        for name in class_names:
            if not self.class_exists(name):
                continue
            factories = self.get_valid_methods(name, method_type='factory')
            setters = self.get_valid_methods(name, method_type='setter')
            factory_returns = {}
            for m in factories:
                rt = self.get_factory_return_type(name, m)
                if rt:
                    factory_returns[m] = rt
            constraints[name] = {
                "factory_methods": factories,
                "setters": setters,
                "factory_returns": factory_returns,
            }
        return constraints

    def generate_constraint_prompt(self, class_names: List[str],
                                   max_methods_per_class: int = 20) -> str:
        return self._idx.get_compact_context(class_names, max_methods_per_class)

    def get_related_classes(self, class_name: str, depth: int = 2) -> Set[str]:
        related = set()
        info = self._idx.classes.get(class_name, {})
        for base in info.get("bases", []):
            related.add(base)
        for ret in info.get("factory", {}).values():
            if ret and ret in self._idx.classes:
                related.add(ret)
        return related

    def get_class_hierarchy(self, class_name: str) -> List[str]:
        chain = [class_name]
        info = self._idx.classes.get(class_name, {})
        for base in info.get("bases", []):
            chain.append(base)
        return chain

    def get_creation_chain(self, target_class: str):
        return []  # Simplified

    def validate_operation_plan(self, operations: List[Dict]) -> List[ValidationError]:
        errors = []
        for i, op in enumerate(operations):
            source_class = op.get('source_class', '')
            method_name = op.get('method_name', '')
            if source_class and method_name:
                is_valid, method_errors = self.validate_method_call(source_class, method_name)
                for e in method_errors:
                    e.location = f"Op {i+1}: {source_class}.{method_name}"
                errors.extend(method_errors)
        return errors


class _SymbolTableCompat:
    """Backward-compatible symbol_table interface."""
    def __init__(self, idx: APIIndex):
        self._idx = idx
        self.classes = idx.classes

    def has_method(self, method_name: str, class_name: str = None) -> bool:
        return self._idx.method_exists(method_name, class_name)

    def find_similar_method(self, method: str, limit: int = 3) -> List[str]:
        return self._idx.find_similar_method(method, limit=limit)


class _CodeGraphCompat:
    """Backward-compatible code_graph interface."""
    def __init__(self, idx: APIIndex):
        self._idx = idx

    def get_valid_methods_for_class(self, class_name: str, include_inherited: bool = True) -> List[str]:
        m = self._idx.get_methods_for_class(class_name)
        return m.get("factory", []) + m.get("setters", []) + m.get("getters", [])

    def get_inheritance_chain(self, class_name: str) -> List[str]:
        chain = [class_name]
        info = self._idx.classes.get(class_name, {})
        for base in info.get("bases", []):
            chain.append(base)
        return chain

    def get_factory_methods(self, class_name: str):
        info = self._idx.classes.get(class_name, {})
        return list(info.get("factory", {}).items())

    def get_required_context(self, target_class: str, depth: int = 2):
        return []


# Singleton
_kb_instance: Optional[UnifiedKnowledgeBase] = None


def get_knowledge_base(force_rebuild: bool = False) -> UnifiedKnowledgeBase:
    global _kb_instance
    if _kb_instance is None or force_rebuild:
        _kb_instance = UnifiedKnowledgeBase(force_rebuild=force_rebuild)
    return _kb_instance
