#!/usr/bin/env python3
"""
Script di test per optimizer V2 con subset ridotto dei dati
"""

import pandas as pd
import sys
from pathlib import Path

# Aggiungi src al PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent / "src"))

from optimizer_v2 import LaboratoriOptimizerV2
from ortools.sat.python import cp_model

def test_con_subset(suffix="_test"):
    """Testa l'optimizer con un subset di dati"""

    print("\n" + "="*60)
    print(f"  TEST OPTIMIZER V2 - Subset{suffix}")
    print("="*60 + "\n")

    input_dir = "data/input"

    # Carica dati con suffisso
    try:
        scuole = pd.read_csv(f"{input_dir}/esempio_scuole{suffix}.csv")
        classi = pd.read_csv(f"{input_dir}/esempio_classi{suffix}.csv")
        formatrici = pd.read_csv(f"{input_dir}/esempio_formatrici{suffix}.csv")
        laboratori = pd.read_csv(f"{input_dir}/esempio_laboratori{suffix}.csv")
        fasce = pd.read_csv(f"{input_dir}/esempio_fasce_orarie_scuole{suffix}.csv")
    except FileNotFoundError as e:
        print(f"❌ File non trovato: {e}")
        print(f"Esegui prima: python create_test_subset.py")
        sys.exit(1)

    print(f"📂 Dati caricati:")
    print(f"  ✓ {len(scuole)} scuole")
    print(f"  ✓ {len(classi)} classi")
    print(f"  ✓ {len(formatrici)} formatrici")
    print(f"  ✓ {len(laboratori)} laboratori")
    print(f"  ✓ {len(fasce)} fasce orarie")
    print()

    # Crea optimizer
    optimizer = LaboratoriOptimizerV2(scuole, classi, formatrici, laboratori, fasce)

    # Costruisci modello
    optimizer.build_model()

    # Risolvi (timeout più breve per test)
    print("🔍 Risoluzione...")
    status = optimizer.solve(time_limit_seconds=60)

    # Esporta risultati
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        output_file = f"data/output/calendario_v2_test{suffix}.xlsx"
        optimizer.export_results(output_file)
        print(f"\n🎉 Test completato! Risultati salvati in: {output_file}\n")
    else:
        print("\n⚠️  Nessuna soluzione trovata nel tempo limite.\n")
        print("Possibili cause:")
        print("  - Vincoli troppo restrittivi")
        print("  - Risorse insufficienti (formatrici, fasce orarie)")
        print("  - Timeout troppo breve")
        print()
        sys.exit(1)


if __name__ == "__main__":
    suffix = sys.argv[1] if len(sys.argv) > 1 else "_test"
    test_con_subset(suffix)
