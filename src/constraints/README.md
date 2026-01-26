# Constraint System Documentation

Structured constraint modeling for Cosmic School scheduling optimizer.

## Overview

This constraint system provides a structured, type-safe way to express scheduling constraints based on CSV data and INTERPRETAZIONE_VINCOLI.md specifications.

## Architecture

```
constraints/
├── base.py                  # Base classes (Constraint, HardConstraint, SoftConstraint)
├── hard_constraints.py      # Hard constraints (MUST be satisfied)
├── soft_constraints.py      # Soft constraints (preferences to optimize)
├── special_rules.py         # Special case constraints
├── factory.py               # Factory to build constraints from CSV
└── __init__.py              # Package exports
```

## Constraint Hierarchy

```
Constraint (ABC)
├── HardConstraint (must be satisfied)
│   ├── H01: TrainerTotalHoursConstraint
│   ├── H02: TrainerAvailabilityConstraint
│   ├── H03: FixedDatesConstraint
│   ├── H04: ClassLabAssignmentConstraint
│   ├── H05: LabTimeOfDayConstraint
│   ├── H06: ClassTimeSlotsConstraint
│   ├── H07: ClassExcludedDatesConstraint
│   ├── H08: MaxOneMeetingPerWeekConstraint
│   ├── H09: Lab8LastConstraint
│   ├── H10: NoTrainerOverlapConstraint
│   ├── H11: SchedulingPeriodConstraint
│   ├── H12: MaxGroupSizeConstraint
│   ├── H13: LabCompletionConstraint
│   └── H14: Lab9BeforeLab5Constraint
│
└── SoftConstraint (preferences to optimize)
    ├── S01: MaximizeGroupingConstraint (CRITICAL)
    ├── S02: TrainerContinuityConstraint
    ├── S03: TrainerWeeklyHoursConstraint
    ├── S04: TrainerTimePreferenceConstraint
    ├── S05: PreferredGroupingConstraint
    ├── S06: LabSequenceConstraint
    ├── S07: FifthYearPriorityConstraint
    ├── S08: TimeSlotVariationConstraint
    ├── S09: BalanceTrainerLoadConstraint
    └── S10: MinimizeLateMaySchedulingConstraint

Special Rules:
├── SP01: CitizenScienceGapConstraint
├── SP02: PartialLabMeetingsConstraint
├── SP03: MultiMeetingAfternoonConstraint
├── SP04: OneMeetingTimeConstraint
├── SP05: WeekdayTimeSpecificConstraint
├── SP06: IgnoreExternalLabsConstraint
└── SP07: SaturdayOnlyMargheritaConstraint
```

## Usage

### Basic Usage

```python
from constraints import ConstraintFactory

# Initialize factory
factory = ConstraintFactory(
    data_dir="data/input",
    config_path="config/constraint_weights.yaml"
)

# Build all constraints from CSV data
constraints = factory.build_all_constraints()

# Filter by type
hard_constraints = [c for c in constraints if c.type.value == 'hard']
soft_constraints = [c for c in constraints if c.type.value == 'soft']

# Filter by category
from constraints import ConstraintCategory
temporal = [c for c in constraints if c.category == ConstraintCategory.TEMPORAL]
```

### Working with Individual Constraints

```python
from constraints import TrainerTotalHoursConstraint

# Create constraint manually
constraint = TrainerTotalHoursConstraint(
    trainer_id=1,
    trainer_name="Anita",
    max_hours=292
)

# Access properties
print(constraint.id)           # "H01"
print(constraint.name)         # "Trainer Total Hours"
print(constraint.type.value)   # "hard"
print(constraint.category.value)  # "capacity"
print(constraint.description)  # Full description

# Export to dict
data = constraint.to_dict()
```

### Generating Reports

```python
# Get summary statistics
summary = factory.get_constraint_summary(constraints)

print(f"Total: {summary['total']}")
print(f"Hard: {summary['by_type']['hard']}")
print(f"Soft: {summary['by_type']['soft']}")
print(f"By category: {summary['by_category']}")

# Export to JSON
factory.export_constraints_to_json(constraints, "output/constraints.json")
```

### Integrating with Optimizer

Each constraint class has two key methods for OR-Tools integration:

```python
class MyConstraint(HardConstraint):
    def validate(self, solution: Any) -> bool:
        """Check if solution satisfies this constraint."""
        # Implement validation logic
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint to CP-SAT model."""
        # Implement: model.Add(...)
        pass
```

For soft constraints:

```python
class MySoftConstraint(SoftConstraint):
    def penalty(self, solution: Any) -> float:
        """Calculate penalty for this constraint."""
        # Return 0 if satisfied, higher values for violations
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add term to objective function."""
        # Return expression to minimize
        pass
```

## Constraint Categories

### TEMPORAL
Time-related constraints (dates, slots, schedules)
- H02: Trainer availability
- H03: Fixed dates
- H05: Lab time of day
- H06: Class time slots
- H07: Excluded dates
- H08: Max one meeting per week
- H11: Scheduling period
- S07: Fifth year priority
- S08: Time slot variation

### CAPACITY
Resource capacity constraints (hours, overlaps)
- H01: Trainer total hours
- H10: No trainer overlap
- S03: Trainer weekly hours
- S09: Balance trainer load

### SEQUENCING
Order and sequence constraints
- H09: Lab 8 must be last
- H14: Lab 9 before Lab 5
- S06: Lab sequence preference
- SP01: Citizen Science gap

### ASSIGNMENT
Assignment constraints (who does what)
- H04: Class-lab assignment
- H13: Lab completion
- S02: Trainer continuity

### GROUPING
Class grouping constraints
- H12: Max group size
- S01: Maximize grouping
- S05: Preferred grouping

## Configuration

Edit `config/constraint_weights.yaml` to adjust weights:

```yaml
objective_function:
  maximize_grouping: 20      # CRITICAL: bonus for grouping
  trainer_continuity: 10     # Penalty for trainer changes
  fifth_year_priority: 3     # Penalty for late 5th year
  # ... etc
```

## Data Sources

Constraints are built from CSV files:

- **formatrici.csv** → Trainer constraints (H01, H02, H10, S02, S03, S04)
- **classi.csv** → Class constraints (H08, H09, S05, S07, S08)
- **laboratori.csv** → Lab definitions (H13)
- **laboratori_classi.csv** → Class-lab assignments (H03, H04, H05, H13, SP02, SP03, SP04)
- **fasce_orarie_classi.csv** → Time slot constraints (H06, SP05)
- **date_escluse_classi.csv** → Excluded dates (H07)
- **formatrici_classi.csv** → Trainer-class preferences (S02)
- **scuole.csv** → School information (SP01)

## Special Cases

### Citizen Science (Lab 4.0)
For schools: Potenza, Vasto, Bafile, Lanciano, Peano Rosa
- Schedule only 4 meetings (not 5)
- Leave 1-week gap between meeting 2 and 4
- Week 3 = autonomous meeting (no trainer)

### Lab 8.0 (Presentazione Manuali)
MUST be the last lab scheduled for every class (HARD)

### Lab 9.0 and 5.0
Lab 9.0 must come before Lab 5.0 (HARD)

### Partial Meetings
Some classes do fewer meetings than standard:
- "solo 1 incontro" = only 1 meeting
- "solo 2 incontri" = only 2 meetings

### Afternoon Requirements
Various requirements for afternoon meetings:
- "pomeriggio" = ALL meetings in afternoon
- "un incontro deve essere di pomeriggio" = at least 1 afternoon
- "2 incontri devono essere di pomeriggio ma non in settimane consecutive" = 2 afternoon, non-consecutive

## Budget Context

Understanding why grouping (S01) is CRITICAL:

- **Total budget**: 708 hours (sum of all trainer hours)
- **With max grouping**: 664 hours needed → **+44h margin** ✅
- **Without grouping**: 926 hours needed → **exceeds budget** ❌

Therefore, `maximize_grouping` has the highest weight (20) to ensure budget feasibility.

## Testing

```python
# Test individual constraint
constraint = TrainerTotalHoursConstraint(
    trainer_id=1,
    trainer_name="Anita",
    max_hours=292
)

# Create mock solution
solution = {...}

# Validate
is_valid = constraint.validate(solution)
print(f"Constraint satisfied: {is_valid}")
```

## Extending the System

To add a new constraint:

1. Choose the appropriate base class (`HardConstraint` or `SoftConstraint`)
2. Define the constraint class in the appropriate file
3. Implement `validate()` and `add_to_model()` (for hard)
4. Or implement `penalty()` and `add_to_objective()` (for soft)
5. Add to `factory.py` if it should be built from CSV
6. Add weight to `constraint_weights.yaml` if soft

Example:

```python
@dataclass
class MyNewConstraint(HardConstraint):
    """Description of constraint."""
    param1: int
    param2: str

    id: str = "H15"
    name: str = "My New Constraint"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Detailed description"

    def validate(self, solution: Any) -> bool:
        # Implement validation
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        # Add to CP-SAT model
        pass
```

## See Also

- `INTERPRETAZIONE_VINCOLI.md` - Full constraint specifications
- `config/constraint_weights.yaml` - Weight configuration
- `examples/constraint_example.py` - Usage examples
