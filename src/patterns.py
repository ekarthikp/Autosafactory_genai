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

14. DATA ACCESS METHODS (note the spelling!):
    - WRONG: runnable.new_DataReadAccess("name")
    - RIGHT: runnable.new_DataReadAcces("name")  # One 's'!
    - Same for new_DataWriteAcces (one 's')

15. DATA ACCESS VARIABLE REFERENCES:
    - For interface data elements (VariableDataPrototype from SenderReceiverInterface):
      accessed_var = data_access.new_AccessedVariable()
      var_ref = accessed_var.new_AutosarVariable()  # For interface data elements!
      var_ref.set_portPrototype(port)  # Direct setter!
      var_ref.set_targetDataPrototype(data_element)  # Direct setter!

    - For implementation data type sub-elements (less common):
      var_ref = accessed_var.new_AutosarVariableInImplDatatype()
      var_ref.set_portPrototype(port)
      var_ref.set_targetDataPrototype(impl_type_element)  # Must be AbstractImplementationDataTypeElement!

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

# Working code pattern for software component
SWC_PATTERN = '''
# === Software Component Pattern ===
# Create interface first
sr_interface = interfaces_pkg.new_SenderReceiverInterface("If_SignalName")
data_element = sr_interface.new_DataElement("DataElementName")

# Set data type using DIRECT SETTER (NOT new_TypeRef()!)
data_element.set_type(impl_data_type)  # Direct setter!

# Create software component
swc = components_pkg.new_ApplicationSwComponentType("ComponentName_SWC")

# Add receiver port (R-Port) - use DIRECT SETTER for interface!
r_port = swc.new_RPortPrototype("RPort_Name")
r_port.set_requiredInterface(sr_interface)  # Direct setter!

# Add provider port (P-Port) - use DIRECT SETTER for interface!
p_port = swc.new_PPortPrototype("PPort_Name")
p_port.set_providedInterface(sr_interface)  # Direct setter!

# Create internal behavior
internal_behavior = swc.new_InternalBehavior("ComponentName_Behavior")

# Add runnable - use new_Runnable, NOT new_RunnableEntity!
runnable = internal_behavior.new_Runnable("RunnableName")
runnable.set_symbol("RunnableSymbol")

# Add timing event
timing_event = internal_behavior.new_TimingEvent("TE_10ms")
timing_event.set_period(0.01)  # 10ms
timing_event.set_startOnEvent(runnable)  # Direct setter!

# Add data access (note: one 's' in DataReadAcces/DataWriteAcces!)
data_read = runnable.new_DataReadAcces("DRA_Name")
accessed_var = data_read.new_AccessedVariable()
# Use new_AutosarVariable for interface data elements (VariableDataPrototype)
var_ref = accessed_var.new_AutosarVariable()
var_ref.set_portPrototype(r_port)  # Direct setter!
var_ref.set_targetDataPrototype(data_element)  # Direct setter!
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

def get_pattern_for_task(task_keywords):
    """Returns relevant patterns based on task keywords."""
    patterns = []
    task_lower = task_keywords.lower()

    if "cluster" in task_lower or "baudrate" in task_lower:
        patterns.append(CAN_CLUSTER_PATTERN)

    if "frame" in task_lower:
        patterns.append(CAN_FRAME_PATTERN)

    if "signal" in task_lower or "pdu" in task_lower:
        patterns.append(SIGNAL_PDU_PATTERN)

    if "component" in task_lower or "swc" in task_lower or "port" in task_lower:
        patterns.append(SWC_PATTERN)

    if "type" in task_lower or "datatype" in task_lower:
        patterns.append(DATA_TYPE_PATTERN)

    # Always include critical hints
    return CRITICAL_API_HINTS + "\n\nRELEVANT PATTERNS:\n" + "\n".join(patterns)
