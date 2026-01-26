#!/usr/bin/env python3
"""
Test solving Optimizer on a subset of schools (2 schools only).

This is a quick test to verify the solver works before running on full dataset.
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from optimizer import Optimizer


def create_subset_data(num_schools=2):
    """
    Crea un subset dei dati CSV con solo le prime N scuole.

    Returns:
        temp_dir: Directory temporanea con i CSV filtrati
    """
    import tempfile
    import shutil

    # Crea directory temporanea
    temp_dir = Path(tempfile.mkdtemp(prefix="cosmic_subset_"))

    # Directory input originale
    input_dir = Path("data/input")

    # Carica scuole e prendi le prime N
    scuole = pd.read_csv(input_dir / "scuole.csv")
    scuole_subset = scuole.head(num_schools)
    school_ids = set(scuole_subset['scuola_id'].values)

    print(f"\n📋 Scuole selezionate ({num_schools}):")
    for _, row in scuole_subset.iterrows():
        print(f"  - {row['nome']} (ID: {row['scuola_id']})")

    # Salva scuole
    scuole_subset.to_csv(temp_dir / "scuole.csv", index=False)

    # Filtra classi per le scuole selezionate
    classi = pd.read_csv(input_dir / "classi.csv")
    classi_subset = classi[classi['scuola_id'].isin(school_ids)]
    class_ids = set(classi_subset['classe_id'].values)
    classi_subset.to_csv(temp_dir / "classi.csv", index=False)

    print(f"\n📚 Classi incluse: {len(classi_subset)}")

    # Laboratori (tutti)
    shutil.copy(input_dir / "laboratori.csv", temp_dir / "laboratori.csv")

    # Laboratori_classi (solo per classi del subset)
    lab_classi = pd.read_csv(input_dir / "laboratori_classi.csv")
    lab_classi_subset = lab_classi[lab_classi['classe_id'].isin(class_ids)]
    lab_classi_subset.to_csv(temp_dir / "laboratori_classi.csv", index=False)

    print(f"🔬 Lab assignments: {len(lab_classi_subset)}")

    # Formatrici (tutte)
    shutil.copy(input_dir / "formatrici.csv", temp_dir / "formatrici.csv")

    # Formatrici_classi (solo per classi del subset)
    form_classi = pd.read_csv(input_dir / "formatrici_classi.csv")
    form_classi_subset = form_classi[form_classi['classe_id'].isin(class_ids)]
    form_classi_subset.to_csv(temp_dir / "formatrici_classi.csv", index=False)

    # Fasce orarie scuole (solo per scuole del subset)
    fasce_scuole = pd.read_csv(input_dir / "fasce_orarie_scuole.csv")
    fasce_scuole_subset = fasce_scuole[fasce_scuole['scuola_id'].isin(school_ids)]
    fasce_scuole_subset.to_csv(temp_dir / "fasce_orarie_scuole.csv", index=False)

    # Fasce orarie classi (solo per classi del subset)
    fasce_classi = pd.read_csv(input_dir / "fasce_orarie_classi.csv")
    fasce_classi_subset = fasce_classi[fasce_classi['classe_id'].isin(class_ids)]
    fasce_classi_subset.to_csv(temp_dir / "fasce_orarie_classi.csv", index=False)

    # Date escluse classi (solo per classi del subset)
    date_escluse = pd.read_csv(input_dir / "date_escluse_classi.csv")
    date_escluse_subset = date_escluse[date_escluse['classe_id'].isin(class_ids)]
    date_escluse_subset.to_csv(temp_dir / "date_escluse_classi.csv", index=False)

    print(f"\n✅ Dati subset creati in: {temp_dir}")

    return temp_dir


def main():
    """Test solving on subset"""
    print("=" * 80)
    print("  TEST SOLVING - Optimizer (2 Schools Subset)")
    print("=" * 80)

    # Crea subset dati
    temp_dir = create_subset_data(num_schools=2)

    try:
        # Crea optimizer con subset
        optimizer = Optimizer(
            input_dir=str(temp_dir),
            verbose=True
        )

        # Esegui ottimizzazione
        print("\n" + "=" * 80)
        print("  AVVIO OTTIMIZZAZIONE")
        print("=" * 80)

        success = optimizer.run(
            output_path="data/output/test_subset_solution.csv",
            time_limit=120  # 2 minuti timeout
        )

        if success:
            print("\n" + "=" * 80)
            print("  ✅ OTTIMIZZAZIONE COMPLETATA CON SUCCESSO!")
            print("=" * 80)

            # Mostra statistiche soluzione
            print("\n📊 Statistiche soluzione:")
            print(f"  - Incontri schedulati: {len(optimizer.variables.meetings)}")
            print(f"  - Variabili accorpamento: {len(optimizer.variables.accorpa)}")

            # Conta accorpamenti attivi
            if optimizer.solver.StatusName(optimizer.solver.Solve(optimizer.model)) in ["OPTIMAL", "FEASIBLE"]:
                accorpamenti_attivi = sum(
                    1 for var in optimizer.variables.accorpa.values()
                    if optimizer.solver.Value(var) == 1
                )
                print(f"  - Accorpamenti attivati: {accorpamenti_attivi}")

            return 0
        else:
            print("\n" + "=" * 80)
            print("  ❌ OTTIMIZZAZIONE FALLITA")
            print("=" * 80)
            return 1

    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup temp dir
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n🗑  Pulizia temp dir: {temp_dir}")


if __name__ == '__main__':
    sys.exit(main())
