#!/usr/bin/env python3
"""
Crea un subset ridotto dei dati per testing incrementale
Fase 1: 1 scuola con le sue classi
"""

import pandas as pd
from pathlib import Path

INPUT_DIR = Path("data/input")
OUTPUT_SUFFIX = "_test"

def crea_subset_1_scuola():
    """Crea subset con solo 1 scuola e le sue classi"""

    print("="*60)
    print("Creazione subset ridotto - 1 SCUOLA")
    print("="*60)
    print()

    # Leggi dati completi
    scuole = pd.read_csv(INPUT_DIR / "scuole.csv")
    classi = pd.read_csv(INPUT_DIR / "classi.csv")
    formatrici = pd.read_csv(INPUT_DIR / "formatrici.csv")
    laboratori = pd.read_csv(INPUT_DIR / "laboratori.csv")
    fasce = pd.read_csv(INPUT_DIR / "fasce_orarie_scuole.csv")

    print(f"Dati completi:")
    print(f"  {len(scuole)} scuole")
    print(f"  {len(classi)} classi")
    print(f"  {len(formatrici)} formatrici")
    print(f"  {len(laboratori)} laboratori")
    print()

    # Seleziona 1 scuola (la prima)
    scuola_id = scuole.iloc[0]['scuola_id']
    scuola_nome = scuole.iloc[0]['nome']

    scuole_subset = scuole[scuole['scuola_id'] == scuola_id].copy()
    classi_subset = classi[classi['scuola_id'] == scuola_id].copy()

    # Mantieni tutte le formatrici (sono solo 4)
    formatrici_subset = formatrici.copy()

    # Mantieni tutti i laboratori
    laboratori_subset = laboratori.copy()

    # Mantieni solo le fasce della scuola selezionata
    fasce_subset = fasce[fasce['scuola_id'] == scuola_id].copy()

    print(f"Subset creato (scuola: {scuola_nome}):")
    print(f"  {len(scuole_subset)} scuola")
    print(f"  {len(classi_subset)} classi")
    print(f"  {len(formatrici_subset)} formatrici")
    print(f"  {len(laboratori_subset)} laboratori")
    print(f"  {len(fasce_subset)} fasce orarie")
    print()

    # Filtra anche i file vincoli se esistono
    try:
        laboratori_classi = pd.read_csv(INPUT_DIR / "laboratori_classi.csv")
        laboratori_classi_subset = laboratori_classi[laboratori_classi['classe_id'].isin(classi_subset['classe_id'])].copy()
        laboratori_classi_subset.to_csv(INPUT_DIR / f"laboratori_classi{OUTPUT_SUFFIX}.csv", index=False)
        print(f"  Filtrato laboratori_classi: {len(laboratori_classi_subset)} righe")
    except:
        pass

    try:
        formatrici_classi = pd.read_csv(INPUT_DIR / "formatrici_classi.csv")
        formatrici_classi_subset = formatrici_classi[formatrici_classi['classe_id'].isin(classi_subset['classe_id'])].copy()
        formatrici_classi_subset.to_csv(INPUT_DIR / f"formatrici_classi{OUTPUT_SUFFIX}.csv", index=False)
        print(f"  Filtrato formatrici_classi: {len(formatrici_classi_subset)} righe")
    except:
        pass

    try:
        date_escluse = pd.read_csv(INPUT_DIR / "date_escluse_classi.csv")
        date_escluse_subset = date_escluse[date_escluse['classe_id'].isin(classi_subset['classe_id'])].copy()
        date_escluse_subset.to_csv(INPUT_DIR / f"date_escluse_classi{OUTPUT_SUFFIX}.csv", index=False)
        print(f"  Filtrato date_escluse: {len(date_escluse_subset)} righe")
    except:
        pass

    # Salva i subset (senza prefisso, solo suffisso)
    scuole_subset.to_csv(INPUT_DIR / f"scuole{OUTPUT_SUFFIX}.csv", index=False)
    classi_subset.to_csv(INPUT_DIR / f"classi{OUTPUT_SUFFIX}.csv", index=False)
    formatrici_subset.to_csv(INPUT_DIR / f"formatrici{OUTPUT_SUFFIX}.csv", index=False)
    laboratori_subset.to_csv(INPUT_DIR / f"laboratori{OUTPUT_SUFFIX}.csv", index=False)
    fasce_subset.to_csv(INPUT_DIR / f"fasce_orarie_scuole{OUTPUT_SUFFIX}.csv", index=False)

    print("✅ File subset creati con suffisso '_test'")
    print()

    # Calcola dimensione problema
    n_variabili = (len(classi_subset) * len(laboratori_subset) *
                   len(formatrici_subset) * 20 * 5 * len(fasce_subset))

    print(f"Stima variabili: {n_variabili:,}")
    print(f"  ({len(classi_subset)} classi × {len(laboratori_subset)} lab × "
          f"{len(formatrici_subset)} formatrici × 20 sett × 5 gg × {len(fasce_subset)} fasce)")
    print()


def crea_subset_3_scuole():
    """Crea subset con 3 scuole e le loro classi"""

    print("="*60)
    print("Creazione subset ridotto - 3 SCUOLE")
    print("="*60)
    print()

    # Leggi dati completi
    scuole = pd.read_csv(INPUT_DIR / "scuole.csv")
    classi = pd.read_csv(INPUT_DIR / "classi.csv")
    formatrici = pd.read_csv(INPUT_DIR / "formatrici.csv")
    laboratori = pd.read_csv(INPUT_DIR / "laboratori.csv")
    fasce = pd.read_csv(INPUT_DIR / "fasce_orarie_scuole.csv")

    # Seleziona 3 scuole (prime 3)
    scuole_ids = scuole.head(3)['scuola_id'].tolist()

    scuole_subset = scuole[scuole['scuola_id'].isin(scuole_ids)].copy()
    classi_subset = classi[classi['scuola_id'].isin(scuole_ids)].copy()
    fasce_subset = fasce[fasce['scuola_id'].isin(scuole_ids)].copy()

    print(f"Subset creato:")
    print(f"  {len(scuole_subset)} scuole")
    print(f"  {len(classi_subset)} classi")
    print()

    # Salva (senza prefisso, solo suffisso)
    suffix = "_test3"
    scuole_subset.to_csv(INPUT_DIR / f"scuole{suffix}.csv", index=False)
    classi_subset.to_csv(INPUT_DIR / f"classi{suffix}.csv", index=False)
    formatrici.to_csv(INPUT_DIR / f"formatrici{suffix}.csv", index=False)
    laboratori.to_csv(INPUT_DIR / f"laboratori{suffix}.csv", index=False)
    fasce_subset.to_csv(INPUT_DIR / f"fasce_orarie_scuole{suffix}.csv", index=False)

    print("✅ File subset creati con suffisso '_test3'")
    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "3":
        crea_subset_3_scuole()
    else:
        crea_subset_1_scuola()
