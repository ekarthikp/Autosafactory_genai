"""
Constrained Generator - Near-Deterministic Code Generation
===========================================================
Forces the LLM to select from valid API methods only using structured
outputs and Pydantic models. Integrates with Gemini 2.5 Pro.

Features:
- Dynamic enum generation from valid method lists
- Pydantic models for structured code generation
- Signature validation before code execution
- Integration with Gemini's structured output API
"""

import json
from typing import Dict, List, Optional, Any, Literal, Tuple
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field, validator

from src.ast_indexer import get_symbol_table, SymbolTable, MethodSignature, Parameter
from src.code_graph import get_code_graph, CodeKnowledgeGraph


# ============================================================================
# Pydantic Models for Structured Code Generation
# ============================================================================

class APICall(BaseModel):
    """Represents a single API call in the generated code."""
    target_variable: str = Field(description="Variable name to assign the result to")
    source_object: str = Field(description="Object/variable to call the method on")
    method_name: str = Field(description="Method to call (must be from valid methods list)")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass")
    comment: Optional[str] = Field(default=None, description="Optional inline comment")


class CodeStep(BaseModel):
    """A step in the code generation plan."""
    step_number: int = Field(description="Order of execution")
    description: str = Field(description="What this step accomplishes")
    action_type: Literal["create", "configure", "reference", "retrieve", "save"] = Field(
        description="Type of action"
    )
    api_calls: List[APICall] = Field(description="API calls for this step")


class GeneratedCodePlan(BaseModel):
    """Complete structured code generation plan."""
    imports: List[str] = Field(
        default=["import autosarfactory.autosarfactory as autosarfactory"],
        description="Required imports"
    )
    initialization: str = Field(
        description="Code for file initialization (new_file or read)"
    )
    steps: List[CodeStep] = Field(description="Ordered steps to execute")
    finalization: str = Field(
        default="autosarfactory.save()",
        description="Code to save/finalize"
    )
    
    def to_python_code(self) -> str:
        """Convert the plan to executable Python code."""
        lines = []
        
        # Imports
        for imp in self.imports:
            lines.append(imp)
        lines.append("")
        
        # Main function
        lines.append("def main():")
        lines.append(f"    # Initialization")
        lines.append(f"    {self.initialization}")
        lines.append("")
        
        # Steps
        for step in self.steps:
            lines.append(f"    # Step {step.step_number}: {step.description}")
            for call in step.api_calls:
                args_str = ", ".join(
                    f"{k}={repr(v)}" if not isinstance(v, str) or not v.startswith("$") 
                    else f"{k}={v[1:]}"  # Remove $ prefix for variable references
                    for k, v in call.arguments.items()
                )
                code_line = f"    {call.target_variable} = {call.source_object}.{call.method_name}({args_str})"
                if call.comment:
                    code_line += f"  # {call.comment}"
                lines.append(code_line)
            lines.append("")
        
        # Finalization
        lines.append(f"    # Save")
        lines.append(f"    {self.finalization}")
        lines.append("    print('ARXML file generated successfully!')")
        lines.append("")
        
        # Main block with error handling
        lines.append('if __name__ == "__main__":')
        lines.append("    try:")
        lines.append("        main()")
        lines.append("    except Exception as e:")
        lines.append("        import traceback")
        lines.append('        with open("execution_error.log", "w") as f:')
        lines.append("            f.write(traceback.format_exc())")
        lines.append('        print("Execution failed. See execution_error.log for details.")')
        lines.append("        raise e")
        
        return "\n".join(lines)


class MethodSelection(BaseModel):
    """Result of method selection with validation."""
    class_name: str = Field(description="Class the method belongs to")
    method_name: str = Field(description="Selected method name")
    reason: str = Field(description="Why this method was selected")
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Result of signature validation."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


# ============================================================================
# Constrained Generator
# ============================================================================

class ConstrainedGenerator:
    """
    Generates code with constraints that prevent API hallucination.
    Uses the symbol table and code graph to enforce valid method selection.
    """
    
    def __init__(self, symbol_table: SymbolTable = None, 
                 graph: CodeKnowledgeGraph = None):
        """
        Initialize the constrained generator.
        
        Args:
            symbol_table: Pre-built symbol table, or None to load
            graph: Pre-built code graph, or None to load
        """
        self.symbols = symbol_table or get_symbol_table()
        self.graph = graph or get_code_graph()
    
    def build_method_constraints(self, class_names: List[str]) -> Dict[str, List[str]]:
        """
        Build constraints mapping class names to valid methods.
        
        Args:
            class_names: List of classes to include
            
        Returns:
            Dict mapping class name to list of valid method names
        """
        constraints = {}
        
        for class_name in class_names:
            if class_name in self.symbols.classes:
                # Get all methods including inherited
                methods = self.graph.get_valid_methods_for_class(class_name)
                constraints[class_name] = sorted(methods)
        
        # Add module-level functions
        constraints["_module"] = list(self.symbols.module_functions.keys())
        
        return constraints
    
    def validate_method_call(self, class_name: str, method_name: str, 
                             arguments: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate a method call against the symbol table.
        
        Args:
            class_name: Class to call method on
            method_name: Method to call
            arguments: Arguments to pass
            
        Returns:
            ValidationResult with errors and suggestions
        """
        errors = []
        suggestions = []
        
        # Check if method exists
        valid, msg = self.graph.validate_method_call(class_name, method_name)
        if not valid:
            errors.append(msg)
            
            # Find similar methods
            similar = self.symbols.find_similar_method(method_name)
            if similar:
                suggestions.append(f"Did you mean one of: {', '.join(similar)}?")
            
            return ValidationResult(is_valid=False, errors=errors, suggestions=suggestions)
        
        # Validate arguments against signature
        if arguments:
            signature = self.symbols.get_signature(method_name, class_name)
            if signature:
                arg_errors = self._validate_arguments(signature, arguments)
                errors.extend(arg_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            suggestions=suggestions
        )
    
    def _validate_arguments(self, signature: MethodSignature, 
                           arguments: Dict[str, Any]) -> List[str]:
        """Validate arguments against a method signature."""
        errors = []
        
        # Check required parameters
        required_params = {p.name for p in signature.parameters if p.is_required}
        provided_params = set(arguments.keys())
        
        missing = required_params - provided_params
        if missing:
            errors.append(f"Missing required arguments: {', '.join(missing)}")
        
        # Check for unknown parameters
        valid_params = {p.name for p in signature.parameters}
        unknown = provided_params - valid_params
        if unknown:
            errors.append(f"Unknown arguments: {', '.join(unknown)}")
        
        return errors
    
    def generate_constraint_prompt(self, class_names: List[str]) -> str:
        """
        Generate a prompt section that lists valid methods for each class.
        This is injected into the LLM prompt to constrain generation.
        
        Args:
            class_names: Classes to include in constraints
            
        Returns:
            Formatted constraint text for the prompt
        """
        constraints = self.build_method_constraints(class_names)
        
        lines = [
            "=== VALID API METHODS (USE ONLY THESE) ===",
            "You MUST use ONLY the methods listed below. Any other method will fail.",
            ""
        ]
        
        for class_name, methods in sorted(constraints.items()):
            if class_name == "_module":
                lines.append("Module-level functions:")
            else:
                lines.append(f"\n{class_name}:")
            
            # Group by type
            factories = [m for m in methods if m.startswith("new_")]
            setters = [m for m in methods if m.startswith("set_")]
            getters = [m for m in methods if m.startswith("get_")]
            other = [m for m in methods if not any(m.startswith(p) for p in ["new_", "set_", "get_"])]
            
            if factories:
                lines.append(f"  Factory methods: {', '.join(factories[:15])}")
                if len(factories) > 15:
                    lines.append(f"    ... and {len(factories)-15} more")
            if setters:
                lines.append(f"  Setters: {', '.join(setters[:15])}")
                if len(setters) > 15:
                    lines.append(f"    ... and {len(setters)-15} more")
            if getters and len(getters) <= 10:
                lines.append(f"  Getters: {', '.join(getters)}")
        
        lines.append("\n" + "=" * 50)
        
        return "\n".join(lines)
    
    def get_factory_chain(self, target_class: str) -> List[Tuple[str, str, str]]:
        """
        Get the chain of factory methods needed to create a target class.
        
        Args:
            target_class: The class we want to create
            
        Returns:
            List of (source_class, factory_method, result_class) tuples
        """
        chain = []
        
        # Use BFS to find factory paths
        # Start from root creators (module functions like new_file)
        visited = set()
        queue = [(None, func_name, None) for func_name in self.symbols.module_functions 
                 if func_name.startswith("new_")]
        
        while queue and len(chain) < 10:  # Limit depth
            source, method, created = queue.pop(0)
            
            if created == target_class:
                chain.append((source, method, created))
                break
            
            if created and created not in visited:
                visited.add(created)
                
                # Get factory methods of this class
                if created in self.symbols.classes:
                    factories = self.graph.get_factory_methods(created)
                    for factory_name, return_type in factories:
                        if return_type and return_type not in visited:
                            queue.append((created, factory_name, return_type))
        
        return chain
    
    def check_instantiability(self, class_name: str) -> Tuple[bool, str]:
        """
        Check if a class can be instantiated directly.
        
        Returns:
            Tuple of (can_instantiate, reason)
        """
        if class_name not in self.symbols.classes:
            return False, f"Class '{class_name}' not found"
        
        class_info = self.symbols.classes[class_name]
        
        if class_info.is_abstract:
            return False, f"'{class_name}' is abstract and cannot be instantiated directly"
        
        if not class_info.can_instantiate:
            return False, f"'{class_name}' cannot be instantiated (check factory methods)"
        
        return True, "OK"
    
    def get_creation_pattern(self, target_class: str) -> Optional[str]:
        """
        Get a code pattern for creating an instance of the target class.
        
        Args:
            target_class: Class to create
            
        Returns:
            Code snippet showing how to create this class, or None
        """
        # Check if it's directly instantiable
        can_inst, reason = self.check_instantiability(target_class)
        if can_inst:
            return f"# {target_class} can be instantiated directly\nobj = {target_class}()"
        
        # Find factory methods that create this class
        creating_classes = []
        for class_name, class_info in self.symbols.classes.items():
            for factory in class_info.factory_methods:
                # Check return type (rough match)
                if factory.return_type and target_class.lower() in factory.return_type.lower():
                    creating_classes.append((class_name, factory.name))
        
        if creating_classes:
            examples = [f"# From {cls}: {method}()" for cls, method in creating_classes[:3]]
            return f"# {target_class} is created via factory methods:\n" + "\n".join(examples)
        
        return None


# ============================================================================
# Integration with Gemini 2.5 Pro
# ============================================================================

def create_structured_generation_prompt(
    task_description: str,
    class_names: List[str],
    output_file: str = "output.arxml",
    is_edit_mode: bool = False,
    source_file: str = None
) -> Tuple[str, Dict[str, List[str]]]:
    """
    Create a prompt with structured constraints for Gemini.
    
    Args:
        task_description: What to generate
        class_names: Classes involved in the task
        output_file: Output ARXML file path
        is_edit_mode: Whether editing existing file
        source_file: Source file for edit mode
        
    Returns:
        Tuple of (prompt_text, constraints_dict)
    """
    generator = ConstrainedGenerator()
    
    # Build constraints
    constraints = generator.build_method_constraints(class_names)
    constraint_prompt = generator.generate_constraint_prompt(class_names)
    
    # Build initialization instruction
    if is_edit_mode:
        init_instruction = f"""
OPERATION MODE: EDIT EXISTING FILE
Source: {source_file}
Output: {output_file}

Use: autosar_root, status = autosarfactory.read(["{source_file}"])
"""
    else:
        init_instruction = f"""
OPERATION MODE: CREATE NEW FILE
Output: {output_file}

Use: root_pkg = autosarfactory.new_file("{output_file}", defaultArPackage="Root", overWrite=True)
"""
    
    prompt = f"""
You are an AUTOSAR code generation system. Generate ONLY valid Python code.

TASK: {task_description}

{init_instruction}

{constraint_prompt}

CRITICAL RULES:
1. Use ONLY methods from the VALID API METHODS section above
2. Use direct setters (set_frame, set_pdu) NOT new_*Ref().set_value() patterns
3. Create objects via factory methods (new_*), not direct instantiation
4. End with autosarfactory.save()

Generate a complete Python script:
"""
    
    return prompt, constraints


# Singleton for easy access
_generator_instance: Optional[ConstrainedGenerator] = None


def get_constrained_generator() -> ConstrainedGenerator:
    """Get or create the singleton ConstrainedGenerator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ConstrainedGenerator()
    return _generator_instance


if __name__ == "__main__":
    # Test the constrained generator
    print("Testing Constrained Generator...")
    
    gen = get_constrained_generator()
    
    # Test constraint building
    print("\n=== Constraints for CAN classes ===")
    constraints = gen.build_method_constraints(["CanCluster", "CanFrame", "CanPhysicalChannel"])
    for cls, methods in constraints.items():
        print(f"{cls}: {len(methods)} methods")
    
    # Test validation
    print("\n=== Validation Tests ===")
    result = gen.validate_method_call("CanCluster", "new_CanClusterVariant")
    print(f"CanCluster.new_CanClusterVariant: valid={result.is_valid}")
    
    result = gen.validate_method_call("CanCluster", "new_FakeMethod")
    print(f"CanCluster.new_FakeMethod: valid={result.is_valid}, errors={result.errors}")
    
    # Test constraint prompt generation
    print("\n=== Constraint Prompt (excerpt) ===")
    prompt = gen.generate_constraint_prompt(["CanCluster", "CanFrame"])
    print(prompt[:500] + "...")
    
    # Test instantiability check
    print("\n=== Instantiability Checks ===")
    for cls in ["CanCluster", "ARPackage"]:
        can, reason = gen.check_instantiability(cls)
        print(f"{cls}: can_instantiate={can} ({reason})")
