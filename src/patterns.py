"""
Patterns - Re-exports from api_fixes for backward compatibility.
=================================================================
All patterns and API hints are now consolidated in api_fixes.py.
This module provides the same interface as before.

Based on: https://github.com/girishchandranc/autosarfactory
Verified against: Examples/create_autosar_basic_communication.py
"""

from src.api_fixes import (
    COMPACT_API_RULES as CRITICAL_API_HINTS,
    COMPACT_PATTERNS,
    get_relevant_patterns as get_pattern_for_task,
)


def get_minimal_example():
    """Return a minimal working autosarfactory example.

    Verified against the real repo example at:
    https://github.com/girishchandranc/autosarfactory/blob/master/Examples/create_autosar_basic_communication.py
    """
    return '''from autosarfactory import autosarfactory

def main():
    # Create new file - returns ARPackage
    root_pkg = autosarfactory.new_file("output.arxml", defaultArPackage="Root", overWrite=True)

    # --- Data Types ---
    types_pkg = root_pkg.new_ARPackage("DataTypes")
    base = types_pkg.new_SwBaseType("uint8")
    base_def = base.new_BaseTypeDirectDefinition()  # no name arg!
    base_def.set_baseTypeSize(8)

    impl = types_pkg.new_ImplementationDataType("Impl_uint8")
    impl.set_category("VALUE")
    props = impl.new_SwDataDefProps()  # no name arg!
    variant = props.new_SwDataDefPropsVariant()  # no name arg!
    variant.set_baseType(base)  # direct setter, NOT new_BaseTypeRef().set_value()

    # --- Interface ---
    iface_pkg = root_pkg.new_ARPackage("Interfaces")
    sri = iface_pkg.new_SenderReceiverInterface("SRI_Speed")
    de = sri.new_DataElement("Speed")  # NOT new_VariableDataPrototype!
    de.set_type(impl)  # direct setter

    # --- SWC with ports ---
    swc_pkg = root_pkg.new_ARPackage("SwComponents")
    swc = swc_pkg.new_ApplicationSwComponentType("SpeedSensor")
    pp = swc.new_PPortPrototype("SpeedOut")
    pp.set_providedInterface(sri)  # direct setter, NOT new_ProvidedInterfaceRef()

    # --- Internal behavior ---
    beh = swc.new_InternalBehavior("Beh")  # NOT new_SwcInternalBehavior!
    run = beh.new_Runnable("Run_ReadSpeed")  # NOT new_RunnableEntity!
    run.set_symbol("Run_ReadSpeed")
    run.set_canBeInvokedConcurrently(True)

    te = beh.new_TimingEvent("TE_10ms")
    te.set_period(0.01)
    te.set_startOnEvent(run)  # direct setter

    # --- Data send point (chained creation) ---
    dsp = run.new_DataSendPoint("DSP_Speed")
    auto_var = dsp.new_AccessedVariable().new_AutosarVariable()  # chaining OK
    auto_var.set_portPrototype(pp)
    auto_var.set_targetDataPrototype(de)

    # Save all files
    autosarfactory.save()
    print("Done!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open("execution_error.log", "w") as f:
            f.write(traceback.format_exc())
        print("Failed. See execution_error.log")
        raise
'''


def get_full_communication_example():
    """Return a more comprehensive example based on the repo's create_autosar_basic_communication.py."""
    return '''from autosarfactory import autosarfactory

def main():
    # === FILE SETUP ===
    datatypes_pkg = autosarfactory.new_file("datatypes.arxml", defaultArPackage="DataTypes", overWrite=True)
    interfaces_pkg = autosarfactory.new_file("interfaces.arxml", defaultArPackage="Interfaces", overWrite=True)
    swc_pkg = autosarfactory.new_file("swcomponents.arxml", defaultArPackage="SwComponents", overWrite=True)

    # === BASE TYPE ===
    base_uint8 = datatypes_pkg.new_SwBaseType("uint8")
    base_def = base_uint8.new_BaseTypeDirectDefinition()
    base_def.set_baseTypeSize(8)

    # === IMPLEMENTATION DATA TYPE ===
    impl_uint8 = datatypes_pkg.new_ImplementationDataType("Impl_uint8")
    impl_uint8.set_category("VALUE")
    props = impl_uint8.new_SwDataDefProps().new_SwDataDefPropsVariant()  # chaining
    props.set_baseType(base_uint8)

    # === COMPU METHOD (linear scaling) ===
    compu = datatypes_pkg.new_CompuMethod("CM_Speed")
    compu.set_category("LINEAR")
    coeffs = compu.new_CompuInternalToPhys().new_CompuScales().new_CompuScale() \\
        .new_CompuScaleRationalFormula().new_CompuRationalCoeffs()  # deep chaining!
    coeffs.new_CompuNumerator().new_V().set_value(1.0)
    coeffs.new_CompuDenominator().new_V().set_value(1.0)

    # === DATA CONSTRAINT ===
    dc = datatypes_pkg.new_DataConstr("DC_Speed")
    rule = dc.new_DataConstrRule()
    phys = rule.new_PhysConstrs()
    phys.set_lowerLimit(0)
    phys.set_upperLimit(255)
    phys.set_lowerLimitType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)
    phys.set_upperLimitType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)

    # === SENDER-RECEIVER INTERFACE ===
    sri = interfaces_pkg.new_SenderReceiverInterface("SRI_Speed")
    de = sri.new_DataElement("Speed")
    de.set_type(impl_uint8)

    # === CLIENT-SERVER INTERFACE ===
    csi = interfaces_pkg.new_ClientServerInterface("CSI_Diag")
    op = csi.new_Operation("ReadDTC")
    arg = op.new_Argument("DTCCode")
    arg.set_type(impl_uint8)

    # === SWC: Sensor ===
    sensor = swc_pkg.new_ApplicationSwComponentType("SpeedSensor")
    pp = sensor.new_PPortPrototype("SpeedOut")
    pp.set_providedInterface(sri)

    beh = sensor.new_InternalBehavior("SensorBeh")
    run = beh.new_Runnable("Run_ReadSpeed")
    run.set_symbol("Run_ReadSpeed")
    te = beh.new_TimingEvent("TE_10ms")
    te.set_period(0.01)
    te.set_startOnEvent(run)

    dsp = run.new_DataSendPoint("DSP_Speed")
    auto_var = dsp.new_AccessedVariable().new_AutosarVariable()
    auto_var.set_portPrototype(pp)
    auto_var.set_targetDataPrototype(de)

    # === SWC: Actuator ===
    actuator = swc_pkg.new_ApplicationSwComponentType("SpeedActuator")
    rp = actuator.new_RPortPrototype("SpeedIn")
    rp.set_requiredInterface(sri)

    beh2 = actuator.new_InternalBehavior("ActuatorBeh")
    run2 = beh2.new_Runnable("Run_ApplySpeed")
    run2.set_symbol("Run_ApplySpeed")
    dre = beh2.new_DataReceivedEvent("DRE_Speed")
    dre.set_startOnEvent(run2)

    dra = run2.new_DataReceivePointByArgument("DRA_Speed")
    auto_var2 = dra.new_AccessedVariable().new_AutosarVariable()
    auto_var2.set_portPrototype(rp)
    auto_var2.set_targetDataPrototype(de)

    # === COMPOSITION ===
    comp = swc_pkg.new_CompositionSwComponentType("TopComposition")
    proto1 = comp.new_Component("SensorProto")
    proto1.set_type(sensor)
    proto2 = comp.new_Component("ActuatorProto")
    proto2.set_type(actuator)

    conn = comp.new_AssemblySwConnector("SensorToActuator")
    prov = conn.new_Provider()
    prov.set_contextComponent(proto1)
    prov.set_targetPPort(pp)
    req = conn.new_Requester()
    req.set_contextComponent(proto2)
    req.set_targetRPort(rp)

    # Save all files
    autosarfactory.save()
    print("Generated 3 ARXML files successfully!")

if __name__ == "__main__":
    main()
'''
