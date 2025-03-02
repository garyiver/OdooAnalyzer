"""Module organization analysis"""

def analyze_module_organization(fields, field_usage, registry):
    """Analyze current module organization and suggest improvements"""
    # Fields that should be moved to core
    fields_to_move = []

    # Try to identify core modules
    core_candidates = set()
    for field in fields:
        if field.module.lower() in ('core', 'base_custom', 'base'):
            core_candidates.add(field.module)

    # Use the first core module found, or None if none exist
    core_module = next(iter(core_candidates)) if core_candidates else None

    # Find fields used across modules
    for field in fields:
        # Skip fields already in core
        if core_module and field.module == core_module:
            continue

        # Skip if this field has no usages
        if field.field_key not in field_usage:
            continue

        # Find unique modules using this field
        using_modules = set()
        for usage in field_usage[field.field_key]:
            if 'module' in usage:
                using_modules.add(usage['module'])

        # If used in multiple modules (including its own)
        if len(using_modules) > 1:
            # Add to list of fields to move
            fields_to_move.append({
                'field': field.name,
                'field_key': field.field_key,
                'model': field.model,
                'current_module': field.module,
                'used_in_modules': list(sorted(using_modules)),
                'recommendation': f"Move to {core_module or 'core'} module"
            })

    return {
        'fields_to_move': fields_to_move,
        'core_module': core_module
    }
