"""
Dump dir() of classes to file
"""
import autosarfactory.autosarfactory as af

with open("class_dump.txt", "w") as f:
    f.write("=== CompositionSwComponentType ===\n")
    try:
        c = af.CompositionSwComponentType
        for m in dir(c):
            f.write(f"{m}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
        
    f.write("\n=== SignalServiceTranslationEventProps ===\n")
    try:
        c = af.SignalServiceTranslationEventProps
        for m in dir(c):
            f.write(f"{m}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")

    f.write("\n=== SenderReceiverToSignalMapping ===\n")
    try:
        c = af.SenderReceiverToSignalMapping
        for m in dir(c):
            f.write(f"{m}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
