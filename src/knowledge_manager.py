"""
Knowledge Manager - Provides API knowledge for code generation.
================================================================
Uses the new APIIndex for accurate, compact knowledge retrieval.
Replaces the old JSON-based knowledge graph approach.
"""

import os
import difflib
from typing import Dict, List, Set, Optional


class KnowledgeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KnowledgeManager, cls).__new__(cls)
            cls._instance._api_index = None
            cls._instance._init_index()
        return cls._instance

    def _init_index(self):
        """Initialize the API index."""
        try:
            from src.api_index import get_api_index
            self._api_index = get_api_index()
        except Exception as e:
            print(f"Warning: API index not available: {e}")

    def get_class_info(self, class_name):
        """Get info for a class."""
        if self._api_index is None:
            return None
        return self._api_index.classes.get(class_name)

    def search_classes(self, query, limit=5):
        """Search for classes matching the query."""
        if self._api_index is None:
            return []

        query_lower = query.lower()
        matches = []

        # Exact match
        for name in self._api_index.classes:
            if name.lower() == query_lower:
                matches.append(name)
                break

        # Contains match
        for name in self._api_index.classes:
            if name not in matches and query_lower in name.lower():
                matches.append(name)

        # Fuzzy match
        if len(matches) < limit:
            fuzzy = difflib.get_close_matches(
                query, list(self._api_index.classes.keys()), n=limit, cutoff=0.6
            )
            for m in fuzzy:
                if m not in matches:
                    matches.append(m)

        return matches[:limit]

    def get_dependencies(self, class_name, recursive=True, depth=0, max_depth=2):
        """Get dependencies for a class (parent classes, factory return types)."""
        deps = set()
        if self._api_index is None or class_name not in self._api_index.classes:
            return deps

        info = self._api_index.classes[class_name]

        # Parent classes
        for base in info.get('bases', []):
            deps.add(base)

        # Factory return types
        for ret_type in info.get('factory', {}).values():
            if ret_type and ret_type in self._api_index.classes:
                deps.add(ret_type)

        # Recursive expansion
        if recursive and depth < max_depth:
            sub_deps = set()
            for dep in list(deps):
                sub_deps.update(self.get_dependencies(dep, True, depth + 1, max_depth))
            deps.update(sub_deps)

        return deps

    def get_context_for_classes(self, class_names):
        """Generate compact text context for a list of classes."""
        if self._api_index is None:
            return ""

        # Expand with dependencies
        all_classes = set(class_names)
        for name in class_names:
            all_classes.update(self.get_dependencies(name, recursive=True, max_depth=1))

        return self._api_index.get_compact_context(sorted(all_classes))

    def find_method_origin(self, method_name):
        """Find which classes define a specific method."""
        if self._api_index is None:
            return []
        return self._api_index._method_to_classes.get(method_name, [])

    def suggest_fix_for_attribute_error(self, class_name, attribute_name):
        """Suggest fix for AttributeError."""
        if self._api_index is None:
            return None

        # Check for similar methods on the class
        similar = self._api_index.find_similar_method(attribute_name, class_name)
        if similar:
            return f"Did you mean '{similar[0]}' instead of '{attribute_name}'?"

        # Check if method exists elsewhere
        origins = self.find_method_origin(attribute_name)
        if origins:
            return f"'{attribute_name}' exists on {origins[:3]}. Wrong object?"

        return None

    def search_domain_knowledge(self, query):
        """Search domain_knowledge.txt for relevant context."""
        domain_file = os.path.join(os.path.dirname(__file__), "domain_knowledge.txt")
        if not os.path.exists(domain_file):
            return ""

        try:
            with open(domain_file, "r") as f:
                content = f.read()

            paragraphs = content.split("\n\n")
            query_words = set(w for w in query.lower().split() if len(w) > 3)
            relevant = [p.strip() for p in paragraphs
                       if any(w in p.lower() for w in query_words)]

            if relevant:
                return "\n=== DOMAIN KNOWLEDGE ===\n" + "\n\n".join(relevant[:5]) + "\n"
            return ""
        except Exception:
            return ""
