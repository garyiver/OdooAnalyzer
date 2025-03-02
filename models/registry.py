"""Model registry for tracking Odoo models and fields"""
from collections import defaultdict

class ModelRegistry:
    """Store and track Odoo models and their fields"""
    def __init__(self):
        # model_name -> {'module': module, 'file_path': path, 'class_name': name}
        self.models = {}

        # model_name -> [inherited_models]
        self.inherits = defaultdict(list)

        # model_name -> {field_name: FieldDefinition}
        self.fields = defaultdict(dict)

        # model_name.field_name -> FieldDefinition
        self.qualified_fields = {}

        # view_id -> {'model': model_name, 'inherit_id': parent_view_id}
        self.views = {}

        # class_name -> model_name
        self.class_to_model = {}

        # Maps model aliases to actual model names
        self.model_aliases = {}

    def register_model(self, model_name, class_name, module, file_path):
        """Register a model definition"""
        self.models[model_name] = {
            'module': module,
            'file_path': file_path,
            'class_name': class_name
        }
        self.class_to_model[class_name] = model_name

    def register_inherit(self, model_name, inherited_model):
        """Register an inheritance relationship"""
        if inherited_model not in self.inherits[model_name]:
            self.inherits[model_name].append(inherited_model)

    def register_field(self, model_name, field):
        """Register a field definition"""
        self.fields[model_name][field.name] = field
        self.qualified_fields[f"{model_name}.{field.name}"] = field

    def register_view(self, view_id, model_name=None, inherit_id=None):
        """Register a view definition"""
        if view_id not in self.views:
            self.views[view_id] = {'model': model_name, 'inherit_id': inherit_id}
        else:
            if model_name:
                self.views[view_id]['model'] = model_name
            if inherit_id:
                self.views[view_id]['inherit_id'] = inherit_id

    def resolve_inherited_view_model(self, view_id: str, visited=None):
        """Resolve the model for a view that inherits another view"""
        if visited is None:
            visited = set()

        if view_id in visited:
            return None  # Prevent infinite recursion

        visited.add(view_id)

        if view_id not in self.views:
            return None

        # If this view specifies a model, return it
        if self.views[view_id].get('model'):
            return self.views[view_id]['model']

        # Otherwise, check if it inherits another view
        inherit_id = self.views[view_id].get('inherit_id')
        if inherit_id:
            # Handle Odoo's dot notation for external IDs
            if '.' in inherit_id:
                _, inherit_id = inherit_id.split('.')

            return self.resolve_inherited_view_model(inherit_id, visited)

        return None

    def resolve_view_model(self, view_id: str):
        """Get the model for a view, including through inheritance"""
        # Handle Odoo's dot notation for external IDs
        if '.' in view_id:
            _, view_id = view_id.split('.')

        model = self.resolve_inherited_view_model(view_id)
        if model:
            return model

        return None

    def get_model_inheritance_chain(self, model_name: str, visited=None):
        """Get all models in the inheritance chain for a model"""
        if visited is None:
            visited = set()

        if model_name in visited:
            return []  # Prevent infinite recursion

        visited.add(model_name)

        if model_name not in self.inherits:
            return []

        result = list(self.inherits[model_name])
        for inherited in self.inherits[model_name]:
            result.extend(self.get_model_inheritance_chain(inherited, visited))

        return list(set(result))  # Remove duplicates

    def resolve_field_owner(self, field_name: str, model_name: str):
        """Find which model in the inheritance chain owns a field"""
        # Check if the field is directly defined in this model
        if model_name in self.fields and field_name in self.fields[model_name]:
            return model_name

        # Get all models in the inheritance chain
        inheritance_chain = self.get_model_inheritance_chain(model_name)

        # Check each inherited model
        for inherited in inheritance_chain:
            if inherited in self.fields and field_name in self.fields[inherited]:
                return inherited

        return None

    def get_field(self, model_name: str, field_name: str):
        """Get a field definition, considering inheritance"""
        # Check if the field is directly defined in this model
        if model_name in self.fields and field_name in self.fields[model_name]:
            return self.fields[model_name][field_name]

        # Try to resolve through inheritance
        owner = self.resolve_field_owner(field_name, model_name)
        if owner:
            return self.fields[owner][field_name]

        return None

    def get_field_by_key(self, field_key):
        """Get a field definition by its qualified key (model.field_name)"""
        return self.qualified_fields.get(field_key)

    def add_model_alias(self, alias, actual_model):
        """Register a model alias (e.g. from _name to _inherit)"""
        self.model_aliases[alias] = actual_model

    def resolve_model_name(self, model_ref):
        """Resolve a model reference to its actual model name"""
        return self.model_aliases.get(model_ref, model_ref)
