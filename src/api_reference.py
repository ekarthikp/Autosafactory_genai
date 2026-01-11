# Autosarfactory API Reference - VERIFIED WORKING PATTERNS
# Source: Official autosarfactory test suite

"""
=== CRITICAL API PATTERNS (VERIFIED FROM TESTS) ===

1. READING FILES:
   root, status = autosarfactory.read([file_list])  # Returns tuple!
   if not status or root is None:
       raise Exception("Failed to load")

2. GETTING NODES BY PATH:
   node = autosarfactory.get_node('/Package/Element/Child')

3. CREATING NEW FILE:
   arPackage = autosarfactory.new_file(filePath, overWrite=True, defaultArPackage="PackageName")

4. SAVING:
   autosarfactory.save()  # Save to original files
   autosarfactory.saveAs(mergedFilePath, overWrite=True)  # Save to single merged file

5. REINITIALIZE:
   autosarfactory.reinit()  # Clear all loaded data

6. GET ALL INSTANCES OF A TYPE:
   runnables = autosarfactory.get_all_instances(root, autosarfactory.RunnableEntity)

=== DATA TYPES ===

# SwBaseType
uint8BaseType = baseTypePack.new_SwBaseType('uint8')
baseTypeDef = uint8BaseType.new_BaseTypeDirectDefinition()
baseTypeDef.set_baseTypeEncoding('2C')
baseTypeDef.set_nativeDeclaration('unsigned char')
baseTypeDef.set_memAlignment(8)
baseTypeDef.set_baseTypeSize(16)

# ImplementationDataType
uint8 = implTypePack.new_ImplementationDataType('uint8')
variant = uint8.new_SwDataDefProps().new_SwDataDefPropsVariant()
variant.set_baseType(uint8BaseType)
variant.set_compuMethod(compu1)
variant.set_dataConstr(dataConstr)

# CompuMethod
compu1 = compuPack.new_CompuMethod('cm1')
intoPhy = compu1.new_CompuInternalToPhys()
compuScales = intoPhy.new_CompuScales()

# CompuScale with constant
compuScale = compuScales.new_CompuScale()
compuScale.new_CompuScaleConstantContents().new_CompuConst().new_CompuConstTextContent().set_vt('VALUE_NAME')
upperLimit = compuScale.new_UpperLimit()
upperLimit.set(upperLimitVal)
upperLimit.set_intervalType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)
lowerLimit = compuScale.new_LowerLimit()
lowerLimit.set(lowerLimitVal)
lowerLimit.set_intervalType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)

# CompuMethod with rational coefficients
compu2 = compuPack.new_CompuMethod('cm2')
rationalCoeff = compu2.new_CompuInternalToPhys().new_CompuScales().new_CompuScale().new_CompuScaleRationalFormula().new_CompuRationalCoeffs()
num = rationalCoeff.new_CompuNumerator()
num.new_V().set(100)

# DataConstr
dataConstr = dataConstrPack.new_DataConstr('dc1')
intConstr = dataConstr.new_DataConstrRule().new_InternalConstrs()
dcLowerLimit = intConstr.new_LowerLimit()
dcLowerLimit.set(-128)
dcLowerLimit.set_intervalType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)

=== INTERFACES ===

# SenderReceiverInterface
srIf = ifPack.new_SenderReceiverInterface('srif1')
vdp = srIf.new_DataElement('de1')  # NOT new_VariableDataPrototype!
vdp.set_type(uint8)
vdp.new_NumericalValueSpecification().new_Value().set('1')

# ClientServerInterface
csif = pack.new_ClientServerInterface('csif')
op1 = csif.new_Operation('op1')
arg1 = op1.new_Argument('arg1')
arg1.set_type(autosarfactory.get_node('/DataTypes/ImplTypes/uint8'))

=== SOFTWARE COMPONENTS ===

# ApplicationSwComponentType with P-Port
asw1 = swcPack.new_ApplicationSwComponentType('asw1')
port1 = asw1.new_PPortPrototype('outPort')
port1.set_providedInterface(srIf)  # Direct setter!

# ApplicationSwComponentType with R-Port
asw2 = swcPack.new_ApplicationSwComponentType('asw2')
port2 = asw2.new_RPortPrototype('inPort')
port2.set_requiredInterface(srIf)  # Direct setter!

# PRPortPrototype (Provider-Requirer)
port = swc.new_PRPortPrototype('p1')
port.set_providedRequiredInterface(srIf)

=== INTERNAL BEHAVIOR ===

# Create InternalBehavior (NOT SwcInternalBehavior!)
beh1 = asw1.new_InternalBehavior('beh1')

# TimingEvent
te1 = beh1.new_TimingEvent('te_5ms')
te1.set_period(0.005)  # In seconds!
te1.set_startOnEvent(run1)  # Direct setter to runnable!

# DataReceivedEvent
dre = beh2.new_DataReceivedEvent('DRE_Vdp')
data = dre.new_Data()
data.set_contextRPort(port2)  # NOT set_port!
data.set_targetDataElement(vdp)  # Use targetDataElement for events!
dre.set_startOnEvent(run2)

# Runnable (NOT RunnableEntity!)
run1 = beh1.new_Runnable('Runnable_1')
run1.set_symbol('Run1')
run1.set_canBeInvokedConcurrently(True)

=== DATA ACCESS POINTS ===

# DataSendPoint (for P-Port sending data)
dsp = run1.new_DataSendPoint('dsp')
var = dsp.new_AccessedVariable().new_AutosarVariable()
var.set_portPrototype(port1)  # Direct setter!
var.set_targetDataPrototype(vdp)  # Use targetDataPrototype!

# DataReceivePointByArgument (for R-Port receiving data with events)
dra = run2.new_DataReceivePointByArgument('dra')
var_dra = dra.new_AccessedVariable().new_AutosarVariable()
var_dra.set_portPrototype(port2)
var_dra.set_targetDataPrototype(vdp)

# DataWriteAcces (alternative, note ONE 's'!)
dwa = runnable.new_DataWriteAcces('dwa1')
var = dwa.new_AccessedVariable().new_AutosarVariable()
var.set_portPrototype(port)
var.set_targetDataPrototype(dataElement)

=== COMPOSITION AND CONNECTORS ===

# CompositionSwComponentType
composition = swcPack.new_CompositionSwComponentType('Comp')

# SwComponentPrototype (use new_Component, NOT new_SwComponentPrototype!)
asw1_proto = composition.new_Component('asw1_proto')
asw2_proto = composition.new_Component('asw2_proto')
asw1_proto.set_type(asw1)  # Direct setter!
asw2_proto.set_type(asw2)

# AssemblySwConnector
conn1 = composition.new_AssemblySwConnector('conn1')
provider = conn1.new_Provider()
provider.set_contextComponent(asw1_proto)
provider.set_targetPPort(port1)  # NOT set_port!
requirer = conn1.new_Requester()
requirer.set_contextComponent(asw2_proto)
requirer.set_targetRPort(port2)  # NOT set_port!

=== CAN NETWORK ===

# ISignal
sig1 = signalsPack.new_ISignal('sig1')
sig1.set_systemSignal(syssig1)
sig1.set_length(4)
sig1.set_dataTypePolicy(autosarfactory.DataTypePolicyEnum.VALUE_LEGACY)
sig1.set_iSignalType(autosarfactory.ISignalTypeEnum.VALUE_PRIMITIVE)

# SystemSignal
syssig1 = systemsignalsPack.new_SystemSignal('syssig1')
syssig1.set_dynamicLength(True)

# AdminData
sdg = sig1.new_AdminData().new_Sdg()
sdg.set_gid("12")
sdg.new_Sd().set_value("new_sd")

# CanCluster with Variant (NOT directly on cluster!)
canChannel = pack.new_CanCluster('Can_Cluster_0').new_CanClusterVariant('variant').new_CanPhysicalChannel('Can_channel_0')

# ISignalTriggering
sigTrig = canChannel.new_ISignalTriggering('sigTrig')

# PduTriggering
pduTrig = canChannel.new_PduTriggering('pduTrig')
pduTrig.new_ISignalTriggering().set_iSignalTriggering(sigTrig)

=== ECU AND SYSTEM ===

# EcuInstance
ecu1 = ecuPack.new_EcuInstance('ecu1')
ecu1.set_wakeUpOverBusSupported(True)
ecu1.set_sleepModeSupported(False)

# System
system = sysPack.new_System('CanSystem')

# SystemMapping
sysMapping = system.new_Mapping('Mappings')

# SenderReceiverToSignalMapping
srMapping = sysMapping.new_SenderReceiverToSignalMapping('outportToSig1Mapping')
srMapping.set_systemSignal(syssig1)
mapDe = srMapping.new_DataElement()
mapDe.set_contextPort(port1)
mapDe.set_targetDataPrototype(vdp)

# RootSoftwareComposition
rootComp = system.new_RootSoftwareComposition('rootSwcom')
rootComp.set_softwareComposition(composition)

# SwcToEcuMapping (use new_SwMapping, NOT new_SwcToEcuMapping!)
swctoEcuMp = sysMapping.new_SwMapping('SwcMapping')
swctoEcuMp.set_ecuInstance(ecu1)
swcMap1 = swctoEcuMp.new_Component()
swcMap1.set_contextComposition(rootComp)
swcMap1.add_contextComponent(asw1_proto)  # Use add_ for multiple!

=== DIAGNOSTIC ===

# DiagnosticServiceSwMapping
dswm = pack.new_DiagnosticServiceSwMapping('map1')
dswm.set_diagnosticDataElement(dataElement)

# DiagnosticExtendedDataRecord
dataElement = pack.new_DiagnosticExtendedDataRecord('record').new_RecordElement().new_DataElement('element')

=== ARRAY TYPES (StdCppImplementationDataType) ===

# StdCppImplementationDataType
stdImplementationDataType = typesPackage.new_StdCppImplementationDataType('Array')
symbolProps = stdImplementationDataType.new_Namespace('namespace_ns')
symbolProps.set_symbol('ns')
cppTemplateArgument = stdImplementationDataType.new_TemplateArgument()
positiveIntegerValueVariationPoint = stdImplementationDataType.new_ArraySize()
positiveIntegerValueVariationPoint.set(6)
stdImplementationDataType.set_category('ARRAY')
stdImplementationDataType.set_typeEmitter('TYPE_EMITTER_ARA')

=== NAVIGATION ===

# Get packages from root
root.get_arPackages()  # Returns list of ARPackage

# Get elements from package
package.get_elements()  # Returns list of elements

# Get specific element from package (iterate, don't use get_*)
swc = next((x for x in package.get_elements() if x.name == 'asw1'), None)

# Get parent
parent = element.get_parent()

# Get by path (NOT on loaded elements, use autosarfactory.get_node!)
node = autosarfactory.get_node('/Full/Path/To/Element')

# Get reference as string (useful when target node is missing)
path_str = data_element.get_type_as_string()  # Returns '/DataTypes/ImplTypes/uint8'

# Get nodes that reference this element
referencing_nodes = element.referenced_by  # Returns list

=== REMOVE ELEMENTS ===

# Remove from containment
package.remove_element(swc)

# Remove from reference list
swcEcuMapping.get_components()[0].remove_contextComponent(swcProto)

=== EXPORT ===

# Export specific element to file
swc.export_to_file('path/to/export.arxml', overWrite=True)

# Generic export
autosarfactory.export_to_file(implPack, 'path/to/export.arxml', overWrite=True)
"""
