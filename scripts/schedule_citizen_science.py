#!/usr/bin/env python3
"""
Script per distribuire gli incontri del laboratorio Citizen Science (Lab 4)
nel calendario, minimizzando il numero di incontri totali attraverso accorpamenti.
"""

import csv
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Configurazione
LAB_ID = 4  # Citizen Science
LAB_NUM_MEETINGS = 5  # Numero di incontri per classe
MAX_TRAINERS = 4  # Numero massimo di formatrici disponibili
MAX_GROUP_SIZE = 2  # Max 2 classi per incontro


def read_lab_classes() -> Dict[int, Dict]:
    """Legge quali classi devono fare il lab 4 e i loro requisiti."""
    lab_classes = {}
    with open('data/input/laboratori_classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['laboratorio_id'] == str(LAB_ID):
                classe_id = int(row['classe_id'])
                # Determina il numero di incontri effettivi
                dettagli = row.get('dettagli', '').lower()
                if 'solo 1 incontro' in dettagli:
                    num_meetings = 1
                elif 'solo 2 incontri' in dettagli:
                    num_meetings = 2
                else:
                    num_meetings = LAB_NUM_MEETINGS

                lab_classes[classe_id] = {
                    'nome': row['nome_classe'],
                    'num_meetings': num_meetings,
                    'dettagli': row.get('dettagli', ''),
                    'scheduled_meetings': []
                }
    return lab_classes


def read_classes_info() -> Dict[int, Dict]:
    """Legge informazioni sulle classi (scuola, accorpamenti preferenziali)."""
    classes_info = {}
    with open('data/input/classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            classe_id = int(row['classe_id'])
            classes_info[classe_id] = {
                'nome': row['nome'],
                'scuola_id': int(row['scuola_id']),
                'accorpamento_pref': row.get('accorpamento_preferenziale', '').strip()
            }
    return classes_info


def read_availability() -> Tuple[List[str], Dict[str, Set[int]], List[str]]:
    """
    Legge la disponibilità delle classi.
    Returns: (list of slot_ids, dict mapping slot_id -> set of available class_ids, list of class_columns)
    """
    with open('data/output/class_availability.csv', 'r') as f:
        reader = csv.DictReader(f)

        # Prima riga: leggo le intestazioni (formato: "classe_id-scuola_id-nome")
        class_columns = reader.fieldnames[1:]  # Escludo 'slot_id'

        availability = {}
        slot_ids = []

        for row in reader:
            slot_id = row['slot_id']
            slot_ids.append(slot_id)

            # Identifico quali classi sono disponibili (valore 'S')
            available = set()
            for col in class_columns:
                if row[col] == 'S':
                    # Estrai classe_id dal formato "classe_id-scuola_id-nome"
                    classe_id = int(col.split('-')[0])
                    available.add(classe_id)

            availability[slot_id] = available

    return slot_ids, availability, class_columns


def find_grouping_opportunities(
    available_classes: Set[int],
    classes_info: Dict[int, Dict],
    lab_classes: Dict[int, Dict]
) -> List[Tuple[List[int], int]]:
    """
    Trova opportunità di accorpamento tra le classi disponibili.
    Returns: list of (group, priority) dove group è lista di class_ids
    Priority: 2 = accorpamento preferenziale, 1 = stessa scuola, 0 = nessun accorpamento
    """
    opportunities = []
    used = set()

    # Prima priorità: accorpamenti preferenziali
    for classe_id in available_classes:
        if classe_id in used:
            continue

        classe_info = classes_info[classe_id]
        pref = classe_info['accorpamento_pref']

        if pref:
            # Cerca la classe con cui accorpare
            for other_id in available_classes:
                if other_id == classe_id or other_id in used:
                    continue

                other_info = classes_info[other_id]
                if other_info['nome'] == pref:
                    opportunities.append(([classe_id, other_id], 2))
                    used.add(classe_id)
                    used.add(other_id)
                    break

    # Seconda priorità: stessa scuola
    by_school = defaultdict(list)
    for classe_id in available_classes:
        if classe_id not in used:
            scuola_id = classes_info[classe_id]['scuola_id']
            by_school[scuola_id].append(classe_id)

    for scuola_id, school_classes in by_school.items():
        # Accorpa a coppie
        for i in range(0, len(school_classes), MAX_GROUP_SIZE):
            group = school_classes[i:i+MAX_GROUP_SIZE]
            opportunities.append((group, 1))
            used.update(group)

    # Classi singole rimaste
    for classe_id in available_classes:
        if classe_id not in used:
            opportunities.append(([classe_id], 0))

    # Ordina per priorità (più alta prima)
    opportunities.sort(key=lambda x: x[1], reverse=True)

    return opportunities


def schedule_lab(
    slot_ids: List[str],
    availability: Dict[str, Set[int]],
    lab_classes: Dict[int, Dict],
    classes_info: Dict[int, Dict],
    max_weeks: int = 8
) -> Tuple[Dict[str, List[Tuple[int, str]]], Dict[str, Dict[int, List[int]]]]:
    """
    Schedula gli incontri del laboratorio.
    Returns:
        - dict mapping slot_id -> list of (classe_id, lab_label)
        - dict mapping slot_id -> dict mapping classe_id -> list of grouped classe_ids
    """
    # Traccia i progressi di ogni classe
    progress = {cid: 0 for cid in lab_classes.keys()}

    # Calendario risultante
    schedule = {slot_id: [] for slot_id in slot_ids}

    # Traccia gli accorpamenti: slot_id -> {classe_id -> [other_classe_ids]}
    groupings = {slot_id: {} for slot_id in slot_ids}

    # Limita alle prime N settimane
    relevant_slots = []
    for slot_id in slot_ids:
        week = int(slot_id.split('-')[0][1:])
        if week < max_weeks:
            relevant_slots.append(slot_id)

    print(f"Scheduling per le prime {max_weeks} settimane ({len(relevant_slots)} slot)")

    # Itera su ogni slot nelle prime settimane
    for slot_id in relevant_slots:
        available_class_ids = availability[slot_id]

        # Filtra solo le classi che devono fare lab 4 e hanno ancora incontri da fare
        available_for_lab = set()
        for cid in available_class_ids:
            if cid in lab_classes and progress[cid] < lab_classes[cid]['num_meetings']:
                available_for_lab.add(cid)

        if not available_for_lab:
            continue

        # Trova opportunità di accorpamento
        opportunities = find_grouping_opportunities(available_for_lab, classes_info, lab_classes)

        # Schedula fino a MAX_TRAINERS incontri per questo slot
        meetings_in_slot = 0
        for group, priority in opportunities:
            if meetings_in_slot >= MAX_TRAINERS:
                break

            # Verifica se tutte le classi nel gruppo possono fare questo incontro
            can_schedule = True
            meeting_number = None

            for cid in group:
                if progress[cid] >= lab_classes[cid]['num_meetings']:
                    can_schedule = False
                    break

                # Tutte le classi del gruppo devono essere allo stesso incontro
                if meeting_number is None:
                    meeting_number = progress[cid] + 1
                elif progress[cid] + 1 != meeting_number:
                    can_schedule = False
                    break

            if can_schedule and meeting_number:
                # Schedula l'incontro
                label = f"L{LAB_ID}-{meeting_number}"
                for cid in group:
                    schedule[slot_id].append((cid, label))
                    progress[cid] += 1

                # Registra l'accorpamento (solo se il gruppo ha più di 1 classe)
                if len(group) > 1:
                    for cid in group:
                        # Per ogni classe, salva le altre classi del gruppo
                        groupings[slot_id][cid] = [other_cid for other_cid in group if other_cid != cid]

                meetings_in_slot += 1

                # Log
                group_names = [classes_info[cid]['nome'] for cid in group]
                scuola = classes_info[group[0]]['scuola_id']
                print(f"  {slot_id}: Scuola {scuola} - {' + '.join(group_names)} -> {label}")

    # Secondo passaggio: completa le classi incomplete senza vincoli di accorpamento
    incomplete_classes = [cid for cid in lab_classes.keys() if progress[cid] < lab_classes[cid]['num_meetings']]

    if incomplete_classes:
        print(f"\n=== Secondo passaggio: completamento {len(incomplete_classes)} classi ===")

        for slot_id in slot_ids:  # Considera tutti gli slot, non solo le prime settimane
            available_class_ids = availability[slot_id]

            # Filtra le classi incomplete che sono disponibili
            available_incomplete = [cid for cid in incomplete_classes if cid in available_class_ids and progress[cid] < lab_classes[cid]['num_meetings']]

            if not available_incomplete:
                continue

            # Schedula senza accorpamenti, fino a MAX_TRAINERS per slot
            meetings_in_slot = len(schedule[slot_id])

            for cid in available_incomplete:
                if meetings_in_slot >= MAX_TRAINERS:
                    break

                if progress[cid] < lab_classes[cid]['num_meetings']:
                    meeting_number = progress[cid] + 1
                    label = f"L{LAB_ID}-{meeting_number}"

                    schedule[slot_id].append((cid, label))
                    progress[cid] += 1
                    meetings_in_slot += 1

                    class_name = classes_info[cid]['nome']
                    scuola = classes_info[cid]['scuola_id']
                    print(f"  {slot_id}: Scuola {scuola} - {class_name} -> {label}")

    # Report finale
    print("\n=== Report finale ===")
    incomplete = []
    for cid, lab_info in lab_classes.items():
        expected = lab_info['num_meetings']
        actual = progress[cid]
        class_name = classes_info[cid]['nome']
        scuola = classes_info[cid]['scuola_id']

        if actual < expected:
            incomplete.append((scuola, class_name, actual, expected))
            print(f"⚠️  Scuola {scuola} - {class_name}: {actual}/{expected} incontri schedulati")

    if not incomplete:
        print("✅ Tutte le classi hanno completato gli incontri richiesti!")
    else:
        print(f"\n⚠️  {len(incomplete)} classi non hanno completato tutti gli incontri")

    return schedule, groupings


def read_formatrici_availability() -> Dict[str, int]:
    """
    Legge la disponibilità delle formatrici per ogni slot.
    Returns: dict mapping slot_id -> numero di formatrici disponibili
    """
    formatrici_count = {}

    try:
        with open('data/output/formatrici_availability.csv', 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                slot_id = row['slot_id']
                # Conta quante colonne non hanno 'N'
                count = 0
                for col, val in row.items():
                    if col != 'slot_id' and val != 'N':
                        count += 1
                formatrici_count[slot_id] = count
    except FileNotFoundError:
        print("⚠️  File formatrici_availability.csv non trovato. Colonna non aggiunta.")
        return {}

    return formatrici_count


def write_calendar(
    slot_ids: List[str],
    availability: Dict[str, Set[int]],
    schedule: Dict[str, List[Tuple[int, str]]],
    groupings: Dict[str, Dict[int, List[int]]],
    class_columns: List[str],
    classes_info: Dict[int, Dict]
):
    """Scrive il calendario risultante in formato CSV con indicazione degli accorpamenti."""
    # Crea mapping: classe_id -> colonna (formato "classe_id-scuola_id-nome")
    cid_to_col = {}
    for col in class_columns:
        classe_id = int(col.split('-')[0])
        cid_to_col[classe_id] = col

    # Leggi disponibilità formatrici
    formatrici_count = read_formatrici_availability()

    with open('data/output/calendario_laboratori.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header (mantiene formato "classe_id-scuola_id-nome") + colonne finali
        header = ['slot_id'] + class_columns + ['num_formatrici']
        if formatrici_count:
            header.append('num_formatrici_disponibili')
        writer.writerow(header)

        # Per ogni slot
        for slot_id in slot_ids:
            row = [slot_id]

            # Crea mapping: classe_id -> label
            scheduled_map = {}
            for classe_id, label in schedule.get(slot_id, []):
                scheduled_map[classe_id] = label

            # Per ogni colonna classe
            for col in class_columns:
                # Estrai classe_id dal formato "classe_id-scuola_id-nome"
                classe_id = int(col.split('-')[0])

                if classe_id in scheduled_map:
                    # C'è un laboratorio schedulato
                    label = scheduled_map[classe_id]

                    # Verifica se è accorpata con altre classi
                    if classe_id in groupings.get(slot_id, {}):
                        grouped_with = groupings[slot_id][classe_id]
                        # Aggiungi le colonne delle classi accorpate
                        grouped_cols = [cid_to_col[other_cid] for other_cid in grouped_with]
                        label = f"{label}/{'/'.join(grouped_cols)}"

                    row.append(label)
                elif classe_id in availability[slot_id]:
                    # Disponibile ma non schedulato
                    row.append('-')
                else:
                    # Non disponibile
                    row.append('X')

            # Calcola numero formatrici: conta i gruppi unici
            # Ogni classe schedulata conta 0.5 se accorpata, 1 se singola
            classes_in_slot = [cid for cid, _ in schedule.get(slot_id, [])]
            grouped_classes = set()

            # Identifica tutte le classi accorpate
            for cid in classes_in_slot:
                if cid in groupings.get(slot_id, {}):
                    grouped_classes.add(cid)

            # Conta: classi accorpate contano 0.5, singole contano 1
            num_formatrici = 0.0
            for cid in classes_in_slot:
                if cid in grouped_classes:
                    num_formatrici += 0.5
                else:
                    num_formatrici += 1.0

            # Aggiungi alla riga (come numero intero se è intero, altrimenti float)
            if num_formatrici == int(num_formatrici):
                row.append(int(num_formatrici))
            else:
                row.append(num_formatrici)

            # Aggiungi numero formatrici disponibili se presente
            if formatrici_count:
                row.append(formatrici_count.get(slot_id, 0))

            writer.writerow(row)

    print(f"\n✅ Calendario scritto in data/output/calendario_laboratori.csv")


def main():
    print("=== Scheduling Citizen Science (Lab 4) ===\n")

    # Leggi i dati
    print("Caricamento dati...")
    lab_classes = read_lab_classes()
    classes_info = read_classes_info()
    slot_ids, availability, class_columns = read_availability()

    print(f"  - {len(lab_classes)} classi devono fare il lab")
    print(f"  - {len(slot_ids)} slot disponibili")
    print(f"  - {len(class_columns)} colonne classi")

    # Schedula
    print("\nScheduling...\n")
    schedule, groupings = schedule_lab(slot_ids, availability, lab_classes, classes_info, max_weeks=12)

    # Scrivi il calendario
    write_calendar(slot_ids, availability, schedule, groupings, class_columns, classes_info)


if __name__ == '__main__':
    main()
