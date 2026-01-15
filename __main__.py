"""
Odoo Module Analyzer for Upgrade Planning with improved error handling

This script analyzes Odoo modules to help plan a reorganization for upgrade from v14 to v17.
"""
import argparse
import csv
import logging
import os
import sys
import traceback
import time
import warnings

# Suppress SyntaxWarnings from analyzed Python files (not our code)
# These warnings come from regex patterns in the source files being analyzed
warnings.filterwarnings('ignore', category=SyntaxWarning, message='.*invalid escape sequence.*')

from models.registry import ModelRegistry
from parsers.manifest_parser import parse_manifest_files
from parsers.python_parser import parse_python_files
from parsers.xml_parser import parse_xml_files
from analysis.module_analyzer import ModuleAnalyzer
from analysis.recommendations import generate_restructuring_recommendations
from analysis.module_consolidation import analyze_module_consolidation
from analysis.module_summary import generate_module_summary
from analysis.migration_analysis import analyze_migration
from analysis.csl_models import export_csl_models
from utils.file_utils import get_safe_files, get_custom_modules

import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('odoo_analyzer.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Analyze Odoo modules for upgrade planning')
    parser.add_argument('--dir', type=str, required=True, help='Path to Odoo custom modules directory')
    parser.add_argument('--output', type=str, default='./analysis_results', help='Output directory for results')
    parser.add_argument('--custom-only', action='store_true',
                        help='Only analyze custom modules, skip standard Odoo modules')
    parser.add_argument('--skip-problematic', action='store_true', help='Skip files that might cause parsing issues')

    # Additional analysis options
    parser.add_argument('--analyze-sharing', action='store_true', help='Analyze field sharing across modules')
    parser.add_argument('--identify-core', action='store_true', help='Identify fields that should be in core module')
    parser.add_argument('--generate-recommendations', action='store_true', 
                        help='Generate restructuring recommendations for csl_core consolidation')
    parser.add_argument('--analyze-consolidation', action='store_true',
                        help='Analyze module consolidation opportunities (which modules to combine)')
    parser.add_argument('--eligible-modules', type=str, nargs='+', default=None,
                        help='List of module names eligible for consolidation (overrides auto-detection)')
    
    # Migration analysis options
    parser.add_argument('--analyze-migration', action='store_true',
                        help='Analyze migration differences between original and new codebases')
    parser.add_argument('--original-dir', type=str, default=r'C:\Odoo\sh\src\user',
                        help='Path to original codebase (default: C:\\Odoo\\sh\\src\\user)')
    parser.add_argument('--new-dir', type=str, default=r'C:\Cursor\Odoo\csl_addons\odoo',
                        help='Path to new codebase (default: C:\\Cursor\\Odoo\\csl_addons\\odoo)')

    return parser.parse_args()


def check_output_files_writable(output_dir, args):
    """
    Check if output files are writable before processing starts.
    This helps catch issues early (e.g., files open in Excel) rather than failing at the end.
    
    Returns:
        tuple: (is_writable: bool, issues: list of error messages)
    """
    issues = []
    output_files = []
    
    # Always created files
    output_files.append('fields_analysis.csv')
    output_files.append('method_overrides.csv')
    
    # Conditionally created files
    if args.analyze_sharing:
        output_files.extend([
            'shared_fields.csv',
            'field_dependencies.csv',
            'field_dependencies_summary.csv',
            'view_field_analysis.csv',
            'core_candidates.csv',
            'shared_methods.csv',
            'utility_candidates.csv'
        ])
    
    if args.generate_recommendations:
        output_files.extend([
            'restructuring_recommendations.md',
            'modules_to_move_to_csl_core.csv',
            'migration_priority.csv'
        ])
    
    # First, check if directory is writable
    try:
        test_file = os.path.join(output_dir, '.write_test_tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except (PermissionError, OSError) as e:
        issues.append(f"Cannot write to output directory '{output_dir}': {e}")
        return False, issues
    
    # Check each file
    for filename in output_files:
        file_path = os.path.join(output_dir, filename)
        
        # Check if file exists and is locked
        if os.path.exists(file_path):
            try:
                # Try to open in write mode (this will fail if file is locked by another process)
                # On Windows, this will raise PermissionError if file is open in Excel
                with open(file_path, 'r+b') as f:
                    # File is not locked, we can proceed
                    pass
            except PermissionError:
                issues.append(f"File is locked (likely open in Excel or another program): {file_path}")
            except Exception as e:
                issues.append(f"Cannot access file {file_path}: {e}")
    
    return len(issues) == 0, issues


def export_csv(data, file_path, field_names):
    """Export data to CSV"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=field_names)
            writer.writeheader()
            for item in data:
                # Ensure all fields are present, filling in blanks if needed
                row = {field: item.get(field, '') for field in field_names}
                writer.writerow(row)
        logger.info(f"Exported data to {file_path}")
    except Exception as e:
        logger.error(f"Error exporting data to {file_path}: {e}")


def main():
    """Main function with improved error handling"""
    start_time = time.time()
    args = parse_args()

    # Set configuration
    config.BASE_DIR = args.dir
    output_dir = args.output

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Check if output files are writable before starting processing
    logger.info("Checking if output files are writable...")
    is_writable, issues = check_output_files_writable(output_dir, args)
    if not is_writable:
        logger.error("=" * 80)
        logger.error("OUTPUT FILES ARE NOT WRITABLE - Please close the following files:")
        logger.error("=" * 80)
        for issue in issues:
            logger.error(f"  - {issue}")
        logger.error("=" * 80)
        logger.error("Processing will fail at the end if files remain open.")
        logger.error("Please close the files and try again.")
        return 1

    # Initialize registry
    registry = ModelRegistry()

    try:
        # Parse manifest files to get module dependencies
        logger.info("Parsing manifest files...")
        manifest_dependencies = parse_manifest_files(config.BASE_DIR)
        logger.info(f"Found {len(manifest_dependencies)} modules with manifest dependencies")

        # Get list of modules to process if custom-only is specified
        if args.custom_only:
            custom_modules = get_custom_modules(config.BASE_DIR)
            custom_module_paths = [module['path'] for module in custom_modules]
            logger.info(f"Focusing on {len(custom_module_paths)} custom modules")
        else:
            custom_module_paths = [config.BASE_DIR]  # Process everything

        # Parse Python files to extract model and field definitions
        logger.info("Parsing Python files...")
        all_fields = []
        all_method_overrides = []
        all_methods = []

        for module_path in custom_module_paths:
            try:
                logger.info(f"Processing Python files in {module_path}")
                if args.skip_problematic:
                    # Use safer file filtering
                    python_files = get_safe_files(module_path, '.py', exclude_patterns=['test_', 'demo_'])

                    # Process files individually to avoid one bad file breaking everything
                    for file_path in python_files:
                        try:
                            fields, method_overrides, methods = parse_python_files([file_path], registry)
                            all_fields.extend(fields)
                            all_method_overrides.extend(method_overrides)
                            all_methods.extend(methods)
                        except Exception as e:
                            logger.error(f"Error processing Python file {file_path}: {e}")
                            continue
                else:
                    # Process entire module
                    fields, method_overrides, methods = parse_python_files(module_path, registry)
                    all_fields.extend(fields)
                    all_method_overrides.extend(method_overrides)
                    all_methods.extend(methods)
            except Exception as e:
                logger.error(f"Error processing Python files in module {module_path}: {e}")
                logger.error(traceback.format_exc())

        logger.info(f"Found {len(all_fields)} field definitions, {len(all_method_overrides)} method overrides, and {len(all_methods)} total methods")

        # Set manifest dependencies in registry for module priority calculation
        registry.set_manifest_dependencies(manifest_dependencies)

        # Normalize field keys to use root/original owner models
        # This ensures consistent field identification and tracks root modules
        # Uses manifest dependencies to determine which module is the "root" when multiple exist
        logger.info("Normalizing field keys to use root owner models...")
        registry.normalize_field_keys()
        logger.info("Field key normalization completed")

        # Parse XML files to extract field usage
        logger.info("Parsing XML files...")
        field_usage = {}

        for module_path in custom_module_paths:
            try:
                logger.info(f"Processing XML files in {module_path}")
                if args.skip_problematic:
                    # Use safer file filtering
                    xml_files = get_safe_files(module_path, '.xml', exclude_patterns=['test_', 'demo_'])

                    # Process files individually
                    for file_path in xml_files:
                        try:
                            file_usage = parse_xml_files([file_path], registry)
                            # Merge file usage with overall usage
                            for field_key, usages in file_usage.items():
                                if field_key not in field_usage:
                                    field_usage[field_key] = []
                                field_usage[field_key].extend(usages)
                        except Exception as e:
                            logger.error(f"Error processing XML file {file_path}: {e}")
                            continue
                else:
                    # Process entire module
                    module_usage = parse_xml_files(module_path, registry)
                    # Merge module usage with overall usage
                    for field_key, usages in module_usage.items():
                        if field_key not in field_usage:
                            field_usage[field_key] = []
                        field_usage[field_key].extend(usages)
            except Exception as e:
                logger.error(f"Error processing XML files in module {module_path}: {e}")
                logger.error(traceback.format_exc())

        logger.info(f"Found {len(field_usage)} unique field references in XML files")

        # Export basic field definitions
        # Collect all fields from registry after normalization to ensure correct root_module and is_extension
        field_list = []
        
        # Get eligible modules from config for is_eligible_module flag
        eligible_modules = set(config.ELIGIBLE_MODULES_FOR_CORE) if config.ELIGIBLE_MODULES_FOR_CORE else set()
        
        for model_name, model_fields in registry.fields.items():
            for field_name, fields_list in model_fields.items():
                for field in fields_list:
                    try:
                        # Pass eligible_modules and field_usage to populate usage stats and eligible flag
                        field_dict = field.to_dict(eligible_modules=eligible_modules, field_usage=field_usage)
                        field_list.append(field_dict)
                    except Exception as e:
                        logger.error(f"Error converting field to dict: {e}")
        
        # Generate module summary for eligible modules
        try:
            logger.info("Generating module summary for eligible modules...")
            generate_module_summary(output_dir, registry, field_list, all_methods, eligible_modules)
        except Exception as e:
            logger.error(f"Error generating module summary: {e}")
            logger.error(traceback.format_exc())

        if field_list:
            # Ensure all fields have the same keys (handle cases where some fields might not have root_module set yet)
            all_keys = set()
            for field_dict in field_list:
                all_keys.update(field_dict.keys())
            # Use a consistent order - removed dependency_fields, added is_eligible_module and is_redundant_extension
            field_keys = ['model', 'field_name', 'field_key', 'field_type', 'attributes', 'defined_in', 
                         'module', 'root_module', 'root_model', 'extending_modules', 'is_eligible_module',
                         'is_computed', 'is_stored', 'is_related', 
                         'usage_count', 'used_in_modules', 'used_in_views', 
                         'is_extension', 'extended_from', 'added_attributes', 'modified_attributes', 'removed_attributes',
                         'is_redundant_extension']
            # Only include keys that exist in the data
            export_keys = [k for k in field_keys if k in all_keys]
            export_csv(field_list, os.path.join(output_dir, 'fields_analysis.csv'), export_keys)

        # Export method overrides
        export_csv(all_method_overrides, os.path.join(output_dir, 'method_overrides.csv'),
                   ['class', 'model', 'method', 'file_path', 'module'])
        
        # Export csl_* module models
        try:
            export_csl_models(registry, output_dir, base_dir=config.BASE_DIR)
        except Exception as e:
            logger.error(f"Error exporting csl_* models: {e}")
            logger.error(traceback.format_exc())
        
        # Export model inheritance relationships
        inheritance_data = []
        
        # First, handle models with _name that inherit other models
        for model_name, inherited_models in registry.inherits.items():
            if model_name in registry.models:
                model_module = registry.models[model_name].get('module', 'unknown')
                for inherited_model in inherited_models:
                    # Skip None values
                    if not inherited_model:
                        continue
                    # Get inherited module - may not be in registry if it's a standard Odoo model
                    inherited_module = 'unknown'
                    if inherited_model and isinstance(inherited_model, str) and inherited_model in registry.models:
                        inherited_module = registry.models[inherited_model].get('module', 'unknown')
                    elif inherited_model and isinstance(inherited_model, str):
                        # Infer from model name (e.g., "mail.thread" -> "mail", "product.template" -> "product")
                        if '.' in inherited_model:
                            model_prefix = inherited_model.split('.')[0]
                            # Check if it's a known standard Odoo module
                            if model_prefix in ['mail', 'product', 'sale', 'purchase', 'account', 'stock', 
                                               'project', 'hr', 'base', 'web', 'portal', 'website']:
                                inherited_module = model_prefix
                    
                    inheritance_data.append({
                        'model': model_name,
                        'module': model_module,
                        'inherited_model': inherited_model,
                        'inherited_module': inherited_module
                    })
        
        # Also handle extension-only classes (no _name, just _inherit)
        for module, extensions in registry.module_extensions.items():
            for model_name, inherited_model in extensions:
                # Skip None values
                if not model_name or not inherited_model:
                    continue
                # Get inherited module - may not be in registry if it's a standard Odoo model
                inherited_module = 'unknown'
                if inherited_model and isinstance(inherited_model, str) and inherited_model in registry.models:
                    inherited_module = registry.models[inherited_model].get('module', 'unknown')
                elif inherited_model and isinstance(inherited_model, str):
                    # Infer from model name
                    if '.' in inherited_model:
                        model_prefix = inherited_model.split('.')[0]
                        if model_prefix in ['mail', 'product', 'sale', 'purchase', 'account', 'stock', 
                                           'project', 'hr', 'base', 'web', 'portal', 'website']:
                            inherited_module = model_prefix
                
                inheritance_data.append({
                    'model': model_name,
                    'module': module,
                    'inherited_model': inherited_model,
                    'inherited_module': inherited_module
                })
        
        if inheritance_data:
            export_csv(inheritance_data, os.path.join(output_dir, 'model_inheritance.csv'),
                      ['model', 'module', 'inherited_model', 'inherited_module'])

        # Export field usage
        field_usage_list = []
        for field_key, usages in field_usage.items():
            for usage in usages:
                field_usage_list.append(usage)

        if field_usage_list:
            export_csv(field_usage_list, os.path.join(output_dir, 'field_usage.csv'),
                       field_usage_list[0].keys())

        # Advanced analysis using ModuleAnalyzer
        if args.analyze_sharing or args.identify_core:
            try:
                logger.info("Starting advanced analysis...")
                analyzer = ModuleAnalyzer(registry, field_usage, manifest_dependencies)

                # Analyze field sharing across modules
                if args.analyze_sharing:
                    try:
                        logger.info("Analyzing field sharing across modules...")
                        shared_fields = analyzer.analyze_field_sharing()
                        export_csv(shared_fields, os.path.join(output_dir, 'shared_fields.csv'),
                                   ['field_key', 'model', 'field_name', 'used_in_modules', 'defined_in_module',
                                    'root_module', 'extending_modules', 'usage_count'])
                        
                        # Analyze field dependencies for csl_core consolidation
                        try:
                            logger.info("Analyzing field dependencies for csl_core consolidation...")
                            field_dependencies = analyzer.analyze_field_dependencies_for_core()
                            
                            # Export detailed field dependencies
                            field_dep_list = []
                            for dep_info in field_dependencies:
                                for field_info in dep_info['fields']:
                                    field_dep_list.append(field_info)
                            
                            if field_dep_list:
                                export_csv(field_dep_list, os.path.join(output_dir, 'field_dependencies.csv'),
                                          ['field_key', 'root_model', 'field_name', 'root_module', 
                                           'defined_in_module', 'extending_modules', 'is_extension',
                                           'field_type', 'used_in_modules', 'usage_count'])
                            
                            # Export summary by root module
                            dep_summary = []
                            for dep_info in field_dependencies:
                                dep_summary.append({
                                    'root_module': dep_info['root_module'],
                                    'field_count': dep_info['field_count'],
                                    'extending_modules': dep_info['extending_modules']
                                })
                            
                            if dep_summary:
                                export_csv(dep_summary, os.path.join(output_dir, 'field_dependencies_summary.csv'),
                                          ['root_module', 'field_count', 'extending_modules'])
                        except Exception as e:
                            logger.error(f"Error analyzing field dependencies: {e}")
                            logger.error(traceback.format_exc())

                        # Analyze view field usage
                        try:
                            view_analysis = analyzer.analyze_view_field_usage()
                            export_csv(view_analysis, os.path.join(output_dir, 'view_field_analysis.csv'),
                                       ['field_key', 'view_modules', 'data_modules', 'shared_between',
                                        'recommendation'])
                        except Exception as e:
                            logger.error(f"Error analyzing view field usage: {e}")
                    except Exception as e:
                        logger.error(f"Error analyzing field sharing: {e}")
                        logger.error(traceback.format_exc())

                # Identify fields that should be in core module
                if args.identify_core:
                    try:
                        logger.info("Identifying fields that should be in core module...")
                        core_candidates = analyzer.identify_core_candidates()
                        export_csv(core_candidates, os.path.join(output_dir, 'core_candidates.csv'),
                                   ['type', 'key', 'current_module', 'used_in', 'reason'])

                        # Analyze business logic methods
                        try:
                            shared_methods = analyzer.analyze_business_logic_methods(all_method_overrides)
                            export_csv(shared_methods, os.path.join(output_dir, 'shared_methods.csv'),
                                       ['key', 'model', 'method', 'modules', 'recommendation'])
                        except Exception as e:
                            logger.error(f"Error analyzing shared methods: {e}")

                        # Identify utility method candidates
                        try:
                            utility_candidates = analyzer.identify_utility_candidates(all_method_overrides)
                            export_csv(utility_candidates, os.path.join(output_dir, 'utility_candidates.csv'),
                                       ['key', 'model', 'method', 'module', 'file_path', 'reason'])
                        except Exception as e:
                            logger.error(f"Error identifying utility candidates: {e}")
                    except Exception as e:
                        logger.error(f"Error identifying core candidates: {e}")
                        logger.error(traceback.format_exc())
            except Exception as e:
                logger.error(f"Error in advanced analysis: {e}")
                logger.error(traceback.format_exc())

        # Generate restructuring recommendations if requested
        if args.generate_recommendations:
            try:
                logger.info("Generating restructuring recommendations for csl_core...")
                # Use command-line eligible modules if provided, otherwise use config/auto-detect
                eligible_modules = args.eligible_modules
                if eligible_modules:
                    logger.info(f"Using specified eligible modules: {eligible_modules}")
                generate_restructuring_recommendations(output_dir, output_dir, eligible_modules)
                logger.info("Restructuring recommendations generated successfully")
            except Exception as e:
                logger.error(f"Error generating recommendations: {e}")
                logger.error(traceback.format_exc())
        
        # Analyze module consolidation opportunities if requested
        if args.analyze_consolidation:
            try:
                logger.info("Analyzing module consolidation opportunities...")
                # Use command-line eligible modules if provided, otherwise use config
                eligible_modules = args.eligible_modules
                if eligible_modules:
                    logger.info(f"Using specified eligible modules for consolidation: {eligible_modules}")
                analyze_module_consolidation(output_dir, output_dir, eligible_modules)
                logger.info("Module consolidation analysis completed successfully")
            except Exception as e:
                logger.error(f"Error analyzing module consolidation: {e}")
                logger.error(traceback.format_exc())
        
        # Perform migration analysis if requested
        if args.analyze_migration:
            try:
                logger.info("=" * 80)
                logger.info("PERFORMING MIGRATION ANALYSIS")
                logger.info("=" * 80)
                # Use command-line eligible modules if provided, otherwise use config
                eligible_modules = args.eligible_modules
                if not eligible_modules:
                    eligible_modules = config.ELIGIBLE_MODULES_FOR_CORE if config.ELIGIBLE_MODULES_FOR_CORE else []
                
                if eligible_modules:
                    logger.info(f"Using eligible modules: {eligible_modules}")
                    analyze_migration(
                        args.original_dir,
                        args.new_dir,
                        output_dir,
                        eligible_modules
                    )
                    logger.info("Migration analysis completed successfully")
                else:
                    logger.warning("No eligible modules specified - skipping migration analysis")
            except Exception as e:
                logger.error(f"Error performing migration analysis: {e}")
                logger.error(traceback.format_exc())

        # Report execution time
        elapsed_time = time.time() - start_time
        logger.info(f"Analysis completed in {elapsed_time:.2f} seconds. Results exported to {output_dir}")
        return 0
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == '__main__':
    sys.exit(main())