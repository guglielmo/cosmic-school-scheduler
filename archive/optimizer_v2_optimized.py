#!/usr/bin/env python3
"""
Ottimizzatore V2 OTTIMIZZATO per performance e parallelizzazione
- Usa 16 core durante solving
- Pre-calcola indici per evitare cicli su tutti gli assignments
- Semplifica costruzione vincoli
"""

import pandas as pd
from ortools.sat.python import cp_model
from typing import Dict, List, Tuple
import sys
from collections import defaultdict
from export_formatter import esporta_formato_richiesto


class LaboratoriOptimizerV2Optimized:
    """Ottimizzatore V2 con performance ottimizzate."""

    def __init__(self,
                 scuole_df: pd.DataFrame,
                 classi_df: pd.DataFrame,
                 formatrici_df: pd.DataFrame,
                 laboratori_df: pd.DataFrame,
                 fasce_orarie_scuole_df: pd.DataFrame):
        self.scuole = scuole_df
        self.classi = classi_df
        self.formatrici = formatrici_df
        self.laboratori = laboratori_df
        self.fasce_orarie_scuole = fasce_orarie_scuole_df

        self.model = cp_model.CpModel()
        self.assignments = {}  # [classe, lab, formatrice, settimana, giorno, fascia]

        # Indici pre-calcolati per velocizzare i vincoli
        self.assignments_by_classe = defaultdict(list)
        self.assignments_by_classe_settimana = defaultdict(list)
        self.assignments_by_formatrice_slot = defaultdict(list)
        self.assignments_by_classe_lab = defaultdict(list)

        self.solver = cp_model.CpSolver()

    def build_model(self):
        """Costruisce il modello con vincoli ottimizzati."""

        print("📊 Costruzione del modello ottimizzato...")

        num_settimane = 20
        giorni_settimana = ['lun', 'mar', 'mer', 'gio', 'ven']

        # FASE 1: Creazione variabili
        print("  • Creazione variabili di decisione...")
        n_vars = 0

        for _, classe in self.classi.iterrows():
            scuola_id = classe['scuola_id']
            scuola = self.scuole[self.scuole['scuola_id'] == scuola_id].iloc[0]
            fasce_scuola = self.fasce_orarie_scuole[self.fasce_orarie_scuole['scuola_id'] == scuola_id]

            for _, lab in self.laboratori.iterrows():
                for _, formatrice in self.formatrici.iterrows():
                    for settimana in range(num_settimane):
                        for giorno in giorni_settimana:
                            # Filtra giorni non disponibili
                            giorni_disp = str(formatrice['giorni_disponibili']).split(',')
                            if giorno not in giorni_disp:
                                continue

                            for _, fascia in fasce_scuola.iterrows():
                                # Filtra fasce incompatibili con preferenza scuola
                                preferenza_scuola = scuola['preferenza_orario']
                                tipo_fascia = fascia['tipo_giornata']

                                if preferenza_scuola == 'mattina' and tipo_fascia != 'mattina':
                                    continue
                                if preferenza_scuola == 'pomeriggio' and tipo_fascia != 'pomeriggio':
                                    continue

                                # Crea variabile
                                var_name = f"c{classe['classe_id']}_l{lab['laboratorio_id']}_f{formatrice['formatrice_id']}_w{settimana}_d{giorno}_fa{fascia['fascia_id']}"
                                var = self.model.NewBoolVar(var_name)

                                key = (
                                    classe['classe_id'],
                                    lab['laboratorio_id'],
                                    formatrice['formatrice_id'],
                                    settimana,
                                    giorno,
                                    fascia['fascia_id']
                                )

                                self.assignments[key] = var
                                n_vars += 1

                                # Pre-calcola indici per velocizzare vincoli
                                self.assignments_by_classe[classe['classe_id']].append(key)
                                self.assignments_by_classe_settimana[(classe['classe_id'], settimana)].append(key)
                                self.assignments_by_formatrice_slot[(formatrice['formatrice_id'], settimana, giorno, fascia['fascia_id'])].append(key)
                                self.assignments_by_classe_lab[(classe['classe_id'], lab['laboratorio_id'])].append(key)

        print(f"  ✓ Create {n_vars:,} variabili (con filtri ottimizzati)")

        # VINCOLO 1: Ogni classe completa tutti i laboratori
        print("  ✓ Vincolo: ogni classe completa tutti i laboratori")
        for _, classe in self.classi.iterrows():
            for _, lab in self.laboratori.iterrows():
                keys = self.assignments_by_classe_lab[(classe['classe_id'], lab['laboratorio_id'])]
                if keys:
                    self.model.Add(sum(self.assignments[k] for k in keys) == lab['num_incontri'])

        # VINCOLO 2: Max 1 incontro per classe per settimana
        print("  ✓ Vincolo: max 1 incontro/settimana per classe")
        for (classe_id, settimana), keys in self.assignments_by_classe_settimana.items():
            self.model.Add(sum(self.assignments[k] for k in keys) <= 1)

        # VINCOLO 3: No sovrapposizioni formatrici (OTTIMIZZATO)
        print("  ✓ Vincolo: no sovrapposizioni formatrici (ottimizzato)")
        for slot_key, keys in self.assignments_by_formatrice_slot.items():
            if len(keys) > 1:  # Solo se ci sono conflitti possibili
                self.model.Add(sum(self.assignments[k] for k in keys) <= 1)

        # VINCOLO 4: Sequenzialità laboratori (semplificata)
        print("  ✓ Vincolo: sequenzialità laboratori")
        for _, classe in self.classi.iterrows():
            for idx in range(len(self.laboratori) - 1):
                lab_corrente = self.laboratori.iloc[idx]
                lab_successivo = self.laboratori.iloc[idx + 1]

                min_settimana_start = int(lab_corrente['num_incontri'])

                for settimana in range(min_settimana_start):
                    keys = [k for k in self.assignments_by_classe_lab[(classe['classe_id'], lab_successivo['laboratorio_id'])]
                           if k[3] == settimana]
                    for key in keys:
                        self.model.Add(self.assignments[key] == 0)

        # OBIETTIVO: minimizza cambi formatrice + penalizza stessa fascia consecutiva
        print("  ✓ Definizione funzione obiettivo")
        penalita_totale = []

        # Penalità cambio formatrice (OTTIMIZZATA)
        for _, classe in self.classi.iterrows():
            for _, lab in self.laboratori.iterrows():
                keys_lab = self.assignments_by_classe_lab[(classe['classe_id'], lab['laboratorio_id'])]

                # Raggruppa per formatrice
                by_formatrice = defaultdict(list)
                for k in keys_lab:
                    by_formatrice[k[2]].append(k)

                formatrici_ids = list(by_formatrice.keys())
                for i, f1 in enumerate(formatrici_ids):
                    for f2 in formatrici_ids[i+1:]:
                        if by_formatrice[f1] and by_formatrice[f2]:
                            cambio = self.model.NewBoolVar(f"cambio_c{classe['classe_id']}_l{lab['laboratorio_id']}_f{f1}_f{f2}")
                            self.model.Add(sum(self.assignments[k] for k in by_formatrice[f1]) >= 1).OnlyEnforceIf(cambio)
                            self.model.Add(sum(self.assignments[k] for k in by_formatrice[f2]) >= 1).OnlyEnforceIf(cambio)
                            penalita_totale.append(10 * cambio)

        # Penalità stessa fascia in settimane consecutive
        fasce_uniche = self.fasce_orarie_scuole['fascia_id'].unique()
        for _, classe in self.classi.iterrows():
            for sett in range(num_settimane - 1):
                for fascia_id in fasce_uniche:
                    keys_questa = [k for k in self.assignments_by_classe_settimana[(classe['classe_id'], sett)]
                                  if k[5] == fascia_id]
                    keys_prossima = [k for k in self.assignments_by_classe_settimana[(classe['classe_id'], sett + 1)]
                                    if k[5] == fascia_id]

                    if keys_questa and keys_prossima:
                        stessa_fascia = self.model.NewBoolVar(f"stessa_fascia_c{classe['classe_id']}_f{fascia_id}_w{sett}")
                        self.model.Add(sum(self.assignments[k] for k in keys_questa) >= 1).OnlyEnforceIf(stessa_fascia)
                        self.model.Add(sum(self.assignments[k] for k in keys_prossima) >= 1).OnlyEnforceIf(stessa_fascia)
                        penalita_totale.append(2 * stessa_fascia)

        if penalita_totale:
            self.model.Minimize(sum(penalita_totale))

        print("✅ Modello costruito!\n")

    def solve(self, time_limit_seconds: int = 180, num_workers: int = 16):
        """Risolve il modello usando parallelizzazione."""

        print(f"🔍 Avvio solver PARALLELO ({num_workers} core, timeout: {time_limit_seconds}s)...\n")

        # CONFIGURAZIONE PARALLELIZZAZIONE
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.num_search_workers = num_workers  # USA TUTTI I CORE!
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.cp_model_presolve = True
        self.solver.parameters.linearization_level = 2  # Massima linearizzazione

        status = self.solver.Solve(self.model)

        print("\n" + "="*60)
        if status == cp_model.OPTIMAL:
            print("✅ SOLUZIONE OTTIMALE TROVATA!")
        elif status == cp_model.FEASIBLE:
            print("✅ SOLUZIONE AMMISSIBILE TROVATA")
        else:
            print("❌ NESSUNA SOLUZIONE TROVATA")
            print(f"Status: {self.solver.StatusName()}")
            return None
        print("="*60 + "\n")

        return status

    def export_results(self, output_path: str):
        """Esporta i risultati nel formato richiesto."""

        if self.solver.StatusName() not in ['OPTIMAL', 'FEASIBLE']:
            print("⚠️  Nessuna soluzione da esportare")
            return

        print("📝 Generazione risultati...\n")

        risultati = []

        for key, var in self.assignments.items():
            if self.solver.Value(var) == 1:
                classe_id, lab_id, formatrice_id, settimana, giorno, fascia_id = key

                classe_nome = self.classi[self.classi['classe_id'] == classe_id]['nome'].values[0]
                scuola_id = self.classi[self.classi['classe_id'] == classe_id]['scuola_id'].values[0]
                scuola_nome = self.scuole[self.scuole['scuola_id'] == scuola_id]['nome'].values[0]
                lab_nome = self.laboratori[self.laboratori['laboratorio_id'] == lab_id]['nome'].values[0]
                formatrice_nome = self.formatrici[self.formatrici['formatrice_id'] == formatrice_id]['nome'].values[0]

                fascia_row = self.fasce_orarie_scuole[(self.fasce_orarie_scuole['scuola_id'] == scuola_id) &
                                                       (self.fasce_orarie_scuole['fascia_id'] == fascia_id)]
                fascia_nome = fascia_row['nome'].values[0] if len(fascia_row) > 0 else f"Fascia {fascia_id}"

                risultati.append({
                    'Settimana': settimana + 1,
                    'Giorno': giorno,
                    'Fascia': fascia_nome,
                    'Scuola': scuola_nome,
                    'Classe': classe_nome,
                    'Laboratorio': lab_nome,
                    'Formatrice': formatrice_nome,
                    'Ore': self.laboratori[self.laboratori['laboratorio_id'] == lab_id]['ore_per_incontro'].values[0]
                })

        df_calendario = pd.DataFrame(risultati).sort_values(['Settimana', 'Giorno', 'Fascia'])

        esporta_formato_richiesto(
            df_calendario,
            self.scuole,
            self.classi,
            self.laboratori,
            self.formatrici,
            self.fasce_orarie_scuole,
            output_path
        )

        # Statistiche
        print("📊 STATISTICHE:")
        print("-" * 60)
        for _, formatrice in self.formatrici.iterrows():
            ore_totali = df_calendario[df_calendario['Formatrice'] == formatrice['nome']]['Ore'].sum()
            num_incontri = len(df_calendario[df_calendario['Formatrice'] == formatrice['nome']])
            print(f"  {formatrice['nome']:12} | {ore_totali:3.0f} ore | {num_incontri:2.0f} incontri")
        print("-" * 60)
        print(f"\nTotale incontri: {len(df_calendario)}")
        print(f"Valore obiettivo: {self.solver.ObjectiveValue():.0f}")
        print(f"Tempo risoluzione: {self.solver.WallTime():.2f}s\n")


def load_data(input_dir: str, suffix: str = ""):
    """Carica dati includendo fasce orarie per scuola."""

    print(f"📂 Caricamento dati da: {input_dir} (suffix: '{suffix}')")

    scuole = pd.read_csv(f"{input_dir}/esempio_scuole{suffix}.csv")
    classi = pd.read_csv(f"{input_dir}/esempio_classi{suffix}.csv")
    formatrici = pd.read_csv(f"{input_dir}/esempio_formatrici{suffix}.csv")
    laboratori = pd.read_csv(f"{input_dir}/esempio_laboratori{suffix}.csv")
    fasce_orarie_scuole = pd.read_csv(f"{input_dir}/esempio_fasce_orarie_scuole{suffix}.csv")

    print(f"  ✓ {len(scuole)} scuole")
    print(f"  ✓ {len(classi)} classi")
    print(f"  ✓ {len(formatrici)} formatrici")
    print(f"  ✓ {len(laboratori)} laboratori")
    print(f"  ✓ {len(fasce_orarie_scuole)} fasce orarie")
    print()

    return scuole, classi, formatrici, laboratori, fasce_orarie_scuole


def main():
    """Main ottimizzato."""

    print("\n" + "="*60)
    print("  COSMIC SCHOOL - Optimizer V2 OTTIMIZZATO (16 core)")
    print("="*60 + "\n")

    # Parametri da linea di comando
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    num_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 180

    input_dir = "data/input"
    output_file = f"data/output/calendario_v2_optimized{suffix}.xlsx"

    try:
        scuole, classi, formatrici, laboratori, fasce = load_data(input_dir, suffix)
    except FileNotFoundError as e:
        print(f"❌ Errore: {e}")
        sys.exit(1)

    optimizer = LaboratoriOptimizerV2Optimized(scuole, classi, formatrici, laboratori, fasce)
    optimizer.build_model()

    status = optimizer.solve(time_limit_seconds=timeout, num_workers=num_workers)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        optimizer.export_results(output_file)
        print("🎉 Ottimizzazione completata!\n")
    else:
        print("⚠️  Ottimizzazione fallita.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
