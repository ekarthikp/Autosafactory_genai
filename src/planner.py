import json
from src.utils import get_llm_model
from src.knowledge_manager import KnowledgeManager

# AUTOSAR element dependencies - what elements need to be created together
ELEMENT_DEPENDENCIES = """
AUTOSAR ELEMENT CREATION ORDER AND DEPENDENCIES:

1. FILE AND PACKAGES (Always first):
   - autosarfactory.new_file() creates the ARXML file
   - ARPackages organize all elements (DataTypes, Interfaces, Components, System, Communication)

2. DATA TYPES (If signals/interfaces are needed):
   - SwBaseType (defines primitive: uint8, uint16, etc.)
   - BaseTypeDirectDefinition (sets size and encoding)
   - ImplementationDataType (used by interfaces)
   - SwDataDefProps + SwDataDefPropsVariant + BaseTypeRef (links impl type to base type)

3. CAN CLUSTER (For CAN communication):
   - CanCluster (the network)
   - CanClusterVariant (variant of the cluster)
   - CanClusterConditional + CanClusterConfig (for baudrate!)
   - CanPhysicalChannel (the physical bus)

4. CAN FRAMES (After channel exists):
   - CanFrame (the frame container, set frameLength for DLC)
   - CanFrameTriggering on channel (sets CAN ID via set_identifier)
   - FrameRef links triggering to frame

5. SIGNALS AND PDUs (After frames):
   - ISignal (the signal, set length in bits)
   - ISignalIPdu (PDU container, set length in bytes)
   - ISignalToPduMapping (maps signal to PDU, needs name!)
   - ISignalRef links mapping to signal
   - ISignalTriggering on channel (optional)

6. PDU TO FRAME MAPPING (Links PDU to Frame):
   - PduToFrameMapping on channel (needs name!)
   - PduRef links mapping to PDU
   - Set startPosition and packingByteOrder

7. ECU (If ECU is needed):
   - EcuInstance
   - CanCommunicationController (optional)

8. INTERFACES (Before software components):
   - SenderReceiverInterface (for data exchange)
   - DataElement (the data carried by interface)
   - TypeRef links to ImplementationDataType

9. SOFTWARE COMPONENT (After interfaces):
   - ApplicationSwComponentType
   - RPortPrototype (receiver port) + RequiredInterfaceRef
   - PPortPrototype (provider port) + ProvidedInterfaceRef

10. BEHAVIOR (After component):
    - SwcInternalBehavior
    - RunnableEntity (the executable code unit)
    - DataReadAcces / DataWriteAcces (note: one 's'!)
    - TimingEvent (triggers the runnable)

11. SAVE (Always last):
    - autosarfactory.save() writes the ARXML file
"""

class Planner:
    def __init__(self):
        self.model = get_llm_model()
        self.km = KnowledgeManager()

    def create_plan(self, user_input, edit_context=None):
        """
        Generates a structured checklist plan from user input with API awareness.
        Uses a DEEP PLANNING strategy for complex requests.
        """
        # Build edit mode section if applicable
        edit_section = ""
        if edit_context:
            source_file = edit_context.get('source_file')
            output_file = edit_context.get('output_file', 'output.arxml')
            edit_section = f"""
OPERATION MODE: EDIT EXISTING ARXML
Source File: {source_file}
Output File: {output_file}

IMPORTANT EDIT MODE RULES:
- Use autosarfactory.read(["{source_file}"]) to load the existing file - NOT new_file()!
- Navigate to existing packages using get_ARPackage("PackageName")
- Add new elements to existing packages where appropriate
- DO NOT recreate elements that already exist in the file
- Save with autosarfactory.save() when done
"""

        # Get Domain Knowledge
        domain_knowledge = self.km.search_domain_knowledge(user_input)

        # 1. DECOMPOSITION STEP
        # Break down the request into architectural blocks
        decomposition_prompt = f"""
You are an Expert AUTOSAR Architect.
Analyze the following user requirement and break it down into major architectural blocks.
User Requirement: "{user_input}"

{domain_knowledge}

Identify if this is a "Simple" or "Complex" request.
- Simple: Just creating a few elements (e.g., "Create a CAN cluster").
- Complex: Involves multiple layers, signal-to-service mapping, full ECU configuration, or many dependencies.

If Complex, list the major subsystems that need to be built (e.g., "Communication Layer", "Application Layer", "Service Layer", "DataType Definition").

Return a JSON object:
{{
  "complexity": "Simple" or "Complex",
  "blocks": ["Block 1", "Block 2", ...]
}}
"""
        try:
            resp = self.model.generate_content(decomposition_prompt)
            decomp = json.loads(self._clean_json(resp.text))
            complexity = decomp.get("complexity", "Simple")
        except:
            complexity = "Simple" # Fallback

        # 2. DETAILED PLANNING STEP
        # Adjust prompt based on complexity
        if complexity == "Complex":
            planning_instruction = """
THIS IS A COMPLEX REQUEST. YOU MUST GENERATE A "HUGE" AND DETAILED PLAN.
DO NOT SIMPLIFY. BREAK DOWN EVERY SINGLE ELEMENT.

For "Signal to Service" or similar complex scenarios, you must include:
1. Service Interface & Service Instance (Provided/Required)
2. Ethernet/CAN Cluster & Physical Channel
3. Socket Adaptor / SoAd Config (if Ethernet) or CanTp (if CAN)
4. PDU Definition (ISignalIPdu) & Mapping to Frame
5. Signal Definition (ISignal) & Mapping to PDU
6. SOME/IP Transformation Props (if applicable)
7. Application Component & Ports
8. Port-to-Service Mapping
"""
        else:
            planning_instruction = "Generate a standard detailed checklist."

        prompt = f"""
You are an AUTOSAR Architecture Planner with deep knowledge of the autosarfactory library.
Your goal is to create a precise, step-by-step checklist that will guide code generation.

User Requirement:
"{user_input}"

{domain_knowledge}

{edit_section}
{ELEMENT_DEPENDENCIES}

{planning_instruction}

PLANNING RULES:
1. Follow the dependency order above - elements must be created in the right sequence
2. Be explicit about EVERY element that needs to be created
3. Include specific technical details from the user's requirements:
   - Baudrate values (e.g., 500000 for 500kbps)
   - CAN IDs in hex (e.g., 0x100, 0x200)
   - Frame lengths/DLC (1-8 bytes for standard CAN)
   - Signal bit lengths and start positions
   - Element names as specified by user
4. For signal routing between frames, include:
   - Signal creation
   - Mapping to source (Rx) PDU
   - Mapping to destination (Tx) PDU
   - PDU-to-frame mappings for both frames
5. Include ARPackage creation for organization
6. Always end with "Save ARXML file"

Output Format:
Return ONLY a JSON object with this structure:
{{
  "description": "Brief summary of what will be created",
  "checklist": [
    "Step 1: Create ARXML file with root ARPackage",
    "Step 2: Create sub-packages (Communication, System, etc.)",
    "Step 3: ...",
    ...
    "Step N: Save ARXML file"
  ]
}}

IMPORTANT: Each step should be specific and actionable. Include actual values from the user's requirements.

Example for "CAN cluster with 500kbps and frame 0x123":
{{
  "description": "Create CAN cluster with frame",
  "checklist": [
    "Step 1: Create ARXML file with root ARPackage 'System'",
    "Step 2: Create sub-packages: Communication, SystemConfig",
    "Step 3: Create CanCluster 'HS_CAN'",
    "Step 4: Create CanClusterVariant 'HS_CAN_Variant'",
    "Step 5: Configure baudrate to 500000 via CanClusterConfig",
    "Step 6: Create CanPhysicalChannel 'HS_CAN_Channel'",
    "Step 7: Create CanFrame with frameLength 8 bytes",
    "Step 8: Create CanFrameTriggering with identifier 0x123",
    "Step 9: Link frame to triggering via FrameRef",
    "Step 10: Save ARXML file"
  ]
}}

Now create a detailed plan for the user's requirement:
"""
        response = self.model.generate_content(prompt)
        text = response.text
        return self._parse_response(text)

    def _clean_json(self, text):
        if "```json" in text:
            return text.split("```json")[1].split("```")[0]
        elif "```" in text:
            return text.split("```")[1].split("```")[0]
        return text

    def _parse_response(self, text):
        text = self._clean_json(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "description": "Failed to parse plan",
                "checklist": ["Error parsing LLM output", text]
            }

if __name__ == "__main__":
    planner = Planner()
    # Test with a complex request
    plan = planner.create_plan("Create a Service Oriented Architecture with a Sensor SWC sending data to a Service via SOME/IP.")
    print(json.dumps(plan, indent=2))
