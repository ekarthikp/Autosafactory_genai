"""
Patterns - Re-exports from api_fixes for backward compatibility.
=================================================================
All patterns and API hints are now consolidated in api_fixes.py.
This module provides the same interface as before.

Based on: https://github.com/girishchandranc/autosarfactory
"""

from src.api_fixes import (
    COMPACT_API_RULES as CRITICAL_API_HINTS,
    COMPACT_PATTERNS,
    get_relevant_patterns as get_pattern_for_task,
)


def get_minimal_example():
    """Return a minimal working autosarfactory example."""
    return '''import autosarfactory.autosarfactory as autosarfactory

def main():
    # Create new file
    root_pkg = autosarfactory.new_file("output.arxml", defaultArPackage="Root", overWrite=True)

    # SenderReceiver interface with data element
    sri = root_pkg.new_SenderReceiverInterface("SRI_Speed")
    de = sri.new_DataElement("Speed")  # NOT new_VariableDataPrototype!

    # SWC with ports
    swc = root_pkg.new_ApplicationSwComponentType("SpeedSensor")
    pp = swc.new_PPortPrototype("SpeedOut")
    pp.set_providedInterface(sri)  # Direct setter, NOT new_*Ref()

    # Internal behavior
    beh = swc.new_InternalBehavior("Beh")  # NOT new_SwcInternalBehavior!
    run = beh.new_Runnable("Run_ReadSpeed")  # NOT new_RunnableEntity!
    run.set_symbol("Run_ReadSpeed")
    te = beh.new_TimingEvent("TE_10ms")
    te.set_period(0.01)
    te.set_startOnEvent(run)

    # Data send point
    dsp = run.new_DataSendPoint("DSP_Speed")
    av = dsp.new_AccessedVariable()
    auto_var = av.new_AutosarVariable()
    auto_var.set_portPrototype(pp)
    auto_var.set_targetDataPrototype(de)

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
