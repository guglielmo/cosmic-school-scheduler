"""
Soft constraints (preferences) for Cosmic School scheduling.

These constraints contribute to the objective function and should be optimized.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal, Any
from .base import SoftConstraint, ConstraintCategory


@dataclass(kw_only=True)
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

    id: str = field(default="S01", init=False)
    name: str = field(default="Maximize Grouping", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.GROUPING, init=False)
    description: str = field(default="Maximize class grouping to stay within hours budget (CRITICAL)", init=False)

    def penalty(self, solution: Any) -> float:
        """Calculate bonus (negative penalty) for each grouped meeting."""
        # TODO: Implement validation logic
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
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


@dataclass(kw_only=True)
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

    id: str = field(default="S02", init=False)
    name: str = field(default="Trainer Continuity", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.ASSIGNMENT, init=False)
    description: str = field(default="Prefer same trainer for all labs of a class", init=False)

    def penalty(self, solution: Any) -> float:
        """Count number of times trainer changes for this class."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add penalty term for each trainer change."""
        # Trova tutti gli incontri di questa classe
        class_meetings = variables.meetings_by_class.get(self.class_id, [])

        if not class_meetings:
            return 0

        # Per ogni incontro, penalizza se non è assegnato alla formatrice preferita
        penalty_terms = []

        for meeting in class_meetings:
            # Crea variabile is_not_preferred: True se formatrice != preferred
            is_not_preferred = model.NewBoolVar(f"not_pref_{self.class_id}_{meeting}")
            model.Add(variables.formatrice[meeting] != self.preferred_trainer_id).OnlyEnforceIf(is_not_preferred)
            model.Add(variables.formatrice[meeting] == self.preferred_trainer_id).OnlyEnforceIf(is_not_preferred.Not())

            # Ogni volta che non è la formatrice preferita, aggiungiamo 1 alla penalità
            penalty_terms.append(is_not_preferred)

        # Ritorna la somma delle penalità (da minimizzare)
        # Nota: l'obiettivo è massimizzato, quindi ritorniamo -sum per massimizzare continuità
        return -sum(penalty_terms) if penalty_terms else 0


@dataclass(kw_only=True)
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

    id: str = field(default="S03", init=False)
    name: str = field(default="Trainer Weekly Hours", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.CAPACITY, init=False)
    description: str = field(default="Try to match average weekly hours target (not strict)", init=False)

    def penalty(self, solution: Any) -> float:
        """Calculate deviation from target weekly hours."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add penalty for deviation from weekly target."""
        # TODO: Implementazione complessa - richiede calcolo delle ore per settimana
        # per ogni formatrice e penalizzare deviazioni dalla media target
        # Per ora skip
        pass


@dataclass(kw_only=True)
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

    id: str = field(default="S04", init=False)
    name: str = field(default="Trainer Time Preference", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Respect trainer's morning/afternoon preference", init=False)

    def penalty(self, solution: Any) -> float:
        """Count mismatches with time preference."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add penalty for assignments not matching preference."""
        # Mappings
        fascia_morning = [1, 2]
        fascia_afternoon = [3]

        # Crea variabili is_formatrice per tutti gli incontri
        for meeting in variables.meetings:
            key = (self.trainer_id, meeting)
            if key not in variables.is_formatrice:
                is_f = model.NewBoolVar(f"isf_{self.trainer_id}_{meeting}")
                model.Add(variables.formatrice[meeting] == self.trainer_id).OnlyEnforceIf(is_f)
                model.Add(variables.formatrice[meeting] != self.trainer_id).OnlyEnforceIf(is_f.Not())
                variables.is_formatrice[key] = is_f

        penalty_terms = []

        for meeting in variables.meetings:
            is_f = variables.is_formatrice[(self.trainer_id, meeting)]

            # Penalizza se non rispetta la preferenza
            if self.preferred_time == "mattina":
                # Vuole mattina, penalizza se pomeriggio
                for f in fascia_afternoon:
                    is_afternoon = model.NewBoolVar(f"aft_{self.trainer_id}_{meeting}_{f}")
                    model.Add(variables.fascia[meeting] == f).OnlyEnforceIf(is_afternoon)
                    model.Add(variables.fascia[meeting] != f).OnlyEnforceIf(is_afternoon.Not())

                    # both = is_f AND is_afternoon
                    both = model.NewBoolVar(f"both_{self.trainer_id}_{meeting}_{f}")
                    model.AddBoolAnd([is_f, is_afternoon]).OnlyEnforceIf(both)

                    penalty_terms.append(both)

            elif self.preferred_time == "pomeriggio":
                # Vuole pomeriggio, penalizza se mattina
                for f in fascia_morning:
                    is_morning = model.NewBoolVar(f"morn_{self.trainer_id}_{meeting}_{f}")
                    model.Add(variables.fascia[meeting] == f).OnlyEnforceIf(is_morning)
                    model.Add(variables.fascia[meeting] != f).OnlyEnforceIf(is_morning.Not())

                    both = model.NewBoolVar(f"both_{self.trainer_id}_{meeting}_{f}")
                    model.AddBoolAnd([is_f, is_morning]).OnlyEnforceIf(both)

                    penalty_terms.append(both)

        # Ritorna -sum per massimizzare (minimizzare penalità)
        return -sum(penalty_terms) if penalty_terms else 0


@dataclass(kw_only=True)
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

    id: str = field(default="S05", init=False)
    name: str = field(default="Preferred Grouping", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.GROUPING, init=False)
    description: str = field(default="Prefer grouping classes with their preferred partners", init=False)

    def penalty(self, solution: Any) -> float:
        """Calculate bonus (negative penalty) when paired with preferred partner."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add bonus term when preferred grouping occurs."""
        # Se esiste una variabile accorpa per questa coppia preferita, premiala

        # Cerca tutte le variabili accorpa che coinvolgono questa coppia
        bonus_terms = []

        for (c1, c2, lab), accorpa_var in variables.accorpa.items():
            # Se questa coppia corrisponde alla preferenza (in qualsiasi ordine)
            if ((c1 == self.class_id and c2 == self.preferred_partner_id) or
                (c1 == self.preferred_partner_id and c2 == self.class_id)):
                # Bonus quando accorpa=1
                bonus_terms.append(accorpa_var)

        # Ritorna somma dei bonus (già positivo per massimizzare)
        return sum(bonus_terms) if bonus_terms else 0


@dataclass(kw_only=True)
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

    id: str = field(default="S06", init=False)
    name: str = field(default="Lab Sequence", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.SEQUENCING, init=False)
    description: str = field(default="Prefer ideal sequence: Sensibilizzazione → Citizen Science → Orientamento", init=False)

    def penalty(self, solution: Any) -> float:
        """Calculate bonus (negative penalty) for respecting sequence."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add bonus term for correct sequence."""
        # Sequenza ideale: 7.0 -> 4.0 -> 5.0
        # Penalizza se non rispetta l'ordine

        # Per ogni classe, verifica se ha questi lab e se rispetta l'ordine
        penalty_terms = []

        for class_id in context.class_info.keys():
            class_meetings = variables.meetings_by_class.get(class_id, [])

            # Trova incontri dei lab nella sequenza ideale
            lab7_meetings = [m for m in class_meetings if m.lab_id == 7]
            lab4_meetings = [m for m in class_meetings if m.lab_id == 4]
            lab5_meetings = [m for m in class_meetings if m.lab_id == 5]

            # Se ha lab 7 e lab 4, 7 deve venire prima di 4
            if lab7_meetings and lab4_meetings:
                last_lab7 = max(lab7_meetings, key=lambda m: m.meeting_index)
                first_lab4 = min(lab4_meetings, key=lambda m: m.meeting_index)

                # Penalizza se week[lab7] >= week[lab4]
                violates = model.NewBoolVar(f"viol_74_{class_id}")
                model.Add(variables.settimana[last_lab7] >= variables.settimana[first_lab4]).OnlyEnforceIf(violates)
                model.Add(variables.settimana[last_lab7] < variables.settimana[first_lab4]).OnlyEnforceIf(violates.Not())
                penalty_terms.append(violates)

            # Se ha lab 4 e lab 5, 4 deve venire prima di 5
            if lab4_meetings and lab5_meetings:
                last_lab4 = max(lab4_meetings, key=lambda m: m.meeting_index)
                first_lab5 = min(lab5_meetings, key=lambda m: m.meeting_index)

                violates = model.NewBoolVar(f"viol_45_{class_id}")
                model.Add(variables.settimana[last_lab4] >= variables.settimana[first_lab5]).OnlyEnforceIf(violates)
                model.Add(variables.settimana[last_lab4] < variables.settimana[first_lab5]).OnlyEnforceIf(violates.Not())
                penalty_terms.append(violates)

        # Ritorna -sum per massimizzare (minimizzare violazioni)
        return -sum(penalty_terms) if penalty_terms else 0


@dataclass(kw_only=True)
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

    id: str = field(default="S07", init=False)
    name: str = field(default="Fifth Year Priority", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Fifth-year classes should finish early (avoid May)", init=False)

    def penalty(self, solution: Any) -> float:
        """Calculate penalty for late scheduling (especially May)."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add increasing penalty for later weeks."""
        if self.class_year != 5:
            # Solo per classi quinte
            return 0

        # Trova tutti gli incontri di questa classe
        class_meetings = variables.meetings_by_class.get(self.class_id, [])

        if not class_meetings:
            return 0

        # Penalizza settimane tarde (settimane 12+ sono a Maggio, assumendo)
        # Penalità progressiva: settimana * coefficiente
        MAY_START_WEEK = 12  # Settimane dopo questa sono considerate "tarde"

        penalty_terms = []

        for meeting in class_meetings:
            # Per ogni incontro, aggiungiamo una penalità proporzionale alla settimana
            # se la settimana è >= MAY_START_WEEK

            # Crea variabile is_late: True se settimana >= MAY_START_WEEK
            is_late = model.NewBoolVar(f"late_{self.class_id}_{meeting}")
            model.Add(variables.settimana[meeting] >= MAY_START_WEEK).OnlyEnforceIf(is_late)
            model.Add(variables.settimana[meeting] < MAY_START_WEEK).OnlyEnforceIf(is_late.Not())

            # Se late, penalità = settimana (più tardi = più penalità)
            # Usiamo una variabile ausiliaria
            week_penalty = model.NewIntVar(0, context.num_settimane, f"week_pen_{self.class_id}_{meeting}")
            model.Add(week_penalty == variables.settimana[meeting]).OnlyEnforceIf(is_late)
            model.Add(week_penalty == 0).OnlyEnforceIf(is_late.Not())

            penalty_terms.append(week_penalty)

        # Ritorna -sum per massimizzare (vogliamo minimizzare la penalità)
        return -sum(penalty_terms) if penalty_terms else 0


@dataclass(kw_only=True)
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

    id: str = field(default="S08", init=False)
    name: str = field(default="Time Slot Variation", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Rotate time slots to avoid same slot in consecutive weeks", init=False)

    def penalty(self, solution: Any) -> float:
        """Count occurrences of same slot in consecutive weeks."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add penalty for same slot in consecutive weeks."""
        # Trova tutti gli incontri di questa classe
        class_meetings = variables.meetings_by_class.get(self.class_id, [])

        if len(class_meetings) < 2:
            # Serve almeno 2 incontri per avere consecutive weeks
            return 0

        # Ordina per settimana (approssimazione: usiamo tutti i meeting)
        penalty_terms = []

        # Per ogni coppia di incontri
        for i, m1 in enumerate(class_meetings):
            for m2 in class_meetings[i+1:]:
                # Se sono in settimane consecutive E hanno stesso slot, penalità
                # week2 == week1 + 1 AND slot2 == slot1

                # Crea variabile consecutive_weeks
                consecutive = model.NewBoolVar(f"consec_{self.class_id}_{m1}_{m2}")
                # consecutive sse |week1 - week2| == 1
                diff = model.NewIntVar(-context.num_settimane, context.num_settimane, f"diff_{m1}_{m2}")
                model.Add(diff == variables.settimana[m2] - variables.settimana[m1])

                # consecutive se diff == 1 o diff == -1
                is_plus_one = model.NewBoolVar(f"plus_{m1}_{m2}")
                is_minus_one = model.NewBoolVar(f"minus_{m1}_{m2}")
                model.Add(diff == 1).OnlyEnforceIf(is_plus_one)
                model.Add(diff != 1).OnlyEnforceIf(is_plus_one.Not())
                model.Add(diff == -1).OnlyEnforceIf(is_minus_one)
                model.Add(diff != -1).OnlyEnforceIf(is_minus_one.Not())

                model.AddBoolOr([is_plus_one, is_minus_one]).OnlyEnforceIf(consecutive)
                model.AddBoolAnd([is_plus_one.Not(), is_minus_one.Not()]).OnlyEnforceIf(consecutive.Not())

                # Crea variabile same_slot
                same_slot = model.NewBoolVar(f"same_{self.class_id}_{m1}_{m2}")
                model.Add(variables.slot[m1] == variables.slot[m2]).OnlyEnforceIf(same_slot)
                model.Add(variables.slot[m1] != variables.slot[m2]).OnlyEnforceIf(same_slot.Not())

                # Penalità se consecutive AND same_slot
                both = model.NewBoolVar(f"both_{self.class_id}_{m1}_{m2}")
                model.AddBoolAnd([consecutive, same_slot]).OnlyEnforceIf(both)

                penalty_terms.append(both)

        # Ritorna -sum per massimizzare (minimizzare penalità)
        return -sum(penalty_terms) if penalty_terms else 0


@dataclass(kw_only=True)
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

    id: str = field(default="S09", init=False)
    name: str = field(default="Balance Trainer Load", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.CAPACITY, init=False)
    description: str = field(default="Balance trainer workload across weeks (avoid extreme weeks)", init=False)

    def penalty(self, solution: Any) -> float:
        """Calculate variance in weekly hours."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add penalty for high variance in weekly load."""
        # TODO: Implementazione complessa - richiede calcolo ore per settimana
        # e calcolo varianza, che è difficile da modellare in CP-SAT
        # Per ora skip
        pass


@dataclass(kw_only=True)
class MinimizeLateMaySchedulingConstraint(SoftConstraint):
    """
    S10: Generally prefer earlier scheduling over later.

    Beyond S07 (fifth year priority), generally prefer finishing earlier.

    Weight: 1 (low penalty for late scheduling)
    """
    weight: int = 1

    id: str = field(default="S10", init=False)
    name: str = field(default="Minimize Late May Scheduling", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Generally prefer earlier scheduling", init=False)

    def penalty(self, solution: Any) -> float:
        """Small penalty for meetings in late May."""
        pass

    def add_to_objective(self, model: Any, variables: Any, context: Any) -> Any:
        """Add small penalty for late meetings."""
        # Penalizza tutti gli incontri schedulati tardi (settimane > 12)
        LATE_THRESHOLD = 12

        penalty_terms = []

        for meeting in variables.meetings:
            # Crea variabile is_late
            is_late = model.NewBoolVar(f"late_{meeting}")
            model.Add(variables.settimana[meeting] > LATE_THRESHOLD).OnlyEnforceIf(is_late)
            model.Add(variables.settimana[meeting] <= LATE_THRESHOLD).OnlyEnforceIf(is_late.Not())

            penalty_terms.append(is_late)

        # Ritorna -sum per massimizzare (minimizzare penalità)
        return -sum(penalty_terms) if penalty_terms else 0
