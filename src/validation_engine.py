"""
Validation Engine - Pre-Generation Validation and Reflexion Loop
=================================================================
Uses api_fixes.py as single source of truth for all corrections.
Uses api_index.py for method existence validation.

Based on: https://github.com/girishchandranc/autosarfactory
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple, Callable
from enum import Enum, auto

from src.api_fixes import HALLUCINATION_FIXES, apply_all_fixes


class ValidationSeverity(Enum):
    ERROR = auto()
    WARNING = auto()
    INFO = auto()


class ValidationCategory(Enum):
    SYNTAX = auto()
    SYMBOL = auto()
    TYPE = auto()
    REFERENCE = auto()
    SEMANTIC = auto()
    HALLUCINATION = auto()
    BEST_PRACTICE = auto()


@dataclass
class ValidationIssue:
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    auto_fix: Optional[Callable[[str], str]] = None

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
        lines = ["VALIDATION ISSUES FOUND:"]
        for issue in self.issues:
            severity = issue.severity.name
            line_info = f" (line {issue.line_number})" if issue.line_number else ""
            lines.append(f"  [{severity}]{line_info}: {issue.message}")
            if issue.suggestion:
                lines.append(f"    -> Suggestion: {issue.suggestion}")
        return "\n".join(lines)


class PreGenerationValidator:
    """Validates code BEFORE execution using static analysis + api_fixes."""

    def __init__(self, kb=None):
        self.kb = kb
        self._api_index = None

    def _get_index(self):
        if self._api_index is None:
            try:
                from src.api_index import get_api_index
                self._api_index = get_api_index()
            except Exception:
                pass
        return self._api_index

    def validate(self, code: str, auto_fix: bool = True) -> ValidationResult:
        issues = []

        # 1. Syntax check
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            issues.append(ValidationIssue(
                category=ValidationCategory.SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=str(e.msg),
                line_number=e.lineno
            ))
            return ValidationResult(is_valid=False, issues=issues)

        # 2. Check hallucinations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method = node.func.attr
                if method in HALLUCINATION_FIXES:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.HALLUCINATION,
                        severity=ValidationSeverity.ERROR,
                        message=f"'{method}' is hallucinated",
                        line_number=getattr(node, 'lineno', None),
                        suggestion=f"Use '{HALLUCINATION_FIXES[method]}'"
                    ))

        # 3. Check reference patterns
        for match in re.finditer(r'\.new_(\w+)Ref\(\)\.set_value\(', code):
            line_num = code[:match.start()].count('\n') + 1
            issues.append(ValidationIssue(
                category=ValidationCategory.REFERENCE,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid ref pattern: new_{match.group(1)}Ref().set_value()",
                line_number=line_num,
                suggestion=f"Use set_{match.group(1)[0].lower() + match.group(1)[1:]}(value)"
            ))

        # 4. Check common mistakes
        if re.search(r'autosarfactory\.save\([^)]+\)', code):
            issues.append(ValidationIssue(
                category=ValidationCategory.SEMANTIC,
                severity=ValidationSeverity.ERROR,
                message="save() takes no arguments"
            ))

        if re.search(r'set_packingByteOrder\(["\']', code):
            issues.append(ValidationIssue(
                category=ValidationCategory.TYPE,
                severity=ValidationSeverity.ERROR,
                message="ByteOrder needs enum, not string"
            ))

        # 5. Check method existence via API index
        idx = self._get_index()
        if idx:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    method = node.func.attr
                    if method.startswith(('new_', 'set_', 'get_')) and method not in HALLUCINATION_FIXES:
                        if not idx.method_exists(method):
                            similar = idx.find_similar_method(method)
                            issues.append(ValidationIssue(
                                category=ValidationCategory.SYMBOL,
                                severity=ValidationSeverity.ERROR,
                                message=f"'{method}' not found in API",
                                line_number=getattr(node, 'lineno', None),
                                suggestion=f"Did you mean: {', '.join(similar)}?" if similar else None
                            ))

        # Auto-fix
        fixes_applied = []
        fixed_code = None
        if auto_fix and issues:
            fixed_code, fixes_applied = apply_all_fixes(code)
            if fixed_code == code:
                fixed_code = None
                fixes_applied = []

        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        is_valid = not has_errors or bool(fixes_applied)

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            fixed_code=fixed_code,
            fixes_applied=fixes_applied
        )


class ValidationPipeline:
    """Complete validation pipeline combining all components."""

    def __init__(self, kb=None, llm_model=None):
        self.pre_validator = PreGenerationValidator(kb)
        self.llm_model = llm_model

    def validate_and_fix_code(self, code: str, context: str = "",
                              use_reflexion: bool = True) -> Tuple[str, ValidationResult]:
        result = self.pre_validator.validate(code, auto_fix=True)
        final_code = result.fixed_code if result.fixed_code else code
        return final_code, result

    def quick_fix(self, code: str) -> Tuple[str, List[str]]:
        return apply_all_fixes(code)


_validator_instance: Optional[PreGenerationValidator] = None
_pipeline_instance: Optional[ValidationPipeline] = None


def get_pre_validator() -> PreGenerationValidator:
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = PreGenerationValidator()
    return _validator_instance


def get_validation_pipeline(llm_model=None) -> ValidationPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = ValidationPipeline(llm_model=llm_model)
    return _pipeline_instance
