#!/usr/bin/env python3
"""
Analisi Capacità - Calcolo slot necessari vs disponibili

Calcola:
1. DOMANDA (slot necessari per i laboratori):
   - Minimo: tutti gli accorpamenti possibili attivi
   - Massimo: nessun accorpamento

2. OFFERTA (slot disponibili per le formatrici):
   - Considerando disponibilità mattina/pomeriggio per giorno
   - Considerando vincoli sabato (solo scuole 10,13 e formatrice 4)
   - Considerando settimane GSSI da escludere
   - Considerando calendario (inizio giovedì, Pasqua, fine)
"""

import pandas as pd
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta

from date_parser import DateParser


def load_data(input_dir: str):
    """Carica tutti i dati necessari."""
    input_path = Path(input_dir)
    return {
        'scuole': pd.read_csv(input_path / "scuole.csv"),
        'classi': pd.read_csv(input_path / "classi.csv"),
        'laboratori': pd.read_csv(input_path / "laboratori.csv"),
        'laboratori_classi': pd.read_csv(input_path / "laboratori_classi.csv"),
        'formatrici': pd.read_csv(input_path / "formatrici.csv"),
        'fasce_orarie_scuole': pd.read_csv(input_path / "fasce_orarie_scuole.csv"),
        'fasce_orarie_classi': pd.read_csv(input_path / "fasce_orarie_classi.csv"),
        'date_escluse_classi': pd.read_csv(input_path / "date_escluse_classi.csv"),
    }


def get_valid_days():
    """
    Restituisce lista di (settimana, giorno) validi nel calendario.

    Vincoli:
    - Settimana 0: solo da giovedì (giorno >= 3)
    - Settimana 9: solo fino a mercoledì (giorno <= 2) - pre-Pasqua
    - Settimana 15 (ultima): solo fino a giovedì (giorno <= 3)
    - Settimane 10-15: post-Pasqua (dal 13 aprile)
    """
    NUM_SETTIMANE = 16
    valid_days = []

    for sett in range(NUM_SETTIMANE):
        for giorno in range(6):  # 0=lun, 5=sab
            # Settimana 0: solo da giovedì
            if sett == 0 and giorno < 3:
                continue
            # Settimana 9: solo fino a mercoledì (pre-Pasqua)
            if sett == 9 and giorno > 2:
                continue
            # Ultima settimana: solo fino a giovedì
            if sett == NUM_SETTIMANE - 1 and giorno > 3:
                continue

            valid_days.append((sett, giorno))

    return valid_days


def analyze_demand(data):
    """
    Calcola la domanda di slot (incontri da schedulare).

    Returns:
        dict con:
        - total_meetings: numero totale incontri
        - min_slots: minimo slot necessari (max accorpamenti)
        - max_slots: massimo slot necessari (nessun accorpamento)
        - potential_groupings: numero accorpamenti possibili
    """
    # Lab FOP (gestiti da formatrici)
    lab_ids_validi = set(data['laboratori']['laboratorio_id'].values)

    # Incontri per classe
    labs_per_classe = defaultdict(list)
    for _, row in data['laboratori_classi'].iterrows():
        if row['laboratorio_id'] in lab_ids_validi:
            labs_per_classe[row['classe_id']].append(row['laboratorio_id'])

    # Numero incontri per lab
    num_incontri_lab = {}
    for _, lab in data['laboratori'].iterrows():
        num_incontri_lab[lab['laboratorio_id']] = int(lab['num_incontri'])

    # Scuola per classe
    scuola_per_classe = {}
    for _, row in data['classi'].iterrows():
        scuola_per_classe[row['classe_id']] = row['scuola_id']

    # Conta incontri totali
    total_meetings = 0
    meetings_per_lab = defaultdict(int)
    for classe_id, labs in labs_per_classe.items():
        for lab_id in labs:
            n = num_incontri_lab.get(lab_id, 1)
            total_meetings += n
            meetings_per_lab[lab_id] += n

    # Calcola accorpamenti possibili
    # Due classi possono accorparsi se: stessa scuola, stesso lab
    classi_per_scuola = defaultdict(list)
    for classe_id, scuola_id in scuola_per_classe.items():
        if classe_id in labs_per_classe:
            classi_per_scuola[scuola_id].append(classe_id)

    potential_groupings = 0
    meetings_saved_by_grouping = 0

    groupings_detail = []

    for scuola_id, classi_scuola in classi_per_scuola.items():
        for i, c1 in enumerate(classi_scuola):
            for c2 in classi_scuola[i+1:]:
                # Lab in comune
                labs_c1 = set(labs_per_classe[c1])
                labs_c2 = set(labs_per_classe[c2])
                labs_comuni = labs_c1 & labs_c2

                for lab_id in labs_comuni:
                    n = num_incontri_lab.get(lab_id, 1)
                    potential_groupings += 1
                    meetings_saved_by_grouping += n

                    # Nomi classi per dettaglio
                    nome_c1 = data['classi'][data['classi']['classe_id'] == c1]['nome'].iloc[0]
                    nome_c2 = data['classi'][data['classi']['classe_id'] == c2]['nome'].iloc[0]
                    nome_lab = data['laboratori'][data['laboratori']['laboratorio_id'] == lab_id]['nome'].iloc[0]
                    nome_scuola = data['scuole'][data['scuole']['scuola_id'] == scuola_id]['nome'].iloc[0]
                    groupings_detail.append({
                        'scuola': nome_scuola,
                        'classe1': nome_c1,
                        'classe2': nome_c2,
                        'lab': nome_lab,
                        'incontri': n
                    })

    return {
        'total_meetings': total_meetings,
        'max_slots': total_meetings,  # Nessun accorpamento
        'min_slots': total_meetings - meetings_saved_by_grouping,  # Max accorpamenti
        'potential_groupings': potential_groupings,
        'meetings_saved_max': meetings_saved_by_grouping,
        'meetings_per_lab': dict(meetings_per_lab),
        'groupings_detail': groupings_detail,
        'num_classi': len(labs_per_classe),
    }


def analyze_supply(data):
    """
    Calcola l'offerta di slot (disponibilità formatrici).

    Ipotesi:
    - Mattina: max 2 slot non sovrapposti (es. 8-10 e 11-13)
    - Pomeriggio: 1 slot
    - Anita (formatrice 1): può fare 3 slot/giorno
    - Altre formatrici: 2 slot/giorno
    - Sabato: solo formatrice 4, solo scuole 10 e 13

    Returns:
        dict con dettagli disponibilità
    """
    DateParser.load_fasce_info(data['fasce_orarie_scuole'])

    valid_days = get_valid_days()

    # Giorni feriali vs sabato
    weekdays = [(s, g) for s, g in valid_days if g < 5]
    saturdays = [(s, g) for s, g in valid_days if g == 5]

    print(f"\n  Giorni validi: {len(valid_days)} totali")
    print(f"    - Feriali (lun-ven): {len(weekdays)}")
    print(f"    - Sabati: {len(saturdays)}")

    # Mappa disponibilità formatrici
    giorni_map = {'lun': 0, 'mar': 1, 'mer': 2, 'gio': 3, 'ven': 4, 'sab': 5}

    formatrici_info = {}
    for _, f in data['formatrici'].iterrows():
        f_id = int(f['formatrice_id'])
        nome = f['nome']

        # Mattine disponibili
        mattine_str = f.get('mattine_disponibili', '')
        if pd.isna(mattine_str) or mattine_str == '':
            mattine = None  # Tutte
        else:
            mattine = set()
            for g in str(mattine_str).split(','):
                g = g.strip().lower()
                if g in giorni_map:
                    mattine.add(giorni_map[g])

        # Pomeriggi disponibili
        pomeriggi_str = f.get('pomeriggi_disponibili', '')
        if pd.isna(pomeriggi_str) or pomeriggi_str == '':
            pomeriggi = None  # Tutti
        else:
            pomeriggi = set()
            for g in str(pomeriggi_str).split(','):
                g = g.strip().lower()
                if g in giorni_map:
                    pomeriggi.add(giorni_map[g])

        # Sabato
        lavora_sab = str(f.get('lavora_sabato', 'no')).strip().lower() == 'si'

        # Slot specifici (Margherita)
        date_disp_str = f.get('date_disponibili', '')
        if pd.notna(date_disp_str) and date_disp_str != '':
            slot_specifici = DateParser.parse_date_disponibili(date_disp_str)
        else:
            slot_specifici = None

        # Budget ore
        ore_budget = {1: 292, 2: 128, 3: 160, 4: 128}.get(f_id, 100)

        formatrici_info[f_id] = {
            'nome': nome,
            'mattine': mattine,
            'pomeriggi': pomeriggi,
            'lavora_sabato': lavora_sab,
            'slot_specifici': slot_specifici,
            'ore_budget': ore_budget,
        }

    # Calcola slot disponibili per ogni formatrice
    results = {}
    total_slots_min = 0  # Conservativo (2 slot/giorno tranne Anita)
    total_slots_max = 0  # Ottimistico (3 slot/giorno)

    for f_id, info in formatrici_info.items():
        nome = info['nome']

        if info['slot_specifici'] is not None:
            # Margherita: conta slot specifici
            # Ogni entry è (sett, giorno, [fasce])
            # Raggruppa per (sett, giorno) e conta quanti slot non sovrapposti
            days_with_slots = defaultdict(list)
            for sett, giorno, fasce in info['slot_specifici']:
                days_with_slots[(sett, giorno)].extend(fasce)

            # Per ogni giorno, stima slot non sovrapposti
            # Semplificazione: mattina = max 2, pomeriggio = 1
            slots_count = 0
            for (sett, giorno), fasce in days_with_slots.items():
                fasce_mattina = [f for f in fasce if f <= 5]
                fasce_pomeriggio = [f for f in fasce if f > 5]

                # Mattina: max 2 non sovrapposti
                if fasce_mattina:
                    slots_count += min(2, len(fasce_mattina))
                # Pomeriggio: max 1
                if fasce_pomeriggio:
                    slots_count += 1

            results[f_id] = {
                'nome': nome,
                'giorni_disponibili': len(days_with_slots),
                'slots_min': slots_count,  # Margherita fa quello che può
                'slots_max': slots_count,
                'ore_budget': info['ore_budget'],
                'max_ore_da_slot': slots_count * 2,  # 2 ore per slot
            }
            total_slots_min += slots_count
            total_slots_max += slots_count
        else:
            # Altre formatrici: calcola in base a mattine/pomeriggi disponibili
            giorni_effettivi = 0
            slots_mattina = 0
            slots_pomeriggio = 0

            for sett, giorno in valid_days:
                is_sabato = (giorno == 5)

                # Sabato: solo formatrice 4
                if is_sabato:
                    if f_id != 4 or not info['lavora_sabato']:
                        continue

                # Controlla disponibilità mattina
                if info['mattine'] is None or giorno in info['mattine']:
                    slots_mattina += 2  # Max 2 slot mattina

                # Controlla disponibilità pomeriggio
                if info['pomeriggi'] is None or giorno in info['pomeriggi']:
                    slots_pomeriggio += 1  # 1 slot pomeriggio

                if (info['mattine'] is None or giorno in info['mattine']) or \
                   (info['pomeriggi'] is None or giorno in info['pomeriggi']):
                    giorni_effettivi += 1

            # Anita (f_id=1) può fare 3 slot/giorno, altre 2
            if f_id == 1:
                slots_per_day_min = 3
                slots_per_day_max = 3
            else:
                slots_per_day_min = 2
                slots_per_day_max = 3

            # Slot totali = min(mattina + pomeriggio, slot_per_day * giorni)
            raw_slots = slots_mattina + slots_pomeriggio
            slots_min = min(raw_slots, giorni_effettivi * slots_per_day_min)
            slots_max = min(raw_slots, giorni_effettivi * slots_per_day_max)

            # Limita anche per budget ore (ogni slot = 2 ore)
            max_slots_by_budget = info['ore_budget'] // 2
            slots_min = min(slots_min, max_slots_by_budget)
            slots_max = min(slots_max, max_slots_by_budget)

            results[f_id] = {
                'nome': nome,
                'giorni_disponibili': giorni_effettivi,
                'slots_mattina_raw': slots_mattina,
                'slots_pomeriggio_raw': slots_pomeriggio,
                'slots_min': slots_min,
                'slots_max': slots_max,
                'ore_budget': info['ore_budget'],
                'max_ore_da_slot': slots_max * 2,
            }
            total_slots_min += slots_min
            total_slots_max += slots_max

    return {
        'formatrici': results,
        'total_slots_min': total_slots_min,
        'total_slots_max': total_slots_max,
        'valid_days': len(valid_days),
        'weekdays': len(weekdays),
        'saturdays': len(saturdays),
    }


def analyze_gssi_impact(data):
    """
    Analizza l'impatto dei corsi GSSI sulla disponibilità delle classi.

    Se una classe ha un corso GSSI in una settimana, non può fare corsi FOP
    in quella stessa settimana (vincolo H2: max 1 incontro/settimana per classe).

    Returns:
        dict con dettagli impatto GSSI per classe
    """
    DateParser.load_fasce_info(data['fasce_orarie_scuole'])

    # Lab FOP vs GSSI
    lab_ids_fop = set(data['laboratori']['laboratorio_id'].values)
    tutti_lab_ids = set(data['laboratori_classi']['laboratorio_id'].values)
    lab_ids_gssi = tutti_lab_ids - lab_ids_fop

    # Settimane GSSI per classe
    settimane_gssi = defaultdict(set)
    for _, row in data['laboratori_classi'].iterrows():
        lab_id = row['laboratorio_id']
        if lab_id not in lab_ids_gssi:
            continue
        if pd.isna(row.get('date_fissate')) or row['date_fissate'] == '':
            continue

        classe_id = row['classe_id']
        parsed = DateParser.parse_date_fissate(row['date_fissate'])
        for sett, giorno, fasce_valide in parsed:
            if sett is not None:
                settimane_gssi[classe_id].add(sett)

    # Incontri FOP per classe
    incontri_fop_per_classe = defaultdict(int)
    for _, row in data['laboratori_classi'].iterrows():
        if row['laboratorio_id'] in lab_ids_fop:
            lab_id = row['laboratorio_id']
            num_inc = data['laboratori'][data['laboratori']['laboratorio_id'] == lab_id]['num_incontri'].iloc[0]
            incontri_fop_per_classe[row['classe_id']] += int(num_inc)

    # Settimane totali disponibili nel calendario
    valid_days = get_valid_days()
    settimane_valide = set(sett for sett, _ in valid_days)
    num_settimane_totali = len(settimane_valide)

    # Analisi per classe
    classi_info = {}
    classi_critiche = []

    for classe_id in incontri_fop_per_classe:
        classe_row = data['classi'][data['classi']['classe_id'] == classe_id]
        if len(classe_row) == 0:
            continue
        classe_row = classe_row.iloc[0]
        nome_classe = classe_row['nome']
        scuola_id = classe_row['scuola_id']
        scuola_nome = data['scuole'][data['scuole']['scuola_id'] == scuola_id]['nome'].iloc[0]

        sett_gssi = settimane_gssi.get(classe_id, set())
        sett_libere = settimane_valide - sett_gssi
        incontri_necessari = incontri_fop_per_classe[classe_id]

        margine = len(sett_libere) - incontri_necessari

        classi_info[classe_id] = {
            'nome': nome_classe,
            'scuola': scuola_nome,
            'settimane_gssi': len(sett_gssi),
            'settimane_libere': len(sett_libere),
            'incontri_fop': incontri_necessari,
            'margine': margine,
            'critica': margine < 2,  # Meno di 2 settimane di margine
        }

        if margine < 2:
            classi_critiche.append(classi_info[classe_id])

    return {
        'lab_ids_gssi': lab_ids_gssi,
        'num_settimane_totali': num_settimane_totali,
        'classi_con_gssi': len(settimane_gssi),
        'classi_info': classi_info,
        'classi_critiche': classi_critiche,
        'totale_settimane_bloccate': sum(len(s) for s in settimane_gssi.values()),
    }


def main():
    print("=" * 70)
    print("  ANALISI CAPACITÀ - Slot necessari vs disponibili")
    print("=" * 70)

    data = load_data("data/input")

    # === DOMANDA ===
    print("\n" + "=" * 70)
    print("  DOMANDA (slot necessari)")
    print("=" * 70)

    demand = analyze_demand(data)

    print(f"\n  Classi coinvolte: {demand['num_classi']}")
    print(f"  Incontri totali: {demand['total_meetings']}")
    print(f"\n  Incontri per laboratorio:")
    lab_names = {row['laboratorio_id']: row['nome'] for _, row in data['laboratori'].iterrows()}
    for lab_id, count in sorted(demand['meetings_per_lab'].items()):
        print(f"    - {lab_names.get(lab_id, lab_id)}: {count} incontri")

    print(f"\n  Accorpamenti possibili: {demand['potential_groupings']}")
    print(f"  Incontri risparmiabili con accorpamenti: {demand['meetings_saved_max']}")

    print(f"\n  SLOT NECESSARI:")
    print(f"    - MINIMO (tutti accorpati): {demand['min_slots']} slot")
    print(f"    - MASSIMO (nessun accorpamento): {demand['max_slots']} slot")

    # Dettaglio accorpamenti per scuola
    if demand['groupings_detail']:
        print(f"\n  Dettaglio accorpamenti possibili per scuola:")
        by_scuola = defaultdict(list)
        for g in demand['groupings_detail']:
            by_scuola[g['scuola']].append(g)
        for scuola, groups in sorted(by_scuola.items()):
            tot_inc = sum(g['incontri'] for g in groups)
            print(f"    {scuola}: {len(groups)} coppie, {tot_inc} incontri risparmiabili")

    # === OFFERTA ===
    print("\n" + "=" * 70)
    print("  OFFERTA (slot disponibili formatrici)")
    print("=" * 70)

    supply = analyze_supply(data)

    print(f"\n  Dettaglio per formatrice:")
    for f_id, info in sorted(supply['formatrici'].items()):
        print(f"\n    {info['nome']} (ID {f_id}):")
        print(f"      Giorni disponibili: {info['giorni_disponibili']}")
        if 'slots_mattina_raw' in info:
            print(f"      Slot mattina (raw): {info['slots_mattina_raw']}")
            print(f"      Slot pomeriggio (raw): {info['slots_pomeriggio_raw']}")
        print(f"      Budget ore: {info['ore_budget']}h")
        print(f"      Slot effettivi: {info['slots_min']} - {info['slots_max']}")
        print(f"      Ore da slot: max {info['max_ore_da_slot']}h")

    print(f"\n  SLOT DISPONIBILI TOTALI:")
    print(f"    - MINIMO (conservativo, 2/giorno): {supply['total_slots_min']} slot")
    print(f"    - MASSIMO (ottimistico, 3/giorno): {supply['total_slots_max']} slot")

    # === IMPATTO GSSI ===
    print("\n" + "=" * 70)
    print("  IMPATTO CORSI GSSI (settimane bloccate per classe)")
    print("=" * 70)

    gssi = analyze_gssi_impact(data)

    print(f"\n  Laboratori GSSI: {gssi['lab_ids_gssi']}")
    print(f"  Settimane totali nel calendario: {gssi['num_settimane_totali']}")
    print(f"  Classi con corsi GSSI: {gssi['classi_con_gssi']}")
    print(f"  Totale settimane bloccate (somma): {gssi['totale_settimane_bloccate']}")

    # Mostra classi critiche (poco margine)
    if gssi['classi_critiche']:
        print(f"\n  CLASSI CRITICHE (margine < 2 settimane):")
        print(f"  {'Classe':<15} {'Scuola':<25} {'Sett.GSSI':<10} {'Sett.Libere':<12} {'Inc.FOP':<10} {'Margine':<10}")
        print(f"  {'-'*15} {'-'*25} {'-'*10} {'-'*12} {'-'*10} {'-'*10}")
        for c in sorted(gssi['classi_critiche'], key=lambda x: x['margine']):
            status = "IMPOSSIBILE" if c['margine'] < 0 else "CRITICO"
            print(f"  {c['nome']:<15} {c['scuola']:<25} {c['settimane_gssi']:<10} {c['settimane_libere']:<12} {c['incontri_fop']:<10} {c['margine']:<+10} {status}")
    else:
        print(f"\n  Nessuna classe critica (tutte hanno margine >= 2 settimane)")

    # Riepilogo per scuola
    print(f"\n  Riepilogo per scuola:")
    by_scuola = defaultdict(list)
    for classe_id, info in gssi['classi_info'].items():
        by_scuola[info['scuola']].append(info)

    for scuola, classi in sorted(by_scuola.items()):
        tot_gssi = sum(c['settimane_gssi'] for c in classi)
        critiche = sum(1 for c in classi if c['critica'])
        print(f"    {scuola}: {len(classi)} classi, {tot_gssi} sett. GSSI totali, {critiche} critiche")

    # === CONFRONTO ===
    print("\n" + "=" * 70)
    print("  CONFRONTO DOMANDA vs OFFERTA")
    print("=" * 70)

    print(f"\n  {'Scenario':<40} {'Domanda':<10} {'Offerta':<10} {'Margine':<10}")
    print(f"  {'-'*40} {'-'*10} {'-'*10} {'-'*10}")

    # Scenario ottimistico: min domanda, max offerta
    margin_best = supply['total_slots_max'] - demand['min_slots']
    status_best = "OK" if margin_best >= 0 else "DEFICIT"
    print(f"  {'Ottimistico (tutti accorpati, 3/g)':<40} {demand['min_slots']:<10} {supply['total_slots_max']:<10} {margin_best:<+10} {status_best}")

    # Scenario realistico: qualche accorpamento, 2/giorno
    realistic_demand = (demand['min_slots'] + demand['max_slots']) // 2
    realistic_supply = (supply['total_slots_min'] + supply['total_slots_max']) // 2
    margin_real = realistic_supply - realistic_demand
    status_real = "OK" if margin_real >= 0 else "DEFICIT"
    print(f"  {'Realistico (50% accorpamenti, 2.5/g)':<40} {realistic_demand:<10} {realistic_supply:<10} {margin_real:<+10} {status_real}")

    # Scenario pessimistico: max domanda, min offerta
    margin_worst = supply['total_slots_min'] - demand['max_slots']
    status_worst = "OK" if margin_worst >= 0 else "DEFICIT"
    print(f"  {'Pessimistico (no accorpamenti, 2/g)':<40} {demand['max_slots']:<10} {supply['total_slots_min']:<10} {margin_worst:<+10} {status_worst}")

    print("\n" + "=" * 70)

    # Suggerimenti
    problemi = []
    if margin_worst < 0:
        problemi.append(f"Deficit slot nel caso pessimistico: {-margin_worst}")
    if gssi['classi_critiche']:
        impossibili = [c for c in gssi['classi_critiche'] if c['margine'] < 0]
        if impossibili:
            problemi.append(f"{len(impossibili)} classi con margine negativo (impossibili da schedulare)")

    if problemi:
        print("\n  PROBLEMI RILEVATI:")
        for p in problemi:
            print(f"    - {p}")
        print("\n  Possibili soluzioni:")
        print(f"    1. Massimizzare accorpamenti (risparmio max: {demand['meetings_saved_max']} slot)")
        print(f"    2. Aumentare disponibilità formatrici")
        print(f"    3. Estendere il calendario")
        print(f"    4. Spostare alcuni corsi GSSI")
    else:
        print("\n  Nessun problema critico rilevato.")


if __name__ == "__main__":
    main()
