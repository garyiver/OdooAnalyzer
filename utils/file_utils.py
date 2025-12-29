"""File utilities for Odoo analyzer"""
import os
from pathlib import Path
import config
import logging

logger = logging.getLogger(__name__)

# Base directory - will be overridden by command line args
BASE_DIR = ""

def get_module_name(file_path):
    r"""Extract module name from file path
    
    For paths like:
    - C:\Odoo\sh\src\user\csl_contacts\models\res_partner.py -> csl_contacts
    - C:\Odoo\sh\src\odoo\odoo\addons\base\models\res_partner.py -> base
    
    The module name is the directory containing __manifest__.py, which is typically
    the directory before 'models', 'views', 'wizard', etc.
    """
    parts = Path(file_path).parts
    
    # Look for common Odoo module subdirectories (models, views, wizard, etc.)
    # The module name is the directory before these
    module_subdirs = {'models', 'views', 'wizard', 'wizards', 'controllers', 'static', 'data', 'security', 'report', 'tests'}
    
    for i, part in enumerate(parts):
        if part in module_subdirs and i > 0:
            # Module name is the directory before the subdirectory
            return parts[i - 1]
    
    # Fallback: if BASE_DIR is set, find first part after it
    if config.BASE_DIR:
        base_dir_name = Path(config.BASE_DIR).name
        for i, part in enumerate(parts):
            if part == base_dir_name and i + 1 < len(parts):
                # Skip intermediate directories like 'odoo', 'user', 'enterprise'
                # and find the actual module directory
                for j in range(i + 1, len(parts)):
                    potential_module = parts[j]
                    # Skip common intermediate directories
                    if potential_module not in {'odoo', 'addons', 'user', 'enterprise', 'custom'}:
                        return potential_module
                # If we only have intermediate dirs, return the first one
                return parts[i + 1] if i + 1 < len(parts) else "unknown"
    
    # Last fallback
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


def is_odoo_module_path(path):
    """Check if a path is likely an Odoo module path"""
    # Look for common module indicators
    if os.path.isdir(path):
        manifest_path = os.path.join(path, "__manifest__.py")
        old_manifest_path = os.path.join(path, "__openerp__.py")
        return os.path.exists(manifest_path) or os.path.exists(old_manifest_path)
    return False


def get_custom_modules(base_dir):
    """
    Get list of likely custom module paths
    Helps to filter out standard modules that might cause parsing issues
    """
    custom_modules = []

    # Skip standard module directories
    standard_dirs = ['base', 'web', 'addons', 'core', 'enterprise']

    for root, dirs, _ in os.walk(base_dir):
        # Skip directories that are likely to be standard modules
        dirs[:] = [d for d in dirs if d.lower() not in standard_dirs]

        if is_odoo_module_path(root):
            # Get the module name (last folder name in path)
            module_name = os.path.basename(root)
            custom_modules.append({
                'name': module_name,
                'path': root
            })

    logger.info(f"Found {len(custom_modules)} potential custom modules")
    return custom_modules


def get_safe_files(base_dir, extension, exclude_patterns=None):
    """
    Get files with the specified extension, excluding potentially problematic ones

    Args:
        base_dir: Base directory to search
        extension: File extension to look for (e.g. '.py', '.xml')
        exclude_patterns: List of patterns to exclude (e.g. ['test_', 'demo_'])

    Returns:
        List of file paths
    """
    if exclude_patterns is None:
        exclude_patterns = []

    # Add common problematic file patterns
    exclude_patterns.extend([
        'tests/', 'test_', '_test.',
        'demo/', 'demo_', '_demo.',
        'example/', 'example_', '_example.'
    ])

    files = []
    try:
        for root, _, filenames in os.walk(base_dir):
            # Skip directories that match exclude patterns
            if any(pattern in root for pattern in exclude_patterns if pattern.endswith('/')):
                continue

            for filename in filenames:
                if filename.endswith(extension):
                    # Skip files that match exclude patterns
                    if any(pattern in filename for pattern in exclude_patterns if not pattern.endswith('/')):
                        continue

                    files.append(os.path.join(root, filename))
    except Exception as e:
        logger.error(f"Error walking directory {base_dir}: {e}")

    return files