"""
Autosarfactory Package
======================
AUTOSAR ARXML file creation and manipulation library.

This package provides classes and functions for working with AUTOSAR ARXML files,
including reading, creating, modifying, and saving ARXML files according to the
AUTOSAR 4.0 schema.

Main functions:
- read(): Read existing ARXML files
- new_file(): Create new ARXML files
- save(): Save changes to ARXML files
- saveAs(): Save ARXML to a new file
"""

from . import autosarfactory
from .autosarfactory import (
    # Core file operations
    read,
    new_file,
    save,
    saveAs,
    get_root,
    export_to_file,

    # Utility functions
    reinit,
    get_node,
    get_all_instances,
)

__all__ = [
    'autosarfactory',
    'read',
    'new_file',
    'save',
    'saveAs',
    'get_root',
    'export_to_file',
    'reinit',
    'get_node',
    'get_all_instances',
]
