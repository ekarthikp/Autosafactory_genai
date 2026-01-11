"""
Code Knowledge Graph - Structural Relationships for Autosarfactory
===================================================================
NetworkX-based graph representing class hierarchies, method relationships,
and factory patterns. Enables intelligent context retrieval and validation.

Features:
- Class inheritance hierarchy
- Factory method return type relationships
- Valid method lookup per class (including inherited)
- Instantiability checking
"""

import os
import json
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass

try:
    import networkx as nx
except ImportError:
    raise ImportError("Please install networkx: pip install networkx")

from src.ast_indexer import get_symbol_table, SymbolTable, ClassInfo, MethodSignature


# Edge types
EDGE_INHERITS = "INHERITS"      # Class A inherits from Class B
EDGE_CONTAINS = "CONTAINS"      # Class contains method
EDGE_RETURNS = "RETURNS"        # Factory method returns type
EDGE_ACCEPTS = "ACCEPTS"        # Setter accepts type

# Node types  
NODE_CLASS = "CLASS"
NODE_METHOD = "METHOD"
NODE_FUNCTION = "FUNCTION"


@dataclass
class MethodContext:
    """Context needed to use a method correctly."""
    method_name: str
    parent_class: str
    parameters: List[str]
    return_type: Optional[str]
    requires_classes: List[str]  # Classes needed as arguments
    creates_class: Optional[str]  # What this factory method creates


class CodeKnowledgeGraph:
    """
    Knowledge graph representing the structure of autosarfactory.
    Provides rich queries for method lookup, dependency traversal,
    and constraint generation.
    """
    
    CACHE_FILE = os.path.join(os.path.dirname(__file__), "code_graph_cache.json")
    
    def __init__(self, symbol_table: SymbolTable = None, force_rebuild: bool = False):
        """
        Initialize the code knowledge graph.
        
        Args:
            symbol_table: Pre-built symbol table, or None to load automatically
            force_rebuild: If True, rebuild even if cache exists
        """
        self.graph = nx.DiGraph()
        self.symbol_table = symbol_table or get_symbol_table()
        self._class_methods_cache: Dict[str, Set[str]] = {}
        
        # Build or load graph
        if not force_rebuild and self._load_cache():
            print(f"Loaded code graph from cache: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        else:
            self._build_graph()
            self._save_cache()
    
    def _build_graph(self):
        """Build the graph from symbol table."""
        print("Building code knowledge graph...")
        
        # Add class nodes
        for class_name, class_info in self.symbol_table.classes.items():
            self.graph.add_node(
                class_name,
                type=NODE_CLASS,
                is_abstract=class_info.is_abstract,
                can_instantiate=class_info.can_instantiate
            )
            
            # Add inheritance edges
            for base in class_info.bases:
                if base in self.symbol_table.classes:
                    self.graph.add_edge(class_name, base, type=EDGE_INHERITS)
            
            # Add method nodes and edges
            for method in class_info.get_all_methods():
                method_id = f"{class_name}.{method.name}"
                
                self.graph.add_node(
                    method_id,
                    type=NODE_METHOD,
                    is_factory=method.is_factory,
                    is_setter=method.is_setter,
                    is_getter=method.is_getter,
                    return_type=method.return_type
                )
                
                # Class contains method
                self.graph.add_edge(class_name, method_id, type=EDGE_CONTAINS)
                
                # Factory method returns type
                if method.is_factory and method.return_type:
                    return_type = self._extract_type_name(method.return_type)
                    if return_type and return_type in self.symbol_table.classes:
                        self.graph.add_edge(method_id, return_type, type=EDGE_RETURNS)
        
        # Add module-level function nodes
        for func_name, func_sig in self.symbol_table.module_functions.items():
            self.graph.add_node(
                func_name,
                type=NODE_FUNCTION,
                is_factory=func_sig.is_factory,
                return_type=func_sig.return_type
            )
        
        print(f"Built graph with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")
    
    def _extract_type_name(self, type_str: str) -> Optional[str]:
        """Extract class name from type annotation string."""
        if not type_str:
            return None
        
        # Handle common patterns
        # "<class 'autosarfactory.autosarfactory.CanCluster'>" -> "CanCluster"
        if "autosarfactory." in type_str:
            parts = type_str.split(".")
            return parts[-1].rstrip("'>")
        
        # "Optional[CanCluster]" -> "CanCluster"
        if "Optional" in type_str or "List" in type_str:
            import re
            match = re.search(r'\[(\w+)\]', type_str)
            if match:
                return match.group(1)
        
        # Plain class name
        if type_str in self.symbol_table.classes:
            return type_str
        
        return None
    
    def _save_cache(self):
        """Save graph structure to cache."""
        try:
            data = {
                "nodes": list(self.graph.nodes(data=True)),
                "edges": list(self.graph.edges(data=True))
            }
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(data, f)
            print(f"Saved code graph cache to {self.CACHE_FILE}")
        except Exception as e:
            print(f"Warning: Could not save graph cache: {e}")
    
    def _load_cache(self) -> bool:
        """Load graph from cache if available."""
        if not os.path.exists(self.CACHE_FILE):
            return False
        
        try:
            with open(self.CACHE_FILE, 'r') as f:
                data = json.load(f)
            
            self.graph = nx.DiGraph()
            for node, attrs in data["nodes"]:
                self.graph.add_node(node, **attrs)
            for u, v, attrs in data["edges"]:
                self.graph.add_edge(u, v, **attrs)
            
            return True
        except Exception as e:
            print(f"Cache load failed: {e}")
            return False
    
    # ========== Query Methods ==========
    
    def get_valid_methods_for_class(self, class_name: str, 
                                     include_inherited: bool = True) -> List[str]:
        """
        Get all valid method names that can be called on this class.
        
        Args:
            class_name: The class to query
            include_inherited: Whether to include methods from parent classes
            
        Returns:
            List of method names (without class prefix)
        """
        # Check cache
        cache_key = f"{class_name}_{include_inherited}"
        if cache_key in self._class_methods_cache:
            return list(self._class_methods_cache[cache_key])
        
        if class_name not in self.graph:
            return []
        
        methods = set()
        
        # Get direct methods (edges of type CONTAINS from class to methods)
        for _, method_id, data in self.graph.out_edges(class_name, data=True):
            if data.get("type") == EDGE_CONTAINS:
                # Extract method name from "ClassName.methodName"
                method_name = method_id.split(".")[-1]
                methods.add(method_name)
        
        # Get inherited methods
        if include_inherited:
            for _, base_class, data in self.graph.out_edges(class_name, data=True):
                if data.get("type") == EDGE_INHERITS:
                    inherited = self.get_valid_methods_for_class(base_class, True)
                    methods.update(inherited)
        
        # Cache result
        self._class_methods_cache[cache_key] = methods
        return list(methods)
    
    def get_factory_methods(self, class_name: str) -> List[Tuple[str, str]]:
        """
        Get factory methods and their return types for a class.
        
        Returns:
            List of tuples: (method_name, return_type)
        """
        if class_name not in self.graph:
            return []
        
        factory_methods = []
        
        for _, method_id, data in self.graph.out_edges(class_name, data=True):
            if data.get("type") == EDGE_CONTAINS:
                method_data = self.graph.nodes.get(method_id, {})
                if method_data.get("is_factory"):
                    method_name = method_id.split(".")[-1]
                    
                    # Find return type
                    return_type = None
                    for _, target, edge_data in self.graph.out_edges(method_id, data=True):
                        if edge_data.get("type") == EDGE_RETURNS:
                            return_type = target
                            break
                    
                    factory_methods.append((method_name, return_type))
        
        return factory_methods
    
    def get_creatable_types(self, from_class: str) -> List[str]:
        """Get all types that can be created from this class via factory methods."""
        return [t for _, t in self.get_factory_methods(from_class) if t]
    
    def get_inheritance_chain(self, class_name: str) -> List[str]:
        """Get the inheritance chain for a class (from most derived to base)."""
        if class_name not in self.graph:
            return []
        
        chain = [class_name]
        current = class_name
        
        while True:
            bases = [target for _, target, data in self.graph.out_edges(current, data=True)
                    if data.get("type") == EDGE_INHERITS]
            if not bases:
                break
            current = bases[0]  # Take first base
            chain.append(current)
        
        return chain
    
    def is_instantiable(self, class_name: str) -> bool:
        """Check if a class can be instantiated (not abstract)."""
        if class_name not in self.graph:
            return False
        
        node_data = self.graph.nodes[class_name]
        return node_data.get("can_instantiate", True)
    
    def get_abstract_classes(self) -> List[str]:
        """Get all abstract classes that cannot be instantiated."""
        return [node for node, data in self.graph.nodes(data=True)
                if data.get("type") == NODE_CLASS and data.get("is_abstract", False)]
    
    def get_required_context(self, class_name: str, depth: int = 2) -> List[str]:
        """
        Get classes needed to work with this class (dependencies).
        
        Args:
            class_name: The class to analyze
            depth: How deep to traverse relationships
            
        Returns:
            List of related class names
        """
        if class_name not in self.graph:
            return []
        
        related = set()
        to_process = [(class_name, 0)]
        processed = set()
        
        while to_process:
            current, current_depth = to_process.pop(0)
            if current in processed or current_depth > depth:
                continue
            processed.add(current)
            
            # Only process class nodes
            node_data = self.graph.nodes.get(current, {})
            if node_data.get("type") != NODE_CLASS:
                continue
            
            related.add(current)
            
            # Add bases
            for _, target, data in self.graph.out_edges(current, data=True):
                if data.get("type") == EDGE_INHERITS:
                    to_process.append((target, current_depth + 1))
            
            # Add factory return types
            for factory_name, return_type in self.get_factory_methods(current):
                if return_type:
                    to_process.append((return_type, current_depth + 1))
        
        return list(related - {class_name})
    
    def validate_method_call(self, class_name: str, method_name: str) -> Tuple[bool, str]:
        """
        Validate if a method can be called on a class.
        
        Returns:
            Tuple of (is_valid, error_message_or_empty)
        """
        if class_name not in self.graph:
            return False, f"Class '{class_name}' not found"
        
        valid_methods = self.get_valid_methods_for_class(class_name)
        
        if method_name in valid_methods:
            return True, ""
        
        # Find similar methods for suggestion
        import difflib
        similar = difflib.get_close_matches(method_name, valid_methods, n=3, cutoff=0.6)
        
        if similar:
            return False, f"Method '{method_name}' not found on '{class_name}'. Did you mean: {', '.join(similar)}?"
        
        return False, f"Method '{method_name}' not found on '{class_name}'"
    
    def get_method_context(self, class_name: str, method_name: str) -> Optional[MethodContext]:
        """Get full context for using a method."""
        if class_name not in self.symbol_table.classes:
            return None
        
        class_info = self.symbol_table.classes[class_name]
        method_sig = class_info.get_method(method_name)
        
        if not method_sig:
            return None
        
        # Determine what classes are required as arguments
        requires = []
        for param in method_sig.parameters:
            if param.type_hint:
                type_name = self._extract_type_name(param.type_hint)
                if type_name and type_name in self.symbol_table.classes:
                    requires.append(type_name)
        
        # Determine what this creates (for factory methods)
        creates = None
        if method_sig.is_factory:
            creates = self._extract_type_name(method_sig.return_type)
        
        return MethodContext(
            method_name=method_name,
            parent_class=class_name,
            parameters=[p.name for p in method_sig.parameters],
            return_type=method_sig.return_type,
            requires_classes=requires,
            creates_class=creates
        )
    
    def build_constraint_set(self, class_names: List[str]) -> Dict[str, List[str]]:
        """
        Build a complete constraint set for code generation.
        
        Args:
            class_names: Classes that will be used in the generated code
            
        Returns:
            Dict mapping class names to their valid methods
        """
        constraints = {}
        
        for class_name in class_names:
            if class_name in self.graph:
                methods = self.get_valid_methods_for_class(class_name)
                constraints[class_name] = sorted(methods)
        
        return constraints


# Singleton instance
_graph_instance: Optional[CodeKnowledgeGraph] = None


def get_code_graph(force_rebuild: bool = False) -> CodeKnowledgeGraph:
    """
    Get the global code knowledge graph instance.
    
    Args:
        force_rebuild: If True, rebuild from symbol table
        
    Returns:
        CodeKnowledgeGraph instance
    """
    global _graph_instance
    
    if _graph_instance is None or force_rebuild:
        _graph_instance = CodeKnowledgeGraph(force_rebuild=force_rebuild)
    
    return _graph_instance


if __name__ == "__main__":
    # Test the graph
    print("Testing Code Knowledge Graph...")
    
    graph = get_code_graph()
    
    # Test method lookup
    print("\n=== CanCluster Methods ===")
    methods = graph.get_valid_methods_for_class("CanCluster")
    print(f"Total methods: {len(methods)}")
    print(f"Factory methods: {[m for m in methods if m.startswith('new_')][:10]}")
    
    # Test factory methods with return types
    print("\n=== CanCluster Factory Methods ===")
    factories = graph.get_factory_methods("CanCluster")
    for name, return_type in factories[:5]:
        print(f"  {name} -> {return_type}")
    
    # Test inheritance
    print("\n=== Inheritance Chain for CanCluster ===")
    chain = graph.get_inheritance_chain("CanCluster")
    print(f"  {' -> '.join(chain)}")
    
    # Test validation
    print("\n=== Validation Tests ===")
    valid, msg = graph.validate_method_call("CanCluster", "new_CanClusterVariant")
    print(f"  CanCluster.new_CanClusterVariant: {valid}")
    
    valid, msg = graph.validate_method_call("CanCluster", "new_FakeMethod")
    print(f"  CanCluster.new_FakeMethod: {valid} - {msg}")
    
    # Test abstract classes
    print("\n=== Abstract Classes ===")
    abstract = graph.get_abstract_classes()
    print(f"  Found {len(abstract)} abstract classes")
    
    # Test constraint building
    print("\n=== Constraint Set ===")
    constraints = graph.build_constraint_set(["CanCluster", "CanFrame"])
    for cls, methods in constraints.items():
        print(f"  {cls}: {len(methods)} valid methods")
