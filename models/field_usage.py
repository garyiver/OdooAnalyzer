"""Field usage tracking class with record type classification"""

class FieldUsage:
    """Store information about field usage"""
    # Record type constants
    RECORD_TYPE_VIEW = 'view'
    RECORD_TYPE_DATA = 'data'
    RECORD_TYPE_UNKNOWN = 'unknown'

    def __init__(self, field_key, context, module, file_path, model=None):
        self.field_key = field_key
        self.context = context  # View ID or file name
        self.module = module
        self.file_path = file_path
        self.model = model if model else ''  # Empty string if no model
        self.record_type = self.RECORD_TYPE_UNKNOWN  # Default to unknown
        self.view_type = ''  # Form, tree, kanban, etc.

    def to_dict(self):
        """Convert to dictionary for CSV export"""
        return {
            'field_key': self.field_key,
            'context': self.context,
            'module': self.module,
            'file_path': self.file_path,
            'model': self.model,
            'record_type': self.record_type,
            'view_type': self.view_type
        }

    @property
    def is_view_field(self):
        """Check if this field is used in a view"""
        return self.record_type == self.RECORD_TYPE_VIEW

    @property
    def is_data_field(self):
        """Check if this field is used in a data record"""
        return self.record_type == self.RECORD_TYPE_DATA