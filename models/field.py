"""Field definition class for Odoo analyzer"""
from pathlib import Path
import config

def get_module_name(file_path):
    r"""Extract module name from file path
    
    For paths like:
    - C:\Odoo\sh\src\user\csl_contacts\models\res_partner.py -> csl_contacts
    - C:\Odoo\sh\src\odoo\odoo\addons\base\models\res_partner.py -> base
    
    The module name is the directory containing __manifest__.py, which is typically
    the directory before 'models', 'views', 'wizard', etc.
    """
    parts = Path(file_path).parts
    
    # Look for common Odoo module subdirectories (models, views, wizard, etc.)
    # The module name is the directory before these
    module_subdirs = {'models', 'views', 'wizard', 'wizards', 'controllers', 'static', 'data', 'security', 'report', 'tests'}
    
    for i, part in enumerate(parts):
        if part in module_subdirs and i > 0:
            # Module name is the directory before the subdirectory
            return parts[i - 1]
    
    # Fallback: if BASE_DIR is set, find first part after it
    if config.BASE_DIR:
        base_dir_name = Path(config.BASE_DIR).name
        for i, part in enumerate(parts):
            if part == base_dir_name and i + 1 < len(parts):
                # Skip intermediate directories like 'odoo', 'user', 'enterprise'
                # and find the actual module directory
                for j in range(i + 1, len(parts)):
                    potential_module = parts[j]
                    # Skip common intermediate directories
                    if potential_module not in {'odoo', 'addons', 'user', 'enterprise', 'custom'}:
                        return potential_module
                # If we only have intermediate dirs, return the first one
                return parts[i + 1] if i + 1 < len(parts) else "unknown"
    
    # Last fallback
    return "unknown"

def format_module_set(modules):
    """Format a set of modules as a sorted string"""
    if not modules:
        return ""
    return ', '.join(sorted(modules))

class FieldDefinition:
    """Store information about an Odoo field"""
    def __init__(self, model, name, field_type, attributes, file_path):
        self.model = model  # Model where field is defined (may be child model)
        self.name = name
        self.field_type = field_type
        self.attributes = attributes
        self.file_path = file_path
        self.module = get_module_name(file_path)  # Module where field is defined
        self.is_computed = 'compute' in attributes
        # If 'store' is explicitly set, use that value
        if 'store' in attributes:
            store_value = attributes['store'].lower()
            self.is_stored = store_value in ('true', '1', 'yes', 't')
        else:
            self.is_stored = not self.is_computed
        self.is_related = 'related' in attributes
        self.dependency_fields = []  # For computed fields
        self.usage_count = 0
        self.used_in_modules = set()
        self.used_in_views = set()
        
        # Root/original owner tracking - will be set after registration
        self.root_model = None  # Original model that owns this field
        self.root_module = None  # Module where field is originally defined
        self.extending_modules = set()  # Modules that extend this field (if different from root)
        
        # Temporary field_key - will be normalized to use root_model
        self.field_key = f"{self.model}.{self.name}"

        # Field extension tracking
        self.is_extension = False
        self.extended_from = None
        self.original_attributes = {}
        self.added_attributes = {}
        self.modified_attributes = {}
        self.removed_attributes = {}  # Attributes that were in original but not in extension
    
    def set_root_owner(self, root_model, root_module):
        """Set the root/original owner of this field and update field_key"""
        self.root_model = root_model
        self.root_module = root_module
        # Update field_key to use root model for consistent identification
        self.field_key = f"{root_model}.{self.name}"
    
    def add_extending_module(self, module_name):
        """Add a module that extends this field"""
        if module_name and module_name != self.root_module:
            self.extending_modules.add(module_name)

    def mark_as_extension(self, original_field_path):
        """Mark this field as an extension of a core field"""
        self.is_extension = True
        self.extended_from = original_field_path

    def is_redundant_extension(self):
        """
        Check if this field extension is redundant/unnecessary.
        An extension is redundant if:
        1. It's marked as an extension
        2. It doesn't add any new attributes
        3. It doesn't modify any attributes
        4. It doesn't remove any attributes
        5. All its attributes are unchanged from the original (just repeating them)
        
        Note: Removing attributes (like domain or context) is NOT redundant - it's a meaningful change
        that removes restrictions/functionality.
        """
        if not self.is_extension:
            return False
        
        # If attributes were removed, it's NOT redundant (removing domain/context is meaningful)
        if self.removed_attributes:
            return False
        
        # If attributes were added, it's NOT redundant
        if self.added_attributes:
            return False
        
        # If attributes were modified, it's NOT redundant
        if self.modified_attributes:
            return False
        
        # If we get here, no attributes were added, modified, or removed
        # This means the extension is just repeating the original attributes
        # However, we should also verify that all attributes match
        if self.original_attributes:
            for attr_name, attr_value in self.attributes.items():
                if attr_name not in self.original_attributes:
                    # This shouldn't happen if removed_attributes is empty, but check anyway
                    return False
                if attr_value != self.original_attributes[attr_name]:
                    # Value changed, so it's not redundant
                    return False
        
        # All attributes are unchanged and nothing was added/removed/modified
        return True

    def to_dict(self, eligible_modules=None, field_usage=None):
        """
        Convert to dictionary for CSV export
        
        Args:
            eligible_modules: Set of eligible module names (for is_eligible_module flag)
            field_usage: Dictionary of field_key -> list of FieldUsage objects (for usage stats)
        """
        # Determine if module is eligible
        # Only check the actual module where THIS field definition exists, not root_module
        # A field in standard Odoo module (like 'project') should not be eligible even if
        # it extends a field whose root_module is eligible
        is_eligible = False
        if eligible_modules:
            is_eligible = self.module in eligible_modules
        
        # Get usage statistics from field_usage if provided
        usage_count = self.usage_count
        used_in_modules = self.used_in_modules.copy() if self.used_in_modules else set()
        used_in_views = self.used_in_views.copy() if self.used_in_views else set()
        
        if field_usage and self.field_key in field_usage:
            usages = field_usage[self.field_key]
            usage_count = len(usages)
            for usage in usages:
                # field_usage contains dictionaries (from FieldUsage.to_dict())
                if isinstance(usage, dict):
                    # Extract module
                    if usage.get('module'):
                        used_in_modules.add(usage['module'])
                    
                    # Extract view usage
                    context = usage.get('context')
                    if context:
                        # Check if it's a view
                        record_type = usage.get('record_type', '')
                        if record_type == 'view' or ('.' in context and record_type != 'data'):
                            # Likely a view ID (format: module.view_id) or explicitly marked as view
                            used_in_views.add(context)
                elif hasattr(usage, 'module'):
                    # Handle FieldUsage objects directly (fallback)
                    if usage.module:
                        used_in_modules.add(usage.module)
                    if hasattr(usage, 'context') and usage.context:
                        if hasattr(usage, 'record_type') and usage.record_type == 'view':
                            used_in_views.add(usage.context)
        
        # Check if extension is redundant
        is_redundant = self.is_redundant_extension()
        
        return {
            'model': self.model,
            'field_name': self.name,
            'field_key': self.field_key,
            'field_type': self.field_type,
            'attributes': str(self.attributes),
            'defined_in': self.file_path,
            'module': self.module,  # Module where this definition exists
            'root_module': self.root_module if self.root_module else self.module,  # Root module where originally defined
            'root_model': self.root_model if self.root_model else self.model,  # Root model that owns this field
            'extending_modules': format_module_set(self.extending_modules),  # Modules that extend this field
            'is_eligible_module': str(is_eligible),
            'is_computed': str(self.is_computed),
            'is_stored': str(self.is_stored),
            'is_related': str(self.is_related),
            'usage_count': str(usage_count),
            'used_in_modules': format_module_set(used_in_modules),
            'used_in_views': ','.join(sorted(used_in_views)) if used_in_views else '',
            'is_extension': str(self.is_extension),
            'extended_from': self.extended_from if self.extended_from else '',
            'added_attributes': str(self.added_attributes),
            'modified_attributes': str(self.modified_attributes),
            'removed_attributes': str(self.removed_attributes) if hasattr(self, 'removed_attributes') else '{}',
            'is_redundant_extension': str(is_redundant)
        }
