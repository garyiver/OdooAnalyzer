"""Python file parser for Odoo analyzer"""
import ast
import logging
import os
from ..utils.file_utils import get_files, get_module_name
from ..models.field import FieldDefinition


logger = logging.getLogger(__name__)

class ModelVisitor(ast.NodeVisitor):
    """AST visitor to extract model information"""

    def __init__(self, file_path, registry):
        self.file_path = file_path
        self.module = get_module_name(file_path)
        self.registry = registry
        self.current_class = None

    def visit_ClassDef(self, node):
        """Process class definitions to identify Odoo models"""
        old_class = self.current_class
        self.current_class = node.name

        # Check if this is an Odoo model
        model_name = None
        inherits = []

        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        # Find _name attribute
                        if target.id == '_name' and isinstance(stmt.value, ast.Constant):
                            model_name = stmt.value.s

                        # Find _inherit attribute
                        elif target.id == '_inherit':
                            if isinstance(stmt.value, ast.Constant):
                                inherits.append(stmt.value.s)
                            elif isinstance(stmt.value, ast.List):
                                for elt in stmt.value.elts:
                                    if isinstance(elt, ast.Constant):
                                        inherits.append(elt.s)

        if model_name or inherits:
            # Register the model if it has a name
            if model_name:
                self.registry.register_model(model_name, node.name, self.module, self.file_path)

                # Register _name to _inherit relationships (inheritance)
                for inherited in inherits:
                    self.registry.register_inherit(model_name, inherited)

            # If no _name but has _inherit with a single model, this is a class extension
            elif len(inherits) == 1:
                inherited_model = inherits[0]
                # Register class to model mapping for field discovery
                self.registry.class_to_model[node.name] = inherited_model

                # No need to register inheritance since there's no unique model name

            # For multiple inheritance without _name, this is more complex
            # We'll register the class name as a temporary model
            elif len(inherits) > 1:
                # Use class name as a temporary model identifier
                temp_model = f"temp.{node.name}"
                self.registry.register_model(temp_model, node.name, self.module, self.file_path)

                # Register inheritance for each inherited model
                for inherited in inherits:
                    self.registry.register_inherit(temp_model, inherited)

                # Map the class to the first inherited model for field discovery
                self.registry.class_to_model[node.name] = inherits[0]

        # Continue with child nodes
        self.generic_visit(node)
        self.current_class = old_class


class FieldVisitor(ast.NodeVisitor):
    """AST visitor to extract field definitions"""

    def __init__(self, file_path, registry):
        self.file_path = file_path
        self.module = get_module_name(file_path)
        self.registry = registry
        self.current_class = None
        self.current_model = None
        self.fields = []
        self.method_overrides = []
        self.compute_methods = {}  # name: method_node

    def visit_ClassDef(self, node):
        """Process class definitions to find field definitions"""
        old_class = self.current_class
        old_model = self.current_model

        self.current_class = node.name

        # Determine the model for this class
        model_name = None

        # First, check if this class is mapped to a model in our registry
        if node.name in self.registry.class_to_model:
            model_name = self.registry.class_to_model[node.name]

        # If not, look for _name or _inherit in the class body
        if not model_name:
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            if target.id == '_name' and isinstance(stmt.value, ast.Constant):
                                model_name = stmt.value.s
                                break
                            elif target.id == '_inherit' and not model_name:
                                if isinstance(stmt.value, ast.Constant):
                                    model_name = stmt.value.s
                                    break
                                elif isinstance(stmt.value, ast.List) and stmt.value.elts:
                                    # Use the first inherited model as the main model
                                    first_elt = stmt.value.elts[0]
                                    if isinstance(first_elt, ast.Constant):
                                        model_name = first_elt.s
                                        break

        self.current_model = model_name

        if self.current_model:
            # Process field definitions in this model
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    self._process_field_assignment(stmt)
                elif isinstance(stmt, ast.FunctionDef):
                    self._check_for_method_override(stmt)
                    self._process_compute_method(stmt)

        # Visit child nodes
        self.generic_visit(node)

        self.current_class = old_class
        self.current_model = old_model

    def _process_field_assignment(self, stmt):
        """Process field assignments in Odoo models"""
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                field_name = target.id

                # Skip non-field assignments
                if field_name.startswith('_'):
                    continue

                # Check if this is a field definition (fields.XXX(...))
                if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute):
                    func_value = stmt.value.func.value

                    # Check for fields.XXX or models.XXX patterns
                    if (hasattr(func_value, 'id') and func_value.id in ('fields', 'models')):
                        field_type = stmt.value.func.attr

                        # Extract field attributes
                        attributes = {}
                        for kw in stmt.value.keywords:
                            if isinstance(kw.value, ast.Constant):
                                attributes[kw.arg] = str(kw.value.value)
                            else:
                                try:
                                    attributes[kw.arg] = ast.unparse(kw.value)
                                except (AttributeError, ValueError):
                                    attributes[kw.arg] = 'complex_expression'

                        # Create the field definition
                        field = FieldDefinition(
                            self.current_model,
                            field_name,
                            field_type,
                            attributes,
                            self.file_path
                        )

                        # Check if this field extends a core field
                        if self.current_model in self.registry.inherits:
                            # Get all models in the inheritance chain
                            inherited_models = self.registry.get_model_inheritance_chain(self.current_model)
                            inherited_models.append(self.current_model)  # Include self for completeness

                            # Check if the field is defined in any parent model
                            for parent_model in inherited_models:
                                if parent_model == self.current_model:
                                    continue  # Skip self

                                parent_field = self.registry.get_field(parent_model, field_name)
                                if parent_field:
                                    # This is an extension of an existing field
                                    field.mark_as_extension(parent_field.file_path)

                                    # Track which attributes were added or modified
                                    field.original_attributes = parent_field.attributes.copy()
                                    field.added_attributes = {}
                                    field.modified_attributes = {}

                                    # Compare attributes to determine which were added or modified
                                    for attr_name, attr_value in attributes.items():
                                        if attr_name not in parent_field.attributes:
                                            # This is a new attribute
                                            field.added_attributes[attr_name] = attr_value
                                        elif attr_value != parent_field.attributes[attr_name]:
                                            # This attribute was modified
                                            field.modified_attributes[attr_name] = {
                                                'old': parent_field.attributes[attr_name],
                                                'new': attr_value
                                            }

                                    break

                        # Process compute methods
                        if 'compute' in attributes:
                            compute_value = attributes['compute']
                            # Strip quotes and prefix if present
                            compute_method = compute_value.strip('\'"_')
                            if compute_method in self.compute_methods:
                                self._analyze_compute_dependencies(field, compute_method)

                        # Register the field with the model registry
                        self.registry.register_field(self.current_model, field)
                        self.fields.append(field)

    def _check_for_method_override(self, node):
        """Identify method overrides by checking for super() calls"""
        has_super_call = False

        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute):
                if isinstance(stmt.func.value, ast.Call) and isinstance(stmt.func.value.func, ast.Name):
                    if stmt.func.value.func.id == 'super' and stmt.func.attr == node.name:
                        has_super_call = True
                        break

        if has_super_call:
            self.method_overrides.append({
                'class': self.current_class,
                'model': self.current_model,
                'method': node.name,
                'file_path': self.file_path,
                'module': self.module
            })

    def _process_compute_method(self, node):
        """Store compute methods for later analysis"""
        self.compute_methods[node.name] = node

    def _analyze_compute_dependencies(self, field, compute_method):
        """Analyze compute method to find field dependencies"""
        if compute_method not in self.compute_methods:
            return

        node = self.compute_methods[compute_method]

        # Look for self.field_name references in the compute method
        field_refs = []
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Attribute) and isinstance(stmt.value, ast.Name) and stmt.value.id == 'self':
                field_name = stmt.attr
                if not field_name.startswith('_'):
                    field_refs.append(field_name)

        # Remove duplicates and exclude the computed field itself
        dep_fields = [f for f in set(field_refs) if f != field.name]

        # Also check for explicit dependencies in depends() decorator
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func,
                                                              ast.Name) and decorator.func.id == 'depends':
                for arg in decorator.args:
                    if isinstance(arg, ast.Constant):
                        dep_fields.append(arg.s)
                    elif isinstance(arg, ast.Tuple) or isinstance(arg, ast.List):
                        for elt in arg.elts:
                            if isinstance(elt, ast.Constant):
                                dep_fields.append(elt.s)

        # Update field dependencies
        field.dependency_fields = list(set(dep_fields))


def parse_python_file(file_path, registry):
    """Parse Python file to extract model and field information"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        tree = ast.parse(file_content)

        # First pass: gather model and inheritance information
        model_visitor = ModelVisitor(file_path, registry)
        model_visitor.visit(tree)

        # Second pass: gather field definitions
        field_visitor = FieldVisitor(file_path, registry)
        field_visitor.visit(tree)

        return field_visitor.fields, field_visitor.method_overrides
    except Exception as e:
        logger.error(f"Error parsing Python file {file_path}: {e}")
        return [], []


def parse_python_files(base_dir, registry):
    """Parse all Python files in the directory"""
    all_fields = []
    all_method_overrides = []

    # First pass: Extract model definitions and inheritance
    logger.info("Extracting model definitions and inheritance...")
    for file_path in get_files(base_dir, '.py'):
        if file_path.endswith('__manifest__.py'):
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content)
            visitor = ModelVisitor(file_path, registry)
            visitor.visit(tree)
        except Exception as e:
            logger.error(f"Error processing model definitions in {file_path}: {e}")

    logger.info(f"Found {len(registry.models)} model definitions with {sum(len(inherits) for inherits in registry.inherits.values())} inheritance relationships")

    # Second pass: Extract field definitions and methods
    logger.info("Extracting field definitions and methods...")
    for file_path in get_files(base_dir, '.py'):
        if file_path.endswith('__manifest__.py'):
            continue

        fields, method_overrides = parse_python_file(file_path, registry)
        all_fields.extend(fields)
        all_method_overrides.extend(method_overrides)

    return all_fields, all_method_overrides
