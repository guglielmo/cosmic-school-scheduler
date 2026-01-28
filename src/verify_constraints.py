#!/usr/bin/env python3
"""
Verify constraints on the calendar with trainer assignments.

Checks:
1. Hours assigned to each trainer
2. For each class:
   - All required labs have been assigned
   - Lab integrity (correct number of meetings per lab)
"""

import csv
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple


def load_reference_data(data_dir: Path) -> Dict:
    """Load all reference data."""

    # Schools
    schools = {}
    with open(data_dir / "scuole.csv", 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            schools[int(row['scuola_id'])] = row['nome']

    # Classes
    classes = {}
    with open(data_dir / "classi.csv", 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            classes[int(row['classe_id'])] = {
                'nome': row['nome'],
                'scuola_id': int(row['scuola_id'])
            }

    # Labs with number of meetings
    labs = {}
    with open(data_dir / "laboratori.csv", 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            labs[int(row['laboratorio_id'])] = {
                'nome': row['nome'],
                'num_incontri': int(row['num_incontri']),
                'ore_per_incontro': int(row['ore_per_incontro'])
            }

    # Trainers
    trainers = {}
    with open(data_dir / "formatrici.csv", 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            trainers[int(row['formatrice_id'])] = {
                'nome': row['nome'],
                'ore_generali': int(row['ore_generali'])
            }

    # Class-lab assignments (which labs each class must attend and how many meetings)
    class_labs = defaultdict(dict)  # class_id -> {lab_id -> num_meetings}
    with open(data_dir / "laboratori_classi.csv", 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            class_id = int(row['classe_id'])
            lab_id = int(row['laboratorio_id'])
            # Only include labs that are in our labs.csv (FOP labs)
            if lab_id in labs:
                # Check for "solo X incontri" notes
                dettagli = row.get('dettagli', '').lower()
                if 'solo 1 incontro' in dettagli:
                    num_meetings = 1
                elif 'solo 2 incontri' in dettagli:
                    num_meetings = 2
                else:
                    num_meetings = labs[lab_id]['num_incontri']
                class_labs[class_id][lab_id] = num_meetings

    return {
        'schools': schools,
        'classes': classes,
        'labs': labs,
        'trainers': trainers,
        'class_labs': dict(class_labs)
    }


def parse_calendar(calendar_path: Path) -> List[Dict]:
    """Parse calendar and extract all assignments."""
    records = []

    with open(calendar_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)

        for row in reader:
            slot_id = row[0]

            for col_idx, cell in enumerate(row[1:-2]):  # Skip slot_id and last 2 cols
                if not cell or cell in ('X', '-') or ':' not in cell:
                    continue

                # Handle cells with multiple labs (joined by " + ")
                labs = [lab.strip() for lab in cell.split(' + ')]

                for lab_info in labs:
                    # Parse cell: L{lab}-{meeting}/{col}-{school}-{class}:{trainer_id}-{trainer_name}
                    match = re.match(r'L(\d+)-(\d+)/(\d+)-(\d+)-([^:]+):(\d+)-(.+)', lab_info)
                    if match:
                        records.append({
                            'slot_id': slot_id,
                            'lab_id': int(match.group(1)),
                            'meeting_num': int(match.group(2)),
                            'col_idx': int(match.group(3)),
                            'school_id': int(match.group(4)),
                            'class_name': match.group(5),
                            'trainer_id': int(match.group(6)),
                            'trainer_name': match.group(7)
                        })

    return records


def verify_trainer_hours(records: List[Dict], ref_data: Dict) -> Dict:
    """Calculate hours assigned to each trainer."""

    # Group by trainer and count unique (slot_id, school_id, lab_id, meeting_num)
    trainer_groups = defaultdict(set)

    for r in records:
        # Each unique group = 2 hours
        key = (r['slot_id'], r['school_id'], r['lab_id'], r['meeting_num'])
        trainer_groups[r['trainer_id']].add(key)

    results = {}
    for t_id, trainer_info in ref_data['trainers'].items():
        groups = trainer_groups.get(t_id, set())
        assigned_hours = len(groups) * 2  # 2 hours per meeting
        budget_hours = trainer_info['ore_generali']

        results[t_id] = {
            'nome': trainer_info['nome'],
            'groups': len(groups),
            'assigned_hours': assigned_hours,
            'budget_hours': budget_hours,
            'diff': assigned_hours - budget_hours,
            'pct_used': assigned_hours / budget_hours * 100 if budget_hours > 0 else 0
        }

    return results


def verify_class_labs(records: List[Dict], ref_data: Dict) -> Dict:
    """Verify each class has all required labs with correct number of meetings."""

    # Build class mapping from col_idx to class_id
    # We need to match class_name + school_id to class_id
    class_lookup = {}
    for class_id, info in ref_data['classes'].items():
        key = (info['scuola_id'], info['nome'])
        class_lookup[key] = class_id

    # Group records by class
    class_records = defaultdict(list)
    for r in records:
        key = (r['school_id'], r['class_name'])
        class_id = class_lookup.get(key)
        if class_id:
            class_records[class_id].append(r)

    results = {}

    # class_labs is now: class_id -> {lab_id -> num_meetings}
    for class_id, lab_meetings in ref_data['class_labs'].items():
        class_info = ref_data['classes'].get(class_id, {})
        class_name = class_info.get('nome', f'Class {class_id}')
        school_id = class_info.get('scuola_id', 0)
        school_name = ref_data['schools'].get(school_id, f'School {school_id}')

        # Get assigned labs and meetings for this class
        assigned = defaultdict(set)  # lab_id -> set of meeting_nums
        for r in class_records.get(class_id, []):
            assigned[r['lab_id']].add(r['meeting_num'])

        # Check each required lab
        lab_status = {}
        all_complete = True

        for lab_id, required_meetings in lab_meetings.items():
            lab_info = ref_data['labs'].get(lab_id, {})
            lab_name = lab_info.get('nome', f'Lab {lab_id}')

            assigned_meetings = assigned.get(lab_id, set())
            num_assigned = len(assigned_meetings)

            is_complete = num_assigned == required_meetings
            if not is_complete:
                all_complete = False

            lab_status[lab_id] = {
                'nome': lab_name,
                'required': required_meetings,
                'assigned': num_assigned,
                'meetings': sorted(assigned_meetings),
                'complete': is_complete
            }

        results[class_id] = {
            'nome': class_name,
            'scuola': school_name,
            'all_complete': all_complete,
            'labs': lab_status
        }

    return results


def print_report(trainer_results: Dict, class_results: Dict, ref_data: Dict):
    """Print verification report."""

    print("=" * 70)
    print("CONSTRAINT VERIFICATION REPORT")
    print("=" * 70)

    # 1. Trainer hours
    print("\n" + "=" * 70)
    print("1. TRAINER HOURS")
    print("=" * 70)

    total_assigned = 0
    total_budget = 0

    print(f"\n{'Formatrice':<15} {'Gruppi':>8} {'Ore Ass.':>10} {'Budget':>10} {'Diff':>8} {'%':>8}")
    print("-" * 70)

    for t_id in sorted(trainer_results.keys()):
        r = trainer_results[t_id]
        total_assigned += r['assigned_hours']
        total_budget += r['budget_hours']

        diff_str = f"{r['diff']:+d}" if r['diff'] != 0 else "0"
        print(f"{r['nome']:<15} {r['groups']:>8} {r['assigned_hours']:>10} {r['budget_hours']:>10} {diff_str:>8} {r['pct_used']:>7.1f}%")

    print("-" * 70)
    print(f"{'TOTALE':<15} {'':<8} {total_assigned:>10} {total_budget:>10} {total_assigned - total_budget:>+8}")

    # 2. Class lab completion
    print("\n" + "=" * 70)
    print("2. CLASS LAB COMPLETION")
    print("=" * 70)

    complete_classes = sum(1 for r in class_results.values() if r['all_complete'])
    incomplete_classes = len(class_results) - complete_classes

    print(f"\nClasses with all labs complete: {complete_classes}")
    print(f"Classes with missing labs: {incomplete_classes}")

    if incomplete_classes > 0:
        print("\n" + "-" * 70)
        print("INCOMPLETE CLASSES:")
        print("-" * 70)

        for class_id in sorted(class_results.keys()):
            r = class_results[class_id]
            if not r['all_complete']:
                print(f"\n  {r['nome']} ({r['scuola']}):")
                for lab_id, lab in r['labs'].items():
                    if not lab['complete']:
                        print(f"    - {lab['nome']}: {lab['assigned']}/{lab['required']} meetings")
                        if lab['assigned'] > 0:
                            print(f"      (has meetings: {lab['meetings']})")

    # 3. Lab integrity check
    print("\n" + "=" * 70)
    print("3. LAB INTEGRITY (meetings per lab)")
    print("=" * 70)

    integrity_issues = []
    for class_id, r in class_results.items():
        for lab_id, lab in r['labs'].items():
            if lab['assigned'] > 0 and lab['assigned'] != lab['required']:
                integrity_issues.append({
                    'class': r['nome'],
                    'school': r['scuola'],
                    'lab': lab['nome'],
                    'expected': lab['required'],
                    'actual': lab['assigned'],
                    'meetings': lab['meetings']
                })

    if integrity_issues:
        print(f"\nFound {len(integrity_issues)} integrity issues:")
        print("-" * 70)
        for issue in integrity_issues[:20]:
            print(f"  {issue['class']} ({issue['school']}): {issue['lab']}")
            print(f"    Expected {issue['expected']} meetings, got {issue['actual']}: {issue['meetings']}")
        if len(integrity_issues) > 20:
            print(f"  ... and {len(integrity_issues) - 20} more")
    else:
        print("\n✓ All assigned labs have correct number of meetings")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_ok = incomplete_classes == 0 and len(integrity_issues) == 0

    print(f"\n  Trainer hours within budget: {'✓' if total_assigned <= total_budget else '✗'}")
    print(f"  All classes complete: {'✓' if incomplete_classes == 0 else '✗'}")
    print(f"  Lab integrity: {'✓' if len(integrity_issues) == 0 else '✗'}")
    print(f"\n  Overall: {'✓ ALL CONSTRAINTS SATISFIED' if all_ok else '✗ SOME ISSUES FOUND'}")
    print("=" * 70)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Verify calendar constraints')
    parser.add_argument('--calendar', default='data/output/calendario_con_formatrici.csv',
                        help='Calendar CSV file')
    parser.add_argument('--data-dir', default='data/input',
                        help='Input data directory')

    args = parser.parse_args()

    calendar_path = Path(args.calendar)
    data_dir = Path(args.data_dir)

    # Load data
    print("Loading data...")
    ref_data = load_reference_data(data_dir)
    print(f"  Loaded {len(ref_data['trainers'])} trainers")
    print(f"  Loaded {len(ref_data['classes'])} classes")
    print(f"  Loaded {len(ref_data['labs'])} labs")
    print(f"  Loaded {len(ref_data['class_labs'])} class-lab assignments")

    # Parse calendar
    print(f"\nParsing calendar from {calendar_path}...")
    records = parse_calendar(calendar_path)
    print(f"  Found {len(records)} assignments")

    # Verify
    print("\nVerifying constraints...")
    trainer_results = verify_trainer_hours(records, ref_data)
    class_results = verify_class_labs(records, ref_data)

    # Report
    print_report(trainer_results, class_results, ref_data)


if __name__ == '__main__':
    main()
