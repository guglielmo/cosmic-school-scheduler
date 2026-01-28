#!/usr/bin/env python3
"""
Genera un calendario unificato che combina Lab 4, 5, 7, 8 e 9.
Legge i calendari ottimizzati OR-Tools e li unisce in un unico file.
"""

import csv
from typing import Dict, Set


def read_class_availability():
    """Legge la disponibilità base delle classi."""
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

    return class_columns, all_slots, availability


def read_lab_schedule(filename: str, lab_prefix: str, formatrici_col: str):
    """
    Legge un calendario laboratorio.
    Args:
        filename: path al file CSV
        lab_prefix: prefisso del laboratorio (es: "L4-")
        formatrici_col: nome della colonna num_formatrici da leggere
    Returns:
        - schedule: dict mapping slot_id -> dict mapping classe_id -> label (es: "L4-1")
        - formatrici_count: dict mapping slot_id -> num formatrici (float, considera accorpamenti)
    """
    schedule = {}
    formatrici_count = {}

    try:
        f = open(filename, 'r')
    except FileNotFoundError:
        # File non esiste, ritorna dizionari vuoti
        return schedule, formatrici_count

    with f:
        reader = csv.DictReader(f)

        for row in reader:
            slot_id = row['slot_id']
            schedule[slot_id] = {}

            # Leggi num_formatrici dalla colonna specificata (già calcolato correttamente con accorpamenti)
            num_form = row.get(formatrici_col, '0')
            try:
                formatrici_count[slot_id] = float(num_form) if num_form else 0
            except (ValueError, KeyError):
                formatrici_count[slot_id] = 0

            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_disponibili',
                          'num_formatrici_lab5', 'num_formatrici_lab4', 'num_formatrici_lab7',
                          'num_formatrici_lab8', 'num_formatrici_lab9', 'num_formatrici_lab8_lab9',
                          'num_formatrici_prev', 'num_formatrici_totali']:
                    continue

                if val and val.startswith(lab_prefix):
                    classe_id = int(col.split('-')[0])
                    schedule[slot_id][classe_id] = val

    return schedule, formatrici_count


def read_formatrici_availability():
    """Legge disponibilità formatrici."""
    formatrici_count = {}

    with open('data/output/formatrici_availability.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            slot_id = row['slot_id']
            count = sum(1 for col, val in row.items() if col != 'slot_id' and val != 'N')
            formatrici_count[slot_id] = count

    return formatrici_count


def read_formatrici_budget():
    """
    Legge il budget ore delle formatrici.
    Returns: budget totale disponibile in termini di incontri (ore / 2)
    """
    total_hours = 0

    with open('data/input/formatrici.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ore_generali = int(row.get('ore_generali', 0))
            total_hours += ore_generali

    # Ogni incontro è di 2 ore
    return total_hours / 2


def generate_unified_calendar():
    """Genera il calendario unificato."""
    print("=== Generazione calendario unificato ===\n")

    # Leggi dati
    print("Caricamento dati...")
    class_columns, all_slots, availability = read_class_availability()
    lab4_schedule, lab4_formatrici = read_lab_schedule('data/output/calendario_lab4_ortools.csv', 'L4-', 'num_formatrici')
    lab5_schedule, lab5_formatrici = read_lab_schedule('data/output/calendario_lab5_ortools.csv', 'L5-', 'num_formatrici_lab5')
    lab7_schedule, lab7_formatrici = read_lab_schedule('data/output/calendario_lab7_ortools.csv', 'L7-', 'num_formatrici_lab7')
    lab8_schedule, lab8_formatrici = read_lab_schedule('data/output/calendario_lab8_ortools.csv', 'L8-', 'num_formatrici_lab8')
    lab9_schedule, lab9_formatrici = read_lab_schedule('data/output/calendario_lab9_ortools.csv', 'L9-', 'num_formatrici_lab9')
    formatrici_availability = read_formatrici_availability()
    formatrici_budget_incontri = read_formatrici_budget()

    print(f"  - {len(all_slots)} slot")
    print(f"  - {len(class_columns)} classi")
    print(f"  - Lab 4: {sum(len(v) for v in lab4_schedule.values())} incontri")
    print(f"  - Lab 5: {sum(len(v) for v in lab5_schedule.values())} incontri")
    print(f"  - Lab 7: {sum(len(v) for v in lab7_schedule.values())} incontri")
    print(f"  - Lab 8: {sum(len(v) for v in lab8_schedule.values())} incontri")
    print(f"  - Lab 9: {sum(len(v) for v in lab9_schedule.values())} incontri")
    print(f"  - Budget formatrici: {formatrici_budget_incontri:.1f} incontri")

    # Genera calendario unificato
    print("\nGenerazione calendario...")

    # Traccia totali per riga finale
    total_formatrici_usate = 0.0

    with open('data/output/calendario_laboratori.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header (senza colonne separate Lab 4/Lab 5)
        header = ['slot_id'] + class_columns + [
            'num_formatrici',
            'num_formatrici_disponibili'
        ]
        writer.writerow(header)

        # Per ogni slot
        for slot_id in all_slots:
            row = [slot_id]

            lab4_in_slot = lab4_schedule.get(slot_id, {})
            lab5_in_slot = lab5_schedule.get(slot_id, {})
            lab7_in_slot = lab7_schedule.get(slot_id, {})
            lab8_in_slot = lab8_schedule.get(slot_id, {})
            lab9_in_slot = lab9_schedule.get(slot_id, {})

            # Per ogni classe
            for col in class_columns:
                classe_id = int(col.split('-')[0])

                # Combina Lab 4, 5, 7, 8, 9
                labels = []
                if classe_id in lab4_in_slot:
                    labels.append(lab4_in_slot[classe_id])
                if classe_id in lab5_in_slot:
                    labels.append(lab5_in_slot[classe_id])
                if classe_id in lab7_in_slot:
                    labels.append(lab7_in_slot[classe_id])
                if classe_id in lab9_in_slot:
                    labels.append(lab9_in_slot[classe_id])
                if classe_id in lab8_in_slot:
                    labels.append(lab8_in_slot[classe_id])

                if labels:
                    # Se ha più lab, uniscili con "+"
                    row.append(' + '.join(labels))
                elif availability[slot_id].get(classe_id, False):
                    row.append('-')
                else:
                    row.append('X')

            # Conta formatrici (somma dei valori già corretti da tutti i lab)
            num_lab4 = lab4_formatrici.get(slot_id, 0)
            num_lab5 = lab5_formatrici.get(slot_id, 0)
            num_lab7 = lab7_formatrici.get(slot_id, 0)
            num_lab8 = lab8_formatrici.get(slot_id, 0)
            num_lab9 = lab9_formatrici.get(slot_id, 0)
            num_total = num_lab4 + num_lab5 + num_lab7 + num_lab8 + num_lab9
            num_avail = formatrici_availability.get(slot_id, 0)

            # Formatta come intero se possibile
            if num_total == int(num_total):
                num_total_display = int(num_total)
            else:
                num_total_display = num_total

            row.extend([num_total_display, num_avail])

            # Accumula totale
            total_formatrici_usate += num_total

            writer.writerow(row)

        # Riga finale TOTALE
        total_formatrici_display = int(total_formatrici_usate) if total_formatrici_usate == int(total_formatrici_usate) else total_formatrici_usate
        total_row = ['Totale'] + [''] * len(class_columns) + [
            total_formatrici_display,  # num_formatrici totale
            int(formatrici_budget_incontri)  # num_formatrici_disponibili
        ]
        writer.writerow(total_row)

    print(f"✅ Calendario unificato scritto in data/output/calendario_laboratori.csv")

    # Statistiche
    print("\n=== Statistiche ===")

    # Conta slot utilizzati
    slots_with_labs = set()
    for slot_id in all_slots:
        if (lab4_schedule.get(slot_id) or lab5_schedule.get(slot_id) or
            lab7_schedule.get(slot_id) or lab8_schedule.get(slot_id) or
            lab9_schedule.get(slot_id)):
            slots_with_labs.add(slot_id)

    # Conta slot con overbooking (usando i valori corretti con accorpamenti)
    overbooking_count = 0
    for slot_id in all_slots:
        num_lab4 = lab4_formatrici.get(slot_id, 0)
        num_lab5 = lab5_formatrici.get(slot_id, 0)
        num_lab7 = lab7_formatrici.get(slot_id, 0)
        num_lab8 = lab8_formatrici.get(slot_id, 0)
        num_lab9 = lab9_formatrici.get(slot_id, 0)
        num_total = num_lab4 + num_lab5 + num_lab7 + num_lab8 + num_lab9
        num_avail = formatrici_availability.get(slot_id, 0)

        if num_total > num_avail:
            overbooking_count += 1

    # Conta classi per ogni lab
    all_lab4_classes = set()
    all_lab5_classes = set()
    all_lab7_classes = set()
    all_lab8_classes = set()
    all_lab9_classes = set()
    for slot_id in all_slots:
        all_lab4_classes.update(lab4_schedule.get(slot_id, {}).keys())
        all_lab5_classes.update(lab5_schedule.get(slot_id, {}).keys())
        all_lab7_classes.update(lab7_schedule.get(slot_id, {}).keys())
        all_lab8_classes.update(lab8_schedule.get(slot_id, {}).keys())
        all_lab9_classes.update(lab9_schedule.get(slot_id, {}).keys())

    print(f"Slot utilizzati: {len(slots_with_labs)}")
    print(f"Slot in overbooking: {overbooking_count}")
    print(f"Classi totali con Lab 4: {len(all_lab4_classes)}")
    print(f"Classi totali con Lab 5: {len(all_lab5_classes)}")
    print(f"Classi totali con Lab 7: {len(all_lab7_classes)}")
    print(f"Classi totali con Lab 8: {len(all_lab8_classes)}")
    print(f"Classi totali con Lab 9: {len(all_lab9_classes)}")
    print(f"\n=== Budget formatrici ===")
    print(f"Formatrici-incontri totali: {total_formatrici_usate:.1f}")
    print(f"Budget disponibile (incontri): {int(formatrici_budget_incontri)}")
    print(f"Margine: {formatrici_budget_incontri - total_formatrici_usate:.1f} incontri")
    print(f"Utilizzo: {total_formatrici_usate / formatrici_budget_incontri * 100:.1f}%")

    # Verifica conflitti settimanali (max 1 lab per settimana)
    print("\n=== Verifica vincoli settimanali ===")
    week_conflicts = []

    all_classes = (all_lab4_classes | all_lab5_classes | all_lab7_classes |
                   all_lab8_classes | all_lab9_classes)

    for classe_id in all_classes:
        for week in range(16):
            labs_in_week = []

            for slot_id in all_slots:
                slot_week = int(slot_id.split('-')[0][1:])
                if slot_week == week:
                    if classe_id in lab4_schedule.get(slot_id, {}):
                        labs_in_week.append('L4')
                    if classe_id in lab5_schedule.get(slot_id, {}):
                        labs_in_week.append('L5')
                    if classe_id in lab7_schedule.get(slot_id, {}):
                        labs_in_week.append('L7')
                    if classe_id in lab8_schedule.get(slot_id, {}):
                        labs_in_week.append('L8')
                    if classe_id in lab9_schedule.get(slot_id, {}):
                        labs_in_week.append('L9')

            # Rimuovi duplicati
            labs_in_week = list(set(labs_in_week))

            if len(labs_in_week) > 1:
                week_conflicts.append((classe_id, week, labs_in_week))
                print(f"⚠️  Classe {classe_id}: {', '.join(labs_in_week)} in settimana {week}")

    if len(week_conflicts) == 0:
        print("✅ Nessun conflitto: max 1 lab per settimana rispettato")


if __name__ == '__main__':
    generate_unified_calendar()
