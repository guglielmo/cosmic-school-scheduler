#!/usr/bin/env python3
"""
Ottimizzatore per la distribuzione di laboratori scolastici.
Versione 2: include fasce orarie e giorni della settimana.
"""

import pandas as pd
from ortools.sat.python import cp_model
from typing import Dict, List, Tuple
import sys
from export_formatter import esporta_formato_richiesto


class LaboratoriOptimizerV2:
    """Ottimizzatore con gestione fasce orarie."""

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
        self.solver = cp_model.CpSolver()

    def build_model(self):
        """Costruisce il modello con vincoli su fasce orarie."""

        print("📊 Costruzione del modello di ottimizzazione (con fasce orarie)...")

        num_settimane = 20  # gennaio-maggio
        giorni_settimana = ['lun', 'mar', 'mer', 'gio', 'ven']  # sabato gestito separatamente

        # VARIABILI: assignment[classe, lab, formatrice, settimana, giorno, fascia]
        print("  • Creazione variabili di decisione...")
        for _, classe in self.classi.iterrows():
            scuola_id = classe['scuola_id']
            scuola = self.scuole[self.scuole['scuola_id'] == scuola_id].iloc[0]

            # Fasce orarie specifiche per questa scuola
            fasce_scuola = self.fasce_orarie_scuole[self.fasce_orarie_scuole['scuola_id'] == scuola_id]

            for _, lab in self.laboratori.iterrows():
                for _, formatrice in self.formatrici.iterrows():
                    for settimana in range(num_settimane):
                        for giorno in giorni_settimana:
                            # Verifica disponibilità formatrice in questo giorno
                            if giorno not in formatrice['giorni_disponibili']:
                                continue

                            for _, fascia in fasce_scuola.iterrows():
                                # Verifica compatibilità fascia con preferenza scuola
                                preferenza_scuola = scuola['preferenza_orario']
                                tipo_fascia = fascia['tipo_giornata']

                                if preferenza_scuola == 'mattina' and tipo_fascia != 'mattina':
                                    continue
                                if preferenza_scuola == 'pomeriggio' and tipo_fascia != 'pomeriggio':
                                    continue
                                # 'misto' accetta tutto

                                # Verifica preferenza formatrice (soft constraint qui, penalizzato nell'obiettivo)
                                preferenza_formatrice = formatrice['preferenza_fasce']
                                # Per ora creiamo tutte le variabili, penalizzeremo nell'obiettivo

                                var_name = f"c{classe['classe_id']}_l{lab['laboratorio_id']}_f{formatrice['formatrice_id']}_w{settimana}_d{giorno}_fa{fascia['fascia_id']}"
                                self.assignments[(
                                    classe['classe_id'],
                                    lab['laboratorio_id'],
                                    formatrice['formatrice_id'],
                                    settimana,
                                    giorno,
                                    fascia['fascia_id']
                                )] = self.model.NewBoolVar(var_name)

        print(f"  ✓ Create {len(self.assignments)} variabili")

        # VINCOLO 1: Ogni classe completa tutti i laboratori
        print("  ✓ Vincolo: ogni classe completa tutti i laboratori")
        for _, classe in self.classi.iterrows():
            for _, lab in self.laboratori.iterrows():
                incontri_totali = []
                for key in self.assignments:
                    if key[0] == classe['classe_id'] and key[1] == lab['laboratorio_id']:
                        incontri_totali.append(self.assignments[key])

                if incontri_totali:
                    self.model.Add(sum(incontri_totali) == lab['num_incontri'])

        # VINCOLO 2: Max 1 incontro per classe per settimana
        print("  ✓ Vincolo: max 1 incontro/settimana per classe")
        for _, classe in self.classi.iterrows():
            for settimana in range(num_settimane):
                incontri_settimana = []
                for key in self.assignments:
                    if key[0] == classe['classe_id'] and key[3] == settimana:
                        incontri_settimana.append(self.assignments[key])

                if incontri_settimana:
                    self.model.Add(sum(incontri_settimana) <= 1)

        # VINCOLO 3: Una formatrice non può essere in due posti contemporaneamente
        print("  ✓ Vincolo: no sovrapposizioni formatrici")
        fasce_uniche = self.fasce_orarie_scuole['fascia_id'].unique()
        for _, formatrice in self.formatrici.iterrows():
            for settimana in range(num_settimane):
                for giorno in giorni_settimana:
                    for fascia_id in fasce_uniche:
                        # In una fascia oraria, una formatrice può fare max 1 incontro
                        incontri_slot = []
                        for key in self.assignments:
                            if (key[2] == formatrice['formatrice_id'] and
                                key[3] == settimana and
                                key[4] == giorno and
                                key[5] == fascia_id):
                                incontri_slot.append(self.assignments[key])

                        if incontri_slot:
                            self.model.Add(sum(incontri_slot) <= 1)

        # VINCOLO 4: Variare fascia oraria per classe (non sempre la stessa)
        # Questo sarà gestito come soft constraint nell'obiettivo
        print("  ✓ Vincolo: rotazione fasce orarie (soft, nell'obiettivo)")

        # VINCOLO 5: Sequenzialità laboratori (semplificata)
        print("  ✓ Vincolo: sequenzialità laboratori")
        for _, classe in self.classi.iterrows():
            for idx in range(len(self.laboratori) - 1):
                lab_corrente = self.laboratori.iloc[idx]
                lab_successivo = self.laboratori.iloc[idx + 1]

                min_settimana_start = lab_corrente['num_incontri']
                for settimana in range(min_settimana_start):
                    for key in self.assignments:
                        if (key[0] == classe['classe_id'] and
                            key[1] == lab_successivo['laboratorio_id'] and
                            key[3] == settimana):
                            self.model.Add(self.assignments[key] == 0)

        # OBIETTIVO: minimizza cambi formatrice + penalizza stessa fascia consecutiva
        print("  ✓ Definizione funzione obiettivo")

        penalita_totale = []

        # Penalità cambio formatrice
        for _, classe in self.classi.iterrows():
            for _, lab in self.laboratori.iterrows():
                formatrici_list = self.formatrici['formatrice_id'].tolist()
                for i, f1 in enumerate(formatrici_list):
                    for f2 in formatrici_list[i+1:]:
                        lavora_f1 = []
                        lavora_f2 = []
                        for key in self.assignments:
                            if key[0] == classe['classe_id'] and key[1] == lab['laboratorio_id']:
                                if key[2] == f1:
                                    lavora_f1.append(self.assignments[key])
                                if key[2] == f2:
                                    lavora_f2.append(self.assignments[key])

                        if lavora_f1 and lavora_f2:
                            cambio = self.model.NewBoolVar(f"cambio_c{classe['classe_id']}_l{lab['laboratorio_id']}_f{f1}_f{f2}")
                            self.model.Add(sum(lavora_f1) >= 1).OnlyEnforceIf(cambio)
                            self.model.Add(sum(lavora_f2) >= 1).OnlyEnforceIf(cambio)
                            penalita_totale.append(10 * cambio)  # Peso alto

        # Penalità stessa fascia in settimane consecutive
        fasce_uniche = self.fasce_orarie_scuole['fascia_id'].unique()
        for _, classe in self.classi.iterrows():
            for sett in range(num_settimane - 1):
                for fascia_id in fasce_uniche:
                    usa_questa_settimana = []
                    usa_prossima_settimana = []

                    for key in self.assignments:
                        if key[0] == classe['classe_id'] and key[5] == fascia_id:
                            if key[3] == sett:
                                usa_questa_settimana.append(self.assignments[key])
                            if key[3] == sett + 1:
                                usa_prossima_settimana.append(self.assignments[key])

                    if usa_questa_settimana and usa_prossima_settimana:
                        stessa_fascia = self.model.NewBoolVar(f"stessa_fascia_c{classe['classe_id']}_f{fascia_id}_w{sett}")
                        self.model.Add(sum(usa_questa_settimana) >= 1).OnlyEnforceIf(stessa_fascia)
                        self.model.Add(sum(usa_prossima_settimana) >= 1).OnlyEnforceIf(stessa_fascia)
                        penalita_totale.append(2 * stessa_fascia)  # Peso medio

        # Penalità per mismatch tra preferenza formatrice e fascia oraria
        print("  ✓ Penalità preferenze formatrici su fasce orarie")
        for key in self.assignments:
            classe_id, lab_id, formatrice_id, settimana, giorno, fascia_id = key

            # Trova la formatrice
            formatrice = self.formatrici[self.formatrici['formatrice_id'] == formatrice_id].iloc[0]
            preferenza_formatrice = formatrice['preferenza_fasce']

            # Trova la fascia
            fascia = self.fasce_orarie_scuole[self.fasce_orarie_scuole['fascia_id'] == fascia_id]
            if len(fascia) > 0:
                tipo_fascia = fascia.iloc[0]['tipo_giornata']

                # Se la formatrice ha preferenza diversa dal tipo fascia, penalizza
                if preferenza_formatrice != 'misto':
                    if preferenza_formatrice != tipo_fascia:
                        # Penalità bassa (permettiamo ma non è ottimale)
                        penalita_totale.append(1 * self.assignments[key])

        if penalita_totale:
            self.model.Minimize(sum(penalita_totale))

        print("✅ Modello costruito!\n")

    def solve(self, time_limit_seconds: int = 120):
        """Risolve il modello."""

        print(f"🔍 Avvio solver (timeout: {time_limit_seconds}s)...\n")

        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.log_search_progress = False  # Meno verbose per V2

        status = self.solver.Solve(self.model)

        print("\n" + "="*60)
        if status == cp_model.OPTIMAL:
            print("✅ SOLUZIONE OTTIMALE TROVATA!")
        elif status == cp_model.FEASIBLE:
            print("✅ SOLUZIONE AMMISSIBILE TROVATA")
        else:
            print("❌ NESSUNA SOLUZIONE TROVATA")
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

                # Trova la fascia per questa scuola
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

        # Usa il formatter per generare l'output nel formato richiesto
        esporta_formato_richiesto(
            df_calendario,
            self.scuole,
            self.classi,
            self.laboratori,
            self.formatrici,
            self.fasce_orarie_scuole,
            output_path
        )

        # Statistiche a schermo
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


def load_data(input_dir: str):
    """Carica dati includendo fasce orarie per scuola."""

    print(f"📂 Caricamento dati da: {input_dir}")

    scuole = pd.read_csv(f"{input_dir}/esempio_scuole.csv")
    classi = pd.read_csv(f"{input_dir}/esempio_classi.csv")
    formatrici = pd.read_csv(f"{input_dir}/esempio_formatrici.csv")
    laboratori = pd.read_csv(f"{input_dir}/esempio_laboratori.csv")
    fasce_orarie_scuole = pd.read_csv(f"{input_dir}/esempio_fasce_orarie_scuole.csv")

    print(f"  ✓ {len(scuole)} scuole")
    print(f"  ✓ {len(classi)} classi")
    print(f"  ✓ {len(formatrici)} formatrici")
    print(f"  ✓ {len(laboratori)} laboratori")
    print(f"  ✓ {len(fasce_orarie_scuole)} fasce orarie (per scuola)")
    print()

    return scuole, classi, formatrici, laboratori, fasce_orarie_scuole


def main():
    """Main con fasce orarie."""

    print("\n" + "="*60)
    print("  COSMIC SCHOOL - Ottimizzatore V2 (con fasce orarie)")
    print("="*60 + "\n")

    input_dir = "data/input"
    output_file = "data/output/calendario_v2_con_fasce.xlsx"

    try:
        scuole, classi, formatrici, laboratori, fasce = load_data(input_dir)
    except FileNotFoundError as e:
        print(f"❌ Errore: {e}")
        sys.exit(1)

    optimizer = LaboratoriOptimizerV2(scuole, classi, formatrici, laboratori, fasce)
    optimizer.build_model()

    status = optimizer.solve(time_limit_seconds=180)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        optimizer.export_results(output_file)
        print("🎉 Ottimizzazione completata!\n")
    else:
        print("⚠️  Ottimizzazione fallita.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
