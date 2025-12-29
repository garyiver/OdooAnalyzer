# Module Priority for Root Field Identification

## Overview

When multiple fields with the same name exist in the same model (from different modules), we need to determine which one is the "root" definition. This is done using **module priority** based on Odoo manifest dependencies.

## How Module Priority Works

### 1. Manifest Dependencies

Odoo modules declare their dependencies in `__manifest__.py`:

```python
{
    'name': 'My Custom Module',
    'depends': ['base', 'sale', 'account'],  # This module depends on these
    ...
}
```

### 2. Dependency Graph

The system builds a dependency graph:
- **Module A depends on Module B** → B is more "base" than A
- If `csl_contacts` depends on `base`, then `base` is more fundamental

### 3. Priority Calculation

Priority score (lower = more base):
- **Base modules** (`odoo`, `base`): Priority = 0 (most base)
- **Other modules**: Priority = `dependencies_count - (dependent_count * 0.5)`
  - Fewer dependencies = more base
  - Being a dependency of many modules = more base

### 4. Root Field Selection

When multiple fields exist with the same name:

**Example: `res.partner.street`**
- Defined in `odoo` module (base Odoo)
- Extended in `user/csl_contacts` module (custom)

**Selection Process:**
1. Group all fields by `(model, field_name)` → `(res.partner, street)`
2. Calculate priority for each module:
   - `odoo`: Priority = 0 (base module)
   - `user`: Priority = higher (depends on other modules)
3. Sort by priority (lowest first)
4. **Root field** = field in module with lowest priority
5. **Extension fields** = all other fields

### 5. Example Scenarios

#### Scenario 1: Base Module vs Custom Module
```
odoo/base module: res.partner.street (priority: 0)
user/csl_contacts: res.partner.street (priority: 5)

Result: odoo is root, user is extension
```

#### Scenario 2: Multiple Custom Modules
```
module_a (depends on base): res.partner.custom_field (priority: 1)
module_b (depends on module_a): res.partner.custom_field (priority: 2)

Result: module_a is root, module_b is extension
```

#### Scenario 3: Same Dependency Level
```
module_x (depends on base): res.partner.field (priority: 1)
module_y (depends on base): res.partner.field (priority: 1)

Result: Alphabetically first is root (tiebreaker)
```

## Why This Matters

1. **Correct Root Identification**: Ensures we identify the original field definition, not an extension
2. **Dependency Tracking**: Shows which modules extend which fields
3. **Consolidation Planning**: When moving to `csl_core`, you know:
   - Root module = where field should come from
   - Extending modules = what depends on the field

## Implementation Details

### Code Flow

1. **Parse Manifests** (`__main__.py`):
   ```python
   manifest_dependencies = parse_manifest_files(config.BASE_DIR)
   ```

2. **Set in Registry** (`__main__.py`):
   ```python
   registry.set_manifest_dependencies(manifest_dependencies)
   ```

3. **Compute Priorities** (`models/registry.py`):
   ```python
   registry._compute_module_priorities()
   ```

4. **Use in Normalization** (`models/registry.py`):
   ```python
   fields_list.sort(key=lambda f: (
       self._get_module_priority(f.module),  # Lower = more base
       f.module  # Alphabetical tiebreaker
   ))
   ```

## Special Cases

### Unknown Modules
- Modules not found in manifests get priority = 1000 (least base)
- This ensures known modules are preferred over unknown ones

### Circular Dependencies
- The priority calculation handles cycles gracefully
- Base modules (`odoo`, `base`) always win in case of ambiguity

### Missing Manifests
- If a module has no manifest, it's treated as unknown
- Falls back to alphabetical ordering

## Benefits

✅ **Accurate Root Detection**: Uses actual Odoo dependency structure  
✅ **Respects Module Hierarchy**: Understands which modules are more fundamental  
✅ **Handles Complex Scenarios**: Works with multiple inheritance levels  
✅ **Consolidation Ready**: Perfect for planning `csl_core` migration  

