# Debugging Constraints

## How to Enable/Disable Constraints

Edit `src/constraints/config/constraint_weights.yaml` and set any constraint to `false` to disable it:

```yaml
enabled_constraints:
  H10_no_trainer_overlap: false  # <-- DISABLE THIS ONE
  S01_maximize_grouping: true     # Keep this enabled
```

## Testing Strategy

### 1. Disable H10 (Most Expensive Constraint)

The H10 constraint creates 461k internal constraints. Disable it to test:

```yaml
H10_no_trainer_overlap: false
```

Run optimizer:
```bash
python src/optimizer.py --verbose --timeout 60
```

### 2. Disable All Grouping Constraints

Grouping creates 16k variables. Test without grouping:

```yaml
S01_maximize_grouping: false
H12_max_group_size: false
S05_preferred_grouping: false
```

### 3. Minimal Constraint Set

Disable everything except essentials:

```yaml
enabled_constraints:
  # Keep only these
  H08_max_one_meeting_per_week: true
  H13_lab_completion: true
  
  # Disable all others
  H01_trainer_total_hours: false
  H02_trainer_availability: false
  # ... etc
```

## Constraint Costs (Estimated)

| Constraint | Variables | Internal Constraints | Notes |
|------------|-----------|---------------------|-------|
| **H10** | 1,924 | **461,760** | Most expensive! |
| S01 (grouping) | 16,000 | 64,000 | Necessary for budget |
| S02 | ~435 | ~870 | Low cost |
| Others | ~200 | ~1,000 | Negligible |

## Quick Tests

```bash
# Test 1: Disable H10 only
# Edit config, set H10_no_trainer_overlap: false
python src/optimizer.py --verbose --timeout 60

# Test 2: Minimal set (just completion)
# Disable all except H13
python src/optimizer.py --verbose --timeout 30

# Test 3: Small subset
python scripts/test_subset.py
```

## Expected Behavior

When you run with disabled constraints, you'll see:

```
⏸  Constraint H10 (No Trainer Overlap) is DISABLED
⚠  1 constraints disabled via configuration
```

The model will be smaller and faster, but may produce invalid solutions!

## Re-enabling

Set back to `true` in the YAML file and re-run.
