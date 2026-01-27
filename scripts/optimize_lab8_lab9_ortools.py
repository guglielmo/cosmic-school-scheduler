#!/usr/bin/env python3
"""
Scheduler OR-Tools per Lab 9 e Lab 8.

Vincoli speciali:
- Lab 9 (se presente) viene PRIMA di Lab 8
- Lab 8 DEVE essere l'ultimo lab per ogni classe
- Le classi quinte hanno priorità (finiscono prima)
- Entrambi hanno 1 incontro
"""

import csv
from typing import Dict, List, Set, Tuple
from ortools.sat.python import cp_model


def read_previous_labs_schedule() -> Dict[int, List[Tuple[str, str]]]:
    """Legge i calendari Lab 4, 5, 7."""
    schedule = {}

    # Lab 4
    with open('data/output/calendario_lab4_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            if slot_id == 'Totale':
                continue

            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_disponibili']:
                    continue

                if val and val.startswith('L4-'):
                    classe_id = int(col.split('-')[0])
                    if classe_id not in schedule:
                        schedule[classe_id] = []
                    schedule[classe_id].append((slot_id, 'L4'))

    # Lab 5
    with open('data/output/calendario_lab5_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            if slot_id == 'Totale':
                continue

            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici_lab5', 'num_formatrici_lab4',
                          'num_formatrici_totali', 'num_formatrici_disponibili']:
                    continue

                if val and val.startswith('L5-'):
                    classe_id = int(col.split('-')[0])
                    if classe_id not in schedule:
                        schedule[classe_id] = []
                    schedule[classe_id].append((slot_id, 'L5'))

    # Lab 7
    with open('data/output/calendario_lab7_ortools.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            if slot_id == 'Totale':
                continue

            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici_lab7', 'num_formatrici_prev',
                          'num_formatrici_totali', 'num_formatrici_disponibili']:
                    continue

                if val and val.startswith('L7-'):
                    classe_id = int(col.split('-')[0])
                    if classe_id not in schedule:
                        schedule[classe_id] = []
                    schedule[classe_id].append((slot_id, 'L7'))

    return schedule


def read_lab_classes() -> Tuple[Set[int], Set[int]]:
    """
    Legge le classi che devono fare Lab 8 e Lab 9.
    Returns: (lab8_classes, lab9_classes)
    """
    lab8_classes = set()
    lab9_classes = set()

    with open('data/input/laboratori_classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lab_id = int(row['laboratorio_id'])
            classe_id = int(row['classe_id'])
            
            if lab_id == 8:
                lab8_classes.add(classe_id)
            elif lab_id == 9:
                lab9_classes.add(classe_id)

    return lab8_classes, lab9_classes


def read_class_info() -> Dict[int, Dict]:
    """Legge informazioni classi (nome, scuola, se è quinta)."""
    class_info = {}
    
    with open('data/input/classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            classe_id = int(row['classe_id'])
            nome = row['nome']
            is_quinta = nome.startswith('5')
            
            class_info[classe_id] = {
                'nome': nome,
                'scuola_id': int(row['scuola_id']),
                'is_quinta': is_quinta
            }

    return class_info


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
    formatrici_availability = {}

    with open('data/output/formatrici_availability.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            count = sum(1 for col, val in row.items() if col != 'slot_id' and val != 'N')
            formatrici_availability[slot_id] = count

    return formatrici_availability


def build_lab8_lab9_model(
    lab8_classes: Set[int],
    lab9_classes: Set[int],
    class_availability: Dict[int, Set[str]],
    formatrici_availability: Dict[str, int],
    previous_schedule: Dict,
    class_info: Dict
):
    """Costruisce e risolve il modello OR-Tools per Lab 9 e Lab 8."""

    model = cp_model.CpModel()

    # Trova ultima settimana di lab precedenti per ogni classe
    last_previous_lab_week = {}
    slot_to_week = {}

    all_slots = sorted(set(
        slot for slots in class_availability.values() for slot in slots
    ))

    for slot_id in all_slots:
        week = int(slot_id.split('-')[0][1:])
        slot_to_week[slot_id] = week

    for classe_id, prev_meetings in previous_schedule.items():
        if prev_meetings:
            max_week = max(slot_to_week.get(slot_id, -1) for slot_id, _ in prev_meetings)
            last_previous_lab_week[classe_id] = max_week

    relevant_slots = all_slots

    print(f"Slot rilevanti: {len(relevant_slots)}")
    print(f"Classi Lab 8: {len(lab8_classes)}")
    print(f"Classi Lab 9: {len(lab9_classes)}")
    print(f"Classi con entrambi: {len(lab8_classes & lab9_classes)}")

    # Variabili: meeting[classe_id, lab_id, slot_id] = 1 se schedulato
    # lab_id: 8 o 9
    meeting = {}

    # Per Lab 9 (viene prima)
    for classe_id in lab9_classes:
        for slot_id in relevant_slots:
            if slot_id in class_availability.get(classe_id, set()):
                slot_week = slot_to_week[slot_id]

                # Lab 9 deve iniziare DOPO tutti i lab precedenti
                if classe_id in last_previous_lab_week:
                    if slot_week <= last_previous_lab_week[classe_id]:
                        continue

                var_name = f"meeting_c{classe_id}_L9_s{slot_id}"
                meeting[classe_id, 9, slot_id] = model.NewBoolVar(var_name)

    # Per Lab 8 (viene dopo, ed è l'ultimo)
    for classe_id in lab8_classes:
        for slot_id in relevant_slots:
            if slot_id in class_availability.get(classe_id, set()):
                slot_week = slot_to_week[slot_id]

                # Lab 8 deve iniziare DOPO tutti i lab precedenti
                if classe_id in last_previous_lab_week:
                    if slot_week <= last_previous_lab_week[classe_id]:
                        continue

                var_name = f"meeting_c{classe_id}_L8_s{slot_id}"
                meeting[classe_id, 8, slot_id] = model.NewBoolVar(var_name)

    # Variabili per accorpamenti
    grouped = {}

    for lab_id in [8, 9]:
        classes_for_lab = lab8_classes if lab_id == 8 else lab9_classes
        
        for c1 in classes_for_lab:
            for c2 in classes_for_lab:
                if c1 >= c2:
                    continue

                if class_info[c1]['scuola_id'] != class_info[c2]['scuola_id']:
                    continue

                # Trova slot comuni dove entrambe sono disponibili
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

                for slot_id in common_relevant:
                    var_name = f"grouped_c{c1}_c{c2}_L{lab_id}_s{slot_id}"
                    grouped[c1, c2, lab_id, slot_id] = model.NewBoolVar(var_name)

    print(f"Variabili di accorpamento: {len(grouped)}")

    # === VINCOLI HARD ===

    # H1: Ogni classe deve fare Lab 8 esattamente una volta
    for classe_id in lab8_classes:
        slots_for_lab8 = []
        for slot_id in relevant_slots:
            if (classe_id, 8, slot_id) in meeting:
                slots_for_lab8.append(meeting[classe_id, 8, slot_id])

        if slots_for_lab8:
            model.Add(sum(slots_for_lab8) == 1)
        else:
            print(f"⚠️  Classe {classe_id}: nessuno slot disponibile per Lab 8")

    # H2: Ogni classe deve fare Lab 9 esattamente una volta (se richiesto)
    for classe_id in lab9_classes:
        slots_for_lab9 = []
        for slot_id in relevant_slots:
            if (classe_id, 9, slot_id) in meeting:
                slots_for_lab9.append(meeting[classe_id, 9, slot_id])

        if slots_for_lab9:
            model.Add(sum(slots_for_lab9) == 1)
        else:
            print(f"⚠️  Classe {classe_id}: nessuno slot disponibile per Lab 9")

    # H3: Lab 9 deve essere PRIMA di Lab 8 (per classi che hanno entrambi)
    both_labs = lab8_classes & lab9_classes
    for classe_id in both_labs:
        # Crea variabili intere per la settimana di Lab 9 e Lab 8
        week_lab9 = model.NewIntVar(0, 15, f"week_L9_c{classe_id}")
        week_lab8 = model.NewIntVar(0, 15, f"week_L8_c{classe_id}")

        # Collega week_lab9 alle variabili booleane
        for slot_id in relevant_slots:
            if (classe_id, 9, slot_id) in meeting:
                slot_week = slot_to_week[slot_id]
                model.Add(week_lab9 == slot_week).OnlyEnforceIf(meeting[classe_id, 9, slot_id])

        # Collega week_lab8 alle variabili booleane
        for slot_id in relevant_slots:
            if (classe_id, 8, slot_id) in meeting:
                slot_week = slot_to_week[slot_id]
                model.Add(week_lab8 == slot_week).OnlyEnforceIf(meeting[classe_id, 8, slot_id])

        # Lab 9 deve essere prima: week_lab9 < week_lab8
        model.Add(week_lab9 < week_lab8)

    # H4: Lab 8 deve essere l'ULTIMO lab per ogni classe
    # Crea variabile per settimana di Lab 8
    week_lab8_vars = {}
    for classe_id in lab8_classes:
        week_lab8_vars[classe_id] = model.NewIntVar(0, 15, f"week_L8_c{classe_id}")

        for slot_id in relevant_slots:
            if (classe_id, 8, slot_id) in meeting:
                slot_week = slot_to_week[slot_id]
                model.Add(week_lab8_vars[classe_id] == slot_week).OnlyEnforceIf(
                    meeting[classe_id, 8, slot_id]
                )

    # Per classi con Lab 9, Lab 9 deve essere prima di Lab 8 (già fatto in H3)
    # Ma Lab 8 deve essere dopo TUTTI gli altri lab già schedulati

    # H5: Link accorpamenti a scheduling
    for (c1, c2, lab_id, slot_id), group_var in grouped.items():
        if (c1, lab_id, slot_id) in meeting and (c2, lab_id, slot_id) in meeting:
            model.Add(meeting[c1, lab_id, slot_id] == 1).OnlyEnforceIf(group_var)
            model.Add(meeting[c2, lab_id, slot_id] == 1).OnlyEnforceIf(group_var)

    # H6: Max 1 accorpamento per classe per lab
    for classe_id in (lab8_classes | lab9_classes):
        for lab_id in [8, 9]:
            if lab_id == 8 and classe_id not in lab8_classes:
                continue
            if lab_id == 9 and classe_id not in lab9_classes:
                continue
            
            for slot_id in relevant_slots:
                groupings_here = []
                for (c1, c2, lid, sid), group_var in grouped.items():
                    if lid == lab_id and sid == slot_id:
                        if c1 == classe_id or c2 == classe_id:
                            groupings_here.append(group_var)

                if groupings_here:
                    model.Add(sum(groupings_here) <= 1)

    # H7: Vincolo formatrici disponibili
    # Leggi formatrici già usate
    prev_formatrici = {}

    with open('data/output/calendario_laboratori.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            if slot_id != 'Totale':
                num = row.get('num_formatrici', '0')
                try:
                    prev_formatrici[slot_id] = float(num) if num else 0
                except ValueError:
                    prev_formatrici[slot_id] = 0

    for slot_id in relevant_slots:
        num_available = formatrici_availability.get(slot_id, 0)

        # Formatrici già usate
        prev_units = int(prev_formatrici.get(slot_id, 0) * 2)

        # Lab 8 e Lab 9 con accorpamenti
        trainer_units = []
        
        for lab_id in [8, 9]:
            classes_for_lab = lab8_classes if lab_id == 8 else lab9_classes
            
            for classe_id in classes_for_lab:
                if (classe_id, lab_id, slot_id) in meeting:
                    meet_var = meeting[classe_id, lab_id, slot_id]

                    # Trova se questa classe è accorpata
                    is_grouped_vars = []
                    for (c1, c2, lid, sid), group_var in grouped.items():
                        if lid == lab_id and sid == slot_id:
                            if c1 == classe_id or c2 == classe_id:
                                is_grouped_vars.append(group_var)

                    if is_grouped_vars:
                        contribution = model.NewIntVar(0, 2, f"contrib_c{classe_id}_L{lab_id}_s{slot_id}")
                        model.Add(contribution == 2 * meet_var - sum(is_grouped_vars))
                        trainer_units.append(contribution)
                    else:
                        trainer_units.append(2 * meet_var)

        if trainer_units:
            model.Add(prev_units + sum(trainer_units) <= 2 * num_available)

    # === OBIETTIVO ===

    objective_terms = []

    # Obiettivo 1: MASSIMIZZA accorpamenti (peso alto)
    for (c1, c2, lab_id, slot_id), group_var in grouped.items():
        objective_terms.append(100 * group_var)

    # Obiettivo 2: MINIMIZZA settimana Lab 8 (finire prima, peso maggiore per quinte)
    for classe_id in lab8_classes:
        if classe_id in week_lab8_vars:
            is_quinta = class_info[classe_id]['is_quinta']
            peso = 50 if is_quinta else 10  # Quinte hanno peso 5x maggiore
            objective_terms.append(-peso * week_lab8_vars[classe_id])

    # Obiettivo 3: Minimizza slot utilizzati (peso molto basso)
    slots_used = []
    for slot_id in relevant_slots:
        slot_used = model.NewBoolVar(f"slot_used_{slot_id}")

        meetings_in_slot = []
        for classe_id in (lab8_classes | lab9_classes):
            for lab_id in [8, 9]:
                if (classe_id, lab_id, slot_id) in meeting:
                    meetings_in_slot.append(meeting[classe_id, lab_id, slot_id])

        if meetings_in_slot:
            model.Add(sum(meetings_in_slot) > 0).OnlyEnforceIf(slot_used)
            model.Add(sum(meetings_in_slot) == 0).OnlyEnforceIf(slot_used.Not())
            slots_used.append(slot_used)

    for slot_used_var in slots_used:
        objective_terms.append(-1 * slot_used_var)

    if objective_terms:
        model.Maximize(sum(objective_terms))

    # === SOLVE ===

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    solver.parameters.num_search_workers = 4

    print("\n=== Risoluzione OR-Tools (Lab 8 + Lab 9) ===")
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"✅ Soluzione trovata (status: {solver.StatusName(status)})")
        print(f"   Tempo: {solver.WallTime():.2f}s")
        print(f"   Valore obiettivo: {solver.ObjectiveValue()}")

        # Estrai soluzione
        lab8_schedule = {}
        lab9_schedule = {}
        new_groupings = {}

        for classe_id in lab8_classes:
            for slot_id in relevant_slots:
                if (classe_id, 8, slot_id) in meeting:
                    if solver.Value(meeting[classe_id, 8, slot_id]) == 1:
                        lab8_schedule[classe_id] = slot_id

        for classe_id in lab9_classes:
            for slot_id in relevant_slots:
                if (classe_id, 9, slot_id) in meeting:
                    if solver.Value(meeting[classe_id, 9, slot_id]) == 1:
                        lab9_schedule[classe_id] = slot_id

        # Estrai accorpamenti
        for (c1, c2, lab_id, slot_id), group_var in grouped.items():
            if solver.Value(group_var) == 1:
                if slot_id not in new_groupings:
                    new_groupings[slot_id] = {}

                if lab_id not in new_groupings[slot_id]:
                    new_groupings[slot_id][lab_id] = {}

                if c1 not in new_groupings[slot_id][lab_id]:
                    new_groupings[slot_id][lab_id][c1] = []
                if c2 not in new_groupings[slot_id][lab_id]:
                    new_groupings[slot_id][lab_id][c2] = []

                new_groupings[slot_id][lab_id][c1].append(c2)
                new_groupings[slot_id][lab_id][c2].append(c1)

        # Conta accorpamenti
        total_grouped_l8 = sum(len(g.get(8, {})) for g in new_groupings.values())
        total_grouped_l9 = sum(len(g.get(9, {})) for g in new_groupings.values())
        
        if len(lab8_schedule) > 0:
            grouping_pct_l8 = (total_grouped_l8 / len(lab8_schedule)) * 100
            print(f"   Accorpamenti Lab 8: {total_grouped_l8}/{len(lab8_schedule)} ({grouping_pct_l8:.1f}%)")
        
        if len(lab9_schedule) > 0:
            grouping_pct_l9 = (total_grouped_l9 / len(lab9_schedule)) * 100
            print(f"   Accorpamenti Lab 9: {total_grouped_l9}/{len(lab9_schedule)} ({grouping_pct_l9:.1f}%)")

        return lab8_schedule, lab9_schedule, new_groupings

    else:
        print(f"❌ Nessuna soluzione trovata (status: {solver.StatusName(status)})")
        return None, None, None


def write_calendars(
    lab8_schedule: Dict[int, str],
    lab9_schedule: Dict[int, str],
    new_groupings: Dict,
    lab8_classes: Set[int],
    lab9_classes: Set[int],
    class_availability: Dict[int, Set[str]],
    formatrici_availability: Dict[str, int],
    class_info: Dict
):
    """Scrive i calendari Lab 8 e Lab 9."""

    # Leggi struttura base
    with open('data/output/class_availability.csv', 'r') as f:
        reader = csv.DictReader(f)
        class_columns = reader.fieldnames[1:]
        all_slots = []

        for row in reader:
            all_slots.append(row['slot_id'])

    # Leggi formatrici già usate
    prev_formatrici = {}

    with open('data/output/calendario_laboratori.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            if slot_id != 'Totale':
                num = row.get('num_formatrici', '0')
                try:
                    prev_formatrici[slot_id] = float(num) if num else 0
                except ValueError:
                    prev_formatrici[slot_id] = 0

    # Crea mapping classe_id -> colonna
    cid_to_col = {}
    for col in class_columns:
        classe_id = int(col.split('-')[0])
        cid_to_col[classe_id] = col

    # Scrivi calendario combinato Lab 8 + Lab 9
    with open('data/output/calendario_lab8_lab9_ortools.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(['slot_id'] + class_columns + [
            'num_formatrici_lab8',
            'num_formatrici_lab9',
            'num_formatrici_lab8_lab9',
            'num_formatrici_prev',
            'num_formatrici_totali',
            'num_formatrici_disponibili'
        ])

        total_l8 = 0.0
        total_l9 = 0.0

        # Per ogni slot
        for slot_id in all_slots:
            row = [slot_id]

            for col in class_columns:
                classe_id = int(col.split('-')[0])

                labels = []
                
                # Lab 9
                if classe_id in lab9_schedule and lab9_schedule[classe_id] == slot_id:
                    label = "L9-1"
                    if slot_id in new_groupings and 9 in new_groupings[slot_id]:
                        if classe_id in new_groupings[slot_id][9]:
                            grouped_with = new_groupings[slot_id][9][classe_id]
                            grouped_cols = [cid_to_col[other_cid] for other_cid in grouped_with]
                            label = f"{label}/{'/'.join(grouped_cols)}"
                    labels.append(label)

                # Lab 8
                if classe_id in lab8_schedule and lab8_schedule[classe_id] == slot_id:
                    label = "L8-1"
                    if slot_id in new_groupings and 8 in new_groupings[slot_id]:
                        if classe_id in new_groupings[slot_id][8]:
                            grouped_with = new_groupings[slot_id][8][classe_id]
                            grouped_cols = [cid_to_col[other_cid] for other_cid in grouped_with]
                            label = f"{label}/{'/'.join(grouped_cols)}"
                    labels.append(label)

                if labels:
                    row.append(' + '.join(labels))
                elif slot_id in class_availability.get(classe_id, set()):
                    row.append('-')
                else:
                    row.append('X')

            # Conta formatrici
            classes_l8_in_slot = [cid for cid, sid in lab8_schedule.items() if sid == slot_id]
            classes_l9_in_slot = [cid for cid, sid in lab9_schedule.items() if sid == slot_id]

            grouped_l8 = set()
            grouped_l9 = set()

            if slot_id in new_groupings:
                if 8 in new_groupings[slot_id]:
                    grouped_l8.update(new_groupings[slot_id][8].keys())
                if 9 in new_groupings[slot_id]:
                    grouped_l9.update(new_groupings[slot_id][9].keys())

            num_l8 = sum(0.5 if cid in grouped_l8 else 1.0 for cid in classes_l8_in_slot)
            num_l9 = sum(0.5 if cid in grouped_l9 else 1.0 for cid in classes_l9_in_slot)
            num_combined = num_l8 + num_l9
            num_prev = prev_formatrici.get(slot_id, 0)
            num_total = num_combined + num_prev
            num_avail = formatrici_availability.get(slot_id, 0)

            total_l8 += num_l8
            total_l9 += num_l9

            # Formatta come intero se possibile
            for val in [num_l8, num_l9, num_combined, num_prev, num_total]:
                if val == int(val):
                    row.append(int(val))
                else:
                    row.append(val)
            
            row.append(num_avail)

            writer.writerow(row)

        # Riga totale
        total_row = ['Totale'] + [''] * len(class_columns)
        
        for val in [total_l8, total_l9, total_l8 + total_l9]:
            if val == int(val):
                total_row.append(int(val))
            else:
                total_row.append(val)
        
        total_row.extend(['', '', ''])  # prev, totali, disponibili
        writer.writerow(total_row)

    print(f"✅ Calendario Lab 8+9 scritto in data/output/calendario_lab8_lab9_ortools.csv")


def main():
    print("=== Scheduler Lab 8 + Lab 9 ===\n")

    # Leggi dati
    print("Caricamento dati...")
    previous_schedule = read_previous_labs_schedule()
    lab8_classes, lab9_classes = read_lab_classes()
    class_info = read_class_info()
    class_availability = read_class_availability()
    formatrici_availability = read_formatrici_availability()

    print(f"  - {len(lab8_classes)} classi devono fare Lab 8")
    print(f"  - {len(lab9_classes)} classi devono fare Lab 9")
    print(f"  - {sum(1 for c in lab8_classes if class_info[c]['is_quinta'])} classi quinte con Lab 8")
    print(f"  - {sum(1 for c in lab9_classes if class_info[c]['is_quinta'])} classi quinte con Lab 9")

    # Costruisci e risolvi modello
    lab8_schedule, lab9_schedule, new_groupings = build_lab8_lab9_model(
        lab8_classes,
        lab9_classes,
        class_availability,
        formatrici_availability,
        previous_schedule,
        class_info
    )

    if lab8_schedule is not None:
        print("\n=== Schedulazione ===")
        print(f"Lab 8 complete: {len(lab8_schedule)}/{len(lab8_classes)}")
        print(f"Lab 9 complete: {len(lab9_schedule)}/{len(lab9_classes)}")

        # Scrivi calendario
        write_calendars(
            lab8_schedule,
            lab9_schedule,
            new_groupings,
            lab8_classes,
            lab9_classes,
            class_availability,
            formatrici_availability,
            class_info
        )

        print("\n=== Verifica vincoli ===")

    else:
        print("\n⚠️  Impossibile trovare una soluzione fattibile")


if __name__ == '__main__':
    main()
