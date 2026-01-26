# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cosmic School is a school laboratory scheduling optimizer that uses Google OR-Tools (CP-SAT solver) to assign workshops to classes and trainers, respecting complex hard and soft constraints.

**Current Version**: Optimizer with formal constraint system
**Constraint Specification**: See `INTERPRETAZIONE_VINCOLI.md` for complete constraint definitions

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Or with uv (recommended)
uv pip install -r requirements.txt
```

## Commands

```bash
# Run Optimizer
python src/optimizer.py --verbose --timeout 300

# Test on subset of data
python scripts/test_subset.py

# Run pipeline tests
python scripts/test_v7_pipeline.py

# Analyze constraint system
./analyze-constraints
```

As a general rule, optimization runs should be launched by the user in a separate shell. Just provide the command and wait for results to be pasted into the conversation.

## Architecture

### Optimizer (`src/optimizer.py`)

**Constraint-based scheduler** using formal constraint modeling system.

**Variables** (for each meeting of each class-lab pair):
- `settimana[class, lab, k]`: IntVar(0..15) - Week number
- `giorno[class, lab, k]`: IntVar(0..5) - Day (Mon-Sat)
- `fascia[class, lab, k]`: IntVar(1..3) - Time slot (morning1, morning2, afternoon)
- `formatrice[class, lab, k]`: IntVar(1..4) - Trainer ID
- `accorpa[c1, c2, lab]`: BoolVar - True if classes grouped together

**Key Features**:
- Uses `ConstraintFactory` to load constraints from CSV data
- 14 Hard Constraints (H01-H14) - must be satisfied
- 10 Soft Constraints (S01-S10) - optimized in objective function
- Grouping optimization critical for budget feasibility
- Full traceability: each constraint mapped to INTERPRETAZIONE_VINCOLI.md

### Constraint System (`src/constraints/`)

Structured, type-safe constraint modeling:

```
src/constraints/
├── base.py              # Base classes (HardConstraint, SoftConstraint)
├── hard_constraints.py  # 14 hard constraints (H01-H14)
├── soft_constraints.py  # 10 soft constraints (S01-S10)
├── special_rules.py     # Special cases (Citizen Science gap, etc.)
├── factory.py           # ConstraintFactory - builds from CSV
└── README.md            # Complete constraint documentation
```

See `src/constraints/README.md` for detailed constraint documentation.

### Utilities

- `date_utils.py`: Date mapping for scheduling windows
- `export_formatter.py`: Transforms results to Excel format (4 sheets)

## Constraints

**Hard Constraints** (must be satisfied):
- H01: Trainer total hours budget
- H02: Trainer temporal availability
- H03: Fixed dates (pre-scheduled)
- H04-H07: Class-specific constraints
- H08: Max 1 meeting/week per class
- H09: Lab 8 must be last
- H10: No trainer overlap
- H11: Scheduling period (16 weeks)
- H12: Max 2 classes grouped together
- H13: Lab completion
- H14: Lab 9 before Lab 5

**Soft Constraints** (optimized):
- S01: **Maximize grouping (CRITICAL - weight 20)**
- S02: Trainer continuity per class
- S03-S10: Various preferences (time slots, sequences, etc.)

See `INTERPRETAZIONE_VINCOLI.md` for complete specifications.

## Input Data

CSV files in `data/input/`:
- `scuole.csv`: Schools
- `classi.csv`: Classes
- `formatrici.csv`: Trainers with hours budget and availability
- `laboratori.csv`: Workshops (5 FOP labs)
- `laboratori_classi.csv`: Class-lab assignments, fixed dates
- `fasce_orarie_classi.csv`: Class time slot constraints
- `date_escluse_classi.csv`: Excluded dates per class
- `formatrici_classi.csv`: Trainer-class preferences

## Output

- Default: `data/output/calendario.csv`
- Columns: class, school, lab, meeting number, trainer, week, day, time slot, date/time, grouped_with

## Solver Configuration

- Default timeout: 300s (5 minutes)
- 16 weeks scheduling horizon (2 windows: Jan 28 - Apr 1, Apr 13 - May 16)
- 12 parallel workers
- CP-SAT solver with constraint propagation

## Testing

```bash
# Create test subset (2 schools)
python scripts/create_test_subset.py

# Run on subset
python scripts/test_subset.py

# Pipeline smoke tests
python scripts/test_v7_pipeline.py
```

## Budget Context

**Critical**: Grouping (S01) has highest weight because:
- Total budget: 708 hours (sum of 4 trainers)
- With max grouping: 664 hours needed → **+44h margin** ✅
- Without grouping: 926 hours needed → **exceeds budget** ❌

Therefore, maximizing class grouping is essential for feasibility.
