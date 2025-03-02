#!/usr/bin/env python3
"""Main entry point for the Odoo analyzer"""
import argparse
import logging
import os
from . import config
from .models import ModelRegistry
from .parsers import parse_python_files, parse_xml_files, parse_manifest_files
from .analysis import (analyze_module_dependencies, analyze_unused_fields,
                      analyze_shared_fields, analyze_module_organization)
from .exporters import export_results
from .utils.log_utils import setup_logging

def main():
    """Main analysis function"""
    parser = argparse.ArgumentParser(description='Analyze Odoo codebase for module reorganization')
    parser.add_argument('--path', type=str, help='Path to custom modules directory')
    parser.add_argument('--output', type=str, help='Output directory for reports', default='analysis_results')
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO')
    args = parser.parse_args()

    # Update the global config
    config.BASE_DIR = args.path

    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Use the directory path from command line
    base_dir = args.path
    output_dir = args.output

    logger.info(f"Starting Odoo codebase analysis for: {base_dir}")
    logger.info(f"Results will be saved to: {output_dir}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Create model registry
    registry = ModelRegistry()

    # Run analysis phases
    all_fields, all_method_overrides = parse_python_files(base_dir, registry)
    field_usage = parse_xml_files(base_dir, registry)
    manifest_dependencies = parse_manifest_files(base_dir)

    # Run analysis
    inheritance_dependencies = analyze_module_dependencies(registry, manifest_dependencies)
    unused_fields = analyze_unused_fields(all_fields, field_usage)
    shared_fields = analyze_shared_fields(all_fields, field_usage)
    org_recommendations = analyze_module_organization(all_fields, field_usage, registry)

    # Export results
    export_results(
        output_dir=output_dir,
        all_fields=all_fields,
        field_usage=field_usage,
        method_overrides=all_method_overrides,
        manifest_dependencies=manifest_dependencies,
        inheritance_dependencies=inheritance_dependencies,
        unused_fields=unused_fields,
        shared_fields=shared_fields,
        organization_recommendations=org_recommendations
    )

    # Print summary
    logger.info("\nAnalysis Summary:")
    logger.info(f"- Total fields: {len(all_fields)}")
    logger.info(f"- Unused fields: {len(unused_fields)}")
    logger.info(f"- Shared fields: {len(shared_fields)}")
    logger.info(f"- Fields to move to core: {len(org_recommendations['fields_to_move'])}")
    logger.info(f"- Method overrides: {len(all_method_overrides)}")
    logger.info(f"- Modules: {len(manifest_dependencies)}")

    logger.info(f"\nAnalysis complete. Results available in: {output_dir}")

if __name__ == '__main__':
    main()
