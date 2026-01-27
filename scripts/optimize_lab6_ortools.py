#!/usr/bin/env python3
"""
Scheduler OR-Tools per il laboratorio 6 (2 incontri).

Vincoli speciali Lab 6:
- I 2 incontri devono essere CONSECUTIVI (settimane consecutive)
- Non devono esserci altri laboratori tra i 2 incontri Lab 6
- Sequenzialità con altri lab: Lab 6 dopo Lab 4, Lab 5
"""

import csv
from typing import Dict, List, Set, Tuple
from ortools.sat.python import cp_model


def read_previous_labs_schedule():
    """
    Legge i calendari dei lab precedenti (Lab 4 e Lab 5).
    Returns: dict mapping classe_id -> list of (slot_id, lab_id)
    """
    previous_schedule = {}

    # Lab 4
    with open('data/output/calendario_lab4_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_disponibili']:
                    continue
                if val.startswith('L4-'):
                    classe_id = int(col.split('-')[0])
                    if classe_id not in previous_schedule:
                        previous_schedule[classe_id] = []
                    previous_schedule[classe_id].append((slot_id, 4))

    # Lab 5
    with open('data/output/calendario_lab5_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_lab5',
                          'num_formatrici_lab4', 'num_formatrici_totali', 'num_formatrici_disponibili']:
                    continue
                if val.startswith('L5-'):
                    classe_id = int(col.split('-')[0])
                    if classe_id not in previous_schedule:
                        previous_schedule[classe_id] = []
                    lab_part = val.split('/')[0]  
                    previous_schedule[classe_id].append((slot_id, 5))

    return previous_schedule


def read_lab6_classes() -> Dict[int, int]:
    """Legge quanti incontri Lab 6 servono per ogni classe."""
    lab6_classes = {}

    with open('data/input/laboratori_classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['laboratorio_id'] == '6':
                classe_id = int(row['classe_id'])
                # Lab 6 ha sempre 2 incontri
                lab6_classes[classe_id] = 2

    return lab6_classes


def read_class_availability() -> Dict[int, Set[str]]:
    """Legge disponibilità delle classi."""
    class_availability = {}

    with open('data/output/class_availability.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            for col, val in row.items():
                if col != 'slot_id' and val == 'S':
                    classe_id = int(col.split('-')[0])
                    if classe_id not in class_availability:
                        class_availability[classe_id] = set()
                    class_availability[classe_id].add(slot_id)

    return class_availability


def read_formatrici_availability() -> Dict[str, int]:
    """Legge disponibilità formatrici per slot."""
    formatrici_count = {}

    with open('data/output/formatrici_availability.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            count = sum(1 for col, val in row.items() if col != 'slot_id' and val != 'N')
            formatrici_count[slot_id] = count

    return formatrici_count


def read_classes_info() -> Dict[int, Dict]:
    """Legge informazioni sulle classi."""
    classes_info = {}
    with open('data/input/classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            classe_id = int(row['classe_id'])
            classes_info[classe_id] = {
                'nome': row['nome'],
                'scuola_id': int(row['scuola_id']),
            }
    return classes_info


def read_grouping_preferences() -> Dict[int, str]:
    """Legge accorpamenti preferenziali."""
    preferences = {}
    with open('data/input/classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            classe_id = int(row['classe_id'])
            pref = row.get('accorpamento_preferenziale', '').strip()
            if pref:
                preferences[classe_id] = pref
    return preferences


def build_lab6_model(
    lab6_classes: Dict[int, int],
    class_availability: Dict[int, Set[str]],
    formatrici_availability: Dict[str, int],
    previous_schedule: Dict
):
    """Costruisce e risolve il modello OR-Tools per Lab 6 con vincoli di consecutività."""

    model = cp_model.CpModel()

    # Leggi info classi per accorpamenti
    classes_info = read_classes_info()
    grouping_preferences = read_grouping_preferences()

    # Leggi num_formatrici Lab 4 e Lab 5 dai file
    lab4_formatrici = {}
    with open('data/output/calendario_lab4_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            num_form = row.get('num_formatrici', '0')
            try:
                lab4_formatrici[slot_id] = float(num_form) if num_form else 0
            except ValueError:
                lab4_formatrici[slot_id] = 0

    lab5_formatrici = {}
    with open('data/output/calendario_lab5_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            num_form = row.get('num_formatrici_lab5', '0')
            try:
                lab5_formatrici[slot_id] = float(num_form) if num_form else 0
            except ValueError:
                lab5_formatrici[slot_id] = 0

    # Lista di tutti gli slot
    all_slots = sorted(set(
        slot for slots in class_availability.values() for slot in slots
    ))

    # Limita alle prime 16 settimane
    relevant_slots = [s for s in all_slots if int(s.split('-')[0][1:]) < 16]

    print(f"Slot rilevanti: {len(relevant_slots)}")
    print(f"Classi Lab 6: {len(lab6_classes)}")

    # Crea mapping: slot_id -> week_num
    slot_to_week = {}
    for slot_id in relevant_slots:
        week = int(slot_id.split('-')[0][1:])
        slot_to_week[slot_id] = week

    # Crea mapping: week -> slots
    week_to_slots = {}
    for slot_id in relevant_slots:
        week = slot_to_week[slot_id]
        if week not in week_to_slots:
            week_to_slots[week] = []
        week_to_slots[week].append(slot_id)

    # === VARIABILI ===

    # meeting[classe_id, meeting_num, slot_id] = 1 se l'incontro Lab 6 è in quello slot
    meeting = {}

    # Trova l'ultima settimana di tutti i lab precedenti per ogni classe
    last_previous_lab_week = {}
    for classe_id, prev_meetings in previous_schedule.items():
        if prev_meetings:
            max_week = max(slot_to_week.get(slot_id, -1) for slot_id, _ in prev_meetings)
            last_previous_lab_week[classe_id] = max_week

    for classe_id, num_meetings in lab6_classes.items():
        for meeting_num in range(1, num_meetings + 1):
            for slot_id in relevant_slots:
                # Solo se la classe è disponibile
                if slot_id in class_availability.get(classe_id, set()):
                    slot_week = slot_to_week[slot_id]

                    # Lab 6 deve iniziare DOPO tutti i lab precedenti
                    if classe_id in last_previous_lab_week:
                        if slot_week <= last_previous_lab_week[classe_id]:
                            continue  # Salta questo slot

                    var_name = f"meeting_c{classe_id}_m{meeting_num}_s{slot_id}"
                    meeting[classe_id, meeting_num, slot_id] = model.NewBoolVar(var_name)

    # Variabili per accorpamenti
    grouped = {}

    for c1 in lab6_classes.keys():
        for c2 in lab6_classes.keys():
            if c1 >= c2:
                continue

            if classes_info[c1]['scuola_id'] != classes_info[c2]['scuola_id']:
                continue

            # Trova slot comuni dove entrambe sono disponibili (e validi temporalmente)
            common_slots = class_availability.get(c1, set()) & class_availability.get(c2, set())
            common_relevant = set()

            for slot_id in common_slots & set(relevant_slots):
                slot_week = slot_to_week[slot_id]

                # Verifica vincoli temporali per entrambe le classi
                valid_for_c1 = True
                valid_for_c2 = True

                if c1 in last_previous_lab_week:
                    if slot_week <= last_previous_lab_week[c1]:
                        valid_for_c1 = False

                if c2 in last_previous_lab_week:
                    if slot_week <= last_previous_lab_week[c2]:
                        valid_for_c2 = False

                if valid_for_c1 and valid_for_c2:
                    common_relevant.add(slot_id)

            if not common_relevant:
                continue

            # Per ogni numero di incontro (1, 2)
            for meeting_num in range(1, 3):
                for slot_id in common_relevant:
                    var_name = f"grouped_c{c1}_c{c2}_m{meeting_num}_s{slot_id}"
                    grouped[c1, c2, meeting_num, slot_id] = model.NewBoolVar(var_name)

    print(f"Variabili di accorpamento Lab 6: {len(grouped)}")

    # === VINCOLI HARD ===

    # H1: Ogni incontro Lab 6 deve essere schedulato esattamente una volta
    for classe_id, num_meetings in lab6_classes.items():
        for meeting_num in range(1, num_meetings + 1):
            slots_for_meeting = []
            for slot_id in relevant_slots:
                if (classe_id, meeting_num, slot_id) in meeting:
                    slots_for_meeting.append(meeting[classe_id, meeting_num, slot_id])

            if slots_for_meeting:
                model.Add(sum(slots_for_meeting) == 1)
            else:
                print(f"⚠️  Classe {classe_id} meeting {meeting_num}: nessuno slot disponibile")

    # H2: VINCOLO CONSECUTIVITÀ - I 2 incontri Lab 6 devono essere in settimane DIVERSE E CONSECUTIVE
    # Incontro 1 e Incontro 2 non possono essere nella stessa settimana
    for classe_id in lab6_classes.keys():
        for week in week_to_slots.keys():
            week_slots = week_to_slots[week]

            # Raccogli meeting 1 e meeting 2 in questa settimana
            meetings_in_week = []
            meeting1_in_week = []
            meeting2_in_week = []

            for slot_id in week_slots:
                if (classe_id, 1, slot_id) in meeting:
                    meeting1_in_week.append(meeting[classe_id, 1, slot_id])
                if (classe_id, 2, slot_id) in meeting:
                    meeting2_in_week.append(meeting[classe_id, 2, slot_id])

            # Non possono essere entrambi nella stessa settimana
            if meeting1_in_week and meeting2_in_week:
                model.Add(sum(meeting1_in_week) + sum(meeting2_in_week) <= 1)

    # H2b: VINCOLO ORDINE E CONSECUTIVITÀ - week(M2) = week(M1) + 1
    # Creiamo variabili intere per la settimana di ciascun incontro, poi forziamo M2 = M1 + 1
    for classe_id in lab6_classes.keys():
        # Crea variabile intera per la settimana dell'incontro 1 e 2
        week_m1 = model.NewIntVar(0, 15, f"week_m1_c{classe_id}")
        week_m2 = model.NewIntVar(0, 15, f"week_m2_c{classe_id}")

        # Collega week_m1 alle variabili booleane di meeting 1
        for slot_id in relevant_slots:
            if (classe_id, 1, slot_id) in meeting:
                slot_week = slot_to_week[slot_id]
                # Se meeting 1 è schedulato in questo slot, allora week_m1 = slot_week
                model.Add(week_m1 == slot_week).OnlyEnforceIf(meeting[classe_id, 1, slot_id])

        # Collega week_m2 alle variabili booleane di meeting 2
        for slot_id in relevant_slots:
            if (classe_id, 2, slot_id) in meeting:
                slot_week = slot_to_week[slot_id]
                # Se meeting 2 è schedulato in questo slot, allora week_m2 = slot_week
                model.Add(week_m2 == slot_week).OnlyEnforceIf(meeting[classe_id, 2, slot_id])

        # Vincolo: week_m2 = week_m1 + 1 (consecutività e ordine)
        model.Add(week_m2 == week_m1 + 1)

    # H3: Link accorpamenti a scheduling
    for (c1, c2, meeting_num, slot_id), group_var in grouped.items():
        if (c1, meeting_num, slot_id) in meeting and (c2, meeting_num, slot_id) in meeting:
            model.Add(meeting[c1, meeting_num, slot_id] == 1).OnlyEnforceIf(group_var)
            model.Add(meeting[c2, meeting_num, slot_id] == 1).OnlyEnforceIf(group_var)

    # H4: Max 1 accorpamento per classe per meeting
    for classe_id in lab6_classes.keys():
        for meeting_num in range(1, 3):
            for slot_id in relevant_slots:
                groupings_here = []
                for (c1, c2, m, s), group_var in grouped.items():
                    if m == meeting_num and s == slot_id:
                        if c1 == classe_id or c2 == classe_id:
                            groupings_here.append(group_var)

                if groupings_here:
                    model.Add(sum(groupings_here) <= 1)

    # H5: Vincolo formatrici disponibili (considerando Lab 4, Lab 5, e Lab 6 con accorpamenti)
    for slot_id in relevant_slots:
        num_available = formatrici_availability.get(slot_id, 0)

        # Lab 4 + Lab 5 trainer units (già moltiplicati per 2)
        prev_trainer_units = int((lab4_formatrici.get(slot_id, 0) + lab5_formatrici.get(slot_id, 0)) * 2)

        # Lab 6 con accorpamenti
        trainer_units_lab6 = []
        for classe_id in lab6_classes.keys():
            for meeting_num in range(1, 3):
                if (classe_id, meeting_num, slot_id) in meeting:
                    meet_var = meeting[classe_id, meeting_num, slot_id]

                    # Trova se è accorpata
                    is_grouped_vars = []
                    for (c1, c2, m, s), group_var in grouped.items():
                        if m == meeting_num and s == slot_id:
                            if c1 == classe_id or c2 == classe_id:
                                is_grouped_vars.append(group_var)

                    if is_grouped_vars:
                        contribution = model.NewIntVar(0, 2, f"contrib_c{classe_id}_m{meeting_num}_s{slot_id}")
                        model.Add(contribution == 2 * meet_var - sum(is_grouped_vars))
                        trainer_units_lab6.append(contribution)
                    else:
                        trainer_units_lab6.append(2 * meet_var)

        if trainer_units_lab6:
            model.Add(prev_trainer_units + sum(trainer_units_lab6) <= 2 * num_available)

    # === OBIETTIVO ===

    objective_terms = []

    # Obiettivo 1: MASSIMIZZA accorpamenti
    for (c1, c2, meeting_num, slot_id), group_var in grouped.items():
        is_preferential = False
        c1_pref = grouping_preferences.get(c1, '')
        c2_pref = grouping_preferences.get(c2, '')
        c1_name = classes_info[c1]['nome']
        c2_name = classes_info[c2]['nome']

        if c1_pref == c2_name or c2_pref == c1_name:
            is_preferential = True

        if is_preferential:
            objective_terms.append(200 * group_var)
        else:
            objective_terms.append(100 * group_var)

    # Obiettivo 2: Minimizza numero di slot utilizzati (concentra gli incontri)
    slots_used = []
    for slot_id in relevant_slots:
        slot_used = model.NewBoolVar(f"slot_used_{slot_id}")

        meetings_in_slot = []
        for classe_id in lab6_classes.keys():
            for meeting_num in range(1, 3):
                if (classe_id, meeting_num, slot_id) in meeting:
                    meetings_in_slot.append(meeting[classe_id, meeting_num, slot_id])

        if meetings_in_slot:
            model.Add(sum(meetings_in_slot) > 0).OnlyEnforceIf(slot_used)
            model.Add(sum(meetings_in_slot) == 0).OnlyEnforceIf(slot_used.Not())
            slots_used.append(slot_used)

    # Penalizza slot usati (peso 1)
    for slot_used_var in slots_used:
        objective_terms.append(-1 * slot_used_var)

    # Massimizza obiettivo
    if objective_terms:
        model.Maximize(sum(objective_terms))

    # === SOLVE ===

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0
    solver.parameters.num_search_workers = 4

    print("\n=== Risoluzione OR-Tools (Lab 6) ===")
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"✅ Soluzione trovata (status: {solver.StatusName(status)})")
        print(f"   Tempo: {solver.WallTime():.2f}s")
        print(f"   Valore obiettivo: {solver.ObjectiveValue()}")

        # Estrai soluzione
        lab6_schedule = {}
        lab6_groupings = {}

        for classe_id in lab6_classes.keys():
            lab6_schedule[classe_id] = []
            for meeting_num in range(1, 3):
                for slot_id in relevant_slots:
                    if (classe_id, meeting_num, slot_id) in meeting:
                        if solver.Value(meeting[classe_id, meeting_num, slot_id]) == 1:
                            lab6_schedule[classe_id].append((slot_id, meeting_num))

        # Estrai accorpamenti
        for (c1, c2, meeting_num, slot_id), group_var in grouped.items():
            if solver.Value(group_var) == 1:
                if slot_id not in lab6_groupings:
                    lab6_groupings[slot_id] = {}

                if c1 not in lab6_groupings[slot_id]:
                    lab6_groupings[slot_id][c1] = []
                if c2 not in lab6_groupings[slot_id]:
                    lab6_groupings[slot_id][c2] = []

                lab6_groupings[slot_id][c1].append(c2)
                lab6_groupings[slot_id][c2].append(c1)

        # Conta accorpamenti
        total_grouped = sum(len(v) for v in lab6_groupings.values())
        total_meetings = sum(len(v) for v in lab6_schedule.values())
        if total_meetings > 0:
            grouping_pct = (total_grouped / total_meetings) * 100
            print(f"   Accorpamenti Lab 6: {total_grouped}/{total_meetings} incontri ({grouping_pct:.1f}%)")

        # Conta slot utilizzati
        slots_with_lab6 = set(slot for meetings in lab6_schedule.values() for slot, _ in meetings)
        print(f"   Slot utilizzati: {len(slots_with_lab6)}")

        return lab6_schedule, lab6_groupings

    else:
        print(f"❌ Nessuna soluzione trovata (status: {solver.StatusName(status)})")
        return None, None


def write_lab6_calendar(
    lab6_schedule: Dict,
    lab6_groupings: Dict,
    lab6_classes: Dict[int, int],
    formatrici_availability: Dict[str, int]
):
    """Scrive il calendario Lab 6 con indicatori di accorpamento."""

    # Leggi struttura
    with open('data/output/class_availability.csv', 'r') as f:
        reader = csv.DictReader(f)
        class_columns = reader.fieldnames[1:]
        all_slots = []
        availability = {}

        for row in reader:
            slot_id = row['slot_id']
            all_slots.append(slot_id)
            availability[slot_id] = {}

            for col in class_columns:
                classe_id = int(col.split('-')[0])
                availability[slot_id][classe_id] = row[col] == 'S'

    # Crea mapping classe_id -> colonna
    cid_to_col = {}
    for col in class_columns:
        classe_id = int(col.split('-')[0])
        cid_to_col[classe_id] = col

    # Crea mapping: slot -> meetings
    slot_meetings_lab6 = {}
    for classe_id, meetings in lab6_schedule.items():
        for slot_id, meeting_num in meetings:
            if slot_id not in slot_meetings_lab6:
                slot_meetings_lab6[slot_id] = []
            slot_meetings_lab6[slot_id].append((classe_id, meeting_num))

    # Leggi num_formatrici Lab 4 e Lab 5
    lab4_formatrici = {}
    with open('data/output/calendario_lab4_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            num_form = row.get('num_formatrici', '0')
            try:
                lab4_formatrici[slot_id] = float(num_form) if num_form else 0
            except ValueError:
                lab4_formatrici[slot_id] = 0

    lab5_formatrici = {}
    with open('data/output/calendario_lab5_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            num_form = row.get('num_formatrici_lab5', '0')
            try:
                lab5_formatrici[slot_id] = float(num_form) if num_form else 0
            except ValueError:
                lab5_formatrici[slot_id] = 0

    # Scrivi calendario
    with open('data/output/calendario_lab6_ortools.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(['slot_id'] + class_columns + [
            'num_formatrici_lab6', 'num_formatrici_prev',
            'num_formatrici_totali', 'num_formatrici_disponibili'
        ])

        # Per ogni slot
        for slot_id in all_slots:
            row = [slot_id]

            # Per ogni classe
            for col in class_columns:
                classe_id = int(col.split('-')[0])

                # Trova Lab 6
                meeting_here = None
                if slot_id in slot_meetings_lab6:
                    for cid, mnum in slot_meetings_lab6[slot_id]:
                        if cid == classe_id:
                            meeting_here = mnum
                            break

                if meeting_here:
                    label = f"L6-{meeting_here}"

                    # Aggiungi indicatore accorpamento
                    if classe_id in lab6_groupings.get(slot_id, {}):
                        grouped_with = lab6_groupings[slot_id][classe_id]
                        grouped_cols = [cid_to_col[other_cid] for other_cid in grouped_with]
                        label = f"{label}/{'/'.join(grouped_cols)}"

                    row.append(label)
                elif availability[slot_id].get(classe_id, False):
                    row.append('-')
                else:
                    row.append('X')

            # Conta formatrici Lab 6 (considerando accorpamenti)
            classes_in_slot_lab6 = [cid for cid, _ in slot_meetings_lab6.get(slot_id, [])]
            grouped_classes_lab6 = set()

            for cid in classes_in_slot_lab6:
                if cid in lab6_groupings.get(slot_id, {}):
                    grouped_classes_lab6.add(cid)

            num_lab6 = 0.0
            for cid in classes_in_slot_lab6:
                if cid in grouped_classes_lab6:
                    num_lab6 += 0.5
                else:
                    num_lab6 += 1.0

            # Lab precedenti
            num_prev = lab4_formatrici.get(slot_id, 0) + lab5_formatrici.get(slot_id, 0)
            num_total = num_lab6 + num_prev
            num_avail = formatrici_availability.get(slot_id, 0)

            # Formatta
            if num_lab6 == int(num_lab6):
                num_lab6 = int(num_lab6)
            if num_total == int(num_total):
                num_total = int(num_total)

            row.extend([num_lab6, num_prev, num_total, num_avail])

            writer.writerow(row)

    print(f"✅ Calendario Lab 6 scritto in data/output/calendario_lab6_ortools.csv")


def main():
    print("=== Scheduler Lab 6 + Accorpamenti ===\n")

    # Leggi dati
    print("Caricamento dati...")
    previous_schedule = read_previous_labs_schedule()
    lab6_classes = read_lab6_classes()
    class_availability = read_class_availability()
    formatrici_availability = read_formatrici_availability()

    print(f"  - {len(lab6_classes)} classi devono fare Lab 6")
    print(f"  - {len(class_availability)} classi con disponibilità")

    # Costruisci e risolvi modello
    lab6_schedule, lab6_groupings = build_lab6_model(
        lab6_classes,
        class_availability,
        formatrici_availability,
        previous_schedule
    )

    if lab6_schedule:
        print("\n=== Schedulazione Lab 6 ===")

        # Verifica completamento
        complete = sum(1 for cid, meetings in lab6_schedule.items()
                      if len(meetings) == lab6_classes[cid])
        print(f"Classi complete: {complete}/{len(lab6_classes)}")

        # Verifica consecutività
        print("\n=== Verifica consecutività ===")
        for classe_id, meetings in lab6_schedule.items():
            if len(meetings) == 2:
                weeks = [int(slot.split('-')[0][1:]) for slot, _ in meetings]
                weeks.sort()
                distance = weeks[1] - weeks[0]
                if distance > 2:
                    print(f"⚠️  Classe {classe_id}: distanza {distance} settimane tra incontri")

        # Scrivi calendario
        write_lab6_calendar(lab6_schedule, lab6_groupings, lab6_classes, formatrici_availability)

        # Verifica overbooking
        print("\n=== Verifica vincoli ===")
        # TODO: implementare verifica overbooking completa

    else:
        print("\n⚠️  Impossibile trovare una soluzione fattibile")


if __name__ == '__main__':
    main()
