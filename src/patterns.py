"""
Common working patterns for AUTOSAR ARXML generation.
These are proven code snippets that the LLM can reference.
"""

# Critical API hints that LLMs often get wrong
CRITICAL_API_HINTS = """
CRITICAL API USAGE NOTES (Verified Against Actual Library):

=== GENERAL RULE: USE DIRECT SETTERS, NOT new_*Ref() ===
The autosarfactory library uses DIRECT SETTERS for references.
DO NOT use patterns like new_*Ref() + set_value() - these methods don't exist!

=== EDIT MODE: READING EXISTING FILES ===

1. READ FUNCTION - Returns tuple (AUTOSAR_root, bool_status):
   autosar_root, status = autosarfactory.read([file_path])  # MUST be a list!
   if not status or not autosar_root:
       raise Exception("Failed to load file")

   WRONG: autosar_root = autosarfactory.read([file])[0]  # Don't index!
   WRONG: autosar_root = autosarfactory.read(file)  # Must be a LIST!
   RIGHT: autosar_root, status = autosarfactory.read([file])  # Unpack tuple!

2. NAVIGATING PACKAGES - Iterate, don't use get_ARPackage():
   WRONG: pkg = root.get_ARPackage("Name")  # Method doesn't exist!
   RIGHT:
     for pkg in root.get_arPackages():
         if pkg.get_shortName() == "Name":
             found_pkg = pkg

3. NAVIGATING ELEMENTS - Iterate, don't use get_*Type():
   WRONG: swc = pkg.get_ApplicationSwComponentType("Name")  # Doesn't exist!
   RIGHT:
     for elem in pkg.get_elements():
         if elem.get_shortName() == "Name":
             found_elem = elem

4. SAVING CHANGES:
   autosarfactory.save()  # Save to original file(s)
   autosarfactory.saveAs("new_file.arxml", overWrite=True)  # Save to new file

   WRONG: autosarfactory.save(root, file)  # This signature doesn't exist!

=== CAN COMMUNICATION ===

1. BAUDRATE:
   - WRONG: can_cluster.set_baudrate(500000)
   - RIGHT: Set baudrate on CanClusterConditional (returned by new_CanClusterVariant):
     can_cluster_variant = can_cluster.new_CanClusterVariant("VariantName")
     can_cluster_variant.set_baudrate(500000)

2. FRAME REFERENCES:
   - RIGHT: frame_trig.set_frame(frame)  # Direct setter!

3. SIGNAL REFERENCES:
   - RIGHT: signal_mapping.set_iSignal(signal)  # Direct setter!

4. PDU REFERENCES:
   - RIGHT: pdu_to_frame.set_pdu(pdu)  # Direct setter!

5. PDU TO FRAME MAPPING LOCATION:
   - WRONG: can_channel.new_PduToFrameMapping("name")
   - RIGHT: frame.new_PduToFrameMapping("MappingName")  # Create on Frame!

6. BYTE ORDER (Use ByteOrderEnum, NOT strings!):
   - WRONG: set_packingByteOrder("MOST-SIGNIFICANT-BYTE-LAST")
   - RIGHT: set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)

=== DATA TYPES ===

7. BASE TYPE REFERENCE (SwDataDefProps):
   - WRONG: sw_data_def_props.new_BaseTypeRef() + set_value()
   - RIGHT: Use SwDataDefPropsVariant with direct setter:
     sw_data_def_props = impl_type.new_SwDataDefProps()
     sw_props_variant = sw_data_def_props.new_SwDataDefPropsVariant()
     sw_props_variant.set_baseType(base_type)  # Direct setter!

8. DATA ELEMENT TYPE REFERENCE (VariableDataPrototype):
   - WRONG: data_element.new_TypeRef() + set_value()
   - RIGHT: data_element.set_type(impl_data_type)  # Direct setter!

=== SOFTWARE COMPONENTS ===

9. PORT INTERFACE REFERENCES:
   - WRONG: r_port.new_RequiredInterfaceRef() + set_value()
   - RIGHT: r_port.set_requiredInterface(interface)  # Direct setter!

   - WRONG: p_port.new_ProvidedInterfaceRef() + set_value()
   - RIGHT: p_port.set_providedInterface(interface)  # Direct setter!

10. INTERNAL BEHAVIOR (CRITICAL - Often wrong!):
    - WRONG: swc.new_SwcInternalBehavior("name")  # This method doesn't exist!
    - RIGHT: swc.new_InternalBehavior("name")  # Returns SwcInternalBehavior

11. GETTING BEHAVIORS AND EVENTS:
    - swc.get_internalBehaviors() returns a LIST, iterate through it
    - behavior.get_events() returns a LIST, iterate through it
    - Filter events by type: type(event).__name__ == "TimingEvent"

12. TIMING EVENT:
    - Create: timing_event = behavior.new_TimingEvent("EventName")
    - Get period: timing_event.get_period()
    - Set period: timing_event.set_period(0.01)  # 10ms

13. RUNNABLE ENTITY:
    - WRONG: internal_behavior.new_RunnableEntity("name")
    - RIGHT: internal_behavior.new_Runnable("name")  # Returns RunnableEntity


14. DATA ACCESS METHODS - CHOOSE THE RIGHT ONE (CRITICAL!):
    
    For P-Port (Provider/Sender):
    - Use new_DataSendPoint("name") for sending data
    - dsp = runnable.new_DataSendPoint("dsp")
    - var = dsp.new_AccessedVariable().new_AutosarVariable()
    - var.set_portPrototype(p_port)
    - var.set_targetDataPrototype(data_element)
    
    For R-Port (Receiver) with DataReceivedEvent:
    - Use new_DataReceivePointByArgument("name")
    - dra = runnable.new_DataReceivePointByArgument("dra")
    - var = dra.new_AccessedVariable().new_AutosarVariable()
    - var.set_portPrototype(r_port)
    - var.set_targetDataPrototype(data_element)
    
    Alternative (less common):
    - new_DataReadAcces("name") - NOTE: ONE 's'!
    - new_DataWriteAcces("name") - NOTE: ONE 's'!

15. DATA RECEIVED EVENT (for R-Port):
    - dre = behavior.new_DataReceivedEvent("DRE_Name")
    - data = dre.new_Data()
    - data.set_contextRPort(r_port)  # NOT set_port!
    - data.set_targetDataElement(data_element)  # Use targetDataElement for events!
    - dre.set_startOnEvent(runnable)

=== COMPOSITION AND CONNECTORS ===

13. SW COMPONENT PROTOTYPE TYPE:
    - WRONG: sw_comp_proto.new_TypeRef() + set_value()
    - RIGHT: sw_comp_proto.set_type(swc_type)  # Direct setter!

14. ASSEMBLY CONNECTOR PORTS:
    - Create provider/requester refs, then use direct setters:
      provider_ref = connector.new_Provider()
      provider_ref.set_targetPPort(p_port)  # Direct setter!

      requester_ref = connector.new_Requester()
      requester_ref.set_targetRPort(r_port)  # Direct setter!

15. COM SPEC DATA ELEMENT:
    - WRONG: com_spec.new_DataElementRef() + set_value()
    - RIGHT: com_spec.set_dataElement(data_element)  # Direct setter!

=== SYSTEM ===

16. SYSTEM AND SYSTEM MAPPING:
    - system = system_pkg.new_System("SystemName")
    - system_mapping = system.new_Mapping("MappingName")

=== METHOD NAME REQUIREMENTS ===

17. These factory methods REQUIRE a name argument:
    - new_ISignalToPduMapping("MappingName")
    - new_PduToFrameMapping("MappingName")
    - new_CanFrameTriggering("TrigName")
    - new_Runnable("RunnableName")
    - new_TimingEvent("EventName")
    - new_DataReadAcces("AccessName")
    - new_DataWriteAcces("AccessName")

18. ETHERNET CLUSTER CONFIGURATION (CRITICAL!):
    - WRONG: ethernet_cluster.new_EthernetPhysicalChannel("Name")
    - RIGHT: Create Variant first, then Channel on the Variant (Conditional):
      eth_cluster = pkg.new_EthernetCluster("EthCluster")
      eth_variant = eth_cluster.new_EthernetClusterVariant("EthVariant") # Returns EthernetClusterConditional
      eth_channel = eth_variant.new_EthernetPhysicalChannel("EthChannel")

19. SW BASE TYPE SIZE:
    - WRONG: new_SwBaseType("uint16", 16)
    - RIGHT: Create SwBaseType, then BaseTypeDirectDefinition, then set size:
      uint16 = pkg.new_SwBaseType("uint16")
      uint16_def = uint16.new_BaseTypeDirectDefinition()
      uint16_def.set_baseTypeSize(16)

20. SENDER-RECEIVER INTERFACE DATA ELEMENT:
    - WRONG: sri.new_VariableDataPrototype("Name")
    - RIGHT: sri.new_DataElement("Name")

21. SERVICE INTERFACE EVENT:
    - WRONG: si.new_ServiceEvent("Name")
    - RIGHT: si.new_Event("Name")

22. SOME/IP NAMING (CRITICAL - Lowercase 'p'!):
    - WRONG: new_SomeIpServiceInterfaceDeployment, new_SomeIpEventDeployment
    - RIGHT: new_SomeipServiceInterfaceDeployment, new_SomeipEventDeployment
    - RIGHT: new_ProvidedSomeipServiceInstance

23. COMPOSITION COMPONENTS:
    - WRONG: new_SwComponentPrototype("Name")
    - WRONG: new_ComponentPrototype("Name")
    - RIGHT: new_Component("Name")  # Returns SwComponentPrototype

24. INSTANCE REFERENCES (e.g., for S2S Translation):
    - WRONG: create_ref_to_translationTarget(...)
    - RIGHT: Create the reference object, then set context/target:
      ref = props.new_TranslationTarget()  # Returns InstanceRef
      ref.set_contextComponent(component_proto)
      ref.set_targetDataPrototype(data_element)

25. EVENT GROUPS:
    - WRONG: si.new_EventGroup("Name")
    - RIGHT: EventGroups are NOT created on ServiceInterface in this version.
             They are typically handled via Deployment or configuration.

26. SYSTEM MAPPING & ECU MAPPING (CRITICAL!):
    - WRONG: sys_map.new_SwcToEcuMapping("Name")  # DOES NOT EXIST!
    - WRONG: sys_map.new_SoftwareComponentToEcuMapping("Name")  # DOES NOT EXIST!
    - RIGHT: The method is new_SwMapping() which returns a SwcToEcuMapping object:
      sys_map = system.new_Mapping("Name")
      swc_map = sys_map.new_SwMapping("Name")  # Returns SwcToEcuMapping!
      swc_map.set_ecuInstance(ecu_instance)
      comp_ref = swc_map.new_Component()  # To reference the SWC prototype

27. CAN FRAME TRIGGERING:
    - WRONG: frame.new_CanFrameTriggering(...)
    - RIGHT: Created on the Physical Channel:
      trig = channel.new_CanFrameTriggering("Name")
      trig.set_frame(frame)

28. SIGNAL TO SERVICE TRANSLATION PROPS (CRITICAL!):
    - WRONG: props_set.new_SignalServiceTranslationProps("Name")  # Note plural!
    - RIGHT: props_set.new_SignalServiceTranslationProp("Name")  # Singular 'Prop'!
      props_set = package.new_SignalServiceTranslationPropsSet("Name")
      props = props_set.new_SignalServiceTranslationProp("Name")  # Singular!
      props.set_composition(composition)
"""

# Working code pattern for CAN cluster setup
CAN_CLUSTER_PATTERN = '''
# === CAN Cluster Setup Pattern ===
# Create CAN cluster with baudrate
can_cluster = system_pkg.new_CanCluster("ClusterName")
# new_CanClusterVariant returns a CanClusterConditional object
can_cluster_variant = can_cluster.new_CanClusterVariant("ClusterName_Variant")

# Set baudrate directly on the CanClusterConditional (returned by new_CanClusterVariant)
can_cluster_variant.set_baudrate(500000)  # e.g., 500 kbps

# Create physical channel
can_channel = can_cluster_variant.new_CanPhysicalChannel("ClusterName_Channel")
'''

# Working code pattern for CAN frame with triggering
CAN_FRAME_PATTERN = '''
# === CAN Frame Pattern ===
# Create frame
frame = communication_pkg.new_CanFrame("FrameName")
frame.set_frameLength(8)  # DLC in bytes (1-8 for standard CAN)

# Create frame triggering on the channel (sets CAN ID)
frame_trig = can_channel.new_CanFrameTriggering("FrameName_Trig")
frame_trig.set_identifier(0x123)  # CAN ID in hex

# Link frame to triggering using direct setter
frame_trig.set_frame(frame)  # Direct setter - no need for new_FrameRef()!
'''

# Working code pattern for signal and PDU mapping
SIGNAL_PDU_PATTERN = '''
# === Signal and PDU Mapping Pattern ===
# Create signal
i_signal = communication_pkg.new_ISignal("SignalName")
i_signal.set_iSignalType(autosarfactory.ISignalTypeEnum.VALUE_PRIMITIVE)
i_signal.set_length(16)  # bits

# Create PDU
ipdu = communication_pkg.new_ISignalIPdu("PduName")
ipdu.set_length(8)  # bytes

# Map signal to PDU
signal_mapping = ipdu.new_ISignalToPduMapping("SignalName_To_Pdu")  # Name required!
signal_mapping.set_startPosition(0)  # Start bit position
# Use ByteOrderEnum for byte order (NOT strings!)
signal_mapping.set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)  # Little Endian

# Link signal using direct setter
signal_mapping.set_iSignal(i_signal)  # Direct setter - no need for new_ISignalRef()!

# Map PDU to Frame (on the FRAME, not the channel!)
pdu_to_frame = frame.new_PduToFrameMapping("Pdu_To_Frame")  # Name required! Create on Frame object!
pdu_to_frame.set_startPosition(0)
pdu_to_frame.set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)

# Link PDU using direct setter
pdu_to_frame.set_pdu(ipdu)  # Direct setter - no need for new_PduRef()!
'''

# Working code pattern for software component (VERIFIED FROM ACTUAL WORKING CODE!)
SWC_PATTERN = '''
# === Software Component Pattern (VERIFIED WORKING!) ===

# Create interface and data element
srIf = interfaces_pkg.new_SenderReceiverInterface('srif1')
vdp = srIf.new_DataElement('de1')  # NOT new_VariableDataPrototype!
vdp.set_type(impl_data_type)  # Direct setter!

# Create software component with P-Port (provider)
asw1 = swcs_pkg.new_ApplicationSwComponentType('asw1')
port1 = asw1.new_PPortPrototype('outPort')
port1.set_providedInterface(srIf)  # Direct setter!

# Create internal behavior
beh1 = asw1.new_InternalBehavior('beh1')  # NOT new_SwcInternalBehavior!

# Create timing event
te1 = beh1.new_TimingEvent('te_5ms')
te1.set_period(0.005)  # 5ms in seconds

# Create runnable
run1 = beh1.new_Runnable('Runnable_1')  # NOT new_RunnableEntity!
run1.set_symbol('Run1')
te1.set_startOnEvent(run1)  # Direct setter!

# DATA SEND POINT (for P-Port) - CORRECT PATTERN!
dsp = run1.new_DataSendPoint('dsp')  # NOT new_DataWriteAcces for P-Port!
var = dsp.new_AccessedVariable().new_AutosarVariable()
var.set_portPrototype(port1)  # Direct setter!
var.set_targetDataPrototype(vdp)  # Use set_targetDataPrototype!

# === R-Port (receiver) pattern ===
asw2 = swcs_pkg.new_ApplicationSwComponentType('asw2')
port2 = asw2.new_RPortPrototype('inPort')
port2.set_requiredInterface(srIf)  # Direct setter!

beh2 = asw2.new_InternalBehavior('beh2')

# Data Received Event - triggers on data arrival
dre = beh2.new_DataReceivedEvent('DRE_Vdp')
data = dre.new_Data()
data.set_contextRPort(port2)  # NOT set_port!
data.set_targetDataElement(vdp)  # Use set_targetDataElement for events!

run2 = beh2.new_Runnable('Runnable_2')
run2.set_symbol('Run2')
dre.set_startOnEvent(run2)

# DATA RECEIVE POINT BY ARGUMENT (for R-Port) - CORRECT PATTERN!
dra = run2.new_DataReceivePointByArgument('dra')  # NOT new_DataReadAcces for R-Port with events!
var_dra = dra.new_AccessedVariable().new_AutosarVariable()
var_dra.set_portPrototype(port2)
var_dra.set_targetDataPrototype(vdp)  # Use set_targetDataPrototype!

# === Composition and Connectors ===
composition = swcs_pkg.new_CompositionSwComponentType('Comp')
asw1_proto = composition.new_Component('asw1_proto')  # NOT new_SwComponentPrototype!
asw2_proto = composition.new_Component('asw2_proto')
asw1_proto.set_type(asw1)  # Direct setter!
asw2_proto.set_type(asw2)

# Assembly connector
conn1 = composition.new_AssemblySwConnector('conn1')
provider = conn1.new_Provider()
provider.set_contextComponent(asw1_proto)
provider.set_targetPPort(port1)  # NOT set_port!
requester = conn1.new_Requester()
requester.set_contextComponent(asw2_proto)
requester.set_targetRPort(port2)  # NOT set_port!
'''

# Working code pattern for data types
DATA_TYPE_PATTERN = '''
# === Data Type Pattern ===
# Create base type
uint16_type = datatypes_pkg.new_SwBaseType("uint16")
uint16_def = uint16_type.new_BaseTypeDirectDefinition()
uint16_def.set_baseTypeSize(16)  # bits
uint16_def.set_baseTypeEncoding("NONE")

# Create implementation data type
impl_uint16 = datatypes_pkg.new_ImplementationDataType("Impl_uint16")
impl_uint16.set_category("VALUE")

# Link to base type through SwDataDefProps - use DIRECT SETTER!
sw_data_def_props = impl_uint16.new_SwDataDefProps()
sw_props_variant = sw_data_def_props.new_SwDataDefPropsVariant()
sw_props_variant.set_baseType(uint16_type)  # Direct setter! NOT new_BaseTypeRef()!
'''

# Complete minimal working example
MINIMAL_EXAMPLE = '''
# === Complete Minimal CAN System Example ===
import autosarfactory.autosarfactory as autosarfactory

# Create file with root package
root_pkg = autosarfactory.new_file("output.arxml", defaultArPackage="System", overWrite=True)

# Create sub-packages
communication_pkg = root_pkg.new_ARPackage("Communication")
system_pkg = root_pkg.new_ARPackage("SystemConfig")

# Create CAN cluster
can_cluster = system_pkg.new_CanCluster("HS_CAN")
# new_CanClusterVariant returns a CanClusterConditional object
can_variant = can_cluster.new_CanClusterVariant("HS_CAN_Variant")

# Set baudrate directly on the CanClusterConditional
can_variant.set_baudrate(500000)

# Create channel
can_channel = can_variant.new_CanPhysicalChannel("HS_CAN_Channel")

# Create frame
frame = communication_pkg.new_CanFrame("MyFrame")
frame.set_frameLength(8)

# Create frame triggering
frame_trig = can_channel.new_CanFrameTriggering("MyFrame_Trig")
frame_trig.set_identifier(0x100)
frame_trig.set_frame(frame)  # Direct setter!

# Create signal
signal = communication_pkg.new_ISignal("MySignal")
signal.set_iSignalType(autosarfactory.ISignalTypeEnum.VALUE_PRIMITIVE)
signal.set_length(8)

# Create PDU
pdu = communication_pkg.new_ISignalIPdu("MyPdu")
pdu.set_length(8)

# Map signal to PDU - use ByteOrderEnum for byte order!
sig_map = pdu.new_ISignalToPduMapping("MySignal_Map")
sig_map.set_startPosition(0)
sig_map.set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)
sig_map.set_iSignal(signal)  # Direct setter!

# Map PDU to frame - create on the FRAME object, not channel!
pdu_map = frame.new_PduToFrameMapping("MyPdu_Map")
pdu_map.set_startPosition(0)
pdu_map.set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)
pdu_map.set_pdu(pdu)  # Direct setter!

# Save
autosarfactory.save()
print("ARXML created successfully!")
'''

def get_all_patterns():
    """Returns all patterns concatenated for inclusion in prompts."""
    return f"""
{CRITICAL_API_HINTS}

WORKING CODE PATTERNS:

{CAN_CLUSTER_PATTERN}

{CAN_FRAME_PATTERN}

{SIGNAL_PDU_PATTERN}

{DATA_TYPE_PATTERN}

{SWC_PATTERN}
"""

def get_minimal_example():
    """Returns the minimal working example."""
    return MINIMAL_EXAMPLE

def get_pattern_for_task(task_keywords, max_patterns=3):
    """
    Returns ONLY the most relevant patterns based on task keywords.
    OPTIMIZED: Limits to top N patterns to reduce prompt token count.
    """
    task_lower = task_keywords.lower()
    
    # Pattern definitions with their trigger keywords
    pattern_configs = [
        {
            'pattern': CAN_CLUSTER_PATTERN,
            'keywords': ['cluster', 'can', 'baudrate', 'channel', 'variant'],
            'name': 'CAN_CLUSTER'
        },
        {
            'pattern': CAN_FRAME_PATTERN,
            'keywords': ['frame', 'triggering', 'dlc', 'framelength', 'identifier'],
            'name': 'CAN_FRAME'
        },
        {
            'pattern': SIGNAL_PDU_PATTERN,
            'keywords': ['signal', 'pdu', 'isignal', 'ipdu', 'mapping', 'byte order'],
            'name': 'SIGNAL_PDU'
        },
        {
            'pattern': SWC_PATTERN,
            'keywords': ['component', 'swc', 'port', 'interface', 'behavior', 'runnable', 'timing'],
            'name': 'SWC'
        },
        {
            'pattern': DATA_TYPE_PATTERN,
            'keywords': ['type', 'datatype', 'basetype', 'uint', 'implementation'],
            'name': 'DATA_TYPE'
        },
    ]
    
    # Score each pattern by keyword overlap
    scored_patterns = []
    for config in pattern_configs:
        score = sum(1 for kw in config['keywords'] if kw in task_lower)
        if score > 0:
            scored_patterns.append((score, config['pattern'], config['name']))
    
    # Sort by score (highest first) and take top N
    scored_patterns.sort(reverse=True)
    selected = scored_patterns[:max_patterns]
    
    if selected:
        pattern_names = [name for _, _, name in selected]
        print(f"   📋 Selected patterns: {', '.join(pattern_names)}")
        patterns_text = "\n".join(pattern for _, pattern, _ in selected)
    else:
        # Fallback: include minimal example if no keywords matched
        patterns_text = MINIMAL_EXAMPLE
    
    # Only include critical hints (condensed version)
    return f"""
CRITICAL API NOTES:
- Use DIRECT SETTERS for references: set_frame(obj), set_iSignal(obj), set_pdu(obj)
- Baudrate: set on CanClusterConditional (returned by new_CanClusterVariant)
- InternalBehavior: swc.new_InternalBehavior() NOT new_SwcInternalBehavior()  
- Runnable: behavior.new_Runnable() NOT new_RunnableEntity()
- DataAccess: new_DataReadAcces (one 's'!), new_DataWriteAcces (one 's'!)
- ByteOrder: use autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST
- PduToFrameMapping: create on FRAME object, not channel

RELEVANT PATTERNS:
{patterns_text}
"""

