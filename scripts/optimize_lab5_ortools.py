#!/usr/bin/env python3
"""
Scheduler OR-Tools per il laboratorio "Orientamento e Competenze" (Lab 5).

Vincoli:
- Tutti i vincoli del Lab 4 (disponibilità classi, formatrici, max 1 incontro/settimana)
- NUOVO: Una classe può avere solo incontri di UN laboratorio in una settimana
- NUOVO: Lab 5 inizia solo dopo che Lab 4 è completato per quella classe
"""

import csv
from typing import Dict, List, Set, Tuple
from ortools.sat.python import cp_model


def read_lab4_schedule() -> Dict[int, List[Tuple[str, int]]]:
    """
    Legge il calendario Lab 4 ottimizzato.
    Returns: dict mapping classe_id -> list of (slot_id, meeting_num)
    """
    lab4_schedule = {}

    with open('data/output/calendario_lab4_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            slot_id = row['slot_id']

            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_disponibili']:
                    continue

                if val.startswith('L4-'):
                    # Estrai classe_id
                    classe_id = int(col.split('-')[0])

                    # Gestisci formato con accorpamento: "L4-1/3-1-4B/5-1-5B" -> "L4-1"
                    lab_part = val.split('/')[0]  # Prende solo "L4-1"
                    meeting_num = int(lab_part.split('-')[1])  # Estrai "1" da "L4-1"

                    if classe_id not in lab4_schedule:
                        lab4_schedule[classe_id] = []
                    lab4_schedule[classe_id].append((slot_id, meeting_num))

    return lab4_schedule


def get_last_lab4_week(lab4_schedule: Dict) -> Dict[int, int]:
    """
    Per ogni classe, trova l'ultima settimana in cui ha Lab 4.
    Returns: dict mapping classe_id -> last_week_num
    """
    last_week = {}

    for classe_id, meetings in lab4_schedule.items():
        max_week = -1
        for slot_id, _ in meetings:
            week = int(slot_id.split('-')[0][1:])
            max_week = max(max_week, week)
        last_week[classe_id] = max_week

    return last_week


def read_lab5_classes() -> Dict[int, int]:
    """Legge quanti incontri Lab 5 servono per ogni classe."""
    lab5_classes = {}

    with open('data/input/laboratori_classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['laboratorio_id'] == '5':  # Orientamento e competenze
                classe_id = int(row['classe_id'])

                # Normalmente 2 incontri per Lab 5
                dettagli = row.get('dettagli', '').lower()
                if 'solo 1 incontro' in dettagli:
                    num_meetings = 1
                else:
                    num_meetings = 2  # Default per Lab 5

                lab5_classes[classe_id] = num_meetings

    return lab5_classes


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


def build_lab5_model(
    lab5_classes: Dict[int, int],
    class_availability: Dict[int, Set[str]],
    formatrici_availability: Dict[str, int],
    lab4_schedule: Dict,
    last_lab4_week: Dict[int, int]
):
    """Costruisce e risolve il modello OR-Tools per Lab 5 con accorpamenti."""

    model = cp_model.CpModel()

    # Leggi info classi per accorpamenti
    classes_info = read_classes_info()
    grouping_preferences = read_grouping_preferences()

    # Leggi num_formatrici Lab 4 dal file (già contato con accorpamenti)
    lab4_formatrici_per_slot = {}
    with open('data/output/calendario_lab4_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            num_form = row.get('num_formatrici', '0')
            try:
                lab4_formatrici_per_slot[slot_id] = float(num_form) if num_form else 0
            except ValueError:
                lab4_formatrici_per_slot[slot_id] = 0

    # Lista di tutti gli slot
    all_slots = sorted(set(
        slot for slots in class_availability.values() for slot in slots
    ))

    # Limita alle prime 16 settimane (periodo di scheduling)
    relevant_slots = [s for s in all_slots if int(s.split('-')[0][1:]) < 16]

    print(f"Slot rilevanti: {len(relevant_slots)}")
    print(f"Classi Lab 5: {len(lab5_classes)}")

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

    # meeting[classe_id, meeting_num, slot_id] = 1 se l'incontro Lab 5 è in quello slot
    meeting = {}

    for classe_id, num_meetings in lab5_classes.items():
        for meeting_num in range(1, num_meetings + 1):
            for slot_id in relevant_slots:
                # Solo se la classe è disponibile
                if slot_id in class_availability.get(classe_id, set()):
                    slot_week = slot_to_week[slot_id]

                    # Se la classe ha fatto Lab 4, Lab 5 deve iniziare DOPO
                    # Se NON ha fatto Lab 4, può iniziare quando vuole
                    if classe_id in lab4_schedule:
                        last_lab4 = last_lab4_week.get(classe_id, -1)
                        if slot_week <= last_lab4:
                            continue  # Salta questo slot

                    var_name = f"meeting_c{classe_id}_m{meeting_num}_s{slot_id}"
                    meeting[classe_id, meeting_num, slot_id] = model.NewBoolVar(var_name)

    # grouped[c1, c2, meeting_num, slot_id] = 1 se le due classi sono accorpate per questo incontro Lab 5
    grouped = {}

    # Crea variabili di accorpamento per coppie valide (stessa scuola, disponibilità comune)
    for c1 in lab5_classes.keys():
        for c2 in lab5_classes.keys():
            if c1 >= c2:  # Solo coppie uniche
                continue

            # Verifica che siano della stessa scuola
            if classes_info[c1]['scuola_id'] != classes_info[c2]['scuola_id']:
                continue

            # Trova slot comuni dove entrambe sono disponibili
            common_slots = class_availability.get(c1, set()) & class_availability.get(c2, set())
            common_relevant = set()

            # Filtra slot validi per entrambe le classi (considerando vincolo Lab 4)
            for slot_id in common_slots & set(relevant_slots):
                slot_week = slot_to_week[slot_id]

                # Verifica vincoli Lab 4 per entrambe le classi
                valid_for_c1 = True
                valid_for_c2 = True

                if c1 in lab4_schedule:
                    last_lab4_c1 = last_lab4_week.get(c1, -1)
                    if slot_week <= last_lab4_c1:
                        valid_for_c1 = False

                if c2 in lab4_schedule:
                    last_lab4_c2 = last_lab4_week.get(c2, -1)
                    if slot_week <= last_lab4_c2:
                        valid_for_c2 = False

                if valid_for_c1 and valid_for_c2:
                    common_relevant.add(slot_id)

            if not common_relevant:
                continue

            # Per ogni numero di incontro (1..2 tipicamente per Lab 5)
            max_meetings = min(lab5_classes[c1], lab5_classes[c2])
            for meeting_num in range(1, max_meetings + 1):
                for slot_id in common_relevant:
                    var_name = f"grouped_c{c1}_c{c2}_m{meeting_num}_s{slot_id}"
                    grouped[c1, c2, meeting_num, slot_id] = model.NewBoolVar(var_name)

    print(f"Variabili di accorpamento Lab 5: {len(grouped)}")

    # === VINCOLI HARD ===

    # H1: Ogni incontro Lab 5 deve essere schedulato esattamente una volta
    for classe_id, num_meetings in lab5_classes.items():
        for meeting_num in range(1, num_meetings + 1):
            slots_for_meeting = []
            for slot_id in relevant_slots:
                if (classe_id, meeting_num, slot_id) in meeting:
                    slots_for_meeting.append(meeting[classe_id, meeting_num, slot_id])

            if slots_for_meeting:
                model.Add(sum(slots_for_meeting) == 1)
            else:
                print(f"⚠️  Classe {classe_id} meeting {meeting_num}: nessuno slot disponibile dopo Lab 4")

    # H2: Max 1 incontro Lab 5 per classe per settimana
    for classe_id, num_meetings in lab5_classes.items():
        for week, week_slots in week_to_slots.items():
            meetings_this_week = []
            for meeting_num in range(1, num_meetings + 1):
                for slot_id in week_slots:
                    if (classe_id, meeting_num, slot_id) in meeting:
                        meetings_this_week.append(meeting[classe_id, meeting_num, slot_id])

            if meetings_this_week:
                model.Add(sum(meetings_this_week) <= 1)

    # H3: NUOVO - Una classe non può avere Lab 4 e Lab 5 nella stessa settimana
    # Questo vincolo si applica SOLO alle classi che hanno effettivamente fatto Lab 4
    class_has_lab4_in_week = {}
    for classe_id, lab4_meetings in lab4_schedule.items():
        for slot_id, _ in lab4_meetings:
            week = slot_to_week.get(slot_id, -1)
            if week >= 0:
                class_has_lab4_in_week[(classe_id, week)] = True

    # Per ogni classe che ha fatto Lab 4, se ha Lab 4 in una settimana, non può avere Lab 5
    for classe_id, num_meetings in lab5_classes.items():
        # Solo per classi che hanno fatto Lab 4
        if classe_id in lab4_schedule:
            for week, week_slots in week_to_slots.items():
                # Se questa classe ha Lab 4 in questa settimana
                if class_has_lab4_in_week.get((classe_id, week), False):
                    # Allora non può avere Lab 5
                    meetings_this_week = []
                    for meeting_num in range(1, num_meetings + 1):
                        for slot_id in week_slots:
                            if (classe_id, meeting_num, slot_id) in meeting:
                                meetings_this_week.append(meeting[classe_id, meeting_num, slot_id])

                    if meetings_this_week:
                        model.Add(sum(meetings_this_week) == 0)

    # H4: Link accorpamenti a scheduling
    # Se grouped[c1, c2, m, slot] = 1, allora entrambi meeting[c1, m, slot] e meeting[c2, m, slot] = 1
    for (c1, c2, meeting_num, slot_id), group_var in grouped.items():
        if (c1, meeting_num, slot_id) in meeting and (c2, meeting_num, slot_id) in meeting:
            # grouped => both meetings scheduled in this slot
            model.Add(meeting[c1, meeting_num, slot_id] == 1).OnlyEnforceIf(group_var)
            model.Add(meeting[c2, meeting_num, slot_id] == 1).OnlyEnforceIf(group_var)

    # H5: Una classe può essere accorpata con al massimo 1 altra classe per meeting
    for classe_id in lab5_classes.keys():
        for meeting_num in range(1, lab5_classes[classe_id] + 1):
            for slot_id in relevant_slots:
                # Conta con quante altre classi è accorpata in questo slot per questo meeting
                groupings_here = []
                for (c1, c2, m, s), group_var in grouped.items():
                    if m == meeting_num and s == slot_id:
                        if c1 == classe_id or c2 == classe_id:
                            groupings_here.append(group_var)

                if groupings_here:
                    # Può essere accorpata con al massimo 1 altra classe
                    model.Add(sum(groupings_here) <= 1)

    # H6: Vincolo formatrici disponibili (considerando accorpamenti Lab 5 E Lab 4 già schedulato)
    # Lab 4 è già ottimizzato con accorpamenti, quindi usiamo il num_formatrici effettivo
    for slot_id in relevant_slots:
        num_available = formatrici_availability.get(slot_id, 0)

        # Lab 4 trainer units (già moltiplicato per 2)
        lab4_trainer_units = int(lab4_formatrici_per_slot.get(slot_id, 0) * 2)

        # Conta Lab 5 con accorpamenti
        trainer_units_lab5 = []
        for classe_id, num_meetings in lab5_classes.items():
            for meeting_num in range(1, num_meetings + 1):
                if (classe_id, meeting_num, slot_id) in meeting:
                    meet_var = meeting[classe_id, meeting_num, slot_id]

                    # Trova se questa classe è accorpata
                    is_grouped_vars = []
                    for (c1, c2, m, s), group_var in grouped.items():
                        if m == meeting_num and s == slot_id:
                            if c1 == classe_id or c2 == classe_id:
                                is_grouped_vars.append(group_var)

                    if is_grouped_vars:
                        # contribution = 2 * meet_var - sum(is_grouped)
                        contribution = model.NewIntVar(0, 2, f"contrib_c{classe_id}_m{meeting_num}_s{slot_id}")
                        model.Add(contribution == 2 * meet_var - sum(is_grouped_vars))
                        trainer_units_lab5.append(contribution)
                    else:
                        # Nessun accorpamento possibile, contribuisce 2 unità se schedulato
                        trainer_units_lab5.append(2 * meet_var)

        if trainer_units_lab5:
            # Totale <= 2 * disponibili
            model.Add(lab4_trainer_units + sum(trainer_units_lab5) <= 2 * num_available)

    # === OBIETTIVO ===

    objective_terms = []

    # Obiettivo 1: MASSIMIZZA accorpamenti (peso molto alto)
    # Accorpamenti preferenziali hanno peso maggiore
    for (c1, c2, meeting_num, slot_id), group_var in grouped.items():
        # Verifica se è un accorpamento preferenziale
        is_preferential = False
        c1_pref = grouping_preferences.get(c1, '')
        c2_pref = grouping_preferences.get(c2, '')
        c1_name = classes_info[c1]['nome']
        c2_name = classes_info[c2]['nome']

        if c1_pref == c2_name or c2_pref == c1_name:
            is_preferential = True

        # Peso: 200 per preferenziali, 100 per stessa scuola
        if is_preferential:
            objective_terms.append(200 * group_var)
        else:
            objective_terms.append(100 * group_var)

    # Obiettivo 2: Minimizza slot utilizzati (peso basso)
    # Aiuta a concentrare gli incontri
    slots_used = []
    for slot_id in relevant_slots:
        # Variabile ausiliaria: slot_used[slot_id] = 1 se c'è almeno un Lab 5 in questo slot
        slot_used = model.NewBoolVar(f"slot_used_{slot_id}")

        meetings_in_slot = []
        for classe_id, num_meetings in lab5_classes.items():
            for meeting_num in range(1, num_meetings + 1):
                if (classe_id, meeting_num, slot_id) in meeting:
                    meetings_in_slot.append(meeting[classe_id, meeting_num, slot_id])

        if meetings_in_slot:
            # slot_used == 1 se sum(meetings) > 0
            model.Add(sum(meetings_in_slot) > 0).OnlyEnforceIf(slot_used)
            model.Add(sum(meetings_in_slot) == 0).OnlyEnforceIf(slot_used.Not())
            slots_used.append(slot_used)

    # Penalizza slot usati (peso 1)
    for slot_used_var in slots_used:
        objective_terms.append(-1 * slot_used_var)

    # Massimizza: accorpamenti (peso 100-200) - slot usati (peso 1)
    if objective_terms:
        model.Maximize(sum(objective_terms))

    # === SOLVE ===

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0
    solver.parameters.num_search_workers = 4

    print("\n=== Risoluzione OR-Tools (Lab 5) ===")
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"✅ Soluzione trovata (status: {solver.StatusName(status)})")
        print(f"   Tempo: {solver.WallTime():.2f}s")
        print(f"   Valore obiettivo: {solver.ObjectiveValue()}")

        # Estrai soluzione
        lab5_schedule = {}
        lab5_groupings = {}  # slot_id -> {classe_id -> [other_classe_ids]}

        for classe_id, num_meetings in lab5_classes.items():
            lab5_schedule[classe_id] = []
            for meeting_num in range(1, num_meetings + 1):
                for slot_id in relevant_slots:
                    if (classe_id, meeting_num, slot_id) in meeting:
                        if solver.Value(meeting[classe_id, meeting_num, slot_id]) == 1:
                            lab5_schedule[classe_id].append((slot_id, meeting_num))

        # Estrai accorpamenti
        for (c1, c2, meeting_num, slot_id), group_var in grouped.items():
            if solver.Value(group_var) == 1:
                if slot_id not in lab5_groupings:
                    lab5_groupings[slot_id] = {}

                if c1 not in lab5_groupings[slot_id]:
                    lab5_groupings[slot_id][c1] = []
                if c2 not in lab5_groupings[slot_id]:
                    lab5_groupings[slot_id][c2] = []

                lab5_groupings[slot_id][c1].append(c2)
                lab5_groupings[slot_id][c2].append(c1)

        # Conta accorpamenti
        total_grouped = sum(len(v) for v in lab5_groupings.values())
        total_meetings = sum(len(v) for v in lab5_schedule.values())
        if total_meetings > 0:
            grouping_pct = (total_grouped / total_meetings) * 100
            print(f"   Accorpamenti Lab 5: {total_grouped}/{total_meetings} incontri ({grouping_pct:.1f}%)")

        # Conta slot utilizzati
        slots_with_lab5 = set(slot for meetings in lab5_schedule.values() for slot, _ in meetings)
        print(f"   Slot utilizzati: {len(slots_with_lab5)}")

        return lab5_schedule, lab5_groupings

    else:
        print(f"❌ Nessuna soluzione trovata (status: {solver.StatusName(status)})")
        return None, None


def write_lab5_calendar(
    lab5_schedule: Dict,
    lab5_groupings: Dict,
    lab5_classes: Dict[int, int],
    formatrici_availability: Dict[str, int],
    lab4_schedule: Dict,
    lab4_groupings: Dict = None
):
    """Scrive il calendario Lab 5 con indicatori di accorpamento."""

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
    slot_meetings_lab5 = {}
    for classe_id, meetings in lab5_schedule.items():
        for slot_id, meeting_num in meetings:
            if slot_id not in slot_meetings_lab5:
                slot_meetings_lab5[slot_id] = []
            slot_meetings_lab5[slot_id].append((classe_id, meeting_num))

    # Conta anche Lab 4 per formatrici
    # Leggi num_formatrici effettivo da calendario_lab4_ortools.csv
    lab4_formatrici_per_slot = {}
    with open('data/output/calendario_lab4_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            num_form = row.get('num_formatrici', '0')
            try:
                lab4_formatrici_per_slot[slot_id] = float(num_form) if num_form else 0
            except ValueError:
                lab4_formatrici_per_slot[slot_id] = 0

    # Scrivi calendario
    with open('data/output/calendario_lab5_ortools.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(['slot_id'] + class_columns + [
            'num_formatrici_lab5', 'num_formatrici_lab4',
            'num_formatrici_totali', 'num_formatrici_disponibili'
        ])

        # Per ogni slot
        for slot_id in all_slots:
            row = [slot_id]

            # Per ogni classe
            for col in class_columns:
                classe_id = int(col.split('-')[0])

                # Trova Lab 5
                meeting_here = None
                if slot_id in slot_meetings_lab5:
                    for cid, mnum in slot_meetings_lab5[slot_id]:
                        if cid == classe_id:
                            meeting_here = mnum
                            break

                if meeting_here:
                    label = f"L5-{meeting_here}"

                    # Aggiungi indicatore accorpamento
                    if classe_id in lab5_groupings.get(slot_id, {}):
                        grouped_with = lab5_groupings[slot_id][classe_id]
                        grouped_cols = [cid_to_col[other_cid] for other_cid in grouped_with]
                        label = f"{label}/{'/'.join(grouped_cols)}"

                    row.append(label)
                elif availability[slot_id].get(classe_id, False):
                    row.append('-')
                else:
                    row.append('X')

            # Conta formatrici Lab 5 (considerando accorpamenti)
            classes_in_slot_lab5 = [cid for cid, _ in slot_meetings_lab5.get(slot_id, [])]
            grouped_classes_lab5 = set()

            # Identifica classi accorpate Lab 5
            for cid in classes_in_slot_lab5:
                if cid in lab5_groupings.get(slot_id, {}):
                    grouped_classes_lab5.add(cid)

            # Conta: accorpate = 0.5, singole = 1
            num_lab5 = 0.0
            for cid in classes_in_slot_lab5:
                if cid in grouped_classes_lab5:
                    num_lab5 += 0.5
                else:
                    num_lab5 += 1.0

            # Lab 4 già contato con accorpamenti
            num_lab4 = lab4_formatrici_per_slot.get(slot_id, 0)
            num_total = num_lab5 + num_lab4
            num_avail = formatrici_availability.get(slot_id, 0)

            # Formatta come intero se possibile
            if num_lab5 == int(num_lab5):
                num_lab5 = int(num_lab5)
            if num_total == int(num_total):
                num_total = int(num_total)

            row.extend([num_lab5, num_lab4, num_total, num_avail])

            writer.writerow(row)

    print(f"✅ Calendario Lab 5 scritto in data/output/calendario_lab5_ortools.csv")


def main():
    print("=== Scheduler Lab 5 (Orientamento e Competenze) + Accorpamenti ===\n")

    # Leggi dati
    print("Caricamento dati...")
    lab4_schedule = read_lab4_schedule()
    last_lab4_week = get_last_lab4_week(lab4_schedule)
    lab5_classes = read_lab5_classes()
    class_availability = read_class_availability()
    formatrici_availability = read_formatrici_availability()

    print(f"  - {len(lab4_schedule)} classi hanno completato Lab 4")
    print(f"  - {len(lab5_classes)} classi devono fare Lab 5")
    print(f"  - {len(class_availability)} classi con disponibilità")

    # Costruisci e risolvi modello
    lab5_schedule, lab5_groupings = build_lab5_model(
        lab5_classes,
        class_availability,
        formatrici_availability,
        lab4_schedule,
        last_lab4_week
    )

    if lab5_schedule:
        print("\n=== Schedulazione Lab 5 ===")

        # Verifica completamento
        complete = sum(1 for cid, meetings in lab5_schedule.items()
                      if len(meetings) == lab5_classes[cid])
        print(f"Classi complete: {complete}/{len(lab5_classes)}")

        # Scrivi calendario
        write_lab5_calendar(lab5_schedule, lab5_groupings, lab5_classes, formatrici_availability, lab4_schedule)

        # Verifica overbooking e conta formatrici
        print("\n=== Verifica vincoli ===")
        overbooking_count = 0
        week_conflict_count = 0

        # Leggi num_formatrici Lab 4 dal file
        lab4_formatrici_per_slot = {}
        with open('data/output/calendario_lab4_ortools.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                slot_id = row['slot_id']
                num_form = row.get('num_formatrici', '0')
                try:
                    lab4_formatrici_per_slot[slot_id] = float(num_form) if num_form else 0
                except ValueError:
                    lab4_formatrici_per_slot[slot_id] = 0

        # Crea slot_meetings per Lab 5
        slot_meetings_lab5 = {}
        for classe_id, meetings in lab5_schedule.items():
            for slot_id, meeting_num in meetings:
                if slot_id not in slot_meetings_lab5:
                    slot_meetings_lab5[slot_id] = []
                slot_meetings_lab5[slot_id].append(classe_id)

        # Verifica overbooking formatrici
        total_lab5_trainer_meetings = 0.0
        for slot_id, classes_in_slot in slot_meetings_lab5.items():
            # Conta Lab 5 con accorpamenti
            grouped_classes = set()
            for cid in classes_in_slot:
                if cid in lab5_groupings.get(slot_id, {}):
                    grouped_classes.add(cid)

            num_lab5 = 0.0
            for cid in classes_in_slot:
                if cid in grouped_classes:
                    num_lab5 += 0.5
                else:
                    num_lab5 += 1.0

            total_lab5_trainer_meetings += num_lab5

            num_lab4 = lab4_formatrici_per_slot.get(slot_id, 0)
            total = num_lab5 + num_lab4
            avail = formatrici_availability.get(slot_id, 0)

            if total > avail:
                overbooking_count += 1

        # Verifica conflitti settimanali
        for classe_id in lab5_classes.keys():
            # Per ogni settimana
            for week in range(16):
                has_lab4 = any(int(s.split('-')[0][1:]) == week
                              for s, _ in lab4_schedule.get(classe_id, []))
                has_lab5 = any(int(s.split('-')[0][1:]) == week
                              for s, _ in lab5_schedule.get(classe_id, []))

                if has_lab4 and has_lab5:
                    week_conflict_count += 1
                    print(f"⚠️  Classe {classe_id} ha Lab 4 e Lab 5 in settimana {week}")

        print(f"Slot in overbooking: {overbooking_count}")
        print(f"Conflitti Lab 4/5 in stessa settimana: {week_conflict_count}")
        print(f"Formatrici-incontri Lab 5: {total_lab5_trainer_meetings:.1f}")

    else:
        print("\n⚠️  Impossibile trovare una soluzione fattibile")


if __name__ == '__main__':
    main()
