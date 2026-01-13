"""
Error Feedback Manager
======================
Tracks all errors and fixes during code generation for continuous learning and improvement.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import difflib


class ErrorFeedbackManager:
    """
    Manages error feedback collection and retrieval for continuous improvement.
    
    Stores all errors encountered during code generation along with:
    - Error details (type, message, line, traceback)
    - Context (plan, code snippet)
    - Fix attempts and outcomes
    - Timestamps for analysis
    """
    
    def __init__(self, feedback_file: str = "src/error_feedback.json"):
        """
        Initialize the error feedback manager.
        
        Args:
            feedback_file: Path to the JSON file storing error feedback
        """
        self.feedback_file = feedback_file
        self.feedback_data = {
            "errors": [],
            "metadata": {
                "total_errors": 0,
                "total_fixes_attempted": 0,
                "total_successful_fixes": 0,
                "last_updated": None
            }
        }
        self.load_feedback()
    
    def load_feedback(self):
        """Load existing feedback from JSON file."""
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)

                # Validate and merge with default structure
                if not isinstance(loaded_data, dict):
                    print("Warning: Loaded data is not a dictionary. Using default structure.")
                    return

                # Ensure 'errors' key exists and is a list
                if 'errors' not in loaded_data or not isinstance(loaded_data['errors'], list):
                    print("Warning: Missing or invalid 'errors' key. Initializing as empty list.")
                    loaded_data['errors'] = []

                # Ensure 'metadata' key exists and is a dict with all required fields
                if 'metadata' not in loaded_data or not isinstance(loaded_data['metadata'], dict):
                    print("Warning: Missing or invalid 'metadata' key. Using default metadata.")
                    loaded_data['metadata'] = self.feedback_data['metadata'].copy()
                else:
                    # Merge with default metadata to ensure all required fields exist
                    default_meta = self.feedback_data['metadata']
                    for key, default_value in default_meta.items():
                        if key not in loaded_data['metadata']:
                            loaded_data['metadata'][key] = default_value

                # Update feedback_data only after validation
                self.feedback_data = loaded_data
                print(f"Loaded {len(self.feedback_data['errors'])} error records from feedback file.")
            except Exception as e:
                print(f"Warning: Could not load feedback file: {e}")
                # Keep default empty structure
    
    def save_feedback(self):
        """Save feedback to JSON file."""
        try:
            # Ensure metadata exists before updating
            if "metadata" not in self.feedback_data or not isinstance(self.feedback_data["metadata"], dict):
                self.feedback_data["metadata"] = {
                    "total_errors": 0,
                    "total_fixes_attempted": 0,
                    "total_successful_fixes": 0,
                    "last_updated": None
                }

            # Update metadata
            self.feedback_data["metadata"]["last_updated"] = datetime.now().isoformat()

            # Ensure directory exists
            os.makedirs(os.path.dirname(self.feedback_file) if os.path.dirname(self.feedback_file) else ".", exist_ok=True)

            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(self.feedback_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save feedback file: {e}")
    
    def record_error(self, error_entry: Dict):
        """
        Record an error and fix attempt.
        
        Args:
            error_entry: Dictionary containing error information with keys:
                - timestamp: ISO format timestamp
                - error_type: Type of error (AttributeError, TypeError, etc.)
                - error_message: Full error message
                - error_line: Line number where error occurred (optional)
                - code_snippet: Relevant code snippet (optional)
                - plan_context: Brief description from the plan
                - fix_attempt_number: Which fix attempt this was
                - fix_applied: Description of the fix that was applied
                - fix_successful: Boolean indicating if fix worked
                - traceback: Full traceback (optional)
        """
        # Ensure errors list exists
        if "errors" not in self.feedback_data or not isinstance(self.feedback_data["errors"], list):
            self.feedback_data["errors"] = []

        # Add to errors list
        self.feedback_data["errors"].append(error_entry)

        # Ensure metadata exists and has required fields
        if "metadata" not in self.feedback_data or not isinstance(self.feedback_data["metadata"], dict):
            self.feedback_data["metadata"] = {
                "total_errors": 0,
                "total_fixes_attempted": 0,
                "total_successful_fixes": 0,
                "last_updated": None
            }

        # Update metadata
        metadata = self.feedback_data["metadata"]
        metadata["total_errors"] = metadata.get("total_errors", 0) + 1
        if error_entry.get("fix_applied"):
            metadata["total_fixes_attempted"] = metadata.get("total_fixes_attempted", 0) + 1
        if error_entry.get("fix_successful", False):
            metadata["total_successful_fixes"] = metadata.get("total_successful_fixes", 0) + 1

        # Save after each record (for persistence)
        self.save_feedback()
    
    def record_success(self, generation_info: Dict):
        """
        Record a successful generation (no errors).
        
        Args:
            generation_info: Dictionary with:
                - timestamp: ISO format timestamp
                - plan_description: Brief plan description
                - attempts_count: How many attempts it took (1 = first try)
        """
        # Could extend this to track successful patterns too
        pass
    
    def get_similar_errors(self, error_message: str, limit: int = 5) -> List[Dict]:
        """
        Find past errors with similar error messages.
        
        Args:
            error_message: The error message to match against
            limit: Maximum number of similar errors to return
            
        Returns:
            List of error entries sorted by similarity
        """
        if not self.feedback_data["errors"]:
            return []
        
        # Extract error messages for comparison
        past_errors = self.feedback_data["errors"]
        error_messages = [e.get("error_message", "") for e in past_errors]
        
        # Find close matches
        close_matches = difflib.get_close_matches(
            error_message, 
            error_messages, 
            n=limit, 
            cutoff=0.6
        )
        
        # Return the corresponding error entries
        similar = []
        for match in close_matches:
            for error in past_errors:
                if error.get("error_message") == match:
                    similar.append(error)
                    break
        
        return similar
    
    def get_statistics(self) -> Dict:
        """
        Get aggregated statistics about errors and fixes.

        Returns:
            Dictionary with statistics:
                - total_errors
                - total_fix_attempts
                - total_successful_fixes
                - success_rate
                - error_types_breakdown
                - common_errors (top 5)
        """
        # Ensure metadata exists with default values
        if "metadata" not in self.feedback_data or not isinstance(self.feedback_data["metadata"], dict):
            self.feedback_data["metadata"] = {
                "total_errors": 0,
                "total_fixes_attempted": 0,
                "total_successful_fixes": 0,
                "last_updated": None
            }

        # Ensure errors list exists
        if "errors" not in self.feedback_data or not isinstance(self.feedback_data["errors"], list):
            self.feedback_data["errors"] = []

        metadata = self.feedback_data["metadata"]
        errors = self.feedback_data["errors"]
        
        # Calculate success rate
        total_fixes = metadata.get("total_fixes_attempted", 0)
        successful = metadata.get("total_successful_fixes", 0)
        success_rate = (successful / total_fixes * 100) if total_fixes > 0 else 0
        
        # Error type breakdown
        error_types = {}
        for error in errors:
            error_type = error.get("error_type", "Unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # Common errors (by message similarity)
        # Group similar error messages
        error_message_counts = {}
        for error in errors:
            msg = error.get("error_message", "")[:100]  # First 100 chars
            error_message_counts[msg] = error_message_counts.get(msg, 0) + 1
        
        # Get top 5
        common_errors = sorted(
            error_message_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        return {
            "total_errors": metadata.get("total_errors", 0),
            "total_fix_attempts": total_fixes,
            "total_successful_fixes": successful,
            "success_rate": round(success_rate, 2),
            "error_types_breakdown": error_types,
            "common_errors": [{"message": msg, "count": count} for msg, count in common_errors],
            "last_updated": metadata.get("last_updated")
        }
    
    def get_success_rate_for_error_type(self, error_type: str) -> float:
        """
        Calculate fix success rate for a specific error type.
        
        Args:
            error_type: The error type (e.g., "AttributeError")
            
        Returns:
            Success rate as percentage (0-100)
        """
        errors_of_type = [e for e in self.feedback_data["errors"] if e.get("error_type") == error_type]
        
        if not errors_of_type:
            return 0.0
        
        successful = len([e for e in errors_of_type if e.get("fix_successful", False)])
        return (successful / len(errors_of_type)) * 100
    
    def get_fix_suggestions(self, error_type: str, error_message: str) -> List[str]:
        """
        Get suggestions for fixing an error based on past successful fixes.
        
        Args:
            error_type: The error type
            error_message: The error message
            
        Returns:
            List of fix descriptions that worked in the past
        """
        # Find similar successful fixes
        similar = self.get_similar_errors(error_message, limit=10)
        
        suggestions = []
        for error in similar:
            if error.get("fix_successful", False) and error.get("fix_applied"):
                suggestions.append(error["fix_applied"])
        
        # Return unique suggestions
        return list(set(suggestions))[:5]


# Singleton instance
_instance = None

def get_error_feedback_manager() -> ErrorFeedbackManager:
    """Get or create the singleton ErrorFeedbackManager instance."""
    global _instance
    if _instance is None:
        _instance = ErrorFeedbackManager()
    return _instance
