#!/usr/bin/env python3
"""
Optimizer V0 - Minimo Assoluto

Variabili: assignment[classe_id, lab_id, settimana]

Vincoli (con fonti):
- H1: Ogni classe completa ogni lab (fonte: laboratori_classi.csv)
- H2: Max 1 incontro/settimana per classe (fonte: criteri.xlsx riga 25)
- Periodo: 14 settimane effettive (fonte: criteri.xlsx righe 33-34)
  - Blocco 1: 28/1/2026 - 1/4/2026 (settimane 0-9)
  - GAP Pasqua: 2/4 - 12/4/2026
  - Blocco 2: 13/4/2026 - 16/5/2026 (settimane 10-14)

Semplificazioni:
- Ignora formatrici
- Ignora fasce orarie
- Ignora giorni specifici
"""

import pandas as pd
from ortools.sat.python import cp_model
from pathlib import Path
from collections import defaultdict
import sys


class DataLoaderV0:
    """Carica solo i dati minimi necessari"""

    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)

    def load_all(self):
        """Carica CSV essenziali"""
        print(f"Caricamento dati da: {self.input_dir}")

        self.scuole = pd.read_csv(self.input_dir / "scuole.csv")
        self.classi = pd.read_csv(self.input_dir / "classi.csv")
        self.laboratori = pd.read_csv(self.input_dir / "laboratori.csv")
        self.laboratori_classi = pd.read_csv(self.input_dir / "laboratori_classi.csv")

        print(f"  {len(self.scuole)} scuole")
        print(f"  {len(self.classi)} classi")
        print(f"  {len(self.laboratori)} laboratori")
        print(f"  {len(self.laboratori_classi)} combinazioni lab-classe")
        print()

        return self


class OptimizerV0:
    """Optimizer minimo: solo completamento lab + max 1/settimana"""

    # 15 settimane effettive (fonte: criteri.xlsx righe 33-34)
    # Blocco 1: settimane 0-9 (28/1 - 1/4/2026)
    # GAP Pasqua: 2/4 - 12/4/2026
    # Blocco 2: settimane 10-14 (13/4 - 16/5/2026)
    NUM_SETTIMANE = 15

    def __init__(self, data: DataLoaderV0):
        self.data = data
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.assignments = {}  # (classe_id, lab_id, settimana) -> BoolVar

    def build_model(self):
        """Costruisce il modello"""
        print("Costruzione modello V0...")

        # Prepara mapping: quali lab deve fare ogni classe
        labs_per_classe = defaultdict(list)
        for _, row in self.data.laboratori_classi.iterrows():
            labs_per_classe[row['classe_id']].append(row['laboratorio_id'])

        # Crea variabili
        n_vars = 0
        for classe_id in labs_per_classe.keys():
            for lab_id in labs_per_classe[classe_id]:
                for settimana in range(self.NUM_SETTIMANE):
                    var_name = f"c{classe_id}_l{lab_id}_w{settimana}"
                    self.assignments[(classe_id, lab_id, settimana)] = \
                        self.model.NewBoolVar(var_name)
                    n_vars += 1

        print(f"  Create {n_vars:,} variabili")

        # VINCOLO V0.1: Ogni classe completa ogni lab
        print("  Vincolo V0.1: completamento laboratori")
        for classe_id, labs in labs_per_classe.items():
            for lab_id in labs:
                # Trova num_incontri per questo lab
                lab_row = self.data.laboratori[
                    self.data.laboratori['laboratorio_id'] == lab_id
                ]
                if len(lab_row) == 0:
                    continue
                num_incontri = int(lab_row.iloc[0]['num_incontri'])

                # Somma delle settimane assegnate == num_incontri
                vars_lab = [
                    self.assignments[(classe_id, lab_id, w)]
                    for w in range(self.NUM_SETTIMANE)
                ]
                self.model.Add(sum(vars_lab) == num_incontri)

        # VINCOLO V1.1: Max 1 incontro per settimana per classe
        print("  Vincolo V1.1: max 1 incontro/settimana per classe")
        for classe_id in labs_per_classe.keys():
            for settimana in range(self.NUM_SETTIMANE):
                vars_settimana = [
                    self.assignments[(classe_id, lab_id, settimana)]
                    for lab_id in labs_per_classe[classe_id]
                    if (classe_id, lab_id, settimana) in self.assignments
                ]
                if vars_settimana:
                    self.model.Add(sum(vars_settimana) <= 1)

        print("  Modello V0 costruito!")
        print()

    def solve(self, time_limit_seconds: int = 60):
        """Risolve il modello"""
        print(f"Avvio solver (timeout: {time_limit_seconds}s)...")

        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.log_search_progress = False

        status = self.solver.Solve(self.model)

        if status == cp_model.OPTIMAL:
            print("SOLUZIONE OTTIMALE TROVATA!")
        elif status == cp_model.FEASIBLE:
            print("SOLUZIONE AMMISSIBILE TROVATA")
        else:
            print(f"NESSUNA SOLUZIONE (status: {self.solver.StatusName()})")
            return None

        print(f"Tempo: {self.solver.WallTime():.2f}s")
        print()
        return status

    def export_results(self, output_path: str):
        """Esporta risultati in CSV"""
        if self.solver.StatusName() not in ['OPTIMAL', 'FEASIBLE']:
            print("Nessuna soluzione da esportare")
            return

        print(f"Esportazione risultati in: {output_path}")

        risultati = []
        for (classe_id, lab_id, settimana), var in self.assignments.items():
            if self.solver.Value(var) == 1:
                # Lookup nomi
                classe_row = self.data.classi[
                    self.data.classi['classe_id'] == classe_id
                ].iloc[0]
                lab_row = self.data.laboratori[
                    self.data.laboratori['laboratorio_id'] == lab_id
                ].iloc[0]
                scuola_row = self.data.scuole[
                    self.data.scuole['scuola_id'] == classe_row['scuola_id']
                ].iloc[0]

                risultati.append({
                    'settimana': settimana + 1,
                    'classe_id': classe_id,
                    'classe': classe_row['nome'],
                    'scuola': scuola_row['nome'],
                    'lab_id': lab_id,
                    'laboratorio': lab_row['nome'],
                    'num_incontri_lab': lab_row['num_incontri'],
                })

        df = pd.DataFrame(risultati)
        df = df.sort_values(['scuola', 'classe', 'settimana'])

        # Salva CSV
        df.to_csv(output_path, index=False)
        print(f"  Salvati {len(df)} incontri")

        # Statistiche
        print()
        print("STATISTICHE:")
        print(f"  Incontri totali: {len(df)}")
        print(f"  Classi: {df['classe_id'].nunique()}")
        print(f"  Settimane usate: {df['settimana'].nunique()}")

        # Verifica completamento
        print()
        print("VERIFICA COMPLETAMENTO:")
        for lab_id in df['lab_id'].unique():
            lab_nome = df[df['lab_id'] == lab_id]['laboratorio'].iloc[0]
            incontri_per_classe = df[df['lab_id'] == lab_id].groupby('classe_id').size()
            print(f"  {lab_nome}: {incontri_per_classe.mean():.1f} incontri/classe (attesi: {df[df['lab_id'] == lab_id]['num_incontri_lab'].iloc[0]})")


def main():
    print()
    print("=" * 50)
    print("  OPTIMIZER V0 - Minimo Assoluto")
    print("=" * 50)
    print()

    input_dir = "data/input"
    output_file = "data/output/calendario_V0.csv"

    # Crea directory output se non esiste
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    try:
        data = DataLoaderV0(input_dir).load_all()
    except FileNotFoundError as e:
        print(f"Errore: {e}")
        sys.exit(1)

    optimizer = OptimizerV0(data)
    optimizer.build_model()

    status = optimizer.solve(time_limit_seconds=60)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        optimizer.export_results(output_file)
        print()
        print("Ottimizzazione V0 completata!")
    else:
        print("Ottimizzazione fallita.")
        sys.exit(1)


if __name__ == "__main__":
    main()
