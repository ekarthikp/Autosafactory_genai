"""
Neuro-Symbolic Generator - Near-Deterministic Code Generation
==============================================================
This is the main generator that combines all neuro-symbolic components
into a unified, near-deterministic code generation pipeline.

Architecture:
1. Intent Parser: Extract classes and parameters from user query
2. Constrained Selection: Force LLM to select only valid methods
3. Code Synthesizer: Generate code from validated operations
4. Validation Pipeline: Catch and fix any remaining issues
5. Reflexion Loop: Self-correct if execution fails

The LLM is used for:
- Intent understanding (what the user wants)
- Semantic reasoning (how to structure the solution)

The LLM is NOT used for:
- Method name generation (constrained to valid options)
- API pattern decisions (enforced by knowledge base)
- Reference patterns (enforced by synthesizer)
"""

import os
import json
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from enum import Enum

# Import neuro-symbolic components
from src.knowledge_base import get_knowledge_base, UnifiedKnowledgeBase
from src.code_synthesizer import get_code_synthesizer, DeterministicCodeSynthesizer
from src.constrained_selector import (
    get_selection_engine,
    get_intent_parser,
    ConstrainedSelectionEngine,
    IntentParser,
    CodePlanResult
)
from src.validation_engine import (
    get_validation_pipeline,
    ValidationPipeline,
    ValidationResult
)
from src.patterns import CRITICAL_API_HINTS, get_pattern_for_task, get_minimal_example


# ============================================================================
# Generation Result
# ============================================================================

@dataclass
class GenerationResult:
    """Complete result of code generation."""
    success: bool
    code: str
    validation_result: Optional[ValidationResult] = None
    fixes_applied: List[str] = field(default_factory=list)
    generation_method: str = "neuro_symbolic"
    iterations: int = 1
    error_message: Optional[str] = None


# ============================================================================
# Neuro-Symbolic Generator
# ============================================================================

class NeuroSymbolicGenerator:
    """
    Main generator using the neuro-symbolic architecture.

    This generator implements the "near-deterministic" approach by:
    1. Using ground truth (symbol table) for all API decisions
    2. Constraining LLM selection to valid methods only
    3. Applying deterministic fixes before execution
    4. Using reflexion loop for any remaining issues
    """

    def __init__(self, llm_model=None, enable_fallback: bool = True):
        """
        Initialize the generator.

        Args:
            llm_model: The LLM model for semantic reasoning
            enable_fallback: If True, fall back to traditional generation if structured fails
        """
        # LLM model
        if llm_model is None:
            from src.utils import get_llm_model
            self.model = get_llm_model()
        else:
            self.model = llm_model

        # Neuro-symbolic components
        self.kb = get_knowledge_base()
        self.synthesizer = get_code_synthesizer()
        self.selector = get_selection_engine()
        self.intent_parser = get_intent_parser()
        self.validation_pipeline = get_validation_pipeline(llm_model=self.model)

        self.enable_fallback = enable_fallback

        print("NeuroSymbolicGenerator initialized with:")
        print(f"  - {len(self.kb.symbol_table.classes)} classes in knowledge base")
        print(f"  - Fallback enabled: {enable_fallback}")

    def generate(self, plan: Dict[str, Any],
                 output_file: str = "output.arxml",
                 edit_context: Dict[str, Any] = None) -> GenerationResult:
        """
        Generate code from a plan using the neuro-symbolic pipeline.

        Args:
            plan: The execution plan with 'checklist' and 'description'
            output_file: Output ARXML file path
            edit_context: Optional dict with 'source_file' for edit mode

        Returns:
            GenerationResult with generated code
        """
        is_edit_mode = edit_context is not None
        source_file = edit_context.get('source_file') if edit_context else None

        print("   🧠 Neuro-Symbolic Generation Pipeline")

        try:
            # Phase 1: Parse intent from plan
            print("   📊 Phase 1: Parsing intent...")
            plan_text = str(plan.get('checklist', '')) + ' ' + str(plan.get('description', ''))
            intent = self.intent_parser.parse_intent(plan_text)

            relevant_classes = intent['classes']
            print(f"      Identified {len(relevant_classes)} relevant classes")

            # Phase 2: Generate constrained selection prompt
            print("   🔒 Phase 2: Building constraints...")
            selection_prompt = self.selector.generate_selection_prompt(
                relevant_classes,
                plan_text,
                output_file,
                is_edit_mode,
                source_file
            )

            # Phase 3: Ask LLM to create structured plan
            print("   🤖 Phase 3: LLM structured planning...")
            structured_plan = self._get_structured_plan(
                plan,
                selection_prompt,
                output_file,
                is_edit_mode,
                source_file
            )

            if structured_plan is None:
                raise ValueError("Failed to get structured plan from LLM")

            # Phase 4: Validate the plan
            print("   ✓ Phase 4: Validating plan...")
            plan_issues = self.validation_pipeline.validate_plan(
                structured_plan.get('operations', [])
            )

            if plan_issues:
                print(f"      Found {len(plan_issues)} issues, applying fixes...")
                structured_plan = self._repair_plan(structured_plan)

            # Phase 5: Synthesize code
            print("   ⚙️ Phase 5: Synthesizing code...")
            code, synth_errors = self.synthesizer.synthesize_from_operations(
                structured_plan.get('operations', []),
                output_file,
                is_edit_mode,
                source_file
            )

            # Phase 6: Validate generated code
            print("   🔍 Phase 6: Validating generated code...")
            fixed_code, validation_result = self.validation_pipeline.validate_and_fix_code(
                code,
                context=self._build_fix_context(plan),
                use_reflexion=False  # Use deterministic fixes first
            )

            if validation_result.fixed_code:
                code = validation_result.fixed_code

            # Check if valid
            if validation_result.is_valid:
                print("   ✅ Generation successful!")
                return GenerationResult(
                    success=True,
                    code=code,
                    validation_result=validation_result,
                    fixes_applied=validation_result.fixes_applied,
                    generation_method="neuro_symbolic"
                )

            # If not valid and reflexion available, try reflexion
            print("   🔄 Applying reflexion loop...")
            final_code, final_result = self.validation_pipeline.validate_and_fix_code(
                code,
                context=self._build_fix_context(plan),
                use_reflexion=True
            )

            if final_result.is_valid:
                return GenerationResult(
                    success=True,
                    code=final_code if final_result.fixed_code else code,
                    validation_result=final_result,
                    fixes_applied=final_result.fixes_applied,
                    generation_method="neuro_symbolic_reflexion",
                    iterations=len(self.validation_pipeline.reflexion_loop.history)
                )

            # Fall back if enabled
            if self.enable_fallback:
                print("   ⚠️ Structured generation had issues, trying fallback...")
                return self._fallback_generation(plan, output_file, edit_context)

            return GenerationResult(
                success=False,
                code=final_code if final_result.fixed_code else code,
                validation_result=final_result,
                error_message="Validation failed after reflexion"
            )

        except Exception as e:
            print(f"   ❌ Neuro-symbolic generation failed: {e}")

            if self.enable_fallback:
                print("   ⚠️ Falling back to traditional generation...")
                return self._fallback_generation(plan, output_file, edit_context)

            return GenerationResult(
                success=False,
                code="",
                error_message=str(e)
            )

    def _get_structured_plan(self, plan: Dict[str, Any],
                             constraints_prompt: str,
                             output_file: str,
                             is_edit_mode: bool,
                             source_file: str = None) -> Optional[Dict]:
        """
        Get a structured code plan from the LLM.

        The LLM is constrained to select only from valid methods.
        """
        checklist = plan.get('checklist', [])
        if isinstance(checklist, list):
            checklist_text = "\n".join(f"  {i+1}. {item}" for i, item in enumerate(checklist))
        else:
            checklist_text = str(checklist)

        prompt = f"""
{constraints_prompt}

TASK TO IMPLEMENT:
{checklist_text}

Generate a structured code plan as JSON. Each operation must use ONLY methods from the VALID METHODS list above.

Example format:
{{
  "summary": "Create a CAN cluster with frame and signal",
  "operations": [
    {{
      "step_number": 1,
      "description": "Create root package",
      "source_variable": "root_pkg",
      "source_class": "ARPackage",
      "method_name": "new_ARPackage",
      "arguments": [{{"name": "shortName", "value": "Communication", "is_variable_ref": false}}],
      "result_variable": "comm_pkg"
    }}
  ],
  "output_file": "{output_file}",
  "is_edit_mode": {str(is_edit_mode).lower()},
  "source_file": {f'"{source_file}"' if source_file else 'null'}
}}

CRITICAL:
- Use ONLY methods from the VALID METHODS list
- For references, use direct setters (set_frame, set_pdu) NOT new_*Ref patterns
- For behaviors, use new_InternalBehavior NOT new_SwcInternalBehavior
- For runnables, use new_Runnable NOT new_RunnableEntity

Return ONLY the JSON object, no markdown:
"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text

            # Extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            # Try to parse
            plan_dict = json.loads(text.strip())
            return plan_dict

        except json.JSONDecodeError as e:
            print(f"      Warning: Failed to parse structured plan: {e}")
            return None
        except Exception as e:
            print(f"      Warning: Failed to get structured plan: {e}")
            return None

    def _repair_plan(self, plan: Dict) -> Dict:
        """Repair a plan by fixing known hallucinations."""
        from src.knowledge_base import HALLUCINATION_FIXES

        repaired = plan.copy()
        operations = repaired.get('operations', [])

        for op in operations:
            method_name = op.get('method_name', '')
            if method_name in HALLUCINATION_FIXES:
                op['method_name'] = HALLUCINATION_FIXES[method_name]

        return repaired

    def _build_fix_context(self, plan: Dict) -> str:
        """Build context for LLM fixing."""
        return f"""
ORIGINAL TASK:
{plan.get('checklist', '')}

{CRITICAL_API_HINTS}
"""

    def _fallback_generation(self, plan: Dict[str, Any],
                             output_file: str,
                             edit_context: Dict = None) -> GenerationResult:
        """
        Fall back to traditional LLM-based generation.

        This is used when structured generation fails.
        """
        from src.generator import Generator

        # Use the existing generator
        fallback_gen = Generator(enable_deep_thinking=False, enable_codebase_kb=False)
        fallback_gen.model = self.model

        try:
            code = fallback_gen.generate_code(plan, output_file, edit_context)

            # Apply deterministic fixes
            fixed_code, fixes = self.validation_pipeline.quick_fix(code)

            return GenerationResult(
                success=True,
                code=fixed_code,
                fixes_applied=fixes,
                generation_method="fallback_traditional"
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                code="",
                error_message=f"Fallback generation failed: {e}"
            )

    def generate_simple(self, description: str,
                        output_file: str = "output.arxml") -> GenerationResult:
        """
        Simple interface for quick code generation.

        Args:
            description: Natural language description of what to create
            output_file: Output file path

        Returns:
            GenerationResult
        """
        plan = {
            "description": description,
            "checklist": [description]
        }
        return self.generate(plan, output_file)


# ============================================================================
# Integration with Existing Generator
# ============================================================================

class HybridGenerator:
    """
    Hybrid generator that combines neuro-symbolic and traditional approaches.

    Uses neuro-symbolic as primary, with intelligent fallback.
    """

    def __init__(self, llm_model=None):
        """Initialize hybrid generator."""
        if llm_model is None:
            from src.utils import get_llm_model
            self.model = get_llm_model()
        else:
            self.model = llm_model

        self.neuro_gen = NeuroSymbolicGenerator(
            llm_model=self.model,
            enable_fallback=True
        )

    def generate_code(self, plan: Dict[str, Any],
                      output_file: str = "output.arxml",
                      edit_context: Dict = None) -> str:
        """
        Generate code using the hybrid approach.

        This is API-compatible with the existing Generator class.

        Returns:
            Generated Python code string
        """
        result = self.neuro_gen.generate(plan, output_file, edit_context)

        if result.success:
            print(f"   Generation method: {result.generation_method}")
            if result.fixes_applied:
                print(f"   Fixes applied: {len(result.fixes_applied)}")
            return result.code
        else:
            raise RuntimeError(f"Code generation failed: {result.error_message}")


# ============================================================================
# Singleton Access
# ============================================================================

_neuro_gen_instance: Optional[NeuroSymbolicGenerator] = None
_hybrid_gen_instance: Optional[HybridGenerator] = None


def get_neuro_generator(llm_model=None) -> NeuroSymbolicGenerator:
    """Get the global neuro-symbolic generator instance."""
    global _neuro_gen_instance

    if _neuro_gen_instance is None:
        _neuro_gen_instance = NeuroSymbolicGenerator(llm_model=llm_model)

    return _neuro_gen_instance


def get_hybrid_generator(llm_model=None) -> HybridGenerator:
    """Get the global hybrid generator instance."""
    global _hybrid_gen_instance

    if _hybrid_gen_instance is None:
        _hybrid_gen_instance = HybridGenerator(llm_model=llm_model)

    return _hybrid_gen_instance


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    print("Testing Neuro-Symbolic Generator...")
    print("=" * 60)

    # Simple test without LLM
    from src.code_synthesizer import get_code_synthesizer
    from src.validation_engine import get_pre_validator

    synthesizer = get_code_synthesizer()
    validator = get_pre_validator()

    # Test operation synthesis
    operations = [
        {
            "source_var": "root_pkg",
            "method_name": "new_ARPackage",
            "result_var": "comm_pkg",
            "arguments": {"shortName": "Communication"}
        },
        {
            "source_var": "comm_pkg",
            "method_name": "new_CanCluster",
            "result_var": "cluster",
            "arguments": {"shortName": "HS_CAN"}
        },
        {
            "source_var": "cluster",
            "method_name": "new_CanClusterVariant",
            "result_var": "variant",
            "arguments": {"shortName": "HS_CAN_Variant"}
        },
        {
            "source_var": "variant",
            "method_name": "set_baudrate",
            "arguments": {"baudrate": 500000}
        }
    ]

    print("\n=== Synthesizing from operations ===")
    code, errors = synthesizer.synthesize_from_operations(operations)

    print("\n=== Generated Code ===")
    print(code)

    print("\n=== Validation ===")
    result = validator.validate(code)
    print(f"Valid: {result.is_valid}")
    print(f"Errors: {result.error_count}")

    if result.fixes_applied:
        print(f"Fixes applied: {result.fixes_applied}")
