"""
Hard constraints for Cosmic School scheduling.

These constraints MUST be satisfied for any feasible solution.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal, Any, Tuple
from .base import HardConstraint, ConstraintCategory, MeetingKey


@dataclass(kw_only=True)
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

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
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
            # Ottieni ore per questo lab dal context
            lab_id = meeting.lab_id
            hours = context.lab_info[lab_id]['hours_per_meeting']

            is_f = variables.is_formatrice.get((self.trainer_id, meeting))
            if is_f is not None:
                # is_f è una BoolVar CP-SAT: se vale 1, contribuisce hours; se vale 0, contribuisce 0
                hour_contributions.append(hours * is_f)

        # Sottrai ore duplicate per accorpamenti
        # Se due classi sono accorpate, la formatrice fa UN solo incontro per entrambe
        # Quindi sottraiamo le ore del "secondo" meeting (c2) quando accorpa=1
        for (c1, c2, lab), accorpa_var in variables.accorpa.items():
            # Ottieni numero di meeting per questo lab
            lab_info = context.lab_info[lab]
            num_meetings = lab_info.get('num_meetings', 1)
            hours_per_meeting = lab_info['hours_per_meeting']

            for k in range(num_meetings):
                # Crea chiave per il k-esimo meeting di c2
                meeting_c2 = MeetingKey(c2, lab, k)

                if meeting_c2 in variables.meetings:
                    is_f_c2 = variables.is_formatrice.get((self.trainer_id, meeting_c2))
                    if is_f_c2 is not None:
                        # Crea variabile intermedia: both = accorpa AND is_assigned_to_this_trainer
                        both = model.NewBoolVar(f"grp_hrs_{self.trainer_id}_{c2}_{lab}_{k}")
                        model.AddBoolAnd([accorpa_var, is_f_c2]).OnlyEnforceIf(both)
                        model.AddBoolOr([accorpa_var.Not(), is_f_c2.Not()]).OnlyEnforceIf(both.Not())

                        # Sottrai le ore duplicate
                        hour_contributions.append(-hours_per_meeting * both)

        if hour_contributions:
            total_hours = sum(hour_contributions)
            model.Add(total_hours <= self.max_hours)


@dataclass(kw_only=True)
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

    id: str = field(default="H02", init=False)
    name: str = field(default="Trainer Availability", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Trainer can only work on available days/times", init=False)

    def validate(self, solution: Any) -> bool:
        """Check if all assignments respect trainer availability."""
        pass

    def _parse_italian_datetime(self, date_str: str, date_mapper) -> List[Tuple[int, int, int]]:
        """
        Parse Italian date-time format like "13 Gennaio 10.00-14.00".

        Returns:
            List of (week, day, fascia) tuples. May return multiple tuples for time ranges.
        """
        import re
        from datetime import datetime

        # Italian month names
        month_map = {
            'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
            'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
            'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
        }

        # Parse format: "13 Gennaio 10.00-14.00"
        match = re.match(r'(\d+)\s+(\w+)\s+([\d.]+)-([\d.]+)', date_str.strip(), re.IGNORECASE)
        if not match:
            return []

        day_num = int(match.group(1))
        month_name = match.group(2).lower()
        start_time = match.group(3)
        end_time = match.group(4)

        month = month_map.get(month_name)
        if not month:
            return []

        # Assume year 2026
        try:
            date = datetime(2026, month, day_num)
        except ValueError:
            return []

        # Convert to (week, day)
        try:
            week, day = date_mapper.date_to_week_day(date)
        except ValueError:
            return []

        # Parse time range to fascia
        # 08:00-10:00, 09:00-11:00, 10:00-12:00, 11:00-13:00 -> fascia 1 or 2
        # 14:00-16:00, 15:00-17:00 -> fascia 3
        start_hour = int(start_time.split('.')[0])
        end_hour = int(end_time.split('.')[0])

        slots = []

        # Determine which fasce have sufficient overlap (at least 1 hour)
        # This allows Margherita's flexible time slots like 08:00-10:00 or 15:00-17:00

        # Fascia 1: 09:00-11:00
        # Check overlap: max(start, 9) to min(end, 11)
        fascia1_start, fascia1_end = 9, 11
        overlap1 = max(0, min(end_hour, fascia1_end) - max(start_hour, fascia1_start))
        if overlap1 >= 1:  # At least 1 hour overlap
            slots.append((week, day, 1))

        # Fascia 2: 11:00-13:00
        fascia2_start, fascia2_end = 11, 13
        overlap2 = max(0, min(end_hour, fascia2_end) - max(start_hour, fascia2_start))
        if overlap2 >= 1:
            slots.append((week, day, 2))

        # Fascia 3: 14:00-16:00
        fascia3_start, fascia3_end = 14, 16
        overlap3 = max(0, min(end_hour, fascia3_end) - max(start_hour, fascia3_start))
        if overlap3 >= 1:
            slots.append((week, day, 3))

        return slots

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Add constraints based on available days and time slots."""
        # Mappings
        day_to_num = {"lun": 0, "mar": 1, "mer": 2, "gio": 3, "ven": 4, "sab": 5}
        fascia_morning = [1, 2]  # mattino1, mattino2
        fascia_afternoon = [3]   # pomeriggio

        # Crea variabili is_formatrice per tutti gli incontri
        for meeting in variables.meetings:
            key = (self.trainer_id, meeting)
            if key not in variables.is_formatrice:
                is_f = model.NewBoolVar(f"isf_{self.trainer_id}_{meeting}")
                model.Add(variables.formatrice[meeting] == self.trainer_id).OnlyEnforceIf(is_f)
                model.Add(variables.formatrice[meeting] != self.trainer_id).OnlyEnforceIf(is_f.Not())
                variables.is_formatrice[key] = is_f

        # Per ogni incontro assegnato a questa formatrice
        for meeting in variables.meetings:
            is_f = variables.is_formatrice[(self.trainer_id, meeting)]

            # 1. Saturday constraint
            if not self.works_saturday:
                # Se non lavora il sabato, giorno != 5 quando assegnata
                model.Add(variables.giorno[meeting] != 5).OnlyEnforceIf(is_f)

            # 2. Available mornings/afternoons
            # ONLY apply generic availability if NO whitelist is provided
            # If whitelist (available_dates) exists, skip generic constraints
            if not self.available_dates:
                # Se available_mornings è vuoto, non può fare mattine
                if not self.available_mornings:
                    # fascia != 1 AND fascia != 2
                    for f in fascia_morning:
                        model.Add(variables.fascia[meeting] != f).OnlyEnforceIf(is_f)

                # Se available_afternoons è vuoto, non può fare pomeriggi
                if not self.available_afternoons:
                    # fascia != 3
                    for f in fascia_afternoon:
                        model.Add(variables.fascia[meeting] != f).OnlyEnforceIf(is_f)

            # 3. Specific weekday restrictions per time of day
            # ONLY apply if NO whitelist (same as above)
            if not self.available_dates and self.available_mornings:
                available_morning_days = [day_to_num[d] for d in self.available_mornings if d in day_to_num]

                # Se assegnata a questa formatrice E in fascia mattina, allora giorno deve essere in available_morning_days
                for f in fascia_morning:
                    is_morning = model.NewBoolVar(f"is_morning_{self.trainer_id}_{meeting}_{f}")
                    model.Add(variables.fascia[meeting] == f).OnlyEnforceIf(is_morning)
                    model.Add(variables.fascia[meeting] != f).OnlyEnforceIf(is_morning.Not())

                    # is_f AND is_morning => giorno in available_morning_days
                    both = model.NewBoolVar(f"both_{self.trainer_id}_{meeting}_{f}")
                    model.AddBoolAnd([is_f, is_morning]).OnlyEnforceIf(both)

                    # Se both=True, allora giorno deve essere in available_morning_days
                    # Usiamo AddAllowedAssignments
                    if available_morning_days:
                        # giorno deve essere uno dei valori permessi
                        allowed_tuples = [(d,) for d in available_morning_days]
                        model.AddAllowedAssignments([variables.giorno[meeting]], allowed_tuples).OnlyEnforceIf(both)

            # Stessa logica per pomeriggi
            if not self.available_dates and self.available_afternoons:
                available_afternoon_days = [day_to_num[d] for d in self.available_afternoons if d in day_to_num]

                for f in fascia_afternoon:
                    is_afternoon = model.NewBoolVar(f"is_afternoon_{self.trainer_id}_{meeting}_{f}")
                    model.Add(variables.fascia[meeting] == f).OnlyEnforceIf(is_afternoon)
                    model.Add(variables.fascia[meeting] != f).OnlyEnforceIf(is_afternoon.Not())

                    both = model.NewBoolVar(f"both_aft_{self.trainer_id}_{meeting}_{f}")
                    model.AddBoolAnd([is_f, is_afternoon]).OnlyEnforceIf(both)

                    if available_afternoon_days:
                        allowed_tuples = [(d,) for d in available_afternoon_days]
                        model.AddAllowedAssignments([variables.giorno[meeting]], allowed_tuples).OnlyEnforceIf(both)

        # 4. WHITELIST: available_dates (specific date-time slots)
        # TEMPORARILY DISABLED: Too many constraints (~500 per trainer)
        # TODO: Optimize implementation using forbidden slots instead of allowed slots
        if False and self.available_dates:
            from ..date_utils import DateMapper
            date_mapper = DateMapper()

            allowed_slots = set()  # Set of (week, day, fascia) tuples

            for date_str in self.available_dates:
                # Parse format like "13 Gennaio 10.00-14.00"
                parsed_slots = self._parse_italian_datetime(date_str, date_mapper)
                for slot in parsed_slots:
                    allowed_slots.add(slot)

            if allowed_slots:
                # For each meeting, if assigned to this trainer, (week, day, fascia) must be in allowed_slots
                for meeting in variables.meetings:
                    is_f = variables.is_formatrice[(self.trainer_id, meeting)]

                    # Convert to list of tuples
                    allowed_tuples = list(allowed_slots)

                    # If assigned to this trainer, then (settimana, giorno, fascia) must be in allowed_tuples
                    model.AddAllowedAssignments(
                        [variables.settimana[meeting], variables.giorno[meeting], variables.fascia[meeting]],
                        allowed_tuples
                    ).OnlyEnforceIf(is_f)


@dataclass(kw_only=True)
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

    id: str = field(default="H03", init=False)
    name: str = field(default="Fixed Dates", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Pre-fixed dates are immutable and occupy the class for that week", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that fixed dates are preserved and no other meetings in same week."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Fix assignments for these specific dates."""
        from date_utils import DateMapper

        if not self.fixed_dates:
            # Nessuna data fissata
            return

        date_mapper = DateMapper()

        # Trova gli incontri di questa classe per questo lab
        class_meetings = variables.meetings_by_class.get(self.class_id, [])
        lab_meetings = [m for m in class_meetings if m.lab_id == self.lab_id]

        if not lab_meetings:
            return

        # Parse fixed dates
        fixed_slots = []
        for date_str in self.fixed_dates:
            result = date_mapper.parse_datetime_range(date_str)
            if result:
                date, slot = result
                try:
                    week, day = date_mapper.date_to_week_day(date)
                    fixed_slots.append((week, day, slot))
                except ValueError as e:
                    # Data fuori dalle finestre valide o in domenica
                    continue

        if not fixed_slots:
            # Nessuna data valida parsata
            return

        # Assegna le prime N meetings alle date fissate
        for i, (week, day, slot) in enumerate(fixed_slots):
            if i >= len(lab_meetings):
                break  # Più date fissate che incontri

            meeting = lab_meetings[i]

            # Fissa le variabili
            model.Add(variables.settimana[meeting] == week)
            model.Add(variables.giorno[meeting] == day)
            model.Add(variables.fascia[meeting] == slot)


@dataclass(kw_only=True)
class ClassLabAssignmentConstraint(HardConstraint):
    """
    H04: Each class only does specific labs assigned to it.

    Source: laboratori_classi.csv
    Not all classes do all labs. Each class has a specific subset.
    """
    class_id: int
    class_name: str
    assigned_labs: List[int]  # Lab IDs this class must complete

    id: str = field(default="H04", init=False)
    name: str = field(default="Class-Lab Assignment", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.ASSIGNMENT, init=False)
    description: str = field(default="Class can only be assigned to its designated labs", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that class only has meetings for assigned labs."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Constrain assignments to only assigned labs."""
        # Già gestito implicitamente nella creazione delle variabili:
        # creiamo variabili solo per i lab assegnati a ciascuna classe
        # (vedi build_variables() in optimizer.py)
        pass


@dataclass(kw_only=True)
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

    id: str = field(default="H05", init=False)
    name: str = field(default="Lab Time of Day", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Lab must be scheduled in specified time of day (morning/afternoon)", init=False)

    def validate(self, solution: Any) -> bool:
        """Check if lab is scheduled in correct time of day."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Constrain time slot to morning or afternoon slots."""
        # Trova tutti gli incontri di questa classe per questo lab
        class_meetings = variables.meetings_by_class.get(self.class_id, [])
        lab_meetings = [m for m in class_meetings if m.lab_id == self.lab_id]

        # Mappings
        fascia_morning = [1, 2]   # mattino1, mattino2
        fascia_afternoon = [3]    # pomeriggio

        for meeting in lab_meetings:
            if self.time_of_day == "mattina":
                # fascia deve essere 1 o 2
                model.AddAllowedAssignments([variables.fascia[meeting]], [(1,), (2,)])
            elif self.time_of_day == "pomeriggio":
                # fascia deve essere 3
                model.Add(variables.fascia[meeting] == 3)


@dataclass(kw_only=True)
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

    id: str = field(default="H06", init=False)
    name: str = field(default="Class Time Slots", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Class can only use available time slots and weekdays", init=False)

    def validate(self, solution: Any) -> bool:
        """Check if all class meetings use allowed slots and weekdays."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Constrain assignments to available slots and days."""
        if not self.is_hard:
            # Se non è un constraint hard (preferenza invece di disponibile), skip
            return

        # Mappings
        day_to_num = {"lunedì": 0, "martedì": 1, "mercoledì": 2,
                      "giovedì": 3, "venerdì": 4, "sabato": 5}
        slot_to_num = {"mattino1": 1, "mattino2": 2, "pomeriggio": 3}

        # Trova tutti gli incontri di questa classe
        class_meetings = variables.meetings_by_class.get(self.class_id, [])

        # Converti available_slots e available_weekdays in numeri
        available_slot_nums = [slot_to_num.get(s, 0) for s in self.available_slots if s in slot_to_num]
        available_day_nums = [day_to_num.get(d, 0) for d in self.available_weekdays if d in day_to_num]

        for meeting in class_meetings:
            # Fascia deve essere in available_slots
            if available_slot_nums:
                allowed_fasce = [(f,) for f in available_slot_nums]
                model.AddAllowedAssignments([variables.fascia[meeting]], allowed_fasce)

            # Giorno deve essere in available_weekdays
            if available_day_nums:
                allowed_giorni = [(d,) for d in available_day_nums]
                model.AddAllowedAssignments([variables.giorno[meeting]], allowed_giorni)


@dataclass(kw_only=True)
class ClassExcludedDatesConstraint(HardConstraint):
    """
    H07: Class cannot have meetings on excluded dates.

    Source: date_escluse_classi.csv -> date_escluse
    Dates when class is unavailable (various formats need parsing).
    """
    class_id: int
    class_name: str
    excluded_dates: List[str]  # Parsed date ranges/specific dates

    id: str = field(default="H07", init=False)
    name: str = field(default="Class Excluded Dates", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Class cannot have meetings on excluded dates", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that no meetings fall on excluded dates."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Exclude assignments on forbidden dates."""
        from date_utils import DateMapper

        if not self.excluded_dates:
            return

        date_mapper = DateMapper()

        # Trova tutti gli incontri di questa classe
        class_meetings = variables.meetings_by_class.get(self.class_id, [])

        if not class_meetings:
            return

        # Parse excluded dates e converti in (settimana, giorno)
        excluded_week_days = []

        for date_str in self.excluded_dates:
            # Prova a parsare come singola data
            date = date_mapper.parse_date_string(date_str)
            if date:
                try:
                    week, day = date_mapper.date_to_week_day(date)
                    excluded_week_days.append((week, day))
                except ValueError:
                    # Data fuori range
                    continue

        if not excluded_week_days:
            return

        # Per ogni incontro, escludi le date proibite
        for meeting in class_meetings:
            for week, day in excluded_week_days:
                # Se settimana = week AND giorno = day, allora False
                # Usiamo AddBoolOr per negare la condizione
                is_week = model.NewBoolVar(f"is_week_{meeting}_{week}")
                is_day = model.NewBoolVar(f"is_day_{meeting}_{day}")

                model.Add(variables.settimana[meeting] == week).OnlyEnforceIf(is_week)
                model.Add(variables.settimana[meeting] != week).OnlyEnforceIf(is_week.Not())

                model.Add(variables.giorno[meeting] == day).OnlyEnforceIf(is_day)
                model.Add(variables.giorno[meeting] != day).OnlyEnforceIf(is_day.Not())

                # Non può essere entrambi (week AND day)
                model.AddBoolOr([is_week.Not(), is_day.Not()])


@dataclass(kw_only=True)
class MaxOneMeetingPerWeekConstraint(HardConstraint):
    """
    H08: Each class can have at most 1 meeting per week.

    This applies to both scheduled meetings and fixed dates.
    """
    class_id: int
    class_name: str

    id: str = field(default="H08", init=False)
    name: str = field(default="Max One Meeting Per Week", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="Class can have maximum 1 meeting per week (including fixed dates)", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that class has max 1 meeting per week."""
        # TODO: Implement validation logic
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Add constraint: sum(meetings_in_week) <= 1."""
        # Raccogli tutte le variabili settimana per questa classe
        week_vars = []

        for meeting in variables.meetings_by_class.get(self.class_id, []):
            if meeting in variables.settimana:
                week_vars.append(variables.settimana[meeting])

        # Se la classe ha più di un incontro, devono essere in settimane diverse
        if len(week_vars) > 1:
            model.AddAllDifferent(week_vars)


@dataclass(kw_only=True)
class Lab8LastConstraint(HardConstraint):
    """
    H09: Lab 8.0 (Presentazione Manuali) must always be the last lab for each class.

    Source: INTERPRETAZIONE_VINCOLI.md -> Laboratorio 8.0
    """
    class_id: int
    class_name: str

    id: str = field(default="H09", init=False)
    name: str = field(default="Lab 8 Must Be Last", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.SEQUENCING, init=False)
    description: str = field(default="Lab 8.0 (Presentazione Manuali) must be scheduled last", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that Lab 8 is scheduled after all other labs."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Add constraint: Lab 8 must be scheduled after all other labs for this class."""
        # Lab 8.0 = laboratorio_id 8
        LAB_8_ID = 8

        # Trova tutti gli incontri di questa classe
        class_meetings = variables.meetings_by_class.get(self.class_id, [])

        # Separa incontri Lab 8 da altri lab
        lab8_meetings = [m for m in class_meetings if m.lab_id == LAB_8_ID]
        other_meetings = [m for m in class_meetings if m.lab_id != LAB_8_ID]

        if not lab8_meetings or not other_meetings:
            # Se non c'è Lab 8 o non ci sono altri lab, nessun constraint
            return

        # Lab 8 deve iniziare dopo tutti gli altri lab
        # Prendi il primo incontro del Lab 8
        first_lab8 = min(lab8_meetings, key=lambda m: m.meeting_index)

        # Per ogni altro incontro, Lab 8 deve essere in una settimana successiva
        for other in other_meetings:
            # week[lab8_first] > week[other]
            model.Add(variables.settimana[first_lab8] > variables.settimana[other])


@dataclass(kw_only=True)
class NoTrainerOverlapConstraint(HardConstraint):
    """
    H10: A trainer cannot be in two places at the same time.

    No double-booking of trainers.
    """
    trainer_id: int
    trainer_name: str

    id: str = field(default="H10", init=False)
    name: str = field(default="No Trainer Overlap", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.CAPACITY, init=False)
    description: str = field(default="Trainer cannot have overlapping assignments", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that trainer has no overlapping meetings."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Add constraint: trainer cannot have overlapping assignments using interval variables.

        This uses CP-SAT's NoOverlap constraint which is much more efficient than
        creating O(n²) pairwise constraints. We create optional interval variables
        for each meeting, active only when assigned to this trainer.

        IMPORTANT: When two classes are grouped (accorpa=1), they share the same slot
        and trainer. We must NOT count the "secondary" class's meeting as a separate
        interval, otherwise NoOverlap will incorrectly flag it as overlapping.
        """
        intervals = []

        # Build mapping: for each meeting, find if it's a "secondary" in any grouping
        # Secondary = c2 in accorpa[c1, c2, lab] where c1 < c2
        # We collect all accorpa variables where this meeting's class is c2
        meeting_is_secondary = {}  # meeting -> list of accorpa BoolVars
        for (c1, c2, lab), accorpa_var in variables.accorpa.items():
            # Find all meetings of c2 for this lab
            for meeting in variables.meetings:
                if meeting.class_id == c2 and meeting.lab_id == lab:
                    if meeting not in meeting_is_secondary:
                        meeting_is_secondary[meeting] = []
                    meeting_is_secondary[meeting].append(accorpa_var)

        for meeting in variables.meetings:
            key = (self.trainer_id, meeting)

            # Create is_formatrice variable if not exists
            if key not in variables.is_formatrice:
                is_f = model.NewBoolVar(f"isf_{self.trainer_id}_{meeting}")
                model.Add(variables.formatrice[meeting] == self.trainer_id).OnlyEnforceIf(is_f)
                model.Add(variables.formatrice[meeting] != self.trainer_id).OnlyEnforceIf(is_f.Not())
                variables.is_formatrice[key] = is_f

            is_assigned = variables.is_formatrice[key]

            # Check if this meeting is secondary in any grouping
            secondary_vars = meeting_is_secondary.get(meeting, [])

            if secondary_vars:
                # This meeting could be secondary (grouped with another class)
                # is_present = is_assigned AND NOT(any secondary grouping is active)
                # i.e., the interval is present only if assigned AND not grouped as secondary

                # Create: is_secondary = OR(all accorpa vars for this meeting)
                is_secondary = model.NewBoolVar(f"is_sec_{self.trainer_id}_{meeting}")
                model.AddBoolOr(secondary_vars).OnlyEnforceIf(is_secondary)
                model.AddBoolAnd([v.Not() for v in secondary_vars]).OnlyEnforceIf(is_secondary.Not())

                # is_present = is_assigned AND NOT is_secondary
                is_present = model.NewBoolVar(f"present_{self.trainer_id}_{meeting}")
                model.AddBoolAnd([is_assigned, is_secondary.Not()]).OnlyEnforceIf(is_present)
                model.AddBoolOr([is_assigned.Not(), is_secondary]).OnlyEnforceIf(is_present.Not())
            else:
                # Not a secondary in any grouping, just use is_assigned
                is_present = is_assigned

            # Create optional interval variable
            # - start: slot (linear time encoding: week*60 + day*12 + timeslot)
            # - size: 1 (each meeting occupies exactly 1 discrete slot)
            # - is_present: True only if this trainer is assigned AND not grouped as secondary
            interval = model.NewOptionalFixedSizeIntervalVar(
                start=variables.slot[meeting],
                size=1,
                is_present=is_present,
                name=f"interval_t{self.trainer_id}_m{meeting}"
            )
            intervals.append(interval)

        # Single NoOverlap constraint replaces 115,440 pairwise constraints per trainer
        # This is O(n) instead of O(n²) - approximately 100x more efficient!
        model.AddNoOverlap(intervals)


@dataclass(kw_only=True)
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

    id: str = field(default="H11", init=False)
    name: str = field(default="Scheduling Period", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.TEMPORAL, init=False)
    description: str = field(default="All meetings must be within scheduling windows (excluding Easter)", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that all meetings are within valid windows."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Constrain meeting dates to valid windows."""
        from datetime import datetime

        # Week 0 is partial: starts Monday 26/01 but school starts Wednesday 28/01
        # So days 0 (Mon 26/01) and 1 (Tue 27/01) are not valid
        WINDOW1_START = datetime(2026, 1, 28)  # Wednesday

        for meeting in variables.meetings:
            # For week 0, only days 2-5 are valid (Wed-Sat, starting from 28/01)
            # Create constraint: week=0 => day >= 2
            is_week0 = model.NewBoolVar(f"is_w0_{meeting}")
            model.Add(variables.settimana[meeting] == 0).OnlyEnforceIf(is_week0)
            model.Add(variables.settimana[meeting] != 0).OnlyEnforceIf(is_week0.Not())

            # If week 0, then day must be >= 2 (Wednesday or later)
            model.Add(variables.giorno[meeting] >= 2).OnlyEnforceIf(is_week0)

        # Easter break: weeks 10-11 are not available
        EASTER_WEEKS = [10, 11]
        for meeting in variables.meetings:
            for week in EASTER_WEEKS:
                model.Add(variables.settimana[meeting] != week)


@dataclass(kw_only=True)
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

    id: str = field(default="H12", init=False)
    name: str = field(default="Max Group Size", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.GROUPING, init=False)
    description: str = field(default="Maximum 2 classes can be grouped together per meeting", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that no meeting has > 2 classes."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Add constraint: maximum 2 classes can be grouped.

        For each class, at most ONE accorpa variable involving that class can be true.
        This prevents chains like: A-B grouped AND A-C grouped → A,B,C all together.

        For each class X and each lab:
            sum(accorpa[(X,Y,lab)] for all Y) + sum(accorpa[(Z,X,lab)] for all Z) <= 1
        """
        from collections import defaultdict

        # Group accorpa variables by (class, lab)
        # For each class, collect all accorpa vars where it participates
        class_lab_accorpa = defaultdict(list)  # (class_id, lab_id) -> [accorpa_vars]

        for (c1, c2, lab), accorpa_var in variables.accorpa.items():
            # c1 participates in this grouping
            class_lab_accorpa[(c1, lab)].append(accorpa_var)
            # c2 participates in this grouping
            class_lab_accorpa[(c2, lab)].append(accorpa_var)

        # For each (class, lab), at most one accorpa can be true
        for (class_id, lab_id), accorpa_vars in class_lab_accorpa.items():
            if len(accorpa_vars) > 1:
                # sum(accorpa_vars) <= 1
                model.Add(sum(accorpa_vars) <= 1)


@dataclass(kw_only=True)
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

    id: str = field(default="H13", init=False)
    name: str = field(default="Lab Completion", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.ASSIGNMENT, init=False)
    description: str = field(default="Class must complete all required meetings for each lab", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that all required meetings are scheduled."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Add constraint: all required meetings must be scheduled."""
        # Già gestito implicitamente nella creazione delle variabili:
        # creiamo esattamente num_meetings_required variabili per ogni (classe, lab)
        # Quindi tutte le variabili devono essere assegnate = tutti gli incontri schedulati
        pass


@dataclass(kw_only=True)
class Lab9BeforeLab5Constraint(HardConstraint):
    """
    H14: Lab 9.0 must be scheduled before Lab 5.0.

    Source: INTERPRETAZIONE_VINCOLI.md -> Sequenza Ideale Laboratori FOP
    Lab 9.0 (Sensibilizzazione pt.2) must come before Lab 5.0 (Orientamento).
    """
    class_id: int
    class_name: str

    id: str = field(default="H14", init=False)
    name: str = field(default="Lab 9 Before Lab 5", init=False)
    category: ConstraintCategory = field(default=ConstraintCategory.SEQUENCING, init=False)
    description: str = field(default="Lab 9.0 must be scheduled before Lab 5.0", init=False)

    def validate(self, solution: Any) -> bool:
        """Check that Lab 9 comes before Lab 5."""
        pass

    def add_to_model(self, model: Any, variables: Any, context: Any) -> None:
        """Add constraint: Lab 9 must be scheduled before Lab 5."""
        LAB_9_ID = 9
        LAB_5_ID = 5

        # Trova tutti gli incontri di questa classe
        class_meetings = variables.meetings_by_class.get(self.class_id, [])

        # Trova incontri dei lab 9 e 5
        lab9_meetings = [m for m in class_meetings if m.lab_id == LAB_9_ID]
        lab5_meetings = [m for m in class_meetings if m.lab_id == LAB_5_ID]

        if not lab9_meetings or not lab5_meetings:
            # Se non ci sono entrambi i lab, nessun constraint
            return

        # L'ultimo incontro del Lab 9 deve essere prima del primo incontro del Lab 5
        last_lab9 = max(lab9_meetings, key=lambda m: m.meeting_index)
        first_lab5 = min(lab5_meetings, key=lambda m: m.meeting_index)

        # week[last_lab9] < week[first_lab5]
        model.Add(variables.settimana[last_lab9] < variables.settimana[first_lab5])
