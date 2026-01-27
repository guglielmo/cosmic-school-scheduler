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
    """Costruisce e risolve il modello OR-Tools."""

    model = cp_model.CpModel()

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

    # grouped[c1, c2, slot_id] = 1 se le due classi sono accorpate in quello slot
    grouped = {}

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

    # H2: Una classe può avere al massimo 1 incontro per settimana
    for classe_id, num_meetings in lab_classes.items():
        # Raggruppa slot per settimana
        slots_by_week = {}
        for slot_id in relevant_slots:
            week = int(slot_id.split('-')[0][1:])
            if week not in slots_by_week:
                slots_by_week[week] = []
            slots_by_week[week].append(slot_id)

        # Per ogni settimana
        for week, week_slots in slots_by_week.items():
            meetings_this_week = []
            for meeting_num in range(1, num_meetings + 1):
                for slot_id in week_slots:
                    if (classe_id, meeting_num, slot_id) in meeting:
                        meetings_this_week.append(meeting[classe_id, meeting_num, slot_id])

            if meetings_this_week:
                model.Add(sum(meetings_this_week) <= 1)

    # H3: Vincolo formatrici disponibili
    # Per ogni slot, il numero di formatrici utilizzate <= disponibili
    # (assumendo che ogni incontro usi 1 formatrice, accorpamenti ridurranno dopo)
    for slot_id in relevant_slots:
        num_available = formatrici_availability.get(slot_id, 0)

        # Conta quante classi hanno un incontro in questo slot
        meetings_in_slot = []
        for classe_id, num_meetings in lab_classes.items():
            for meeting_num in range(1, num_meetings + 1):
                if (classe_id, meeting_num, slot_id) in meeting:
                    meetings_in_slot.append(meeting[classe_id, meeting_num, slot_id])

        if meetings_in_slot:
            # Per ora vincolo conservativo: non più incontri che formatrici
            # TODO: considerare accorpamenti
            model.Add(sum(meetings_in_slot) <= num_available)

    # === OBIETTIVO ===

    # Minimizza il cambiamento rispetto alla soluzione esistente
    # per gli slot NON in overbooking
    changes = []

    for classe_id, meetings in existing_schedule.items():
        for slot_id, meeting_num in meetings:
            if slot_id not in overbooking_slots:
                # Se questo incontro era qui, premiamo mantenerlo
                if (classe_id, meeting_num, slot_id) in meeting:
                    # Penalizza il NON mantenerlo (inverso della variabile)
                    changes.append(1 - meeting[classe_id, meeting_num, slot_id])

    # Obiettivo: minimizza le modifiche
    if changes:
        model.Minimize(sum(changes))

    # === SOLVE ===

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.num_search_workers = 4

    print("\n=== Risoluzione OR-Tools ===")
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"✅ Soluzione trovata (status: {solver.StatusName(status)})")
        print(f"   Tempo: {solver.WallTime():.2f}s")
        print(f"   Modifiche dalla soluzione greedy: {solver.ObjectiveValue()}")

        # Estrai soluzione
        new_schedule = {}
        for classe_id, num_meetings in lab_classes.items():
            new_schedule[classe_id] = []
            for meeting_num in range(1, num_meetings + 1):
                for slot_id in relevant_slots:
                    if (classe_id, meeting_num, slot_id) in meeting:
                        if solver.Value(meeting[classe_id, meeting_num, slot_id]) == 1:
                            new_schedule[classe_id].append((slot_id, meeting_num))

        return new_schedule

    else:
        print(f"❌ Nessuna soluzione trovata (status: {solver.StatusName(status)})")
        return None


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
    lab_classes: Dict[int, int],
    formatrici_availability: Dict[str, int]
):
    """Scrive il calendario ottimizzato (semplificato, senza accorpamenti per ora)."""

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
                    row.append(f"L4-{meeting_here}")
                elif availability[slot_id].get(classe_id, False):
                    row.append('-')
                else:
                    row.append('X')

            # Conta formatrici necessarie (senza accorpamenti per ora)
            num_formatrici = len(slot_meetings.get(slot_id, []))
            row.append(num_formatrici)

            # Formatrici disponibili
            row.append(formatrici_availability.get(slot_id, 0))

            writer.writerow(row)

    print(f"✅ Calendario scritto in data/output/calendario_lab4_ortools.csv")


def main():
    print("=== Ottimizzazione Citizen Science con OR-Tools ===\n")

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
    new_schedule = build_ortools_model(
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
        write_optimized_calendar(new_schedule, lab_classes, formatrici_availability)

        # Verifica overbooking
        print("\n=== Verifica vincoli ===")
        overbooking_count = 0
        for slot_id in formatrici_availability.keys():
            if slot_id in new_schedule or any(slot_id in sched for sched in new_schedule.values()):
                # Conta incontri in questo slot
                num_meetings = sum(1 for meetings in new_schedule.values()
                                  for s, _ in meetings if s == slot_id)
                num_avail = formatrici_availability[slot_id]

                if num_meetings > num_avail:
                    overbooking_count += 1

        print(f"Slot in overbooking: {overbooking_count}")

    else:
        print("\n⚠️  Impossibile trovare una soluzione fattibile")
        print("     Suggerimenti:")
        print("     - Aumentare il numero di settimane (max_weeks)")
        print("     - Rilassare alcuni vincoli")
        print("     - Verificare disponibilità formatrici")


if __name__ == '__main__':
    main()
