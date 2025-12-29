# Eligible Modules Configuration

## Overview

The restructuring recommendations tool uses a simple list of modules eligible for consolidation into `csl_core`. Only modules in this list will be considered for consolidation recommendations.

## Configuration

### Config File (`config.py`)

Edit `ELIGIBLE_MODULES_FOR_CORE` in `config.py` to specify which modules are eligible:

```python
ELIGIBLE_MODULES_FOR_CORE = [
    'bista_convert_product',
    'csl_account',
    'csl_attendance',
    # ... add your modules here
]
```

### Command-Line Override

You can also specify eligible modules via command-line (overrides config):

```bash
python -m __main__ --dir C:\Odoo\sh\src --generate-recommendations \
    --eligible-modules csl_contacts csl_project csl_sales
```

## How It Works

1. **Data Loading**: The tool loads field analysis data from CSV files
2. **Module Filtering**: Only modules in `ELIGIBLE_MODULES_FOR_CORE` are considered for consolidation
3. **Recommendations**: Generates recommendations only for eligible modules

## Example Usage

### Using config file (default):
```bash
python -m __main__ --dir C:\Odoo\sh\src --output results \
    --analyze-sharing --generate-recommendations
```

### Override with command-line:
```bash
python -m __main__ --dir C:\Odoo\sh\src --output results \
    --analyze-sharing --generate-recommendations \
    --eligible-modules csl_contacts csl_project my_module
```

## Output

The recommendations will only include:
- Modules from the eligible list
- Fields defined in those modules
- Dependencies between eligible modules

Modules not in the eligible list are completely excluded from the consolidation recommendations.

