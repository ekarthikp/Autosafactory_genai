import re
from src.utils import get_llm_model
from src.knowledge import inspect_class
from src.patterns import CRITICAL_API_HINTS, get_minimal_example

class Fixer:
    def __init__(self):
        self.model = get_llm_model()
        self.previous_errors = []  # Track previous errors to detect repeated failures
        self.fix_attempts = 0

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

    def fix_code(self, code, error_log, plan):
        """
        Fixes the code based on the error log with API knowledge.
        """
        self.fix_attempts += 1

        # Check if we're seeing repeated errors - if so, be more aggressive with commenting out
        is_repeated = self._is_repeated_error(error_log)
        error_line = self._extract_error_line(error_log)

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

        # Get relevant API knowledge based on the error
        relevant_classes = self._extract_relevant_classes_from_error(error_log, code)
        api_context = []
        for cls in relevant_classes:
            info = inspect_class(cls)
            if "not found" not in info:
                api_context.append(info)
        api_context_str = "\n\n".join(api_context) if api_context else "No specific API context extracted."

        prompt = f"""
You are an Expert Python Debugger for AUTOSAR code using the 'autosarfactory' library.

The following code failed to execute or verify. Your job is to fix it.

FAILED CODE:
```python
{code}
```

ERROR LOG:
{error_log}

ORIGINAL PLAN:
{plan['checklist']}

{CRITICAL_API_HINTS}

RELEVANT API KNOWLEDGE (for classes mentioned in the error):
{api_context_str}

WORKING EXAMPLE FOR REFERENCE:
{get_minimal_example()}

COMMON FIXES FOR TYPICAL ERRORS:

1. "AttributeError: 'X' object has no attribute 'set_Y'" errors:
   - WRONG: obj.set_frame(frame) or obj.set_iSignal(signal)
   - RIGHT: Create a *Ref child, then set_value():
     frame_ref = obj.new_FrameRef()
     frame_ref.set_value(frame)

2. "AttributeError: 'CanCluster' has no attribute 'set_baudrate'":
   - Baudrate is set on CanClusterConditional (returned by new_CanClusterVariant), NOT CanCluster:
     can_cluster_variant = can_cluster.new_CanClusterVariant("VariantName")
     can_cluster_variant.set_baudrate(500000)  # Direct call on CanClusterConditional
   - DO NOT use get_canClusterConfig() or new_CanClusterConfig() - these methods don't exist!

3. "TypeError: missing required argument 'name'":
   - Methods like new_ISignalToPduMapping, new_PduToFrameMapping, new_CanFrameTriggering REQUIRE a name argument
   - WRONG: pdu.new_ISignalToPduMapping()
   - RIGHT: pdu.new_ISignalToPduMapping("SignalMapping_Name")

4. "AttributeError: 'X' has no attribute 'new_DataReadAccess'":
   - Note the spelling in autosarfactory: DataReadAcces (one 's')
   - WRONG: runnable.new_DataReadAccess("name")
   - RIGHT: runnable.new_DataReadAcces("name")

5. Verification errors (missing elements):
   - Ensure all elements are created within proper ARPackages
   - Ensure autosarfactory.save() is called at the end
   - Check that all references are properly linked

6. ByteOrderEnum errors (TypeError for set_packingByteOrder):
   - WRONG: set_packingByteOrder("MOST-SIGNIFICANT-BYTE-LAST")
   - RIGHT: set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)

7. "AttributeError: 'CanPhysicalChannel' has no attribute 'new_PduToFrameMapping'":
   - PduToFrameMapping is created on the FRAME, not the channel!
   - WRONG: channel.new_PduToFrameMapping("name")
   - RIGHT: frame.new_PduToFrameMapping("name")

IMPORTANT: If you cannot fix a particular line of code after trying, COMMENT IT OUT with a TODO explaining what was attempted and why it failed. DO NOT leave broken code - either fix it or comment it out so the rest of the script can run.
{additional_instructions}
TASK:
1. Analyze the error carefully
2. Apply the appropriate fix based on the patterns above
3. If you absolutely cannot fix a line, COMMENT IT OUT rather than leaving broken code
4. Return ONLY the complete fixed Python script

FIXED PYTHON SCRIPT:
"""
        print("   Fixing code with API knowledge...")
        response = self.model.generate_content(prompt)
        code = response.text

        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        return code.strip()
