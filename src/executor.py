import subprocess
import os
import sys
from typing import Dict
from lxml import etree

class Executor:
    def _parse_error(self, stderr: str) -> Dict:
        """
        Parse error information from stderr.
        
        Returns:
            Dictionary with structured error info:
                - type: Error type (AttributeError, TypeError, etc.)
                - message: Error message
                - line: Line number
                - traceback: Full traceback
        """
        import re
        
        error_info = {
            "type": "Unknown",
            "message": stderr,
            "line": None,
            "traceback": stderr
        }
        
        # Extract error type
        type_match = re.search(r'(\w+Error):', stderr)
        if type_match:
            error_info["type"] = type_match.group(1)
        
        # Extract line number
        line_match = re.search(r'line (\d+)', stderr)
        if line_match:
            error_info["line"] = int(line_match.group(1))
        
        # Extract just the error message (last line typically)
        lines = stderr.strip().split('\n')
        if lines:
            error_info["message"] = lines[-1]
        
        return error_info
    
    def run_script(self, script_content, filename="generated_script.py", timeout=30):
        """
        Saves and runs the python script.
        
        Args:
            script_content: The Python script to execute
            filename: Output filename for the script
            timeout: Maximum execution time in seconds
            
        Returns:
            Tuple of (success: bool, result: str or Dict)
            - If success: (True, stdout)
            - If failure: (False, error_dict with type, message, line, traceback)
        """
        with open(filename, "w") as f:
            f.write(script_content)

        try:
            # Run the script
            result = subprocess.run(
                [sys.executable, filename],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                # Parse error
                error_info = self._parse_error(result.stderr)
                
                # Write to error log
                error_msg = f"Runtime Error:\n{result.stderr}"
                with open("error_log.txt", "w") as log:
                    log.write(error_msg)
                
                return False, error_info

            return True, result.stdout

        except subprocess.TimeoutExpired:
            error_info = {
                "type": "TimeoutError",
                "message": f"Script execution exceeded {timeout} seconds",
                "line": None,
                "traceback": f"Timeout after {timeout}s"
            }
            return False, error_info
        except Exception as e:
            error_info = {
                "type": type(e).__name__,
                "message": str(e),
                "line": None,
                "traceback": str(e)
            }
            return False, error_info

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
