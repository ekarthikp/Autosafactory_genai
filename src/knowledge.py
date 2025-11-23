import inspect
import autosarfactory.autosarfactory as autosarfactory

def get_class_by_name(class_name):
    """
    Returns the class object for a given class name.
    """
    if hasattr(autosarfactory, class_name):
        return getattr(autosarfactory, class_name)
    return None

def get_inheritance_chain(cls):
    """
    Returns a list of parent classes for the given class.
    """
    if cls is None:
        return []
    return [c.__name__ for c in cls.__mro__ if c.__module__.startswith('autosarfactory')]

def get_methods(cls):
    """
    Returns a dictionary of methods categorized by type (new, set, get, etc.).
    Includes inherited methods.
    """
    if cls is None:
        return {}

    methods = {
        'new': [],
        'set': [],
        'get': [],
        'add': [],
        'other': []
    }

    # specific exclusions
    exclusions = ['__', 'autosar', 'parent', 'tag', 'text', 'tail']

    for name, member in inspect.getmembers(cls):
        if any(exc in name for exc in exclusions):
            continue

        if not callable(member):
            continue

        # Get signature if possible
        try:
            sig = str(inspect.signature(member))
        except:
            sig = "(...)"

        entry = f"{name}{sig}"

        if name.startswith('new_'):
            methods['new'].append(entry)
        elif name.startswith('set_'):
            methods['set'].append(entry)
        elif name.startswith('get_'):
            methods['get'].append(entry)
        elif name.startswith('add_'):
            methods['add'].append(entry)
        else:
            methods['other'].append(entry)

    return methods

def inspect_class(class_name):
    """
    Returns a formatted string describing the class API.
    """
    cls = get_class_by_name(class_name)
    if not cls:
         return f"Class '{class_name}' not found in autosarfactory."

    # Check if it's a function, not a class
    if inspect.isfunction(cls) or inspect.ismethod(cls):
        sig = str(inspect.signature(cls))
        return f"## Function: {class_name}{sig}\nThis is a module-level function."

    parents = get_inheritance_chain(cls)
    methods = get_methods(cls)

    # Constructor info
    try:
        init_sig = str(inspect.signature(cls.__init__))
    except:
        init_sig = "(...)"

    output = []
    output.append(f"## Class: {class_name}")
    output.append(f"Inheritance: {' -> '.join(parents)}")
    output.append(f"Constructor: {class_name}{init_sig}")

    if methods['new']:
        output.append("\n### Factory Methods (create children):")
        for m in sorted(methods['new']):
            output.append(f"- {m}")

    if methods['set']:
        output.append("\n### Setter Methods (configuration):")
        for m in sorted(methods['set']):
            output.append(f"- {m}")

    # We mostly care about creating and setting for generation

    return "\n".join(output)

def search_classes(query):
    """
    Search for classes matching the query.
    """
    query = query.lower()
    matches = []
    for name in dir(autosarfactory):
        if query in name.lower():
            matches.append(name)
    return matches

if __name__ == "__main__":
    # Test with a few classes
    print(inspect_class("CanCluster"))
    print("\n" + "="*50 + "\n")
    print(inspect_class("new_file"))
