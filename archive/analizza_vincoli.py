#!/usr/bin/env python3
"""
Analizza i vincoli dai nuovi CSV per capire la complessità
"""

import pandas as pd
from pathlib import Path

INPUT_DIR = Path("data/input")


def analizza_laboratori_classi():
    """Analizza quali laboratori fa ogni classe"""
    print("="*60)
    print("LABORATORI PER CLASSE")
    print("="*60)

    df = pd.read_csv(INPUT_DIR / "laboratori_classi.csv")

    # Conta laboratori per classe
    lab_per_classe = df.groupby('classe_id').size()

    print(f"\nTotale righe: {len(df)}")
    print(f"Classi uniche: {df['classe_id'].nunique()}")
    print(f"Laboratori unici: {df['laboratorio_id'].nunique()}")
    print(f"\nMedia laboratori per classe: {lab_per_classe.mean():.1f}")
    print(f"Min laboratori per classe: {lab_per_classe.min()}")
    print(f"Max laboratori per classe: {lab_per_classe.max()}")

    # Date già fissate
    date_fissate = df[df['date_fissate'].notna()]
    print(f"\nClassi con date già fissate: {len(date_fissate)}")

    if len(date_fissate) > 0:
        print("\nEsempi date fissate:")
        for _, row in date_fissate.head(5).iterrows():
            print(f"  Classe {row['nome_classe']} - Lab {row['laboratorio_id']}: {row['date_fissate']}")


def analizza_formatrici_classi():
    """Analizza assegnamenti formatrici-classi"""
    print("\n" + "="*60)
    print("ASSEGNAMENTI FORMATRICI-CLASSI")
    print("="*60)

    df = pd.read_csv(INPUT_DIR / "formatrici_classi.csv")

    print(f"\nTotale assegnamenti: {len(df)}")
    print(f"Classi coperte: {df['classe_id'].nunique()}")
    print(f"Formatrici coinvolte: {df['formatrice_id'].nunique()}")

    # Classi per formatrice
    classi_per_formatrice = df.groupby('nome_formatrice')['classe_id'].nunique()
    print("\nClassi per formatrice:")
    for nome, n_classi in classi_per_formatrice.items():
        print(f"  {nome}: {n_classi} classi")

    # Verifica se ci sono classi senza assegnamento
    classi_totali = pd.read_csv(INPUT_DIR / "classi.csv")
    classi_senza_formatrice = set(classi_totali['classe_id']) - set(df['classe_id'])

    if classi_senza_formatrice:
        print(f"\n⚠️  {len(classi_senza_formatrice)} classi SENZA formatrice assegnata!")
        print(f"    Classi IDs: {sorted(list(classi_senza_formatrice))[:10]}...")


def analizza_date_escluse():
    """Analizza date escluse per classe"""
    print("\n" + "="*60)
    print("DATE ESCLUSE PER CLASSE")
    print("="*60)

    df = pd.read_csv(INPUT_DIR / "date_escluse_classi.csv")

    print(f"\nClassi con date escluse: {len(df)}")

    # Tipologie di date escluse
    print("\nEsempi formati date escluse:")
    for _, row in df.head(5).iterrows():
        print(f"  Classe {row['nome_classe']}: {row['date_escluse']}")


def analizza_fasce_orarie_classi():
    """Analizza fasce orarie specifiche per classe"""
    print("\n" + "="*60)
    print("FASCE ORARIE PER CLASSE")
    print("="*60)

    df = pd.read_csv(INPUT_DIR / "fasce_orarie_classi.csv")

    print(f"\nTotale classi: {len(df)}")

    # Conta fasce per classe
    def conta_fasce(fasce_str):
        if pd.isna(fasce_str):
            return 0
        # Conta newline o virgole
        if '\n' in str(fasce_str):
            return len(str(fasce_str).split('\n'))
        elif ',' in str(fasce_str):
            return len(str(fasce_str).split(','))
        return 1

    df['n_fasce'] = df['fasce_disponibili'].apply(conta_fasce)

    print(f"\nMedia fasce disponibili per classe: {df['n_fasce'].mean():.1f}")
    print(f"Min fasce: {df['n_fasce'].min()}")
    print(f"Max fasce: {df['n_fasce'].max()}")

    # Classi con poche fasce (vincolo restrittivo)
    classi_poche_fasce = df[df['n_fasce'] <= 3]
    print(f"\nClassi con ≤3 fasce disponibili: {len(classi_poche_fasce)}")

    if len(classi_poche_fasce) > 0:
        print("\nEsempi:")
        for _, row in classi_poche_fasce.head(5).iterrows():
            print(f"  Classe {row['nome_classe']}: {row['n_fasce']} fasce - {row['fasce_disponibili']}")


def calcola_ore_richieste():
    """Calcola ore totali richieste vs disponibili"""
    print("\n" + "="*60)
    print("BILANCIAMENTO ORE")
    print("="*60)

    laboratori_classi = pd.read_csv(INPUT_DIR / "laboratori_classi.csv")
    laboratori = pd.read_csv(INPUT_DIR / "laboratori.csv")
    formatrici = pd.read_csv(INPUT_DIR / "formatrici.csv")

    # Merge per avere ore_per_incontro e num_incontri
    merged = laboratori_classi.merge(
        laboratori[['laboratorio_id', 'num_incontri', 'ore_per_incontro']],
        on='laboratorio_id'
    )

    # Ore totali richieste
    ore_totali = (merged['num_incontri'] * merged['ore_per_incontro']).sum()

    # Ore disponibili formatrici
    ore_disponibili = formatrici['ore_settimanali_max'].sum() * 20  # 20 settimane

    print(f"\nOre totali richieste: {ore_totali:.0f} ore")
    print(f"Ore disponibili formatrici: {ore_disponibili:.0f} ore (4 formatrici × ~20 sett)")
    print(f"Rapporto: {ore_totali/ore_disponibili*100:.1f}%")

    if ore_totali > ore_disponibili:
        print(f"\n⚠️  PROBLEMA: Mancano {ore_totali - ore_disponibili:.0f} ore!")
    else:
        print(f"\n✅ OK: {ore_disponibili - ore_totali:.0f} ore di margine")


def main():
    """Analisi completa vincoli"""

    print("\n" + "="*60)
    print("ANALISI VINCOLI CALENDARIO V2")
    print("="*60 + "\n")

    analizza_laboratori_classi()
    analizza_formatrici_classi()
    analizza_date_escluse()
    analizza_fasce_orarie_classi()
    calcola_ore_richieste()

    print("\n" + "="*60)
    print("RIEPILOGO")
    print("="*60)

    classi = pd.read_csv(INPUT_DIR / "classi.csv")
    laboratori = pd.read_csv(INPUT_DIR / "laboratori.csv")
    formatrici = pd.read_csv(INPUT_DIR / "formatrici.csv")

    print(f"\n📊 Dimensioni problema:")
    print(f"  • {len(classi)} classi")
    print(f"  • {len(laboratori)} laboratori (solo formatrici)")
    print(f"  • {len(formatrici)} formatrici")
    print(f"  • 20 settimane")
    print(f"  • ~12 fasce orarie medie per scuola")

    print(f"\n🔒 Vincoli critici:")
    print(f"  • Assegnamenti formatrice-classe: HARD")
    print(f"  • Laboratori specifici per classe: HARD")
    print(f"  • Date già fissate: HARD")
    print(f"  • Date escluse: HARD")
    print(f"  • Fasce orarie limitate: HARD")

    print()


if __name__ == "__main__":
    main()
