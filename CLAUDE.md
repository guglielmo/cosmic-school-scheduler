# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cosmic School is a school laboratory scheduling optimizer that uses Google OR-Tools (CP-SAT solver) to assign workshops to classes and trainers, respecting complex constraints.

## Commands

```bash
# Run basic optimizer (simpler, week-based scheduling)
./optimize

# Run V2 optimizer (with time slots per school and trainer preferences)
./optimize-v2
```

As a general rule, the optimization runs should be launched by the user in a separate shell, not by me in a subshell, within the conversation. So just provide the command (assuming the virtualenv has been already activated) and sit bax, relax, and wait for results to be cut and pasted into the conversation.

Both scripts auto-create virtualenv with `uv` if missing, installing: pandas, openpyxl, ortools.

## Architecture

### Two Optimizer Versions

**V1 (`src/optimizer.py`):** Basic optimizer using week as the temporal unit. Variables are `assignment[class, lab, trainer, week]`. Faster, simpler.

**V2 (`src/optimizer_v2.py`):** Extended optimizer with day and time slot granularity. Variables are `assignment[class, lab, trainer, week, day, slot]`. Handles:
- Per-school time slots (`esempio_fasce_orarie_scuole.csv`)
- Trainer time preferences (morning/afternoon/mixed)
- Rotation of time slots to avoid burdening same teachers

### Export Formatter (`src/export_formatter.py`)

Transforms optimizer results into the required 4-sheet Excel format:
- `complessivo`: Full calendar with all details (16 columns)
- `per_formatore_sett_data`: View by trainer sorted by date
- `per_scuola_per_Classe`: View by school and class
- `per_scuola_per_data`: View by school sorted by date

Activity mapping (lab name → activity code):
- Citizen Science → A3
- Discriminazioni di genere → A5
- Orientamento e competenze → A6
- Presentazione manuali → A7

### Constraints (Hard)

1. Each class completes all workshops
2. Max 1 meeting/week per class
3. Workshop sequentiality (lab N+1 starts only after lab N completes)
4. No trainer overlap (same time slot)

### Constraints (Soft, minimized in objective)

1. Minimize trainer changes per class (continuity weight: 10)
2. Avoid same time slot in consecutive weeks (weight: 2)
3. Respect trainer time preferences (weight: 1)

## Input Data Format

CSV files in `data/input/`:
- `esempio_scuole.csv`: school_id, name, city, time_preference, saturday_available
- `esempio_classi.csv`: class_id, name, school_id, year, priority
- `esempio_formatrici.csv`: trainer_id, name, max_weekly_hours, works_saturday, available_days, slot_preference
- `esempio_laboratori.csv`: lab_id, name, num_meetings, hours_per_meeting, sequence
- `esempio_fasce_orarie_scuole.csv` (V2): school_id, slot_id, name, start_time, end_time, day_type

## Output

- V1: `data/output/calendario_ottimizzato.xlsx`
- V2: `data/output/calendario_v2_con_fasce.xlsx`

## Solver Configuration

- Default timeout: 120s (V1) / 180s (V2)
- 20 weeks scheduling horizon (January-May)
- Max 2 meetings/week per trainer (V1 constraint)
