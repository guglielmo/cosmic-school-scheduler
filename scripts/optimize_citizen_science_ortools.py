#!/usr/bin/env python3
"""
Scheduler basato su OR-Tools per ottimizzare la distribuzione del laboratorio
Citizen Science rispettando i vincoli delle formatrici disponibili.

Parte dalla soluzione greedy in calendario_laboratori.csv e la ridistribuisce
per eliminare gli overbooking.
"""

import csv
from typing import Dict, List, Set, Tuple
from ortools.sat.python import cp_model


def read_existing_schedule() -> Tuple[Dict, Dict, Set]:
    """
    Legge il calendario esistente per capire quali incontri sono schedulati.
    Returns:
        - dict: {classe_id -> list of (slot_id, meeting_num)}
        - dict: {slot_id -> set of (classe_id, meeting_num)}
        - set: slot_ids con overbooking
    """
    class_schedule = {}
    slot_schedule = {}
    overbooking_slots = set()

    with open('data/output/calendario_lab4_greedy.csv', 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            slot_id = row['slot_id']
            slot_schedule[slot_id] = set()

            # Verifica overbooking
            num_used = row.get('num_formatrici', '0')
            num_avail = row.get('num_formatrici_disponibili', '0')

            if num_used and num_avail and num_used not in ['0', '']:
                if float(num_used) > int(num_avail):
                    overbooking_slots.add(slot_id)

            # Leggi incontri schedulati
            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_disponibili']:
                    continue

                if val.startswith('L4-'):
                    # Estrai classe_id dal formato "classe_id-scuola_id-nome"
                    classe_id = int(col.split('-')[0])

                    # Estrai meeting_num da "L4-X/..." o "L4-X"
                    meeting_num = int(val.split('/')[0].split('-')[1])

                    if classe_id not in class_schedule:
                        class_schedule[classe_id] = []
                    class_schedule[classe_id].append((slot_id, meeting_num))
                    slot_schedule[slot_id].add((classe_id, meeting_num))

    return class_schedule, slot_schedule, overbooking_slots


def read_lab_classes() -> Dict[int, int]:
    """Legge quanti incontri serve fare per ogni classe."""
    lab_classes = {}

    with open('data/input/laboratori_classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['laboratorio_id'] == '4':
                classe_id = int(row['classe_id'])
                dettagli = row.get('dettagli', '').lower()

                if 'solo 1 incontro' in dettagli:
                    num_meetings = 1
                elif 'solo 2 incontri' in dettagli:
                    num_meetings = 2
                else:
                    num_meetings = 5

                lab_classes[classe_id] = num_meetings

    return lab_classes


def read_class_availability() -> Dict[int, Set[str]]:
    """
    Legge disponibilità delle classi.
    Returns: dict mapping classe_id -> set of available slot_ids
    """
    class_availability = {}

    with open('data/output/class_availability.csv', 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            slot_id = row['slot_id']

            for col, val in row.items():
                if col != 'slot_id' and val == 'S':
                    # Estrai classe_id
                    classe_id = int(col.split('-')[0])

                    if classe_id not in class_availability:
                        class_availability[classe_id] = set()
                    class_availability[classe_id].add(slot_id)

    return class_availability


def read_formatrici_availability() -> Dict[str, int]:
    """
    Legge disponibilità formatrici per slot.
    Returns: dict mapping slot_id -> num formatrici disponibili
    """
    formatrici_count = {}

    with open('data/output/formatrici_availability.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            count = sum(1 for col, val in row.items() if col != 'slot_id' and val != 'N')
            formatrici_count[slot_id] = count

    return formatrici_count


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


def build_ortools_model(
    lab_classes: Dict[int, int],
    class_availability: Dict[int, Set[str]],
    formatrici_availability: Dict[str, int],
    existing_schedule: Dict,
    overbooking_slots: Set[str]
):
    """Costruisce e risolve il modello OR-Tools con ottimizzazione accorpamenti."""

    model = cp_model.CpModel()

    # Leggi info classi per accorpamenti
    classes_info = read_classes_info()
    grouping_preferences = read_grouping_preferences()

    # Lista di tutti gli slot (ordine cronologico)
    all_slots = sorted(set(
        slot for slots in class_availability.values() for slot in slots
    ))

    # Limita alle prime settimane (come scheduler greedy)
    relevant_slots = [s for s in all_slots if int(s.split('-')[0][1:]) < 12]

    print(f"Slot rilevanti: {len(relevant_slots)}")
    print(f"Slot in overbooking: {len(overbooking_slots)}")

    # === VARIABILI ===

    # meeting[classe_id, meeting_num, slot_id] = 1 se l'incontro è in quello slot
    meeting = {}

    for classe_id, num_meetings in lab_classes.items():
        for meeting_num in range(1, num_meetings + 1):
            for slot_id in relevant_slots:
                # Solo se la classe è disponibile
                if slot_id in class_availability.get(classe_id, set()):
                    var_name = f"meeting_c{classe_id}_m{meeting_num}_s{slot_id}"
                    meeting[classe_id, meeting_num, slot_id] = model.NewBoolVar(var_name)

    # grouped[c1, c2, meeting_num, slot_id] = 1 se le due classi sono accorpate per questo incontro
    grouped = {}

    # Crea variabili di accorpamento per coppie valide
    for c1 in lab_classes.keys():
        for c2 in lab_classes.keys():
            if c1 >= c2:  # Solo coppie uniche
                continue

            # Verifica che siano della stessa scuola
            if classes_info[c1]['scuola_id'] != classes_info[c2]['scuola_id']:
                continue

            # Trova slot comuni dove entrambe sono disponibili
            common_slots = class_availability.get(c1, set()) & class_availability.get(c2, set())
            common_relevant = common_slots & set(relevant_slots)

            if not common_relevant:
                continue

            # Per ogni numero di incontro (1..5)
            max_meetings = min(lab_classes[c1], lab_classes[c2])
            for meeting_num in range(1, max_meetings + 1):
                for slot_id in common_relevant:
                    var_name = f"grouped_c{c1}_c{c2}_m{meeting_num}_s{slot_id}"
                    grouped[c1, c2, meeting_num, slot_id] = model.NewBoolVar(var_name)

    print(f"Variabili di accorpamento: {len(grouped)}")

    # === VINCOLI HARD ===

    # H1: Ogni incontro deve essere schedulato esattamente una volta
    for classe_id, num_meetings in lab_classes.items():
        for meeting_num in range(1, num_meetings + 1):
            slots_for_meeting = []
            for slot_id in relevant_slots:
                if (classe_id, meeting_num, slot_id) in meeting:
                    slots_for_meeting.append(meeting[classe_id, meeting_num, slot_id])

            if slots_for_meeting:
                model.Add(sum(slots_for_meeting) == 1)

    # H2: VINCOLO SETTIMANALE - Max 1 incontro Lab 4 per classe per settimana
    # NOTA: Questo vincolo copre solo Lab 4. Il vincolo globale "max 1 incontro TOTALE
    # per settimana" sarà applicato dall'optimizer Lab 5, che tiene conto sia di Lab 4
    # (già schedulato) che di Lab 5 (da schedulare).
    for classe_id, num_meetings in lab_classes.items():
        # Raggruppa slot per settimana
        slots_by_week = {}
        for slot_id in relevant_slots:
            week = int(slot_id.split('-')[0][1:])
            if week not in slots_by_week:
                slots_by_week[week] = []
            slots_by_week[week].append(slot_id)

        # Per ogni settimana, max 1 incontro Lab 4
        for week, week_slots in slots_by_week.items():
            meetings_this_week = []
            for meeting_num in range(1, num_meetings + 1):
                for slot_id in week_slots:
                    if (classe_id, meeting_num, slot_id) in meeting:
                        meetings_this_week.append(meeting[classe_id, meeting_num, slot_id])

            if meetings_this_week:
                model.Add(sum(meetings_this_week) <= 1)

    # H3: Link accorpamenti a scheduling
    # Se grouped[c1, c2, m, slot] = 1, allora entrambi meeting[c1, m, slot] e meeting[c2, m, slot] = 1
    for (c1, c2, meeting_num, slot_id), group_var in grouped.items():
        if (c1, meeting_num, slot_id) in meeting and (c2, meeting_num, slot_id) in meeting:
            # grouped => both meetings scheduled in this slot
            model.Add(meeting[c1, meeting_num, slot_id] == 1).OnlyEnforceIf(group_var)
            model.Add(meeting[c2, meeting_num, slot_id] == 1).OnlyEnforceIf(group_var)

            # If both meetings in slot, can optionally be grouped
            # (not forced, but allowed)

    # H4: Una classe può essere accorpata con al massimo 1 altra classe per meeting
    for classe_id in lab_classes.keys():
        for meeting_num in range(1, lab_classes[classe_id] + 1):
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

    # H5: Vincolo formatrici disponibili (considerando accorpamenti)
    # Per ogni slot, il numero di formatrici utilizzate <= disponibili
    # Ogni incontro singolo = 1 formatrice, ogni coppia accorpata = 1 formatrice totale
    for slot_id in relevant_slots:
        num_available = formatrici_availability.get(slot_id, 0)

        # Per ogni classe e meeting, conta:
        # - 1 se ha incontro e NON è accorpata
        # - 0.5 se ha incontro ed È accorpata (la coppia userà 1 formatrice totale)
        # Ma in CP-SAT non possiamo usare frazioni, quindi moltiplichiamo per 2

        # trainer_units[c, m] = 2 se meeting singolo, 1 se accorpato
        trainer_units = []

        classes_in_slot = []
        for classe_id, num_meetings in lab_classes.items():
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
                        # Se accorpata, contribuisce 1 unità (0.5 * 2), altrimenti 2 unità (1 * 2)
                        # contribution = meet_var * (2 - sum(is_grouped))
                        # Creiamo una variabile ausiliaria
                        contribution = model.NewIntVar(0, 2, f"contrib_c{classe_id}_m{meeting_num}_s{slot_id}")
                        # contribution = 2 * meet_var - sum(is_grouped_vars)
                        model.Add(contribution == 2 * meet_var - sum(is_grouped_vars))
                        trainer_units.append(contribution)
                    else:
                        # Nessun accorpamento possibile, contribuisce 2 unità se schedulato
                        trainer_units.append(2 * meet_var)

        if trainer_units:
            # Somma totale / 2 <= formatrici disponibili
            # Equivalente a: somma totale <= 2 * formatrici disponibili
            model.Add(sum(trainer_units) <= 2 * num_available)

    # === OBIETTIVO ===

    objective_terms = []

    # Obiettivo 1: MASSIMIZZA accorpamenti (peso alto)
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

    # Obiettivo 2: MINIMIZZA settimana massima per classe (finire prima)
    # Crea variabili per settimana massima di ogni classe
    max_week = {}
    slot_to_week = {}
    for slot_id in relevant_slots:
        week = int(slot_id.split('-')[0][1:])
        slot_to_week[slot_id] = week

    for classe_id, num_meetings in lab_classes.items():
        max_week[classe_id] = model.NewIntVar(0, 15, f"max_week_c{classe_id}")

        # max_week >= settimana di ogni incontro
        for meeting_num in range(1, num_meetings + 1):
            for slot_id in relevant_slots:
                if (classe_id, meeting_num, slot_id) in meeting:
                    week = slot_to_week[slot_id]
                    # Se questo meeting è schedulato qui, max_week >= week
                    model.Add(max_week[classe_id] >= week).OnlyEnforceIf(
                        meeting[classe_id, meeting_num, slot_id]
                    )

        # Penalizza settimane alte (peso medio-basso, inferiore ad accorpamenti)
        objective_terms.append(-10 * max_week[classe_id])

    # Obiettivo 3: Minimizza modifiche dalla soluzione greedy (peso basso)
    # Solo per slot NON in overbooking
    for classe_id, meetings in existing_schedule.items():
        for slot_id, meeting_num in meetings:
            if slot_id not in overbooking_slots:
                if (classe_id, meeting_num, slot_id) in meeting:
                    # Premio per mantenere: +1 se manteniamo
                    objective_terms.append(1 * meeting[classe_id, meeting_num, slot_id])

    # Massimizza obiettivo totale
    if objective_terms:
        model.Maximize(sum(objective_terms))

    # === SOLVE ===

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0  # Più tempo per trovare buoni accorpamenti
    solver.parameters.num_search_workers = 4

    print("\n=== Risoluzione OR-Tools ===")
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"✅ Soluzione trovata (status: {solver.StatusName(status)})")
        print(f"   Tempo: {solver.WallTime():.2f}s")
        print(f"   Valore obiettivo: {solver.ObjectiveValue()}")

        # Estrai soluzione - schedule e groupings
        new_schedule = {}
        new_groupings = {}  # slot_id -> {classe_id -> [other_classe_ids]}

        for classe_id, num_meetings in lab_classes.items():
            new_schedule[classe_id] = []
            for meeting_num in range(1, num_meetings + 1):
                for slot_id in relevant_slots:
                    if (classe_id, meeting_num, slot_id) in meeting:
                        if solver.Value(meeting[classe_id, meeting_num, slot_id]) == 1:
                            new_schedule[classe_id].append((slot_id, meeting_num))

        # Estrai accorpamenti
        for (c1, c2, meeting_num, slot_id), group_var in grouped.items():
            if solver.Value(group_var) == 1:
                if slot_id not in new_groupings:
                    new_groupings[slot_id] = {}

                if c1 not in new_groupings[slot_id]:
                    new_groupings[slot_id][c1] = []
                if c2 not in new_groupings[slot_id]:
                    new_groupings[slot_id][c2] = []

                new_groupings[slot_id][c1].append(c2)
                new_groupings[slot_id][c2].append(c1)

        # Conta accorpamenti
        total_grouped = sum(len(v) for v in new_groupings.values())
        total_meetings = sum(len(v) for v in new_schedule.values())
        if total_meetings > 0:
            grouping_pct = (total_grouped / total_meetings) * 100
            print(f"   Accorpamenti: {total_grouped}/{total_meetings} incontri ({grouping_pct:.1f}%)")

        return new_schedule, new_groupings

    else:
        print(f"❌ Nessuna soluzione trovata (status: {solver.StatusName(status)})")
        return None, None


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


def write_optimized_calendar(
    new_schedule: Dict,
    new_groupings: Dict,
    lab_classes: Dict[int, int],
    formatrici_availability: Dict[str, int]
):
    """Scrive il calendario ottimizzato con indicatori di accorpamento."""

    # Leggi struttura del calendario originale
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

    # Leggi info classi
    classes_info = read_classes_info()

    # Crea mapping: slot -> list of (classe_id, meeting_num)
    slot_meetings = {}
    for classe_id, meetings in new_schedule.items():
        for slot_id, meeting_num in meetings:
            if slot_id not in slot_meetings:
                slot_meetings[slot_id] = []
            slot_meetings[slot_id].append((classe_id, meeting_num))

    # Crea mapping classe_id -> colonna
    cid_to_col = {}
    for col in class_columns:
        classe_id = int(col.split('-')[0])
        cid_to_col[classe_id] = col

    # Scrivi calendario
    with open('data/output/calendario_lab4_ortools.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(['slot_id'] + class_columns + ['num_formatrici', 'num_formatrici_disponibili'])

        # Per ogni slot
        for slot_id in all_slots:
            row = [slot_id]

            # Per ogni classe
            for col in class_columns:
                classe_id = int(col.split('-')[0])

                # Trova se questa classe ha un incontro in questo slot
                meeting_here = None
                if slot_id in slot_meetings:
                    for cid, mnum in slot_meetings[slot_id]:
                        if cid == classe_id:
                            meeting_here = mnum
                            break

                if meeting_here:
                    label = f"L4-{meeting_here}"

                    # Aggiungi indicatore accorpamento
                    if classe_id in new_groupings.get(slot_id, {}):
                        grouped_with = new_groupings[slot_id][classe_id]
                        grouped_cols = [cid_to_col[other_cid] for other_cid in grouped_with]
                        label = f"{label}/{'/'.join(grouped_cols)}"

                    row.append(label)
                elif availability[slot_id].get(classe_id, False):
                    row.append('-')
                else:
                    row.append('X')

            # Conta formatrici necessarie (considerando accorpamenti)
            classes_in_slot = [cid for cid, _ in slot_meetings.get(slot_id, [])]
            grouped_classes = set()

            # Identifica classi accorpate
            for cid in classes_in_slot:
                if cid in new_groupings.get(slot_id, {}):
                    grouped_classes.add(cid)

            # Conta: accorpate = 0.5, singole = 1
            num_formatrici = 0.0
            for cid in classes_in_slot:
                if cid in grouped_classes:
                    num_formatrici += 0.5
                else:
                    num_formatrici += 1.0

            # Scrivi come intero se possibile
            if num_formatrici == int(num_formatrici):
                row.append(int(num_formatrici))
            else:
                row.append(num_formatrici)

            # Formatrici disponibili
            row.append(formatrici_availability.get(slot_id, 0))

            writer.writerow(row)

    print(f"✅ Calendario scritto in data/output/calendario_lab4_ortools.csv")


def main():
    print("=== Ottimizzazione Citizen Science con OR-Tools + Accorpamenti ===\n")

    # Leggi dati
    print("Caricamento dati...")
    existing_schedule, _, overbooking_slots = read_existing_schedule()
    lab_classes = read_lab_classes()
    class_availability = read_class_availability()
    formatrici_availability = read_formatrici_availability()

    print(f"  - {len(lab_classes)} classi")
    print(f"  - {len(existing_schedule)} classi già schedulate")
    print(f"  - {len(overbooking_slots)} slot in overbooking")

    # Costruisci e risolvi modello
    new_schedule, new_groupings = build_ortools_model(
        lab_classes,
        class_availability,
        formatrici_availability,
        existing_schedule,
        overbooking_slots
    )

    if new_schedule:
        print("\n=== Nuova schedulazione ===")

        # Verifica completamento
        complete = sum(1 for cid, meetings in new_schedule.items()
                      if len(meetings) == lab_classes[cid])
        print(f"Classi complete: {complete}/{len(lab_classes)}")

        # Scrivi calendario
        write_optimized_calendar(new_schedule, new_groupings, lab_classes, formatrici_availability)

        # Verifica overbooking e conta formatrici usate
        print("\n=== Verifica vincoli ===")
        overbooking_count = 0
        total_trainer_meetings = 0.0

        # Crea slot_meetings per verifica
        slot_meetings = {}
        for classe_id, meetings in new_schedule.items():
            for slot_id, meeting_num in meetings:
                if slot_id not in slot_meetings:
                    slot_meetings[slot_id] = []
                slot_meetings[slot_id].append(classe_id)

        for slot_id, classes_in_slot in slot_meetings.items():
            # Conta formatrici considerando accorpamenti
            grouped_classes = set()
            for cid in classes_in_slot:
                if cid in new_groupings.get(slot_id, {}):
                    grouped_classes.add(cid)

            num_formatrici = 0.0
            for cid in classes_in_slot:
                if cid in grouped_classes:
                    num_formatrici += 0.5
                else:
                    num_formatrici += 1.0

            total_trainer_meetings += num_formatrici
            num_avail = formatrici_availability.get(slot_id, 0)

            if num_formatrici > num_avail:
                overbooking_count += 1

        print(f"Slot in overbooking: {overbooking_count}")
        print(f"Formatrici-incontri totali: {total_trainer_meetings:.1f}")

    else:
        print("\n⚠️  Impossibile trovare una soluzione fattibile")
        print("     Suggerimenti:")
        print("     - Aumentare il numero di settimane (max_weeks)")
        print("     - Rilassare alcuni vincoli")
        print("     - Verificare disponibilità formatrici")


if __name__ == '__main__':
    main()
