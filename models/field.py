"""Field definition class for Odoo analyzer"""
from pathlib import Path
import config

def get_module_name(file_path):
    """Extract module name from file path"""

    parts = Path(file_path).parts
    # Find the first part after BASE_DIR that doesn't match common subfolders
    for i, part in enumerate(parts):
        if part == Path(config.BASE_DIR).name:
            if i + 1 < len(parts):
                return parts[i + 1]
    # Fallback if we can't determine module
    return "unknown"

def format_module_set(modules):
    """Format a set of modules as a sorted string"""
    if not modules:
        return ""
    return ', '.join(sorted(modules))

class FieldDefinition:
    """Store information about an Odoo field"""
    def __init__(self, model, name, field_type, attributes, file_path):
        self.model = model
        self.name = name
        self.field_type = field_type
        self.attributes = attributes
        self.file_path = file_path
        self.module = get_module_name(file_path)
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
        self.field_key = f"{self.model}.{self.name}"

        # Field extension tracking
        self.is_extension = False
        self.extended_from = None
        self.original_attributes = {}
        self.added_attributes = {}
        self.modified_attributes = {}

    def mark_as_extension(self, original_field_path):
        """Mark this field as an extension of a core field"""
        self.is_extension = True
        self.extended_from = original_field_path

    def to_dict(self):
        """Convert to dictionary for CSV export"""
        return {
            'model': self.model,
            'field_name': self.name,
            'field_key': self.field_key,
            'field_type': self.field_type,
            'attributes': str(self.attributes),
            'defined_in': self.file_path,
            'module': self.module,
            'is_computed': str(self.is_computed),
            'is_stored': str(self.is_stored),
            'is_related': str(self.is_related),
            'dependency_fields': ','.join(self.dependency_fields) if self.dependency_fields else '',
            'usage_count': str(self.usage_count),
            'used_in_modules': format_module_set(self.used_in_modules),
            'used_in_views': ','.join(self.used_in_views) if self.used_in_views else '',
            'is_extension': str(self.is_extension),
            'extended_from': self.extended_from if self.extended_from else '',
            'added_attributes': str(self.added_attributes),
            'modified_attributes': str(self.modified_attributes)
        }
