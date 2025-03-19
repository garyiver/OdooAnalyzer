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

from models.registry import ModelRegistry
from parsers.manifest_parser import parse_manifest_files
from parsers.python_parser import parse_python_files
from parsers.xml_parser import parse_xml_files
from analysis.module_analyzer import ModuleAnalyzer
from utils.file_utils import get_safe_files, get_custom_modules
from utils.cycle_management import CycleManager

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

    # Add cycle detection options
    parser.add_argument('--cycle-verbosity', choices=['low', 'medium', 'high'], default='low',
                        help='Control verbosity of inheritance cycle detection logs')
    parser.add_argument('--analyze-cycles', action='store_true',
                        help='Perform a dedicated analysis of inheritance cycles')

    return parser.parse_args()


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

    # Initialize registry
    registry = ModelRegistry()

    # Initialize cycle manager with specified verbosity
    cycle_manager = CycleManager(verbosity=args.cycle_verbosity)

    # Pass the cycle manager to the registry
    registry.cycle_manager = cycle_manager

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

        for module_path in custom_module_paths:
            try:
                logger.info(f"Processing Python files in {module_path}")
                if args.skip_problematic:
                    # Use safer file filtering
                    python_files = get_safe_files(module_path, '.py', exclude_patterns=['test_', 'demo_'])

                    # Process files individually to avoid one bad file breaking everything
                    for file_path in python_files:
                        try:
                            fields, method_overrides = parse_python_files([file_path], registry)
                            all_fields.extend(fields)
                            all_method_overrides.extend(method_overrides)
                        except Exception as e:
                            logger.error(f"Error processing Python file {file_path}: {e}")
                            continue
                else:
                    # Process entire module
                    fields, method_overrides = parse_python_files(module_path, registry)
                    all_fields.extend(fields)
                    all_method_overrides.extend(method_overrides)
            except Exception as e:
                logger.error(f"Error processing Python files in module {module_path}: {e}")
                logger.error(traceback.format_exc())

        logger.info(f"Found {len(all_fields)} field definitions and {len(all_method_overrides)} method overrides")

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
        field_list = []
        for field in all_fields:
            try:
                field_list.append(field.to_dict())
            except Exception as e:
                logger.error(f"Error converting field to dict: {e}")

        if field_list:
            export_csv(field_list, os.path.join(output_dir, 'fields.csv'), field_list[0].keys())

        # Export method overrides
        export_csv(all_method_overrides, os.path.join(output_dir, 'method_overrides.csv'),
                   ['class', 'model', 'method', 'file_path', 'module'])

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
                                    'usage_count'])

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

        # Report execution time
        elapsed_time = time.time() - start_time
        logger.info(f"Analysis completed in {elapsed_time:.2f} seconds. Results exported to {output_dir}")
        return 0
    except Exception as e:
        logger.error(f"Unhandled exception in main: {e}")
        logger.error(traceback.format_exc())
        return 1

    # Log cycle summary
    cycle_manager.log_summary()

    # Export cycle information
    cycle_manager.export_to_csv(output_dir)

    # Perform dedicated cycle analysis if requested
    if args.analyze_cycles:
        logger.info("Performing dedicated inheritance cycle analysis...")
        cycles = registry.analyze_inheritance_structure()

        # Export detailed cycle analysis
        export_csv(
            [{'cycle': ' -> '.join(cycle)} for cycle in cycles],
            os.path.join(output_dir, 'inheritance_cycle_analysis.csv'),
            ['cycle']
        )

if __name__ == '__main__':
    sys.exit(main())