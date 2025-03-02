"""CSV export functions"""
import csv
import json
import logging
import os
from collections import defaultdict

logger = logging.getLogger(__name__)

def export_fields_to_csv(fields, output_file='fields_analysis.csv'):
    """Export field definitions to CSV"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'model', 'field_name', 'field_key', 'field_type', 'module', 'attributes', 'defined_in',
            'is_computed', 'is_stored', 'is_related', 'dependency_fields',
            'usage_count', 'used_in_modules', 'used_in_views',
            'is_extension', 'extended_from', 'added_attributes', 'modified_attributes'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for f in fields:
            writer.writerow(f.to_dict())
    logger.info(f"Exported field definitions to {output_file}")

def export_field_usage_to_csv(field_usage, output_file='fields_usage.csv'):
    """Export field usage to CSV"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['field_key', 'model', 'field_name', 'usage_count', 'used_in_modules', 'used_in_views']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for field_key, usages in field_usage.items():
            # Extract model and field_name from field_key
            model = ""  # Empty string instead of None
            field_name = field_key

            if '.' in field_key:
                parts = field_key.split('.')
                model = parts[0]
                field_name = parts[1]

            # Get unique modules and views
            modules = set()
            views = set()
            for usage in usages:
                if 'module' in usage and usage['module']:
                    modules.add(str(usage['module']))
                if 'context' in usage and usage['context']:
                    views.add(str(usage['context']))

            # Ensure all values are strings to prevent type issues
            writer.writerow({
                'field_key': str(field_key),
                'model': str(model),
                'field_name': str(field_name),
                'usage_count': str(len(usages)),
                'used_in_modules': '; '.join(sorted(modules)),
                'used_in_views': '; '.join(sorted(views))
            })

    logger.info(f"Exported field usage information to {output_file}")

def export_method_overrides_to_csv(method_overrides, output_file='method_overrides.csv'):
    """Export method overrides to CSV"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['model', 'class', 'method', 'module', 'file_path']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for override in method_overrides:
            writer.writerow(override)

    logger.info(f"Exported method overrides to {output_file}")

def export_module_dependencies_to_csv(manifest_deps, inheritance_deps, output_file='module_dependencies.csv'):
    """Export module dependencies to CSV"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['module', 'name', 'category', 'version', 'manifest_dependencies',
                      'inheritance_dependencies', 'combined_dependencies', 'dependents']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # Process manifest dependencies
        manifest_dict = {}
        for module in manifest_deps:
            manifest_dict[module['module']] = module

        # Create combined dependencies
        combined_deps = {}
        for module, deps in inheritance_deps.items():
            combined = set(deps)
            if module in manifest_dict:
                combined.update(manifest_dict[module].get('dependencies', []))
            combined_deps[module] = sorted(combined)

        # Create reverse dependency lookup (modules that depend on this one)
        dependents = defaultdict(set)
        for module, deps in combined_deps.items():
            for dep in deps:
                dependents[dep].add(module)

        # Write to CSV
        for module in set(list(manifest_dict.keys()) + list(inheritance_deps.keys())):
            manifest_info = manifest_dict.get(module, {})
            manifest_dependencies = manifest_info.get('dependencies', [])
            inherit_dependencies = inheritance_deps.get(module, [])
            combined = combined_deps.get(module, [])
            module_dependents = sorted(dependents.get(module, set()))

            writer.writerow({
                'module': module,
                'name': manifest_info.get('name', ''),
                'category': manifest_info.get('category', ''),
                'version': manifest_info.get('version', ''),
                'manifest_dependencies': '; '.join(manifest_dependencies),
                'inheritance_dependencies': '; '.join(inherit_dependencies),
                'combined_dependencies': '; '.join(combined),
                'dependents': '; '.join(module_dependents)
            })

    logger.info(f"Exported module dependencies to {output_file}")


def export_organization_recommendations_to_csv(recommendations, output_file='module_recommendations.csv'):
    """Export module organization recommendations to CSV"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['field', 'field_key', 'model', 'current_module', 'used_in_modules', 'recommendation']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for field_rec in recommendations['fields_to_move']:
            writer.writerow({
                'field': field_rec['field'],
                'field_key': field_rec['field_key'],
                'model': field_rec['model'],
                'current_module': field_rec['current_module'],
                'used_in_modules': '; '.join(field_rec['used_in_modules']),
                'recommendation': field_rec['recommendation']
            })

    logger.info(f"Exported module organization recommendations to {output_file}")

def export_shared_fields_to_csv(shared_fields, output_file='shared_fields.csv'):
    """Export shared fields to CSV"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['field', 'field_key', 'model', 'defined_in_module', 'used_in_modules', 'usage_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for field in shared_fields:
            writer.writerow({
                'field': field['field'],
                'field_key': field['field_key'],
                'model': field['model'],
                'defined_in_module': field['defined_in_module'],
                'used_in_modules': '; '.join(field['used_in_modules']),
                'usage_count': str(field['usage_count'])
            })

    logger.info(f"Exported shared fields to {output_file}")

def export_results(output_dir, all_fields, field_usage, method_overrides, 
                  manifest_dependencies, inheritance_dependencies, unused_fields,
                  shared_fields, organization_recommendations):
    """Export all analysis results to CSV files"""
     
    logger.info("Exporting results to CSV files...")
    
    # Create file paths with output directory
    fields_csv = os.path.join(output_dir, 'fields_analysis.csv')
    usage_csv = os.path.join(output_dir, 'fields_usage.csv')
    overrides_csv = os.path.join(output_dir, 'method_overrides.csv')
    deps_csv = os.path.join(output_dir, 'module_dependencies.csv')
    unused_csv = os.path.join(output_dir, 'unused_fields.csv')
    recommendations_csv = os.path.join(output_dir, 'module_recommendations.csv')
    shared_csv = os.path.join(output_dir, 'shared_fields.csv')
    
    # Export to CSV files
    export_fields_to_csv(all_fields, fields_csv)
    export_field_usage_to_csv(field_usage, usage_csv)
    export_method_overrides_to_csv(method_overrides, overrides_csv)
    export_module_dependencies_to_csv(manifest_dependencies, inheritance_dependencies, deps_csv)
    export_fields_to_csv(unused_fields, unused_csv)
    export_organization_recommendations_to_csv(organization_recommendations, recommendations_csv)
    export_shared_fields_to_csv(shared_fields, shared_csv)
    
    # Generate statistics
    stats = {
        'total_fields': len(all_fields),
        'unused_fields': len(unused_fields),
        'shared_fields': len(shared_fields),
        'fields_to_move': len(organization_recommendations['fields_to_move']),
        'method_overrides': len(method_overrides),
        'modules': len(manifest_dependencies)
    }
    
    # Write stats to JSON
    with open(os.path.join(output_dir, 'stats.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
