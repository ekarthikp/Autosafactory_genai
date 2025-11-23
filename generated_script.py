import autosarfactory.autosarfactory as autosarfactory
import sys

# Define the output file name
OUTPUT_FILE = "output.arxml"

# Step 1: Create ARXML file with a root ARPackage 'AUTOSAR'
# Using CREATE MODE with new_file()
try:
    root_pkg = autosarfactory.new_file(OUTPUT_FILE, defaultArPackage="AUTOSAR", overWrite=True)
    print(f"Step 1: Successfully created ARXML file '{OUTPUT_FILE}' with root package 'AUTOSAR'.")
except Exception as e:
    print(f"Error in Step 1: {e}")
    sys.exit(1)

# Step 2: Create sub-packages 'DataTypes', 'Interfaces', 'Components', 'Communication', and 'System'
data_types_pkg = root_pkg.new_ARPackage("DataTypes")
interfaces_pkg = root_pkg.new_ARPackage("Interfaces")
components_pkg = root_pkg.new_ARPackage("Components")
communication_pkg = root_pkg.new_ARPackage("Communication")
system_pkg = root_pkg.new_ARPackage("System")
print("Step 2: Successfully created sub-packages.")

# Step 3: In 'DataTypes', create SwBaseType 'uint8_t' for an 8-bit unsigned integer
sbt_uint8 = data_types_pkg.new_SwBaseType("uint8_t")
sbt_uint8_def = sbt_uint8.new_BaseTypeDirectDefinition()
sbt_uint8_def.set_baseTypeSize(8)
sbt_uint8_def.set_baseTypeEncoding("NONE")
print("Step 3: Created SwBaseType 'uint8_t'.")

# Step 4: In 'DataTypes', create ImplementationDataType 'Idt_SignalValue' and link it to SwBaseType 'uint8_t' via SwDataDefProps
idt_signal_value = data_types_pkg.new_ImplementationDataType("Idt_SignalValue")
idt_signal_value.set_category("VALUE")
sw_data_def_props = idt_signal_value.new_SwDataDefProps()
sw_props_variant = sw_data_def_props.new_SwDataDefPropsVariant()
sw_props_variant.set_baseType(sbt_uint8)
print("Step 4: Created ImplementationDataType 'Idt_SignalValue' and linked to 'uint8_t'.")

# Step 5: In 'Communication', create CanCluster 'CAN_Cluster' with a baudrate of 500000
can_cluster = communication_pkg.new_CanCluster("CAN_Cluster")
can_cluster_variant = can_cluster.new_CanClusterVariant("CAN_Cluster_Variant")
can_cluster_variant.set_baudrate(500000)
print("Step 5: Created CanCluster 'CAN_Cluster' with a 500kbps baudrate.")

# Step 6: In 'Communication', create CanPhysicalChannel 'CAN_Channel' and associate it with the cluster
can_channel = can_cluster_variant.new_CanPhysicalChannel("CAN_Channel")
print("Step 6: Created CanPhysicalChannel 'CAN_Channel'.")

# Step 7: In 'Communication', create CanFrame 'Frame_SignalIn' with a frameLength of 1 byte
frame_signal_in = communication_pkg.new_CanFrame("Frame_SignalIn")
frame_signal_in.set_frameLength(1)
print("Step 7: Created CanFrame 'Frame_SignalIn'.")

# Step 8: In 'Communication', create CanFrameTriggering for 'Frame_SignalIn' on 'CAN_Channel' with CAN ID 0x250
frame_trig = can_channel.new_CanFrameTriggering("Frame_SignalIn_Trig")
frame_trig.set_identifier(0x250)
frame_trig.set_frame(frame_signal_in)
print("Step 8: Created CanFrameTriggering with ID 0x250 for the frame.")

# Step 9: In 'Communication', create ISignal 'Sig_ValueIn' with a length of 8 bits
sig_value_in = communication_pkg.new_ISignal("Sig_ValueIn")
sig_value_in.set_length(8)
print("Step 9: Created ISignal 'Sig_ValueIn'.")

# Step 10: In 'Communication', create ISignalIPdu 'Pdu_SignalIn' with a length of 1 byte
pdu_signal_in = communication_pkg.new_ISignalIPdu("Pdu_SignalIn")
pdu_signal_in.set_length(1)
print("Step 10: Created ISignalIPdu 'Pdu_SignalIn'.")

# Step 11: In 'Communication', create ISignalToPduMapping to map 'Sig_ValueIn' to 'Pdu_SignalIn' with a start position of 0
sig_to_pdu_map = pdu_signal_in.new_ISignalToPduMapping("Sig_ValueIn_to_Pdu_SignalIn_Map")
sig_to_pdu_map.set_startPosition(0)
sig_to_pdu_map.set_iSignal(sig_value_in)
sig_to_pdu_map.set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST) # Little-endian
print("Step 11: Mapped ISignal to ISignalIPdu.")

# Step 12: In 'Communication', create PduToFrameMapping to map 'Pdu_SignalIn' to 'Frame_SignalIn' with a start position of 0
pdu_to_frame_map = frame_signal_in.new_PduToFrameMapping("Pdu_SignalIn_to_Frame_SignalIn_Map")
pdu_to_frame_map.set_startPosition(0)
pdu_to_frame_map.set_pdu(pdu_signal_in)
print("Step 12: Mapped ISignalIPdu to CanFrame.")

# Step 13: In 'Interfaces', create ClientServerInterface 'CS_SignalInterface'
cs_interface = interfaces_pkg.new_ClientServerInterface("CS_SignalInterface")
print("Step 13: Created ClientServerInterface 'CS_SignalInterface'.")

# Step 14: In 'CS_SignalInterface', create ClientServerOperation 'SetValue'
op_set_value = cs_interface.new_Operation("SetValue")
print("Step 14: Created ClientServerOperation 'SetValue'.")

# Step 15: In 'SetValue' operation, create an 'IN' direction ArgumentDataPrototype named 'value' and link its type to 'Idt_SignalValue'
arg_value = op_set_value.new_Argument("value")
arg_value.set_direction(autosarfactory.ArgumentDirectionEnum.VALUE_IN)
arg_value.set_type(idt_signal_value)
print("Step 15: Created 'IN' argument 'value' for the operation.")

# Step 16: In 'Components', create ApplicationSwComponentType 'App_SignalProcessor'
app_swc = components_pkg.new_ApplicationSwComponentType("App_SignalProcessor")
print("Step 16: Created ApplicationSwComponentType 'App_SignalProcessor'.")

# Step 17: In 'App_SignalProcessor', create a PPortPrototype 'ppService' and link its provided interface to 'CS_SignalInterface'
pp_service = app_swc.new_PPortPrototype("ppService")
pp_service.set_providedInterface(cs_interface)
print("Step 17: Created PPortPrototype 'ppService' on the application SWC.")

# Step 18: In 'Components', create a CompositionSwComponentType 'TopLevelComposition'
composition = components_pkg.new_CompositionSwComponentType("TopLevelComposition")
print("Step 18: Created CompositionSwComponentType 'TopLevelComposition'.")

# Step 19: In 'TopLevelComposition', create a ComponentPrototype 'SignalProcessor_inst' that instantiates 'App_SignalProcessor'
swc_inst = composition.new_Component("SignalProcessor_inst")
swc_inst.set_type(app_swc)
print("Step 19: Instantiated the application SWC in the composition.")

# Step 20: In 'System', create an EcuInstance 'MyEcu'
ecu_instance = system_pkg.new_EcuInstance("MyEcu")
print("Step 20: Created EcuInstance 'MyEcu'.")

# Step 21: In 'System', create a System and SystemMapping to group system-level connections
system_obj = system_pkg.new_System("TheSystem")
system_mapping = system_obj.new_Mapping("SystemMapping")
print("Step 21: Created System and SystemMapping objects.")

# Step 22: Create the ISignalToServiceMapping in the SystemMapping.
# FIX: The factory method is on the SystemMapping object, not the ARPackage.
sig_to_service_map = system_mapping.new_ISignalToServiceMapping("Sig_To_SetValue_Mapping")
print("Step 22: Created ISignalToServiceMapping in the SystemMapping.")

# Step 23: In 'Sig_To_SetValue_Mapping', set the ISignalRef to point to the signal 'Sig_ValueIn'
sig_to_service_map.set_iSignal(sig_value_in)
print("Step 23: Linked the mapping to the ISignal 'Sig_ValueIn'.")

# Step 24: In 'Sig_To_SetValue_Mapping', set the ClientServerOperationRef to point to the 'SetValue' operation within the context of 'SignalProcessor_inst/ppService'
cs_op_ref = sig_to_service_map.new_ClientServerOperation()
cs_op_ref.set_contextComponent(swc_inst)
cs_op_ref.set_contextPPort(pp_service)
cs_op_ref.set_targetClientServerOperation(op_set_value)
print("Step 24: Linked the mapping to the ClientServerOperation with context.")

# Step 25: In 'Sig_To_SetValue_Mapping', create a ServiceSignalToArgumentMapping to map the signal's value to the 'value' argument of the 'SetValue' operation
arg_mapping = sig_to_service_map.new_ServiceSignalToArgumentMapping()
arg_ref = arg_mapping.new_Argument()
arg_ref.set_contextComponent(swc_inst)
arg_ref.set_contextPPort(pp_service)
arg_ref.set_targetArgumentDataPrototype(arg_value)
print("Step 25: Mapped the signal to the operation's argument.")

# Step 26: Save ARXML file
try:
    autosarfactory.save()
    print(f"\nStep 26: Successfully saved all changes to '{OUTPUT_FILE}'.")
    print("Script finished successfully.")
except Exception as e:
    print(f"Error in Step 26 while saving: {e}")
    sys.exit(1)