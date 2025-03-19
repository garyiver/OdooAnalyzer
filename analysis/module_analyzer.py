"""Module analyzer for field sharing and reorganization"""
import logging
import csv
import os
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

class ModuleAnalyzer:
    """
    Analyzes module structure and field usage to identify candidates for reorganization
    """

    def __init__(self, registry, field_usage, manifest_dependencies):
        self.registry = registry
        self.field_usage = field_usage
        self.manifest_dependencies = manifest_dependencies
        self.field_to_modules = defaultdict(set)
        self.shared_fields = []
        self.core_candidates = []
        self.module_dependencies = self._build_module_dependency_graph()

    def _build_module_dependency_graph(self):
        """Build module dependency graph from manifest dependencies"""
        dependencies = defaultdict(set)
        for module_info in self.manifest_dependencies:
            module = module_info['module']
            for dep in module_info.get('dependencies', []):
                dependencies[module].add(dep)
        return dependencies

    def analyze_field_sharing(self):
        """Analyze field usage to identify shared fields across modules"""
        logger.info("Analyzing field sharing across modules...")

        # Build field to modules mapping
        for field_key, usages in self.field_usage.items():
            modules = set()
            for usage in usages:
                modules.add(usage['module'])

            self.field_to_modules[field_key] = modules

            # Fields used in multiple modules are shared
            if len(modules) > 1:
                field_parts = field_key.split('.')
                if len(field_parts) >= 2:  # Ensure it's a valid field_key with model.field_name
                    model = '.'.join(field_parts[:-1])
                    field_name = field_parts[-1]

                    # Find the field definition for additional info
                    field_def = self.registry.get_field(model, field_name)
                    defined_module = field_def.module if field_def else "unknown"

                    self.shared_fields.append({
                        'field_key': field_key,
                        'model': model,
                        'field_name': field_name,
                        'used_in_modules': ', '.join(modules),
                        'defined_in_module': defined_module,
                        'usage_count': len(usages)
                    })

        logger.info(f"Found {len(self.shared_fields)} shared fields across modules")
        return self.shared_fields

    def identify_core_candidates(self):
        """Identify fields and models that should be moved to core module"""
        logger.info("Identifying candidates for core module...")

        # First, find fields defined in one module but used in multiple modules
        for field_info in self.shared_fields:
            field_key = field_info['field_key']
            defined_module = field_info['defined_in_module']
            used_modules = set(field_info['used_in_modules'].split(', '))

            # If field is defined in one module but used in others, it's a candidate for core
            if defined_module != "unknown" and defined_module in used_modules and len(used_modules) > 1:
                self.core_candidates.append({
                    'type': 'field',
                    'key': field_key,
                    'current_module': defined_module,
                    'used_in': ', '.join(used_modules),
                    'reason': 'Used in multiple modules'
                })

        # Also check for models that should be entirely in core
        core_models = set()
        for model, fields in self.registry.fields.items():
            # If all fields of a model are candidates for core, the whole model could move
            if len(fields) > 1:
                model_field_keys = {f"{model}.{field.name}" for field in fields.values()}
                candidate_keys = {c['key'] for c in self.core_candidates if c['type'] == 'field'}

                if model_field_keys.issubset(candidate_keys):
                    # All fields are candidates, so consider moving the whole model
                    # Find the module where the model is defined
                    model_info = self.registry.models.get(model)
                    if model_info:
                        module = model_info['module']
                        core_models.add(model)

                        self.core_candidates.append({
                            'type': 'model',
                            'key': model,
                            'current_module': module,
                            'used_in': ', '.join({c['used_in'] for c in self.core_candidates
                                                  if c['type'] == 'field' and c['key'].startswith(f"{model}.")}),
                            'reason': 'All fields used in multiple modules'
                        })

        # Remove field candidates for models that we're moving entirely
        self.core_candidates = [c for c in self.core_candidates
                                if c['type'] != 'field' or
                                not any(c['key'].startswith(f"{model}.") for model in core_models)]

        logger.info(f"Identified {len(self.core_candidates)} candidates for core module")
        return self.core_candidates

    def analyze_view_field_usage(self):
        """Analyze field usage in views vs data records"""
        view_fields = defaultdict(set)
        data_fields = defaultdict(set)

        # Group field usage by record type
        for field_key, usages in self.field_usage.items():
            for usage in usages:
                module = usage['module']
                record_type = usage.get('record_type', 'unknown')

                if record_type == 'view':
                    view_fields[field_key].add(module)
                elif record_type == 'data':
                    data_fields[field_key].add(module)

        # Find fields used in views in one module but as data in others
        analysis = []
        for field_key, view_modules in view_fields.items():
            data_modules = data_fields.get(field_key, set())

            if view_modules and data_modules:
                # Fields used in views in some modules and in data in others
                analysis.append({
                    'field_key': field_key,
                    'view_modules': ', '.join(view_modules),
                    'data_modules': ', '.join(data_modules),
                    'shared_between': 'both',
                    'recommendation': 'Move field definition to core'
                })
            elif len(view_modules) > 1:
                # Fields used in views in multiple modules
                analysis.append({
                    'field_key': field_key,
                    'view_modules': ', '.join(view_modules),
                    'data_modules': '',
                    'shared_between': 'views',
                    'recommendation': 'Consider moving field definition to core if views manipulate same data'
                })

        logger.info(f"Analyzed {len(analysis)} fields used in views across modules")
        return analysis

    def analyze_business_logic_methods(self, method_overrides):
        """Analyze business logic methods to identify shared functionality"""
        # Group methods by name and model
        method_groups = defaultdict(list)
        for method in method_overrides:
            key = f"{method['model']}.{method['method']}"
            method_groups[key].append(method)

        # Find methods implemented in multiple modules
        shared_methods = []
        for key, methods in method_groups.items():
            if len(methods) > 1:
                modules = {m['module'] for m in methods}
                if len(modules) > 1:
                    model = methods[0]['model']
                    method_name = methods[0]['method']

                    shared_methods.append({
                        'key': key,
                        'model': model,
                        'method': method_name,
                        'modules': ', '.join(modules),
                        'recommendation': 'Review for possible utility method extraction'
                    })

        logger.info(f"Found {len(shared_methods)} methods shared across modules")
        return shared_methods

    def identify_utility_candidates(self, method_overrides):
        """Identify potential utility methods"""
        utility_candidates = []

        # Look for methods with generic names suggesting utility functions
        utility_keywords = ['get', 'compute', 'calculate', 'format', 'validate', 'check', 'helper', 'util']

        for method in method_overrides:
            method_name = method['method']

            # Check if the method name suggests a utility function
            if any(keyword in method_name.lower() for keyword in utility_keywords):
                # Further analyze to see if it's standalone (few dependencies)
                utility_candidates.append({
                    'key': f"{method['model']}.{method_name}",
                    'model': method['model'],
                    'method': method_name,
                    'module': method['module'],
                    'file_path': method['file_path'],
                    'reason': 'Name suggests utility function'
                })

        logger.info(f"Identified {len(utility_candidates)} potential utility methods")
        return utility_candidates

    def export_analysis(self, output_dir):
        """Export analysis results to CSV files"""
        os.makedirs(output_dir, exist_ok=True)

        # Export shared fields
        self.export_to_csv(
            os.path.join(output_dir, "shared_fields.csv"),
            self.shared_fields,
            ['field_key', 'model', 'field_name', 'used_in_modules', 'defined_in_module', 'usage_count']
        )

        # Export core candidates
        self.export_to_csv(
            os.path.join(output_dir, "core_candidates.csv"),
            self.core_candidates,
            ['type', 'key', 'current_module', 'used_in', 'reason']
        )

        # Export view field usage analysis
        view_analysis = self.analyze_view_field_usage()
        self.export_to_csv(
            os.path.join(output_dir, "view_field_analysis.csv"),
            view_analysis,
            ['field_key', 'view_modules', 'data_modules', 'shared_between', 'recommendation']
        )

        logger.info(f"Analysis results exported to {output_dir}")

    @staticmethod
    def export_to_csv(file_path, data, fieldnames):
        """Export data to CSV file"""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                # Ensure all fields are present
                row_dict = {field: row.get(field, '') for field in fieldnames}
                writer.writerow(row_dict)