"""
Deterministic Code Synthesizer
==============================
Generates Python code from validated operation plans without hallucination.
This is the core of the neuro-symbolic architecture - the LLM provides intent,
but the actual code is synthesized deterministically from ground truth.

Key Features:
1. Template-based code generation from validated operations
2. Type-safe variable tracking
3. Automatic import resolution
4. Reference chain validation
5. Error handling injection
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from enum import Enum, auto
from pydantic import BaseModel, Field, validator
import re

from src.knowledge_base import (
    get_knowledge_base,
    UnifiedKnowledgeBase,
    ValidOperation,
    OperationType,
    ValidationError,
    HALLUCINATION_FIXES
)


# ============================================================================
# Pydantic Models for Structured LLM Output
# ============================================================================

class ActionType(str, Enum):
    """Types of actions in code generation."""
    CREATE = "create"
    CONFIGURE = "configure"
    REFERENCE = "reference"
    ITERATE = "iterate"
    SAVE = "save"


class ParameterValue(BaseModel):
    """A parameter value - either literal or variable reference."""
    is_variable: bool = Field(default=False, description="True if this is a variable reference")
    value: Any = Field(description="The literal value or variable name")

    def to_code(self) -> str:
        """Convert to Python code."""
        if self.is_variable:
            return str(self.value)
        elif isinstance(self.value, str):
            return f'"{self.value}"'
        elif isinstance(self.value, bool):
            return str(self.value)
        elif isinstance(self.value, (int, float)):
            return str(self.value)
        else:
            return repr(self.value)


class APICallSpec(BaseModel):
    """Specification for a single API call."""
    result_variable: str = Field(description="Variable to store result")
    source_variable: str = Field(description="Object to call method on")
    method_name: str = Field(description="Method to call")
    arguments: Dict[str, ParameterValue] = Field(default_factory=dict)
    comment: Optional[str] = Field(default=None, description="Optional comment")

    class Config:
        extra = "forbid"


class CodeStepSpec(BaseModel):
    """Specification for a step in code generation."""
    step_number: int = Field(description="Execution order")
    description: str = Field(description="What this step does")
    action_type: ActionType = Field(description="Type of action")
    api_calls: List[APICallSpec] = Field(description="API calls in this step")

    class Config:
        extra = "forbid"


class CodePlanSpec(BaseModel):
    """Complete code generation plan - structured output from LLM."""
    description: str = Field(description="Brief description of what code does")
    output_file: str = Field(default="output.arxml")
    is_edit_mode: bool = Field(default=False)
    source_file: Optional[str] = Field(default=None)
    steps: List[CodeStepSpec] = Field(description="Ordered steps")

    class Config:
        extra = "forbid"


# ============================================================================
# Code Generation Templates
# ============================================================================

IMPORTS_TEMPLATE = """import autosarfactory.autosarfactory as autosarfactory
"""

CREATE_MODE_INIT_TEMPLATE = '''root_pkg = autosarfactory.new_file("{output_file}", defaultArPackage="Root", overWrite=True)
'''

EDIT_MODE_INIT_TEMPLATE = '''# Load existing file
autosar_root, status = autosarfactory.read(["{source_file}"])
if not status or not autosar_root:
    raise Exception("Failed to load ARXML file: {source_file}")

# === Discovery Helpers ===
def find_all_elements_by_type(root, type_name):
    """Find ALL elements of a given type anywhere in the file"""
    results = []
    def search(container):
        if hasattr(container, 'get_elements'):
            for elem in container.get_elements():
                if type(elem).__name__ == type_name:
                    results.append(elem)
        if hasattr(container, 'get_arPackages'):
            for pkg in container.get_arPackages():
                search(pkg)
    search(root)
    return results

def find_element_by_type(root, type_name):
    """Find FIRST element of a given type"""
    elements = find_all_elements_by_type(root, type_name)
    return elements[0] if elements else None
'''

SAVE_TEMPLATE = """autosarfactory.save()
print("ARXML file generated successfully!")
"""

MAIN_WRAPPER_TEMPLATE = '''
def main():
{body}

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open("execution_error.log", "w") as f:
            f.write(traceback.format_exc())
        print("Execution failed. See execution_error.log for details.")
        raise e
'''


# ============================================================================
# Variable Type Tracker
# ============================================================================

@dataclass
class VariableInfo:
    """Information about a variable in generated code."""
    name: str
    class_type: str
    line_number: int
    is_list: bool = False


class VariableTracker:
    """Tracks variable types throughout code generation."""

    def __init__(self, kb: UnifiedKnowledgeBase):
        self.kb = kb
        self.variables: Dict[str, VariableInfo] = {}
        self.line_counter = 0

    def register_variable(self, name: str, class_type: str, is_list: bool = False):
        """Register a new variable."""
        self.line_counter += 1
        self.variables[name] = VariableInfo(
            name=name,
            class_type=class_type,
            line_number=self.line_counter,
            is_list=is_list
        )

    def get_type(self, var_name: str) -> Optional[str]:
        """Get the type of a variable."""
        info = self.variables.get(var_name)
        return info.class_type if info else None

    def validate_method_call(self, var_name: str, method_name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that a method can be called on a variable.

        Returns:
            Tuple of (is_valid, error_message)
        """
        var_type = self.get_type(var_name)
        if not var_type:
            return True, None  # Unknown variable, assume valid

        if self.kb.method_exists(method_name, var_type):
            return True, None

        # Find similar methods
        similar = self.kb.find_similar_method(method_name, var_type)
        if similar:
            return False, f"Method '{method_name}' not found on '{var_type}'. Did you mean: {', '.join(similar)}?"

        return False, f"Method '{method_name}' not found on '{var_type}'"


# ============================================================================
# Deterministic Code Synthesizer
# ============================================================================

class DeterministicCodeSynthesizer:
    """
    Synthesizes Python code from validated operation plans.

    This class ensures that generated code:
    1. Uses ONLY methods that exist in the symbol table
    2. Has correct argument types and counts
    3. Follows proper reference patterns (direct setters, not new_*Ref())
    4. Includes proper error handling
    """

    def __init__(self, kb: UnifiedKnowledgeBase = None):
        """Initialize the synthesizer."""
        self.kb = kb or get_knowledge_base()
        self.var_tracker: Optional[VariableTracker] = None

    def synthesize_from_plan(self, plan: CodePlanSpec) -> Tuple[str, List[ValidationError]]:
        """
        Synthesize complete Python code from a CodePlanSpec.

        Args:
            plan: The structured code plan

        Returns:
            Tuple of (generated_code, validation_errors)
        """
        errors = []
        self.var_tracker = VariableTracker(self.kb)

        # Build code parts
        code_lines = []

        # 1. Imports
        code_lines.append(IMPORTS_TEMPLATE.strip())
        code_lines.append("")

        # 2. Main function body
        body_lines = []

        # 3. Initialization
        if plan.is_edit_mode:
            init_code = EDIT_MODE_INIT_TEMPLATE.format(
                source_file=plan.source_file or plan.output_file
            )
            body_lines.append(init_code)
            self.var_tracker.register_variable("autosar_root", "AUTOSAR")
        else:
            init_code = CREATE_MODE_INIT_TEMPLATE.format(output_file=plan.output_file)
            body_lines.append(init_code)
            self.var_tracker.register_variable("root_pkg", "ARPackage")

        # 4. Generate code for each step
        for step in plan.steps:
            step_code, step_errors = self._synthesize_step(step)
            body_lines.append(f"\n    # Step {step.step_number}: {step.description}")
            body_lines.extend(step_code)
            errors.extend(step_errors)

        # 5. Finalization
        body_lines.append("")
        body_lines.append("    # Save")
        body_lines.append("    " + SAVE_TEMPLATE.strip())

        # Wrap in main function
        body_text = "\n".join("    " + line if line.strip() else "" for line in body_lines)
        full_code = IMPORTS_TEMPLATE + MAIN_WRAPPER_TEMPLATE.format(body=body_text)

        # Post-process: apply deterministic fixes
        full_code = self._apply_deterministic_fixes(full_code)

        return full_code.strip(), errors

    def _synthesize_step(self, step: CodeStepSpec) -> Tuple[List[str], List[ValidationError]]:
        """Synthesize code for a single step."""
        lines = []
        errors = []

        for call in step.api_calls:
            call_code, call_errors = self._synthesize_api_call(call)
            lines.append("    " + call_code)
            errors.extend(call_errors)

        return lines, errors

    def _synthesize_api_call(self, call: APICallSpec) -> Tuple[str, List[ValidationError]]:
        """
        Synthesize code for a single API call.

        This is where we apply deterministic validation and fixes.
        """
        errors = []

        # 1. Fix potential hallucinated method
        method_name = call.method_name
        corrected, was_fixed = self.kb.fix_hallucinated_method(method_name)
        if was_fixed:
            errors.append(ValidationError(
                error_type="hallucination_fixed",
                message=f"Fixed '{method_name}' -> '{corrected}'",
                severity="warning"
            ))
            method_name = corrected

        # 2. Validate the method call
        source_type = self.var_tracker.get_type(call.source_variable)
        if source_type:
            is_valid, validation_errors = self.kb.validate_method_call(
                source_type, method_name
            )
            errors.extend(validation_errors)

        # 3. Build argument string
        arg_parts = []
        for param_name, param_value in call.arguments.items():
            arg_parts.append(f"{param_name}={param_value.to_code()}")

        args_str = ", ".join(arg_parts)

        # 4. Generate code line
        if call.result_variable:
            code = f"{call.result_variable} = {call.source_variable}.{method_name}({args_str})"

            # Track the result variable type
            if source_type:
                return_type = self.kb.get_factory_return_type(source_type, method_name)
                if return_type:
                    self.var_tracker.register_variable(call.result_variable, return_type)
        else:
            code = f"{call.source_variable}.{method_name}({args_str})"

        # Add comment if present
        if call.comment:
            code += f"  # {call.comment}"

        return code, errors

    def _apply_deterministic_fixes(self, code: str) -> str:
        """
        Apply all deterministic fixes to generated code.

        These fixes are applied as a final safety net to catch
        any remaining hallucinations.
        """
        # Apply all known hallucination fixes
        for wrong, correct in HALLUCINATION_FIXES.items():
            if wrong in code:
                code = code.replace(wrong, correct)

        # Fix reference patterns: new_*Ref().set_value(x) -> set_*(x)
        ref_pattern = r'\.new_(\w+)Ref\(\)\.set_value\(([^)]+)\)'
        def ref_fix(match):
            ref_type = match.group(1)
            value = match.group(2)
            setter_name = ref_type[0].lower() + ref_type[1:]
            return f'.set_{setter_name}({value})'

        code = re.sub(ref_pattern, ref_fix, code)

        # Fix save() with arguments
        code = re.sub(r'autosarfactory\.save\([^)]+\)', 'autosarfactory.save()', code)

        # Fix ByteOrder string literals
        code = re.sub(
            r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-LAST["\']\)',
            'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)',
            code
        )
        code = re.sub(
            r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-FIRST["\']\)',
            'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_FIRST)',
            code
        )

        return code

    def synthesize_from_operations(self, operations: List[Dict[str, Any]],
                                   output_file: str = "output.arxml",
                                   is_edit_mode: bool = False,
                                   source_file: str = None) -> Tuple[str, List[ValidationError]]:
        """
        Synthesize code from a list of operation dictionaries.

        This is a lower-level interface for when you have raw operations
        rather than a structured plan.

        Args:
            operations: List of operation dicts with keys:
                - source_var: Variable to call method on
                - method_name: Method to call
                - result_var: Variable to store result (optional)
                - arguments: Dict of argument name -> value
            output_file: Output ARXML file path
            is_edit_mode: Whether editing existing file
            source_file: Source file for edit mode

        Returns:
            Tuple of (generated_code, validation_errors)
        """
        errors = []
        self.var_tracker = VariableTracker(self.kb)

        lines = [IMPORTS_TEMPLATE.strip(), ""]
        body_lines = []

        # Initialization
        if is_edit_mode:
            init_code = EDIT_MODE_INIT_TEMPLATE.format(
                source_file=source_file or output_file
            )
            body_lines.extend(init_code.split('\n'))
            self.var_tracker.register_variable("autosar_root", "AUTOSAR")
        else:
            init_code = CREATE_MODE_INIT_TEMPLATE.format(output_file=output_file)
            body_lines.append(init_code.strip())
            self.var_tracker.register_variable("root_pkg", "ARPackage")

        body_lines.append("")

        # Process operations
        for i, op in enumerate(operations):
            source_var = op.get('source_var', '')
            method_name = op.get('method_name', '')
            result_var = op.get('result_var')
            arguments = op.get('arguments', {})
            comment = op.get('comment')

            # Fix hallucinations
            corrected, was_fixed = self.kb.fix_hallucinated_method(method_name)
            if was_fixed:
                errors.append(ValidationError(
                    error_type="hallucination_fixed",
                    message=f"Op {i+1}: Fixed '{method_name}' -> '{corrected}'",
                    severity="warning"
                ))
                method_name = corrected

            # Validate
            source_type = self.var_tracker.get_type(source_var)
            if source_type:
                is_valid, val_errors = self.kb.validate_method_call(source_type, method_name)
                errors.extend(val_errors)

            # Build argument string
            arg_parts = []
            for param_name, param_value in arguments.items():
                if isinstance(param_value, str):
                    if param_value.startswith('$'):
                        arg_parts.append(f"{param_name}={param_value[1:]}")
                    else:
                        arg_parts.append(f'{param_name}="{param_value}"')
                else:
                    arg_parts.append(f"{param_name}={param_value}")

            args_str = ", ".join(arg_parts)

            # Generate code
            if result_var:
                code_line = f"    {result_var} = {source_var}.{method_name}({args_str})"
                # Track result type
                if source_type:
                    return_type = self.kb.get_factory_return_type(source_type, method_name)
                    if return_type:
                        self.var_tracker.register_variable(result_var, return_type)
            else:
                code_line = f"    {source_var}.{method_name}({args_str})"

            if comment:
                code_line += f"  # {comment}"

            body_lines.append(code_line)

        # Finalization
        body_lines.append("")
        body_lines.append("    " + SAVE_TEMPLATE.strip())

        # Wrap in main
        body_text = "\n".join(body_lines)
        full_code = IMPORTS_TEMPLATE + MAIN_WRAPPER_TEMPLATE.format(body=body_text)

        # Apply final fixes
        full_code = self._apply_deterministic_fixes(full_code)

        return full_code.strip(), errors

    def validate_generated_code(self, code: str) -> List[ValidationError]:
        """
        Validate already-generated code against the knowledge base.

        This is used to check LLM-generated code before execution.
        """
        import ast as python_ast

        errors = []

        # Parse the code
        try:
            tree = python_ast.parse(code)
        except SyntaxError as e:
            return [ValidationError(
                error_type="syntax_error",
                message=str(e),
                location=f"Line {e.lineno}"
            )]

        # Find all method calls
        for node in python_ast.walk(tree):
            if isinstance(node, python_ast.Call):
                if isinstance(node.func, python_ast.Attribute):
                    method_name = node.func.attr

                    # Check if this looks like an autosarfactory method
                    if method_name.startswith(('new_', 'set_', 'get_')):
                        # Check for hallucination
                        corrected, was_fixed = self.kb.fix_hallucinated_method(method_name)
                        if was_fixed:
                            errors.append(ValidationError(
                                error_type="hallucination",
                                message=f"'{method_name}' should be '{corrected}'",
                                location=f"Line {node.lineno}" if hasattr(node, 'lineno') else None,
                                suggestion=corrected
                            ))

                        # Check if method exists anywhere
                        if not self.kb.method_exists(method_name):
                            similar = self.kb.find_similar_method(method_name)
                            suggestion = f"Did you mean: {', '.join(similar)}?" if similar else None
                            errors.append(ValidationError(
                                error_type="method_not_found",
                                message=f"Method '{method_name}' not found in API",
                                location=f"Line {node.lineno}" if hasattr(node, 'lineno') else None,
                                suggestion=suggestion
                            ))

        return errors

    def fix_generated_code(self, code: str) -> Tuple[str, List[str]]:
        """
        Apply all deterministic fixes to existing code.

        Returns:
            Tuple of (fixed_code, list_of_applied_fixes)
        """
        applied_fixes = []

        # Apply hallucination fixes
        for wrong, correct in HALLUCINATION_FIXES.items():
            if wrong in code:
                code = code.replace(wrong, correct)
                applied_fixes.append(f"{wrong} -> {correct}")

        # Fix reference patterns
        ref_pattern = r'\.new_(\w+)Ref\(\)\.set_value\(([^)]+)\)'
        matches = re.findall(ref_pattern, code)
        if matches:
            def ref_fix(match):
                ref_type = match.group(1)
                value = match.group(2)
                setter_name = ref_type[0].lower() + ref_type[1:]
                return f'.set_{setter_name}({value})'
            code = re.sub(ref_pattern, ref_fix, code)
            applied_fixes.append("Fixed reference pattern (new_*Ref -> set_*)")

        # Fix save signature
        if re.search(r'autosarfactory\.save\([^)]+\)', code):
            code = re.sub(r'autosarfactory\.save\([^)]+\)', 'autosarfactory.save()', code)
            applied_fixes.append("Fixed save() signature")

        # Fix ByteOrder
        if 'set_packingByteOrder("' in code or "set_packingByteOrder('" in code:
            code = re.sub(
                r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-LAST["\']\)',
                'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)',
                code
            )
            code = re.sub(
                r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-FIRST["\']\)',
                'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_FIRST)',
                code
            )
            applied_fixes.append("Fixed ByteOrder enum usage")

        return code, applied_fixes


# ============================================================================
# Singleton Access
# ============================================================================

_synthesizer_instance: Optional[DeterministicCodeSynthesizer] = None


def get_code_synthesizer() -> DeterministicCodeSynthesizer:
    """Get the global code synthesizer instance."""
    global _synthesizer_instance

    if _synthesizer_instance is None:
        _synthesizer_instance = DeterministicCodeSynthesizer()

    return _synthesizer_instance


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing Deterministic Code Synthesizer...")

    synthesizer = get_code_synthesizer()

    # Test simple operation synthesis
    operations = [
        {
            "source_var": "root_pkg",
            "method_name": "new_ARPackage",
            "result_var": "comm_pkg",
            "arguments": {"shortName": "Communication"}
        },
        {
            "source_var": "comm_pkg",
            "method_name": "new_CanFrame",
            "result_var": "frame",
            "arguments": {"shortName": "TestFrame"}
        },
        {
            "source_var": "frame",
            "method_name": "set_frameLength",
            "arguments": {"frameLength": 8}
        }
    ]

    code, errors = synthesizer.synthesize_from_operations(operations)

    print("\n=== Generated Code ===")
    print(code)

    print("\n=== Validation Errors ===")
    for error in errors:
        print(f"  [{error.severity}] {error.message}")

    # Test hallucination fix
    print("\n=== Testing Hallucination Fix ===")
    bad_code = '''
    behavior = swc.new_SwcInternalBehavior("beh")
    runnable = behavior.new_RunnableEntity("run")
    '''

    fixed_code, fixes = synthesizer.fix_generated_code(bad_code)
    print("Applied fixes:", fixes)
    print("Fixed code:", fixed_code)
