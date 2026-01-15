"""
Export models created by csl_* modules
"""
import ast
import csv
import logging
import os
from utils.file_utils import get_files, get_module_name

logger = logging.getLogger(__name__)


class ModelExtractor(ast.NodeVisitor):
    """
    AST visitor to extract model definitions without registering them.
    This allows us to capture ALL model definitions, including duplicates.
    """
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.module = get_module_name(file_path)
        self.models = []  # List of (model_name, class_name, module, file_path)
    
    def visit_ClassDef(self, node, depth=0):
        """Process class definitions to identify Odoo models"""
        if depth > 100:  # Safety limit
            return
        
        # Check if this is an Odoo model
        model_name = None
        inherits = []
        
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        # Find _name attribute
                        if target.id == '_name' and isinstance(stmt.value, ast.Constant):
                            model_name = stmt.value.s
                        
                        # Find _inherit attribute
                        elif target.id == '_inherit':
                            if isinstance(stmt.value, ast.Constant):
                                inherit_val = stmt.value.s
                                if inherit_val:  # Filter out None, empty strings, etc.
                                    inherits.append(inherit_val)
                            elif isinstance(stmt.value, ast.List):
                                for elt in stmt.value.elts:
                                    if isinstance(elt, ast.Constant):
                                        elt_val = elt.s
                                        if elt_val:  # Filter out None, empty strings, etc.
                                            inherits.append(elt_val)
        
        # Only collect models that are actually CREATED (not just extended)
        # A model is created if:
        # 1. It has _name and NO _inherit, OR
        # 2. It has _name and _inherit, but _name is NOT in the _inherit list
        if model_name:
            is_new_model = len(inherits) == 0 or model_name not in inherits
            if is_new_model:
                self.models.append((model_name, node.name, self.module, self.file_path))
        
        # Continue with child nodes
        self.generic_visit(node)


def extract_models_from_files(base_dir):
    """
    Extract all model definitions from Python files in the directory.
    Returns a list of (model_name, class_name, module, file_path) tuples.
    """
    all_models = []
    python_files = list(get_files(base_dir, '.py'))
    
    logger.info(f"Extracting models from {len(python_files)} Python files...")
    
    for file_path in python_files:
        if file_path.endswith('__manifest__.py'):
            continue
        
        module = get_module_name(file_path)
        
        # Only process csl_* modules
        if not module.startswith('csl_'):
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            tree = ast.parse(file_content)
            extractor = ModelExtractor(file_path)
            extractor.visit(tree)
            
            all_models.extend(extractor.models)
        
        except Exception as e:
            logger.warning(f"Error extracting models from {file_path}: {e}")
    
    return all_models


def export_csl_models(registry, output_dir, base_dir=None):
    """
    Export models created by modules starting with 'csl_'
    
    This function parses files directly to capture ALL model definitions,
    including duplicates in different modules (e.g., deprecated vs new locations).
    
    Args:
        registry: ModelRegistry instance (kept for API compatibility, not used for model discovery)
        output_dir: Directory to write the output file
        base_dir: Base directory to search for Python files (required for direct parsing)
    """
    logger.info("Exporting models from csl_* modules...")
    
    if base_dir is None:
        logger.warning("base_dir not provided, falling back to registry data (may miss duplicate definitions)")
        # Fallback: use registry data (will only show last registered definition per model)
        csl_models = []
        for model_name, model_info in registry.models.items():
            module = model_info.get('module', '')
            if module.startswith('csl_'):
                csl_models.append({
                    'model_name': model_name,
                    'class_name': model_info.get('class_name', ''),
                    'module': module,
                    'file_path': model_info.get('file_path', '')
                })
    else:
        # Parse files directly to capture all definitions
        extracted_models = extract_models_from_files(base_dir)
        
        csl_models = []
        for model_name, class_name, module, file_path in extracted_models:
            csl_models.append({
                'model_name': model_name,
                'class_name': class_name,
                'module': module,
                'file_path': file_path
            })
    
    # Sort by model name, then by module (so duplicates are grouped together)
    csl_models.sort(key=lambda x: (x['model_name'], x['module']))
    
    # Write to CSV
    output_file = os.path.join(output_dir, 'csl_models.csv')
    fieldnames = ['model_name', 'class_name', 'module', 'file_path']
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csl_models)
        unique_model_names = set(m['model_name'] for m in csl_models)
        duplicate_models = {name: [m for m in csl_models if m['model_name'] == name] 
                           for name in unique_model_names if len([m for m in csl_models if m['model_name'] == name]) > 1}
        
        logger.info(f"Exported {len(csl_models)} model definitions from csl_* modules to {output_file}")
        logger.info(f"  Found {len(unique_model_names)} unique model names")
        logger.info(f"  Found {len(duplicate_models)} models defined in multiple modules (duplicates): {sorted(duplicate_models.keys())}")
    except Exception as e:
        logger.error(f"Error exporting csl_* models to {output_file}: {e}")
        raise
