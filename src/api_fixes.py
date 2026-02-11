"""
Consolidated API Fixes - Single source of truth for all autosarfactory corrections.
====================================================================================
All known LLM hallucinations, method name corrections, and pattern fixes
are defined here. Every other module imports from this file.

Based on: https://github.com/girishchandranc/autosarfactory
"""

import re
from typing import Tuple, List

# ============================================================================
# Known LLM hallucinations: wrong method -> correct method
# ============================================================================

HALLUCINATION_FIXES = {
    # Behavior methods (MOST COMMON!)
    'new_SwcInternalBehavior': 'new_InternalBehavior',
    'new_RunnableEntity': 'new_Runnable',

    # Data access (note the spelling - one 's')
    'new_DataReadAccess': 'new_DataReadAcces',
    'new_DataWriteAccess': 'new_DataWriteAcces',

    # Data elements
    'new_VariableDataPrototype': 'new_DataElement',
    'new_ServiceEvent': 'new_Event',

    # Components
    'new_SwComponentPrototype': 'new_Component',
    'new_ComponentPrototype': 'new_Component',

    # SOME/IP (lowercase 'p' in 'Someip')
    'new_SomeIpServiceInterfaceDeployment': 'new_SomeipServiceInterfaceDeployment',
    'new_SomeIpEventDeployment': 'new_SomeipEventDeployment',
    'new_SomeIpMethodDeployment': 'new_SomeipMethodDeployment',
    'new_SomeIpFieldDeployment': 'new_SomeipFieldDeployment',
    'new_SomeIpClientServerInterfaceDeployment': 'new_SomeipServiceInterfaceDeployment',

    # System mapping
    'new_SwcToEcuMapping': 'new_SwMapping',
    'new_SoftwareComponentToEcuMapping': 'new_SwMapping',

    # Signal service translation (singular not plural)
    'new_SignalServiceTranslationProps': 'new_SignalServiceTranslationProp',

    # Reference setters
    'set_variableDataPrototype': 'set_targetDataPrototype',
    'set_dataPrototype': 'set_targetDataPrototype',
    'set_variablePrototype': 'set_targetDataPrototype',
    'set_communicationCluster': 'set_commController',

    # Port/type references
    'set_typeRef': 'set_type',
    'set_dataType': 'set_type',
    'set_implementationType': 'set_type',

    # Timing
    'new_TimerEvent': 'new_TimingEvent',

    # Ports
    'new_ReceiverPort': 'new_RPortPrototype',
    'new_ProviderPort': 'new_PPortPrototype',
    'new_RequiredPort': 'new_RPortPrototype',
    'new_ProvidedPort': 'new_PPortPrototype',

    # CAN
    'new_CanCommunicationController': 'new_CommunicationController',

    # IPdu
    'new_IPdu': 'new_ISignalIPdu',

    # Import casing
    'from Autosarfactory import': 'from autosarfactory import',
    'import Autosarfactory': 'import autosarfactory',
}


def apply_hallucination_fixes(code: str) -> Tuple[str, List[str]]:
    """Apply all known hallucination fixes to code. Returns (fixed_code, list_of_fixes)."""
    fixes = []
    for wrong, correct in HALLUCINATION_FIXES.items():
        if wrong in code:
            code = code.replace(wrong, correct)
            fixes.append(f"{wrong} -> {correct}")
    return code, fixes


def apply_pattern_fixes(code: str) -> Tuple[str, List[str]]:
    """Apply regex-based pattern fixes. Returns (fixed_code, list_of_fixes)."""
    fixes = []

    # Fix reference patterns: .new_*Ref().set_value(x) -> .set_*(x)
    ref_pattern = r'\.new_(\w+)Ref\(\)\.set_value\(([^)]+)\)'
    def ref_fix(match):
        ref_type = match.group(1)
        value = match.group(2)
        setter = ref_type[0].lower() + ref_type[1:]
        return f'.set_{setter}({value})'

    new_code = re.sub(ref_pattern, ref_fix, code)
    if new_code != code:
        fixes.append("Fixed new_*Ref().set_value() -> set_*()")
        code = new_code

    # Fix save() with non-list arguments (save() accepts optional list of filenames)
    save_match = re.search(r'autosarfactory\.save\(([^)]+)\)', code)
    if save_match:
        arg = save_match.group(1).strip()
        # Only fix if NOT a list arg and NOT a variable - e.g. save(root) or save("file.arxml")
        if not arg.startswith('[') and not arg.startswith('status') and '"' in arg and ',' not in arg:
            # Wrap single filename in list: save("file.arxml") -> save(["file.arxml"])
            code = code.replace(save_match.group(0), f'autosarfactory.save([{arg}])')
            fixes.append("Fixed save() single arg to list")

    # Fix ByteOrder string literals -> enum
    byte_order_fixes = [
        (r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-LAST["\']\)',
         'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)'),
        (r'set_packingByteOrder\(["\']MOST-SIGNIFICANT-BYTE-FIRST["\']\)',
         'set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_FIRST)'),
    ]
    for pattern, replacement in byte_order_fixes:
        new_code = re.sub(pattern, replacement, code)
        if new_code != code:
            fixes.append("Fixed ByteOrder string -> enum")
            code = new_code

    # Fix read() without list
    read_pattern = r'autosarfactory\.read\(([^)\[\]]+)\)'
    match = re.search(read_pattern, code)
    if match and not match.group(1).strip().startswith('['):
        arg = match.group(1).strip()
        code = code.replace(match.group(0), f'autosarfactory.read([{arg}])')
        fixes.append("Fixed read() to use list argument")

    return code, fixes


def apply_all_fixes(code: str) -> Tuple[str, List[str]]:
    """Apply all fixes (hallucination + pattern). Returns (fixed_code, all_fixes)."""
    all_fixes = []

    code, fixes = apply_hallucination_fixes(code)
    all_fixes.extend(fixes)

    code, fixes = apply_pattern_fixes(code)
    all_fixes.extend(fixes)

    return code, all_fixes


# ============================================================================
# Compact API rules for prompt injection (minimal tokens)
# ============================================================================

COMPACT_API_RULES = """CRITICAL API RULES:
1. IMPORT: from autosarfactory import autosarfactory  # or: import autosarfactory.autosarfactory as autosarfactory
2. CREATE: root_pkg = autosarfactory.new_file("out.arxml", defaultArPackage="Root", overWrite=True)
3. READ: root, status = autosarfactory.read(["file.arxml"])  # LIST arg, returns TUPLE
4. SAVE: autosarfactory.save()  # saves ALL files; or save(["specific.arxml"])
   saveAs: autosarfactory.saveAs("merged.arxml", overWrite=True)  # merge all into one
5. REFERENCES USE DIRECT SETTERS - NEVER use new_*Ref().set_value():
   port.set_providedInterface(iface), port.set_requiredInterface(iface)
   frame_trig.set_frame(frame), sig_map.set_iSignal(signal), pdu_map.set_pdu(pdu)
   sw_props_variant.set_baseType(base_type), data_elem.set_type(impl_type)
   sw_comp_proto.set_type(swc_type), com_spec.set_dataElement(elem)
6. FACTORY METHOD NAMES (easy to get wrong):
   swc.new_InternalBehavior(name) NOT new_SwcInternalBehavior
   behavior.new_Runnable(name) NOT new_RunnableEntity
   sri.new_DataElement(name) NOT new_VariableDataPrototype
   composition.new_Component(name) NOT new_SwComponentPrototype
   sys_map.new_SwMapping(name) NOT new_SwcToEcuMapping
   behavior.new_DataReadAcces(name) - ONE 's'!
   behavior.new_DataWriteAcces(name) - ONE 's'!
7. BAUDRATE: set on CanClusterConditional (returned by new_CanClusterVariant)
8. BYTE ORDER: autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST (not string)
9. PDU-TO-FRAME MAPPING: create on FRAME object, not channel
10. FRAME TRIGGERING: create on CHANNEL: channel.new_CanFrameTriggering(name)
11. NAVIGATE: root.get_arPackages(), pkg.get_elements(), autosarfactory.get_node('/Path/Name')
12. SOMEIP: lowercase 'p' -> new_SomeipServiceInterfaceDeployment
13. CHAINING: deep nesting is valid - compu.new_CompuInternalToPhys().new_CompuScales().new_CompuScale()
14. NO-NAME ELEMENTS: some new_* take no name arg: new_SwDataDefProps(), new_CompuScales(), new_BaseTypeDirectDefinition()
15. SET TO NONE to unset: runnable.set_symbol(None), event.set_startOnEvent(None)
16. MULTI-REF: use add_*/remove_* for multi-value refs: mapping.add_contextComponent(proto)
17. ALT CREATION: obj = autosarfactory.TypeName(); obj.set_shortName('n'); parent.add_element(obj)
"""

COMPACT_PATTERNS = {
    "can_cluster": """# CAN Cluster
cluster = pkg.new_CanCluster("Name")
variant = cluster.new_CanClusterVariant("Name_Variant")  # returns CanClusterConditional
variant.set_baudrate(500000)
channel = variant.new_CanPhysicalChannel("Name_Channel")""",

    "can_frame": """# CAN Frame + Triggering
frame = pkg.new_CanFrame("Name")
frame.set_frameLength(8)
trig = channel.new_CanFrameTriggering("Name_Trig")
trig.set_identifier(0x100)
trig.set_frame(frame)  # direct setter""",

    "signal_pdu": """# Signal + PDU mapping
signal = pkg.new_ISignal("Name")
signal.set_iSignalType(autosarfactory.ISignalTypeEnum.VALUE_PRIMITIVE)
signal.set_length(8)
pdu = pkg.new_ISignalIPdu("Name_Pdu")
pdu.set_length(8)
sig_map = pdu.new_ISignalToPduMapping("Map_Name")
sig_map.set_startPosition(0)
sig_map.set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)
sig_map.set_iSignal(signal)
pdu_map = frame.new_PduToFrameMapping("PduMap")  # on FRAME!
pdu_map.set_startPosition(0)
pdu_map.set_packingByteOrder(autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST)
pdu_map.set_pdu(pdu)""",

    "swc": """# SWC with ports and behavior
sri = pkg.new_SenderReceiverInterface('srif')
de = sri.new_DataElement('de')  # NOT new_VariableDataPrototype
de.set_type(impl_type)
swc = pkg.new_ApplicationSwComponentType('swc')
pp = swc.new_PPortPrototype('outPort')
pp.set_providedInterface(sri)
rp = swc.new_RPortPrototype('inPort')
rp.set_requiredInterface(sri)
beh = swc.new_InternalBehavior('beh')  # NOT new_SwcInternalBehavior
te = beh.new_TimingEvent('te')
te.set_period(0.01)
run = beh.new_Runnable('run')  # NOT new_RunnableEntity
run.set_symbol('RunFunc')
te.set_startOnEvent(run)""",

    "data_type": """# Data type
base = pkg.new_SwBaseType("uint16")
base_def = base.new_BaseTypeDirectDefinition()
base_def.set_baseTypeSize(16)
impl = pkg.new_ImplementationDataType("Impl_uint16")
impl.set_category("VALUE")
props = impl.new_SwDataDefProps()
variant = props.new_SwDataDefPropsVariant()
variant.set_baseType(base)  # direct setter""",

    "data_access": """# Data send/receive
dsp = runnable.new_DataSendPoint('dsp')
var = dsp.new_AccessedVariable().new_AutosarVariable()
var.set_portPrototype(p_port)
var.set_targetDataPrototype(data_elem)
dra = runnable.new_DataReceivePointByArgument('dra')
var2 = dra.new_AccessedVariable().new_AutosarVariable()
var2.set_portPrototype(r_port)
var2.set_targetDataPrototype(data_elem)""",

    "composition": """# Composition
comp = pkg.new_CompositionSwComponentType('Comp')
proto1 = comp.new_Component('proto1')  # NOT new_SwComponentPrototype
proto1.set_type(swc1)
proto2 = comp.new_Component('proto2')
proto2.set_type(swc2)
conn = comp.new_AssemblySwConnector('conn')
prov = conn.new_Provider()
prov.set_contextComponent(proto1)
prov.set_targetPPort(p_port)
req = conn.new_Requester()
req.set_contextComponent(proto2)
req.set_targetRPort(r_port)""",

    "edit_mode": """# Edit existing file
root, status = autosarfactory.read(["existing.arxml"])
if not status: raise Exception("Failed to load")
# Navigate by path or iterating
node = autosarfactory.get_node('/PkgName/ElementName')
for pkg in root.get_arPackages():
    for elem in pkg.get_elements():
        if type(elem).__name__ == "ApplicationSwComponentType":
            swc = elem
# Modify, then save
autosarfactory.save()""",

    "compu_method": """# CompuMethod with linear formula
compu = pkg.new_CompuMethod("CM_Speed")
compu.set_category("LINEAR")
# Chain deeply nested elements
coeffs = compu.new_CompuInternalToPhys().new_CompuScales().new_CompuScale().new_CompuScaleRationalFormula().new_CompuRationalCoeffs()
coeffs.new_CompuNumerator().new_V().set_value(1.0)
coeffs.new_CompuDenominator().new_V().set_value(1.0)""",

    "data_constr": """# DataConstr with limits
dc = pkg.new_DataConstr("DC_Speed")
rule = dc.new_DataConstrRule()
phys = rule.new_PhysConstrs()
phys.set_lowerLimit(0)
phys.set_upperLimit(255)
phys.set_lowerLimitType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)
phys.set_upperLimitType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)""",

    "system_mapping": """# System with mapping
sys = pkg.new_System("Sys")
mapping = sys.new_Mapping("Map")
root_comp = sys.new_RootSoftwareComposition("RootSwComp")
root_comp.set_softwareComposition(composition)
swc_map = mapping.new_SwMapping("SwcMap")
swc_map.set_ecuInstance(ecu)
swc_map.add_contextComponent(proto)""",
}


def get_relevant_patterns(task_text: str, max_patterns: int = 3) -> str:
    """Get only the patterns relevant to the task, minimizing tokens."""
    text_lower = task_text.lower()

    PATTERN_KEYWORDS = {
        "can_cluster": ["cluster", "can", "baudrate", "channel"],
        "can_frame": ["frame", "triggering", "dlc", "identifier"],
        "signal_pdu": ["signal", "pdu", "isignal", "mapping", "byte order"],
        "swc": ["component", "swc", "port", "interface", "behavior", "runnable"],
        "data_type": ["type", "datatype", "basetype", "uint", "implementation"],
        "data_access": ["data send", "data receive", "access", "datasendpoint"],
        "composition": ["composition", "connector", "assembly", "prototype"],
        "edit_mode": ["edit", "modify", "existing", "read"],
        "compu_method": ["compu", "linear", "formula", "scaling", "conversion"],
        "data_constr": ["constraint", "limit", "range", "min", "max"],
        "system_mapping": ["system", "ecu", "mapping", "deployment"],
    }

    scored = []
    for key, keywords in PATTERN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scored.append((score, key))

    scored.sort(reverse=True)
    selected = scored[:max_patterns]

    if not selected:
        # Default: include minimal can_cluster example
        selected = [(1, "can_cluster")]

    parts = []
    for _, key in selected:
        parts.append(COMPACT_PATTERNS[key])

    return "\n\n".join(parts)
