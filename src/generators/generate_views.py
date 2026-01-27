#!/usr/bin/env python3
"""
Generate CSV views from the matrix calendar with trainer assignments.

Input: data/output/calendario_con_formatrici.csv (matrix format)
Output: data/output/views/
    - calendario_giornaliero.csv
    - formatrici/{trainer_name}.csv
    - classi/{class_name}_{school_name}.csv
    - laboratori/Lab_{lab_id}_{lab_name}.csv
"""

import csv
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


def load_reference_data(data_dir: Path) -> Tuple[Dict, Dict, Dict]:
    """Load schools, classes, and labs reference data."""
    schools = {}
    with open(data_dir / "scuole.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            schools[int(row['scuola_id'])] = row['nome']

    classes = {}
    class_to_school = {}
    with open(data_dir / "classi.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            class_id = int(row['classe_id'])
            classes[class_id] = row['nome']
            class_to_school[class_id] = int(row['scuola_id'])

    labs = {}
    with open(data_dir / "laboratori.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            labs[int(row['laboratorio_id'])] = row['nome']

    trainers = {}
    with open(data_dir / "formatrici.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trainers[int(row['formatrice_id'])] = row['nome']

    return {
        'schools': schools,
        'classes': classes,
        'class_to_school': class_to_school,
        'labs': labs,
        'trainers': trainers
    }


def parse_slot_id(slot_id: str) -> Dict:
    """
    Parse slot_id like 's00-01-29-gio-M1' into components.

    Returns dict with: week, month, day, weekday, timeslot, date, fascia_nome
    """
    # Format: s{week}-{month}-{day}-{weekday}-{timeslot}
    match = re.match(r's(\d+)-(\d+)-(\d+)-(\w+)-(\w+)', slot_id)
    if not match:
        return None

    week = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    weekday = match.group(4)
    timeslot = match.group(5)

    # Create date (assuming 2026)
    date = datetime(2026, month, day)

    # Map timeslot to fascia nome
    fascia_map = {
        'M1': ('Mattino1', '09:00-11:00'),
        'M2': ('Mattino2', '11:00-13:00'),
        'P': ('Pomeriggio', '14:00-16:00')
    }
    fascia_nome, time_str = fascia_map.get(timeslot, ('Unknown', ''))

    # Italian weekday names
    weekday_map = {
        'lun': 'Lunedì', 'mar': 'Martedì', 'mer': 'Mercoledì',
        'gio': 'Giovedì', 'ven': 'Venerdì', 'sab': 'Sabato'
    }
    giorno_nome = weekday_map.get(weekday, weekday)

    return {
        'week': week,
        'month': month,
        'day': day,
        'weekday': weekday,
        'timeslot': timeslot,
        'date': date,
        'date_str': date.strftime('%d/%m/%Y'),
        'data_ora': f"{date.strftime('%d/%m/%Y')} {time_str}",
        'fascia_nome': fascia_nome,
        'giorno_nome': giorno_nome
    }


def parse_header(header: str) -> Dict:
    """
    Parse column header like '3-1-4B' into components.

    Returns dict with: col_idx, school_id, class_name
    """
    parts = header.split('-', 2)
    if len(parts) < 3:
        return None

    return {
        'col_idx': int(parts[0]),
        'school_id': int(parts[1]),
        'class_name': parts[2]
    }


def parse_cell(cell: str) -> Optional[Dict]:
    """
    Parse cell value like 'L4-1/3-1-4B:1-Anita' into components.

    Returns dict with: lab_id, meeting_num, col_idx, school_id, class_name, trainer_id, trainer_name
    """
    if not cell or cell in ('X', '-') or not cell.startswith('L'):
        return None

    # Check if has trainer assignment
    if ':' not in cell:
        return None  # No trainer assigned

    # Split lab info and trainer info
    lab_part, trainer_part = cell.split(':', 1)

    # Parse lab part: L{lab}-{meeting}/{col_idx}-{school_id}-{class_name}
    lab_match = re.match(r'L(\d+)-(\d+)/(\d+)-(\d+)-(.+)', lab_part)
    if not lab_match:
        # Try simpler format without class info
        lab_match = re.match(r'L(\d+)-(\d+)', lab_part)
        if lab_match:
            return {
                'lab_id': int(lab_match.group(1)),
                'meeting_num': int(lab_match.group(2)),
                'col_idx': None,
                'school_id': None,
                'class_name': None,
                'trainer_id': int(trainer_part.split('-')[0]),
                'trainer_name': trainer_part.split('-', 1)[1] if '-' in trainer_part else None
            }
        return None

    # Parse trainer part: {trainer_id}-{trainer_name}
    trainer_match = re.match(r'(\d+)-(.+)', trainer_part)
    if not trainer_match:
        return None

    return {
        'lab_id': int(lab_match.group(1)),
        'meeting_num': int(lab_match.group(2)),
        'col_idx': int(lab_match.group(3)),
        'school_id': int(lab_match.group(4)),
        'class_name': lab_match.group(5),
        'trainer_id': int(trainer_match.group(1)),
        'trainer_name': trainer_match.group(2)
    }


def load_and_explode_calendar(calendar_path: Path, ref_data: Dict) -> List[Dict]:
    """
    Load matrix calendar and explode into row-based records.

    Each cell with a lab assignment becomes one record.
    """
    records = []

    with open(calendar_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)

        # Parse column headers (skip slot_id and last 2 columns)
        col_headers = []
        for i, h in enumerate(headers[1:-2]):  # Skip slot_id and num_formatrici columns
            parsed = parse_header(h)
            if parsed:
                parsed['col_pos'] = i
                col_headers.append(parsed)

        # Process each row
        for row in reader:
            slot_id = row[0]
            slot_info = parse_slot_id(slot_id)
            if not slot_info:
                continue

            # Process each cell
            for col_info in col_headers:
                col_pos = col_info['col_pos']
                cell = row[col_pos + 1]  # +1 to skip slot_id column

                cell_info = parse_cell(cell)
                if not cell_info:
                    continue

                # Build record
                school_id = cell_info['school_id'] or col_info['school_id']
                class_name = cell_info['class_name'] or col_info['class_name']

                record = {
                    # Slot info
                    'slot_id': slot_id,
                    'settimana': slot_info['week'],
                    'giorno_nome': slot_info['giorno_nome'],
                    'fascia_nome': slot_info['fascia_nome'],
                    'data_ora': slot_info['data_ora'],
                    'date': slot_info['date'],

                    # Class info
                    'col_idx': col_info['col_idx'],
                    'school_id': school_id,
                    'school_name': ref_data['schools'].get(school_id, f'Scuola {school_id}'),
                    'class_name': class_name,

                    # Lab info
                    'lab_id': cell_info['lab_id'],
                    'lab_name': ref_data['labs'].get(cell_info['lab_id'], f'Lab {cell_info["lab_id"]}'),
                    'meeting_num': cell_info['meeting_num'],

                    # Trainer info
                    'trainer_id': cell_info['trainer_id'],
                    'trainer_name': cell_info['trainer_name']
                }

                records.append(record)

    return records


def generate_daily_view(records: List[Dict], output_path: Path):
    """Generate calendario_giornaliero.csv - collapsed by slot/lab/trainer."""
    # Group by (slot_id, lab_id, meeting_num, trainer_id)
    groups = defaultdict(list)
    for r in records:
        key = (r['slot_id'], r['lab_id'], r['meeting_num'], r['trainer_id'])
        groups[key].append(r)

    daily_records = []
    for key, group in groups.items():
        first = group[0]

        # Collect classes
        classes = sorted(set(r['class_name'] for r in group))
        classes_str = ", ".join(classes)

        # Collect schools
        schools = list(set(r['school_name'] for r in group))
        school_str = schools[0] if len(schools) == 1 else ", ".join(schools)

        daily_records.append({
            'Settimana': first['settimana'],
            'Giorno': first['giorno_nome'],
            'Fascia Oraria': first['fascia_nome'],
            'Data e Ora': first['data_ora'],
            'Classi': classes_str,
            'N. Classi': len(classes),
            'Scuola': school_str,
            'Laboratorio': first['lab_name'],
            'Formatrice': first['trainer_name'],
            'Accorpamento': 'Sì' if len(classes) > 1 else 'No',
            '_date': first['date']
        })

    # Sort by date and fascia
    fascia_order = {'Mattino1': 1, 'Mattino2': 2, 'Pomeriggio': 3}
    daily_records.sort(key=lambda r: (r['_date'], fascia_order.get(r['Fascia Oraria'], 9)))

    # Write output
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['Settimana', 'Giorno', 'Fascia Oraria', 'Data e Ora',
                      'Classi', 'N. Classi', 'Scuola', 'Laboratorio', 'Formatrice', 'Accorpamento']
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(daily_records)

    return len(daily_records)


def generate_trainer_views(records: List[Dict], output_dir: Path):
    """Generate per-trainer views."""
    # Group by trainer
    by_trainer = defaultdict(list)
    for r in records:
        by_trainer[r['trainer_name']].append(r)

    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for trainer_name, trainer_records in by_trainer.items():
        # Group by (slot_id, lab_id, meeting_num)
        groups = defaultdict(list)
        for r in trainer_records:
            key = (r['slot_id'], r['lab_id'], r['meeting_num'])
            groups[key].append(r)

        trainer_output = []
        for key, group in groups.items():
            first = group[0]
            classes = sorted(set(r['class_name'] for r in group))
            schools = list(set(r['school_name'] for r in group))

            trainer_output.append({
                'Classi': ", ".join(classes),
                'N. Classi': len(classes),
                'Scuola': schools[0] if len(schools) == 1 else ", ".join(schools),
                'Laboratorio': first['lab_name'],
                'Settimana': first['settimana'],
                'Giorno': first['giorno_nome'],
                'Fascia Oraria': first['fascia_nome'],
                'Data e Ora': first['data_ora'],
                'Accorpamento': 'Sì' if len(classes) > 1 else 'No',
                '_date': first['date']
            })

        # Sort
        fascia_order = {'Mattino1': 1, 'Mattino2': 2, 'Pomeriggio': 3}
        trainer_output.sort(key=lambda r: (r['_date'], fascia_order.get(r['Fascia Oraria'], 9)))

        # Write
        output_path = output_dir / f"{trainer_name}.csv"
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Classi', 'N. Classi', 'Scuola', 'Laboratorio',
                          'Settimana', 'Giorno', 'Fascia Oraria', 'Data e Ora', 'Accorpamento']
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(trainer_output)

        print(f"  ✓ {trainer_name}: {len(trainer_output)} incontri")
        count += 1

    return count


def generate_class_views(records: List[Dict], output_dir: Path):
    """Generate per-class views."""
    # Group by class
    by_class = defaultdict(list)
    for r in records:
        key = (r['class_name'], r['school_name'])
        by_class[key].append(r)

    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for (class_name, school_name), class_records in by_class.items():
        # Find grouped classes for each meeting
        class_output = []
        for r in class_records:
            # Find other classes in same slot/lab/trainer
            same_slot = [
                rec for rec in records
                if rec['slot_id'] == r['slot_id']
                and rec['lab_id'] == r['lab_id']
                and rec['trainer_id'] == r['trainer_id']
                and rec['class_name'] != r['class_name']
            ]
            grouped_with = ", ".join(sorted(set(rec['class_name'] for rec in same_slot)))

            class_output.append({
                'Laboratorio': r['lab_name'],
                'Incontro N.': r['meeting_num'],
                'Settimana': r['settimana'],
                'Giorno': r['giorno_nome'],
                'Fascia Oraria': r['fascia_nome'],
                'Data e Ora': r['data_ora'],
                'Formatrice': r['trainer_name'],
                'Accorpata Con': grouped_with or '-',
                '_date': r['date']
            })

        # Sort
        fascia_order = {'Mattino1': 1, 'Mattino2': 2, 'Pomeriggio': 3}
        class_output.sort(key=lambda r: (r['_date'], fascia_order.get(r['Fascia Oraria'], 9)))

        # Write
        safe_class = class_name.replace('/', '-').replace(' ', '_')
        safe_school = school_name.replace(' ', '_').replace('.', '')
        output_path = output_dir / f"{safe_class}_{safe_school}.csv"
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Laboratorio', 'Incontro N.', 'Settimana', 'Giorno',
                          'Fascia Oraria', 'Data e Ora', 'Formatrice', 'Accorpata Con']
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(class_output)

        count += 1

    print(f"  ✓ Generated {count} class calendars")
    return count


def generate_lab_views(records: List[Dict], output_dir: Path):
    """Generate per-lab views."""
    # Group by lab
    by_lab = defaultdict(list)
    for r in records:
        by_lab[(r['lab_id'], r['lab_name'])].append(r)

    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for (lab_id, lab_name), lab_records in by_lab.items():
        # Group by (slot_id, trainer_id)
        groups = defaultdict(list)
        for r in lab_records:
            key = (r['slot_id'], r['trainer_id'])
            groups[key].append(r)

        lab_output = []
        for key, group in groups.items():
            first = group[0]
            classes = sorted(set(r['class_name'] for r in group))
            schools = list(set(r['school_name'] for r in group))

            lab_output.append({
                'Classi': ", ".join(classes),
                'N. Classi': len(classes),
                'Scuola': schools[0] if len(schools) == 1 else ", ".join(schools),
                'Settimana': first['settimana'],
                'Giorno': first['giorno_nome'],
                'Fascia Oraria': first['fascia_nome'],
                'Data e Ora': first['data_ora'],
                'Formatrice': first['trainer_name'],
                'Accorpamento': 'Sì' if len(classes) > 1 else 'No',
                '_date': first['date']
            })

        # Sort
        fascia_order = {'Mattino1': 1, 'Mattino2': 2, 'Pomeriggio': 3}
        lab_output.sort(key=lambda r: (r['_date'], fascia_order.get(r['Fascia Oraria'], 9)))

        # Write
        safe_name = lab_name.replace('/', '-').replace(' ', '_')
        output_path = output_dir / f"Lab_{lab_id}_{safe_name}.csv"
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['Classi', 'N. Classi', 'Scuola', 'Settimana', 'Giorno',
                          'Fascia Oraria', 'Data e Ora', 'Formatrice', 'Accorpamento']
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(lab_output)

        print(f"  ✓ Lab {lab_id} ({lab_name}): {len(lab_output)} incontri")
        count += 1

    return count


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate views from matrix calendar')
    parser.add_argument('--input', default='data/output/calendario_con_formatrici.csv',
                        help='Input calendar CSV (matrix format)')
    parser.add_argument('--output-dir', default='data/output/views',
                        help='Output directory for views')
    parser.add_argument('--data-dir', default='data/input',
                        help='Input data directory for reference files')

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    data_dir = Path(args.data_dir)

    print("=" * 60)
    print("GENERATE VIEWS FROM MATRIX CALENDAR")
    print("=" * 60)

    # Load reference data
    print("\nLoading reference data...")
    ref_data = load_reference_data(data_dir)
    print(f"  Loaded {len(ref_data['schools'])} schools")
    print(f"  Loaded {len(ref_data['classes'])} classes")
    print(f"  Loaded {len(ref_data['labs'])} labs")
    print(f"  Loaded {len(ref_data['trainers'])} trainers")

    # Load and explode calendar
    print(f"\nLoading calendar from {input_path}...")
    records = load_and_explode_calendar(input_path, ref_data)
    print(f"  Exploded into {len(records)} individual records")

    # Generate views
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n1. Generating daily calendar...")
    daily_path = output_dir / "calendario_giornaliero.csv"
    n_daily = generate_daily_view(records, daily_path)
    print(f"  ✓ calendario_giornaliero.csv: {n_daily} meetings")

    print("\n2. Generating per-trainer views...")
    n_trainers = generate_trainer_views(records, output_dir / "formatrici")

    print("\n3. Generating per-class views...")
    n_classes = generate_class_views(records, output_dir / "classi")

    print("\n4. Generating per-lab views...")
    n_labs = generate_lab_views(records, output_dir / "laboratori")

    print("\n" + "=" * 60)
    print("✅ Views generated successfully!")
    print(f"   - 1 daily calendar ({n_daily} meetings)")
    print(f"   - {n_trainers} trainer calendars")
    print(f"   - {n_classes} class calendars")
    print(f"   - {n_labs} lab calendars")
    print(f"   Output: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
