#!/usr/bin/env python3
"""
Optimizer V1 - Formatrici + Accorpamenti

Variabili:
- solo[classe, lab, formatrice, settimana] = classe fa lab da sola
- insieme[c1, c2, lab, formatrice, settimana] = due classi fanno lab insieme (c1 < c2)

Vincoli:
- H1: Ogni classe completa ogni lab (fonte: laboratori_classi.csv)
- H2: Max 1 incontro/settimana per classe (fonte: criteri.xlsx riga 25)
- Budget ore TOTALI per formatrice (gli incontri 'insieme' contano 1 volta)

Nota: accorpamenti preferenziali da classi.csv (max 2 classi insieme, stessa scuola)
"""

import pandas as pd
from ortools.sat.python import cp_model
from pathlib import Path
from collections import defaultdict
import sys


class DataLoaderV1:
    """Carica dati incluse formatrici e accorpamenti"""

    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)

    def load_all(self):
        """Carica CSV"""
        print(f"Caricamento dati da: {self.input_dir}")

        self.scuole = pd.read_csv(self.input_dir / "scuole.csv")
        self.classi = pd.read_csv(self.input_dir / "classi.csv")
        self.laboratori = pd.read_csv(self.input_dir / "laboratori.csv")
        self.laboratori_classi = pd.read_csv(self.input_dir / "laboratori_classi.csv")
        self.formatrici = pd.read_csv(self.input_dir / "formatrici.csv")
        self.formatrici_classi = pd.read_csv(self.input_dir / "formatrici_classi.csv")

        print(f"  {len(self.scuole)} scuole")
        print(f"  {len(self.classi)} classi")
        print(f"  {len(self.laboratori)} laboratori")
        print(f"  {len(self.laboratori_classi)} combinazioni lab-classe")
        print(f"  {len(self.formatrici)} formatrici")

        # Conta accorpamenti
        n_acc = self.classi['accorpamento_preferenziale'].notna().sum()
        print(f"  {n_acc} classi con accorpamento preferenziale")
        print()

        return self


class OptimizerV1:
    """Optimizer con formatrici e accorpamenti"""

    NUM_SETTIMANE = 15

    def __init__(self, data: DataLoaderV1):
        self.data = data
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Variabili
        self.solo = {}      # (classe, lab, formatrice, settimana) -> BoolVar
        self.insieme = {}   # (c1, c2, lab, formatrice, settimana) -> BoolVar (c1 < c2)

    def build_model(self):
        """Costruisce il modello"""
        print("Costruzione modello V1 con accorpamenti...")

        # Lab validi (solo quelli in laboratori.csv, esclusi GSSI/GST/LNGS)
        lab_ids_validi = set(self.data.laboratori['laboratorio_id'].values)

        # Prepara mapping: quali lab deve fare ogni classe (solo lab validi)
        labs_per_classe = defaultdict(list)
        for _, row in self.data.laboratori_classi.iterrows():
            if row['laboratorio_id'] in lab_ids_validi:
                labs_per_classe[row['classe_id']].append(row['laboratorio_id'])

        # Prepara mapping: TUTTE le coppie di classi della stessa scuola (c1 < c2)
        # Qualsiasi coppia della stessa scuola può essere accorpata
        coppie_accorpamento = set()
        classi_per_scuola = defaultdict(list)
        for _, row in self.data.classi.iterrows():
            classi_per_scuola[row['scuola_id']].append(row['classe_id'])

        for scuola_id, classi_scuola in classi_per_scuola.items():
            # Genera tutte le coppie possibili per questa scuola
            for i, c1 in enumerate(classi_scuola):
                for c2 in classi_scuola[i+1:]:
                    coppie_accorpamento.add((c1, c2))

        print(f"  Coppie accorpamento possibili (stessa scuola): {len(coppie_accorpamento)}")

        # Mappa classe -> possibili partner
        partner_per_classe = defaultdict(set)
        for c1, c2 in coppie_accorpamento:
            partner_per_classe[c1].add(c2)
            partner_per_classe[c2].add(c1)

        # Lista formatrici
        tutte_formatrici = list(self.data.formatrici['formatrice_id'].astype(int))

        # Ore per incontro per laboratorio
        ore_per_lab = {}
        for _, lab in self.data.laboratori.iterrows():
            ore_per_lab[lab['laboratorio_id']] = int(lab['ore_per_incontro'])

        # Numero incontri per laboratorio
        num_incontri_lab = {}
        for _, lab in self.data.laboratori.iterrows():
            num_incontri_lab[lab['laboratorio_id']] = int(lab['num_incontri'])

        # ===================
        # CREA VARIABILI
        # ===================
        print("  Creazione variabili...")
        n_solo = 0
        n_insieme = 0

        for classe_id in labs_per_classe.keys():
            for lab_id in labs_per_classe[classe_id]:
                for formatrice_id in tutte_formatrici:
                    for settimana in range(self.NUM_SETTIMANE):
                        # Variabile 'solo'
                        var_name = f"solo_c{classe_id}_l{lab_id}_f{formatrice_id}_w{settimana}"
                        self.solo[(classe_id, lab_id, formatrice_id, settimana)] = \
                            self.model.NewBoolVar(var_name)
                        n_solo += 1

        # Variabili 'insieme' solo per coppie valide
        for c1, c2 in coppie_accorpamento:
            # Trova lab comuni alle due classi
            labs_c1 = set(labs_per_classe[c1])
            labs_c2 = set(labs_per_classe[c2])
            labs_comuni = labs_c1 & labs_c2

            for lab_id in labs_comuni:
                for formatrice_id in tutte_formatrici:
                    for settimana in range(self.NUM_SETTIMANE):
                        var_name = f"insieme_c{c1}_c{c2}_l{lab_id}_f{formatrice_id}_w{settimana}"
                        self.insieme[(c1, c2, lab_id, formatrice_id, settimana)] = \
                            self.model.NewBoolVar(var_name)
                        n_insieme += 1

        print(f"    Variabili 'solo': {n_solo:,}")
        print(f"    Variabili 'insieme': {n_insieme:,}")
        print(f"    Totale: {n_solo + n_insieme:,}")

        # ===================
        # VINCOLI
        # ===================

        # VINCOLO H1: Ogni classe completa ogni lab
        print("  Vincolo H1: completamento laboratori")
        for classe_id, labs in labs_per_classe.items():
            partners = partner_per_classe.get(classe_id, set())

            for lab_id in labs:
                num_incontri = num_incontri_lab.get(lab_id, 1)

                # Somma: incontri da sola + incontri insieme
                vars_totali = []

                # Incontri da sola
                for formatrice_id in tutte_formatrici:
                    for w in range(self.NUM_SETTIMANE):
                        key = (classe_id, lab_id, formatrice_id, w)
                        if key in self.solo:
                            vars_totali.append(self.solo[key])

                # Incontri insieme (con ogni possibile partner)
                for partner_id in partners:
                    # Verifica che il partner faccia lo stesso lab
                    if lab_id not in labs_per_classe[partner_id]:
                        continue

                    coppia = tuple(sorted([classe_id, partner_id]))
                    for formatrice_id in tutte_formatrici:
                        for w in range(self.NUM_SETTIMANE):
                            key = (*coppia, lab_id, formatrice_id, w)
                            if key in self.insieme:
                                vars_totali.append(self.insieme[key])

                if vars_totali:
                    self.model.Add(sum(vars_totali) == num_incontri)

        # VINCOLO H2: Max 1 incontro per settimana per classe
        print("  Vincolo H2: max 1 incontro/settimana per classe")
        for classe_id in labs_per_classe.keys():
            partners = partner_per_classe.get(classe_id, set())

            for settimana in range(self.NUM_SETTIMANE):
                vars_settimana = []

                # Incontri da sola
                for lab_id in labs_per_classe[classe_id]:
                    for formatrice_id in tutte_formatrici:
                        key = (classe_id, lab_id, formatrice_id, settimana)
                        if key in self.solo:
                            vars_settimana.append(self.solo[key])

                # Incontri insieme
                for partner_id in partners:
                    coppia = tuple(sorted([classe_id, partner_id]))
                    for lab_id in labs_per_classe[classe_id]:
                        if lab_id not in labs_per_classe.get(partner_id, []):
                            continue
                        for formatrice_id in tutte_formatrici:
                            key = (*coppia, lab_id, formatrice_id, settimana)
                            if key in self.insieme:
                                vars_settimana.append(self.insieme[key])

                if vars_settimana:
                    self.model.Add(sum(vars_settimana) <= 1)

        # VINCOLO: Budget ore TOTALI per formatrice
        ORE_GENERALI = {
            1: 292,   # Anita
            2: 128,   # Andreea
            3: 160,   # Ida
            4: 128,   # Margherita
        }
        print("  Vincolo: budget ore totali formatrice")
        for _, formatrice in self.data.formatrici.iterrows():
            formatrice_id = int(formatrice['formatrice_id'])
            ore_max_totali = ORE_GENERALI.get(formatrice_id, 100)

            # Somma ore: 'solo' + 'insieme' (insieme conta 1 volta, non 2)
            ore_totali = []

            # Ore da incontri 'solo'
            for key, var in self.solo.items():
                if key[2] == formatrice_id:
                    lab_id = key[1]
                    ore = ore_per_lab.get(lab_id, 2)
                    ore_totali.append(ore * var)

            # Ore da incontri 'insieme' (conta 1 volta!)
            for key, var in self.insieme.items():
                if key[3] == formatrice_id:  # formatrice_id è in posizione 3
                    lab_id = key[2]  # lab_id è in posizione 2
                    ore = ore_per_lab.get(lab_id, 2)
                    ore_totali.append(ore * var)

            if ore_totali:
                self.model.Add(sum(ore_totali) <= ore_max_totali)
                print(f"    {formatrice['nome']}: max {ore_max_totali} ore")

        print("  Modello V1 costruito!")
        print()

    def solve(self, time_limit_seconds: int = 120):
        """Risolve il modello"""
        print(f"Avvio solver (timeout: {time_limit_seconds}s)...")

        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.log_search_progress = False
        self.solver.parameters.num_search_workers = 8

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

        # Incontri 'solo'
        for key, var in self.solo.items():
            if self.solver.Value(var) == 1:
                classe_id, lab_id, formatrice_id, settimana = key

                classe_row = self.data.classi[self.data.classi['classe_id'] == classe_id].iloc[0]
                lab_df = self.data.laboratori[self.data.laboratori['laboratorio_id'] == lab_id]
                if len(lab_df) == 0:
                    print(f"  WARN: lab_id {lab_id} non trovato, skip")
                    continue
                lab_row = lab_df.iloc[0]
                scuola_row = self.data.scuole[self.data.scuole['scuola_id'] == classe_row['scuola_id']].iloc[0]
                formatrice_row = self.data.formatrici[self.data.formatrici['formatrice_id'] == formatrice_id].iloc[0]

                risultati.append({
                    'settimana': settimana + 1,
                    'tipo': 'solo',
                    'classe_id': classe_id,
                    'classe': classe_row['nome'],
                    'classe2_id': None,
                    'classe2': None,
                    'scuola': scuola_row['nome'],
                    'lab_id': lab_id,
                    'laboratorio': lab_row['nome'],
                    'formatrice_id': formatrice_id,
                    'formatrice': formatrice_row['nome'],
                    'ore': lab_row['ore_per_incontro'],
                })

        # Incontri 'insieme'
        for key, var in self.insieme.items():
            if self.solver.Value(var) == 1:
                c1, c2, lab_id, formatrice_id, settimana = key

                classe1_row = self.data.classi[self.data.classi['classe_id'] == c1].iloc[0]
                classe2_row = self.data.classi[self.data.classi['classe_id'] == c2].iloc[0]
                lab_df = self.data.laboratori[self.data.laboratori['laboratorio_id'] == lab_id]
                if len(lab_df) == 0:
                    print(f"  WARN: lab_id {lab_id} non trovato, skip")
                    continue
                lab_row = lab_df.iloc[0]
                scuola_row = self.data.scuole[self.data.scuole['scuola_id'] == classe1_row['scuola_id']].iloc[0]
                formatrice_row = self.data.formatrici[self.data.formatrici['formatrice_id'] == formatrice_id].iloc[0]

                risultati.append({
                    'settimana': settimana + 1,
                    'tipo': 'insieme',
                    'classe_id': c1,
                    'classe': classe1_row['nome'],
                    'classe2_id': c2,
                    'classe2': classe2_row['nome'],
                    'scuola': scuola_row['nome'],
                    'lab_id': lab_id,
                    'laboratorio': lab_row['nome'],
                    'formatrice_id': formatrice_id,
                    'formatrice': formatrice_row['nome'],
                    'ore': lab_row['ore_per_incontro'],
                })

        df = pd.DataFrame(risultati)
        df = df.sort_values(['formatrice', 'settimana', 'scuola', 'classe'])

        # Salva CSV
        df.to_csv(output_path, index=False)
        print(f"  Salvati {len(df)} incontri")

        # Statistiche
        n_solo = len(df[df['tipo'] == 'solo'])
        n_insieme = len(df[df['tipo'] == 'insieme'])
        print(f"    - {n_solo} incontri singoli")
        print(f"    - {n_insieme} incontri accorpati (2 classi)")

        ORE_GENERALI = {1: 292, 2: 128, 3: 160, 4: 128}
        print()
        print("STATISTICHE PER FORMATRICE:")
        print("-" * 60)
        for _, formatrice in self.data.formatrici.iterrows():
            nome = formatrice['nome']
            formatrice_id = int(formatrice['formatrice_id'])
            ore_budget = ORE_GENERALI.get(formatrice_id, 100)
            df_f = df[df['formatrice'] == nome]
            ore_totali = df_f['ore'].sum()
            num_incontri = len(df_f)

            print(f"  {nome:12} | {ore_totali:3.0f}/{ore_budget} ore | {num_incontri:3} incontri")
        print("-" * 60)
        print(f"\nTotale incontri: {len(df)}")
        print(f"Ore totali erogate: {df['ore'].sum()}")


def main():
    print()
    print("=" * 60)
    print("  OPTIMIZER V1 - Formatrici + Accorpamenti")
    print("=" * 60)
    print()

    input_dir = "data/input"
    output_file = "data/output/calendario_V1.csv"

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    try:
        data = DataLoaderV1(input_dir).load_all()
    except FileNotFoundError as e:
        print(f"Errore: {e}")
        sys.exit(1)

    optimizer = OptimizerV1(data)
    optimizer.build_model()

    status = optimizer.solve(time_limit_seconds=120)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        optimizer.export_results(output_file)
        print()
        print("Ottimizzazione V1 completata!")
    else:
        print("Ottimizzazione fallita.")
        sys.exit(1)


if __name__ == "__main__":
    main()
