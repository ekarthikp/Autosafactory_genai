"""
API Validator - Ensures generated code uses correct autosarfactory APIs
=======================================================================

This module validates generated Python code against the knowledge_graph.json
to ensure only valid API calls are used. It catches errors BEFORE execution.
"""

import re
import json
import os
from typing import List, Dict, Tuple, Optional


class APIValidator:
    """Validates generated code against the autosarfactory API knowledge base."""

    def __init__(self):
        self.kb = self._load_knowledge_base()
        self._build_api_index()

    def _load_knowledge_base(self) -> Dict:
        """Load the knowledge graph."""
        kb_path = os.path.join(os.path.dirname(__file__), "knowledge_graph.json")
        if os.path.exists(kb_path):
            with open(kb_path, 'r') as f:
                return json.load(f)
        return {}

    def _build_api_index(self):
        """Build fast lookup indexes for API validation."""
        self.factory_methods = {}  # class_name -> set of method names
        self.setter_methods = {}   # class_name -> dict of {method: type}
        self.all_classes = set(self.kb.keys())

        for class_name, info in self.kb.items():
            # Index factory methods (new_*)
            factory = set()
            for fm in info.get('factory_methods', []):
                factory.add(fm['method'])
            self.factory_methods[class_name] = factory

            # Index setter methods (set_*)
            setters = {}
            for ref in info.get('references', []):
                setters[ref['method']] = ref.get('type', 'Unknown')
            self.setter_methods[class_name] = setters

    def validate_code(self, code: str) -> Tuple[bool, List[str], List[str]]:
        """
        Validate generated code against the API.

        Returns:
            (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        # Extract API calls from code
        api_calls = self._extract_api_calls(code)

        for call in api_calls:
            var_name = call['variable']
            method = call['method']
            line_num = call['line']

            # Try to infer the type of the variable
            var_type = self._infer_variable_type(code, var_name)

            if var_type:
                # Validate method exists on this type
                valid, error_msg = self._validate_method_on_type(var_type, method)
                if not valid:
                    errors.append(f"Line {line_num}: {error_msg}")
                    # Try to suggest fix
                    suggestion = self._suggest_fix(var_type, method)
                    if suggestion:
                        errors.append(f"  → Suggestion: {suggestion}")
            else:
                # Can't infer type, just warn
                warnings.append(f"Line {line_num}: Cannot infer type of '{var_name}' to validate '{method}'")

        # Check for common anti-patterns
        anti_pattern_errors = self._check_anti_patterns(code)
        errors.extend(anti_pattern_errors)

        is_valid = len(errors) == 0
        return is_valid, errors, warnings

    def _extract_api_calls(self, code: str) -> List[Dict]:
        """Extract all method calls from the code."""
        calls = []
        lines = code.split('\n')

        # Pattern: variable.method(
        pattern = r'(\w+)\.(new_\w+|set_\w+|get_\w+|add_\w+)\s*\('

        for line_num, line in enumerate(lines, 1):
            for match in re.finditer(pattern, line):
                var_name = match.group(1)
                method = match.group(2)
                calls.append({
                    'variable': var_name,
                    'method': method,
                    'line': line_num,
                    'full_line': line.strip()
                })

        return calls

    def _infer_variable_type(self, code: str, var_name: str) -> Optional[str]:
        """
        Try to infer the type of a variable from the code.
        Uses assignment tracking and factory method return types.
        """
        lines = code.split('\n')

        # Pattern 1: Direct assignment from factory method
        # var = something.new_Something(...)
        pattern1 = rf'{var_name}\s*=\s*\w+\.new_(\w+)\s*\('

        for line in lines:
            match = re.search(pattern1, line)
            if match:
                potential_type = match.group(1)
                # Look up what this factory method returns
                for class_name, methods in self.factory_methods.items():
                    if f'new_{potential_type}' in methods:
                        # Find return type
                        for fm in self.kb[class_name].get('factory_methods', []):
                            if fm['method'] == f'new_{potential_type}':
                                return fm['return_type']
                # If not found in KB, assume the type from the method name
                return potential_type

        # Pattern 2: Module-level function
        # var = autosarfactory.new_file(...)
        pattern2 = rf'{var_name}\s*=\s*autosarfactory\.(new_file|read)\s*\('
        for line in lines:
            match = re.search(pattern2, line)
            if match:
                func = match.group(1)
                if func == 'new_file':
                    return 'ARPackage'  # new_file returns root ARPackage
                elif func == 'read':
                    return 'AUTOSAR'  # read returns AUTOSAR root

        # Pattern 3: Type hints in comments or variable names
        # Common convention: can_cluster, swc, interface, etc.
        type_hints = {
            'cluster': 'CanCluster',
            'frame': 'CanFrame',
            'signal': 'ISignal',
            'pdu': 'ISignalIPdu',
            'swc': 'ApplicationSwComponentType',
            'component': 'ApplicationSwComponentType',
            'interface': 'SenderReceiverInterface',
            'port': 'RPortPrototype',
            'behavior': 'SwcInternalBehavior',
            'runnable': 'RunnableEntity',
            'event': 'TimingEvent',
            'channel': 'CanPhysicalChannel',
            'root': 'ARPackage',
            'pkg': 'ARPackage',
            'package': 'ARPackage',
        }

        var_lower = var_name.lower()
        for hint, type_name in type_hints.items():
            if hint in var_lower:
                return type_name

        return None

    def _validate_method_on_type(self, class_name: str, method: str) -> Tuple[bool, str]:
        """Check if a method exists on a class."""
        if class_name not in self.kb:
            return True, ""  # Can't validate unknown types

        # Check factory methods
        if method.startswith('new_'):
            if method in self.factory_methods.get(class_name, set()):
                return True, ""
            else:
                return False, f"'{class_name}' has no factory method '{method}'"

        # Check setter methods
        if method.startswith('set_'):
            if method in self.setter_methods.get(class_name, {}):
                return True, ""
            else:
                return False, f"'{class_name}' has no setter method '{method}'"

        # Check getter methods (less strict, might be inherited)
        if method.startswith('get_'):
            return True, ""  # Assume getters are valid for now

        return True, ""

    def _suggest_fix(self, class_name: str, wrong_method: str) -> Optional[str]:
        """Suggest a correct method name if available."""
        import difflib

        if class_name not in self.kb:
            return None

        # Get all valid methods for this class
        valid_methods = list(self.factory_methods.get(class_name, set())) + \
                       list(self.setter_methods.get(class_name, {}).keys())

        # Find close matches
        matches = difflib.get_close_matches(wrong_method, valid_methods, n=1, cutoff=0.6)
        if matches:
            return f"Use '{matches[0]}' instead of '{wrong_method}'"

        # Check for common mistakes
        common_fixes = {
            'new_SwcInternalBehavior': 'new_InternalBehavior',
            'new_RunnableEntity': 'new_Runnable',
            'new_DataReadAccess': 'new_DataReadAcces',
            'new_DataWriteAccess': 'new_DataWriteAcces',
            'new_VariableDataPrototype': 'new_DataElement',
        }

        if wrong_method in common_fixes:
            return f"Use '{common_fixes[wrong_method]}' instead"

        return None

    def _check_anti_patterns(self, code: str) -> List[str]:
        """Check for known anti-patterns in the generated code."""
        errors = []

        # Anti-pattern 1: Using new_*Ref().set_value() instead of direct setters
        ref_pattern = r'\.new_(\w+)Ref\(\)\.set_value\('
        if re.search(ref_pattern, code):
            errors.append("Anti-pattern: Using new_*Ref().set_value() - Use direct setters like set_frame(), set_iSignal() instead")

        # Anti-pattern 2: Passing string to ByteOrder methods
        if re.search(r'set_packingByteOrder\(["\']', code):
            errors.append("Anti-pattern: Using string for ByteOrder - Use autosarfactory.ByteOrderEnum.VALUE_MOST_SIGNIFICANT_BYTE_LAST instead")

        # Anti-pattern 3: save() with parameters
        if re.search(r'autosarfactory\.save\([^)]+\)', code):
            errors.append("Anti-pattern: save() takes no parameters - Use autosarfactory.save() or autosarfactory.saveAs(filename)")

        # Anti-pattern 4: Missing error handling
        if 'try:' not in code or 'except' not in code:
            errors.append("Warning: No error handling - Consider adding try/except block")

        return errors

    def get_api_signature(self, class_name: str, method: str) -> Optional[str]:
        """Get the precise API signature for a method."""
        if class_name not in self.kb:
            return None

        info = self.kb[class_name]

        # Search in factory methods
        for fm in info.get('factory_methods', []):
            if fm['method'] == method:
                return_type = fm.get('return_type', 'Unknown')
                return f"{class_name}.{method}(name: str) -> {return_type}"

        # Search in references (setters)
        for ref in info.get('references', []):
            if ref['method'] == method:
                param_type = ref.get('type', 'Unknown')
                return f"{class_name}.{method}({param_type})"

        return None

    def get_all_methods_for_class(self, class_name: str) -> Dict[str, List[str]]:
        """Get all available methods for a class."""
        if class_name not in self.kb:
            return {'factory': [], 'setters': [], 'getters': []}

        info = self.kb[class_name]

        factory = [fm['method'] for fm in info.get('factory_methods', [])]
        setters = [ref['method'] for ref in info.get('references', [])]

        return {
            'factory': factory,
            'setters': setters,
            'getters': []  # Could be extracted but not critical
        }

    def generate_api_context_for_plan(self, plan: Dict) -> str:
        """
        Generate a focused API context based on the plan.
        This is more precise than the current approach.
        """
        from src.knowledge_manager import KnowledgeManager

        km = KnowledgeManager()

        # Extract keywords from plan
        plan_text = str(plan).lower()

        # Identify relevant classes
        relevant_classes = set()

        # Keyword-based class identification (comprehensive protocol support)
        keyword_map = {
            # CAN
            'can': ['CanCluster', 'CanClusterVariant', 'CanFrame', 'CanPhysicalChannel'],
            'canfd': ['CanControllerFdConfiguration', 'CanControllerFdConfigurationRequirements'],
            'can-fd': ['CanControllerFdConfiguration'],

            # LIN
            'lin': ['LinCluster', 'LinClusterConditional', 'LinPhysicalChannel', 'LinFrame',
                   'LinUnconditionalFrame', 'LinMaster', 'LinSlave', 'LinScheduleTable'],

            # Ethernet & SOME/IP
            'ethernet': ['EthernetCluster', 'EthernetClusterConditional', 'EthernetPhysicalChannel',
                        'EthernetFrame', 'EthernetFrameTriggering'],
            'someip': ['SomeipServiceInterface', 'ProvidedSomeipServiceInstance',
                      'RequiredSomeipServiceInstance', 'SomeipServiceInterfaceDeployment'],
            'some/ip': ['SomeipServiceInterface', 'ProvidedSomeipServiceInstance'],

            # FlexRay
            'flexray': ['FlexrayCluster', 'FlexrayClusterConditional', 'FlexrayPhysicalChannel',
                       'FlexrayFrame', 'FlexrayFrameTriggering'],

            # Signal-to-Service Translation
            'translation': ['SignalServiceTranslationProps', 'SignalServiceTranslationEventProps',
                          'ServiceInstanceToSignalMapping'],
            'signal to service': ['SignalServiceTranslationProps', 'ServiceInstanceToSignalMapping'],
            'service to signal': ['SignalServiceTranslationProps', 'ServiceInstanceToSignalMapping'],

            # Common Elements
            'signal': ['ISignal', 'ISignalIPdu', 'ISignalToPduMapping'],
            'component': ['ApplicationSwComponentType', 'SwcInternalBehavior'],
            'port': ['RPortPrototype', 'PPortPrototype'],
            'interface': ['SenderReceiverInterface', 'DataElement'],
            'datatype': ['SwBaseType', 'ImplementationDataType'],
            'runnable': ['RunnableEntity', 'TimingEvent'],
            'behavior': ['SwcInternalBehavior'],
        }

        for keyword, classes in keyword_map.items():
            if keyword in plan_text:
                relevant_classes.update(classes)

        # Always include core classes
        relevant_classes.update(['ARPackage', 'AUTOSAR'])

        # Generate precise API documentation
        output = ["=" * 80]
        output.append("PRECISE API SIGNATURES FOR YOUR PLAN")
        output.append("=" * 80)
        output.append("")

        for class_name in sorted(relevant_classes):
            if class_name not in self.kb:
                continue

            info = self.kb[class_name]
            output.append(f"## {class_name}")

            if info.get('bases'):
                output.append(f"   Inherits from: {' -> '.join(info['bases'])}")

            # Factory methods with precise signatures
            if info.get('factory_methods'):
                output.append("   Factory Methods:")
                for fm in info['factory_methods'][:10]:  # Limit to most common
                    method = fm['method']
                    ret_type = fm['return_type']
                    output.append(f"      {method}(name: str) -> {ret_type}")

            # Setter methods with parameter types
            if info.get('references'):
                output.append("   Setter Methods:")
                for ref in info['references'][:15]:  # Limit to most common
                    method = ref['method']
                    param_type = ref.get('type', 'value')
                    output.append(f"      {method}({param_type})")

            output.append("")

        return "\n".join(output)


# Singleton instance
_validator_instance = None

def get_api_validator() -> APIValidator:
    """Get the singleton API validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = APIValidator()
    return _validator_instance
