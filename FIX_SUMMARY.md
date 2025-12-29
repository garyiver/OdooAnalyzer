# Fix Summary: Unique Field Identification for csl_core Consolidation

## Problem Solved
The code was failing to correctly identify unique fields when they were part of parent modules. Fields defined in parent models and extended in child models were being treated as separate fields instead of the same field.

## Solution Implemented

### 1. Root Module Tracking
- **Root Module**: The module where a field is originally/initially defined
- **Extending Modules**: Modules that extend/redefine the field (if different from root)
- **Root Model**: The original model that owns the field (used for consistent field_key)

### 2. Field Key Normalization
- All `field_key` values now use the **root model** (original owner), not the model where the field is currently defined
- This ensures consistent identification across:
  - Field definitions (Python parsing)
  - Field usages (XML parsing)
  - Analysis outputs

### 3. Changes Made

#### `models/field.py`
- Added `root_model`, `root_module`, and `extending_modules` attributes
- Added `set_root_owner()` method to set root owner and update field_key
- Added `add_extending_module()` method to track modules that extend the field
- Updated `to_dict()` to include `root_module`, `root_model`, and `extending_modules` in CSV exports

#### `models/registry.py`
- Updated `register_field()` to attempt root owner resolution during registration
- Added `normalize_field_keys()` method for post-processing:
  - Resolves all root owners after all fields are registered
  - Normalizes all field_keys to use root models
  - Tracks extending modules for each root field
- Added helper methods: `_get_field_file_path()`, `_get_model_module()`

#### `__main__.py`
- Added call to `registry.normalize_field_keys()` after all Python files are parsed
- Updated CSV export to include new fields (root_module, root_model, extending_modules)
- Added new analysis: `analyze_field_dependencies_for_core()` for csl_core consolidation

#### `analysis/module_analyzer.py`
- Updated `analyze_field_sharing()` to include root_module and extending_modules
- Added `analyze_field_dependencies_for_core()` method:
  - Groups fields by root_module
  - Lists all extending modules for each root module
  - Provides dependency information for consolidation planning

## New Output Files

### `field_dependencies.csv`
Detailed list of all fields with:
- `field_key`: Unique identifier using root model
- `root_model`: Original model that owns the field
- `root_module`: Module where field is originally defined
- `defined_in_module`: Module where this definition exists (may differ from root)
- `extending_modules`: Comma-separated list of modules that extend this field
- `is_extension`: Whether this definition is an extension
- `field_type`, `used_in_modules`, `usage_count`: Additional metadata

### `field_dependencies_summary.csv`
Summary by root module:
- `root_module`: Module where fields are originally defined
- `field_count`: Number of fields in this root module
- `extending_modules`: All modules that extend fields from this root module

### Updated `fields_analysis.csv`
Now includes:
- `root_module`: Root module for each field
- `root_model`: Root model for each field
- `extending_modules`: Modules that extend this field

### Updated `shared_fields.csv`
Now includes:
- `root_module`: Root module for each shared field
- `extending_modules`: Modules that extend this field

## Usage for csl_core Consolidation

1. **Identify Root Modules**: Use `field_dependencies_summary.csv` to see which modules define fields
2. **Find Dependencies**: The `extending_modules` column shows which modules depend on each root module
3. **Plan Migration**: 
   - Fields should be moved to `csl_core` based on their `root_module`
   - Modules listed in `extending_modules` will need to depend on `csl_core`
   - This helps identify circular dependencies that need resolution

## Example

**Before Fix:**
```
Field defined in parent module "base_module":
  - field_key: "sale.order.custom_field"
  - module: "base_module"

Field extended in child module "custom_module":
  - field_key: "sale.order.custom_field" (same key, but treated as separate!)
  - module: "custom_module"
```

**After Fix:**
```
Field defined in parent module "base_module":
  - field_key: "sale.order.custom_field" (using root model)
  - root_module: "base_module"
  - root_model: "sale.order"
  - extending_modules: "custom_module"

Field extended in child module "custom_module":
  - field_key: "sale.order.custom_field" (same key, correctly identified!)
  - root_module: "base_module"
  - root_model: "sale.order"
  - defined_in_module: "custom_module"
  - is_extension: True
```

## Running the Analysis

The fix is automatically applied when you run:
```bash
python -m __main__ --dir <your_modules_dir> --analyze-sharing
```

The new dependency analysis is included when using `--analyze-sharing` flag.

## Benefits

1. **Unique Field Identification**: Each field is now uniquely identified by its root model
2. **Dependency Tracking**: Clear visibility into which modules extend which fields
3. **Consolidation Planning**: Easy to see what needs to move to csl_core and what dependencies exist
4. **Circular Dependency Detection**: The extending_modules list helps identify circular dependencies

