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
        self.fields = defaultdict(lambda: defaultdict(list))  # model_name -> {field_name: [FieldDefinition, ...]}
        self.inherits = defaultdict(list)  # model_name -> [inherited_models]
        self.module_extensions = defaultdict(list)  # module -> [(model_name, inherited_model), ...] for extension-only classes
        self.views = {}  # view_id -> {model, inherit_id, view_type}
        self.class_to_model = {}  # class_name -> model_name
        self.field_owners = {}  # field_name -> {model: original_model} mapping
        self.manifest_dependencies = []  # List of manifest dependency info
        self.module_dependency_graph = {}  # module -> set of dependencies
        self.module_base_priority = {}  # module -> priority score (lower = more base)

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
        if inherited_model and inherited_model not in self.inherits[model_name]:
            self.inherits[model_name].append(inherited_model)
    
    def register_module_extension(self, module, model_name, inherited_model):
        """Register that a module extends a model (for extension-only classes without _name)"""
        if model_name and inherited_model:  # Filter out None values
            self.module_extensions[module].append((model_name, inherited_model))

    def register_field(self, model_name, field):
        """Register a field definition for a model"""
        # Store as list to handle multiple definitions of same field from different modules
        self.fields[model_name][field.name].append(field)

        # Track field ownership for inheritance
        if model_name not in self.field_owners:
            self.field_owners[model_name] = {}

        # Try to resolve the root owner (original model where field is defined)
        # Note: This may not find the root if parent fields aren't registered yet
        # That's okay - normalize_field_keys() will handle it in post-processing
        root_model = self.resolve_field_owner(field.name, model_name, check_existing=False)
        
        if root_model and root_model != model_name:
            # Field is an extension - root is in parent model
            self.field_owners[model_name][field.name] = root_model
            root_field_path = self._get_field_file_path(root_model, field.name)
            if root_field_path:
                field.mark_as_extension(root_field_path)
            # Set root owner (will be finalized in normalize_field_keys)
            root_module = self._get_model_module(root_model)
            if not root_module or root_module == 'unknown':
                root_module = field.module
            field.set_root_owner(root_model, root_module)
        else:
            # Field is newly defined in this model (or root not found yet)
            # Will be finalized in normalize_field_keys()
            self.field_owners[model_name][field.name] = model_name
            # Set temporary root (will be updated if parent is found later)
            field.set_root_owner(model_name, field.module)
    
    def _get_field_file_path(self, model_name, field_name):
        """Get the file path where a field is defined"""
        fields_list = self.get_all_fields(model_name, field_name)
        if fields_list:
            return fields_list[0].file_path
        return None
    
    def _get_model_module(self, model_name):
        """Get the module where a model is defined"""
        if model_name in self.models:
            return self.models[model_name].get('module', 'unknown')
        return 'unknown'

    def register_view(self, view_id, model_name, inherit_id=None, view_type=None):
        """Register a view definition"""
        self.views[view_id] = {
            'model': model_name,
            'inherit_id': inherit_id,
            'view_type': view_type
        }

    def get_field(self, model_name, field_name):
        """Get field definition for a model (returns first one if multiple exist)"""
        if model_name in self.fields and field_name in self.fields[model_name]:
            fields_list = self.fields[model_name][field_name]
            return fields_list[0] if fields_list else None
        return None
    
    def get_all_fields(self, model_name, field_name):
        """Get all field definitions for a model and field name"""
        if model_name in self.fields and field_name in self.fields[model_name]:
            return self.fields[model_name][field_name]
        return []

    def get_model_inheritance_chain(self, model_name, visited=None):
        """
        Get all models in the inheritance chain for a model

        Args:
            model_name: Model to get inheritance chain for
            visited: Set of already visited models (to prevent infinite loops)

        Returns:
            List of models in inheritance chain
        """
        if visited is None:
            visited = set()

        if model_name in visited:
            # Prevent infinite loops
            return []

        visited.add(model_name)

        if model_name not in self.inherits:
            return []

        chain = []
        for inherited in self.inherits[model_name]:
            chain.append(inherited)
            chain.extend(self.get_model_inheritance_chain(inherited, visited))

        # Remove duplicates while preserving order
        seen = set()
        return [m for m in chain if not (m in seen or seen.add(m))]

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
        fields_list = self.get_all_fields(model_name, field_name)
        if fields_list:
            # Check all definitions - find one that's not an extension
            for field in fields_list:
                if not field.is_extension:
                    return model_name

        # Check inherited models
        inheritance_chain = self.get_model_inheritance_chain(model_name)
        for parent_model in inheritance_chain:
            parent_fields = self.get_all_fields(parent_model, field_name)
            if parent_fields:
                # Check all definitions - find one that's not an extension
                for field in parent_fields:
                    if not field.is_extension:
                        # This is the original definition
                        return parent_model

        # Field not found in any parent model
        return None

    def resolve_view_model(self, view_id, visited=None):
        """
        Resolve the model associated with a view
        For inherited views, find the root view's model
        """
        if visited is None:
            visited = set()

        if view_id in visited:
            # Prevent infinite loops
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
            for field_name, fields_list in model_fields.items():
                for field in fields_list:
                    if field.module == module_name:
                        fields.append(field)
        return fields
    
    def set_manifest_dependencies(self, manifest_dependencies):
        """
        Set manifest dependencies and build module dependency graph.
        This is used to determine module priority when identifying root fields.
        """
        self.manifest_dependencies = manifest_dependencies
        
        # Build dependency graph: module -> set of modules it depends on
        self.module_dependency_graph = {}
        for module_info in manifest_dependencies:
            module = module_info['module']
            self.module_dependency_graph[module] = set(module_info.get('dependencies', []))
        
        # Compute base priority for each module
        # Lower priority = more base (fewer dependencies, or is a dependency of others)
        self._compute_module_priorities()
    
    def _is_standard_odoo_module(self, module_name):
        """
        Check if a module is a standard Odoo module based on file paths.
        Modules in src/odoo or src/enterprise are considered standard Odoo.
        
        Args:
            module_name: Name of the module to check
            
        Returns:
            True if module is in standard Odoo paths, False otherwise
        """
        # Check all fields and models registered for this module to find file paths
        standard_path_indicators = ['/odoo/', '\\odoo\\', '/enterprise/', '\\enterprise\\']
        
        # Check models
        for model_name, model_info in self.models.items():
            if model_info.get('module') == module_name:
                file_path = model_info.get('file_path', '')
                if any(indicator in file_path for indicator in standard_path_indicators):
                    return True
        
        # Check fields
        for model_name, model_fields in self.fields.items():
            for field_name, fields_list in model_fields.items():
                for field in fields_list:
                    if field.module == module_name:
                        file_path = field.file_path
                        if any(indicator in file_path for indicator in standard_path_indicators):
                            return True
        
        return False

    def _compute_module_priorities(self):
        """
        Compute priority scores for modules based on dependency graph.
        Lower score = more base module (should be root for fields).
        
        Priority is based on:
        1. Number of dependencies (fewer = more base)
        2. Whether it's a dependency of other modules (if yes, more base)
        3. Special handling for 'odoo' and 'base' modules (always most base)
        4. Path-based detection: modules in src/odoo or src/enterprise are standard Odoo
        """
        # Initialize all modules with a base score
        all_modules = set(self.module_dependency_graph.keys())
        
        # Add modules that are dependencies but may not have manifests
        for deps in self.module_dependency_graph.values():
            all_modules.update(deps)
        
        # Also include modules from registered models and fields
        for model_info in self.models.values():
            all_modules.add(model_info.get('module'))
        for model_fields in self.fields.values():
            for fields_list in model_fields.values():
                for field in fields_list:
                    all_modules.add(field.module)
        
        # Special base modules get highest priority (lowest score)
        base_modules = {'odoo', 'base'}
        
        # Compute dependency depth for each module
        # Modules with fewer dependencies or that are dependencies of many others are more base
        for module in all_modules:
            if not module or module == 'unknown':
                continue
                
            if module in base_modules:
                self.module_base_priority[module] = 0  # Most base
            elif self._is_standard_odoo_module(module):
                # Standard Odoo modules (in src/odoo or src/enterprise) are more base than custom modules
                # Give them a low priority (but higher than base modules)
                self.module_base_priority[module] = 1  # Very base, but not as base as 'base'
            else:
                # Priority = number of direct dependencies
                # Modules with fewer dependencies are more base
                deps_count = len(self.module_dependency_graph.get(module, set()))
                
                # Also check how many modules depend on this one
                # If many modules depend on it, it's more base
                dependent_count = sum(1 for deps in self.module_dependency_graph.values() 
                                     if module in deps)
                
                # Lower score = more base
                # Formula: dependencies count - (dependent_count * 0.5)
                # This means: fewer dependencies = more base, being a dependency = more base
                priority = deps_count - (dependent_count * 0.5)
                self.module_base_priority[module] = priority
        
        # Ensure all modules have a priority (fallback for unknown modules)
        for module in all_modules:
            if module not in self.module_base_priority:
                self.module_base_priority[module] = 1000  # Unknown modules get high priority (less base)
    
    def _get_module_priority(self, module_name):
        """Get the base priority score for a module. Lower = more base."""
        if module_name in self.module_base_priority:
            return self.module_base_priority[module_name]
        
        # Fallback: check if it's a known base module
        if module_name in {'odoo', 'base'}:
            return 0
        
        # Fallback: check if it's a standard Odoo module based on path
        # (in case it wasn't in dependency graph when priorities were computed)
        if self._is_standard_odoo_module(module_name):
            return 1  # Standard Odoo modules are more base than custom modules
        
        # Unknown module - assign high priority (less base)
        # Custom modules not in dependency graph get this
        return 1000
    
    def normalize_field_keys(self):
        """
        Post-processing step to normalize all field_keys to use root models.
        This ensures consistent field identification across definitions and usages.
        Also tracks extending modules for each field.
        """
        # First pass: resolve all root owners
        for model_name, model_fields in self.fields.items():
            for field_name, fields_list in model_fields.items():
                for field in fields_list:
                    # Resolve root owner by checking if field exists in parent models
                    root_model = self.resolve_field_owner(field_name, model_name, check_existing=True)
                    if not root_model:
                        root_model = model_name
                    
                    # Get root module - find the module where the root field is actually defined
                    root_module = None
                    root_fields = self.get_all_fields(root_model, field_name)
                    if root_fields:
                        # Use the first field (will be sorted by priority later)
                        root_module = root_fields[0].module
                    else:
                        # Fallback: use model's module
                        root_module = self._get_model_module(root_model)
                        if not root_module or root_module == 'unknown':
                            root_module = field.module
                    
                    # Set root owner on field
                    field.set_root_owner(root_model, root_module)
        
        # Second pass: identify root fields and track extensions
        # Group fields by (root_model, field_name) to find the actual root definition
        field_groups = {}  # (root_model, field_name) -> list of fields
        
        for model_name, model_fields in self.fields.items():
            for field_name, fields_list in model_fields.items():
                for field in fields_list:
                    root_model = field.root_model
                    root_module = field.root_module
                    key = (root_model, field_name)
                    
                    if key not in field_groups:
                        field_groups[key] = []
                    field_groups[key].append(field)
        
        # Third pass: identify the root field (earliest module) and mark extensions
        for (root_model, field_name), fields_list in field_groups.items():
            if len(fields_list) == 1:
                # Only one definition - it's the root
                field = fields_list[0]
                # If it has extended_from set, it means it was marked as extension earlier
                # but there's no other definition, so it's actually the root
                if field.extended_from:
                    field.extended_from = None  # Clear it since it's the root
                field.is_extension = False
                # Ensure root_module is set correctly (should be same as module for single definition)
                field.set_root_owner(root_model, field.module)
            else:
                # Multiple definitions - find the root based on module dependency priority
                # The root is the field in the most "base" module (lowest priority score)
                # This uses manifest dependencies to determine which module is more fundamental
                fields_list.sort(key=lambda f: (
                    self._get_module_priority(f.module),  # Lower priority = more base
                    f.module  # Then alphabetically as tiebreaker
                ))
                
                root_field = fields_list[0]
                root_field.is_extension = False
                if root_field.extended_from:
                    root_field.extended_from = None  # Clear it since it's the root
                
                # CRITICAL: Update root_field's root_module to use its own module (the actual root)
                root_field.set_root_owner(root_model, root_field.module)
                
                # All others are extensions
                for field in fields_list[1:]:
                    # Mark as extension (force it to True)
                    field.is_extension = True
                    # Add extending module to root field
                    if field.module != root_field.module:
                        root_field.add_extending_module(field.module)
                    # Set extended_from on extension field if not already set
                    if not field.extended_from:
                        field.mark_as_extension(root_field.file_path)
                    # Ensure extension field has correct root (use root_field's module)
                    field.set_root_owner(root_model, root_field.module)
        
        # Final pass: ensure all field_keys use root model
        for model_name, model_fields in self.fields.items():
            for field_name, fields_list in model_fields.items():
                for field in fields_list:
                    if field.root_model:
                        field.field_key = f"{field.root_model}.{field.name}"
                    else:
                        # Fallback: use current model
                        field.set_root_owner(model_name, field.module)
                        field.field_key = f"{model_name}.{field.name}"

    def get_statistics(self):
        """Get statistics about the registry"""
        stats = {
            'total_models': len(self.models),
            'total_fields': sum(sum(len(fields_list) for fields_list in model_fields.values()) 
                               for model_fields in self.fields.values()),
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
            for fields_list in model_fields.values():
                for field in fields_list:
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