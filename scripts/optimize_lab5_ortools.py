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

    with open('data/output/calendario_laboratori_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            slot_id = row['slot_id']

            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_disponibili']:
                    continue

                if val.startswith('L4-'):
                    # Estrai classe_id
                    classe_id = int(col.split('-')[0])
                    meeting_num = int(val.split('-')[1])

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


def build_lab5_model(
    lab5_classes: Dict[int, int],
    class_availability: Dict[int, Set[str]],
    formatrici_availability: Dict[str, int],
    lab4_schedule: Dict,
    last_lab4_week: Dict[int, int]
):
    """Costruisce e risolve il modello OR-Tools per Lab 5."""

    model = cp_model.CpModel()

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

    # H4: Vincolo formatrici disponibili
    # Considera anche gli incontri Lab 4 già schedulati
    for slot_id in relevant_slots:
        num_available = formatrici_availability.get(slot_id, 0)

        # Conta Lab 4 già in questo slot
        lab4_in_slot = sum(1 for meetings in lab4_schedule.values()
                          for s, _ in meetings if s == slot_id)

        # Conta Lab 5 potenziali
        lab5_meetings = []
        for classe_id, num_meetings in lab5_classes.items():
            for meeting_num in range(1, num_meetings + 1):
                if (classe_id, meeting_num, slot_id) in meeting:
                    lab5_meetings.append(meeting[classe_id, meeting_num, slot_id])

        if lab5_meetings:
            # Totale <= disponibili
            model.Add(lab4_in_slot + sum(lab5_meetings) <= num_available)

    # === OBIETTIVO ===

    # Minimizza il numero di slot utilizzati (concentra gli incontri)
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

    # Obiettivo: minimizza slot utilizzati
    if slots_used:
        model.Minimize(sum(slots_used))

    # === SOLVE ===

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0
    solver.parameters.num_search_workers = 4

    print("\n=== Risoluzione OR-Tools (Lab 5) ===")
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"✅ Soluzione trovata (status: {solver.StatusName(status)})")
        print(f"   Tempo: {solver.WallTime():.2f}s")
        print(f"   Slot utilizzati: {int(solver.ObjectiveValue())}")

        # Estrai soluzione
        lab5_schedule = {}
        for classe_id, num_meetings in lab5_classes.items():
            lab5_schedule[classe_id] = []
            for meeting_num in range(1, num_meetings + 1):
                for slot_id in relevant_slots:
                    if (classe_id, meeting_num, slot_id) in meeting:
                        if solver.Value(meeting[classe_id, meeting_num, slot_id]) == 1:
                            lab5_schedule[classe_id].append((slot_id, meeting_num))

        return lab5_schedule

    else:
        print(f"❌ Nessuna soluzione trovata (status: {solver.StatusName(status)})")
        return None


def write_lab5_calendar(
    lab5_schedule: Dict,
    lab5_classes: Dict[int, int],
    formatrici_availability: Dict[str, int],
    lab4_schedule: Dict
):
    """Scrive il calendario Lab 5 (semplificato)."""

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

    # Crea mapping: slot -> meetings
    slot_meetings_lab5 = {}
    for classe_id, meetings in lab5_schedule.items():
        for slot_id, meeting_num in meetings:
            if slot_id not in slot_meetings_lab5:
                slot_meetings_lab5[slot_id] = []
            slot_meetings_lab5[slot_id].append((classe_id, meeting_num))

    # Conta anche Lab 4 per formatrici
    slot_meetings_lab4 = {}
    for classe_id, meetings in lab4_schedule.items():
        for slot_id, meeting_num in meetings:
            if slot_id not in slot_meetings_lab4:
                slot_meetings_lab4[slot_id] = []
            slot_meetings_lab4[slot_id].append((classe_id, meeting_num))

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
                    row.append(f"L5-{meeting_here}")
                elif availability[slot_id].get(classe_id, False):
                    row.append('-')
                else:
                    row.append('X')

            # Conta formatrici
            num_lab5 = len(slot_meetings_lab5.get(slot_id, []))
            num_lab4 = len(slot_meetings_lab4.get(slot_id, []))
            num_total = num_lab5 + num_lab4
            num_avail = formatrici_availability.get(slot_id, 0)

            row.extend([num_lab5, num_lab4, num_total, num_avail])

            writer.writerow(row)

    print(f"✅ Calendario Lab 5 scritto in data/output/calendario_lab5_ortools.csv")


def main():
    print("=== Scheduler Lab 5 (Orientamento e Competenze) ===\n")

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
    lab5_schedule = build_lab5_model(
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
        write_lab5_calendar(lab5_schedule, lab5_classes, formatrici_availability, lab4_schedule)

        # Verifica overbooking
        print("\n=== Verifica vincoli ===")
        overbooking_count = 0
        week_conflict_count = 0

        # Verifica overbooking formatrici
        for slot_id in formatrici_availability.keys():
            lab4_count = sum(1 for m in lab4_schedule.values() for s, _ in m if s == slot_id)
            lab5_count = sum(1 for m in lab5_schedule.values() for s, _ in m if s == slot_id)
            total = lab4_count + lab5_count
            avail = formatrici_availability[slot_id]

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

    else:
        print("\n⚠️  Impossibile trovare una soluzione fattibile")


if __name__ == '__main__':
    main()
