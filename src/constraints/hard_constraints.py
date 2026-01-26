"""
Hard constraints for Cosmic School scheduling.

These constraints MUST be satisfied for any feasible solution.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal, Any
from .base import HardConstraint, ConstraintCategory


@dataclass
class TrainerTotalHoursConstraint(HardConstraint):
    """
    H01: Total hours budget for each trainer must be respected.

    Source: formatrici.csv -> ore_generali
    Each trainer has a fixed total hours budget for the entire scheduling period.
    """
    trainer_id: int
    trainer_name: str
    max_hours: int

    id: str = field(default="H01", init=False)
    name: str = field(default="Trainer Total Hours", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.CAPACITY, init=False)
    description: str = field(default="Total hours budget per trainer must not be exceeded", init=False)

    def validate(self, solution: Any) -> bool:
        """Check if trainer's total hours <= max_hours."""
        # TODO: Implement validation logic
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: sum(assigned_hours) <= max_hours."""
        # Crea variabili is_formatrice se non esistono
        for meeting in variables.meetings:
            key = (self.trainer_id, meeting)
            if key not in variables.is_formatrice:
                is_f = model.NewBoolVar(f"isf_{self.trainer_id}_{meeting}")
                model.Add(variables.formatrice[meeting] == self.trainer_id).OnlyEnforceIf(is_f)
                model.Add(variables.formatrice[meeting] != self.trainer_id).OnlyEnforceIf(is_f.Not())
                variables.is_formatrice[key] = is_f

        # Raccogli contributi ore per questa formatrice
        hour_contributions = []

        for meeting in variables.meetings:
            # Ottieni ore per questo lab (assume che variabili abbia accesso a lab_info)
            # Per ora usiamo un default di 2 ore (TODO: passare lab_info a constraint)
            hours = 2  # Default, deve essere passato dal context

            is_f = variables.is_formatrice.get((self.trainer_id, meeting))
            if is_f:
                hour_contributions.append(hours * is_f)

        # TODO: Sottrarre ore duplicate per accorpamenti quando implementati

        if hour_contributions:
            total_hours = sum(hour_contributions)
            model.Add(total_hours <= self.max_hours)


@dataclass
class TrainerAvailabilityConstraint(HardConstraint):
    """
    H02: Trainer temporal availability must be respected.

    Source: formatrici.csv -> mattine_disponibili, pomeriggi_disponibili,
            date_disponibili, date_escluse_formatrici, lavora_sabato

    Logic:
    - If date_disponibili is set: ONLY those dates/times are available (WHITELIST)
    - If excluded_dates is set: all dates OK EXCEPT those (BLACKLIST)
    - Otherwise: use mattine_disponibili + pomeriggi_disponibili
    - If both empty: all dates available
    - works_saturday: only Margherita can work on Saturday
    """
    trainer_id: int
    trainer_name: str
    available_mornings: List[str]  # ["lun", "mar", ...]
    available_afternoons: List[str]  # ["lun", "mer", ...]
    available_dates: Optional[List[str]] = None  # WHITELIST: Specific date-time slots
    excluded_dates: Optional[List[str]] = None   # BLACKLIST: Dates to exclude
    works_saturday: bool = False

    id: str = "H02"
    name: str = "Trainer Availability"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Trainer can only work on available days/times"

    def validate(self, solution: Any) -> bool:
        """Check if all assignments respect trainer availability."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraints based on available days and time slots."""
        pass


@dataclass
class FixedDatesConstraint(HardConstraint):
    """
    H03: Pre-fixed dates are immutable (SUPER HARD).

    Source: laboratori_classi.csv -> date_fissate
    These dates are already confirmed and cannot be changed.

    Impact:
    - Class is occupied in that week
    - Must respect "max 1 meeting/week" constraint
    - Cannot schedule other meetings in the same week
    """
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    fixed_dates: List[str]  # Parsed dates (e.g., ["2026-02-26 09:00-13:00"])

    id: str = "H03"
    name: str = "Fixed Dates"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Pre-fixed dates are immutable and occupy the class for that week"

    def validate(self, solution: Any) -> bool:
        """Check that fixed dates are preserved and no other meetings in same week."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Fix assignments for these specific dates."""
        pass


@dataclass
class ClassLabAssignmentConstraint(HardConstraint):
    """
    H04: Each class only does specific labs assigned to it.

    Source: laboratori_classi.csv
    Not all classes do all labs. Each class has a specific subset.
    """
    class_id: int
    class_name: str
    assigned_labs: List[int]  # Lab IDs this class must complete

    id: str = "H04"
    name: str = "Class-Lab Assignment"
    category: ConstraintCategory = ConstraintCategory.ASSIGNMENT
    description: str = "Class can only be assigned to its designated labs"

    def validate(self, solution: Any) -> bool:
        """Check that class only has meetings for assigned labs."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Constrain assignments to only assigned labs."""
        pass


@dataclass
class LabTimeOfDayConstraint(HardConstraint):
    """
    H05: Lab must be scheduled at specific time of day (morning/afternoon).

    Source: laboratori_classi.csv -> dettagli
    When specified, the lab meeting MUST be in morning or afternoon.
    """
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    time_of_day: Literal["mattina", "pomeriggio"]

    id: str = "H05"
    name: str = "Lab Time of Day"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Lab must be scheduled in specified time of day (morning/afternoon)"

    def validate(self, solution: Any) -> bool:
        """Check if lab is scheduled in correct time of day."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Constrain time slot to morning or afternoon slots."""
        pass


@dataclass
class ClassTimeSlotsConstraint(HardConstraint):
    """
    H06: Class can only use specific time slots.

    Source: fasce_orarie_classi.csv -> fasce_disponibili, preferenza, giorni_settimana

    If preferenza = "disponibile": HARD constraint (class can ONLY use these slots)
    Also includes weekday restrictions (e.g., "lunedì a giovedì")
    """
    class_id: int
    class_name: str
    available_slots: List[str]  # Slot IDs (e.g., ["mattino1", "mattino2"])
    is_hard: bool  # True if preferenza = "disponibile"
    available_weekdays: List[str]  # e.g., ["lunedì", "martedì", ...]

    id: str = "H06"
    name: str = "Class Time Slots"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Class can only use available time slots and weekdays"

    def validate(self, solution: Any) -> bool:
        """Check if all class meetings use allowed slots and weekdays."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Constrain assignments to available slots and days."""
        pass


@dataclass
class ClassExcludedDatesConstraint(HardConstraint):
    """
    H07: Class cannot have meetings on excluded dates.

    Source: date_escluse_classi.csv -> date_escluse
    Dates when class is unavailable (various formats need parsing).
    """
    class_id: int
    class_name: str
    excluded_dates: List[str]  # Parsed date ranges/specific dates

    id: str = "H07"
    name: str = "Class Excluded Dates"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Class cannot have meetings on excluded dates"

    def validate(self, solution: Any) -> bool:
        """Check that no meetings fall on excluded dates."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Exclude assignments on forbidden dates."""
        pass


@dataclass
class MaxOneMeetingPerWeekConstraint(HardConstraint):
    """
    H08: Each class can have at most 1 meeting per week.

    This applies to both scheduled meetings and fixed dates.
    """
    class_id: int
    class_name: str

    id: str = "H08"
    name: str = "Max One Meeting Per Week"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Class can have maximum 1 meeting per week (including fixed dates)"

    def validate(self, solution: Any) -> bool:
        """Check that class has max 1 meeting per week."""
        # TODO: Implement validation logic
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: sum(meetings_in_week) <= 1."""
        # Raccogli tutte le variabili settimana per questa classe
        week_vars = []

        for meeting in variables.meetings_by_class.get(self.class_id, []):
            if meeting in variables.settimana:
                week_vars.append(variables.settimana[meeting])

        # Se la classe ha più di un incontro, devono essere in settimane diverse
        if len(week_vars) > 1:
            model.AddAllDifferent(week_vars)


@dataclass
class Lab8LastConstraint(HardConstraint):
    """
    H09: Lab 8.0 (Presentazione Manuali) must always be the last lab for each class.

    Source: INTERPRETAZIONE_VINCOLI.md -> Laboratorio 8.0
    """
    class_id: int
    class_name: str

    id: str = "H09"
    name: str = "Lab 8 Must Be Last"
    category: ConstraintCategory = ConstraintCategory.SEQUENCING
    description: str = "Lab 8.0 (Presentazione Manuali) must be scheduled last"

    def validate(self, solution: Any) -> bool:
        """Check that Lab 8 is scheduled after all other labs."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: week_lab8 > week_all_other_labs."""
        pass


@dataclass
class NoTrainerOverlapConstraint(HardConstraint):
    """
    H10: A trainer cannot be in two places at the same time.

    No double-booking of trainers.
    """
    trainer_id: int
    trainer_name: str

    id: str = "H10"
    name: str = "No Trainer Overlap"
    category: ConstraintCategory = ConstraintCategory.CAPACITY
    description: str = "Trainer cannot have overlapping assignments"

    def validate(self, solution: Any) -> bool:
        """Check that trainer has no overlapping meetings."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: sum(overlapping_assignments) <= 1."""
        pass


@dataclass
class SchedulingPeriodConstraint(HardConstraint):
    """
    H11: All meetings must fall within scheduling windows.

    Source: INTERPRETAZIONE_VINCOLI.md
    Window 1: 28/1/2026 - 1/4/2026
    Window 2: 13/4/2026 - 16/5/2026
    (Easter break in between)
    """
    window1_start: str = "2026-01-28"
    window1_end: str = "2026-04-01"
    window2_start: str = "2026-04-13"
    window2_end: str = "2026-05-16"

    id: str = "H11"
    name: str = "Scheduling Period"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "All meetings must be within scheduling windows (excluding Easter)"

    def validate(self, solution: Any) -> bool:
        """Check that all meetings are within valid windows."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Constrain meeting dates to valid windows."""
        pass


@dataclass
class MaxGroupSizeConstraint(HardConstraint):
    """
    H12: Maximum 2 classes can be grouped together for a meeting.

    Source: INTERPRETAZIONE_VINCOLI.md -> Accorpamenti Classi
    General rule: max 2 classes per meeting (for trainer-led labs).

    Conditions for grouping:
    - Same school
    - Same lab
    - Same trainer (if pre-assigned)
    - Same time slot (week + day + time slot)
    - Compatible time slots for both classes
    - Compatible available dates for both
    """
    max_group_size: int = 2

    id: str = "H12"
    name: str = "Max Group Size"
    category: ConstraintCategory = ConstraintCategory.GROUPING
    description: str = "Maximum 2 classes can be grouped together per meeting"

    def validate(self, solution: Any) -> bool:
        """Check that no meeting has > 2 classes."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: sum(classes_in_meeting) <= 2."""
        pass


@dataclass
class LabCompletionConstraint(HardConstraint):
    """
    H13: Each class must complete all its assigned labs.

    Source: Implicit requirement
    All num_incontri for each lab must be scheduled.
    """
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    num_meetings_required: int

    id: str = "H13"
    name: str = "Lab Completion"
    category: ConstraintCategory = ConstraintCategory.ASSIGNMENT
    description: str = "Class must complete all required meetings for each lab"

    def validate(self, solution: Any) -> bool:
        """Check that all required meetings are scheduled."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: sum(scheduled_meetings) = num_meetings_required."""
        pass


@dataclass
class Lab9BeforeLab5Constraint(HardConstraint):
    """
    H14: Lab 9.0 must be scheduled before Lab 5.0.

    Source: INTERPRETAZIONE_VINCOLI.md -> Sequenza Ideale Laboratori FOP
    Lab 9.0 (Sensibilizzazione pt.2) must come before Lab 5.0 (Orientamento).
    """
    class_id: int
    class_name: str

    id: str = "H14"
    name: str = "Lab 9 Before Lab 5"
    category: ConstraintCategory = ConstraintCategory.SEQUENCING
    description: str = "Lab 9.0 must be scheduled before Lab 5.0"

    def validate(self, solution: Any) -> bool:
        """Check that Lab 9 comes before Lab 5."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: week_lab9 < week_lab5."""
        pass
