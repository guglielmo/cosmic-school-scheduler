"""
Special rules and exceptions for Cosmic School scheduling.

These are special-case constraints that don't fit standard categories.
"""

from dataclasses import dataclass, field
from typing import List, Any
from .base import HardConstraint, ConstraintCategory


@dataclass
class CitizenScienceGapConstraint(HardConstraint):
    """
    SP01: Citizen Science Lab 4.0 has 5 meetings, but 3rd is autonomous.

    Source: INTERPRETAZIONE_VINCOLI.md -> Vincoli Speciali
    Applies to schools: Potenza, Vasto, Bafile, Lanciano, Peano Rosa

    Implementation:
    - Schedule only meetings 1, 2, 4, 5 (4 meetings with trainer)
    - Leave 1 week gap between meeting 2 and meeting 4
    - That week = autonomous meeting (no trainer involved)

    Constraint: week_meeting4 >= week_meeting2 + 2
    """
    class_id: int
    class_name: str
    school_id: int
    school_name: str
    applies: bool = False  # True only for specific schools

    # Schools where this applies
    APPLICABLE_SCHOOLS: List[str] = field(default_factory=lambda: [
        "Potenza", "Vasto", "Bafile", "Lanciano", "Peano Rosa"
    ])

    id: str = "SP01"
    name: str = "Citizen Science Gap"
    category: ConstraintCategory = ConstraintCategory.SEQUENCING
    description: str = "Citizen Science needs 1 week gap between meeting 2 and 4 (autonomous meeting)"

    def validate(self, solution: Any) -> bool:
        """Check that there's a 1-week gap between meetings 2 and 4."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: week[meeting4] >= week[meeting2] + 2."""
        pass


@dataclass
class PartialLabMeetingsConstraint(HardConstraint):
    """
    SP02: Some classes do only partial meetings for a lab.

    Source: laboratori_classi.csv -> dettagli (e.g., "solo 1 incontro", "solo 2 incontri")

    When specified, class does fewer meetings than the standard num_incontri.
    Examples:
    - Lab normally has 5 meetings, but this class only does 1
    - Lab normally has 2 meetings, but this class only does 1
    """
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    standard_meetings: int  # From laboratori.csv: num_incontri
    actual_meetings: int    # Reduced number for this class

    id: str = "SP02"
    name: str = "Partial Lab Meetings"
    category: ConstraintCategory = ConstraintCategory.ASSIGNMENT
    description: str = "Class does fewer meetings than standard for this lab"

    def validate(self, solution: Any) -> bool:
        """Check that class has exactly actual_meetings scheduled."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Constrain number of meetings to actual_meetings."""
        pass


@dataclass
class MultiMeetingAfternoonConstraint(HardConstraint):
    """
    SP03: Multiple meetings must be in afternoon but not consecutive weeks.

    Source: laboratori_classi.csv -> dettagli
    Examples:
    - "2 incontri devono essere di pomeriggio ma non in settimane consecutive"
    - "3 incontri devono essere di pomeriggio ma non in settimane consecutive"

    Constraints:
    1. Specified number of meetings must be in afternoon
    2. Those afternoon meetings cannot be in consecutive weeks
    """
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    num_afternoon_required: int  # How many must be afternoon
    avoid_consecutive: bool = True

    id: str = "SP03"
    name: str = "Multi Meeting Afternoon Non-Consecutive"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Multiple afternoon meetings but not in consecutive weeks"

    def validate(self, solution: Any) -> bool:
        """Check afternoon count and non-consecutiveness."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraints for afternoon count and spacing."""
        pass


@dataclass
class OneMeetingTimeConstraint(HardConstraint):
    """
    SP04: One meeting of a lab must be at specific time of day.

    Source: laboratori_classi.csv -> dettagli
    Examples:
    - "un incontro deve essere di pomeriggio"
    - "un incontro deve essere di mattina" (less common)

    At least one meeting must be scheduled in the specified time period.
    """
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    time_of_day: str  # "mattina" or "pomeriggio"
    min_meetings_required: int = 1

    id: str = "SP04"
    name: str = "One Meeting Time Constraint"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "At least one meeting must be in specified time of day"

    def validate(self, solution: Any) -> bool:
        """Check that at least one meeting is in specified time."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraint: sum(meetings_in_time) >= 1."""
        pass


@dataclass
class WeekdayTimeSpecificConstraint(HardConstraint):
    """
    SP05: Some weekdays only allow specific times (morning/afternoon).

    Source: fasce_orarie_classi.csv -> giorni_settimana
    Examples:
    - "mercoledì pomeriggio" (Wednesday only available in afternoon)
    - "lunedì mattina" (Monday only available in morning)

    Parse complex weekday availability like:
    "lunedi, martedi, mercoledi pomeriggio, giovedi pomeriggio, venerdi"
    """
    class_id: int
    class_name: str
    weekday_constraints: dict  # {"mercoledì": "pomeriggio", "giovedì": "pomeriggio"}

    id: str = "SP05"
    name: str = "Weekday Time Specific"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Specific weekdays only available at certain times"

    def validate(self, solution: Any) -> bool:
        """Check that weekday-time combinations are respected."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Add constraints for weekday-time combinations."""
        pass


@dataclass
class IgnoreExternalLabsConstraint(HardConstraint):
    """
    SP06: Ignore labs managed by external partners (GSSI/GST/LNGS).

    Source: INTERPRETAZIONE_VINCOLI.md -> Laboratori
    Only consider labs 4.0, 5.0, 7.0, 8.0, 9.0 (FOP trainer labs).
    IGNORE labs 1.0, 1.1, 2.0, 3.0, 6.0 (external partner labs).

    This is more of a filtering rule than a constraint.
    """
    fop_labs: List[int] = field(default_factory=lambda: [4, 5, 7, 8, 9])
    external_labs: List[int] = field(default_factory=lambda: [1, 2, 3, 6, 11])  # 11 = 1.1

    id: str = "SP06"
    name: str = "Ignore External Labs"
    category: ConstraintCategory = ConstraintCategory.ASSIGNMENT
    description: str = "Only schedule FOP trainer labs (4, 5, 7, 8, 9), ignore external labs"

    def validate(self, solution: Any) -> bool:
        """Check that no external labs are scheduled."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Filter out external labs from decision variables."""
        pass


@dataclass
class SaturdayOnlyMargheritaConstraint(HardConstraint):
    """
    SP07: Only Margherita can work on Saturday.

    Source: formatrici.csv -> lavora_sabato
    Also requires schools that can work Saturday (needs identification).

    Combined with TrainerAvailabilityConstraint (H02).
    """
    trainer_id: int = 4  # Margherita
    trainer_name: str = "Margherita"

    id: str = "SP07"
    name: str = "Saturday Only Margherita"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Only Margherita can work on Saturday"

    def validate(self, solution: Any) -> bool:
        """Check that only Margherita has Saturday assignments."""
        pass

    def add_to_model(self, model: Any, variables: Any) -> None:
        """Constrain Saturday assignments to Margherita only."""
        pass
