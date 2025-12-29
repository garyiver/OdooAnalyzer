"""
Module summary generator - creates a summary of all methods and fields for eligible modules
"""
import csv
import logging
import os
from collections import defaultdict

logger = logging.getLogger(__name__)


def generate_module_summary(output_dir, registry, all_fields, all_methods, eligible_modules):
    """
    Generate a summary file listing all methods and fields for eligible modules
    
    Args:
        output_dir: Directory to write the summary file
        registry: ModelRegistry instance
        all_fields: List of field dictionaries from field.to_dict()
        all_methods: List of all method dictionaries
        eligible_modules: Set of eligible module names
    """
    if not eligible_modules:
        logger.warning("No eligible modules specified - skipping module summary generation")
        return
    
    logger.info(f"Generating module summary for {len(eligible_modules)} eligible modules...")
    
    # Filter fields and methods for eligible modules
    eligible_fields = [f for f in all_fields if f.get('module') in eligible_modules or f.get('root_module') in eligible_modules]
    eligible_methods = [m for m in all_methods if m.get('module') in eligible_modules]
    
    # Group by module
    module_data = defaultdict(lambda: {
        'fields': [],
        'methods': []
    })
    
    # Group fields by module
    # Use a set to track unique field keys per module to avoid duplicates
    field_keys_seen = defaultdict(set)
    
    for field in eligible_fields:
        module = field.get('module', 'unknown')
        root_module = field.get('root_module', '')
        field_key = field.get('field_key', f"{field.get('model', '')}.{field.get('field_name', '')}")
        
        # Add to module where it's defined
        if module in eligible_modules:
            if field_key not in field_keys_seen[module]:
                module_data[module]['fields'].append(field)
                field_keys_seen[module].add(field_key)
        
        # Also add to root_module if different and eligible
        if root_module and root_module in eligible_modules and root_module != module:
            if field_key not in field_keys_seen[root_module]:
                # Create a reference entry for root module
                field_ref = field.copy()
                field_ref['module'] = root_module
                field_ref['is_root_reference'] = True
                module_data[root_module]['fields'].append(field_ref)
                field_keys_seen[root_module].add(field_key)
    
    # Group methods by module
    for method in eligible_methods:
        module = method.get('module', 'unknown')
        if module in eligible_modules:
            module_data[module]['methods'].append(method)
    
    # Create summary data
    summary_data = []
    
    for module in sorted(eligible_modules):
        data = module_data[module]
        fields = data['fields']
        methods = data['methods']
        
        # Add module header row
        summary_data.append({
            'module': module,
            'type': 'MODULE_HEADER',
            'name': '',
            'model': '',
            'file_path': '',
            'details': f'Total: {len(fields)} fields, {len(methods)} methods'
        })
        
        # Add fields section
        if fields:
            summary_data.append({
                'module': module,
                'type': 'SECTION',
                'name': 'FIELDS',
                'model': '',
                'file_path': '',
                'details': f'{len(fields)} fields'
            })
            
            # Group fields by model
            fields_by_model = defaultdict(list)
            for field in fields:
                model = field.get('model', 'unknown')
                fields_by_model[model].append(field)
            
            for model in sorted(fields_by_model.keys()):
                model_fields = fields_by_model[model]
                summary_data.append({
                    'module': module,
                    'type': 'MODEL_HEADER',
                    'name': '',
                    'model': model,
                    'file_path': '',
                    'details': f'{len(model_fields)} fields'
                })
                
                for field in sorted(model_fields, key=lambda x: x.get('field_name', '')):
                    summary_data.append({
                        'module': module,
                        'type': 'FIELD',
                        'name': field.get('field_name', ''),
                        'model': field.get('model', ''),
                        'file_path': field.get('defined_in', ''),
                        'details': f"{field.get('field_type', '')} - {field.get('attributes', '')}"
                    })
        
        # Add methods section
        if methods:
            summary_data.append({
                'module': module,
                'type': 'SECTION',
                'name': 'METHODS',
                'model': '',
                'file_path': '',
                'details': f'{len(methods)} methods'
            })
            
            # Group methods by model
            methods_by_model = defaultdict(list)
            for method in methods:
                model = method.get('model', 'unknown')
                methods_by_model[model].append(method)
            
            for model in sorted(methods_by_model.keys()):
                model_methods = methods_by_model[model]
                summary_data.append({
                    'module': module,
                    'type': 'MODEL_HEADER',
                    'name': '',
                    'model': model,
                    'file_path': '',
                    'details': f'{len(model_methods)} methods'
                })
                
                for method in sorted(model_methods, key=lambda x: x.get('method', '')):
                    override_info = ' (override)' if method.get('is_override', False) else ''
                    summary_data.append({
                        'module': module,
                        'type': 'METHOD',
                        'name': method.get('method', ''),
                        'model': method.get('model', ''),
                        'file_path': method.get('file_path', ''),
                        'details': f"Class: {method.get('class', '')}{override_info}"
                    })
    
    # Write to CSV
    output_file = os.path.join(output_dir, 'module_summary.csv')
    fieldnames = ['module', 'type', 'name', 'model', 'file_path', 'details']
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in summary_data:
                writer.writerow(row)
        logger.info(f"Module summary written to {output_file}")
    except Exception as e:
        logger.error(f"Error writing module summary to {output_file}: {e}")

