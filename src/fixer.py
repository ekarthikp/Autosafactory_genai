import re
from src.utils import get_llm_model
from src.knowledge import inspect_class
from src.patterns import CRITICAL_API_HINTS, get_minimal_example
from src.knowledge_manager import KnowledgeManager

class Fixer:
    def __init__(self, max_attempts=5, enable_deep_analysis=True):
        self.model = get_llm_model()
        self.previous_errors = []  # Track previous errors to detect repeated failures
        self.fix_attempts = 0
        self.max_attempts = max_attempts
        self.enable_deep_analysis = enable_deep_analysis

    def _extract_error_line(self, error_log):
        """Extract the line number from the error traceback."""
        # Look for patterns like "line 24" or "line 73"
        match = re.search(r'line (\d+)', error_log)
        if match:
            return int(match.group(1))
        return None

    def _is_repeated_error(self, error_log):
        """Check if we're seeing the same error repeatedly."""
        # Extract key error info
        error_key = error_log[:200] if len(error_log) > 200 else error_log
        if error_key in self.previous_errors:
            return True
        self.previous_errors.append(error_key)
        return False

    def _extract_relevant_classes_from_error(self, error_log, code):
        """
        Extract class names mentioned in error or code to provide targeted API help.
        """
        classes = set()
        # Common classes that often cause errors
        error_indicators = {
            "CanCluster": ["CanCluster", "CanClusterVariant", "CanClusterConditional", "CanClusterConfig"],
            "baudrate": ["CanClusterConditional", "CanClusterConfig"],
            "CanFrame": ["CanFrame", "CanFrameTriggering", "FrameRef"],
            "ISignal": ["ISignal", "ISignalIPdu", "ISignalToPduMapping", "ISignalRef"],
            "Pdu": ["ISignalIPdu", "PduToFrameMapping", "PduRef"],
            "set_frame": ["CanFrameTriggering", "FrameRef"],
            "set_iSignal": ["ISignalToPduMapping", "ISignalRef"],
            "set_pdu": ["PduToFrameMapping", "PduRef"],
            "SwBaseType": ["SwBaseType", "BaseTypeDirectDefinition"],
            "ImplementationDataType": ["ImplementationDataType", "SwDataDefProps", "SwDataDefPropsVariant"],
            "Interface": ["SenderReceiverInterface", "DataElement"],
            "Port": ["PPortPrototype", "RPortPrototype", "RequiredInterfaceRef", "ProvidedInterfaceRef"],
            "Behavior": ["SwcInternalBehavior", "RunnableEntity"],
            "DataReadAccess": ["RunnableEntity", "DataReadAcces"],  # Note spelling
            "DataWriteAccess": ["RunnableEntity", "DataWriteAcces"],  # Note spelling
        }

        combined_text = error_log + " " + code
        for indicator, cls_list in error_indicators.items():
            if indicator.lower() in combined_text.lower():
                classes.update(cls_list)

        return list(classes)
    
    def _deep_analyze_error(self, code, error_info, plan):
        """
        Deep analysis of error before attempting fix.
        Uses error feedback to find similar past errors and successful fixes.
        
        Args:
            code: The failing code
            error_info: Structured error information (dict or string)
            plan: The execution plan
            
        Returns:
            Dictionary with analysis insights
        """
        from src.error_feedback_manager import get_error_feedback_manager
        efm = get_error_feedback_manager()
        
        # Extract error message
        if isinstance(error_info, dict):
            error_message = error_info.get('message', str(error_info))
            error_type = error_info.get('type', 'Unknown')
        else:
            error_message = str(error_info)
            error_type = 'Unknown'
        
        # Find similar past errors
        similar_errors = efm.get_similar_errors(error_message, limit=3)
        
        # Get fix suggestions
        fix_suggestions = efm.get_fix_suggestions(error_type, error_message)
        
        # Build analysis
        analysis = {
            "error_type": error_type,
            "similar_errors_found": len(similar_errors),
            "past_successful_fixes": fix_suggestions,
            "success_rate_for_type": efm.get_success_rate_for_error_type(error_type)
        }
        
        return analysis

    def fix_code(self, code, error_log, plan):
        """
        Fixes the code based on the error log with API knowledge.
        """
        self.fix_attempts += 1
        
        # Check max attempts
        if self.fix_attempts > self.max_attempts:
            print(f"   ⚠️  Max fix attempts ({self.max_attempts}) reached.")
            return code  # Return code as-is
        
        # Deep analysis of the error (if enabled)
        analysis = None
        if self.enable_deep_analysis:
            print(f"   🔍 Deep analyzing error (attempt {self.fix_attempts})...")
            analysis = self._deep_analyze_error(code, error_log, plan)
            
            if analysis.get('past_successful_fixes'):
                print(f"   💡 Found {len(analysis['past_successful_fixes'])} similar past fixes")

        # Check if we're seeing repeated errors - if so, be more aggressive with commenting out
        is_repeated = self._is_repeated_error(error_log if isinstance(error_log, str) else error_log.get('traceback', ''))
        error_line = self._extract_error_line(error_log if isinstance(error_log, str) else error_log.get('traceback', ''))

        additional_instructions = ""
        if is_repeated:
            additional_instructions = f"""
IMPORTANT: This is a REPEATED error. The previous fix attempt did not work.
If you cannot fix line {error_line if error_line else 'the problematic'} after this attempt,
COMMENT OUT the problematic code section with:
# TODO: Could not fix - <brief description of what was attempted>
# <original code here>

This allows the rest of the script to run and generate partial output.
"""
        elif self.fix_attempts >= 3:
            additional_instructions = """
IMPORTANT: Multiple fix attempts have been made. If the error persists on specific lines,
consider COMMENTING OUT the problematic code sections to allow partial generation.
Add a TODO comment explaining what could not be implemented.
"""
        
        # Add analysis insights to instructions
        if analysis and analysis.get('past_successful_fixes'):
            additional_instructions += f"""

PAST SUCCESSFUL FIXES FOR SIMILAR ERRORS:
{chr(10).join('- ' + f for f in analysis['past_successful_fixes'])}

Apply similar strategies if applicable.
"""

        # Get relevant API knowledge based on the error
        from src.knowledge_manager import KnowledgeManager
        km = KnowledgeManager()
        
        # Extract error text for processing (handle both dict and string)
        if isinstance(error_log, dict):
            error_text = error_log.get('traceback', '') + ' ' + error_log.get('message', '')
            error_type = error_log.get('type', '')
        else:
            error_text = str(error_log)
            error_type = ''
        
        relevant_classes = self._extract_relevant_classes_from_error(error_text, code)
        
        # Use KM to find method origins if AttributeError
        if "AttributeError" in error_text or error_type == "AttributeError":
            # Try to extract the attribute name
            import re
            match = re.search(r"has no attribute '(\w+)'", error_text)
            if match:
                attr_name = match.group(1)
                origin_classes = km.find_method_origin(attr_name)
                if origin_classes:
                    relevant_classes.extend(origin_classes)
                    additional_instructions += f"\n\nHINT: The method '{attr_name}' is defined in {origin_classes}. Check if you are using the correct object."

        # Build context with dependencies
        expanded_classes = set(relevant_classes)
        for cls in relevant_classes:
            deps = km.get_dependencies(cls, recursive=True, max_depth=1)
            expanded_classes.update(deps)
            
        api_context_str = km.get_context_for_classes(list(expanded_classes))


        prompt = f"""
You are an Expert Python Debugger for AUTOSAR code using the 'autosarfactory' library.

The following code failed to execute or verify. Your job is to fix it.

FAILED CODE:
```python
{code}
```

ERROR LOG:
{error_text}

ORIGINAL PLAN:
{plan['checklist']}

{CRITICAL_API_HINTS}

RELEVANT API KNOWLEDGE (for classes mentioned in the error):

FIXED PYTHON SCRIPT:
"""
        print("   Fixing code with API knowledge...")
        
        try:
            # Internal retry loop to force changes
            for internal_attempt in range(2):
                response = self.model.generate_content(prompt)
                fixed_code = response.text

                if "```python" in fixed_code:
                    fixed_code = fixed_code.split("```python")[1].split("```")[0]
                elif "```" in fixed_code:
                    fixed_code = fixed_code.split("```")[1].split("```")[0]
                
                fixed_code = fixed_code.strip()
                
                if fixed_code != code:
                    return fixed_code
                
                print(f"   ⚠️ Fixer returned identical code (internal attempt {internal_attempt + 1}). Retrying with stronger prompt...")
                prompt += "\n\nCRITICAL: You returned the EXACT SAME code as before. You MUST make changes to fix the error. If you cannot fix it, comment out the failing lines."

            return fixed_code

        except Exception as e:
            print(f"   ❌ Fixer LLM call failed: {e}")
            return code # Return original code on failure
