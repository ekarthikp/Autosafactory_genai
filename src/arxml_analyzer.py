"""
ARXML Analyzer
===============
Parses existing ARXML files to extract element information for editing operations.
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

try:
    from lxml import etree
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False


@dataclass
class ARXMLElement:
    """Represents an element found in an ARXML file."""
    element_type: str  # e.g., "CAN-CLUSTER", "CAN-FRAME", "I-SIGNAL"
    name: str
    path: str  # XPath to the element
    properties: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)


@dataclass
class ARXMLAnalysis:
    """Result of analyzing an ARXML file."""
    file_path: str
    is_valid: bool = False
    error_message: Optional[str] = None

    # Detected elements by category
    packages: List[ARXMLElement] = field(default_factory=list)
    clusters: List[ARXMLElement] = field(default_factory=list)
    frames: List[ARXMLElement] = field(default_factory=list)
    signals: List[ARXMLElement] = field(default_factory=list)
    pdus: List[ARXMLElement] = field(default_factory=list)
    ecus: List[ARXMLElement] = field(default_factory=list)
    components: List[ARXMLElement] = field(default_factory=list)
    interfaces: List[ARXMLElement] = field(default_factory=list)
    data_types: List[ARXMLElement] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get a human-readable summary of the ARXML contents."""
        if not self.is_valid:
            return f"Invalid ARXML: {self.error_message}"

        lines = [f"ARXML Analysis: {self.file_path}"]
        lines.append("=" * 50)

        if self.packages:
            lines.append(f"\nPackages ({len(self.packages)}):")
            for pkg in self.packages[:10]:  # Limit to first 10
                lines.append(f"  - {pkg.name}")
            if len(self.packages) > 10:
                lines.append(f"  ... and {len(self.packages) - 10} more")

        if self.clusters:
            lines.append(f"\nCAN Clusters ({len(self.clusters)}):")
            for elem in self.clusters:
                props = []
                if 'baudrate' in elem.properties:
                    props.append(f"baudrate={elem.properties['baudrate']}")
                if 'type' in elem.properties:
                    props.append(f"type={elem.properties['type']}")
                prop_str = f" ({', '.join(props)})" if props else ""
                lines.append(f"  - {elem.name}{prop_str}")

        if self.frames:
            lines.append(f"\nCAN Frames ({len(self.frames)}):")
            for elem in self.frames[:10]:
                props = []
                if 'frame_length' in elem.properties:
                    props.append(f"DLC={elem.properties['frame_length']}")
                if 'identifier' in elem.properties:
                    props.append(f"ID={elem.properties['identifier']}")
                prop_str = f" ({', '.join(props)})" if props else ""
                lines.append(f"  - {elem.name}{prop_str}")
            if len(self.frames) > 10:
                lines.append(f"  ... and {len(self.frames) - 10} more")

        if self.signals:
            lines.append(f"\nSignals ({len(self.signals)}):")
            for elem in self.signals[:10]:
                props = []
                if 'length' in elem.properties:
                    props.append(f"length={elem.properties['length']} bits")
                prop_str = f" ({', '.join(props)})" if props else ""
                lines.append(f"  - {elem.name}{prop_str}")
            if len(self.signals) > 10:
                lines.append(f"  ... and {len(self.signals) - 10} more")

        if self.pdus:
            lines.append(f"\nPDUs ({len(self.pdus)}):")
            for elem in self.pdus[:10]:
                lines.append(f"  - {elem.name}")
            if len(self.pdus) > 10:
                lines.append(f"  ... and {len(self.pdus) - 10} more")

        if self.ecus:
            lines.append(f"\nECUs ({len(self.ecus)}):")
            for elem in self.ecus:
                lines.append(f"  - {elem.name}")

        if self.components:
            lines.append(f"\nSoftware Components ({len(self.components)}):")
            for elem in self.components[:10]:
                lines.append(f"  - {elem.name} ({elem.properties.get('type', 'Unknown')})")
            if len(self.components) > 10:
                lines.append(f"  ... and {len(self.components) - 10} more")

        if self.interfaces:
            lines.append(f"\nInterfaces ({len(self.interfaces)}):")
            for elem in self.interfaces[:10]:
                lines.append(f"  - {elem.name}")
            if len(self.interfaces) > 10:
                lines.append(f"  ... and {len(self.interfaces) - 10} more")

        return "\n".join(lines)

    def get_existing_names(self) -> Dict[str, List[str]]:
        """Get all existing element names by category."""
        return {
            'packages': [p.name for p in self.packages],
            'clusters': [c.name for c in self.clusters],
            'frames': [f.name for f in self.frames],
            'signals': [s.name for s in self.signals],
            'pdus': [p.name for p in self.pdus],
            'ecus': [e.name for e in self.ecus],
            'components': [c.name for c in self.components],
            'interfaces': [i.name for i in self.interfaces],
        }

    def to_context_prompt(self) -> str:
        """Generate a context prompt for the LLM about existing elements."""
        if not self.is_valid:
            return ""

        lines = ["EXISTING ARXML CONTENT:"]
        lines.append(f"File: {self.file_path}")

        names = self.get_existing_names()

        if names['packages']:
            lines.append(f"\nExisting Packages: {', '.join(names['packages'][:20])}")
        if names['clusters']:
            lines.append(f"Existing CAN Clusters: {', '.join(names['clusters'])}")
        if names['frames']:
            lines.append(f"Existing Frames: {', '.join(names['frames'][:20])}")
        if names['signals']:
            lines.append(f"Existing Signals: {', '.join(names['signals'][:20])}")
        if names['ecus']:
            lines.append(f"Existing ECUs: {', '.join(names['ecus'])}")
        if names['components']:
            lines.append(f"Existing Components: {', '.join(names['components'][:10])}")

        lines.append("\nIMPORTANT: Do NOT recreate existing elements. Add new elements or modify existing ones.")

        return "\n".join(lines)


class ARXMLAnalyzer:
    """
    Analyzes ARXML files to extract structure and element information.
    """

    def __init__(self):
        if not LXML_AVAILABLE:
            raise ImportError("lxml is required for ARXML analysis")

    def analyze(self, file_path: str) -> ARXMLAnalysis:
        """
        Analyze an ARXML file and extract its contents.

        Args:
            file_path: Path to the ARXML file

        Returns:
            ARXMLAnalysis with all detected elements
        """
        result = ARXMLAnalysis(file_path=file_path)

        if not os.path.exists(file_path):
            result.error_message = f"File not found: {file_path}"
            return result

        try:
            tree = etree.parse(file_path)
            root = tree.getroot()

            # Extract namespace
            ns = {'ar': root.nsmap[None]} if None in root.nsmap else {}

            result.is_valid = True

            # Extract packages
            self._extract_packages(root, ns, result)

            # Extract CAN clusters
            self._extract_clusters(root, ns, result)

            # Extract frames
            self._extract_frames(root, ns, result)

            # Extract signals
            self._extract_signals(root, ns, result)

            # Extract PDUs
            self._extract_pdus(root, ns, result)

            # Extract ECUs
            self._extract_ecus(root, ns, result)

            # Extract software components
            self._extract_components(root, ns, result)

            # Extract interfaces
            self._extract_interfaces(root, ns, result)

            # Extract data types
            self._extract_data_types(root, ns, result)

        except etree.XMLSyntaxError as e:
            result.error_message = f"XML syntax error: {e}"
        except Exception as e:
            result.error_message = f"Analysis error: {e}"

        return result

    def _get_short_name(self, element, ns) -> Optional[str]:
        """Extract SHORT-NAME from an element."""
        if ns:
            short_name = element.find('ar:SHORT-NAME', ns)
        else:
            short_name = element.find('.//{*}SHORT-NAME')

        if short_name is not None:
            return short_name.text
        return None

    def _extract_packages(self, root, ns, result: ARXMLAnalysis):
        """Extract AR-PACKAGE elements."""
        xpath = "//ar:AR-PACKAGE" if ns else ".//{*}AR-PACKAGE"
        for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
            if 'AR-PACKAGE' in str(elem.tag):
                name = self._get_short_name(elem, ns)
                if name:
                    result.packages.append(ARXMLElement(
                        element_type="AR-PACKAGE",
                        name=name,
                        path=root.getpath(elem) if hasattr(root, 'getpath') else ""
                    ))

    def _extract_clusters(self, root, ns, result: ARXMLAnalysis):
        """Extract CAN-CLUSTER elements."""
        xpath = "//ar:CAN-CLUSTER" if ns else ".//{*}CAN-CLUSTER"
        for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
            if 'CAN-CLUSTER' in str(elem.tag):
                name = self._get_short_name(elem, ns)
                if name:
                    props = {}
                    # Try to find baudrate
                    baudrate_elem = elem.find('.//ar:BAUDRATE', ns) if ns else elem.find('.//{*}BAUDRATE')
                    if baudrate_elem is not None and baudrate_elem.text:
                        props['baudrate'] = baudrate_elem.text

                    # Check if CAN-FD
                    if 'CAN-FD' in str(elem.tag):
                        props['type'] = 'CAN-FD'
                    else:
                        props['type'] = 'CAN'

                    result.clusters.append(ARXMLElement(
                        element_type="CAN-CLUSTER",
                        name=name,
                        path="",
                        properties=props
                    ))

    def _extract_frames(self, root, ns, result: ARXMLAnalysis):
        """Extract CAN-FRAME elements."""
        xpath = "//ar:CAN-FRAME" if ns else ".//{*}CAN-FRAME"
        for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
            if 'CAN-FRAME' in str(elem.tag):
                name = self._get_short_name(elem, ns)
                if name:
                    props = {}
                    # Frame length
                    length_elem = elem.find('.//ar:FRAME-LENGTH', ns) if ns else elem.find('.//{*}FRAME-LENGTH')
                    if length_elem is not None and length_elem.text:
                        props['frame_length'] = length_elem.text

                    result.frames.append(ARXMLElement(
                        element_type="CAN-FRAME",
                        name=name,
                        path="",
                        properties=props
                    ))

    def _extract_signals(self, root, ns, result: ARXMLAnalysis):
        """Extract I-SIGNAL elements."""
        xpath = "//ar:I-SIGNAL" if ns else ".//{*}I-SIGNAL"
        for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
            if 'I-SIGNAL' in str(elem.tag) and 'I-SIGNAL-' not in str(elem.tag):
                name = self._get_short_name(elem, ns)
                if name:
                    props = {}
                    # Signal length
                    length_elem = elem.find('.//ar:LENGTH', ns) if ns else elem.find('.//{*}LENGTH')
                    if length_elem is not None and length_elem.text:
                        props['length'] = length_elem.text

                    result.signals.append(ARXMLElement(
                        element_type="I-SIGNAL",
                        name=name,
                        path="",
                        properties=props
                    ))

    def _extract_pdus(self, root, ns, result: ARXMLAnalysis):
        """Extract I-SIGNAL-I-PDU elements."""
        xpath = "//ar:I-SIGNAL-I-PDU" if ns else ".//{*}I-SIGNAL-I-PDU"
        for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
            if 'I-SIGNAL-I-PDU' in str(elem.tag):
                name = self._get_short_name(elem, ns)
                if name:
                    props = {}
                    length_elem = elem.find('.//ar:LENGTH', ns) if ns else elem.find('.//{*}LENGTH')
                    if length_elem is not None and length_elem.text:
                        props['length'] = length_elem.text

                    result.pdus.append(ARXMLElement(
                        element_type="I-SIGNAL-I-PDU",
                        name=name,
                        path="",
                        properties=props
                    ))

    def _extract_ecus(self, root, ns, result: ARXMLAnalysis):
        """Extract ECU-INSTANCE elements."""
        xpath = "//ar:ECU-INSTANCE" if ns else ".//{*}ECU-INSTANCE"
        for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
            if 'ECU-INSTANCE' in str(elem.tag):
                name = self._get_short_name(elem, ns)
                if name:
                    result.ecus.append(ARXMLElement(
                        element_type="ECU-INSTANCE",
                        name=name,
                        path=""
                    ))

    def _extract_components(self, root, ns, result: ARXMLAnalysis):
        """Extract software component elements."""
        component_types = [
            ("APPLICATION-SW-COMPONENT-TYPE", "Application"),
            ("SENSOR-ACTUATOR-SW-COMPONENT-TYPE", "SensorActuator"),
            ("COMPOSITION-SW-COMPONENT-TYPE", "Composition"),
            ("SERVICE-SW-COMPONENT-TYPE", "Service"),
        ]

        for tag, comp_type in component_types:
            xpath = f"//ar:{tag}" if ns else f".//{{{tag}}}"
            for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
                if tag in str(elem.tag):
                    name = self._get_short_name(elem, ns)
                    if name:
                        result.components.append(ARXMLElement(
                            element_type=tag,
                            name=name,
                            path="",
                            properties={'type': comp_type}
                        ))

    def _extract_interfaces(self, root, ns, result: ARXMLAnalysis):
        """Extract interface elements."""
        interface_types = [
            "SENDER-RECEIVER-INTERFACE",
            "CLIENT-SERVER-INTERFACE",
            "MODE-SWITCH-INTERFACE",
        ]

        for tag in interface_types:
            xpath = f"//ar:{tag}" if ns else f".//{{{tag}}}"
            for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
                if tag in str(elem.tag):
                    name = self._get_short_name(elem, ns)
                    if name:
                        result.interfaces.append(ARXMLElement(
                            element_type=tag,
                            name=name,
                            path="",
                            properties={'type': tag}
                        ))

    def _extract_data_types(self, root, ns, result: ARXMLAnalysis):
        """Extract data type elements."""
        type_tags = [
            "SW-BASE-TYPE",
            "IMPLEMENTATION-DATA-TYPE",
        ]

        for tag in type_tags:
            xpath = f"//ar:{tag}" if ns else f".//{{{tag}}}"
            for elem in root.xpath(xpath, namespaces=ns) if ns else root.iter():
                if tag in str(elem.tag):
                    name = self._get_short_name(elem, ns)
                    if name:
                        result.data_types.append(ARXMLElement(
                            element_type=tag,
                            name=name,
                            path=""
                        ))


def analyze_arxml(file_path: str) -> ARXMLAnalysis:
    """
    Convenience function to analyze an ARXML file.

    Args:
        file_path: Path to the ARXML file

    Returns:
        ARXMLAnalysis with all detected elements
    """
    analyzer = ARXMLAnalyzer()
    return analyzer.analyze(file_path)


def check_arxml_exists(file_path: str) -> bool:
    """Check if an ARXML file exists and is valid."""
    if not os.path.exists(file_path):
        return False

    try:
        analysis = analyze_arxml(file_path)
        return analysis.is_valid
    except:
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        analysis = analyze_arxml(sys.argv[1])
        print(analysis.get_summary())
    else:
        print("Usage: python arxml_analyzer.py <path_to_arxml>")
