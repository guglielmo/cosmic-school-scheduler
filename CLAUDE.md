# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cosmic School is a school laboratory scheduling system that uses Google OR-Tools (CP-SAT solver) to assign workshops to classes and trainers, respecting complex constraints.

The system uses a **modular pipeline** approach: each lab has its own optimizer, and results are combined into a unified calendar with trainer assignments.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Or with uv (recommended)
uv pip install -r requirements.txt
```

## Project Structure

```
src/
├── optimizers/                    # Lab scheduling optimizers
│   ├── lab4_citizen_science.py    # Citizen Science (5 meetings)
│   ├── lab5_orientamento.py       # Orientamento e competenze (2 meetings)
│   ├── lab7_sensibilizzazione.py  # Sensibilizzazione (2 consecutive meetings)
│   ├── lab8_lab9.py               # Presentazione manuali + pt.2
│   └── trainer_assignment.py      # Assigns trainers to scheduled labs
│
├── generators/                    # Calendar and data generation
│   ├── build_slots_calendar.py    # Creates time slot matrix
│   ├── build_class_availability.py # Class availability per slot
│   ├── generate_formatrici_availability.py # Trainer availability
│   ├── generate_unified_calendar.py # Combines all lab calendars
│   └── generate_views.py          # Generates calendar views
│
├── utils/
│   └── date_utils.py              # Date mapping utilities
│
└── verify_constraints.py          # Constraint verification script
```

## Commands

```bash
# Run individual lab optimizers
python src/optimizers/lab4_citizen_science.py
python src/optimizers/lab5_orientamento.py
python src/optimizers/lab7_sensibilizzazione.py
python src/optimizers/lab8_lab9.py

# Generate unified calendar
python src/generators/generate_unified_calendar.py

# Assign trainers
python src/optimizers/trainer_assignment.py -v

# Generate views
python src/generators/generate_views.py

# Verify constraints
python src/verify_constraints.py
```

As a general rule, optimization runs should be launched by the user in a separate shell. Just provide the command and wait for results to be pasted into the conversation.

## Pipeline Overview

1. **Build availability matrices** (run once):
   - `build_slots_calendar.py` - Creates slot structure
   - `build_class_availability.py` - Class availability per slot
   - `generate_formatrici_availability.py` - Trainer availability

2. **Run lab optimizers** (in order):
   - Lab 4 (Citizen Science) - first, has most meetings
   - Lab 5 (Orientamento) - respects Lab 4 schedule
   - Lab 7 (Sensibilizzazione) - after Lab 4 and 5 complete
   - Lab 8/9 - last (Lab 8 must be final lab for each class)

3. **Generate unified calendar**:
   - Combines all lab calendars into one matrix

4. **Assign trainers**:
   - Distributes trainers proportionally to their hours budget
   - Respects trainer availability and groupings (accorpamenti)

5. **Generate views**:
   - Per-trainer, per-class, per-lab, daily views

6. **Verify constraints**:
   - Checks hours, lab completion, integrity

## Key Concepts

### Accorpamenti (Groupings)
Multiple classes can attend the same lab meeting together, using only one trainer. This is critical for staying within the trainer hours budget.

### "Solo X incontri" Notes
Some classes have reduced meeting requirements noted in `laboratori_classi.csv`:
- "solo 1 incontro" - only 1 meeting instead of default
- "solo 2 incontri" - only 2 meetings instead of default

### Trainer Availability
- Trainers have day/timeslot preferences (morning/afternoon)
- One trainer (Margherita) has specific date availability
- Saturday work varies by trainer

## Input Data

CSV files in `data/input/`:
- `scuole.csv`: Schools
- `classi.csv`: Classes with grouping preferences
- `formatrici.csv`: Trainers with hours budget and availability
- `laboratori.csv`: Workshops (5 FOP labs)
- `laboratori_classi.csv`: Class-lab assignments, fixed dates, special notes
- `fasce_orarie_classi.csv`: Class time slot constraints
- `date_escluse_classi.csv`: Excluded dates per class
- `formatrici_classi.csv`: Trainer-class preferences

## Output

- `data/output/calendario_laboratori.csv` - Unified lab calendar (matrix format)
- `data/output/calendario_con_formatrici.csv` - Calendar with trainer assignments
- `data/output/views/` - Various calendar views

## Budget Context

**Critical**: Grouping has highest optimization priority because:
- Total budget: 708 hours (sum of 4 trainers)
- With max grouping: ~500 hours needed
- Without grouping: exceeds budget

Therefore, maximizing class grouping is essential for feasibility.

## Constraint Specification

See `INTERPRETAZIONE_VINCOLI.md` for complete constraint definitions.
