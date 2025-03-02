"""Field analysis functions"""

def analyze_unused_fields(fields, field_usage):
    """Identify fields that have no usages"""
    unused_fields = []

    for field in fields:
        if field.field_key not in field_usage or not field_usage[field.field_key]:
            # No usages found
            unused_fields.append(field)

    return unused_fields

def analyze_shared_fields(fields, field_usage):
    """Identify fields that are used across multiple modules"""
    shared_fields = []

    for field in fields:
        if field.field_key not in field_usage:
            continue

        # Get unique modules using this field
        using_modules = set()
        for usage in field_usage[field.field_key]:
            if 'module' in usage:
                using_modules.add(usage['module'])

        # Remove the defining module from the count
        if field.module in using_modules:
            using_modules.remove(field.module)

        # If used in multiple other modules
        if len(using_modules) > 0:
            shared_fields.append({
                'field': field.name,
                'field_key': field.field_key,
                'model': field.model,
                'defined_in_module': field.module,
                'used_in_modules': list(using_modules),
                'usage_count': len(field_usage[field.field_key])
            })

    return shared_fields
