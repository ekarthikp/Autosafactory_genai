from src.utils import get_llm_model
from src.knowledge import inspect_class
from src.patterns import get_pattern_for_task, get_minimal_example, CRITICAL_API_HINTS
from src.rag_codebase import CodebaseKnowledgeBase

# Pattern for loading existing ARXML
EDIT_MODE_PATTERN = '''
# === EDIT MODE: Loading Existing ARXML ===
import autosarfactory.autosarfactory as autosarfactory

# Load existing file - read() returns a tuple (AUTOSAR_root, status)
autosar_root, status = autosarfactory.read(["{source_file}"])
if not status or not autosar_root:
    raise Exception("Failed to load ARXML file")

print(f"Successfully loaded ARXML file: {source_file}")

# === DISCOVERY HELPERS - Find elements by TYPE, not by assumed names ===

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
    """Find FIRST element of a given type - use when only one exists"""
    elements = find_all_elements_by_type(root, type_name)
    if elements:
        if len(elements) > 1:
            print(f"Warning: Found {{len(elements)}} {{type_name}} elements, using first one: {{elements[0].get_shortName()}}")
        return elements[0]
    return None

def print_structure(root, indent=0):
    """Print all packages and elements in the ARXML"""
    if hasattr(root, 'get_arPackages'):
        for pkg in root.get_arPackages():
            print("  " * indent + f"Package: {{pkg.get_shortName()}}")
            if hasattr(pkg, 'get_elements'):
                for elem in pkg.get_elements():
                    print("  " * (indent+1) + f"Element: {{elem.get_shortName()}} ({{type(elem).__name__}})")
            print_structure(pkg, indent+1)

# Print file structure to see what's available
print("\\n=== ARXML Structure ===")
print_structure(autosar_root)
print("======================\\n")

# === USAGE PATTERNS ===

# Find by TYPE (recommended - doesn't assume names):
# swc = find_element_by_type(autosar_root, "ApplicationSwComponentType")
# timing_events = find_all_elements_by_type(autosar_root, "TimingEvent")
# can_frames = find_all_elements_by_type(autosar_root, "CanFrame")

# === INTERNAL BEHAVIOR PATTERN (CRITICAL!) ===
# WRONG: swc.new_SwcInternalBehavior("name")  # Method doesn't exist!
# RIGHT: swc.new_InternalBehavior("name")  # Returns SwcInternalBehavior

# Get behaviors (returns a LIST):
# behaviors = swc.get_internalBehaviors()
# behavior = behaviors[0] if behaviors else swc.new_InternalBehavior("BehaviorName")

# Get events from a behavior (returns a LIST):
# for event in behavior.get_events():
#     if type(event).__name__ == "TimingEvent":
#         print(f"TimingEvent: {{event.get_shortName()}}, period={{event.get_period()}}")
#         event.set_period(0.01)  # Set to 10ms

# Create a timing event:
# timing_event = behavior.new_TimingEvent("EventName")
# timing_event.set_period(0.1)  # 100ms

# Save changes:
autosarfactory.save()  # Save to original file
# autosarfactory.saveAs("{output_file}", overWrite=True)  # Save to new file
'''


class Generator:
    def __init__(self, enable_deep_thinking=True):
        self.model = get_llm_model()
        self.enable_deep_thinking = enable_deep_thinking
        self.last_thinking = None  # Store thinking for debugging
        self.codebase_kb = None
        try:
            self.codebase_kb = CodebaseKnowledgeBase()
        except Exception as e:
            print(f"Warning: Could not initialize Codebase Knowledge Base: {e}")

    def _deep_think(self, plan, output_file, is_edit_mode):
        """
        Deep thinking phase: Analyze the plan before generating code.
        
        Returns:
            Dictionary with analysis and recommendations
        """
        thinking_prompt = f"""
You are an Expert AUTOSAR Code Analysis AI.
Before generating the actual code, carefully analyze this plan and provide strategic insights.

PLAN TO ANALYZE:
{plan['checklist']}

OUTPUT FILE: {output_file}
MODE: {'EDIT' if is_edit_mode else 'CREATE'}

Your task is to think deeply about potential issues and provide recommendations.

Analyze:
1. **Dependency Order**: Are the steps in the correct order? What must be created before what?
2. **Critical Pitfalls**: What are the most common errors for this type of AUTOSAR configuration?
3. **Reference Patterns**: Which elements will need references to others? How should they be linked?
4. **Validation Strategy**: How can we verify this configuration is correct?
5. **Alternative Approaches**: Are there simpler or more robust ways to achieve this?

Return your analysis as a JSON object:
{{
  "dependency_warnings": ["Step X should come before Step Y because..."],
  "critical_pitfalls": ["Watch out for...", "Common mistake is..."],
  "reference_strategy": {{"Frame to Triggering": "Use direct setter, not new_Ref"}},
  "validation_checklist": ["Ensure X exists", "Verify Y is linked"],
  "recommendations": ["Consider...", "Alternatively..."]
}}
"""
        
        try:
            response = self.model.generate_content(thinking_prompt)
            thinking_text = response.text
            
            # Clean JSON
            if "```json" in thinking_text:
                thinking_text = thinking_text.split("```json")[1].split("```")[0]
            elif "```" in thinking_text:
                thinking_text = thinking_text.split("```")[1].split("```")[0]
            
            import json
            thinking = json.loads(thinking_text)
            self.last_thinking = thinking
            return thinking
        except Exception as e:
            print(f"Warning: Deep thinking failed: {e}")
            # Return empty thinking if it fails
            return {
                "dependency_warnings": [],
                "critical_pitfalls": [],
                "reference_strategy": {},
                "validation_checklist": [],
                "recommendations": []
            }
    
    def generate_code(self, plan, output_file="output.arxml", edit_context=None):
        """
        Generates Python code based on the plan and API knowledge.
        Supports both CREATE and EDIT modes.

        Args:
            plan: The execution plan
            output_file: Output file path
            edit_context: Optional dict with 'source_file' and 'output_file' for edit mode
        """
        # Determine operation mode
        is_edit_mode = False
        source_file = None

        if edit_context:
            is_edit_mode = True
            source_file = edit_context.get('source_file')
            output_file = edit_context.get('output_file', output_file)
        
        # DEEP THINKING PHASE
        thinking = None
        if self.enable_deep_thinking:
            print("   🧠 Deep thinking about the plan...")
            thinking = self._deep_think(plan, output_file, is_edit_mode)

        # 1. Identify relevant classes using Knowledge Manager
        from src.knowledge_manager import KnowledgeManager
        km = KnowledgeManager()
        
        # Search for classes based on plan keywords
        plan_text = str(plan.get('checklist', '')) + ' ' + str(plan.get('description', ''))
        
        # Extract potential keywords from plan
        # We can use the existing heuristic keywords map to seed the search, 
        # but then use KM to expand dependencies.
        initial_classes = self._identify_classes(plan)
        
        # Expand dependencies recursively
        expanded_classes = set(initial_classes)
        for cls in initial_classes:
            deps = km.get_dependencies(cls, recursive=True, max_depth=2)
            expanded_classes.update(deps)
            
        # Always include critical classes
        expanded_classes.add("ARPackage")
        if is_edit_mode:
            expanded_classes.add("read") # Function
        else:
            expanded_classes.add("new_file") # Function
            
        # 2. Build API context using Knowledge Manager
        context_str = km.get_context_for_classes(list(expanded_classes))

        # 2.1 Enhance context with Codebase RAG
        rag_context = ""
        if self.codebase_kb:
            try:
                rag_query = f"{plan.get('description', '')} {plan_text[:200]}"
                # Extract step descriptions for better query
                for step in plan.get('checklist', [])[:5]:
                    rag_query += f" {step}"

                rag_results = self.codebase_kb.query(rag_query, n_results=5)
                rag_context = f"\nADDITIONAL API KNOWLEDGE (RAG):\n{rag_results}\n"
            except Exception as e:
                print(f"Warning: Codebase RAG query failed: {e}")

        context_str += rag_context

        # 3. Get relevant patterns based on plan content
        relevant_patterns = get_pattern_for_task(plan_text)


        # 4. Build mode-specific instructions
        if is_edit_mode:
            mode_instruction = f"""
OPERATION MODE: EDIT/ADD TO EXISTING ARXML

SOURCE FILE: {source_file}
OUTPUT FILE: {output_file}

EDIT MODE PATTERN:
{EDIT_MODE_PATTERN.format(source_file=source_file, output_file=output_file)}

CRITICAL EDIT MODE RULES:
1. Use autosarfactory.read(["{source_file}"]) - pass a LIST, returns tuple (root, status)
2. NEVER use get_ARPackage("name") or get_ApplicationSwComponentType("name") - these don't exist!
3. FIND BY TYPE, NOT BY NAME: Use find_element_by_type(root, "TypeName") or find_all_elements_by_type(root, "TypeName")
4. DO NOT assume element names like "MySwc" or "ComponentTypes" - discover them dynamically
5. To find a TimingEvent: find_all_elements_by_type(autosar_root, "TimingEvent") returns ALL timing events
6. To find a SWC: swc = find_element_by_type(autosar_root, "ApplicationSwComponentType")
7. INTERNAL BEHAVIOR - CRITICAL:
   - WRONG: swc.new_SwcInternalBehavior("name")  # This method DOES NOT EXIST!
   - RIGHT: swc.new_InternalBehavior("name")  # Returns SwcInternalBehavior
8. Get behaviors: swc.get_internalBehaviors() returns a LIST - iterate or use [0]
9. Get events: behavior.get_events() returns a LIST, filter by type(event).__name__ == "TimingEvent"
10. TimingEvent: behavior.new_TimingEvent("name"), event.set_period(0.01) for 10ms
11. Add new elements using new_*() methods on the found package
12. Save: autosarfactory.save() for original, autosarfactory.saveAs("{output_file}", overWrite=True) for new file
13. NEVER use autosarfactory.save(root, file) - that signature doesn't exist!
"""
        else:
            mode_instruction = f"""
OPERATION MODE: CREATE NEW ARXML

OUTPUT FILE: {output_file}

CREATE MODE: Use autosarfactory.new_file("{output_file}", defaultArPackage="...", overWrite=True)
"""

        # 5. Prepare deep thinking insights
        thinking_section = ""
        if thinking and self.enable_deep_thinking:
            thinking_section = f"""
DEEP ANALYSIS OF YOUR PLAN:
Before writing code, I analyzed the plan and found these insights:

DEPENDENCY WARNINGS:
{chr(10).join('- ' + w for w in thinking.get('dependency_warnings', [])) if thinking.get('dependency_warnings') else '- None'}

CRITICAL PITFALLS TO AVOID:
{chr(10).join('- ' + p for p in thinking.get('critical_pitfalls', [])) if thinking.get('critical_pitfalls') else '- None'}

REFERENCE STRATEGY:
{chr(10).join(f'- {k}: {v}' for k, v in thinking.get('reference_strategy', {}).items()) if thinking.get('reference_strategy') else '- Use standard patterns'}

VALIDATION CHECKLIST:
{chr(10).join('- ' + v for v in thinking.get('validation_checklist', [])) if thinking.get('validation_checklist') else '- Standard verification'}

RECOMMENDATIONS:
{chr(10).join('- ' + r for r in thinking.get('recommendations', [])) if thinking.get('recommendations') else '- Follow standard approach'}

"""
        
        # 6. Construct Prompt with patterns and examples
        prompt = f"""
You are an Expert AUTOSAR Code Generator.
You must write a complete, executable Python script using the 'autosarfactory' library.
{mode_instruction}
TASK:
Implement the following plan.

PLAN:
{plan['checklist']}

{thinking_section}
{CRITICAL_API_HINTS}

WORKING CODE PATTERNS (USE THESE AS REFERENCE):
{relevant_patterns}

COMPLETE WORKING EXAMPLE FOR REFERENCE:
{get_minimal_example()}

API KNOWLEDGE (SOURCE OF TRUTH - Available Classes and Methods):
{context_str}

CRITICAL INSTRUCTIONS:
1. FOLLOW THE PATTERNS ABOVE - they are proven to work.
2. Use ONLY the classes and methods listed in the API KNOWLEDGE above.
3. REFERENCES USE DIRECT SETTERS - DO NOT use new_*Ref() + set_value() patterns!
   - Frame references: frame_trig.set_frame(frame)
   - Signal references: signal_mapping.set_iSignal(signal)
   - PDU references: pdu_to_frame.set_pdu(pdu)
   - Port interfaces: r_port.set_requiredInterface(interface), p_port.set_providedInterface(interface)
   - Data element type: data_element.set_type(impl_data_type)
   - Base type: sw_props_variant.set_baseType(base_type)
   - Variable access: var_ref.set_portPrototype(port), var_ref.set_targetDataPrototype(element)
   - SwComponentPrototype: sw_comp_proto.set_type(swc_type)
   - ComSpec: com_spec.set_dataElement(data_element)

4. BAUDRATE SETUP:
   - new_CanClusterVariant returns a CanClusterConditional object
   - Set baudrate DIRECTLY: can_cluster_variant.set_baudrate(500000)

5. NAMING CONVENTIONS - These factory methods REQUIRE names:
   - new_ISignalToPduMapping("MappingName")
   - new_PduToFrameMapping("MappingName")
   - new_CanFrameTriggering("TrigName")
   - new_Runnable("RunnableName")  # NOT new_RunnableEntity!
   - new_TimingEvent("EventName")
   - new_DataReadAcces("AccessName")  # Note: one 's'!
   - new_DataWriteAcces("AccessName")  # Note: one 's'!

6. BYTE ORDER (Use ByteOrderEnum, NOT strings!):
   - RIGHT: set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)

7. PDU TO FRAME MAPPING - Create on FRAME object:
   - frame.new_PduToFrameMapping("MappingName")

8. SOFTWARE COMPONENTS:
   - Ports: swc.new_RPortPrototype("name"), swc.new_PPortPrototype("name")
   - Behavior: swc.new_InternalBehavior("name")
   - Runnable: behavior.new_Runnable("name")  # Returns RunnableEntity

9. The script must:
   - Import: `import autosarfactory.autosarfactory as autosarfactory`
   - For CREATE mode: `autosarfactory.new_file("{output_file}", defaultArPackage="...", overWrite=True)`
   - For EDIT mode: `autosarfactory.read("{source_file if is_edit_mode else output_file}")` and navigate to existing packages
   - Implement all steps in the plan
   - End with: `autosarfactory.save()`

10. ERROR HANDLING (CRITICAL):
    - Wrap the entire main() execution in a try-except block.
    - In the except block, write the traceback to a file named 'execution_error.log'.
    - Print "Execution failed. See execution_error.log for details."
    - Re-raise the exception.

    Example:
    if __name__ == "__main__":
        try:
            main()
        except Exception as e:
            import traceback
            with open("execution_error.log", "w") as f:
                f.write(traceback.format_exc())
            print("Execution failed. See execution_error.log for details.")
            raise e

11. Return ONLY the Python code. No markdown formatting if possible, or wrap in ```python.

GENERATE THE COMPLETE PYTHON SCRIPT:
"""
        print("   Generating code (this may take a moment)...")
        response = self.model.generate_content(prompt)

        code = response.text
        # Clean markdown
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        return code.strip()

    def _identify_classes(self, plan):
        """
        Heuristic to find relevant classes from plan text.
        Enhanced with comprehensive keyword mapping.
        """
        text = str(plan).lower()
        classes = ["ARPackage"]  # Always needed

        # Comprehensive keyword to class mapping
        keywords = {
            # CAN Cluster and Network
            "cluster": ["CanCluster", "CanClusterVariant", "CanClusterConditional", "CanClusterConfig"],
            "baudrate": ["CanClusterConditional", "CanClusterConfig", "CanClusterVariant"],
            "can": ["CanCluster", "CanClusterVariant", "CanClusterConditional", "CanClusterConfig",
                   "CanPhysicalChannel", "CanFrame", "CanFrameTriggering"],
            "physical": ["CanPhysicalChannel"],
            "channel": ["CanPhysicalChannel", "CanClusterVariant"],
            "variant": ["CanClusterVariant"],

            # Frames
            "frame": ["CanFrame", "CanFrameTriggering", "PduToFrameMapping", "FrameRef"],
            "triggering": ["CanFrameTriggering", "ISignalTriggering", "PduTriggering"],
            "id": ["CanFrameTriggering"],
            "identifier": ["CanFrameTriggering"],
            "dlc": ["CanFrame"],
            "framelength": ["CanFrame"],

            # Signals and PDUs
            "signal": ["ISignal", "ISignalIPdu", "ISignalToPduMapping", "ISignalTriggering",
                      "ISignalRef", "ISignalTypeEnum"],
            "pdu": ["ISignalIPdu", "PduToFrameMapping", "ISignalToPduMapping", "PduRef"],
            "mapping": ["ISignalToPduMapping", "PduToFrameMapping"],
            "byte order": ["ByteOrderEnum"],
            "little endian": ["ByteOrderEnum"],
            "big endian": ["ByteOrderEnum"],

            # ECU
            "ecu": ["EcuInstance", "CanCommunicationController"],
            "controller": ["CanCommunicationController", "CommunicationController"],
            "connector": ["CanCommunicationConnector", "CommunicationConnector",
                         "CommunicationConnectorRefConditional", "CommConnectorRef"],

            # Software Components
            "component": ["ApplicationSwComponentType", "SwComponentType",
                         "CompositionSwComponentType", "SwComponentPrototype",
                         "SensorActuatorSwComponentType"],
            "swc": ["ApplicationSwComponentType", "SwComponentType", "SwcInternalBehavior"],
            "application": ["ApplicationSwComponentType"],
            "composition": ["CompositionSwComponentType", "SwComponentPrototype"],

            # Ports
            "port": ["PPortPrototype", "RPortPrototype", "PRPortPrototype"],
            "p-port": ["PPortPrototype", "ProvidedInterfaceRef"],
            "r-port": ["RPortPrototype", "RequiredInterfaceRef"],
            "provider": ["PPortPrototype", "ProvidedInterfaceRef"],
            "receiver": ["RPortPrototype", "RequiredInterfaceRef"],

            # Interfaces
            "interface": ["SenderReceiverInterface", "ClientServerInterface",
                         "ModeSwitchInterface", "DataElement"],
            "sender": ["SenderReceiverInterface"],
            "data element": ["DataElement", "VariableDataPrototype"],

            # Data Types
            "data type": ["SwBaseType", "BaseTypeDirectDefinition", "ImplementationDataType",
                         "SwDataDefProps", "SwDataDefPropsVariant", "SwDataDefPropsConditional"],
            "base type": ["SwBaseType", "BaseTypeDirectDefinition", "BaseTypeRef"],
            "implementation": ["ImplementationDataType", "SwDataDefProps", "SwDataDefPropsVariant"],
            "uint8": ["SwBaseType", "ImplementationDataType"],
            "uint16": ["SwBaseType", "ImplementationDataType"],
            "uint32": ["SwBaseType", "ImplementationDataType"],
            "boolean": ["SwBaseType", "ImplementationDataType"],

            # Behavior and Runnables
            "behavior": ["SwcInternalBehavior", "RunnableEntity", "TimingEvent"],
            "runnable": ["SwcInternalBehavior", "RunnableEntity"],
            "internal behavior": ["SwcInternalBehavior"],
            "event": ["TimingEvent", "DataReceivedEvent", "OperationInvokedEvent"],
            "timing": ["TimingEvent"],

            # Data Access
            "read": ["DataReadAcces"],  # Note: one 's' in autosarfactory
            "write": ["DataWriteAcces"],  # Note: one 's' in autosarfactory
            "access": ["DataReadAcces", "DataWriteAcces"],

            # Routing
            "route": ["ISignal", "ISignalIPdu", "ISignalToPduMapping"],
            "routing": ["ISignal", "ISignalIPdu", "ISignalToPduMapping", "PduToFrameMapping"],
            "gateway": ["ISignal", "ISignalIPdu", "CanFrame", "ApplicationSwComponentType"],

            # References (often needed)
            "reference": ["FrameRef", "PduRef", "ISignalRef", "BaseTypeRef",
                         "TypeRef", "RequiredInterfaceRef", "ProvidedInterfaceRef"],

            # Signal to Service Translation
            "translation": ["SignalServiceTranslationProps", "SignalServiceTranslationEventProps", "SignalServiceTranslationControlEnum"],
            "props": ["SignalServiceTranslationProps", "SignalServiceTranslationEventProps"],
        }

        for key, cls_list in keywords.items():
            if key in text:
                classes.extend(cls_list)
                
        # Use Knowledge Manager for fuzzy search on the whole text words
        # This is expensive if we search every word, so let's just stick to the keywords for now
        # but we can use the KM to validate existence.
        
        return list(set(classes))
