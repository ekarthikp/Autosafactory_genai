import autosarfactory.autosarfactory as autosarfactory

print("=== SomeipServiceInstanceToMachineMapping ===")
methods = dir(autosarfactory.SomeipServiceInstanceToMachineMapping)
for m in methods:
    if m.startswith('set_') or m.startswith('new_'):
        print(m)

print("\n=== SynchronousServerCallPoint ===")
methods = dir(autosarfactory.SynchronousServerCallPoint)
for m in methods:
    if m.startswith('set_') or m.startswith('new_'):
        print(m)
