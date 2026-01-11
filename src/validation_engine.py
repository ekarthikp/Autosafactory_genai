"""
Validation Engine - Pre-Generation Validation and Reflexion Loop
=================================================================
Implements comprehensive validation BEFORE code execution and the
"Reflexion" pattern for automatic self-correction.

Key Features:
1. AST-based code parsing
2. Symbol table validation
3. Type chain validation
4. Semantic correctness checking
5. Automatic error correction
6. Reflexion loop with LLM feedback
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple, Callable
from enum import Enum, auto

from src.knowledge_base import (
    get_knowledge_base,
    UnifiedKnowledgeBase,
    ValidationError,
    HALLUCINATION_FIXES
)


# ============================================================================
# Validation Types
# ============================================================================

class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = auto()      # Must be fixed, will cause runtime failure
    WARNING = auto()    # Should be fixed, may cause issues
    INFO = auto()       # Informational, code will work


class ValidationCategory(Enum):
    """Categories of validation issues."""
    SYNTAX = auto()           # Python syntax errors
    SYMBOL = auto()           # Missing or wrong symbols
    TYPE = auto()             # Type mismatches
    REFERENCE = auto()        # Invalid reference patterns
    SEMANTIC = auto()         # Semantic/logic errors
    HALLUCINATION = auto()    # LLM hallucinated content
    BEST_PRACTICE = auto()    # Style/best practice issues


@dataclass
class ValidationIssue:
    """A single validation issue found in code."""
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    auto_fix: Optional[Callable[[str], str]] = None  # Function to auto-fix

    def to_dict(self) -> Dict:
        return {
            "category": self.category.name,
            "severity": self.severity.name,
            "message": self.message,
            "line": self.line_number,
            "suggestion": self.suggestion
        }


@dataclass
class ValidationResult:
    """Complete validation result for a piece of code."""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    fixed_code: Optional[str] = None
    fixes_applied: List[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)

    def get_errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    def get_feedback(self) -> str:
        """Generate feedback string for LLM reflexion."""
        lines = ["VALIDATION ISSUES FOUND:"]
        for issue in self.issues:
            severity = issue.severity.name
            line_info = f" (line {issue.line_number})" if issue.line_number else ""
            lines.append(f"  [{severity}]{line_info}: {issue.message}")
            if issue.suggestion:
                lines.append(f"    -> Suggestion: {issue.suggestion}")
        return "\n".join(lines)


# ============================================================================
# Pre-Generation Validator
# ============================================================================

class PreGenerationValidator:
    """
    Validates code BEFORE execution using static analysis.

    This implements the core of the pre-validation layer:
    1. Parse code into AST
    2. Extract all method calls
    3. Validate against symbol table
    4. Check for known hallucinations
    5. Verify reference patterns
    """

    def __init__(self, kb: UnifiedKnowledgeBase = None):
        self.kb = kb or get_knowledge_base()

    def validate(self, code: str, auto_fix: bool = True) -> ValidationResult:
        """
        Validate Python code before execution.

        Args:
            code: Python source code
            auto_fix: Whether to automatically fix issues

        Returns:
            ValidationResult with issues and optionally fixed code
        """
        issues = []
        fixed_code = code

        # 1. Syntax check
        syntax_issues = self._check_syntax(code)
        issues.extend(syntax_issues)

        if syntax_issues:
            # Can't continue with AST analysis if syntax is broken
            return ValidationResult(
                is_valid=False,
                issues=issues
            )

        # 2. Parse AST and analyze
        tree = ast.parse(code)

        # 3. Check for hallucinated methods
        hallucination_issues = self._check_hallucinations(tree, code)
        issues.extend(hallucination_issues)

        # 4. Check for invalid reference patterns
        reference_issues = self._check_reference_patterns(code)
        issues.extend(reference_issues)

        # 5. Check method existence
        method_issues = self._check_method_calls(tree)
        issues.extend(method_issues)

        # 6. Check for common mistakes
        common_issues = self._check_common_mistakes(code)
        issues.extend(common_issues)

        # Auto-fix if enabled
        fixes_applied = []
        if auto_fix:
            fixed_code, fixes_applied = self._apply_auto_fixes(code, issues)

            # Re-validate fixed code if fixes were applied
            if fixes_applied:
                revalidation = self.validate(fixed_code, auto_fix=False)
                # Only keep issues that weren't fixed
                remaining_issues = revalidation.issues
            else:
                remaining_issues = issues
        else:
            remaining_issues = issues

        is_valid = all(i.severity != ValidationSeverity.ERROR for i in remaining_issues)

        return ValidationResult(
            is_valid=is_valid,
            issues=remaining_issues,
            fixed_code=fixed_code if fixes_applied else None,
            fixes_applied=fixes_applied
        )

    def _check_syntax(self, code: str) -> List[ValidationIssue]:
        """Check for Python syntax errors."""
        try:
            ast.parse(code)
            return []
        except SyntaxError as e:
            return [ValidationIssue(
                category=ValidationCategory.SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=str(e.msg),
                line_number=e.lineno,
                column=e.offset,
                code_snippet=e.text
            )]

    def _check_hallucinations(self, tree: ast.AST, code: str) -> List[ValidationIssue]:
        """Check for known LLM hallucinations."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr

                    if method_name in HALLUCINATION_FIXES:
                        correct = HALLUCINATION_FIXES[method_name]
                        issues.append(ValidationIssue(
                            category=ValidationCategory.HALLUCINATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"'{method_name}' is a hallucinated method name",
                            line_number=node.lineno if hasattr(node, 'lineno') else None,
                            suggestion=f"Use '{correct}' instead",
                            auto_fix=lambda c, old=method_name, new=correct: c.replace(old, new)
                        ))

        return issues

    def _check_reference_patterns(self, code: str) -> List[ValidationIssue]:
        """Check for incorrect reference patterns."""
        issues = []

        # Pattern: new_*Ref().set_value(x) - this is wrong
        pattern = r'\.new_(\w+)Ref\(\)\.set_value\('
        for match in re.finditer(pattern, code):
            ref_type = match.group(1)
            line_num = code[:match.start()].count('\n') + 1

            issues.append(ValidationIssue(
                category=ValidationCategory.REFERENCE,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid reference pattern: new_{ref_type}Ref().set_value()",
                line_number=line_num,
                suggestion=f"Use direct setter: set_{ref_type[0].lower() + ref_type[1:]}(value)"
            ))

        return issues

    def _check_method_calls(self, tree: ast.AST) -> List[ValidationIssue]:
        """Check that all method calls exist in the API."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    method_name = node.func.attr

                    # Skip non-autosarfactory methods
                    if not method_name.startswith(('new_', 'set_', 'get_')):
                        continue

                    # Skip if already flagged as hallucination
                    if method_name in HALLUCINATION_FIXES:
                        continue

                    # Check if method exists anywhere
                    if not self.kb.method_exists(method_name):
                        similar = self.kb.find_similar_method(method_name)
                        suggestion = f"Did you mean: {', '.join(similar)}?" if similar else None

                        issues.append(ValidationIssue(
                            category=ValidationCategory.SYMBOL,
                            severity=ValidationSeverity.ERROR,
                            message=f"Method '{method_name}' not found in API",
                            line_number=node.lineno if hasattr(node, 'lineno') else None,
                            suggestion=suggestion
                        ))

        return issues

    def _check_common_mistakes(self, code: str) -> List[ValidationIssue]:
        """Check for common coding mistakes."""
        issues = []

        # Check for save() with arguments
        if re.search(r'autosarfactory\.save\([^)]+\)', code):
            issues.append(ValidationIssue(
                category=ValidationCategory.SEMANTIC,
                severity=ValidationSeverity.ERROR,
                message="save() should not have arguments",
                suggestion="Use autosarfactory.save() without arguments"
            ))

        # Check for string byte order instead of enum
        if re.search(r'set_packingByteOrder\(["\']', code):
            issues.append(ValidationIssue(
                category=ValidationCategory.TYPE,
                severity=ValidationSeverity.ERROR,
                message="ByteOrder should use enum, not string",
                suggestion="Use autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST"
            ))

        # Check for read() without list
        if re.search(r'autosarfactory\.read\([^[\]]+\)', code):
            # Make sure it's not already a list
            match = re.search(r'autosarfactory\.read\(([^)]+)\)', code)
            if match and not match.group(1).strip().startswith('['):
                issues.append(ValidationIssue(
                    category=ValidationCategory.SEMANTIC,
                    severity=ValidationSeverity.ERROR,
                    message="read() requires a list argument",
                    suggestion='Use autosarfactory.read(["file.arxml"])'
                ))

        return issues

    def _apply_auto_fixes(self, code: str, issues: List[ValidationIssue]) -> Tuple[str, List[str]]:
        """Apply automatic fixes for issues that have auto_fix functions."""
        fixes_applied = []
        fixed_code = code

        # Apply hallucination fixes
        for wrong, correct in HALLUCINATION_FIXES.items():
            if wrong in fixed_code:
                fixed_code = fixed_code.replace(wrong, correct)
                fixes_applied.append(f"{wrong} -> {correct}")

        # Fix reference patterns
        ref_pattern = r'\.new_(\w+)Ref\(\)\.set_value\(([^)]+)\)'
        matches = list(re.finditer(ref_pattern, fixed_code))
        if matches:
            def ref_fix(match):
                ref_type = match.group(1)
                value = match.group(2)
                setter_name = ref_type[0].lower() + ref_type[1:]
                return f'.set_{setter_name}({value})'

            fixed_code = re.sub(ref_pattern, ref_fix, fixed_code)
            fixes_applied.append("Fixed reference patterns")

        # Fix save() signature
        if re.search(r'autosarfactory\.save\([^)]+\)', fixed_code):
            fixed_code = re.sub(r'autosarfactory\.save\([^)]+\)', 'autosarfactory.save()', fixed_code)
            fixes_applied.append("Fixed save() signature")

        # Fix ByteOrder strings
        if 'set_packingByteOrder("' in fixed_code or "set_packingByteOrder('" in fixed_code:
            fixed_code = re.sub(
                r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-LAST["\']\)',
                'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)',
                fixed_code
            )
            fixed_code = re.sub(
                r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-FIRST["\']\)',
                'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_FIRST)',
                fixed_code
            )
            fixes_applied.append("Fixed ByteOrder enum")

        return fixed_code, fixes_applied


# ============================================================================
# Reflexion Loop
# ============================================================================

class ReflexionLoop:
    """
    Implements the Reflexion pattern for code generation.

    The loop:
    1. Generate code with LLM
    2. Validate statically
    3. If issues found, generate feedback
    4. Ask LLM to fix based on feedback
    5. Repeat until valid or max iterations
    """

    def __init__(self,
                 validator: PreGenerationValidator = None,
                 max_iterations: int = 3,
                 llm_model = None):
        self.validator = validator or PreGenerationValidator()
        self.max_iterations = max_iterations
        self.llm_model = llm_model  # Injected LLM for reflexion
        self.history: List[Dict] = []

    def run(self, initial_code: str,
            context: str = "",
            on_iteration: Callable[[int, str, ValidationResult], None] = None) -> Tuple[str, ValidationResult]:
        """
        Run the reflexion loop to fix code.

        Args:
            initial_code: The initially generated code
            context: Additional context for the LLM
            on_iteration: Callback for each iteration (for progress reporting)

        Returns:
            Tuple of (final_code, final_validation_result)
        """
        current_code = initial_code
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # Validate
            result = self.validator.validate(current_code, auto_fix=True)

            # Record history
            self.history.append({
                "iteration": iteration,
                "error_count": result.error_count,
                "fixes_applied": result.fixes_applied
            })

            # Callback
            if on_iteration:
                on_iteration(iteration, current_code, result)

            # If valid, we're done
            if result.is_valid:
                if result.fixed_code:
                    return result.fixed_code, result
                return current_code, result

            # If we have auto-fixed code, use it
            if result.fixed_code:
                current_code = result.fixed_code

                # Revalidate the fixed code
                recheck = self.validator.validate(current_code, auto_fix=False)
                if recheck.is_valid:
                    return current_code, recheck

            # If still invalid and we have an LLM, ask for reflexion
            if self.llm_model and result.error_count > 0:
                feedback = result.get_feedback()
                current_code = self._llm_reflexion(current_code, feedback, context)

        # Final validation
        final_result = self.validator.validate(current_code, auto_fix=True)
        if final_result.fixed_code:
            return final_result.fixed_code, final_result

        return current_code, final_result

    def _llm_reflexion(self, code: str, feedback: str, context: str) -> str:
        """Ask LLM to fix code based on feedback."""
        if not self.llm_model:
            return code

        prompt = f"""
You are fixing Python code that uses the autosarfactory library.

ORIGINAL CODE:
```python
{code}
```

{feedback}

{context}

CRITICAL RULES:
1. Use new_InternalBehavior() NOT new_SwcInternalBehavior()
2. Use new_Runnable() NOT new_RunnableEntity()
3. Use new_DataReadAcces() / new_DataWriteAcces() (ONE 's'!)
4. Use direct setters (set_frame, set_pdu) NOT new_*Ref().set_value()
5. Use autosarfactory.save() without arguments
6. Use ByteOrderEnum, not string literals

Return ONLY the fixed Python code:
"""

        try:
            response = self.llm_model.generate_content(prompt)
            fixed = response.text

            # Extract code from markdown if present
            if "```python" in fixed:
                fixed = fixed.split("```python")[1].split("```")[0]
            elif "```" in fixed:
                fixed = fixed.split("```")[1].split("```")[0]

            return fixed.strip()

        except Exception as e:
            print(f"Warning: LLM reflexion failed: {e}")
            return code


# ============================================================================
# Integrated Validation Pipeline
# ============================================================================

class ValidationPipeline:
    """
    Complete validation pipeline that combines all validation components.

    Stages:
    1. Pre-generation: Validate the structured plan
    2. Code validation: Validate generated code
    3. Reflexion: Fix issues automatically
    4. Post-validation: Final check before execution
    """

    def __init__(self, kb: UnifiedKnowledgeBase = None, llm_model = None):
        self.kb = kb or get_knowledge_base()
        self.pre_validator = PreGenerationValidator(self.kb)
        self.reflexion_loop = ReflexionLoop(
            validator=self.pre_validator,
            llm_model=llm_model
        )

    def validate_plan(self, operations: List[Dict[str, Any]]) -> List[ValidationIssue]:
        """Validate a code generation plan before synthesis."""
        issues = []

        for i, op in enumerate(operations):
            source_class = op.get('source_class', '')
            method_name = op.get('method_name', '')

            # Check class exists
            if source_class and not self.kb.class_exists(source_class):
                issues.append(ValidationIssue(
                    category=ValidationCategory.SYMBOL,
                    severity=ValidationSeverity.ERROR,
                    message=f"Op {i+1}: Class '{source_class}' not found"
                ))
                continue

            # Check for hallucination
            if method_name in HALLUCINATION_FIXES:
                issues.append(ValidationIssue(
                    category=ValidationCategory.HALLUCINATION,
                    severity=ValidationSeverity.WARNING,
                    message=f"Op {i+1}: '{method_name}' will be auto-corrected to '{HALLUCINATION_FIXES[method_name]}'"
                ))

            # Check method exists
            if source_class and method_name:
                if not self.kb.method_exists(method_name, source_class):
                    # Check if it exists anywhere
                    if not self.kb.method_exists(method_name):
                        similar = self.kb.find_similar_method(method_name, source_class)
                        suggestion = f"Did you mean: {', '.join(similar)}?" if similar else None
                        issues.append(ValidationIssue(
                            category=ValidationCategory.SYMBOL,
                            severity=ValidationSeverity.ERROR,
                            message=f"Op {i+1}: Method '{method_name}' not found on '{source_class}'",
                            suggestion=suggestion
                        ))

        return issues

    def validate_and_fix_code(self, code: str,
                              context: str = "",
                              use_reflexion: bool = True) -> Tuple[str, ValidationResult]:
        """
        Complete validation and fixing of generated code.

        Args:
            code: Generated Python code
            context: Additional context for LLM fixing
            use_reflexion: Whether to use LLM-based reflexion

        Returns:
            Tuple of (fixed_code, validation_result)
        """
        if use_reflexion and self.reflexion_loop.llm_model:
            return self.reflexion_loop.run(code, context)
        else:
            result = self.pre_validator.validate(code, auto_fix=True)
            final_code = result.fixed_code if result.fixed_code else code
            return final_code, result

    def quick_fix(self, code: str) -> Tuple[str, List[str]]:
        """
        Apply quick deterministic fixes without full validation.

        Returns:
            Tuple of (fixed_code, list_of_fixes_applied)
        """
        fixes = []

        # Hallucination fixes
        for wrong, correct in HALLUCINATION_FIXES.items():
            if wrong in code:
                code = code.replace(wrong, correct)
                fixes.append(f"{wrong} -> {correct}")

        # Reference pattern fixes
        ref_pattern = r'\.new_(\w+)Ref\(\)\.set_value\(([^)]+)\)'
        if re.search(ref_pattern, code):
            def ref_fix(match):
                ref_type = match.group(1)
                value = match.group(2)
                setter_name = ref_type[0].lower() + ref_type[1:]
                return f'.set_{setter_name}({value})'
            code = re.sub(ref_pattern, ref_fix, code)
            fixes.append("Reference patterns fixed")

        # Save signature fix
        if re.search(r'autosarfactory\.save\([^)]+\)', code):
            code = re.sub(r'autosarfactory\.save\([^)]+\)', 'autosarfactory.save()', code)
            fixes.append("save() signature fixed")

        # ByteOrder fixes
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
            fixes.append("ByteOrder enum fixed")

        return code, fixes


# ============================================================================
# Singleton Access
# ============================================================================

_validator_instance: Optional[PreGenerationValidator] = None
_pipeline_instance: Optional[ValidationPipeline] = None


def get_pre_validator() -> PreGenerationValidator:
    """Get the global pre-generation validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = PreGenerationValidator()
    return _validator_instance


def get_validation_pipeline(llm_model = None) -> ValidationPipeline:
    """Get the global validation pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = ValidationPipeline(llm_model=llm_model)
    return _pipeline_instance


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing Validation Engine...")

    validator = get_pre_validator()

    # Test with hallucinated code
    bad_code = '''
import autosarfactory.autosarfactory as autosarfactory

def main():
    root = autosarfactory.new_file("test.arxml", defaultArPackage="Root", overWrite=True)
    pkg = root.new_ARPackage("Swc")

    swc = pkg.new_ApplicationSwComponentType("MySwc")
    behavior = swc.new_SwcInternalBehavior("beh")  # WRONG!
    runnable = behavior.new_RunnableEntity("run")   # WRONG!

    # Wrong reference pattern
    ref = frame_trig.new_FrameRef().set_value(frame)

    # Wrong save
    autosarfactory.save(root, "test.arxml")

if __name__ == "__main__":
    main()
'''

    print("\n=== Validating Bad Code ===")
    result = validator.validate(bad_code)

    print(f"Valid: {result.is_valid}")
    print(f"Error count: {result.error_count}")
    print(f"Warning count: {result.warning_count}")

    print("\n=== Issues Found ===")
    for issue in result.issues:
        print(f"  [{issue.severity.name}] {issue.message}")
        if issue.suggestion:
            print(f"    -> {issue.suggestion}")

    if result.fixed_code:
        print("\n=== Fixed Code ===")
        print(result.fixed_code[:500] + "...")

    print(f"\n=== Fixes Applied ===")
    for fix in result.fixes_applied:
        print(f"  - {fix}")
