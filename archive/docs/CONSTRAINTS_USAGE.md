# Using the Constraint System

This guide explains how to use the structured constraint system for Cosmic School scheduling.

## Quick Start

### 1. Analyze Current Constraints

Run the analysis script to see all constraints extracted from your CSV data:

```bash
./analyze-constraints
```

This will:
- Load all CSV files from `data/input/`
- Build constraint objects
- Display summary statistics
- Export to `data/output/constraints_export.json`

### 2. Review Configuration

Edit constraint weights in `config/constraint_weights.yaml`:

```yaml
objective_function:
  maximize_grouping: 20      # CRITICAL: bonus for grouping
  trainer_continuity: 10     # Penalty for trainer changes
  fifth_year_priority: 3     # Penalty for late 5th year
  # ... etc
```

### 3. Use in Your Optimizer

```python
from constraints import ConstraintFactory

# Load constraints
factory = ConstraintFactory()
constraints = factory.build_all_constraints()

# Separate by type
hard_constraints = [c for c in constraints if c.type.value == 'hard']
soft_constraints = [c for c in constraints if c.type.value == 'soft']

# Add to your OR-Tools model
for constraint in hard_constraints:
    constraint.add_to_model(model, variables)

# Build objective function
objective_terms = []
for constraint in soft_constraints:
    term = constraint.add_to_objective(model, variables)
    objective_terms.append(constraint.weight * term)

model.Minimize(sum(objective_terms))
```

## File Structure

```
cosmic-school/
├── src/
│   └── constraints/
│       ├── base.py                  # Base classes
│       ├── hard_constraints.py      # Hard constraints (14)
│       ├── soft_constraints.py      # Soft constraints (10)
│       ├── special_rules.py         # Special cases (7)
│       ├── factory.py               # Builds from CSV
│       └── README.md                # Full documentation
│
├── config/
│   └── constraint_weights.yaml      # Configuration
│
├── examples/
│   └── constraint_example.py        # Usage example
│
├── tests/
│   └── test_constraints.py          # Unit tests
│
├── analyze-constraints              # Analysis script
└── CONSTRAINTS_USAGE.md             # This file
```

## Constraint Categories

### HARD Constraints (Must Be Satisfied)

| ID | Name | Source |
|----|------|--------|
| H01 | Trainer Total Hours | formatrici.csv: ore_generali |
| H02 | Trainer Availability | formatrici.csv: disponibilità |
| H03 | Fixed Dates | laboratori_classi.csv: date_fissate |
| H04 | Class-Lab Assignment | laboratori_classi.csv |
| H05 | Lab Time of Day | laboratori_classi.csv: dettagli |
| H06 | Class Time Slots | fasce_orarie_classi.csv |
| H07 | Class Excluded Dates | date_escluse_classi.csv |
| H08 | Max One Meeting/Week | General rule |
| H09 | Lab 8 Must Be Last | INTERPRETAZIONE_VINCOLI.md |
| H10 | No Trainer Overlap | General rule |
| H11 | Scheduling Period | Jan 28 - May 16 (excl. Easter) |
| H12 | Max Group Size | Max 2 classes per meeting |
| H13 | Lab Completion | All meetings scheduled |
| H14 | Lab 9 Before Lab 5 | Sequence requirement |

### SOFT Constraints (Preferences to Optimize)

| ID | Name | Weight | Purpose |
|----|------|--------|---------|
| S01 | Maximize Grouping | 20 | **CRITICAL**: Stay within budget |
| S02 | Trainer Continuity | 10 | Same trainer per class |
| S03 | Weekly Hours Target | 3 | Match average hours |
| S04 | Time Preference | 1 | Morning/afternoon preference |
| S05 | Preferred Grouping | 5 | Group preferred partners |
| S06 | Lab Sequence | 2 | Ideal sequence: 7→4→5 |
| S07 | Fifth Year Priority | 3 | Finish early, avoid May |
| S08 | Time Slot Variation | 2 | Rotate time slots |
| S09 | Balance Trainer Load | 2 | Even workload distribution |
| S10 | Minimize Late May | 1 | General earlier preference |

### Special Rules

| ID | Name | Description |
|----|------|-------------|
| SP01 | Citizen Science Gap | 1 week gap (autonomous meeting) |
| SP02 | Partial Lab Meetings | Some classes do fewer meetings |
| SP03 | Multi-Afternoon Non-Consecutive | N afternoons, not consecutive |
| SP04 | One Meeting Time | At least 1 meeting in specified time |
| SP05 | Weekday Time Specific | Specific days only at certain times |
| SP06 | Ignore External Labs | Only FOP labs (4,5,7,8,9) |
| SP07 | Saturday Only Margherita | Only she can work Saturday |

## Budget Context

**Why S01 (Maximize Grouping) is CRITICAL:**

```
Budget: 708 hours total
├─ Anita:       292h
├─ Andreea:     128h
├─ Ida:         160h
└─ Margherita:  128h

Requirements:
├─ With optimal grouping:    664h  ← +44h margin ✅
└─ Without grouping:         926h  ← EXCEEDS BUDGET ❌
```

Grouping is not just a preference - it's **essential** to stay within budget.

## CSV Data Mapping

### formatrici.csv
```csv
formatrice_id,nome,ore_generali,lavora_sabato,mattine_disponibili,...
1,Anita,292,no,"lun,mar,mer,gio,ven","lun,mar,mer,gio,ven",
```
→ H01, H02, H10, S03, S04

### classi.csv
```csv
classe_id,nome,scuola_id,anno,priorita,accorpamento_preferenziale
5,5B,1,5,alta,5C
```
→ H08, H09, S05, S07, S08

### laboratori_classi.csv
```csv
classe_id,nome_classe,scuola_id,laboratorio_id,dettagli,date_fissate
1,3A,1,4,,"26 febbraio 9-13"
```
→ H03, H04, H05, H13, SP02, SP03, SP04

### fasce_orarie_classi.csv
```csv
classe_id,nome_classe,fasce_disponibili,preferenza,giorni_settimana
7,4BNO,pomeriggio,disponibile,"lunedì, martedì, mercoledì, giovedì"
```
→ H06, SP05

### date_escluse_classi.csv
```csv
classe_id,nome_classe,date_escluse
5,5B,15 gennaio
```
→ H07

### formatrici_classi.csv
```csv
formatrice_id,nome_formatrice,classe_id,nome_classe
1,Anita,1,3A
```
→ S02 (trainer continuity preference)

## Common Tasks

### Check Total Constraint Count

```bash
./analyze-constraints | grep "Total constraints"
```

### Export Constraints to JSON

```bash
./analyze-constraints --export
# Creates: data/output/constraints_export.json
```

### Filter Constraints by Category

```python
from constraints import ConstraintFactory, ConstraintCategory

factory = ConstraintFactory()
constraints = factory.build_all_constraints()

# Get all temporal constraints
temporal = [c for c in constraints
            if c.category == ConstraintCategory.TEMPORAL]

print(f"Temporal constraints: {len(temporal)}")
for c in temporal:
    print(f"  [{c.id}] {c.name}")
```

### Get Trainer Budget Summary

```python
from constraints import ConstraintFactory, TrainerTotalHoursConstraint

factory = ConstraintFactory()
constraints = factory.build_all_constraints()

trainer_budgets = [c for c in constraints
                   if isinstance(c, TrainerTotalHoursConstraint)]

total = sum(c.max_hours for c in trainer_budgets)
print(f"Total budget: {total} hours")

for c in trainer_budgets:
    print(f"  {c.trainer_name}: {c.max_hours}h")
```

### Validate Constraint Configuration

```python
from constraints import ConstraintFactory

factory = ConstraintFactory()

# Check config loaded
print(f"Config loaded: {factory.config is not None}")
print(f"Objective weights: {factory.config.get('objective_function', {})}")

# Build and validate
constraints = factory.build_all_constraints()
summary = factory.get_constraint_summary(constraints)

print(f"Total: {summary['total']}")
print(f"Hard: {summary['by_type']['hard']}")
print(f"Soft: {summary['by_type']['soft']}")
```

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/test_constraints.py -v

# With coverage
pytest tests/test_constraints.py --cov=src/constraints
```

## Modifying Weights

Edit `config/constraint_weights.yaml` and adjust weights:

```yaml
objective_function:
  # Increase priority of fifth-year classes
  fifth_year_priority: 5  # was: 3

  # Reduce importance of time slot variation
  time_slot_variation: 1  # was: 2
```

Then rebuild constraints:

```python
factory = ConstraintFactory()  # Will reload config
constraints = factory.build_all_constraints()
```

## Adding New Constraints

See `src/constraints/README.md` section "Extending the System" for detailed instructions.

Quick example:

```python
# 1. Add to hard_constraints.py or soft_constraints.py
@dataclass
class MyNewConstraint(HardConstraint):
    param1: int

    id: str = "H15"
    name: str = "My New Constraint"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Description here"

    def validate(self, solution):
        # Implementation
        pass

    def add_to_model(self, model, variables):
        # Implementation
        pass

# 2. Add to factory.py if building from CSV
def _build_my_constraints(self):
    constraints = []
    for row in self.csv_data.get('some_file', []):
        constraints.append(MyNewConstraint(
            param1=int(row['column'])
        ))
    return constraints

# 3. Call from build_all_constraints()
def build_all_constraints(self):
    # ...
    constraints.extend(self._build_my_constraints())
    # ...
```

## Troubleshooting

### "Config file not found"
Ensure `config/constraint_weights.yaml` exists. The factory will work without it but use default weights.

### "CSV file not found"
Check that all required CSV files are in `data/input/`:
- formatrici.csv
- classi.csv
- scuole.csv
- laboratori.csv
- laboratori_classi.csv
- fasce_orarie_classi.csv
- date_escluse_classi.csv
- formatrici_classi.csv

### "Import error: No module named 'constraints'"
Ensure you're running from project root and `src/` is in Python path:

```python
import sys
sys.path.insert(0, 'src')
from constraints import ConstraintFactory
```

### "Weight mismatch warning"
If a soft constraint has a default weight different from config, the config takes precedence:

```python
# In code: weight=5
# In config: my_constraint: 10
# Result: weight=10 (config wins)
```

## Next Steps

1. Run `./analyze-constraints` to see current state
2. Review `data/output/constraints_export.json`
3. Adjust weights in `config/constraint_weights.yaml`
4. Integrate constraints into your optimizer (see `src/optimizer_V5_pp.py`)
5. Run tests: `pytest tests/test_constraints.py`

## References

- **Full constraint specs**: `INTERPRETAZIONE_VINCOLI.md`
- **Implementation details**: `src/constraints/README.md`
- **Example usage**: `examples/constraint_example.py`
- **Configuration**: `config/constraint_weights.yaml`
- **Tests**: `tests/test_constraints.py`
