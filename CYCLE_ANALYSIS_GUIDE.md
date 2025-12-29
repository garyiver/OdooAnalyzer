# How to Verify Inheritance Cycles in CSV Files

## CSV Files to Check

After running the analyzer, check these CSV files in `analysis_results/`:

### 1. `inheritance_cycles.csv`
**Purpose**: Lists all unique cycles and how many times each was detected

**Columns to check:**
- **Cycle**: The inheritance chain showing the cycle (e.g., `sale.order -> sale.order -> sale.order`)
- **Count**: How many times this cycle was detected (high count = likely false positive from repeated detection)
- **Models Involved**: Which models are in the cycle

**What to look for:**
- **Real cycles**: Should have a reasonable count (1-10). If count is 100+, it's likely a false positive from repeated detection
- **Self-referencing cycles**: `model -> model -> model` usually indicates a bug in the detection logic, not a real cycle
- **Multiple models in cycle**: Real cycles typically involve 2-3 different models

### 2. `models_in_cycles.csv`
**Purpose**: Shows which models are involved in cycles and how often

**Columns to check:**
- **Model**: The model name
- **Cycle Occurrences**: Total number of times this model appeared in cycle detections

**What to look for:**
- Models with very high occurrence counts (100+) are likely false positives
- Models that appear in multiple different cycles are more likely to have real issues

### 3. `fields_analysis.csv`
**Purpose**: Check if fields from models in cycles have issues

**Filter for models in cycles:**
- Look for fields where `model` matches models from `models_in_cycles.csv`
- Check if `root_module` and `is_extension` are set correctly
- If many fields from the same model have incorrect `root_module`, it might indicate a real inheritance issue

## How to Identify Real vs False Cycles

### Real Cycles (should investigate):
- ✅ Count < 10 in `inheritance_cycles.csv`
- ✅ Involves 2-3 different models
- ✅ Models are from different modules
- ✅ Cycle path makes logical sense (e.g., `A -> B -> A`)

### False Positives (can ignore):
- ❌ Count > 100 in `inheritance_cycles.csv`
- ❌ Self-referencing: `model -> model -> model`
- ❌ All models in cycle are from the same module
- ❌ Pattern: `sale.order -> sale.order -> sale.order` (same model repeated)

## Example Analysis

**If you see:**
```
Cycle: sale.order -> sale.order -> sale.order
Count: 500
```

**This is likely a false positive because:**
1. High count (500) suggests repeated detection
2. Self-referencing (same model)
3. The model is probably being detected during normalization for every field

**To verify:**
1. Check `models_in_cycles.csv` - if `sale.order` has 500+ occurrences, it's false
2. Check actual Python files - search for `_inherit = "sale.order"` in `sale.order` model definitions
3. Real cycles would show up as: `model_a -> model_b -> model_a` with different model names

## Quick Check Command

You can quickly check for likely false positives:
```python
# In Python or a script
import csv

with open('analysis_results/inheritance_cycles.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cycle = row['Cycle']
        count = int(row['Count'])
        models = set(cycle.split(' -> '))
        
        # Flag potential false positives
        if count > 50 or len(models) == 1:
            print(f"⚠️  Potential false positive: {cycle} (count: {count})")
```

## Next Steps

1. **Review `inheritance_cycles.csv`** - Focus on cycles with low counts (< 10)
2. **Check actual code** - For suspicious cycles, search the codebase for the inheritance definitions
3. **Filter by module** - Real cycles usually involve models from different modules
4. **Use `--cycle-verbosity=low`** - This reduces console spam while still generating the CSV files

