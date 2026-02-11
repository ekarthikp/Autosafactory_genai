"""
Code Fixer - Tiered error correction for autosarfactory code.
==============================================================
Tier 1: Deterministic fixes from api_fixes (no LLM)
Tier 2: Pattern-based regex fixes (no LLM)
Tier 3: LLM-based fix (fallback)

Uses the consolidated api_fixes module as single source of truth.
"""

import re
from typing import Tuple, List, Dict, Optional
from src.utils import get_llm_model
from src.api_fixes import (
    HALLUCINATION_FIXES, COMPACT_API_RULES,
    apply_all_fixes, apply_hallucination_fixes, apply_pattern_fixes
)


class Fixer:
    def __init__(self, max_attempts=5, enable_deep_analysis=False):
        self.model = get_llm_model()
        self.previous_errors = []
        self.fix_attempts = 0
        self.max_attempts = max_attempts

    def fix_code(self, code, error_log, plan):
        """
        Fix code using tiered strategy: deterministic -> pattern -> LLM.
        """
        self.fix_attempts += 1

        if self.fix_attempts > self.max_attempts:
            print(f"   Max fix attempts ({self.max_attempts}) reached.")
            return code

        # Extract error text
        if isinstance(error_log, dict):
            error_text = error_log.get('traceback', '') + ' ' + error_log.get('message', '')
            error_msg = error_log.get('message', '')
        else:
            error_text = str(error_log)
            error_msg = str(error_log)

        # === TIER 1: Deterministic fixes (NO LLM) ===
        print(f"   Tier 1: Deterministic fixes...")
        fixed, fixes = apply_all_fixes(code)
        if fixed != code:
            print(f"   Tier 1 applied {len(fixes)} fixes")
            return fixed

        # === TIER 2: Error-specific deterministic fixes ===
        print(f"   Tier 2: Error-specific fixes...")
        fixed = self._fix_from_error(code, error_msg)
        if fixed != code:
            print(f"   Tier 2 fix applied!")
            return fixed

        # === TIER 3: LLM fix (fallback) ===
        print(f"   Tier 3: LLM fix (attempt {self.fix_attempts})...")
        return self._llm_fix(code, error_text, plan)

    def _fix_from_error(self, code: str, error_msg: str) -> str:
        """Apply targeted fix based on error message."""
        # AttributeError: 'X' has no attribute 'Y'
        attr_match = re.search(r"has no attribute '(\w+)'", error_msg)
        if attr_match:
            bad_method = attr_match.group(1)
            if bad_method in HALLUCINATION_FIXES:
                return code.replace(bad_method, HALLUCINATION_FIXES[bad_method])

            # Try to find similar method via API index
            try:
                from src.api_index import get_api_index
                idx = get_api_index()
                similar = idx.find_similar_method(bad_method)
                if similar:
                    print(f"      Suggesting: {bad_method} -> {similar[0]}")
                    return code.replace(bad_method, similar[0])
            except Exception:
                pass

        # TypeError: argument must be a list
        if "must be a list" in error_msg and "read" in error_msg:
            code = re.sub(
                r'autosarfactory\.read\(([^)\[\]]+)\)',
                lambda m: f'autosarfactory.read([{m.group(1).strip()}])',
                code
            )
            return code

        return code

    def _llm_fix(self, code: str, error_text: str, plan: dict) -> str:
        """Use LLM to fix code that couldn't be fixed deterministically."""
        is_repeated = error_text[:200] in self.previous_errors
        self.previous_errors.append(error_text[:200])

        extra = ""
        if is_repeated:
            extra = "\nThis is a REPEATED error. The previous fix didn't work. Try a different approach or comment out the failing code."
        elif self.fix_attempts >= 3:
            extra = "\nMultiple fix attempts failed. Comment out unfixable sections with TODO comments."

        prompt = f"""Fix this autosarfactory Python code.

ERROR:
{error_text[:1500]}

{COMPACT_API_RULES}

PLAN: {plan.get('checklist', '')}

CODE:
```python
{code}
```
{extra}
Return ONLY the fixed Python code:"""

        try:
            response = self.model.generate_content(prompt)
            fixed = response.text
            if "```python" in fixed:
                fixed = fixed.split("```python")[1].split("```")[0]
            elif "```" in fixed:
                fixed = fixed.split("```")[1].split("```")[0]
            fixed = fixed.strip()

            # Apply deterministic fixes on top of LLM fix
            fixed, _ = apply_all_fixes(fixed)

            return fixed if fixed != code else code
        except Exception as e:
            print(f"   LLM fix failed: {e}")
            return code

    def validate_and_fix(self, code: str, plan: dict) -> Tuple[str, List[str]]:
        """
        Complete validation + fixing pipeline.
        Returns (fixed_code, list_of_issues).
        """
        issues = []

        # Apply all deterministic fixes
        fixed, fixes = apply_all_fixes(code)
        issues.extend(fixes)

        # Validate method existence via API index
        try:
            from src.api_index import get_api_index
            import ast
            idx = get_api_index()
            tree = ast.parse(fixed)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    method = node.func.attr
                    if method.startswith(('new_', 'set_', 'get_')):
                        if not idx.method_exists(method):
                            similar = idx.find_similar_method(method)
                            if similar:
                                fixed = fixed.replace(method, similar[0])
                                issues.append(f"Fixed: {method} -> {similar[0]}")
                            else:
                                issues.append(f"Unknown method: {method}")
        except Exception:
            pass

        return fixed, issues
