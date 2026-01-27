#!/usr/bin/env python3
"""
Genera un calendario unificato che combina Lab 4 e Lab 5.
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


def read_lab_schedule(filename: str, lab_prefix: str) -> Dict[str, Dict[int, str]]:
    """
    Legge un calendario laboratorio.
    Returns: dict mapping slot_id -> dict mapping classe_id -> label (es: "L4-1")
    """
    schedule = {}

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            slot_id = row['slot_id']
            schedule[slot_id] = {}

            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_disponibili',
                          'num_formatrici_lab5', 'num_formatrici_lab4', 'num_formatrici_totali']:
                    continue

                if val.startswith(lab_prefix):
                    classe_id = int(col.split('-')[0])
                    schedule[slot_id][classe_id] = val

    return schedule


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
    lab4_schedule = read_lab_schedule('data/output/calendario_lab4_ortools.csv', 'L4-')
    lab5_schedule = read_lab_schedule('data/output/calendario_lab5_ortools.csv', 'L5-')
    formatrici_availability = read_formatrici_availability()
    formatrici_budget_incontri = read_formatrici_budget()

    print(f"  - {len(all_slots)} slot")
    print(f"  - {len(class_columns)} classi")
    print(f"  - Lab 4: {sum(len(v) for v in lab4_schedule.values())} incontri")
    print(f"  - Lab 5: {sum(len(v) for v in lab5_schedule.values())} incontri")
    print(f"  - Budget formatrici: {formatrici_budget_incontri:.1f} incontri")

    # Genera calendario unificato
    print("\nGenerazione calendario...")

    # Traccia totali per riga finale
    total_formatrici_usate = 0

    with open('data/output/calendario_laboratori.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        header = ['slot_id'] + class_columns + [
            'num_formatrici_lab4',
            'num_formatrici_lab5',
            'num_formatrici_totali',
            'num_formatrici_disponibili'
        ]
        writer.writerow(header)

        # Per ogni slot
        for slot_id in all_slots:
            row = [slot_id]

            lab4_in_slot = lab4_schedule.get(slot_id, {})
            lab5_in_slot = lab5_schedule.get(slot_id, {})

            # Per ogni classe
            for col in class_columns:
                classe_id = int(col.split('-')[0])

                # Combina Lab 4 e Lab 5
                labels = []
                if classe_id in lab4_in_slot:
                    labels.append(lab4_in_slot[classe_id])
                if classe_id in lab5_in_slot:
                    labels.append(lab5_in_slot[classe_id])

                if labels:
                    # Se ha entrambi i lab, uniscili con "+"
                    row.append(' + '.join(labels))
                elif availability[slot_id].get(classe_id, False):
                    row.append('-')
                else:
                    row.append('X')

            # Conta formatrici
            num_lab4 = len(lab4_in_slot)
            num_lab5 = len(lab5_in_slot)
            num_total = num_lab4 + num_lab5
            num_avail = formatrici_availability.get(slot_id, 0)

            row.extend([num_lab4, num_lab5, num_total, num_avail])

            # Accumula totale
            total_formatrici_usate += num_total

            writer.writerow(row)

        # Riga finale TOTALE
        total_row = ['Totale'] + [''] * len(class_columns) + [
            '',  # num_formatrici_lab4 (vuoto)
            '',  # num_formatrici_lab5 (vuoto)
            total_formatrici_usate,  # num_formatrici_totali
            int(formatrici_budget_incontri)  # num_formatrici_disponibili
        ]
        writer.writerow(total_row)

    print(f"✅ Calendario unificato scritto in data/output/calendario_laboratori.csv")

    # Statistiche
    print("\n=== Statistiche ===")

    # Conta slot utilizzati
    slots_with_labs = set()
    for slot_id in all_slots:
        if lab4_schedule.get(slot_id) or lab5_schedule.get(slot_id):
            slots_with_labs.add(slot_id)

    # Conta slot con overbooking
    overbooking_count = 0
    for slot_id in all_slots:
        num_lab4 = len(lab4_schedule.get(slot_id, {}))
        num_lab5 = len(lab5_schedule.get(slot_id, {}))
        num_total = num_lab4 + num_lab5
        num_avail = formatrici_availability.get(slot_id, 0)

        if num_total > num_avail:
            overbooking_count += 1

    # Conta classi con entrambi i lab
    classes_with_both = set()
    for slot_id in all_slots:
        lab4_classes = set(lab4_schedule.get(slot_id, {}).keys())
        lab5_classes = set(lab5_schedule.get(slot_id, {}).keys())
        # Non conta nella stessa settimana, ma in generale
        classes_with_both.update(lab4_classes)

    # Conta effettivamente classi con entrambi
    all_lab4_classes = set()
    all_lab5_classes = set()
    for slot_id in all_slots:
        all_lab4_classes.update(lab4_schedule.get(slot_id, {}).keys())
        all_lab5_classes.update(lab5_schedule.get(slot_id, {}).keys())

    both = all_lab4_classes & all_lab5_classes

    print(f"Slot utilizzati: {len(slots_with_labs)}")
    print(f"Slot in overbooking: {overbooking_count}")
    print(f"Classi totali con Lab 4: {len(all_lab4_classes)}")
    print(f"Classi totali con Lab 5: {len(all_lab5_classes)}")
    print(f"Classi con entrambi i lab: {len(both)}")
    print(f"\n=== Budget formatrici ===")
    print(f"Incontri totali schedulati: {total_formatrici_usate}")
    print(f"Budget disponibile (incontri): {int(formatrici_budget_incontri)}")
    print(f"Margine: {int(formatrici_budget_incontri) - total_formatrici_usate} incontri")
    print(f"Utilizzo: {total_formatrici_usate / formatrici_budget_incontri * 100:.1f}%")

    # Verifica conflitti settimanali
    print("\n=== Verifica vincoli settimanali ===")
    week_conflicts = 0
    for classe_id in both:
        for week in range(16):
            has_lab4 = False
            has_lab5 = False

            for slot_id in all_slots:
                slot_week = int(slot_id.split('-')[0][1:])
                if slot_week == week:
                    if classe_id in lab4_schedule.get(slot_id, {}):
                        has_lab4 = True
                    if classe_id in lab5_schedule.get(slot_id, {}):
                        has_lab5 = True

            if has_lab4 and has_lab5:
                week_conflicts += 1
                print(f"⚠️  Classe {classe_id}: Lab 4 e Lab 5 in settimana {week}")

    if week_conflicts == 0:
        print("✅ Nessun conflitto Lab 4/5 nella stessa settimana")


if __name__ == '__main__':
    generate_unified_calendar()
