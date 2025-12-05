import sys
import os
import json
sys.path.append(os.getcwd())
from src.planner import Planner

planner = Planner()
request = "Create a Signal to Service translation where a CAN signal is mapped to a SOME/IP service event."
print(f"Testing Planner with request: {request}")

plan = planner.create_plan(request)
print("\nGenerated Plan Checklist:")
print(json.dumps(plan['checklist'], indent=2))

# Check for translation props
found = False
for step in plan['checklist']:
    if "SignalServiceTranslationProps" in step or "Translation" in step:
        found = True
        break

if found:
    print("\nSUCCESS: SignalServiceTranslationProps found in plan.")
else:
    print("\nFAILURE: SignalServiceTranslationProps NOT found in plan.")
