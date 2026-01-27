"""
Trainer Assignment Optimizer for Cosmic School Scheduler.

Reads the complete lab calendar and assigns trainers (formatrici) to slots,
distributing workload proportionally to their available hours.

Output format: L4-1/3-1-4B:1-Anita (lab info : trainer_id-trainer_name)
"""

import csv
import re
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set
from ortools.sat.python import cp_model


class TrainerData:
    """Holds trainer information and availability."""

    def __init__(self, trainer_id: int, name: str, hours: int, works_saturday: bool,
                 morning_days: Set[str], afternoon_days: Set[str], specific_dates: List[str]):
        self.id = trainer_id
        self.name = name
        self.hours = hours
        self.works_saturday = works_saturday
        self.morning_days = morning_days
        self.afternoon_days = afternoon_days
        self.specific_dates = specific_dates  # For Margherita
        self.parsed_specific_slots = self._parse_specific_dates()

    def _parse_specific_dates(self) -> Set[Tuple[str, str]]:
        """Parse specific date availability into (date, timeslot) tuples."""
        slots = set()
        if not self.specific_dates:
            return slots

        for date_entry in self.specific_dates:
            date_entry = date_entry.strip()
            if not date_entry:
                continue

            # Format: "13 Gennaio 10.00-14.00"
            match = re.match(r'(\d+)\s+(\w+)\s+(\d+)\.(\d+)-(\d+)\.(\d+)', date_entry)
            if match:
                day = int(match.group(1))
                month_name = match.group(2).lower()
                start_hour = int(match.group(3))
                end_hour = int(match.group(5))

                month_map = {
                    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
                    'maggio': 5, 'giugno': 6
                }
                month = month_map.get(month_name, 1)

                # Create date string in format matching slot_id
                date_obj = datetime(2026, month, day)
                date_str = date_obj.strftime('%m-%d')  # e.g., "01-13"

                # Determine timeslots covered
                # M1: 08:00-10:00 or 09:00-11:00
                # M2: 10:00-12:00 or 11:00-13:00
                # P: 14:00-18:00 or 15:00-17:00
                if start_hour <= 10 and end_hour >= 10:
                    slots.add((date_str, 'M1'))
                if start_hour <= 12 and end_hour >= 12:
                    slots.add((date_str, 'M2'))
                if start_hour <= 11 and end_hour >= 13:
                    slots.add((date_str, 'M2'))
                if (start_hour >= 14 or (start_hour <= 14 and end_hour >= 16)):
                    slots.add((date_str, 'P'))
                if start_hour <= 9 and end_hour >= 11:
                    slots.add((date_str, 'M1'))
                if start_hour <= 11 and end_hour >= 13:
                    slots.add((date_str, 'M2'))
                if start_hour <= 8 and end_hour >= 10:
                    slots.add((date_str, 'M1'))
                if start_hour <= 12 and end_hour >= 14:
                    slots.add((date_str, 'M2'))

        return slots

    def is_available(self, slot_id: str) -> bool:
        """
        Check if trainer is available for a given slot.

        slot_id format: s{week}-{month}-{day}-{weekday}-{timeslot}
        e.g., s00-01-29-gio-M1
        """
        parts = slot_id.split('-')
        if len(parts) < 5:
            return False

        month = parts[1]
        day = parts[2]
        weekday = parts[3].lower()
        timeslot = parts[4]  # M1, M2, P

        # If trainer has specific dates (Margherita), check those
        if self.specific_dates:
            date_str = f"{month}-{day}"
            return (date_str, timeslot) in self.parsed_specific_slots

        # Check Saturday
        if weekday == 'sab' and not self.works_saturday:
            return False

        # Check day/timeslot availability
        is_morning = timeslot in ('M1', 'M2')

        if is_morning:
            return weekday in self.morning_days
        else:  # afternoon
            return weekday in self.afternoon_days


class LabSlot:
    """Represents a lab assignment in a slot."""

    def __init__(self, slot_id: str, col_idx: int, col_name: str, cell_value: str):
        self.slot_id = slot_id
        self.col_idx = col_idx
        self.col_name = col_name  # e.g., "3-1-4B" (school_id-class_id-class_name)
        self.cell_value = cell_value  # e.g., "L4-1/3-1-4B"
        self.class_id = self._extract_class_id()
        self.lab_meeting_key = self._extract_lab_meeting_key()

    def _extract_class_id(self) -> Optional[int]:
        """Extract class_id from column name or cell value."""
        # Column name format: {col_num}-{school_id}-{class_name}
        # Cell value format: L{lab}-{meeting}/{col_num}-{school_id}-{class_name}

        # Try from cell value first
        match = re.search(r'/(\d+)-\d+-', self.cell_value)
        if match:
            return int(match.group(1))

        # Try from column name
        parts = self.col_name.split('-')
        if len(parts) >= 2:
            try:
                return int(parts[0])
            except ValueError:
                pass

        return None

    def _extract_lab_meeting_key(self) -> str:
        """Extract lab-meeting key for grouping (e.g., 'L4-1' from 'L4-1/3-1-4B')."""
        # Format: L{lab}-{meeting}/...
        match = re.match(r'(L\d+-\d+)', self.cell_value)
        if match:
            return match.group(1)
        return self.cell_value


class LabGroup:
    """Represents a group of accorpated lab slots (same lab-meeting at same time)."""

    def __init__(self, slot_id: str, lab_meeting_key: str):
        self.slot_id = slot_id
        self.lab_meeting_key = lab_meeting_key
        self.lab_slots: List[LabSlot] = []

    def add_slot(self, lab_slot: LabSlot):
        self.lab_slots.append(lab_slot)

    @property
    def class_ids(self) -> Set[int]:
        return {ls.class_id for ls in self.lab_slots if ls.class_id}

    @property
    def col_indices(self) -> List[int]:
        return [ls.col_idx for ls in self.lab_slots]


def load_trainers(filepath: str) -> Dict[int, TrainerData]:
    """Load trainer data from CSV."""
    trainers = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trainer_id = int(row['formatrice_id'])
            name = row['nome']
            hours = int(row['ore_generali'])
            works_saturday = row['lavora_sabato'].lower() == 'si'

            # Parse morning/afternoon availability
            morning_str = row.get('mattine_disponibili', '')
            afternoon_str = row.get('pomeriggi_disponibili', '')

            morning_days = set()
            afternoon_days = set()

            if morning_str:
                morning_days = {d.strip().lower() for d in morning_str.split(',') if d.strip()}
            if afternoon_str:
                afternoon_days = {d.strip().lower() for d in afternoon_str.split(',') if d.strip()}

            # Parse specific dates (for Margherita)
            specific_dates = []
            dates_str = row.get('date_disponibili', '')
            if dates_str:
                specific_dates = [d.strip() for d in dates_str.split(';') if d.strip()]

            trainers[trainer_id] = TrainerData(
                trainer_id, name, hours, works_saturday,
                morning_days, afternoon_days, specific_dates
            )

    return trainers


def load_trainer_class_preferences(filepath: str) -> Dict[int, Set[int]]:
    """Load trainer-class preferences. Returns dict: trainer_id -> set of class_ids."""
    preferences = defaultdict(set)

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trainer_id = int(row['formatrice_id'])
            class_id = int(row['classe_id'])
            preferences[trainer_id].add(class_id)

    return dict(preferences)


def load_calendar(filepath: str) -> Tuple[List[str], List[str], List[List[str]]]:
    """
    Load calendar CSV.

    Returns:
        - headers: column headers
        - slot_ids: list of slot IDs (first column values)
        - data: 2D list of cell values
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)

        slot_ids = []
        data = []

        for row in reader:
            if row:
                slot_ids.append(row[0])
                data.append(row[1:])  # Exclude slot_id column

    return headers[1:], slot_ids, data  # Exclude slot_id from headers


def extract_lab_slots(headers: List[str], slot_ids: List[str],
                      data: List[List[str]]) -> List[LabSlot]:
    """Extract all lab assignments from calendar."""
    lab_slots = []

    for row_idx, slot_id in enumerate(slot_ids):
        for col_idx, cell in enumerate(data[row_idx]):
            # Skip non-lab cells (X, -, empty, or just lab code without full info)
            if cell in ('X', '-', '') or not cell.startswith('L'):
                continue

            # Must have format L{lab}-{meeting}/{class_info} or L{lab}-{meeting}
            if '/' in cell:
                col_name = headers[col_idx] if col_idx < len(headers) else str(col_idx)
                lab_slots.append(LabSlot(slot_id, col_idx, col_name, cell))

    return lab_slots


def group_lab_slots(lab_slots: List[LabSlot]) -> List[LabGroup]:
    """
    Group lab slots by (slot_id, lab_meeting_key) to identify accorpamenti.

    Labs with the same lab-meeting key at the same time are grouped together
    and need only ONE trainer.
    """
    groups_dict: Dict[Tuple[str, str], LabGroup] = {}

    for ls in lab_slots:
        key = (ls.slot_id, ls.lab_meeting_key)
        if key not in groups_dict:
            groups_dict[key] = LabGroup(ls.slot_id, ls.lab_meeting_key)
        groups_dict[key].add_slot(ls)

    return list(groups_dict.values())


def optimize_trainer_assignment(
    trainers: Dict[int, TrainerData],
    trainer_prefs: Dict[int, Set[int]],
    lab_groups: List[LabGroup],
    verbose: bool = True
) -> Dict[Tuple[str, int], int]:
    """
    Use OR-Tools to assign trainers to lab groups.

    Each LabGroup represents an accorpamento (grouped classes) that needs ONE trainer.

    Returns:
        Dict mapping (slot_id, col_idx) -> trainer_id for all individual slots
    """
    model = cp_model.CpModel()

    # Group by slot_id (same time) for overlap constraint
    groups_by_time = defaultdict(list)
    for lg in lab_groups:
        groups_by_time[lg.slot_id].append(lg)

    trainer_ids = list(trainers.keys())

    # Pre-check: find slots with availability issues
    if verbose:
        print("\nChecking slot availability...")
        problem_slots = []
        for slot_id, group_list in groups_by_time.items():
            available_trainers = [
                t_id for t_id in trainer_ids
                if trainers[t_id].is_available(slot_id)
            ]
            num_groups = len(group_list)
            num_trainers = len(available_trainers)
            if num_trainers < num_groups:
                problem_slots.append((slot_id, num_groups, num_trainers, available_trainers))

        if problem_slots:
            print(f"  WARNING: {len(problem_slots)} time slots have insufficient trainers:")
            for slot_id, num_groups, num_trainers, avail in problem_slots[:10]:
                avail_names = [trainers[t].name for t in avail]
                print(f"    {slot_id}: {num_groups} groups, {num_trainers} trainers available ({avail_names})")
            if len(problem_slots) > 10:
                print(f"    ... and {len(problem_slots) - 10} more")
        else:
            print("  All slots have sufficient trainer availability")

    # Variables: for each lab GROUP, which trainer is assigned
    # x[group_idx, trainer_id] = 1 if trainer assigned to group
    x = {}

    for g_idx, lg in enumerate(lab_groups):
        for t_id in trainer_ids:
            x[(g_idx, t_id)] = model.NewBoolVar(f'x_{g_idx}_{t_id}')

    # Constraint 1: Each group has exactly one trainer
    for g_idx in range(len(lab_groups)):
        model.Add(sum(x[(g_idx, t_id)] for t_id in trainer_ids) == 1)

    # Constraint 2: Trainer availability
    for g_idx, lg in enumerate(lab_groups):
        for t_id, trainer in trainers.items():
            if not trainer.is_available(lg.slot_id):
                model.Add(x[(g_idx, t_id)] == 0)

    # Constraint 3: No trainer overlap (same trainer can't be in two places at once)
    # Build index mapping: slot_id -> list of group indices
    slot_to_groups = defaultdict(list)
    for g_idx, lg in enumerate(lab_groups):
        slot_to_groups[lg.slot_id].append(g_idx)

    for slot_id, group_indices in slot_to_groups.items():
        for t_id in trainer_ids:
            # A trainer can be assigned to at most 1 group at any given time
            model.Add(sum(x[(g_idx, t_id)] for g_idx in group_indices) <= 1)

    # Count assignments per trainer (count groups, not individual slots)
    trainer_assignments = {}
    for t_id in trainer_ids:
        trainer_assignments[t_id] = sum(
            x[(g_idx, t_id)] for g_idx in range(len(lab_groups))
        )

    # Calculate target proportions based on hours
    total_hours = sum(t.hours for t in trainers.values())
    total_groups = len(lab_groups)

    target_groups = {}
    for t_id, trainer in trainers.items():
        target_groups[t_id] = int(total_groups * trainer.hours / total_hours)

    if verbose:
        print(f"\nTotal groups to assign: {total_groups}")
        print(f"Total trainer hours: {total_hours}")
        print("Target distribution:")
        for t_id, trainer in trainers.items():
            pct = trainer.hours / total_hours * 100
            print(f"  {trainer.name}: {target_groups[t_id]} groups ({pct:.1f}%)")

    # Objective: minimize deviation from target proportions
    deviations = {}
    for t_id in trainer_ids:
        dev_pos = model.NewIntVar(0, total_groups, f'dev_pos_{t_id}')
        dev_neg = model.NewIntVar(0, total_groups, f'dev_neg_{t_id}')

        model.Add(
            trainer_assignments[t_id] == target_groups[t_id] + dev_pos - dev_neg
        )

        deviations[t_id] = (dev_pos, dev_neg)

    # Soft constraint: prefer trainers with class preferences
    preference_bonus = []
    for g_idx, lg in enumerate(lab_groups):
        for t_id in trainer_ids:
            # Check if trainer has preference for any class in the group
            if lg.class_ids & trainer_prefs.get(t_id, set()):
                preference_bonus.append(x[(g_idx, t_id)])

    # Objective: minimize total deviation, maximize preference matches
    total_deviation = sum(d[0] + d[1] for d in deviations.values())
    total_preferences = sum(preference_bonus) if preference_bonus else 0

    # Weight: deviation is more important (x10)
    model.Minimize(10 * total_deviation - total_preferences)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    solver.parameters.num_search_workers = 8

    if verbose:
        print("\nSolving...")

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"No solution found! Status: {solver.StatusName(status)}")
        return {}

    if verbose:
        print(f"Solution found! Status: {solver.StatusName(status)}")
        print(f"Objective value: {solver.ObjectiveValue()}")

    # Extract assignments - expand groups back to individual slots
    assignments = {}
    for g_idx, lg in enumerate(lab_groups):
        for t_id in trainer_ids:
            if solver.Value(x[(g_idx, t_id)]) == 1:
                # Assign this trainer to ALL slots in the group
                for ls in lg.lab_slots:
                    assignments[(ls.slot_id, ls.col_idx)] = t_id
                break

    # Print distribution stats
    if verbose:
        print("\nActual distribution (by groups):")
        counts = defaultdict(int)
        for g_idx, lg in enumerate(lab_groups):
            for t_id in trainer_ids:
                if solver.Value(x[(g_idx, t_id)]) == 1:
                    counts[t_id] += 1
                    break

        for t_id, trainer in trainers.items():
            actual = counts[t_id]
            target = target_groups[t_id]
            diff = actual - target
            print(f"  {trainer.name}: {actual} groups (target: {target}, diff: {diff:+d})")

    return assignments


def apply_assignments(
    headers: List[str],
    slot_ids: List[str],
    data: List[List[str]],
    assignments: Dict[Tuple[str, int], int],
    trainers: Dict[int, TrainerData]
) -> List[List[str]]:
    """Apply trainer assignments to calendar data."""
    new_data = [row.copy() for row in data]

    for (slot_id, col_idx), trainer_id in assignments.items():
        row_idx = slot_ids.index(slot_id)
        trainer = trainers[trainer_id]

        original_value = data[row_idx][col_idx]
        # Append trainer info: ":ID-Name"
        new_value = f"{original_value}:{trainer_id}-{trainer.name}"
        new_data[row_idx][col_idx] = new_value

    return new_data


def save_calendar(filepath: str, headers: List[str], slot_ids: List[str],
                  data: List[List[str]]):
    """Save calendar to CSV."""
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['slot_id'] + headers)
        for slot_id, row in zip(slot_ids, data):
            writer.writerow([slot_id] + row)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Assign trainers to lab slots')
    parser.add_argument('--input', default='data/output/calendario_laboratori.csv',
                        help='Input calendar CSV')
    parser.add_argument('--output', default='data/output/calendario_con_formatrici.csv',
                        help='Output calendar CSV')
    parser.add_argument('--trainers', default='data/input/formatrici.csv',
                        help='Trainers CSV')
    parser.add_argument('--prefs', default='data/input/formatrici_classi.csv',
                        help='Trainer-class preferences CSV')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    print("=" * 60)
    print("TRAINER ASSIGNMENT OPTIMIZER")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    trainers = load_trainers(args.trainers)
    print(f"  Loaded {len(trainers)} trainers")

    trainer_prefs = load_trainer_class_preferences(args.prefs)
    print(f"  Loaded preferences for {len(trainer_prefs)} trainers")

    headers, slot_ids, data = load_calendar(args.input)
    print(f"  Loaded calendar: {len(slot_ids)} slots x {len(headers)} classes")

    # Extract lab slots and group them (accorpamenti)
    lab_slots = extract_lab_slots(headers, slot_ids, data)
    print(f"  Found {len(lab_slots)} lab assignments")

    lab_groups = group_lab_slots(lab_slots)
    print(f"  Grouped into {len(lab_groups)} groups (accorpamenti)")

    # Show grouping stats
    singles = sum(1 for g in lab_groups if len(g.lab_slots) == 1)
    doubles = sum(1 for g in lab_groups if len(g.lab_slots) == 2)
    triples = sum(1 for g in lab_groups if len(g.lab_slots) >= 3)
    print(f"  Grouping: {singles} singles, {doubles} doubles, {triples} triples+")

    # Optimize
    assignments = optimize_trainer_assignment(
        trainers, trainer_prefs, lab_groups, verbose=args.verbose
    )

    if not assignments:
        print("ERROR: No assignments found!")
        return 1

    # Apply and save
    new_data = apply_assignments(headers, slot_ids, data, assignments, trainers)
    save_calendar(args.output, headers, slot_ids, new_data)

    print(f"\nSaved output to: {args.output}")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    exit(main())
