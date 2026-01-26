"""
Constraint factory for building constraints from CSV data.

This module reads CSV files and constructs constraint objects.
"""

import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

from .base import Constraint
from .hard_constraints import (
    TrainerTotalHoursConstraint,
    TrainerAvailabilityConstraint,
    FixedDatesConstraint,
    ClassLabAssignmentConstraint,
    LabTimeOfDayConstraint,
    ClassTimeSlotsConstraint,
    ClassExcludedDatesConstraint,
    MaxOneMeetingPerWeekConstraint,
    Lab8LastConstraint,
    NoTrainerOverlapConstraint,
    SchedulingPeriodConstraint,
    MaxGroupSizeConstraint,
    LabCompletionConstraint,
    Lab9BeforeLab5Constraint,
)
from .soft_constraints import (
    MaximizeGroupingConstraint,
    TrainerContinuityConstraint,
    TrainerWeeklyHoursConstraint,
    TrainerTimePreferenceConstraint,
    PreferredGroupingConstraint,
    LabSequenceConstraint,
    FifthYearPriorityConstraint,
    TimeSlotVariationConstraint,
    BalanceTrainerLoadConstraint,
    MinimizeLateMaySchedulingConstraint,
)
from .special_rules import (
    CitizenScienceGapConstraint,
    PartialLabMeetingsConstraint,
    MultiMeetingAfternoonConstraint,
    OneMeetingTimeConstraint,
    WeekdayTimeSpecificConstraint,
    IgnoreExternalLabsConstraint,
    SaturdayOnlyMargheritaConstraint,
)


class ConstraintFactory:
    """Factory for building constraints from CSV data."""

    def __init__(self, data_dir: str = "data/input", config_path: str = "config/constraint_weights.yaml"):
        """
        Initialize the constraint factory.

        Args:
            data_dir: Directory containing CSV files
            config_path: Path to YAML configuration file with weights
        """
        self.data_dir = Path(data_dir)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.csv_data = {}

    def _load_config(self) -> Dict[str, Any]:
        """Load constraint weights from YAML config."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        return {}

    def _load_csv(self, filename: str) -> List[Dict[str, str]]:
        """Load CSV file and return list of dictionaries."""
        filepath = self.data_dir / filename
        if not filepath.exists():
            print(f"Warning: {filepath} not found")
            return []

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def load_all_csv_data(self):
        """Load all CSV files into memory."""
        csv_files = [
            'formatrici.csv',
            'classi.csv',
            'scuole.csv',
            'laboratori.csv',
            'laboratori_classi.csv',
            'fasce_orarie_classi.csv',
            'fasce_orarie_scuole.csv',
            'date_escluse_classi.csv',
            'formatrici_classi.csv',
        ]

        for filename in csv_files:
            key = filename.replace('.csv', '')
            self.csv_data[key] = self._load_csv(filename)

    def _parse_weekday_list(self, weekday_str: str) -> List[str]:
        """Parse comma-separated weekday list."""
        if not weekday_str or weekday_str.strip() == '':
            return []
        return [day.strip() for day in weekday_str.split(',')]

    def _parse_dettagli(self, dettagli: str) -> Dict[str, Any]:
        """
        Parse the 'dettagli' field from laboratori_classi.csv.

        Returns dict with:
        - time_of_day: "mattina" | "pomeriggio" | None
        - partial_meetings: int | None
        - afternoon_count: int | None (for non-consecutive afternoon meetings)
        - one_afternoon: bool (at least one must be afternoon)
        """
        result = {
            'time_of_day': None,
            'partial_meetings': None,
            'afternoon_count': None,
            'one_afternoon': False,
        }

        if not dettagli:
            return result

        dettagli_lower = dettagli.lower()

        # Check for time of day constraint (all meetings)
        if dettagli_lower == 'mattina':
            result['time_of_day'] = 'mattina'
        elif dettagli_lower == 'pomeriggio':
            result['time_of_day'] = 'pomeriggio'

        # Check for partial meetings: "solo 1 incontro", "solo 2 incontri"
        match = re.search(r'solo (\d+) incontri?', dettagli_lower)
        if match:
            result['partial_meetings'] = int(match.group(1))

        # Check for multiple afternoon meetings non-consecutive
        match = re.search(r'(\d+) incontri devono essere di pomeriggio.*non.*consecutive', dettagli_lower)
        if match:
            result['afternoon_count'] = int(match.group(1))

        # Check for "un incontro deve essere di pomeriggio"
        if 'un incontro deve essere di pomeriggio' in dettagli_lower:
            result['one_afternoon'] = True

        return result

    def _parse_fixed_dates(self, date_str: str) -> List[str]:
        """Parse fixed dates from laboratori_classi.csv."""
        if not date_str or date_str.strip() == '':
            return []

        # Split by comma for multiple dates
        dates = [d.strip() for d in date_str.split(',')]
        return dates

    def build_all_constraints(self) -> List[Constraint]:
        """Build all constraints from loaded CSV data."""
        self.load_all_csv_data()

        constraints = []

        # Build constraints from each source
        constraints.extend(self._build_trainer_constraints())
        constraints.extend(self._build_class_constraints())
        constraints.extend(self._build_lab_constraints())
        constraints.extend(self._build_grouping_constraints())
        constraints.extend(self._build_global_constraints())
        constraints.extend(self._build_special_constraints())

        return constraints

    def _build_trainer_constraints(self) -> List[Constraint]:
        """Build constraints related to trainers."""
        constraints = []

        for row in self.csv_data.get('formatrici', []):
            trainer_id = int(row['formatrice_id'])
            trainer_name = row['nome']

            # H01: Total hours budget
            constraints.append(TrainerTotalHoursConstraint(
                trainer_id=trainer_id,
                trainer_name=trainer_name,
                max_hours=int(row['ore_generali'])
            ))

            # H02: Availability
            available_mornings = self._parse_weekday_list(row.get('mattine_disponibili', ''))
            available_afternoons = self._parse_weekday_list(row.get('pomeriggi_disponibili', ''))
            available_dates_str = row.get('date_disponibili', '').strip()
            available_dates = None
            if available_dates_str:
                available_dates = [d.strip() for d in available_dates_str.split(';')]

            constraints.append(TrainerAvailabilityConstraint(
                trainer_id=trainer_id,
                trainer_name=trainer_name,
                available_mornings=available_mornings,
                available_afternoons=available_afternoons,
                available_dates=available_dates,
                works_saturday=(row.get('lavora_sabato', 'no').lower() == 'si')
            ))

            # H10: No overlap
            constraints.append(NoTrainerOverlapConstraint(
                trainer_id=trainer_id,
                trainer_name=trainer_name
            ))

            # S03: Weekly hours target (if available)
            # Note: ore_settimanali not in current CSV, would need to add or calculate

            # S04: Time preference (if available)
            # Note: preferenza_fasce not in current CSV

        # Trainer continuity from formatrici_classi.csv
        for row in self.csv_data.get('formatrici_classi', []):
            constraints.append(TrainerContinuityConstraint(
                class_id=int(row['classe_id']),
                class_name=row['nome_classe'],
                preferred_trainer_id=int(row['formatrice_id']),
                preferred_trainer_name=row['nome_formatrice'],
                weight=self.config.get('objective_function', {}).get('trainer_continuity', 10)
            ))

        return constraints

    def _build_class_constraints(self) -> List[Constraint]:
        """Build constraints related to classes."""
        constraints = []

        # Build lab assignments per class
        class_labs = {}
        for row in self.csv_data.get('laboratori_classi', []):
            class_id = int(row['classe_id'])
            lab_id = int(row['laboratorio_id'])

            if class_id not in class_labs:
                class_labs[class_id] = {'labs': [], 'name': row['nome_classe'], 'school_id': int(row['scuola_id'])}
            class_labs[class_id]['labs'].append(lab_id)

        # H04: Class-Lab assignments
        for class_id, data in class_labs.items():
            constraints.append(ClassLabAssignmentConstraint(
                class_id=class_id,
                class_name=data['name'],
                assigned_labs=data['labs']
            ))

        # H06: Time slots from fasce_orarie_classi
        for row in self.csv_data.get('fasce_orarie_classi', []):
            class_id = int(row['classe_id'])
            available_slots = [s.strip() for s in row['fasce_disponibili'].split(',')]
            is_hard = (row.get('preferenza', '').strip().lower() == 'disponibile')
            weekdays = self._parse_weekday_list(row.get('giorni_settimana', ''))

            constraints.append(ClassTimeSlotsConstraint(
                class_id=class_id,
                class_name=row['nome_classe'],
                available_slots=available_slots,
                is_hard=is_hard,
                available_weekdays=weekdays
            ))

        # H07: Excluded dates
        for row in self.csv_data.get('date_escluse_classi', []):
            constraints.append(ClassExcludedDatesConstraint(
                class_id=int(row['classe_id']),
                class_name=row['nome_classe'],
                excluded_dates=[row['date_escluse']]  # TODO: Parse date ranges
            ))

        # H08: Max one meeting per week (for all classes)
        for row in self.csv_data.get('classi', []):
            class_id = int(row['classe_id'])
            constraints.append(MaxOneMeetingPerWeekConstraint(
                class_id=class_id,
                class_name=row['nome']
            ))

        # H09: Lab 8 last (for classes that have lab 8)
        for class_id, data in class_labs.items():
            if 8 in data['labs']:
                constraints.append(Lab8LastConstraint(
                    class_id=class_id,
                    class_name=data['name']
                ))

        # H14: Lab 9 before Lab 5 (for classes that have both)
        for class_id, data in class_labs.items():
            if 9 in data['labs'] and 5 in data['labs']:
                constraints.append(Lab9BeforeLab5Constraint(
                    class_id=class_id,
                    class_name=data['name']
                ))

        # S05: Preferred grouping
        for row in self.csv_data.get('classi', []):
            partner = row.get('accorpamento_preferenziale', '').strip()
            if partner:
                # Find partner class_id
                partner_id = None
                for prow in self.csv_data.get('classi', []):
                    if prow['nome'] == partner:
                        partner_id = int(prow['classe_id'])
                        break

                if partner_id:
                    constraints.append(PreferredGroupingConstraint(
                        class_id=int(row['classe_id']),
                        class_name=row['nome'],
                        preferred_partner_id=partner_id,
                        preferred_partner_name=partner,
                        weight=self.config.get('objective_function', {}).get('preferred_grouping', 5)
                    ))

        # S07: Fifth year priority
        for row in self.csv_data.get('classi', []):
            class_year = int(row['anno'])
            if class_year == 5:
                constraints.append(FifthYearPriorityConstraint(
                    class_id=int(row['classe_id']),
                    class_name=row['nome'],
                    class_year=class_year,
                    weight=self.config.get('objective_function', {}).get('fifth_year_priority', 3)
                ))

        # S08: Time slot variation (for all classes)
        for row in self.csv_data.get('classi', []):
            constraints.append(TimeSlotVariationConstraint(
                class_id=int(row['classe_id']),
                class_name=row['nome'],
                weight=self.config.get('objective_function', {}).get('time_slot_variation', 2)
            ))

        return constraints

    def _build_lab_constraints(self) -> List[Constraint]:
        """Build constraints related to labs and class-lab combinations."""
        constraints = []

        # Get lab details
        lab_info = {}
        for row in self.csv_data.get('laboratori', []):
            lab_info[int(row['laboratorio_id'])] = {
                'name': row['nome'],
                'num_meetings': int(row['num_incontri']),
                'hours_per_meeting': int(row['ore_per_incontro'])
            }

        for row in self.csv_data.get('laboratori_classi', []):
            class_id = int(row['classe_id'])
            class_name = row['nome_classe']
            lab_id = int(row['laboratorio_id'])
            lab_name = lab_info.get(lab_id, {}).get('name', f'Lab {lab_id}')

            # H03: Fixed dates
            fixed_dates_str = row.get('date_fissate', '').strip()
            if fixed_dates_str:
                constraints.append(FixedDatesConstraint(
                    class_id=class_id,
                    class_name=class_name,
                    lab_id=lab_id,
                    lab_name=lab_name,
                    fixed_dates=self._parse_fixed_dates(fixed_dates_str)
                ))

            # H05: Lab time of day (if dettagli specifies only mattina/pomeriggio)
            dettagli = self._parse_dettagli(row.get('dettagli', ''))
            if dettagli['time_of_day']:
                constraints.append(LabTimeOfDayConstraint(
                    class_id=class_id,
                    class_name=class_name,
                    lab_id=lab_id,
                    lab_name=lab_name,
                    time_of_day=dettagli['time_of_day']
                ))

            # H13: Lab completion
            num_meetings = lab_info.get(lab_id, {}).get('num_meetings', 0)
            if dettagli['partial_meetings']:
                num_meetings = dettagli['partial_meetings']

            if num_meetings > 0:
                constraints.append(LabCompletionConstraint(
                    class_id=class_id,
                    class_name=class_name,
                    lab_id=lab_id,
                    lab_name=lab_name,
                    num_meetings_required=num_meetings
                ))

            # SP02: Partial lab meetings
            if dettagli['partial_meetings']:
                constraints.append(PartialLabMeetingsConstraint(
                    class_id=class_id,
                    class_name=class_name,
                    lab_id=lab_id,
                    lab_name=lab_name,
                    standard_meetings=lab_info.get(lab_id, {}).get('num_meetings', 0),
                    actual_meetings=dettagli['partial_meetings']
                ))

            # SP03: Multiple afternoon meetings non-consecutive
            if dettagli['afternoon_count']:
                constraints.append(MultiMeetingAfternoonConstraint(
                    class_id=class_id,
                    class_name=class_name,
                    lab_id=lab_id,
                    lab_name=lab_name,
                    num_afternoon_required=dettagli['afternoon_count'],
                    avoid_consecutive=True
                ))

            # SP04: One meeting must be afternoon
            if dettagli['one_afternoon']:
                constraints.append(OneMeetingTimeConstraint(
                    class_id=class_id,
                    class_name=class_name,
                    lab_id=lab_id,
                    lab_name=lab_name,
                    time_of_day='pomeriggio',
                    min_meetings_required=1
                ))

        return constraints

    def _build_grouping_constraints(self) -> List[Constraint]:
        """Build constraints related to class grouping."""
        constraints = []

        # H12: Max group size
        constraints.append(MaxGroupSizeConstraint(max_group_size=2))

        # S01: Maximize grouping (global constraint)
        constraints.append(MaximizeGroupingConstraint(
            weight=self.config.get('objective_function', {}).get('maximize_grouping', 20)
        ))

        return constraints

    def _build_global_constraints(self) -> List[Constraint]:
        """Build global/system-wide constraints."""
        constraints = []

        # H11: Scheduling period
        constraints.append(SchedulingPeriodConstraint())

        # S06: Lab sequence preference
        constraints.append(LabSequenceConstraint(
            weight=self.config.get('objective_function', {}).get('lab_sequence', 2)
        ))

        # S10: Minimize late May scheduling
        constraints.append(MinimizeLateMaySchedulingConstraint(
            weight=self.config.get('objective_function', {}).get('minimize_late_may', 1)
        ))

        return constraints

    def _build_special_constraints(self) -> List[Constraint]:
        """Build special-case constraints."""
        constraints = []

        # SP01: Citizen Science gap (for applicable schools)
        citizen_science_schools = ["Potenza", "Vasto", "Bafile", "Lanciano", "Peano Rosa"]

        # Build school_id -> school_name mapping
        school_map = {}
        for row in self.csv_data.get('scuole', []):
            school_map[int(row['scuola_id'])] = row['nome']

        # Find classes that do lab 4 (Citizen Science) in applicable schools
        for row in self.csv_data.get('laboratori_classi', []):
            if int(row['laboratorio_id']) == 4:  # Citizen Science
                school_id = int(row['scuola_id'])
                school_name = school_map.get(school_id, '')
                applies = school_name in citizen_science_schools

                constraints.append(CitizenScienceGapConstraint(
                    class_id=int(row['classe_id']),
                    class_name=row['nome_classe'],
                    school_id=school_id,
                    school_name=school_name,
                    applies=applies
                ))

        # SP06: Ignore external labs
        constraints.append(IgnoreExternalLabsConstraint())

        # SP07: Saturday only Margherita
        constraints.append(SaturdayOnlyMargheritaConstraint())

        return constraints

    def get_constraint_summary(self, constraints: List[Constraint]) -> Dict[str, Any]:
        """Generate summary statistics about constraints."""
        from collections import Counter

        summary = {
            'total': len(constraints),
            'by_type': Counter(c.type.value for c in constraints),
            'by_category': Counter(c.category.value for c in constraints),
            'by_class': Counter(c.__class__.__name__ for c in constraints),
            'hard_constraints': [c for c in constraints if c.type.value == 'hard'],
            'soft_constraints': [c for c in constraints if c.type.value == 'soft'],
        }

        return summary

    def export_constraints_to_json(self, constraints: List[Constraint], filepath: str):
        """Export constraints to JSON for documentation/debugging."""
        import json

        data = [c.to_dict() for c in constraints]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
