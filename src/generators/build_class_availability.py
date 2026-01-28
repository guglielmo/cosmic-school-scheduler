#!/usr/bin/env python3
"""
Build class availability matrix.

For each slot in slots_calendar.csv, determine if each class is available (S)
or not available (N) based on:
- GSI/GSST fixed dates (blocks entire weeks)
- School constraints (saturday availability)
- Class time slot preferences (mattino1, mattino2, pomeriggio)
- Class weekday availability
- Excluded dates per class

Output: CSV with slot_id as first column, then one column per class with S/N
"""

from datetime import datetime, timedelta
import csv
import sys
from pathlib import Path
import re

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))

from date_utils import DateMapper


# GSI/GSST lab IDs (external partners - block entire weeks)
EXTERNAL_LAB_IDS = {1, 2, 3, 6}

# FOP lab IDs (we're scheduling these)
FOP_LAB_IDS = {4, 5, 7, 8, 9}

# Weekday mapping
WEEKDAY_TO_NUM = {
    'lunedì': 0, 'lunedi': 0, 'lun': 0,
    'martedì': 1, 'martedi': 1, 'mar': 1,
    'mercoledì': 2, 'mercoledi': 2, 'mer': 2,
    'giovedì': 3, 'giovedi': 3, 'gio': 3,
    'venerdì': 4, 'venerdi': 4, 'ven': 4,
    'sabato': 5, 'sab': 5,
    'domenica': 6, 'dom': 6
}

# Slot mapping
SLOT_TO_NUM = {
    'M1': 1, 'mattino1': 1,
    'M2': 2, 'mattino2': 2,
    'P': 3, 'pomeriggio': 3
}


class ClassAvailabilityChecker:
    """Check slot availability for each class."""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.mapper = DateMapper()

        # Load data
        self.classes = self._load_classes()
        self.schools = self._load_schools()
        self.blocked_weeks = self._load_blocked_weeks()
        self.time_constraints = self._load_time_constraints()
        self.excluded_dates = self._load_excluded_dates()

    def _load_classes(self):
        """Load classes with school mapping."""
        classes = {}
        with open(self.data_dir / "input" / "classi.csv", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                classes[int(row['classe_id'])] = {
                    'nome': row['nome'],
                    'scuola_id': int(row['scuola_id']),
                    'anno': int(row['anno'])
                }
        return classes

    def _load_schools(self):
        """Load schools with saturday availability."""
        schools = {}
        with open(self.data_dir / "input" / "scuole.csv", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                schools[int(row['scuola_id'])] = {
                    'nome': row['nome'],
                    'sabato_disponibile': row['sabato_disponibile'].lower() in ['si', 'sì', 'yes', 's']
                }
        return schools

    def _load_blocked_weeks(self):
        """Load weeks blocked by GSI/GSST labs for each class."""
        blocked = {}  # classe_id -> set of week numbers

        with open(self.data_dir / "input" / "laboratori_classi.csv", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                classe_id = int(row['classe_id'])
                lab_id = int(row['laboratorio_id'])
                date_fissate = row.get('date_fissate', '').strip()

                # Only consider GSI/GSST labs (1, 2, 3, 6)
                if lab_id not in EXTERNAL_LAB_IDS or not date_fissate:
                    continue

                if classe_id not in blocked:
                    blocked[classe_id] = set()

                # Parse dates and extract weeks
                weeks = self._parse_fixed_dates_to_weeks(date_fissate)
                blocked[classe_id].update(weeks)

        return blocked

    def _parse_fixed_dates_to_weeks(self, date_str):
        """Parse fixed dates string and return set of week numbers."""
        weeks = set()

        # Split by comma
        parts = date_str.split(',')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Try to extract date in various formats
            # e.g., "26 febbraio 9-13", "9 marzo 9-13"
            match = re.search(r'(\d+)\s+(\w+)', part)
            if match:
                day = int(match.group(1))
                month_name = match.group(2).lower()

                # Map Italian month names
                month_map = {
                    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
                    'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
                    'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
                }

                if month_name in month_map:
                    month = month_map[month_name]
                    year = 2026

                    try:
                        date = datetime(year, month, day)
                        week, _ = self.mapper.date_to_week_day(date)
                        weeks.add(week)
                    except (ValueError, AttributeError):
                        pass  # Invalid date or outside valid windows

        return weeks

    def _load_time_constraints(self):
        """Load time slot and weekday constraints for each class."""
        constraints = {}

        with open(self.data_dir / "input" / "fasce_orarie_classi.csv", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                classe_id = int(row['classe_id'])

                # Parse allowed slots
                fasce_str = row.get('fasce_disponibili', '').lower()
                allowed_slots = set()
                if 'mattino1' in fasce_str or 'mattina1' in fasce_str:
                    allowed_slots.add(1)
                if 'mattino2' in fasce_str or 'mattina2' in fasce_str:
                    allowed_slots.add(2)
                if 'pomeriggio' in fasce_str:
                    allowed_slots.add(3)

                # If no slots specified, allow all
                if not allowed_slots:
                    allowed_slots = {1, 2, 3}

                # Parse allowed weekdays
                giorni_str = row.get('giorni_settimana', '').lower()
                allowed_days = set()

                if giorni_str:
                    # Parse complex format like "lunedì, martedì, mercoledì pomeriggio"
                    for day_name, day_num in WEEKDAY_TO_NUM.items():
                        if day_name in giorni_str:
                            allowed_days.add(day_num)

                    # Check for slot-specific days (e.g., "mercoledì pomeriggio")
                    # For now, we simplify: if a day is mentioned, it's allowed
                    # TODO: handle "mercoledì pomeriggio" to only allow P on Wed
                else:
                    # If no days specified, allow Mon-Fri (0-4)
                    allowed_days = {0, 1, 2, 3, 4}

                constraints[classe_id] = {
                    'allowed_slots': allowed_slots,
                    'allowed_days': allowed_days
                }

        return constraints

    def _load_excluded_dates(self):
        """Load excluded dates for each class."""
        excluded = {}

        with open(self.data_dir / "input" / "date_escluse_classi.csv", encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                classe_id = int(row['classe_id'])
                date_str = row.get('date_escluse', '').strip()

                if not date_str:
                    continue

                if classe_id not in excluded:
                    excluded[classe_id] = {
                        'dates': set(),  # Complete dates (date objects)
                        'weeks': set(),  # Week numbers
                        'date_slots': set()  # (date, slot_num) tuples for specific date+slot exclusions
                    }

                # Parse excluded dates
                self._parse_excluded_dates(date_str, excluded[classe_id])

        return excluded

    def _parse_excluded_dates(self, date_str, excluded_info):
        """Parse excluded dates string."""
        # Split by comma
        parts = date_str.split(',')

        for part in parts:
            part = part.strip().lower()
            if not part:
                continue

            # Check for date ranges: "8-23 gennaio", "2-6 marzo"
            range_match = re.search(r'(\d+)-(\d+)\s+(\w+)', part)
            if range_match:
                start_day = int(range_match.group(1))
                end_day = int(range_match.group(2))
                month_name = range_match.group(3)

                month_map = {
                    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
                    'maggio': 5, 'giugno': 6
                }

                if month_name in month_map:
                    month = month_map[month_name]
                    year = 2026

                    # Add all dates in range
                    current_day = start_day
                    while current_day <= end_day:
                        try:
                            date = datetime(year, month, current_day)
                            excluded_info['dates'].add(date.date())
                            week, _ = self.mapper.date_to_week_day(date)
                            excluded_info['weeks'].add(week)
                        except (ValueError, AttributeError):
                            pass  # Invalid date or outside valid windows
                        current_day += 1
                continue

            # Check for single date: "15 gennaio", "5 febbraio pomeriggio"
            single_match = re.search(r'(\d+)\s+(\w+)', part)
            if single_match:
                day = int(single_match.group(1))
                month_name = single_match.group(2)

                month_map = {
                    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
                    'maggio': 5, 'giugno': 6
                }

                if month_name in month_map:
                    month = month_map[month_name]
                    year = 2026

                    try:
                        date_obj = datetime(year, month, day)

                        # Check if specific slot is mentioned
                        if 'pomeriggio' in part:
                            # Only afternoon is excluded
                            excluded_info['date_slots'].add((date_obj.date(), 3))
                        elif 'mattina' in part or 'mattino' in part:
                            # Morning slots are excluded
                            excluded_info['date_slots'].add((date_obj.date(), 1))
                            excluded_info['date_slots'].add((date_obj.date(), 2))
                            # If "mattina e pomeriggio", also exclude afternoon
                            if 'pomeriggio' in part:
                                excluded_info['date_slots'].add((date_obj.date(), 3))
                        else:
                            # Entire day excluded
                            excluded_info['dates'].add(date_obj.date())
                    except (ValueError, AttributeError):
                        pass  # Invalid date or outside valid windows

    def is_available(self, classe_id, week_num, day_num, slot_num, date):
        """Check if class is available for given slot."""

        # Check if class exists
        if classe_id not in self.classes:
            return False

        classe = self.classes[classe_id]
        scuola_id = classe['scuola_id']
        school = self.schools.get(scuola_id, {})

        # 1. Check blocked weeks (GSI/GSST labs)
        if classe_id in self.blocked_weeks:
            if week_num in self.blocked_weeks[classe_id]:
                return False

        # 2. Check time slot constraints (includes weekday availability from class)
        if classe_id in self.time_constraints:
            constraints = self.time_constraints[classe_id]

            # Check allowed slots
            if slot_num not in constraints['allowed_slots']:
                return False

            # Check allowed days (Saturday is allowed only if specified in class giorni_settimana)
            if constraints['allowed_days'] and day_num not in constraints['allowed_days']:
                return False

        # 3. Check excluded dates
        if classe_id in self.excluded_dates:
            excl = self.excluded_dates[classe_id]

            # Check if entire date is excluded
            if date in excl['dates']:
                return False

            # Check if week is excluded
            if week_num in excl['weeks']:
                return False

            # Check if specific date-slot combo is excluded
            if (date, slot_num) in excl['date_slots']:
                return False

        return True


def build_availability_matrix(data_dir, slots_file, output_file):
    """Build availability matrix for all classes and slots."""

    checker = ClassAvailabilityChecker(data_dir)

    # Load slots
    slots = []
    with open(slots_file, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slots.append({
                'slot_id': row['slot_id'],
                'week_num': int(row['week_num']),
                'day_num': int(row['day_num']),
                'slot_num': int(row['slot_num']),
                'date': datetime.strptime(row['date'], '%Y-%m-%d').date()
            })

    # Get all class IDs (sorted)
    class_ids = sorted(checker.classes.keys())

    # Build matrix
    print(f"🔨 Building availability matrix...")
    print(f"   Classes: {len(class_ids)}")
    print(f"   Slots: {len(slots)}")

    # Write output
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        # Header: slot_id, class1, class2, ...
        # Format: "classe_id-scuola_id-nome_classe"
        fieldnames = ['slot_id'] + [
            f"{cid}-{checker.classes[cid]['scuola_id']}-{checker.classes[cid]['nome']}"
            for cid in class_ids
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # For each slot, check availability for each class
        for slot in slots:
            row_data = {'slot_id': slot['slot_id']}

            for cid in class_ids:
                col_name = f"{cid}-{checker.classes[cid]['scuola_id']}-{checker.classes[cid]['nome']}"
                available = checker.is_available(
                    cid,
                    slot['week_num'],
                    slot['day_num'],
                    slot['slot_num'],
                    slot['date']
                )
                row_data[col_name] = 'S' if available else 'N'

            writer.writerow(row_data)

    # Print summary
    print(f"\n✅ Availability matrix saved to: {output_file}")

    # Calculate and print statistics
    total_slots = len(slots)
    total_classes = len(class_ids)

    # Count available slots per class
    print(f"\n📊 Availability summary:")
    print(f"   Total slots: {total_slots}")
    print(f"   Total classes: {total_classes}")
    print(f"   Total cells: {total_slots * total_classes:,}")


def main():
    """Main entry point."""
    print("🚀 Building class availability matrix...")
    print("=" * 60)

    # Paths
    base_dir = Path(__file__).parent.parent.parent  # Project root
    data_dir = base_dir / "data"
    slots_file = data_dir / "output" / "slots_calendar.csv"
    output_file = data_dir / "output" / "class_availability.csv"

    # Build matrix
    build_availability_matrix(data_dir, slots_file, output_file)

    print("=" * 60)


if __name__ == "__main__":
    main()
