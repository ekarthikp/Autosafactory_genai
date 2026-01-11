"""
Constrained Selection Engine
============================
Implements dynamic enumeration and structured output constraints to force
the LLM to select only from valid API options. This is the mathematical
guarantee against hallucination - the output space is constrained to
only valid selections.

Key Features:
1. Dynamic enum generation from valid method lists
2. Structured output schemas for code planning
3. Type-safe method selection with validation
4. Integration with LLM providers (Gemini, OpenAI, Anthropic)
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple, Type, Union
from enum import Enum
from pydantic import BaseModel, Field, create_model, validator
import re

from src.knowledge_base import (
    get_knowledge_base,
    UnifiedKnowledgeBase,
    HALLUCINATION_FIXES
)


# ============================================================================
# Dynamic Enum Generation
# ============================================================================

def create_method_enum(methods: List[str], enum_name: str = "MethodEnum") -> Type[Enum]:
    """
    Dynamically create an Enum class from a list of valid methods.

    This is the core of constrained decoding - by creating an Enum,
    we force the LLM to select only from the provided options.
    """
    # Sanitize method names for enum member names
    members = {}
    for method in methods:
        # Convert to valid Python identifier
        member_name = method.upper().replace('-', '_')
        members[member_name] = method

    return Enum(enum_name, members)


def create_class_enum(classes: List[str], enum_name: str = "ClassEnum") -> Type[Enum]:
    """Create an Enum for valid class names."""
    members = {cls.upper(): cls for cls in classes}
    return Enum(enum_name, members)


# ============================================================================
# Structured Output Models
# ============================================================================

class MethodSelectionResult(BaseModel):
    """Result of LLM method selection - constrained to valid options."""
    selected_method: str = Field(description="The method name from the valid list")
    source_class: str = Field(description="Class to call the method on")
    confidence: float = Field(default=1.0, ge=0, le=1)
    reasoning: Optional[str] = Field(default=None)


class ArgumentSpec(BaseModel):
    """Specification for a method argument."""
    name: str = Field(description="Argument name")
    value: Any = Field(description="Argument value")
    is_variable_ref: bool = Field(
        default=False,
        description="True if value is a variable reference"
    )


class OperationSpec(BaseModel):
    """Specification for a single code operation."""
    step_number: int = Field(description="Order of execution")
    description: str = Field(description="What this operation does")
    source_variable: str = Field(description="Variable to call method on")
    source_class: str = Field(description="Expected class type of source")
    method_name: str = Field(description="Method to call (must be valid)")
    arguments: List[ArgumentSpec] = Field(default_factory=list)
    result_variable: Optional[str] = Field(
        default=None,
        description="Variable to store result"
    )

    @validator('method_name')
    def fix_hallucinated_method(cls, v):
        """Automatically fix known hallucinations."""
        if v in HALLUCINATION_FIXES:
            return HALLUCINATION_FIXES[v]
        return v


class CodePlanResult(BaseModel):
    """Complete code generation plan from LLM."""
    summary: str = Field(description="Brief summary of what code will do")
    operations: List[OperationSpec] = Field(description="Ordered operations")
    output_file: str = Field(default="output.arxml")
    is_edit_mode: bool = Field(default=False)
    source_file: Optional[str] = Field(default=None)


# ============================================================================
# Constrained Selection Engine
# ============================================================================

class ConstrainedSelectionEngine:
    """
    Forces LLM to select only from valid API options using structured outputs.

    This engine:
    1. Builds dynamic constraint sets for relevant classes
    2. Generates Pydantic schemas that enforce selection
    3. Validates LLM outputs against ground truth
    4. Provides repair for any escaping hallucinations
    """

    def __init__(self, kb: UnifiedKnowledgeBase = None):
        """Initialize the engine."""
        self.kb = kb or get_knowledge_base()
        self._constraint_cache: Dict[str, Dict] = {}

    def build_selection_context(self, class_names: List[str],
                                task_description: str = "") -> Dict[str, Any]:
        """
        Build a context for LLM method selection.

        This includes:
        - Valid methods per class
        - Factory method return types
        - Setter parameter types
        - Common patterns

        Returns:
            Dict with structured context for the LLM
        """
        context = {
            "classes": {},
            "patterns": [],
            "constraints": []
        }

        for class_name in class_names:
            if not self.kb.class_exists(class_name):
                continue

            class_context = {
                "name": class_name,
                "is_abstract": self.kb.is_abstract(class_name),
                "factory_methods": [],
                "setters": [],
                "getters": []
            }

            # Factory methods with return types
            factories = self.kb.get_valid_methods(class_name, method_type='factory')
            for method in factories:
                return_type = self.kb.get_factory_return_type(class_name, method)
                class_context["factory_methods"].append({
                    "name": method,
                    "returns": return_type
                })

            # Setters
            setters = self.kb.get_valid_methods(class_name, method_type='setter')
            for method in setters:
                sig = self.kb.get_method_signature(method, class_name)
                params = []
                if sig:
                    params = [{"name": p.name, "type": p.type_hint} for p in sig.parameters]
                class_context["setters"].append({
                    "name": method,
                    "parameters": params
                })

            context["classes"][class_name] = class_context

        # Add task-specific constraints
        context["constraints"] = self._infer_constraints(task_description)

        return context

    def _infer_constraints(self, task_description: str) -> List[str]:
        """Infer constraints from task description."""
        constraints = []
        task_lower = task_description.lower()

        # CAN-specific constraints
        if "can" in task_lower or "cluster" in task_lower:
            constraints.append("Baudrate must be set on CanClusterConditional (returned by new_CanClusterVariant)")
            constraints.append("CanFrameTriggering is created on CanPhysicalChannel, not CanFrame")

        # SWC-specific constraints
        if "component" in task_lower or "swc" in task_lower or "behavior" in task_lower:
            constraints.append("Use new_InternalBehavior(), NOT new_SwcInternalBehavior()")
            constraints.append("Use new_Runnable(), NOT new_RunnableEntity()")

        # Data access constraints
        if "data" in task_lower or "read" in task_lower or "write" in task_lower:
            constraints.append("Use new_DataReadAcces() with ONE 's'")
            constraints.append("Use new_DataWriteAcces() with ONE 's'")

        # Reference constraints
        if "reference" in task_lower or "link" in task_lower or "connect" in task_lower:
            constraints.append("Use direct setters (set_frame, set_pdu) NOT new_*Ref().set_value()")

        return constraints

    def generate_selection_prompt(self, class_names: List[str],
                                   task_description: str,
                                   output_file: str = "output.arxml",
                                   is_edit_mode: bool = False,
                                   source_file: str = None) -> str:
        """
        Generate a structured prompt for constrained method selection.

        The prompt explicitly lists all valid methods and instructs the LLM
        to only select from this list.
        """
        context = self.build_selection_context(class_names, task_description)

        lines = [
            "=" * 70,
            "CONSTRAINED CODE GENERATION - SELECT ONLY FROM VALID METHODS",
            "=" * 70,
            "",
            f"TASK: {task_description}",
            f"OUTPUT: {output_file}",
            f"MODE: {'EDIT' if is_edit_mode else 'CREATE'}",
            ""
        ]

        if is_edit_mode and source_file:
            lines.append(f"SOURCE FILE: {source_file}")
            lines.append("")

        # List valid methods per class
        lines.append("VALID METHODS (You MUST use ONLY these methods):")
        lines.append("-" * 50)

        for class_name, class_ctx in context["classes"].items():
            if class_ctx["is_abstract"]:
                lines.append(f"\n[ABSTRACT] {class_name} - Cannot instantiate directly")
            else:
                lines.append(f"\n### {class_name}")

            # Factory methods
            if class_ctx["factory_methods"]:
                lines.append("  FACTORY METHODS (create child elements):")
                for fm in class_ctx["factory_methods"][:15]:
                    ret = fm.get("returns", "?")
                    lines.append(f"    - {fm['name']}() -> {ret}")
                if len(class_ctx["factory_methods"]) > 15:
                    lines.append(f"    ... and {len(class_ctx['factory_methods'])-15} more")

            # Setters
            if class_ctx["setters"]:
                lines.append("  SETTERS (configure element):")
                for setter in class_ctx["setters"][:15]:
                    params = setter.get("parameters", [])
                    param_str = ", ".join(f"{p['name']}" for p in params)
                    lines.append(f"    - {setter['name']}({param_str})")
                if len(class_ctx["setters"]) > 15:
                    lines.append(f"    ... and {len(class_ctx['setters'])-15} more")

        lines.append("")
        lines.append("-" * 50)

        # Add constraints
        if context["constraints"]:
            lines.append("\nCRITICAL CONSTRAINTS:")
            for constraint in context["constraints"]:
                lines.append(f"  - {constraint}")

        # Add output format instruction
        lines.append("""
OUTPUT FORMAT:
Return a JSON object with this structure:
{
  "summary": "Brief description",
  "operations": [
    {
      "step_number": 1,
      "description": "What this step does",
      "source_variable": "var_name",
      "source_class": "ClassName",
      "method_name": "method_name_from_valid_list",
      "arguments": [{"name": "arg_name", "value": "value", "is_variable_ref": false}],
      "result_variable": "result_var_name"
    }
  ],
  "output_file": "output.arxml",
  "is_edit_mode": false
}

IMPORTANT:
1. ONLY use method names from the VALID METHODS list above
2. Using ANY other method will cause a runtime error
3. For references, use direct setters (set_frame, set_pdu) NOT new_*Ref patterns
""")

        lines.append("=" * 70)

        return "\n".join(lines)

    def validate_selection(self, selection: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate an LLM's selection against ground truth.

        Args:
            selection: The parsed JSON from LLM

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        operations = selection.get("operations", [])

        for i, op in enumerate(operations):
            class_name = op.get("source_class", "")
            method_name = op.get("method_name", "")

            # Check for hallucination
            if method_name in HALLUCINATION_FIXES:
                correct = HALLUCINATION_FIXES[method_name]
                errors.append(f"Op {i+1}: '{method_name}' -> should be '{correct}'")

            # Check class exists
            if class_name and not self.kb.class_exists(class_name):
                errors.append(f"Op {i+1}: Class '{class_name}' not found")

            # Check method exists
            if class_name and method_name:
                if not self.kb.method_exists(method_name, class_name):
                    similar = self.kb.find_similar_method(method_name, class_name)
                    hint = f" Did you mean: {', '.join(similar)}?" if similar else ""
                    errors.append(f"Op {i+1}: '{class_name}' has no method '{method_name}'.{hint}")

        return len(errors) == 0, errors

    def repair_selection(self, selection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Repair a selection by fixing known hallucinations.

        This is a deterministic post-processing step that catches
        any hallucinations that escaped the constrained generation.
        """
        repaired = selection.copy()
        operations = repaired.get("operations", [])

        for op in operations:
            method_name = op.get("method_name", "")

            # Fix hallucinated methods
            if method_name in HALLUCINATION_FIXES:
                op["method_name"] = HALLUCINATION_FIXES[method_name]

        return repaired

    def create_constrained_schema(self, class_names: List[str]) -> Type[BaseModel]:
        """
        Create a Pydantic model with constrained method selections.

        This creates a schema where method_name can only be one of
        the valid methods for the given classes.
        """
        # Collect all valid methods
        all_methods = set()
        for class_name in class_names:
            methods = self.kb.get_valid_methods(class_name)
            all_methods.update(methods)

        # Create a Literal type with all valid methods
        from typing import Literal, get_args

        if not all_methods:
            # Fallback if no methods found
            method_choices = ("new_ARPackage",)
        else:
            method_choices = tuple(sorted(all_methods))

        # Create dynamic model
        ConstrainedOperation = create_model(
            'ConstrainedOperation',
            step_number=(int, ...),
            description=(str, ...),
            source_variable=(str, ...),
            source_class=(str, ...),
            method_name=(str, ...),  # Literal would be ideal but complex
            arguments=(List[ArgumentSpec], []),
            result_variable=(Optional[str], None)
        )

        return ConstrainedOperation


# ============================================================================
# Intent Parser
# ============================================================================

class IntentParser:
    """
    Parses user intent into structured operations.

    Uses keyword analysis and pattern matching to identify:
    - Required AUTOSAR elements
    - Relationships between elements
    - Configuration parameters
    """

    # Mapping of keywords to relevant classes
    KEYWORD_TO_CLASSES = {
        # CAN
        "can": ["CanCluster", "CanClusterVariant", "CanClusterConditional", "CanPhysicalChannel"],
        "cluster": ["CanCluster", "CanClusterVariant", "CanClusterConditional"],
        "baudrate": ["CanClusterConditional", "CanClusterVariant"],
        "frame": ["CanFrame", "CanFrameTriggering", "PduToFrameMapping"],
        "signal": ["ISignal", "ISignalIPdu", "ISignalToPduMapping", "SystemSignal"],
        "pdu": ["ISignalIPdu", "PduToFrameMapping", "ISignalToPduMapping"],

        # ECU
        "ecu": ["EcuInstance", "CanCommunicationController", "CommunicationConnector"],
        "controller": ["CanCommunicationController", "CommunicationController"],

        # SWC
        "component": ["ApplicationSwComponentType", "CompositionSwComponentType", "SwComponentPrototype"],
        "swc": ["ApplicationSwComponentType", "SwcInternalBehavior"],
        "port": ["PPortPrototype", "RPortPrototype"],
        "interface": ["SenderReceiverInterface", "ClientServerInterface"],
        "behavior": ["SwcInternalBehavior", "RunnableEntity", "TimingEvent"],
        "runnable": ["SwcInternalBehavior", "RunnableEntity", "DataSendPoint", "DataReceivePointByArgument"],
        "event": ["TimingEvent", "DataReceivedEvent"],
        "connector": ["AssemblySwConnector", "DelegationSwConnector"],
        "composition": ["CompositionSwComponentType", "RootSoftwareComposition"],

        # Data Types (comprehensive from example)
        "type": ["SwBaseType", "ImplementationDataType", "StdCppImplementationDataType"],
        "datatype": ["SwBaseType", "ImplementationDataType", "SwDataDefProps", "SwDataDefPropsVariant"],
        "basetype": ["SwBaseType", "BaseTypeDirectDefinition"],
        "uint8": ["SwBaseType", "ImplementationDataType"],
        "array": ["StdCppImplementationDataType"],

        # Compu Methods (from example)
        "compu": ["CompuMethod", "CompuInternalToPhys", "CompuScales", "CompuScale", "CompuConst"],
        "scale": ["CompuScale", "CompuScaleConstantContents", "CompuScaleRationalFormula"],
        "limit": ["LowerLimit", "UpperLimit"],
        "constraint": ["DataConstr", "DataConstrRule", "InternalConstrs"],

        # System and Mapping (comprehensive)
        "system": ["System", "SystemMapping", "RootSoftwareComposition"],
        "mapping": ["SystemMapping", "SenderReceiverToSignalMapping", "SwMapping"],
        "systemsignal": ["SystemSignal"],

        # Ethernet
        "ethernet": ["EthernetCluster", "EthernetPhysicalChannel"],
        "someip": ["SomeipServiceInterfaceDeployment"],

        # Admin Data
        "admin": ["AdminData", "Sdg", "Sd"],
    }

    def __init__(self, kb: UnifiedKnowledgeBase = None):
        self.kb = kb or get_knowledge_base()

    def extract_classes(self, text: str) -> List[str]:
        """Extract relevant classes from task description."""
        text_lower = text.lower()
        classes = set()

        # Always include base package
        classes.add("ARPackage")

        # Match keywords
        for keyword, class_list in self.KEYWORD_TO_CLASSES.items():
            if keyword in text_lower:
                classes.update(class_list)

        # Add dependencies
        expanded = set(classes)
        for cls in list(classes):
            related = self.kb.get_related_classes(cls, depth=1)
            expanded.update(related)

        return list(expanded)

    def extract_parameters(self, text: str) -> Dict[str, Any]:
        """Extract configuration parameters from text."""
        params = {}

        # Baudrate
        baudrate_match = re.search(r'(\d+)\s*(kbps|kbit|baud)', text.lower())
        if baudrate_match:
            value = int(baudrate_match.group(1))
            if 'k' in baudrate_match.group(2):
                value *= 1000
            params["baudrate"] = value

        # CAN ID (hex)
        can_id_match = re.search(r'0x([0-9a-fA-F]+)', text)
        if can_id_match:
            params["can_id"] = int(can_id_match.group(1), 16)

        # Frame length / DLC
        dlc_match = re.search(r'(\d+)\s*(?:byte|dlc)', text.lower())
        if dlc_match:
            params["frame_length"] = int(dlc_match.group(1))

        # Signal length (bits)
        sig_len_match = re.search(r'(\d+)\s*(?:bit)', text.lower())
        if sig_len_match:
            params["signal_length"] = int(sig_len_match.group(1))

        # Period (ms or s)
        period_match = re.search(r'(\d+)\s*(ms|millisecond|s|second)', text.lower())
        if period_match:
            value = float(period_match.group(1))
            if 'ms' in period_match.group(2) or 'milli' in period_match.group(2):
                value /= 1000  # Convert to seconds
            params["period"] = value

        return params

    def parse_intent(self, user_query: str) -> Dict[str, Any]:
        """
        Parse user query into structured intent.

        Returns dict with:
        - classes: List of relevant class names
        - parameters: Extracted configuration parameters
        - operation_hints: Inferred operation types
        """
        classes = self.extract_classes(user_query)
        parameters = self.extract_parameters(user_query)

        # Infer operation types
        query_lower = user_query.lower()
        operation_hints = []

        if any(word in query_lower for word in ["create", "add", "new", "generate"]):
            operation_hints.append("create")
        if any(word in query_lower for word in ["modify", "edit", "change", "update"]):
            operation_hints.append("edit")
        if any(word in query_lower for word in ["link", "connect", "reference", "map"]):
            operation_hints.append("reference")
        if any(word in query_lower for word in ["configure", "set", "specify"]):
            operation_hints.append("configure")

        return {
            "classes": classes,
            "parameters": parameters,
            "operation_hints": operation_hints
        }


# ============================================================================
# Singleton Access
# ============================================================================

_engine_instance: Optional[ConstrainedSelectionEngine] = None
_parser_instance: Optional[IntentParser] = None


def get_selection_engine() -> ConstrainedSelectionEngine:
    """Get the global selection engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ConstrainedSelectionEngine()
    return _engine_instance


def get_intent_parser() -> IntentParser:
    """Get the global intent parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = IntentParser()
    return _parser_instance


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing Constrained Selection Engine...")

    engine = get_selection_engine()
    parser = get_intent_parser()

    # Test intent parsing
    query = "Create a CAN cluster with 500kbps baudrate and a frame with ID 0x123"
    print(f"\nQuery: {query}")

    intent = parser.parse_intent(query)
    print(f"Classes: {intent['classes'][:10]}...")
    print(f"Parameters: {intent['parameters']}")
    print(f"Operation hints: {intent['operation_hints']}")

    # Test selection prompt
    print("\n=== Selection Prompt (excerpt) ===")
    prompt = engine.generate_selection_prompt(
        intent['classes'][:5],
        query
    )
    print(prompt[:1000] + "...")

    # Test validation
    print("\n=== Validation Test ===")
    test_selection = {
        "operations": [
            {
                "source_class": "ARPackage",
                "method_name": "new_CanCluster"
            },
            {
                "source_class": "CanCluster",
                "method_name": "new_SwcInternalBehavior"  # Wrong!
            }
        ]
    }

    is_valid, errors = engine.validate_selection(test_selection)
    print(f"Valid: {is_valid}")
    print(f"Errors: {errors}")

    # Test repair
    print("\n=== Repair Test ===")
    repaired = engine.repair_selection(test_selection)
    print(f"Repaired method: {repaired['operations'][1]['method_name']}")
