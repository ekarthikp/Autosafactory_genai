"""
AST Indexer - Complete Symbol Table Extraction for Autosarfactory
==================================================================
Extracts all classes, methods, signatures from the autosarfactory module
using Python's inspect module. Provides ground truth for constrained generation.

Features:
- Full signature extraction with type hints
- Abstract class detection
- Hierarchy chain analysis
- Lazy caching with JSON persistence
"""

import os
import json
import inspect
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
from datetime import datetime


@dataclass
class Parameter:
    """Represents a method parameter."""
    name: str
    type_hint: Optional[str] = None
    default: Optional[str] = None
    is_required: bool = True


@dataclass
class MethodSignature:
    """Complete method signature information."""
    name: str
    parameters: List[Parameter] = field(default_factory=list)
    return_type: Optional[str] = None
    parent_class: str = ""
    docstring: Optional[str] = None
    is_factory: bool = False      # new_* methods
    is_setter: bool = False       # set_* methods
    is_getter: bool = False       # get_* methods
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "parameters": [asdict(p) for p in self.parameters],
            "return_type": self.return_type,
            "parent_class": self.parent_class,
            "docstring": self.docstring,
            "is_factory": self.is_factory,
            "is_setter": self.is_setter,
            "is_getter": self.is_getter
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MethodSignature":
        params = [Parameter(**p) for p in data.get("parameters", [])]
        return cls(
            name=data["name"],
            parameters=params,
            return_type=data.get("return_type"),
            parent_class=data.get("parent_class", ""),
            docstring=data.get("docstring"),
            is_factory=data.get("is_factory", False),
            is_setter=data.get("is_setter", False),
            is_getter=data.get("is_getter", False)
        )


@dataclass
class ClassInfo:
    """Complete class information including methods and hierarchy."""
    name: str
    bases: List[str] = field(default_factory=list)
    is_abstract: bool = False
    can_instantiate: bool = True
    docstring: Optional[str] = None
    factory_methods: List[MethodSignature] = field(default_factory=list)
    setters: List[MethodSignature] = field(default_factory=list)
    getters: List[MethodSignature] = field(default_factory=list)
    other_methods: List[MethodSignature] = field(default_factory=list)
    
    def get_all_methods(self) -> List[MethodSignature]:
        """Get all methods of this class."""
        return self.factory_methods + self.setters + self.getters + self.other_methods
    
    def has_method(self, method_name: str) -> bool:
        """Check if class has a specific method."""
        return any(m.name == method_name for m in self.get_all_methods())
    
    def get_method(self, method_name: str) -> Optional[MethodSignature]:
        """Get method by name."""
        for m in self.get_all_methods():
            if m.name == method_name:
                return m
        return None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "bases": self.bases,
            "is_abstract": self.is_abstract,
            "can_instantiate": self.can_instantiate,
            "docstring": self.docstring,
            "factory_methods": [m.to_dict() for m in self.factory_methods],
            "setters": [m.to_dict() for m in self.setters],
            "getters": [m.to_dict() for m in self.getters],
            "other_methods": [m.to_dict() for m in self.other_methods]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ClassInfo":
        return cls(
            name=data["name"],
            bases=data.get("bases", []),
            is_abstract=data.get("is_abstract", False),
            can_instantiate=data.get("can_instantiate", True),
            docstring=data.get("docstring"),
            factory_methods=[MethodSignature.from_dict(m) for m in data.get("factory_methods", [])],
            setters=[MethodSignature.from_dict(m) for m in data.get("setters", [])],
            getters=[MethodSignature.from_dict(m) for m in data.get("getters", [])],
            other_methods=[MethodSignature.from_dict(m) for m in data.get("other_methods", [])]
        )


class SymbolTable:
    """
    Complete symbol table with all classes and methods from autosarfactory.
    Provides lookup and validation capabilities.
    """
    
    def __init__(self, classes: Dict[str, ClassInfo] = None, 
                 module_functions: Dict[str, MethodSignature] = None):
        self.classes = classes or {}
        self.module_functions = module_functions or {}
        self._method_index: Dict[str, List[str]] = {}  # method_name -> [class_names]
        self._build_method_index()
    
    def _build_method_index(self):
        """Build an index of method names to their parent classes."""
        self._method_index.clear()
        for class_name, class_info in self.classes.items():
            for method in class_info.get_all_methods():
                if method.name not in self._method_index:
                    self._method_index[method.name] = []
                self._method_index[method.name].append(class_name)
    
    def has_class(self, class_name: str) -> bool:
        """Check if a class exists in the symbol table."""
        return class_name in self.classes
    
    def has_method(self, method_name: str, class_name: str = None) -> bool:
        """Check if a method exists, optionally scoped to a specific class."""
        if class_name:
            if class_name not in self.classes:
                return False
            return self.classes[class_name].has_method(method_name)
        return method_name in self._method_index or method_name in self.module_functions
    
    def get_method_classes(self, method_name: str) -> List[str]:
        """Get all classes that define a specific method."""
        return self._method_index.get(method_name, [])
    
    def get_signature(self, method_name: str, class_name: str = None) -> Optional[MethodSignature]:
        """Get method signature."""
        if method_name in self.module_functions:
            return self.module_functions[method_name]
        if class_name and class_name in self.classes:
            return self.classes[class_name].get_method(method_name)
        # Search all classes
        for cls_info in self.classes.values():
            if cls_info.has_method(method_name):
                return cls_info.get_method(method_name)
        return None
    
    def get_factory_methods(self, class_name: str) -> List[str]:
        """Get all factory method names for a class."""
        if class_name not in self.classes:
            return []
        return [m.name for m in self.classes[class_name].factory_methods]
    
    def get_instantiable_classes(self) -> List[str]:
        """Get all classes that can be instantiated (not abstract)."""
        return [name for name, info in self.classes.items() if info.can_instantiate]
    
    def find_similar_method(self, method_name: str, limit: int = 3) -> List[str]:
        """Find methods with similar names (for error suggestions)."""
        import difflib
        all_methods = list(self._method_index.keys()) + list(self.module_functions.keys())
        return difflib.get_close_matches(method_name, all_methods, n=limit, cutoff=0.6)
    
    def to_dict(self) -> Dict:
        return {
            "classes": {name: info.to_dict() for name, info in self.classes.items()},
            "module_functions": {name: sig.to_dict() for name, sig in self.module_functions.items()},
            "metadata": {
                "total_classes": len(self.classes),
                "total_methods": sum(len(c.get_all_methods()) for c in self.classes.values()),
                "total_module_functions": len(self.module_functions)
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SymbolTable":
        classes = {name: ClassInfo.from_dict(info) for name, info in data.get("classes", {}).items()}
        module_functions = {name: MethodSignature.from_dict(sig) 
                          for name, sig in data.get("module_functions", {}).items()}
        return cls(classes=classes, module_functions=module_functions)


class ASTIndexer:
    """
    Indexes the autosarfactory module using Python's inspect module.
    Extracts complete API information for constrained code generation.
    """
    
    CACHE_FILE = os.path.join(os.path.dirname(__file__), "symbol_table.json")
    # Only exclude private/dunder methods and specific internal patterns
    EXCLUSIONS = {'autosar', 'parent', 'tag', 'text', 'tail', 'Element'}
    
    def __init__(self, force_rebuild: bool = False):
        """
        Initialize the indexer.
        
        Args:
            force_rebuild: If True, rebuild cache even if exists
        """
        self.force_rebuild = force_rebuild
        self._symbol_table: Optional[SymbolTable] = None
    
    def get_symbol_table(self) -> SymbolTable:
        """
        Get the symbol table, loading from cache or building if needed.
        Uses lazy loading with caching.
        """
        if self._symbol_table is not None:
            return self._symbol_table
        
        # Try to load from cache
        if not self.force_rebuild and os.path.exists(self.CACHE_FILE):
            print("Loading symbol table from cache...")
            try:
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._symbol_table = SymbolTable.from_dict(data)
                print(f"Loaded {len(self._symbol_table.classes)} classes from cache.")
                return self._symbol_table
            except Exception as e:
                print(f"Cache load failed: {e}. Rebuilding...")
        
        # Build from scratch
        print("Building symbol table from autosarfactory module...")
        self._symbol_table = self._build_symbol_table()
        
        # Save to cache
        self._save_cache()
        
        return self._symbol_table
    
    def _save_cache(self):
        """Save symbol table to cache file."""
        if self._symbol_table is None:
            return
        
        try:
            cache_data = self._symbol_table.to_dict()
            cache_data["metadata"]["generated_at"] = datetime.now().isoformat()
            
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            print(f"Symbol table cached to {self.CACHE_FILE}")
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")
    
    def _should_exclude(self, name: str) -> bool:
        """Check if a name should be excluded from indexing."""
        # Exclude dunder methods and private methods (starting with _)
        if name.startswith('_'):
            return True
        # Exclude specific patterns
        if any(exc in name.lower() for exc in self.EXCLUSIONS):
            return True
        return False
    
    def _build_symbol_table(self) -> SymbolTable:
        """Build complete symbol table from autosarfactory module."""
        import autosarfactory.autosarfactory as autosarfactory
        
        classes: Dict[str, ClassInfo] = {}
        module_functions: Dict[str, MethodSignature] = {}
        
        count = 0
        total = len(dir(autosarfactory))
        
        for name in dir(autosarfactory):
            if self._should_exclude(name):
                continue
            
            count += 1
            if count % 100 == 0:
                print(f"  Processing {count}/{total}...")
            
            try:
                obj = getattr(autosarfactory, name)
                
                # Handle module-level functions (like new_file, read, save)
                if inspect.isfunction(obj):
                    sig = self._extract_function_signature(name, obj)
                    if sig:
                        module_functions[name] = sig
                    continue
                
                # Handle classes
                if inspect.isclass(obj):
                    class_info = self._extract_class_info(name, obj)
                    if class_info:
                        classes[name] = class_info
                        
            except Exception as e:
                # Skip problematic entries
                continue
        
        print(f"Indexed {len(classes)} classes and {len(module_functions)} module functions.")
        return SymbolTable(classes=classes, module_functions=module_functions)
    
    def _extract_function_signature(self, name: str, func) -> Optional[MethodSignature]:
        """Extract signature from a function."""
        try:
            sig = inspect.signature(func)
            params = self._extract_parameters(sig)
            
            return_type = None
            if sig.return_annotation != inspect.Parameter.empty:
                return_type = str(sig.return_annotation)
            
            return MethodSignature(
                name=name,
                parameters=params,
                return_type=return_type,
                docstring=inspect.getdoc(func),
                is_factory=name.startswith('new_'),
                is_setter=name.startswith('set_'),
                is_getter=name.startswith('get_')
            )
        except Exception:
            return None
    
    def _extract_parameters(self, sig: inspect.Signature) -> List[Parameter]:
        """Extract parameters from a signature."""
        params = []
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue
            
            type_hint = None
            if param.annotation != inspect.Parameter.empty:
                type_hint = str(param.annotation)
            
            default = None
            is_required = True
            if param.default != inspect.Parameter.empty:
                default = repr(param.default)
                is_required = False
            
            params.append(Parameter(
                name=param_name,
                type_hint=type_hint,
                default=default,
                is_required=is_required
            ))
        
        return params
    
    def _extract_class_info(self, name: str, cls) -> Optional[ClassInfo]:
        """Extract complete class information."""
        try:
            # Get base classes
            bases = []
            if hasattr(cls, '__mro__'):
                for base in cls.__mro__:
                    if base.__name__ != name and base.__name__ != 'object':
                        if hasattr(base, '__module__') and base.__module__ and \
                           'autosarfactory' in str(base.__module__):
                            bases.append(base.__name__)
            
            # Check if abstract
            is_abstract = self._is_abstract_class(cls)
            can_instantiate = not is_abstract
            
            # Extract methods
            factory_methods = []
            setters = []
            getters = []
            other_methods = []
            
            for method_name, method in inspect.getmembers(cls):
                if self._should_exclude(method_name):
                    continue
                
                if not callable(method):
                    continue
                
                sig = self._extract_method_signature(method_name, method, name)
                if sig is None:
                    continue
                
                if method_name.startswith('new_'):
                    factory_methods.append(sig)
                elif method_name.startswith('set_'):
                    setters.append(sig)
                elif method_name.startswith('get_'):
                    getters.append(sig)
                else:
                    other_methods.append(sig)
            
            return ClassInfo(
                name=name,
                bases=bases,
                is_abstract=is_abstract,
                can_instantiate=can_instantiate,
                docstring=inspect.getdoc(cls),
                factory_methods=factory_methods,
                setters=setters,
                getters=getters,
                other_methods=other_methods
            )
            
        except Exception:
            return None
    
    def _extract_method_signature(self, name: str, method, parent_class: str) -> Optional[MethodSignature]:
        """Extract signature from a method."""
        try:
            sig = inspect.signature(method)
            params = self._extract_parameters(sig)
            
            return_type = None
            if sig.return_annotation != inspect.Parameter.empty:
                return_type = str(sig.return_annotation)
            
            return MethodSignature(
                name=name,
                parameters=params,
                return_type=return_type,
                parent_class=parent_class,
                docstring=inspect.getdoc(method),
                is_factory=name.startswith('new_'),
                is_setter=name.startswith('set_'),
                is_getter=name.startswith('get_')
            )
        except Exception:
            # Fallback for methods where signature extraction fails
            return MethodSignature(
                name=name,
                parent_class=parent_class,
                is_factory=name.startswith('new_'),
                is_setter=name.startswith('set_'),
                is_getter=name.startswith('get_')
            )
    
    def _is_abstract_class(self, cls) -> bool:
        """
        Check if a class is abstract.
        Detects ABC inheritance and @abstractmethod decorators.
        """
        import abc
        
        # Check if inherits from ABC
        if hasattr(abc, 'ABC') and issubclass(cls, abc.ABC):
            return True
        
        # Check for ABCMeta metaclass
        if hasattr(cls, '__abstractmethods__') and cls.__abstractmethods__:
            return True
        
        # Check for abstract methods
        for method_name in dir(cls):
            try:
                method = getattr(cls, method_name)
                if getattr(method, '__isabstractmethod__', False):
                    return True
            except Exception:
                continue
        
        return False


# Singleton instance for easy access
_indexer_instance: Optional[ASTIndexer] = None


def get_symbol_table(force_rebuild: bool = False) -> SymbolTable:
    """
    Get the global symbol table instance.
    
    Args:
        force_rebuild: If True, rebuild cache even if exists
        
    Returns:
        SymbolTable with complete API information
    """
    global _indexer_instance
    
    if _indexer_instance is None or force_rebuild:
        _indexer_instance = ASTIndexer(force_rebuild=force_rebuild)
    
    return _indexer_instance.get_symbol_table()


def rebuild_symbol_table() -> SymbolTable:
    """Force rebuild of the symbol table cache."""
    return get_symbol_table(force_rebuild=True)


if __name__ == "__main__":
    # Test the indexer
    print("Testing AST Indexer...")
    
    symbols = get_symbol_table()
    
    print(f"\nTotal classes: {len(symbols.classes)}")
    print(f"Total module functions: {len(symbols.module_functions)}")
    
    # Test specific lookups
    if "CanCluster" in symbols.classes:
        can_cluster = symbols.classes["CanCluster"]
        print(f"\nCanCluster factory methods: {[m.name for m in can_cluster.factory_methods]}")
        print(f"CanCluster is abstract: {can_cluster.is_abstract}")
    
    # Test method search
    similar = symbols.find_similar_method("new_CanCluster")
    print(f"\nSimilar to 'new_CanCluster': {similar}")
    
    # Test module functions
    print(f"\nModule functions: {list(symbols.module_functions.keys())}")
