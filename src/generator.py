"""
Code Generator - Compact, token-efficient ARXML code generation.
================================================================
Uses the APIIndex for accurate method info and api_fixes for corrections.
Generates compact prompts that use minimal tokens while being accurate.

Based on: https://github.com/girishchandranc/autosarfactory
"""

from src.utils import get_llm_model
from src.api_fixes import (
    COMPACT_API_RULES, apply_all_fixes, get_relevant_patterns
)

# Lazy import APIIndex (expensive to build on first run)
_api_index = None

def _get_api_index():
    global _api_index
    if _api_index is None:
        try:
            from src.api_index import get_api_index
            _api_index = get_api_index()
        except Exception as e:
            print(f"Warning: API index not available: {e}")
    return _api_index


# Compact edit mode template
EDIT_TEMPLATE = '''import autosarfactory.autosarfactory as autosarfactory

root, status = autosarfactory.read(["{source_file}"])
if not status or not root:
    raise Exception("Failed to load {source_file}")

def find_by_type(container, type_name):
    """Find all elements of a given type recursively."""
    results = []
    if hasattr(container, 'get_elements'):
        for e in container.get_elements():
            if type(e).__name__ == type_name:
                results.append(e)
    if hasattr(container, 'get_arPackages'):
        for p in container.get_arPackages():
            results.extend(find_by_type(p, type_name))
    return results
'''


class Generator:
    def __init__(self, enable_deep_thinking=False, enable_codebase_kb=False):
        self.model = get_llm_model()

    def generate_code(self, plan, output_file="output.arxml", edit_context=None):
        """
        Generate Python code from plan using compact, token-efficient prompts.
        """
        is_edit = edit_context is not None
        source_file = edit_context.get('source_file') if edit_context else None

        # Get relevant API context from index
        plan_text = str(plan.get('checklist', '')) + ' ' + str(plan.get('description', ''))
        api_context = self._get_api_context(plan_text)
        patterns = get_relevant_patterns(plan_text)

        # Build mode section
        if is_edit:
            mode_section = f"""MODE: EDIT existing file
SOURCE: {source_file}
- Use autosarfactory.read(["{source_file}"]) returns tuple (root, status)
- Navigate: root.get_arPackages(), pkg.get_elements() - iterate, don't index by name
- find_by_type(root, "ClassName") to locate elements
- Save: autosarfactory.save()"""
        else:
            mode_section = f"""MODE: CREATE new file
- root_pkg = autosarfactory.new_file("{output_file}", defaultArPackage="Root", overWrite=True)
- Save: autosarfactory.save()"""

        prompt = f"""You are an AUTOSAR code generator. Write a complete Python script.

{COMPACT_API_RULES}

{mode_section}

WORKING PATTERNS:
{patterns}

{api_context}

TASK:
{plan['checklist']}

Write the complete script. Use main() with try/except that logs to execution_error.log.
Return ONLY Python code:"""

        print("   Generating code...")
        response = self.model.generate_content(prompt)
        code = self._extract_code(response.text)

        # Apply deterministic fixes before returning
        code, fixes = apply_all_fixes(code)
        if fixes:
            print(f"   Applied {len(fixes)} pre-execution fixes")
            for f in fixes[:5]:
                print(f"      - {f}")

        return code

    def _get_api_context(self, plan_text: str) -> str:
        """Get compact API context relevant to the task."""
        idx = _get_api_index()
        if idx is None:
            return ""

        context = idx.get_relevant_context(plan_text)
        if context:
            return f"\nRELEVANT API METHODS:\n{context}\n"
        return ""

    def _extract_code(self, text: str) -> str:
        """Extract Python code from LLM response."""
        if "```python" in text:
            text = text.split("```python")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()
