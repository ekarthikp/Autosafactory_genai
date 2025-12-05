import autosarfactory.autosarfactory as autosarfactory
import traceback

def main():
    """
    Main function to generate the AUTOSAR ARXML file based on the plan.
    """
    print("Starting ARXML generation process...")

    # Step 1: Create ARXML file and root ARPackage 'S2S_System'
    root_pkg = autosarfactory.new_file("output.arxml", defaultArPackage="S2S_System", overWrite=True)
    print("Step 1: ARXML file created with root package 'S2S_System'.")

    # Step 2: Create sub-packages for clear organization
    datatypes_pkg = root_pkg.new_ARPackage("DataTypes")
    interfaces_pkg = root_pkg.new_ARPackage("Interfaces")
    components_pkg = root_pkg.new_ARPackage("Components")
    comm_pkg = root_pkg.new_ARPackage("Communication")
    ecu_pkg = root_pkg.new_ARPackage("ECU")
    deployment_pkg = root_pkg.new_ARPackage("Deployment")
    system_pkg = root_pkg.new_ARPackage("System")
    print("Step 2: Sub-packages created.")

    # Step 3: In 'DataTypes' package, create SwBaseType 'uint16' with a BaseTypeSize of 16.
    uint16_type = datatypes_pkg.new_SwBaseType("uint16")
    uint16_def = uint16_type.new_BaseTypeDirectDefinition()
    uint16_def.set_baseTypeSize(16)
    print("Step 3: SwBaseType 'uint16' created.")

    # Step 4: In 'DataTypes' package, create ImplementationDataType 'Idt_VehicleSpeed_kmh'.
    idt_vehicle_speed = datatypes_pkg.new_ImplementationDataType("Idt_VehicleSpeed_kmh")
    idt_vehicle_speed.set_category("VALUE")
    print("Step 4: ImplementationDataType 'Idt_VehicleSpeed_kmh' created.")

    # Step 5: Add SwDataDefProps to 'Idt_VehicleSpeed_kmh' and link it to the 'uint16' SwBaseType.
    sw_data_def_props = idt_vehicle_speed.new_SwDataDefProps()
    sw_props_variant = sw_data_def_props.new_SwDataDefPropsVariant()
    sw_props_variant.set_baseType(uint16_type)
    print("Step 5: SwDataDefProps added and linked to 'uint16'.")

    # Step 6: In 'Communication' package, create CanCluster 'CAN_Cluster_1'.
    can_cluster = comm_pkg.new_CanCluster("CAN_Cluster_1")
    print("Step 6: CanCluster 'CAN_Cluster_1' created.")

    # Step 7: Create a CanClusterVariant which returns a CanClusterConditional for 'CAN_Cluster_1'.
    can_cluster_variant = can_cluster.new_CanClusterVariant("CAN_Cluster_1_Variant")
    print("Step 7: CanClusterVariant created.")

    # Step 8: On the CanClusterConditional, create a CanClusterBaudrateConfig with baudrate set to 500000.
    can_cluster_variant.set_baudrate(500000)
    print("Step 8: Baudrate set to 500000.")

    # Step 9: Create a CanPhysicalChannel 'CAN_Channel_1' on the CanClusterVariant.
    can_channel_1 = can_cluster_variant.new_CanPhysicalChannel("CAN_Channel_1")
    print("Step 9: CanPhysicalChannel 'CAN_Channel_1' created.")

    # Step 10: In 'Communication' package, create ISignal 'ISig_VehicleSpeed' with a length of 16 bits.
    isig_vehicle_speed = comm_pkg.new_ISignal("ISig_VehicleSpeed")
    isig_vehicle_speed.set_length(16)
    print("Step 10: ISignal 'ISig_VehicleSpeed' created.")

    # Step 11: In 'Communication' package, create ISignalIPdu 'IPDU_VehicleSpeed' with a length of 2 bytes.
    ipdu_vehicle_speed = comm_pkg.new_ISignalIPdu("IPDU_VehicleSpeed")
    ipdu_vehicle_speed.set_length(2)
    print("Step 11: ISignalIPdu 'IPDU_VehicleSpeed' created.")

    # Step 12: Create an ISignalToPduMapping within 'IPDU_VehicleSpeed' to map 'ISig_VehicleSpeed' to this PDU.
    sig_to_pdu_map = ipdu_vehicle_speed.new_ISignalToPduMapping("Map_ISig_to_IPDU_VehicleSpeed")
    sig_to_pdu_map.set_iSignal(isig_vehicle_speed)
    sig_to_pdu_map.set_startPosition(0)
    sig_to_pdu_map.set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST) # Little-endian
    print("Step 12: ISignalToPduMapping created with little-endian byte order.")

    # Step 13: In 'Communication' package, create CanFrame 'Frame_VehicleSpeed' with a frameLength of 2.
    frame_vehicle_speed = comm_pkg.new_CanFrame("Frame_VehicleSpeed")
    frame_vehicle_speed.set_frameLength(2)
    print("Step 13: CanFrame 'Frame_VehicleSpeed' created.")

    # Step 14: On 'CAN_Channel_1', create a CanFrameTriggering with identifier 0x101 and link it to 'Frame_VehicleSpeed'.
    frame_triggering = can_channel_1.new_CanFrameTriggering("Trig_Frame_VehicleSpeed")
    frame_triggering.set_identifier(0x101)
    frame_triggering.set_frame(frame_vehicle_speed)
    print("Step 14: CanFrameTriggering created with ID 0x101.")

    # Step 15: On 'CAN_Channel_1', create a PduToFrameMapping to map 'IPDU_VehicleSpeed' to 'Frame_VehicleSpeed' with a startPosition of 0.
    pdu_to_frame_map = frame_vehicle_speed.new_PduToFrameMapping("Map_IPDU_to_Frame_VehicleSpeed")
    pdu_to_frame_map.set_pdu(ipdu_vehicle_speed)
    pdu_to_frame_map.set_startPosition(0)
    print("Step 15: PduToFrameMapping created.")

    # Step 16: In 'Communication' package, create EthernetCluster 'ETH_Cluster_1'.
    eth_cluster = comm_pkg.new_EthernetCluster("ETH_Cluster_1")
    print("Step 16: EthernetCluster 'ETH_Cluster_1' created.")

    # Step 17: Create an EthernetClusterVariant which returns an EthernetClusterConditional for 'ETH_Cluster_1'.
    eth_cluster_variant = eth_cluster.new_EthernetClusterVariant("ETH_Cluster_1_Variant")
    print("Step 17: EthernetClusterVariant created.")

    # Step 18: Create an EthernetPhysicalChannel 'ETH_Channel_1' on the EthernetClusterVariant.
    eth_channel_1 = eth_cluster_variant.new_EthernetPhysicalChannel("ETH_Channel_1")
    print("Step 18: EthernetPhysicalChannel 'ETH_Channel_1' created.")

    # Step 19: In 'Interfaces' package, create SenderReceiverInterface 'SRI_VehicleSpeed' for the CAN signal.
    sri_vehicle_speed = interfaces_pkg.new_SenderReceiverInterface("SRI_VehicleSpeed")
    print("Step 19: SenderReceiverInterface 'SRI_VehicleSpeed' created.")

    # Step 20: Add a DataElementPrototype 'DE_VehicleSpeed' to 'SRI_VehicleSpeed' and set its type reference to 'Idt_VehicleSpeed_kmh'.
    de_vehicle_speed = sri_vehicle_speed.new_DataElement("DE_VehicleSpeed")
    de_vehicle_speed.set_type(idt_vehicle_speed)
    print("Step 20: DataElement 'DE_VehicleSpeed' added to interface.")

    # Step 21: In 'Interfaces' package, create ServiceInterface 'SI_VehicleInfo' for the SOME/IP service.
    si_vehicle_info = interfaces_pkg.new_ServiceInterface("SI_VehicleInfo")
    print("Step 21: ServiceInterface 'SI_VehicleInfo' created.")

    # Step 22: Add an Event 'VehicleSpeedEvent' to 'SI_VehicleInfo' and set its type reference to 'Idt_VehicleSpeed_kmh'.
    vehicle_speed_event = si_vehicle_info.new_Event("VehicleSpeedEvent")
    vehicle_speed_event.set_type(idt_vehicle_speed)
    print("Step 22: Event 'VehicleSpeedEvent' added to service interface.")

    # Step 23: In 'Components' package, create ApplicationSwComponentType 'Sensor_SWC' to represent the signal source.
    sensor_swc = components_pkg.new_ApplicationSwComponentType("Sensor_SWC")
    print("Step 23: ApplicationSwComponentType 'Sensor_SWC' created.")

    # Step 24: Add a PPortPrototype 'ppVehicleSpeed' to 'Sensor_SWC' and link it to 'SRI_VehicleSpeed'.
    pp_vehicle_speed = sensor_swc.new_PPortPrototype("ppVehicleSpeed")
    pp_vehicle_speed.set_providedInterface(sri_vehicle_speed)
    print("Step 24: P-Port 'ppVehicleSpeed' added to Sensor_SWC.")

    # Step 25: In 'Components' package, create ApplicationSwComponentType 'S2S_Gateway_SWC' for the translation.
    s2s_gateway_swc = components_pkg.new_ApplicationSwComponentType("S2S_Gateway_SWC")
    print("Step 25: ApplicationSwComponentType 'S2S_Gateway_SWC' created.")

    # Step 26: Add an RPortPrototype 'rpVehicleSpeed' to 'S2S_Gateway_SWC' and link it to 'SRI_VehicleSpeed'.
    rp_vehicle_speed = s2s_gateway_swc.new_RPortPrototype("rpVehicleSpeed")
    rp_vehicle_speed.set_requiredInterface(sri_vehicle_speed)
    print("Step 26: R-Port 'rpVehicleSpeed' added to S2S_Gateway_SWC.")

    # Step 27: Add a PPortPrototype 'ppVehicleInfo' to 'S2S_Gateway_SWC' and link it to 'SI_VehicleInfo'.
    pp_vehicle_info = s2s_gateway_swc.new_PPortPrototype("ppVehicleInfo")
    pp_vehicle_info.set_providedInterface(si_vehicle_info)
    print("Step 27: P-Port 'ppVehicleInfo' added to S2S_Gateway_SWC.")

    # Step 28: In 'System' package, create CompositionSwComponentType 'S2S_SystemComposition'.
    s2s_composition = system_pkg.new_CompositionSwComponentType("S2S_SystemComposition")
    print("Step 28: CompositionSwComponentType 'S2S_SystemComposition' created.")

    # Step 29: Instantiate 'Sensor_SWC' as a SwComponentPrototype named 'SensorSWC_Proto' inside the composition.
    sensor_swc_proto = s2s_composition.new_Component("SensorSWC_Proto")
    sensor_swc_proto.set_type(sensor_swc)
    print("Step 29: 'Sensor_SWC' instantiated as 'SensorSWC_Proto'.")

    # Step 30: Instantiate 'S2S_Gateway_SWC' as a SwComponentPrototype named 'GatewaySWC_Proto' inside the composition.
    gateway_swc_proto = s2s_composition.new_Component("GatewaySWC_Proto")
    gateway_swc_proto.set_type(s2s_gateway_swc)
    print("Step 30: 'S2S_Gateway_SWC' instantiated as 'GatewaySWC_Proto'.")

    # Step 31: Create an AssemblySwConnector to connect 'SensorSWC_Proto.ppVehicleSpeed' to 'GatewaySWC_Proto.rpVehicleSpeed'.
    assembly_connector = s2s_composition.new_AssemblySwConnector("Conn_Sensor_to_Gateway")
    provider_ref = assembly_connector.new_Provider()
    provider_ref.set_targetPPort(pp_vehicle_speed)
    provider_ref.set_contextComponent(sensor_swc_proto)
    requester_ref = assembly_connector.new_Requester()
    requester_ref.set_targetRPort(rp_vehicle_speed)
    requester_ref.set_contextComponent(gateway_swc_proto)
    print("Step 31: AssemblySwConnector created.")

    # Step 32: On 'S2S_SystemComposition', create SignalServiceTranslationProps 'S2S_Props_VehicleInfo'.
    s2s_props = s2s_composition.new_SignalServiceTranslationProps("S2S_Props_VehicleInfo")
    print("Step 32: SignalServiceTranslationProps created.")
    
    # Step 33: Set the 'serviceControl' attribute of 'S2S_Props_VehicleInfo' to 'TRANSLATION-START'.
    s2s_props.set_serviceControl(autosarfactory.SignalServiceTranslationControlEnum.VALUE_TRANSLATION_START)
    print("Step 33: serviceControl set to TRANSLATION-START.")

    # Step 34: Create SignalServiceTranslationEventProps 'S2S_EventProps_VehicleSpeed' within 'S2S_Props_VehicleInfo'.
    s2s_event_props = s2s_props.new_SignalServiceTranslationEventProps("S2S_EventProps_VehicleSpeed")
    print("Step 34: SignalServiceTranslationEventProps created.")

    # Step 35: Create the 'translationTarget' instance reference for 'S2S_EventProps_VehicleSpeed'. This reference must target the SERVICE EVENT.
    event_target_iref = s2s_event_props.new_TranslationTarget()
    print("Step 35: translationTarget for event created.")

    # Step 36: Set the instance reference context: contextComponent='GatewaySWC_Proto', contextPort='ppVehicleInfo', targetDataPrototype='VehicleSpeedEvent'.
    event_target_iref.set_contextComponent(gateway_swc_proto)
    event_target_iref.set_contextPort(pp_vehicle_info)
    event_target_iref.set_targetDataPrototype(vehicle_speed_event)
    print("Step 36: Event translationTarget context set correctly.")

    # Step 37: Create SignalServiceTranslationElementProps 'S2S_ElementProps_VehicleSpeed' within 'S2S_EventProps_VehicleSpeed'.
    s2s_element_props = s2s_event_props.new_SignalServiceTranslationElementProps("S2S_ElementProps_VehicleSpeed")
    print("Step 37: SignalServiceTranslationElementProps created.")

    # Step 38: Create the 'translationTarget' instance reference for 'S2S_ElementProps_VehicleSpeed'. This reference must target the SIGNAL DATA ELEMENT.
    element_target_iref = s2s_element_props.new_TranslationTarget()
    print("Step 38: translationTarget for element created.")

    # Step 39: Set the instance reference context: contextComponent='GatewaySWC_Proto', contextPort='rpVehicleSpeed', targetDataPrototype='DE_VehicleSpeed'.
    element_target_iref.set_contextComponent(gateway_swc_proto)
    element_target_iref.set_contextPort(rp_vehicle_speed)
    element_target_iref.set_targetDataPrototype(de_vehicle_speed)
    print("Step 39: Element translationTarget context set correctly.")

    # Step 40: In 'ECU' package, create EcuInstance 'SensorECU'.
    sensor_ecu = ecu_pkg.new_EcuInstance("SensorECU")
    print("Step 40: EcuInstance 'SensorECU' created.")

    # Step 41: In 'ECU' package, create EcuInstance 'GatewayECU'.
    gateway_ecu = ecu_pkg.new_EcuInstance("GatewayECU")
    print("Step 41: EcuInstance 'GatewayECU' created.")

    # Step 42: In 'Deployment' package, create SomeipServiceInterfaceDeployment 'Deploy_SI_VehicleInfo' and link it to 'SI_VehicleInfo'.
    deploy_si_vehicle_info = deployment_pkg.new_SomeipServiceInterfaceDeployment("Deploy_SI_VehicleInfo")
    deploy_si_vehicle_info.set_serviceInterface(si_vehicle_info)
    print("Step 42: SomeipServiceInterfaceDeployment created.")

    # Step 43: Set the 'serviceInterfaceId' of 'Deploy_SI_VehicleInfo' to 0x1100.
    deploy_si_vehicle_info.set_serviceInterfaceId(0x1100)
    print("Step 43: ServiceInterfaceId set to 0x1100.")

    # Step 44: Create a SomeipEventDeployment 'Deploy_VehicleSpeedEvent' within 'Deploy_SI_VehicleInfo' and link it to the 'VehicleSpeedEvent'.
    deploy_event = deploy_si_vehicle_info.new_SomeipEventDeployment("Deploy_VehicleSpeedEvent")
    deploy_event.set_event(vehicle_speed_event)
    print("Step 44: SomeipEventDeployment created.")

    # Step 45: Set the 'eventId' of 'Deploy_VehicleSpeedEvent' to 0x8001.
    deploy_event.set_eventId(0x8001)
    print("Step 45: EventId set to 0x8001.")

    # Step 46: On 'GatewayECU', create a ProvidedSomeipServiceInstance 'VehicleInfoService' and link it to 'Deploy_SI_VehicleInfo'.
    provided_service_inst = gateway_ecu.new_ProvidedSomeipServiceInstance("VehicleInfoService")
    provided_service_inst.set_serviceInterfaceDeployment(deploy_si_vehicle_info)
    print("Step 46: ProvidedSomeipServiceInstance created on GatewayECU.")

    # Step 47: Set the 'serviceInstanceId' of 'VehicleInfoService' to 0x0001.
    provided_service_inst.set_serviceInstanceId(0x0001)
    print("Step 47: ServiceInstanceId set to 0x0001.")

    # Step 48: In 'System' package, create the top-level System element named 'TheSystem'.
    the_system = system_pkg.new_System("TheSystem")
    print("Step 48: System element 'TheSystem' created.")

    # Step 49: Set the 'rootSoftwareComposition' of 'TheSystem' to 'S2S_SystemComposition'.
    the_system.set_rootSoftwareComposition(s2s_composition)
    print("Step 49: rootSoftwareComposition linked.")

    # Step 50: Create a SystemMapping 'SysMapping' within 'TheSystem'.
    sys_mapping = the_system.new_Mapping("SysMapping")
    print("Step 50: SystemMapping 'SysMapping' created.")

    # Step 51: Create a SwcToEcuMapping in 'SysMapping' to map 'SensorSWC_Proto' to 'SensorECU'.
    swc_to_ecu_map_sensor = sys_mapping.new_SwcToEcuMapping("Map_SensorSWC_to_SensorECU")
    swc_to_ecu_map_sensor.set_swc(sensor_swc_proto)
    swc_to_ecu_map_sensor.set_ecuInstance(sensor_ecu)
    print("Step 51: SwcToEcuMapping for Sensor created.")

    # Step 52: Create another SwcToEcuMapping in 'SysMapping' to map 'GatewaySWC_Proto' to 'GatewayECU'.
    swc_to_ecu_map_gateway = sys_mapping.new_SwcToEcuMapping("Map_GatewaySWC_to_GatewayECU")
    swc_to_ecu_map_gateway.set_swc(gateway_swc_proto)
    swc_to_ecu_map_gateway.set_ecuInstance(gateway_ecu)
    print("Step 52: SwcToEcuMapping for Gateway created.")

    # Step 53: Save the ARXML file.
    autosarfactory.save()
    print("Step 53: ARXML file 'output.arxml' saved successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open("execution_error.log", "w") as f:
            f.write(traceback.format_exc())
        print(f"Execution failed. See execution_error.log for details.")
        raise e