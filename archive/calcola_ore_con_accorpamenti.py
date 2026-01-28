#!/usr/bin/env python3
"""
Calcola ore richieste considerando accorpamenti possibili
"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

INPUT_DIR = Path("data/input")


def calcola_ore_senza_accorpamenti():
    """Caso peggiore: tutte le classi separate"""

    laboratori_classi = pd.read_csv(INPUT_DIR / "laboratori_classi.csv")
    laboratori = pd.read_csv(INPUT_DIR / "laboratori.csv")

    # Merge per avere ore
    merged = laboratori_classi.merge(
        laboratori[['laboratorio_id', 'num_incontri', 'ore_per_incontro']],
        on='laboratorio_id'
    )

    # Calcola ore considerando Citizen Science = 4 incontri invece di 5
    def calcola_incontri_effettivi(row):
        if row['laboratorio_id'] == 4.0:  # Citizen Science
            # Scuole con 3° incontro autonomo
            scuole_autonome = [1, 2, 4, 5, 12]  # Vasto, Bafile, Lanciano, Peano Rosa, Potenza
            if row['scuola_id'] in scuole_autonome:
                return 4  # Solo 4 incontri con formatrice
        return row['num_incontri']

    merged['incontri_effettivi'] = merged.apply(calcola_incontri_effettivi, axis=1)
    merged['ore_totali'] = merged['incontri_effettivi'] * merged['ore_per_incontro']

    ore_totali = merged['ore_totali'].sum()

    return ore_totali, merged


def stima_ore_con_accorpamenti():
    """Stima con accorpamenti massimi possibili"""

    laboratori_classi = pd.read_csv(INPUT_DIR / "laboratori_classi.csv")
    laboratori = pd.read_csv(INPUT_DIR / "laboratori.csv")
    formatrici_classi = pd.read_csv(INPUT_DIR / "formatrici_classi.csv")

    # Merge per info complete
    merged = laboratori_classi.merge(
        laboratori[['laboratorio_id', 'num_incontri', 'ore_per_incontro']],
        on='laboratorio_id'
    )

    # Aggiungi formatrice assegnata (se presente)
    merged = merged.merge(
        formatrici_classi[['classe_id', 'formatrice_id', 'nome_formatrice']],
        on='classe_id',
        how='left'
    )

    # Calcola incontri effettivi (Citizen Science)
    def calcola_incontri_effettivi(row):
        if row['laboratorio_id'] == 4.0:
            scuole_autonome = [1, 2, 4, 5, 12]
            if row['scuola_id'] in scuole_autonome:
                return 4
        return row['num_incontri']

    merged['incontri_effettivi'] = merged.apply(calcola_incontri_effettivi, axis=1)

    # Raggruppa per: scuola + lab + formatrice (potenziali accorpamenti)
    # Un accorpamento è possibile quando più classi:
    # - Stessa scuola
    # - Stesso laboratorio
    # - Stessa formatrice assegnata (o entrambe senza assegnamento)

    accorpamenti = defaultdict(list)

    for _, row in merged.iterrows():
        # Chiave: (scuola, lab, formatrice)
        # Se formatrice è NaN, uso "ANY" per indicare che può essere chiunque
        formatrice_key = row['formatrice_id'] if pd.notna(row['formatrice_id']) else 'ANY'
        key = (row['scuola_id'], row['laboratorio_id'], formatrice_key)
        accorpamenti[key].append(row)

    # Calcola ore considerando accorpamenti
    ore_totali_accorpate = 0
    n_incontri_totali = 0
    n_accorpamenti = 0

    for key, gruppo in accorpamenti.items():
        scuola_id, lab_id, formatrice = key

        # Numero incontri per questo laboratorio
        incontri = gruppo[0]['incontri_effettivi']
        ore_per_incontro = gruppo[0]['ore_per_incontro']

        # Se ci sono N classi nello stesso gruppo, fanno gli incontri insieme
        n_classi = len(gruppo)

        # Ore per questo gruppo: incontri × ore_per_incontro (una sola volta, non N volte)
        ore_gruppo = incontri * ore_per_incontro
        ore_totali_accorpate += ore_gruppo
        n_incontri_totali += incontri

        if n_classi > 1:
            n_accorpamenti += 1

    return ore_totali_accorpate, n_incontri_totali, n_accorpamenti, accorpamenti


def main():
    print("="*70)
    print("CALCOLO ORE CON ACCORPAMENTI")
    print("="*70)
    print()

    # Budget disponibile
    formatrici = pd.read_csv(INPUT_DIR / "formatrici.csv")
    budget = formatrici['ore_settimanali_max'].sum() * 20  # Approssimazione

    # Leggi ore_generali correttamente dal foglio
    print("📊 BUDGET DISPONIBILE")
    print("-"*70)
    print(f"  Ore totali formatrici (da Excel): 708 ore")
    print()

    # Caso 1: Senza accorpamenti
    print("🚫 SCENARIO 1: NESSUN ACCORPAMENTO (caso peggiore)")
    print("-"*70)
    ore_senza, merged = calcola_ore_senza_accorpamenti()
    print(f"  Ore totali richieste: {ore_senza:.0f} ore")
    print(f"  Budget disponibile:   708 ore")
    deficit_senza = ore_senza - 708
    if deficit_senza > 0:
        print(f"  DEFICIT:              -{deficit_senza:.0f} ore ({deficit_senza/708*100:.1f}% oltre budget)")
    else:
        print(f"  SURPLUS:              +{abs(deficit_senza):.0f} ore")
    print()

    # Caso 2: Con accorpamenti massimi
    print("✅ SCENARIO 2: ACCORPAMENTI MASSIMI (caso ottimale)")
    print("-"*70)
    ore_con, n_incontri, n_accorpamenti, accorpamenti = stima_ore_con_accorpamenti()
    print(f"  Ore totali richieste: {ore_con:.0f} ore")
    print(f"  Budget disponibile:   708 ore")
    deficit_con = ore_con - 708
    if deficit_con > 0:
        print(f"  DEFICIT:              -{deficit_con:.0f} ore ({deficit_con/708*100:.1f}% oltre budget)")
    else:
        print(f"  SURPLUS:              +{abs(deficit_con):.0f} ore")
    print()
    print(f"  Gruppi accorpabili:   {len(accorpamenti)}")
    print(f"  Di cui con >1 classe: {n_accorpamenti}")
    print()

    # Esempi accorpamenti
    print("📋 ESEMPI ACCORPAMENTI POSSIBILI")
    print("-"*70)

    # Top 5 gruppi più grandi
    gruppi_ordinati = sorted(accorpamenti.items(), key=lambda x: len(x[1]), reverse=True)

    for (scuola_id, lab_id, formatrice), gruppo in gruppi_ordinati[:10]:
        if len(gruppo) > 1:
            scuola_nome = gruppo[0]['nome_classe'][:10]  # Approssimazione
            lab_nome = {
                4.0: 'Citizen Science',
                5.0: 'Orientamento',
                7.0: 'Discriminazioni',
                8.0: 'Manuali',
                9.0: 'Discriminazioni pt.2'
            }.get(lab_id, f'Lab {lab_id}')

            formatrice_str = formatrice if formatrice != 'ANY' else 'Qualsiasi'
            classi_str = ', '.join([c['nome_classe'] for c in gruppo[:5]])
            if len(gruppo) > 5:
                classi_str += f' ... (+{len(gruppo)-5})'

            print(f"  • Scuola {scuola_id} | {lab_nome} | Formatrice {formatrice_str}")
            print(f"    → {len(gruppo)} classi: {classi_str}")

    print()
    print("="*70)
    print("CONCLUSIONI")
    print("="*70)

    risparmio = ore_senza - ore_con
    print(f"\n  Risparmio con accorpamenti: {risparmio:.0f} ore ({risparmio/ore_senza*100:.1f}%)")

    if deficit_con > 0:
        print(f"\n  ⚠️  Anche con accorpamenti massimi serve {deficit_con:.0f} ore in più")
        print(f"      Serve ottimizzare ulteriormente o aumentare budget")
    elif deficit_senza > 0 and deficit_con <= 0:
        print(f"\n  ✅ Con accorpamenti il problema è RISOLVIBILE")
        print(f"      Margine di {abs(deficit_con):.0f} ore")
    else:
        print(f"\n  ✅ Problema RISOLVIBILE anche senza tutti gli accorpamenti")
        print(f"      Margine molto ampio: {abs(deficit_senza):.0f} ore senza accorpamenti")

    print()


if __name__ == "__main__":
    main()
