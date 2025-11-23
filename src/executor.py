import subprocess
import os
import sys
from lxml import etree

class Executor:
    def run_script(self, script_content, filename="generated_script.py"):
        """
        Saves and runs the python script.
        """
        with open(filename, "w") as f:
            f.write(script_content)

        try:
            # Run the script
            result = subprocess.run(
                [sys.executable, filename],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return False, f"Runtime Error:\n{result.stderr}"

            return True, result.stdout

        except Exception as e:
            return False, str(e)

    def verify_arxml(self, arxml_path, plan):
        """
        Checks if ARXML exists and contains expected elements from the plan.
        """
        if not os.path.exists(arxml_path):
            return False, f"File {arxml_path} was not created."

        try:
            tree = etree.parse(arxml_path)
            root = tree.getroot()
            # Extract namespace
            ns = {'ar': root.nsmap[None]} if None in root.nsmap else {}

            # Heuristic check against plan
            missing_elements = []
            plan_text = str(plan).lower()

            checks = {
                "cluster": "//ar:CAN-CLUSTER",
                "frame": "//ar:CAN-FRAME",
                "signal": "//ar:I-SIGNAL",
                "ecu": "//ar:ECU-INSTANCE",
                "component": "//ar:APPLICATION-SW-COMPONENT-TYPE"
            }

            for keyword, xpath in checks.items():
                if keyword in plan_text:
                    elements = root.xpath(xpath, namespaces=ns)
                    if not elements:
                        missing_elements.append(f"Expected {keyword} but found none in ARXML.")

            if missing_elements:
                return False, "Verification Failed:\n" + "\n".join(missing_elements)

            return True, "ARXML verified successfully."

        except Exception as e:
            return False, f"Invalid ARXML content: {e}"
