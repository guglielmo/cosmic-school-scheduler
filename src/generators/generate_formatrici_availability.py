#!/usr/bin/env python3
"""
Script per generare la disponibilità delle formatrici su tutti gli slot del calendario.
Crea output/formatrici_availability.csv simile a class_availability.csv.
"""

import csv
import re
from datetime import datetime, time
from typing import Dict, List, Set, Tuple


def parse_margherita_dates(date_string: str) -> List[Tuple[datetime, time, time]]:
    """
    Parsa la stringa di date disponibili di Margherita.
    Returns: list of (date, start_time, end_time)
    """
    if not date_string:
        return []

    results = []
    # Pattern: "13 Gennaio 10.00-14.00"
    pattern = r'(\d+)\s+(\w+)\s+(\d+)\.(\d+)-(\d+)\.(\d+)'

    # Mapping mesi italiani
    months = {
        'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
        'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
        'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
    }

    for match in re.finditer(pattern, date_string, re.IGNORECASE):
        day = int(match.group(1))
        month_name = match.group(2).lower()
        start_hour = int(match.group(3))
        start_min = int(match.group(4))
        end_hour = int(match.group(5))
        end_min = int(match.group(6))

        if month_name in months:
            month = months[month_name]
            # Anno 2026 (da verificare dal calendario)
            year = 2026

            try:
                date = datetime(year, month, day)
                start_time_obj = time(start_hour, start_min)
                end_time_obj = time(end_hour, end_min)
                results.append((date, start_time_obj, end_time_obj))
            except ValueError:
                print(f"⚠️  Data non valida: {day} {month_name} {year}")

    return results


def time_overlaps(start1: time, end1: time, start2: time, end2: time) -> bool:
    """Verifica se due intervalli temporali si sovrappongono."""
    # Converti in minuti per facilitare il confronto
    s1 = start1.hour * 60 + start1.minute
    e1 = end1.hour * 60 + end1.minute
    s2 = start2.hour * 60 + start2.minute
    e2 = end2.hour * 60 + end2.minute

    return s1 < e2 and s2 < e1


def read_formatrici() -> Dict[int, Dict]:
    """Legge le informazioni sulle formatrici."""
    formatrici = {}

    with open('data/input/formatrici.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            formatrice_id = int(row['formatrice_id'])

            # Parsa giorni disponibili
            mattine = row.get('mattine_disponibili', '').strip()
            pomeriggi = row.get('pomeriggi_disponibili', '').strip()

            mattine_giorni = set(mattine.split(',')) if mattine else set()
            pomeriggi_giorni = set(pomeriggi.split(',')) if pomeriggi else set()

            # Parsa date specifiche (Margherita)
            date_disponibili = parse_margherita_dates(row.get('date_disponibili', ''))

            formatrici[formatrice_id] = {
                'nome': row['nome'],
                'lavora_sabato': row['lavora_sabato'].lower() == 'si',
                'mattine_giorni': mattine_giorni,
                'pomeriggi_giorni': pomeriggi_giorni,
                'date_disponibili': date_disponibili
            }

    return formatrici


def read_slots() -> List[Dict]:
    """Legge gli slot dal calendario."""
    slots = []

    with open('data/output/slots_calendar.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parsa la data
            date = datetime.strptime(row['date'], '%Y-%m-%d')

            # Parsa l'orario
            time_range = row['time_range']
            start_str, end_str = time_range.split('-')
            start_time = datetime.strptime(start_str, '%H:%M').time()
            end_time = datetime.strptime(end_str, '%H:%M').time()

            slots.append({
                'slot_id': row['slot_id'],
                'date': date,
                'weekday': row['weekday'],
                'slot_name': row['slot_name'],
                'start_time': start_time,
                'end_time': end_time
            })

    return slots


def is_formatrice_available(
    formatrice: Dict,
    slot: Dict
) -> bool:
    """Determina se una formatrice è disponibile per uno slot."""

    # Caso 1: Margherita (ha date specifiche)
    if formatrice['date_disponibili']:
        # Verifica se c'è una data disponibile che corrisponde
        for avail_date, avail_start, avail_end in formatrice['date_disponibili']:
            # Stessa data?
            if avail_date.date() == slot['date'].date():
                # Orario sovrapposto?
                if time_overlaps(avail_start, avail_end, slot['start_time'], slot['end_time']):
                    return True
        return False

    # Caso 2: Altre formatrici (disponibilità per giorno della settimana)
    weekday = slot['weekday']
    slot_name = slot['slot_name']

    # Sabato: solo se lavora_sabato
    if weekday == 'sab' and not formatrice['lavora_sabato']:
        return False

    # Mattina (M1, M2)
    if slot_name in ['M1', 'M2']:
        return weekday in formatrice['mattine_giorni']

    # Pomeriggio (P)
    if slot_name == 'P':
        return weekday in formatrice['pomeriggi_giorni']

    return False


def generate_availability():
    """Genera il file di disponibilità delle formatrici."""
    print("=== Generazione disponibilità formatrici ===\n")

    # Leggi dati
    print("Caricamento dati...")
    formatrici = read_formatrici()
    slots = read_slots()

    print(f"  - {len(formatrici)} formatrici")
    print(f"  - {len(slots)} slot")

    # Crea le colonne (formato "id-nome")
    formatrici_cols = [f"{fid}-{info['nome']}" for fid, info in sorted(formatrici.items())]

    # Genera la matrice di disponibilità
    print("\nGenerazione disponibilità...")

    with open('data/output/formatrici_availability.csv', 'w', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(['slot_id'] + formatrici_cols)

        # Per ogni slot
        for slot in slots:
            row = [slot['slot_id']]

            # Per ogni formatrice
            for fid in sorted(formatrici.keys()):
                formatrice = formatrici[fid]

                if is_formatrice_available(formatrice, slot):
                    row.append(f"{fid}-{formatrice['nome']}")
                else:
                    row.append('N')

            writer.writerow(row)

    print(f"✅ File generato: data/output/formatrici_availability.csv")

    # Statistiche
    print("\n=== Statistiche ===")
    for fid, info in sorted(formatrici.items()):
        available_count = sum(
            1 for slot in slots
            if is_formatrice_available(info, slot)
        )
        print(f"  {fid}-{info['nome']}: {available_count}/{len(slots)} slot disponibili ({available_count/len(slots)*100:.1f}%)")


if __name__ == '__main__':
    generate_availability()
