"""
Soft constraints (preferences) for Cosmic School scheduling.

These constraints contribute to the objective function and should be optimized.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal, Any
from .base import SoftConstraint, ConstraintCategory


@dataclass
class MaximizeGroupingConstraint(SoftConstraint):
    """
    S01: Maximize grouping of classes (HIGHEST PRIORITY).

    Source: INTERPRETAZIONE_VINCOLI.md -> Budget Ore
    Grouping is ESSENTIAL to stay within budget:
    - With grouping: 664 hours needed
    - Without: 926 hours needed
    - Budget: 708 hours

    Weight: -20 (negative = bonus for grouping, to maximize)
    """
    weight: int = 20  # Penalty reduction when grouping occurs

    id: str = "S01"
    name: str = "Maximize Grouping"
    category: ConstraintCategory = ConstraintCategory.GROUPING
    description: str = "Maximize class grouping to stay within hours budget (CRITICAL)"

    def penalty(self, solution: Any) -> float:
        """Calculate bonus (negative penalty) for each grouped meeting."""
        # TODO: Implement validation logic
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add bonus term for each grouping to objective."""
        # Per ogni variabile accorpa che è True, aggiungiamo un bonus
        # Nota: il peso è positivo, quindi massimizzare accorpa[] massimizza l'obiettivo

        if not variables.accorpa:
            # Nessuna variabile accorpamento creata
            return 0

        # Somma di tutte le variabili accorpamento
        # Ogni accorpa[c1,c2,lab] = 1 contribuisce +1 all'obiettivo
        # Con peso 20, ogni accorpamento vale +20 nell'obiettivo
        return sum(variables.accorpa.values())


@dataclass
class TrainerContinuityConstraint(SoftConstraint):
    """
    S02: Prefer same trainer for all labs of a class.

    Source: formatrici_classi.csv, INTERPRETAZIONE_VINCOLI.md
    "Ideally each trainer should follow the same class for all labs"
    Not HARD, but strongly preferred.

    Weight: 10 (high penalty for changing trainer)
    """
    class_id: int
    class_name: str
    preferred_trainer_id: int
    preferred_trainer_name: str
    weight: int = 10

    id: str = "S02"
    name: str = "Trainer Continuity"
    category: ConstraintCategory = ConstraintCategory.ASSIGNMENT
    description: str = "Prefer same trainer for all labs of a class"

    def penalty(self, solution: Any) -> float:
        """Count number of times trainer changes for this class."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add penalty term for each trainer change."""
        pass


@dataclass
class TrainerWeeklyHoursConstraint(SoftConstraint):
    """
    S03: Try to match average weekly hours target.

    Source: formatrici.csv -> ore_settimanali (media)
    Not strict - the important thing is total hours (H01).
    This just helps distribute work evenly.

    Weight: 3 (medium penalty for deviation)
    """
    trainer_id: int
    trainer_name: str
    target_weekly_hours: float
    weight: int = 3

    id: str = "S03"
    name: str = "Trainer Weekly Hours"
    category: ConstraintCategory = ConstraintCategory.CAPACITY
    description: str = "Try to match average weekly hours target (not strict)"

    def penalty(self, solution: Any) -> float:
        """Calculate deviation from target weekly hours."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add penalty for deviation from weekly target."""
        pass


@dataclass
class TrainerTimePreferenceConstraint(SoftConstraint):
    """
    S04: Respect trainer's time preference (morning/afternoon/mixed).

    Source: formatrici.csv -> preferenza_fasce
    Soft preference - respect when possible but not blocking.

    Weight: 1 (low penalty)
    """
    trainer_id: int
    trainer_name: str
    preferred_time: Literal["mattina", "pomeriggio", "misto"]
    weight: int = 1

    id: str = "S04"
    name: str = "Trainer Time Preference"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Respect trainer's morning/afternoon preference"

    def penalty(self, solution: Any) -> float:
        """Count mismatches with time preference."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add penalty for assignments not matching preference."""
        pass


@dataclass
class PreferredGroupingConstraint(SoftConstraint):
    """
    S05: Prefer grouping of classes with preferred partners.

    Source: classi.csv -> accorpamento_preferenziale
    E.g., 5B prefers to be grouped with 5C.

    Weight: 5 (medium bonus when grouped together)
    """
    class_id: int
    class_name: str
    preferred_partner_id: int
    preferred_partner_name: str
    weight: int = 5

    id: str = "S05"
    name: str = "Preferred Grouping"
    category: ConstraintCategory = ConstraintCategory.GROUPING
    description: str = "Prefer grouping classes with their preferred partners"

    def penalty(self, solution: Any) -> float:
        """Calculate bonus (negative penalty) when paired with preferred partner."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add bonus term when preferred grouping occurs."""
        pass


@dataclass
class LabSequenceConstraint(SoftConstraint):
    """
    S06: Prefer ideal sequence of labs.

    Source: INTERPRETAZIONE_VINCOLI.md -> Sequenza Ideale Laboratori FOP
    Preferred order: 7.0 (Sensibilizzazione) → 4.0 (Citizen Science) → 5.0 (Orientamento)
    Lab 8.0 always last (HARD: H09)
    Lab 9.0 before 5.0 (HARD: H14)

    Weight: 2 (bonus for respecting sequence)
    """
    ideal_sequence: List[int] = field(default_factory=lambda: [7, 4, 5])
    weight: int = 2

    id: str = "S06"
    name: str = "Lab Sequence"
    category: ConstraintCategory = ConstraintCategory.SEQUENCING
    description: str = "Prefer ideal sequence: Sensibilizzazione → Citizen Science → Orientamento"

    def penalty(self, solution: Any) -> float:
        """Calculate bonus (negative penalty) for respecting sequence."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add bonus term for correct sequence."""
        pass


@dataclass
class FifthYearPriorityConstraint(SoftConstraint):
    """
    S07: Fifth-year classes should finish earlier.

    Source: INTERPRETAZIONE_VINCOLI.md -> Priorità Classi Quinte
    Avoid scheduling in May if possible.

    Weight: 3 (penalty increases for later weeks)
    """
    class_id: int
    class_name: str
    class_year: int
    weight: int = 3

    id: str = "S07"
    name: str = "Fifth Year Priority"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Fifth-year classes should finish early (avoid May)"

    def penalty(self, solution: Any) -> float:
        """Calculate penalty for late scheduling (especially May)."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add increasing penalty for later weeks."""
        pass


@dataclass
class TimeSlotVariationConstraint(SoftConstraint):
    """
    S08: Avoid same time slot in consecutive weeks.

    Source: INTERPRETAZIONE_VINCOLI.md -> Variazione Fasce Orarie
    Rotate time slots to avoid burdening same teachers.

    Weight: 2 (small penalty for same slot in consecutive weeks)
    """
    class_id: int
    class_name: str
    weight: int = 2

    id: str = "S08"
    name: str = "Time Slot Variation"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Rotate time slots to avoid same slot in consecutive weeks"

    def penalty(self, solution: Any) -> float:
        """Count occurrences of same slot in consecutive weeks."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add penalty for same slot in consecutive weeks."""
        pass


@dataclass
class BalanceTrainerLoadConstraint(SoftConstraint):
    """
    S09: Balance trainer workload across weeks.

    Avoid weeks with extreme high/low hours for trainers.
    Helps with S03 but focuses on variance rather than average.

    Weight: 2 (small penalty for imbalanced weeks)
    """
    trainer_id: int
    trainer_name: str
    weight: int = 2

    id: str = "S09"
    name: str = "Balance Trainer Load"
    category: ConstraintCategory = ConstraintCategory.CAPACITY
    description: str = "Balance trainer workload across weeks (avoid extreme weeks)"

    def penalty(self, solution: Any) -> float:
        """Calculate variance in weekly hours."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add penalty for high variance in weekly load."""
        pass


@dataclass
class MinimizeLateMaySchedulingConstraint(SoftConstraint):
    """
    S10: Generally prefer earlier scheduling over later.

    Beyond S07 (fifth year priority), generally prefer finishing earlier.

    Weight: 1 (low penalty for late scheduling)
    """
    weight: int = 1

    id: str = "S10"
    name: str = "Minimize Late May Scheduling"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL
    description: str = "Generally prefer earlier scheduling"

    def penalty(self, solution: Any) -> float:
        """Small penalty for meetings in late May."""
        pass

    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """Add small penalty for late meetings."""
        pass
