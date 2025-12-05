import inspect
import json
import os
import sys
from collections import defaultdict

# Add parent directory to path to import autosarfactory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import autosarfactory.autosarfactory as autosarfactory
except ImportError:
    print("Could not import autosarfactory. Make sure it's in the python path.")
    # Do not exit, just let it fail later or raise ImportError
    autosarfactory = None

def build_knowledge_graph():
    """
    Analyzes autosarfactory classes and builds a dependency graph.
    """
    if autosarfactory is None:
        raise ImportError("Could not import autosarfactory module.")

    print("Analyzing autosarfactory classes...")
    
    classes = {}
    
    # 1. Identify all classes
    for name, obj in inspect.getmembers(autosarfactory):
        if inspect.isclass(obj) and obj.__module__.startswith('autosarfactory'):
            classes[name] = {
                'name': name,
                'bases': [b.__name__ for b in obj.__bases__ if b.__module__.startswith('autosarfactory')],
                'methods': {},
                'created_by': [], # Classes that have a new_Name method returning this class
                'references': []  # Classes that this class references (via set_*)
            }

    print(f"Found {len(classes)} classes.")

    # 2. Analyze methods
    for name, info in classes.items():
        cls = getattr(autosarfactory, name)
        
        for method_name, method in inspect.getmembers(cls):
            if not callable(method):
                continue
                
            # Factory methods: new_ChildName
            if method_name.startswith('new_'):
                # Heuristic: new_X usually returns an instance of X
                # But sometimes names differ slightly.
                # We can check return annotation if available, or just guess from name.
                
                # Try to infer return type from name
                child_name = method_name[4:] # remove 'new_'
                
                # Handle some known naming conventions or discrepancies if possible
                # For now, let's assume direct mapping and check if class exists
                if child_name in classes:
                    classes[child_name]['created_by'].append(name)
                    if 'factory_methods' not in info:
                        info['factory_methods'] = []
                    info['factory_methods'].append({'method': method_name, 'return_type': child_name})
                else:
                    # Maybe it returns a Variant or Conditional?
                    # e.g. new_CanClusterVariant -> CanClusterConditional
                    pass

            # Setters: set_Property
            elif method_name.startswith('set_'):
                # Heuristic: set_X(value)
                # We want to know the type of 'value'.
                # Inspect signature
                try:
                    sig = inspect.signature(method)
                    params = list(sig.parameters.values())
                    if len(params) > 0:
                        # Check annotation
                        param = params[0]
                        if param.annotation != inspect.Parameter.empty:
                            # If annotation is a class in autosarfactory
                            ann = param.annotation
                            if isinstance(ann, str):
                                type_name = ann
                            elif hasattr(ann, '__name__'):
                                type_name = ann.__name__
                            else:
                                type_name = str(ann)
                            
                            if type_name in classes:
                                info['references'].append({'method': method_name, 'type': type_name})
                except:
                    pass

    return classes

def save_knowledge_base(kb, filename="src/knowledge_graph.json"):
    with open(filename, 'w') as f:
        json.dump(kb, f, indent=2)
    print(f"Knowledge base saved to {filename}")

if __name__ == "__main__":
    kb = build_knowledge_graph()
    save_knowledge_base(kb)
