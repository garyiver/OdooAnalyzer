"""Module dependency analysis"""
from collections import defaultdict

def analyze_module_dependencies(registry, manifest_deps):
    """Analyze module dependencies based on inheritance and manifest files"""
    # Inheritance-based dependencies
    inheritance_deps = defaultdict(set)

    # Analyze model inheritance to determine module dependencies
    for model_name, inherits in registry.inherits.items():
        if model_name not in registry.models:
            continue

        model_module = registry.models[model_name]['module']

        # For each inherited model
        for inherited_model in inherits:
            if inherited_model not in registry.models:
                continue

            inherited_module = registry.models[inherited_model]['module']

            # If they're in different modules, we have a dependency
            if model_module != inherited_module:
                inheritance_deps[model_module].add(inherited_module)

    # Convert to dictionary with lists
    result = {}
    for module, deps in inheritance_deps.items():
        result[module] = sorted(deps)

    return result
