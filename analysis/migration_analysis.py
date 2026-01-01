"""
Migration Analysis Tool - Compares original and migrated codebases
to identify missing fields, views, and field usage in views
"""
import csv
import logging
import os
from collections import defaultdict
from pathlib import Path

from models.registry import ModelRegistry
from parsers.python_parser import parse_python_files
from parsers.xml_parser import parse_xml_file, extract_view_definitions
from utils.file_utils import get_module_name

logger = logging.getLogger(__name__)


class MigrationAnalyzer:
    """Analyzes migration differences between original and new codebases"""
    
    def __init__(self, original_dir, new_dir, eligible_modules):
        """
        Initialize the migration analyzer
        
        Args:
            original_dir: Path to original codebase (e.g., C:\\Odoo\\sh\\src\\user)
            new_dir: Path to new codebase (e.g., C:\\Cursor\\Odoo\\csl_addons\\odoo)
            eligible_modules: Set of eligible module names to analyze
        """
        self.original_dir = original_dir
        self.new_dir = new_dir
        self.eligible_modules = set(eligible_modules) if eligible_modules else set()
        
        # Data structures for original codebase
        self.original_registry = ModelRegistry()
        self.original_fields = {}  # field_key -> field_info
        self.original_views = {}  # view_id -> view_info
        self.original_view_fields = defaultdict(set)  # view_id -> set of field_keys
        
        # Data structures for new codebase
        self.new_registry = ModelRegistry()
        self.new_fields = {}  # field_key -> field_info
        self.new_views = {}  # view_id -> view_info
        self.new_view_fields = defaultdict(set)  # view_id -> set of field_keys
        
    def analyze(self):
        """Perform the complete analysis of both codebases"""
        logger.info("=" * 80)
        logger.info("MIGRATION ANALYSIS - Starting")
        logger.info(f"Original codebase: {self.original_dir}")
        logger.info(f"New codebase: {self.new_dir}")
        logger.info(f"Eligible modules: {sorted(self.eligible_modules)}")
        logger.info("=" * 80)
        
        # Analyze original codebase
        logger.info("\n" + "=" * 80)
        logger.info("ANALYZING ORIGINAL CODEBASE")
        logger.info("=" * 80)
        self._analyze_codebase(self.original_dir, self.original_registry, 
                              self.original_fields, self.original_views, 
                              self.original_view_fields, "original")
        
        # Analyze new codebase
        logger.info("\n" + "=" * 80)
        logger.info("ANALYZING NEW CODEBASE")
        logger.info("=" * 80)
        self._analyze_codebase(self.new_dir, self.new_registry, 
                              self.new_fields, self.new_views, 
                              self.new_view_fields, "new")
        
        # Compare and generate report
        logger.info("\n" + "=" * 80)
        logger.info("COMPARING CODEBASES")
        logger.info("=" * 80)
        return self._generate_comparison_report()
    
    def _analyze_codebase(self, base_dir, registry, fields_dict, views_dict, view_fields_dict, label):
        """Analyze a single codebase"""
        logger.info(f"Parsing Python files in {base_dir}...")
        
        # Parse Python files to get fields
        all_fields = []
        all_method_overrides = []
        all_methods = []
        
        try:
            fields, method_overrides, methods = parse_python_files(base_dir, registry)
            all_fields.extend(fields)
            all_method_overrides.extend(method_overrides)
            all_methods.extend(methods)
        except Exception as e:
            logger.error(f"Error parsing Python files: {e}")
        
        logger.info(f"Found {len(all_fields)} fields, {len(all_method_overrides)} method overrides, {len(all_methods)} methods")
        
        # Normalize field keys
        logger.info("Normalizing field keys...")
        registry.normalize_field_keys()
        
        # Filter fields by eligible modules and store
        for field in all_fields:
            module = field.module
            root_module = field.root_module if field.root_module else module
            
            if module in self.eligible_modules or root_module in self.eligible_modules:
                field_key = field.field_key
                fields_dict[field_key] = {
                    'field_key': field_key,
                    'model': field.model,
                    'field_name': field.name,
                    'field_type': field.field_type,
                    'module': module,
                    'root_module': root_module,
                    'file_path': field.file_path,
                    'is_extension': field.is_extension
                }
        
        logger.info(f"Stored {len(fields_dict)} fields from eligible modules")
        
        # Parse XML files to get views and field usage
        logger.info(f"Parsing XML files in {base_dir}...")
        field_usage = {}
        
        try:
            # Get all XML files
            xml_files = []
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    if file.endswith('.xml'):
                        xml_files.append(os.path.join(root, file))
            
            logger.info(f"Found {len(xml_files)} XML files")
            
            # Process each XML file
            for xml_file in xml_files:
                try:
                    module = get_module_name(xml_file)
                    if module not in self.eligible_modules:
                        continue
                    
                    # Extract views and field usage - parse_xml_file does both
                    try:
                        file_usage = parse_xml_file(xml_file, registry)
                        for field_key, usages in file_usage.items():
                            if field_key not in field_usage:
                                field_usage[field_key] = []
                            field_usage[field_key].extend(usages)
                    except Exception as e:
                        logger.debug(f"Error processing XML file {xml_file}: {e}")
                        
                except Exception as e:
                    logger.debug(f"Error processing XML file {xml_file}: {e}")
        
        except Exception as e:
            logger.error(f"Error parsing XML files: {e}")
        
        # Store views from eligible modules
        for view_id, view_info in registry.views.items():
            # Extract module from view_id (format: module.view_id)
            if '.' in view_id:
                module = view_id.split('.')[0]
                if module in self.eligible_modules:
                    views_dict[view_id] = {
                        'view_id': view_id,
                        'model': view_info.get('model', ''),
                        'inherit_id': view_info.get('inherit_id', ''),
                        'view_type': view_info.get('view_type', '')
                    }
        
        logger.info(f"Stored {len(views_dict)} views from eligible modules")
        
        # Store field usage in views
        # Note: parse_xml_file returns dicts, not FieldUsage objects
        for field_key, usages in field_usage.items():
            for usage in usages:
                # usage is a dict from to_dict()
                record_type = usage.get('record_type', '')
                if record_type == 'view':
                    view_id = usage.get('context', '')
                    if view_id:
                        # Try to find view_id in views_dict (might need to check with/without module prefix)
                        if view_id in views_dict:
                            view_fields_dict[view_id].add(field_key)
                        else:
                            # Try to find by matching the end of the view_id
                            for vid in views_dict.keys():
                                if view_id.endswith(vid) or vid.endswith(view_id):
                                    view_fields_dict[vid].add(field_key)
                                    break
        
        logger.info(f"Stored field usage for {len(view_fields_dict)} views")
    
    def _generate_comparison_report(self):
        """Generate comparison report showing what's missing in new codebase"""
        logger.info("Generating comparison report...")
        
        report = {
            'missing_fields': [],
            'missing_views': [],
            'missing_view_fields': []
        }
        
        # Find missing fields
        for field_key, field_info in self.original_fields.items():
            if field_key not in self.new_fields:
                report['missing_fields'].append({
                    'field_key': field_key,
                    'model': field_info['model'],
                    'field_name': field_info['field_name'],
                    'field_type': field_info['field_type'],
                    'module': field_info['module'],
                    'root_module': field_info['root_module'],
                    'original_file': field_info['file_path'],
                    'is_extension': field_info['is_extension']
                })
        
        logger.info(f"Found {len(report['missing_fields'])} missing fields")
        
        # Find missing views
        for view_id, view_info in self.original_views.items():
            if view_id not in self.new_views:
                report['missing_views'].append({
                    'view_id': view_id,
                    'model': view_info['model'],
                    'inherit_id': view_info['inherit_id'],
                    'view_type': view_info['view_type']
                })
        
        logger.info(f"Found {len(report['missing_views'])} missing views")
        
        # Find fields missing from views
        for view_id, field_keys in self.original_view_fields.items():
            if view_id in self.new_views:
                # View exists in new codebase, check if fields are missing
                new_fields = self.new_view_fields.get(view_id, set())
                missing = field_keys - new_fields
                for field_key in missing:
                    # Get field info
                    field_info = self.original_fields.get(field_key, {})
                    report['missing_view_fields'].append({
                        'view_id': view_id,
                        'model': self.original_views[view_id].get('model', ''),
                        'view_type': self.original_views[view_id].get('view_type', ''),
                        'field_key': field_key,
                        'field_name': field_info.get('field_name', ''),
                        'module': field_info.get('module', '')
                    })
            else:
                # View is completely missing - all its fields are missing
                for field_key in field_keys:
                    field_info = self.original_fields.get(field_key, {})
                    report['missing_view_fields'].append({
                        'view_id': view_id,
                        'model': self.original_views[view_id].get('model', ''),
                        'view_type': self.original_views[view_id].get('view_type', ''),
                        'field_key': field_key,
                        'field_name': field_info.get('field_name', ''),
                        'module': field_info.get('module', ''),
                        'note': 'View is completely missing'
                    })
        
        logger.info(f"Found {len(report['missing_view_fields'])} missing field references in views")
        
        return report
    
    def export_report(self, output_dir, report):
        """Export the comparison report to CSV files"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Export missing fields
        if report['missing_fields']:
            output_file = os.path.join(output_dir, 'migration_missing_fields.csv')
            fieldnames = ['field_key', 'model', 'field_name', 'field_type', 'module', 
                         'root_module', 'original_file', 'is_extension']
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in report['missing_fields']:
                        writer.writerow(row)
                logger.info(f"Exported {len(report['missing_fields'])} missing fields to {output_file}")
            except Exception as e:
                logger.error(f"Error exporting missing fields: {e}")
        
        # Export missing views
        if report['missing_views']:
            output_file = os.path.join(output_dir, 'migration_missing_views.csv')
            fieldnames = ['view_id', 'model', 'inherit_id', 'view_type']
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in report['missing_views']:
                        writer.writerow(row)
                logger.info(f"Exported {len(report['missing_views'])} missing views to {output_file}")
            except Exception as e:
                logger.error(f"Error exporting missing views: {e}")
        
        # Export missing view fields
        if report['missing_view_fields']:
            output_file = os.path.join(output_dir, 'migration_missing_view_fields.csv')
            fieldnames = ['view_id', 'model', 'view_type', 'field_key', 'field_name', 'module', 'note']
            try:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in report['missing_view_fields']:
                        # Ensure note field exists
                        if 'note' not in row:
                            row['note'] = ''
                        writer.writerow(row)
                logger.info(f"Exported {len(report['missing_view_fields'])} missing view fields to {output_file}")
            except Exception as e:
                logger.error(f"Error exporting missing view fields: {e}")
        
        # Create summary report
        summary_file = os.path.join(output_dir, 'migration_analysis_summary.txt')
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("MIGRATION ANALYSIS SUMMARY\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Original Codebase: {self.original_dir}\n")
                f.write(f"New Codebase: {self.new_dir}\n")
                f.write(f"Eligible Modules: {', '.join(sorted(self.eligible_modules))}\n\n")
                f.write("=" * 80 + "\n\n")
                f.write("ORIGINAL CODEBASE STATISTICS\n")
                f.write(f"  Fields: {len(self.original_fields)}\n")
                f.write(f"  Views: {len(self.original_views)}\n")
                f.write(f"  Views with fields: {len(self.original_view_fields)}\n\n")
                f.write("NEW CODEBASE STATISTICS\n")
                f.write(f"  Fields: {len(self.new_fields)}\n")
                f.write(f"  Views: {len(self.new_views)}\n")
                f.write(f"  Views with fields: {len(self.new_view_fields)}\n\n")
                f.write("=" * 80 + "\n\n")
                f.write("MISSING ITEMS IN NEW CODEBASE\n")
                f.write(f"  Missing Fields: {len(report['missing_fields'])}\n")
                f.write(f"  Missing Views: {len(report['missing_views'])}\n")
                f.write(f"  Missing Field References in Views: {len(report['missing_view_fields'])}\n\n")
                f.write("=" * 80 + "\n")
                f.write("DETAILED REPORTS\n")
                f.write("  - migration_missing_fields.csv: Fields defined in original but not in new\n")
                f.write("  - migration_missing_views.csv: Views defined in original but not in new\n")
                f.write("  - migration_missing_view_fields.csv: Fields used in views in original but not in new\n")
            logger.info(f"Summary report written to {summary_file}")
        except Exception as e:
            logger.error(f"Error writing summary report: {e}")


def analyze_migration(original_dir, new_dir, output_dir, eligible_modules):
    """
    Main function to analyze migration differences
    
    Args:
        original_dir: Path to original codebase
        new_dir: Path to new codebase
        output_dir: Directory to write output files
        eligible_modules: List of eligible module names
    """
    analyzer = MigrationAnalyzer(original_dir, new_dir, eligible_modules)
    report = analyzer.analyze()
    analyzer.export_report(output_dir, report)
    return report

