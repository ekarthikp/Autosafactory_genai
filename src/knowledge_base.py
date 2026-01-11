"""
Unified Code Knowledge Base - Near-Deterministic Ground Truth
==============================================================
This module integrates Symbol Table, Code Graph, and Validation into a single
unified interface. It serves as the "Source of Truth" for all code generation,
eliminating hallucination by constraining the LLM's output space.

Based on: "Determinism in the Stochastic Machine: A Neuro-Symbolic Architecture"

Key Principles:
1. Ground Truth: Every method/class must exist in the symbol table
2. Graph Relationships: Understanding of how classes relate (inheritance, factory, reference)
3. Constrained Selection: Dynamic enumeration of valid options
4. Pre-validation: All operations validated before generation
"""

import os
import json
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any, Callable
from enum import Enum, auto
import difflib

# Import core components
from src.ast_indexer import (
    get_symbol_table,
    SymbolTable,
    ClassInfo,
    MethodSignature,
    Parameter
)
from src.code_graph import (
    get_code_graph,
    CodeKnowledgeGraph,
    EDGE_INHERITS,
    EDGE_CONTAINS,
    EDGE_RETURNS
)


# ============================================================================
# Core Data Classes for Deterministic Code Generation
# ============================================================================

class OperationType(Enum):
    """Types of operations in AUTOSAR code generation."""
    CREATE_FILE = auto()           # new_file()
    CREATE_PACKAGE = auto()        # new_ARPackage()
    CREATE_ELEMENT = auto()        # new_*() factory methods
    SET_ATTRIBUTE = auto()         # set_*() setters
    SET_REFERENCE = auto()         # Direct reference setters
    READ_FILE = auto()             # read() for edit mode
    SAVE_FILE = auto()             # save() / saveAs()
    ITERATE = auto()               # get_*() for iteration


@dataclass
class ValidOperation:
    """Represents a validated operation that can be performed."""
    operation_type: OperationType
    source_class: str
    method_name: str
    parameters: List[Parameter]
    return_type: Optional[str]
    creates_type: Optional[str] = None  # For factory methods
    accepts_type: Optional[str] = None  # For setters
    is_validated: bool = True

    def to_code(self, source_var: str, args: Dict[str, Any] = None) -> str:
        """Generate code for this operation."""
        args = args or {}

        # Build argument string
        arg_parts = []
        for param in self.parameters:
            if param.name in args:
                val = args[param.name]
                if isinstance(val, str) and not val.startswith('$'):
                    arg_parts.append(f'{param.name}="{val}"')
                else:
                    # Variable reference (remove $ prefix if present)
                    val_str = val[1:] if isinstance(val, str) and val.startswith('$') else str(val)
                    arg_parts.append(f'{param.name}={val_str}')
            elif param.is_required:
                raise ValueError(f"Missing required parameter: {param.name}")

        args_str = ", ".join(arg_parts)
        return f"{source_var}.{self.method_name}({args_str})"


@dataclass
class ValidationError:
    """Represents a validation error."""
    error_type: str
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None
    severity: str = "error"  # error, warning, info


@dataclass
class OperationPlan:
    """A validated plan for code generation."""
    operations: List[ValidOperation]
    variable_bindings: Dict[str, str]  # var_name -> class_name
    import_statements: List[str]
    initialization_code: str
    finalization_code: str
    validation_errors: List[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len([e for e in self.validation_errors if e.severity == "error"]) == 0


# ============================================================================
# Known Hallucination Mappings (Deterministic Fixes)
# ============================================================================

# These are KNOWN LLM hallucinations that we fix deterministically
# Key: hallucinated method -> Value: correct method
HALLUCINATION_FIXES: Dict[str, str] = {
    # Behavior methods
    'new_SwcInternalBehavior': 'new_InternalBehavior',
    'new_RunnableEntity': 'new_Runnable',

    # Data access (note the spelling)
    'new_DataReadAccess': 'new_DataReadAcces',
    'new_DataWriteAccess': 'new_DataWriteAcces',

    # Data elements
    'new_VariableDataPrototype': 'new_DataElement',
    'new_ServiceEvent': 'new_Event',

    # Components
    'new_SwComponentPrototype': 'new_Component',
    'new_ComponentPrototype': 'new_Component',

    # SOME/IP (lowercase 'p')
    'new_SomeIpServiceInterfaceDeployment': 'new_SomeipServiceInterfaceDeployment',
    'new_SomeIpEventDeployment': 'new_SomeipEventDeployment',
    'new_SomeIpMethodDeployment': 'new_SomeipMethodDeployment',

    # System mapping
    'new_SwcToEcuMapping': 'new_SwMapping',
    'new_SoftwareComponentToEcuMapping': 'new_SwMapping',

    # Reference setters
    'set_targetDataPrototype': 'set_targetDataElement',
    'set_variableDataPrototype': 'set_targetDataPrototype',
    'set_communicationCluster': 'set_commController',

    # Signal service translation
    'new_SignalServiceTranslationProps': 'new_SignalServiceTranslationProp',
}

# Reverse mapping for quick lookup
CORRECT_TO_WRONG: Dict[str, List[str]] = {}
for wrong, correct in HALLUCINATION_FIXES.items():
    if correct not in CORRECT_TO_WRONG:
        CORRECT_TO_WRONG[correct] = []
    CORRECT_TO_WRONG[correct].append(wrong)


# ============================================================================
# Unified Knowledge Base
# ============================================================================

class UnifiedKnowledgeBase:
    """
    The unified source of truth for code generation.

    Integrates:
    - Symbol Table: Ground truth of what methods/classes exist
    - Code Graph: Relationships between classes
    - Validation Rules: Pre-generation validation
    - Hallucination Prevention: Known fixes
    """

    def __init__(self, force_rebuild: bool = False):
        """Initialize the unified knowledge base."""
        print("Initializing Unified Knowledge Base...")

        # Core components
        self.symbol_table = get_symbol_table(force_rebuild)
        self.code_graph = get_code_graph(force_rebuild)

        # Caches
        self._method_cache: Dict[str, List[MethodSignature]] = {}
        self._factory_return_cache: Dict[str, Dict[str, str]] = {}
        self._valid_chains_cache: Dict[str, Set[str]] = {}

        # Build indexes
        self._build_indexes()

        print(f"Knowledge Base initialized: {len(self.symbol_table.classes)} classes")

    def _build_indexes(self):
        """Build additional indexes for fast lookup."""
        # Build factory return type index
        for class_name, class_info in self.symbol_table.classes.items():
            self._factory_return_cache[class_name] = {}
            for method in class_info.factory_methods:
                if method.return_type:
                    return_type = self._extract_class_name(method.return_type)
                    if return_type:
                        self._factory_return_cache[class_name][method.name] = return_type

    def _extract_class_name(self, type_str: str) -> Optional[str]:
        """Extract class name from type annotation string."""
        if not type_str:
            return None

        # Handle "<class 'autosarfactory.autosarfactory.ClassName'>"
        if "autosarfactory." in type_str:
            parts = type_str.split(".")
            return parts[-1].rstrip("'>")

        # Handle "Optional[ClassName]" or "List[ClassName]"
        import re
        match = re.search(r'\[(\w+)\]', type_str)
        if match:
            return match.group(1)

        # Plain class name
        if type_str in self.symbol_table.classes:
            return type_str

        return None

    # ========================================================================
    # Ground Truth Queries
    # ========================================================================

    def class_exists(self, class_name: str) -> bool:
        """Check if a class exists in the ground truth."""
        return class_name in self.symbol_table.classes

    def method_exists(self, method_name: str, class_name: str = None) -> bool:
        """Check if a method exists, optionally scoped to a class."""
        return self.symbol_table.has_method(method_name, class_name)

    def get_valid_methods(self, class_name: str,
                          include_inherited: bool = True,
                          method_type: str = None) -> List[str]:
        """
        Get all valid method names for a class.

        Args:
            class_name: The class to query
            include_inherited: Include methods from parent classes
            method_type: Filter by type ('factory', 'setter', 'getter', None for all)

        Returns:
            List of valid method names
        """
        methods = self.code_graph.get_valid_methods_for_class(class_name, include_inherited)

        if method_type:
            prefix_map = {
                'factory': 'new_',
                'setter': 'set_',
                'getter': 'get_'
            }
            prefix = prefix_map.get(method_type)
            if prefix:
                methods = [m for m in methods if m.startswith(prefix)]

        return sorted(methods)

    def get_method_signature(self, method_name: str,
                            class_name: str = None) -> Optional[MethodSignature]:
        """Get the full signature for a method."""
        return self.symbol_table.get_signature(method_name, class_name)

    def get_factory_return_type(self, class_name: str,
                                factory_method: str) -> Optional[str]:
        """Get what type a factory method returns."""
        if class_name in self._factory_return_cache:
            return self._factory_return_cache[class_name].get(factory_method)
        return None

    def is_abstract(self, class_name: str) -> bool:
        """Check if a class is abstract."""
        if class_name not in self.symbol_table.classes:
            return False
        return self.symbol_table.classes[class_name].is_abstract

    def can_instantiate(self, class_name: str) -> bool:
        """Check if a class can be instantiated."""
        if class_name not in self.symbol_table.classes:
            return False
        return self.symbol_table.classes[class_name].can_instantiate

    # ========================================================================
    # Hallucination Prevention
    # ========================================================================

    def fix_hallucinated_method(self, method_name: str) -> Tuple[str, bool]:
        """
        Fix a hallucinated method name.

        Returns:
            Tuple of (corrected_name, was_fixed)
        """
        if method_name in HALLUCINATION_FIXES:
            return HALLUCINATION_FIXES[method_name], True
        return method_name, False

    def get_correct_method(self, hallucinated: str) -> Optional[str]:
        """Get the correct method name for a known hallucination."""
        return HALLUCINATION_FIXES.get(hallucinated)

    def find_similar_method(self, method_name: str,
                            class_name: str = None,
                            limit: int = 3) -> List[str]:
        """Find methods similar to the given name."""
        if class_name:
            candidates = self.get_valid_methods(class_name)
        else:
            candidates = list(self.symbol_table._method_index.keys())

        return difflib.get_close_matches(method_name, candidates, n=limit, cutoff=0.6)

    def validate_method_call(self, class_name: str,
                            method_name: str,
                            arguments: Dict[str, Any] = None) -> Tuple[bool, List[ValidationError]]:
        """
        Validate a method call against ground truth.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check class exists
        if not self.class_exists(class_name):
            errors.append(ValidationError(
                error_type="class_not_found",
                message=f"Class '{class_name}' does not exist",
                suggestion=self._suggest_class(class_name)
            ))
            return False, errors

        # Fix potential hallucination
        corrected_method, was_fixed = self.fix_hallucinated_method(method_name)
        if was_fixed:
            errors.append(ValidationError(
                error_type="hallucination_fixed",
                message=f"'{method_name}' was corrected to '{corrected_method}'",
                severity="warning"
            ))
            method_name = corrected_method

        # Check method exists on class
        if not self.method_exists(method_name, class_name):
            similar = self.find_similar_method(method_name, class_name)
            suggestion = f"Did you mean: {', '.join(similar)}?" if similar else None
            errors.append(ValidationError(
                error_type="method_not_found",
                message=f"Method '{method_name}' not found on '{class_name}'",
                suggestion=suggestion
            ))
            return False, errors

        # Validate arguments if provided
        if arguments:
            signature = self.get_method_signature(method_name, class_name)
            if signature:
                arg_errors = self._validate_arguments(signature, arguments)
                errors.extend(arg_errors)

        has_errors = any(e.severity == "error" for e in errors)
        return not has_errors, errors

    def _validate_arguments(self, signature: MethodSignature,
                           arguments: Dict[str, Any]) -> List[ValidationError]:
        """Validate arguments against a method signature."""
        errors = []

        # Check required parameters
        required = {p.name for p in signature.parameters if p.is_required}
        provided = set(arguments.keys())

        missing = required - provided
        for param in missing:
            errors.append(ValidationError(
                error_type="missing_argument",
                message=f"Missing required argument: {param}"
            ))

        # Check for unknown parameters
        valid_params = {p.name for p in signature.parameters}
        unknown = provided - valid_params
        for param in unknown:
            similar = difflib.get_close_matches(param, list(valid_params), n=1)
            suggestion = f"Did you mean '{similar[0]}'?" if similar else None
            errors.append(ValidationError(
                error_type="unknown_argument",
                message=f"Unknown argument: {param}",
                suggestion=suggestion
            ))

        return errors

    def _suggest_class(self, class_name: str) -> Optional[str]:
        """Suggest a class name for a misspelled one."""
        candidates = list(self.symbol_table.classes.keys())
        matches = difflib.get_close_matches(class_name, candidates, n=1, cutoff=0.6)
        return f"Did you mean '{matches[0]}'?" if matches else None

    # ========================================================================
    # Graph-Based Queries
    # ========================================================================

    def get_creation_chain(self, target_class: str) -> List[Tuple[str, str, str]]:
        """
        Get the chain of factory methods to create a target class.

        Returns:
            List of (source_class, factory_method, result_class) tuples
        """
        return self.code_graph.get_required_context(target_class)

    def get_class_hierarchy(self, class_name: str) -> List[str]:
        """Get the inheritance hierarchy for a class."""
        return self.code_graph.get_inheritance_chain(class_name)

    def get_related_classes(self, class_name: str, depth: int = 2) -> Set[str]:
        """Get classes related to this one (for context)."""
        related = set()
        related.update(self.code_graph.get_required_context(class_name, depth))
        related.update(self.code_graph.get_inheritance_chain(class_name))

        # Add factory return types
        for factory, return_type in self.code_graph.get_factory_methods(class_name):
            if return_type:
                related.add(return_type)

        return related

    # ========================================================================
    # Constraint Generation
    # ========================================================================

    def build_constraint_set(self, class_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Build a complete constraint set for code generation.

        This is the core of the "Constrained Decoding" approach - we enumerate
        all valid options so the LLM can only select from them.

        Returns:
            Dict with structure:
            {
                "class_name": {
                    "factory_methods": ["new_X", "new_Y"],
                    "setters": ["set_A", "set_B"],
                    "factory_returns": {"new_X": "ClassX", "new_Y": "ClassY"}
                }
            }
        """
        constraints = {}

        for class_name in class_names:
            if not self.class_exists(class_name):
                continue

            factory_methods = self.get_valid_methods(class_name, method_type='factory')
            setters = self.get_valid_methods(class_name, method_type='setter')

            # Get return types for factory methods
            factory_returns = {}
            for method in factory_methods:
                return_type = self.get_factory_return_type(class_name, method)
                if return_type:
                    factory_returns[method] = return_type

            constraints[class_name] = {
                "factory_methods": factory_methods,
                "setters": setters,
                "factory_returns": factory_returns,
                "is_abstract": self.is_abstract(class_name)
            }

        return constraints

    def generate_constraint_prompt(self, class_names: List[str],
                                   max_methods_per_class: int = 20) -> str:
        """
        Generate a prompt section that constrains the LLM.

        This is injected into the prompt to mathematically prevent
        the LLM from selecting invalid methods.
        """
        constraints = self.build_constraint_set(class_names)

        lines = [
            "=" * 60,
            "VALID API METHODS - YOU MUST USE ONLY THESE",
            "=" * 60,
            "",
            "The following is an EXHAUSTIVE list of valid methods.",
            "Using ANY method not in this list will cause an error.",
            ""
        ]

        for class_name, data in sorted(constraints.items()):
            if data.get("is_abstract"):
                lines.append(f"[ABSTRACT - Cannot instantiate] {class_name}")
            else:
                lines.append(f"### {class_name}")

            # Factory methods
            factories = data.get("factory_methods", [])
            factory_returns = data.get("factory_returns", {})
            if factories:
                lines.append("  Factory methods (create child elements):")
                for method in factories[:max_methods_per_class]:
                    return_type = factory_returns.get(method, "?")
                    lines.append(f"    - {method}() -> {return_type}")
                if len(factories) > max_methods_per_class:
                    lines.append(f"    ... and {len(factories) - max_methods_per_class} more")

            # Setters
            setters = data.get("setters", [])
            if setters:
                lines.append("  Setters (configure this element):")
                for method in setters[:max_methods_per_class]:
                    lines.append(f"    - {method}()")
                if len(setters) > max_methods_per_class:
                    lines.append(f"    ... and {len(setters) - max_methods_per_class} more")

            lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)

    # ========================================================================
    # Operation Validation
    # ========================================================================

    def validate_operation_plan(self, operations: List[Dict[str, Any]]) -> List[ValidationError]:
        """
        Validate a complete operation plan before code generation.

        Each operation should be a dict with:
        - source_var: Variable name to call method on
        - source_class: Class type of source_var
        - method_name: Method to call
        - arguments: Dict of arguments
        - result_var: Variable to store result (optional)
        """
        errors = []
        var_types: Dict[str, str] = {}  # Track variable types

        for i, op in enumerate(operations):
            source_class = op.get('source_class')
            method_name = op.get('method_name')
            arguments = op.get('arguments', {})
            result_var = op.get('result_var')

            # Validate the method call
            is_valid, method_errors = self.validate_method_call(
                source_class, method_name, arguments
            )

            for error in method_errors:
                error.location = f"Operation {i+1}: {source_class}.{method_name}"
                errors.append(error)

            # Track result type for chain validation
            if result_var and is_valid:
                return_type = self.get_factory_return_type(source_class, method_name)
                if return_type:
                    var_types[result_var] = return_type

        return errors

    def create_valid_operation(self, source_class: str,
                               method_name: str,
                               arguments: Dict[str, Any] = None) -> Tuple[Optional[ValidOperation], List[ValidationError]]:
        """
        Create a validated operation object.

        Returns:
            Tuple of (ValidOperation or None, list_of_errors)
        """
        arguments = arguments or {}

        # Validate the method call
        is_valid, errors = self.validate_method_call(source_class, method_name, arguments)

        if not is_valid:
            return None, errors

        # Get signature
        signature = self.get_method_signature(method_name, source_class)
        if not signature:
            return None, [ValidationError(
                error_type="signature_not_found",
                message=f"Could not retrieve signature for {source_class}.{method_name}"
            )]

        # Determine operation type
        if method_name.startswith('new_'):
            op_type = OperationType.CREATE_ELEMENT
            creates_type = self.get_factory_return_type(source_class, method_name)
        elif method_name.startswith('set_'):
            op_type = OperationType.SET_ATTRIBUTE
            creates_type = None
        elif method_name.startswith('get_'):
            op_type = OperationType.ITERATE
            creates_type = None
        else:
            op_type = OperationType.SET_ATTRIBUTE
            creates_type = None

        operation = ValidOperation(
            operation_type=op_type,
            source_class=source_class,
            method_name=method_name,
            parameters=signature.parameters,
            return_type=signature.return_type,
            creates_type=creates_type
        )

        return operation, errors


# ============================================================================
# Singleton Access
# ============================================================================

_kb_instance: Optional[UnifiedKnowledgeBase] = None


def get_knowledge_base(force_rebuild: bool = False) -> UnifiedKnowledgeBase:
    """Get the global knowledge base instance."""
    global _kb_instance

    if _kb_instance is None or force_rebuild:
        _kb_instance = UnifiedKnowledgeBase(force_rebuild=force_rebuild)

    return _kb_instance


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing Unified Knowledge Base...")

    kb = get_knowledge_base()

    # Test ground truth queries
    print("\n=== Ground Truth Queries ===")
    print(f"CanCluster exists: {kb.class_exists('CanCluster')}")
    print(f"FakeClass exists: {kb.class_exists('FakeClass')}")

    # Test method validation
    print("\n=== Method Validation ===")
    is_valid, errors = kb.validate_method_call("CanCluster", "new_CanClusterVariant")
    print(f"CanCluster.new_CanClusterVariant: valid={is_valid}")

    is_valid, errors = kb.validate_method_call("CanCluster", "new_SwcInternalBehavior")
    print(f"CanCluster.new_SwcInternalBehavior: valid={is_valid}, errors={[e.message for e in errors]}")

    # Test hallucination fix
    print("\n=== Hallucination Prevention ===")
    corrected, was_fixed = kb.fix_hallucinated_method("new_SwcInternalBehavior")
    print(f"new_SwcInternalBehavior -> {corrected} (fixed={was_fixed})")

    # Test constraint generation
    print("\n=== Constraint Generation ===")
    prompt = kb.generate_constraint_prompt(["CanCluster", "CanFrame"])
    print(prompt[:500] + "...")
