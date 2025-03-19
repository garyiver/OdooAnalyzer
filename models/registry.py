"""Enhanced model registry with better inheritance tracking"""
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Registry for tracking Odoo models, fields, and inheritance
    """

    def __init__(self):
        self.models = {}  # model_name -> {class_name, module, file_path}
        self.fields = defaultdict(dict)  # model_name -> {field_name: FieldDefinition}
        self.inherits = defaultdict(list)  # model_name -> [inherited_models]
        self.views = {}  # view_id -> {model, inherit_id, view_type}
        self.class_to_model = {}  # class_name -> model_name
        self.field_owners = {}  # field_name -> {model: original_model} mapping

    def register_model(self, model_name, class_name, module, file_path):
        """Register a model with its class name, module, and file path"""
        self.models[model_name] = {
            'class_name': class_name,
            'module': module,
            'file_path': file_path
        }
        self.class_to_model[class_name] = model_name

    def register_inherit(self, model_name, inherited_model):
        """Register a model inheritance relationship"""
        if inherited_model not in self.inherits[model_name]:
            self.inherits[model_name].append(inherited_model)

    def register_field(self, model_name, field):
        """Register a field definition for a model"""
        self.fields[model_name][field.name] = field

        # Track field ownership for inheritance
        if model_name not in self.field_owners:
            self.field_owners[model_name] = {}

        # If this is an extension, note the original owner
        if field.is_extension and field.extended_from:
            # Field is defined in a parent model
            original_model = self.resolve_field_owner(field.name, model_name, check_existing=False)
            if original_model:
                self.field_owners[model_name][field.name] = original_model
        else:
            # Field is newly defined in this model
            self.field_owners[model_name][field.name] = model_name

    def register_view(self, view_id, model_name, inherit_id=None, view_type=None):
        """Register a view definition"""
        self.views[view_id] = {
            'model': model_name,
            'inherit_id': inherit_id,
            'view_type': view_type
        }

    def get_field(self, model_name, field_name):
        """Get field definition for a model"""
        if model_name in self.fields and field_name in self.fields[model_name]:
            return self.fields[model_name][field_name]
        return None

    def get_model_inheritance_chain(self, model_name, visited=None, path=None):
        """
        Get all models in the inheritance chain for a model with detailed cycle detection

        Args:
            model_name: Model to get inheritance chain for
            visited: Set of already visited models (for cycle detection)
            path: List tracking the inheritance path for detailed logging

        Returns:
            List of models in inheritance chain
        """
        if visited is None:
            visited = set()
        if path is None:
            path = []

        # Create a copy of the current path and add this model
        current_path = path + [model_name]

        if model_name in visited:
            # We've hit a cycle, log detailed information
            cycle_start_index = current_path.index(model_name)
            cycle_path = current_path[cycle_start_index:] + [model_name]
            cycle_description = " -> ".join(cycle_path)
            logger.warning(f"Detected inheritance cycle: {cycle_description}")

            # Show what modules define each model in the cycle
            modules_info = []
            for m in cycle_path:
                if m in self.models:
                    module = self.models[m].get('module', 'unknown')
                    modules_info.append(f"{m} (defined in {module})")
                else:
                    modules_info.append(f"{m} (not found in registry)")

            logger.warning(f"Cycle module details: {', '.join(modules_info)}")
            return []

        visited.add(model_name)

        if model_name not in self.inherits:
            return []

        chain = []
        for inherited in self.inherits[model_name]:
            chain.append(inherited)
            # Pass the visited set and updated path to detect cycles
            chain.extend(self.get_model_inheritance_chain(inherited, visited, current_path))

        # Remove duplicates while preserving order
        seen = set()
        return [m for m in chain if not (m in seen or seen.add(m))]

    # Add an option to control the verbosity of cycle detection logs
    def set_cycle_detection_verbosity(self, level):
        """
        Set the verbosity level for inheritance cycle detection logs

        Args:
            level: 'low' (minimal logging), 'medium' (standard), 'high' (detailed)
        """
        self.cycle_detection_verbosity = level

    # Add a method to analyze inheritance relationships
    def analyze_inheritance_structure(self):
        """
        Analyze the inheritance structure to find potential cycles

        Returns:
            List of detected inheritance cycles
        """
        cycles = []

        # Track which models we've already checked to avoid redundant checks
        checked_models = set()

        for model_name in self.models.keys():
            if model_name in checked_models:
                continue

            # Use a depth-first search to detect cycles
            visited = set()
            path = []
            self._dfs_find_cycles(model_name, visited, path, cycles, checked_models)

        return cycles

    def _dfs_find_cycles(self, model_name, visited, path, cycles, checked_models):
        """
        Depth-first search to find inheritance cycles

        Args:
            model_name: Current model in the search
            visited: Set of models visited in the current path
            path: Current inheritance path
            cycles: Output list to collect detected cycles
            checked_models: Set of models that have been fully checked
        """
        # Mark as visited in current path
        visited.add(model_name)
        path.append(model_name)

        # Check all inherited models
        for inherited in self.inherits.get(model_name, []):
            if inherited in path:
                # Cycle detected
                cycle_start = path.index(inherited)
                cycle = path[cycle_start:] + [inherited]
                cycles.append(cycle)
            elif inherited not in checked_models:
                self._dfs_find_cycles(inherited, visited.copy(), path.copy(), cycles, checked_models)

        # Mark as fully checked
        checked_models.add(model_name)

    def resolve_field_owner(self, field_name, model_name, check_existing=True):
        """
        Resolve the true owner model of a field through inheritance
        Args:
            field_name: Name of the field
            model_name: Model where the field is used
            check_existing: Whether to check the field_owners cache

        Returns:
            Original model name that defines the field, or None if not found
        """
        # First check if we already know the owner
        if check_existing and model_name in self.field_owners and field_name in self.field_owners[model_name]:
            return self.field_owners[model_name][field_name]

        # Check if the field is defined in this model
        if model_name in self.fields and field_name in self.fields[model_name]:
            # Field is defined in this model
            field = self.fields[model_name][field_name]
            if not field.is_extension:
                return model_name

        # Check inherited models
        inheritance_chain = self.get_model_inheritance_chain(model_name)
        for parent_model in inheritance_chain:
            if parent_model in self.fields and field_name in self.fields[parent_model]:
                # Field is defined in this parent model
                field = self.fields[parent_model][field_name]
                if not field.is_extension:
                    # This is the original definition
                    return parent_model

        # Field not found in any parent model
        return None

    def resolve_view_model(self, view_id, visited=None):
        """
        Resolve the model associated with a view with cycle detection
        For inherited views, find the root view's model
        """
        if visited is None:
            visited = set()

        if view_id in visited:
            # Detected a cycle in view inheritance
            logger.warning(f"Detected view inheritance cycle for {view_id}")
            return None

        visited.add(view_id)

        if view_id not in self.views:
            return None

        view = self.views[view_id]
        if view['model']:
            return view['model']

        # If this is an inherited view, follow the inheritance chain
        if view['inherit_id']:
            return self.resolve_view_model(view['inherit_id'], visited)

        return None

    def get_models_for_module(self, module_name):
        """Get all models defined in a module"""
        return [model for model, info in self.models.items() if info['module'] == module_name]

    def get_fields_for_module(self, module_name):
        """Get all fields defined in a module"""
        fields = []
        for model_name, model_fields in self.fields.items():
            for field_name, field in model_fields.items():
                if field.module == module_name:
                    fields.append(field)
        return fields

    def get_statistics(self):
        """Get statistics about the registry"""
        stats = {
            'total_models': len(self.models),
            'total_fields': sum(len(fields) for fields in self.fields.values()),
            'total_views': len(self.views),
            'inheritance_relationships': sum(len(inherits) for inherits in self.inherits.values()),
            'models_by_module': defaultdict(int),
            'fields_by_module': defaultdict(int),
            'computed_fields': 0,
            'stored_fields': 0,
            'related_fields': 0,
            'extended_fields': 0
        }

        # Count models by module
        for model, info in self.models.items():
            stats['models_by_module'][info['module']] += 1

        # Count and categorize fields
        for model_fields in self.fields.values():
            for field in model_fields.values():
                stats['fields_by_module'][field.module] += 1

                if field.is_computed:
                    stats['computed_fields'] += 1
                if field.is_stored:
                    stats['stored_fields'] += 1
                if field.is_related:
                    stats['related_fields'] += 1
                if field.is_extension:
                    stats['extended_fields'] += 1

        return stats