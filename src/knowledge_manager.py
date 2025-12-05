import json
import os
import difflib

class KnowledgeManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KnowledgeManager, cls).__new__(cls)
            cls._instance.kb = {}
            cls._instance.load_knowledge_base()
        return cls._instance

    def load_knowledge_base(self):
        """Load the knowledge graph from JSON file."""
        try:
            # Try to find the file in src directory relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            kb_path = os.path.join(base_dir, "knowledge_graph.json")
            
            if os.path.exists(kb_path):
                with open(kb_path, 'r') as f:
                    self.kb = json.load(f)
                print(f"Loaded knowledge base with {len(self.kb)} classes.")
            else:
                print(f"Warning: Knowledge base not found at {kb_path}")
                self.kb = {}
        except Exception as e:
            print(f"Error loading knowledge base: {e}")
            self.kb = {}

    def get_class_info(self, class_name):
        """Get raw info for a class."""
        return self.kb.get(class_name)

    def search_classes(self, query, limit=5):
        """
        Search for classes matching the query using fuzzy matching.
        Returns list of class names.
        """
        query = query.lower()
        matches = []
        
        # 1. Exact match (case insensitive)
        for name in self.kb.keys():
            if name.lower() == query:
                matches.append(name)
                break
        
        # 2. Contains match
        for name in self.kb.keys():
            if name not in matches and query in name.lower():
                matches.append(name)
                
        # 3. Fuzzy match if few results
        if len(matches) < limit:
            fuzzy = difflib.get_close_matches(query, self.kb.keys(), n=limit, cutoff=0.6)
            for m in fuzzy:
                if m not in matches:
                    matches.append(m)
                    
        return matches[:limit]

    def get_dependencies(self, class_name, recursive=True, depth=0, max_depth=2):
        """
        Get dependencies for a class.
        Returns a set of class names that are related (parents, factory return types, reference types).
        """
        deps = set()
        if class_name not in self.kb:
            return deps
            
        info = self.kb[class_name]
        
        # 1. Add bases
        for base in info.get('bases', []):
            deps.add(base)
            
        # 2. Add factory return types (children/creatable items)
        # These are important because if we want to use this class, we might want to create these.
        for fm in info.get('factory_methods', []):
            rt = fm.get('return_type')
            if rt and rt in self.kb:
                deps.add(rt)
                
        # 3. Add reference types (setters)
        # These are critical: if we need to set_X(obj), we need to know about class X.
        for ref in info.get('references', []):
            rt = ref.get('type')
            if rt and rt in self.kb:
                deps.add(rt)
                
        # Recursive step
        if recursive and depth < max_depth:
            sub_deps = set()
            for dep in deps:
                sub_deps.update(self.get_dependencies(dep, recursive=True, depth=depth+1, max_depth=max_depth))
            deps.update(sub_deps)
            
        return deps

    def get_context_for_classes(self, class_names):
        """
        Generate a text context for a list of classes, including their dependencies.
        """
        # 1. Expand dependencies
        all_classes = set(class_names)
        for name in class_names:
            all_classes.update(self.get_dependencies(name, recursive=True, max_depth=1))
            
        # 2. Format output
        output = []
        
        # Sort for stability
        sorted_classes = sorted(list(all_classes))
        
        for name in sorted_classes:
            info = self.kb.get(name)
            if not info:
                continue
                
            output.append(f"## Class: {name}")
            if info.get('bases'):
                output.append(f"Inheritance: {' -> '.join(info['bases'])}")
                
            # Factory methods
            fms = info.get('factory_methods', [])
            if fms:
                output.append("### Factory Methods (Create these children from this class):")
                for fm in fms:
                    output.append(f"- {fm['method']} -> returns {fm['return_type']}")
                    
            # References (Setters)
            refs = info.get('references', [])
            if refs:
                output.append("### References (Set these values):")
                for ref in refs:
                    output.append(f"- {ref['method']}({ref['type']})")
            
            output.append("") # Empty line
            
        return "\n".join(output)

    def find_method_origin(self, method_name):
        """
        Find which class defines a specific method.
        Useful for fixing 'AttributeError'.
        """
        candidates = []
        for name, info in self.kb.items():
            # Check factory methods
            for fm in info.get('factory_methods', []):
                if fm['method'] == method_name:
                    candidates.append(name)
            # Check references
            for ref in info.get('references', []):
                if ref['method'] == method_name:
                    candidates.append(name)
        return candidates

    def suggest_fix_for_attribute_error(self, class_name, attribute_name):
        """
        Suggest a fix for AttributeError: 'X' has no attribute 'Y'.
        """
        # 1. Check if it's a typo in method name
        if class_name in self.kb:
            info = self.kb[class_name]
            all_methods = [fm['method'] for fm in info.get('factory_methods', [])] + \
                          [ref['method'] for ref in info.get('references', [])]
            
            close_matches = difflib.get_close_matches(attribute_name, all_methods, n=1)
            if close_matches:
                return f"Did you mean '{close_matches[0]}' instead of '{attribute_name}'?"

        # 2. Check if the method exists in a parent class (already covered by inheritance, but good to check)
        
        # 3. Check if the method exists in a child or related class (wrong object usage)
        origin_classes = self.find_method_origin(attribute_name)
        if origin_classes:
            return f"The method '{attribute_name}' is defined in {origin_classes}. Are you calling it on the wrong object?"
            
        return None

    def search_domain_knowledge(self, query):
        """
        Searches the domain_knowledge.txt file for relevant context.
        Returns a string containing relevant paragraphs.
        """
        domain_file = os.path.join(os.path.dirname(__file__), "domain_knowledge.txt")
        if not os.path.exists(domain_file):
            return ""

        try:
            with open(domain_file, "r") as f:
                content = f.read()
            
            # Simple paragraph-based search
            paragraphs = content.split("\n\n")
            relevant_paragraphs = []
            query_words = set(query.lower().split())
            
            for p in paragraphs:
                if any(word in p.lower() for word in query_words if len(word) > 3):
                    relevant_paragraphs.append(p.strip())
            
            if relevant_paragraphs:
                return "\n=== DOMAIN KNOWLEDGE (FROM TPS DOC) ===\n" + "\n\n".join(relevant_paragraphs) + "\n=======================================\n"
            return ""
        except Exception as e:
            print(f"Error searching domain knowledge: {e}")
            return ""
