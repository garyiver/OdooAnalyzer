"""File utilities for Odoo analyzer"""
import os
from pathlib import Path
from .. import config

# Base directory - will be overridden by command line args
BASE_DIR = ""

def get_module_name(file_path):
    """Extract the module name from the file path"""
    parts = Path(file_path).parts
    # Find the first part after BASE_DIR that doesn't match common subfolders
    for i, part in enumerate(parts):
        if part == Path(config.BASE_DIR).name:
            if i + 1 < len(parts):
                return parts[i + 1]
    # Fallback if we can't determine module
    return "unknown"

def get_files(base_dir, extension):
    """Get all files with a specific extension in a directory"""
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(extension):
                yield os.path.join(root, file)

def qualified_name(model, field):
    """Create a qualified field name (model.field)"""
    if not model:
        return field
    return f"{model}.{field}"
