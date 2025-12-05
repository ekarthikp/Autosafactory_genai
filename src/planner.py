import json
from src.utils import get_llm_model
from src.knowledge_manager import KnowledgeManager
from src.rag_tps import TPSKnowledgeBase

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
        self.tps_kb = None
        try:
            self.tps_kb = TPSKnowledgeBase()
        except Exception as e:
            print(f"Warning: Could not initialize TPS Knowledge Base: {e}")

    def create_plan(self, user_input, edit_context=None):
        """
        Generates a structured checklist plan from user input with API awareness.
        OPTIMIZED: Single unified LLM call instead of separate decomposition + planning calls.
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
- Navigate to existing packages using iteration (get_arPackages(), get_elements())
- Add new elements to existing packages where appropriate
- DO NOT recreate elements that already exist in the file
- Save with autosarfactory.save() when done
"""

        # Get Domain Knowledge
        domain_knowledge = self.km.search_domain_knowledge(user_input)

        # Get TPS Context (RAG)
        tps_context = ""
        if self.tps_kb:
            try:
                tps_context = self.tps_kb.query(user_input)
                tps_context = f"\nRELEVANT AUTOSAR SPECIFICATION (TPS):\n{tps_context}\n"
            except Exception as e:
                print(f"Warning: TPS RAG query failed: {e}")

        # UNIFIED PLANNING PROMPT - single LLM call instead of two
        prompt = f"""
You are an Expert AUTOSAR Architecture Planner with deep knowledge of the autosarfactory library.
Your goal is to create a precise, step-by-step checklist that will guide code generation.

User Requirement:
"{user_input}"

{domain_knowledge}
{tps_context}

{edit_section}

AUTOSAR ELEMENT CREATION ORDER (Follow this dependency order!):
1. FILE AND PACKAGES: new_file() or read(), then ARPackages
2. DATA TYPES (if needed): SwBaseType -> ImplementationDataType
3. CAN/ETHERNET CLUSTER: Cluster -> Variant -> PhysicalChannel
4. FRAMES: CanFrame with frameLength
5. SIGNALS & PDUs: ISignal, ISignalIPdu, mappings
6. ECU (if needed): EcuInstance
7. INTERFACES: SenderReceiverInterface with DataElement
8. SOFTWARE COMPONENTS: ApplicationSwComponentType with ports
9. BEHAVIOR: InternalBehavior -> Runnable -> TimingEvent
10. SAVE: autosarfactory.save()

COMPLEXITY DETECTION:
- If this involves multiple layers (e.g., signal-to-service, full ECU config, SOME/IP), create a DETAILED plan with all subsystems.
- If this is simple (e.g., just a CAN cluster), keep the plan focused but complete.

PLANNING RULES:
1. Follow the dependency order above - elements must be created in the right sequence
2. Be explicit about EVERY element that needs to be created
3. Include specific technical details from the user's requirements:
   - Baudrate values (e.g., 500000 for 500kbps)
   - CAN IDs in hex (e.g., 0x100, 0x200)
   - Frame lengths/DLC (1-8 bytes for standard CAN)
   - Signal bit lengths and start positions
   - Element names as specified by user
4. Include ARPackage creation for organization
5. Always end with "Save ARXML file"

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
