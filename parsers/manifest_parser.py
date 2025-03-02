"""Manifest file parser for Odoo analyzer"""
import ast
import logging
import os
from ..utils.file_utils import get_module_name

logger = logging.getLogger(__name__)

def parse_manifest_file(file_path):
    """Extract information from a module's __manifest__.py"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Use ast to safely evaluate the Python literals
        manifest_dict = ast.literal_eval(content)

        return {
            'module': get_module_name(file_path),
            'dependencies': manifest_dict.get('depends', []),
            'name': manifest_dict.get('name', ''),
            'description': manifest_dict.get('description', ''),
            'category': manifest_dict.get('category', ''),
            'version': manifest_dict.get('version', ''),
            'auto_install': manifest_dict.get('auto_install', False),
        }
    except Exception as e:
        logger.error(f"Error parsing manifest {file_path}: {e}")
        return {
            'module': get_module_name(file_path),
            'dependencies': []
        }

def parse_manifest_files(base_dir):
    """Parse all manifest files in the directory"""
    logger.info("Processing manifest files for dependencies...")
    manifest_dependencies = []

    for root, _, files in os.walk(base_dir):
        if '__manifest__.py' in files:
            manifest_path = os.path.join(root, '__manifest__.py')
            manifest_data = parse_manifest_file(manifest_path)
            manifest_dependencies.append(manifest_data)

    logger.info(f"Found {len(manifest_dependencies)} modules with manifest dependencies")
    return manifest_dependencies
