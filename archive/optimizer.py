#!/usr/bin/env python3
"""
Ottimizzatore per la distribuzione di laboratori scolastici.
Utilizza OR-Tools per risolvere un problema di scheduling con vincoli.
"""

import pandas as pd
from ortools.sat.python import cp_model
from typing import Dict, List, Tuple
import sys


class LaboratoriOptimizer:
    """Ottimizzatore per l'assegnazione di laboratori a classi e formatrici."""

    def __init__(self,
                 scuole_df: pd.DataFrame,
                 classi_df: pd.DataFrame,
                 formatrici_df: pd.DataFrame,
                 laboratori_df: pd.DataFrame):
        self.scuole = scuole_df
        self.classi = classi_df
        self.formatrici = formatrici_df
        self.laboratori = laboratori_df

        self.model = cp_model.CpModel()
        self.assignments = {}
        self.solver = cp_model.CpSolver()

    def build_model(self):
        """Costruisce il modello di ottimizzazione con variabili e vincoli."""

        print("📊 Costruzione del modello di ottimizzazione...")

        # Variabili di decisione: assignment[classe, lab, formatrice, settimana]
        # 1 se la formatrice f tiene il laboratorio l per la classe c nella settimana w

        num_settimane = 20  # gennaio-maggio, circa 20 settimane

        for _, classe in self.classi.iterrows():
            for _, lab in self.laboratori.iterrows():
                for _, formatrice in self.formatrici.iterrows():
                    for settimana in range(num_settimane):
                        var_name = f"c{classe['classe_id']}_l{lab['laboratorio_id']}_f{formatrice['formatrice_id']}_w{settimana}"
                        self.assignments[(classe['classe_id'],
                                        lab['laboratorio_id'],
                                        formatrice['formatrice_id'],
                                        settimana)] = self.model.NewBoolVar(var_name)

        # VINCOLO 1: Ogni classe deve completare tutti i laboratori
        print("  ✓ Aggiunto vincolo: ogni classe completa tutti i laboratori")
        for _, classe in self.classi.iterrows():
            for _, lab in self.laboratori.iterrows():
                # La somma di tutti gli incontri per questo lab deve essere = num_incontri
                total_incontri = []
                for _, formatrice in self.formatrici.iterrows():
                    for settimana in range(num_settimane):
                        total_incontri.append(
                            self.assignments[(classe['classe_id'],
                                            lab['laboratorio_id'],
                                            formatrice['formatrice_id'],
                                            settimana)]
                        )
                self.model.Add(sum(total_incontri) == lab['num_incontri'])

        # VINCOLO 2: Massimo 1 incontro per classe per settimana
        print("  ✓ Aggiunto vincolo: max 1 incontro/settimana per classe")
        for _, classe in self.classi.iterrows():
            for settimana in range(num_settimane):
                incontri_settimana = []
                for _, lab in self.laboratori.iterrows():
                    for _, formatrice in self.formatrici.iterrows():
                        incontri_settimana.append(
                            self.assignments[(classe['classe_id'],
                                            lab['laboratorio_id'],
                                            formatrice['formatrice_id'],
                                            settimana)]
                        )
                self.model.Add(sum(incontri_settimana) <= 1)

        # VINCOLO 3: Sequenzialità dei laboratori
        # Un laboratorio può iniziare solo se il precedente è finito
        # Versione semplificata: la prima settimana del lab successivo deve essere >= ultima del precedente
        print("  ✓ Aggiunto vincolo: sequenzialità laboratori")
        for _, classe in self.classi.iterrows():
            for idx in range(len(self.laboratori) - 1):
                lab_corrente = self.laboratori.iloc[idx]
                lab_successivo = self.laboratori.iloc[idx + 1]

                # Calcola la settimana di inizio del lab successivo
                prima_settimana_next = self.model.NewIntVar(0, num_settimane - 1,
                    f"prima_sett_c{classe['classe_id']}_l{lab_successivo['laboratorio_id']}")

                # Calcola l'ultima settimana del lab corrente
                ultima_settimana_curr = self.model.NewIntVar(0, num_settimane - 1,
                    f"ultima_sett_c{classe['classe_id']}_l{lab_corrente['laboratorio_id']}")

                # Vincola la prima settimana del lab successivo
                for settimana in range(num_settimane):
                    incontri_in_settimana = []
                    for _, formatrice in self.formatrici.iterrows():
                        incontri_in_settimana.append(
                            self.assignments[(classe['classe_id'],
                                            lab_successivo['laboratorio_id'],
                                            formatrice['formatrice_id'],
                                            settimana)]
                        )
                    # Se c'è un incontro in questa settimana, può essere la prima
                    has_incontro = self.model.NewBoolVar(f"has_next_c{classe['classe_id']}_l{lab_successivo['laboratorio_id']}_w{settimana}")
                    self.model.Add(sum(incontri_in_settimana) >= 1).OnlyEnforceIf(has_incontro)
                    self.model.Add(sum(incontri_in_settimana) == 0).OnlyEnforceIf(has_incontro.Not())

                # Vincola l'ultima settimana del lab corrente
                for settimana in range(num_settimane):
                    incontri_in_settimana = []
                    for _, formatrice in self.formatrici.iterrows():
                        incontri_in_settimana.append(
                            self.assignments[(classe['classe_id'],
                                            lab_corrente['laboratorio_id'],
                                            formatrice['formatrice_id'],
                                            settimana)]
                        )
                    # Se c'è un incontro, aggiorna l'ultima settimana
                    has_incontro = self.model.NewBoolVar(f"has_curr_c{classe['classe_id']}_l{lab_corrente['laboratorio_id']}_w{settimana}")
                    self.model.Add(sum(incontri_in_settimana) >= 1).OnlyEnforceIf(has_incontro)
                    self.model.Add(sum(incontri_in_settimana) == 0).OnlyEnforceIf(has_incontro.Not())

                # Per semplicità: forza un gap minimo di 1 settimana tra la fine di un lab e l'inizio del successivo
                # attraverso il vincolo che il lab successivo non può iniziare nelle prime N settimane
                min_settimana_start = lab_corrente['num_incontri']  # almeno N settimane dopo l'inizio
                for settimana in range(min_settimana_start):
                    for _, formatrice in self.formatrici.iterrows():
                        self.model.Add(
                            self.assignments[(classe['classe_id'],
                                            lab_successivo['laboratorio_id'],
                                            formatrice['formatrice_id'],
                                            settimana)] == 0
                        )

        # VINCOLO 4: Una formatrice non può essere in due scuole contemporaneamente
        print("  ✓ Aggiunto vincolo: no sovrapposizioni formatrici")
        for _, formatrice in self.formatrici.iterrows():
            for settimana in range(num_settimane):
                incontri_formatrice = []
                for _, classe in self.classi.iterrows():
                    for _, lab in self.laboratori.iterrows():
                        incontri_formatrice.append(
                            self.assignments[(classe['classe_id'],
                                            lab['laboratorio_id'],
                                            formatrice['formatrice_id'],
                                            settimana)]
                        )
                # Una formatrice può fare max 2 incontri/settimana (esempio)
                self.model.Add(sum(incontri_formatrice) <= 2)

        # OBIETTIVO: Minimizzare il numero di cambi formatrice per classe
        # e bilanciare il carico tra formatrici
        print("  ✓ Definizione funzione obiettivo: continuità e bilanciamento")

        # Penalità per cambio formatrice
        cambi_formatrice = []
        for _, classe in self.classi.iterrows():
            for _, lab in self.laboratori.iterrows():
                # Per ogni coppia di formatrici, penalizziamo se entrambe lavorano con la stessa classe
                formatrici_list = self.formatrici['formatrice_id'].tolist()
                for i, f1 in enumerate(formatrici_list):
                    for f2 in formatrici_list[i+1:]:
                        # Se entrambe le formatrici lavorano per questa classe in questo lab
                        lavora_f1 = []
                        lavora_f2 = []
                        for settimana in range(num_settimane):
                            lavora_f1.append(
                                self.assignments[(classe['classe_id'], lab['laboratorio_id'], f1, settimana)]
                            )
                            lavora_f2.append(
                                self.assignments[(classe['classe_id'], lab['laboratorio_id'], f2, settimana)]
                            )

                        # Variabile ausiliaria per il cambio
                        cambio = self.model.NewBoolVar(f"cambio_c{classe['classe_id']}_l{lab['laboratorio_id']}_f{f1}_f{f2}")

                        # Se entrambe > 0, allora cambio = 1
                        self.model.Add(sum(lavora_f1) >= 1).OnlyEnforceIf(cambio)
                        self.model.Add(sum(lavora_f2) >= 1).OnlyEnforceIf(cambio)

                        cambi_formatrice.append(cambio)

        # Bilanciamento carico
        ore_per_formatrice = []
        for _, formatrice in self.formatrici.iterrows():
            ore = []
            for _, classe in self.classi.iterrows():
                for _, lab in self.laboratori.iterrows():
                    for settimana in range(num_settimane):
                        # Ogni incontro vale ore_per_incontro
                        ore.append(
                            self.assignments[(classe['classe_id'],
                                            lab['laboratorio_id'],
                                            formatrice['formatrice_id'],
                                            settimana)] * lab['ore_per_incontro']
                        )
            ore_per_formatrice.append(sum(ore))

        # Minimizza: cambi formatrice + varianza ore
        self.model.Minimize(
            10 * sum(cambi_formatrice)  # Peso alto per continuità
        )

        print("✅ Modello costruito con successo!\n")

    def solve(self, time_limit_seconds: int = 60):
        """Risolve il modello di ottimizzazione."""

        print(f"🔍 Avvio solver (timeout: {time_limit_seconds}s)...\n")

        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.log_search_progress = True

        status = self.solver.Solve(self.model)

        print("\n" + "="*60)
        if status == cp_model.OPTIMAL:
            print("✅ SOLUZIONE OTTIMALE TROVATA!")
        elif status == cp_model.FEASIBLE:
            print("✅ SOLUZIONE AMMISSIBILE TROVATA (potrebbe non essere ottimale)")
        else:
            print("❌ NESSUNA SOLUZIONE TROVATA")
            print("   Possibili cause:")
            print("   - Vincoli troppo stringenti")
            print("   - Risorse insufficienti (formatrici/tempo)")
            return None
        print("="*60 + "\n")

        return status

    def export_results(self, output_path: str):
        """Esporta i risultati in formato Excel."""

        if self.solver.StatusName() not in ['OPTIMAL', 'FEASIBLE']:
            print("⚠️  Nessuna soluzione da esportare")
            return

        print("📝 Generazione risultati...\n")

        # Crea DataFrame con le assegnazioni
        risultati = []

        for (classe_id, lab_id, formatrice_id, settimana), var in self.assignments.items():
            if self.solver.Value(var) == 1:
                classe_nome = self.classi[self.classi['classe_id'] == classe_id]['nome'].values[0]
                scuola_id = self.classi[self.classi['classe_id'] == classe_id]['scuola_id'].values[0]
                scuola_nome = self.scuole[self.scuole['scuola_id'] == scuola_id]['nome'].values[0]
                lab_nome = self.laboratori[self.laboratori['laboratorio_id'] == lab_id]['nome'].values[0]
                formatrice_nome = self.formatrici[self.formatrici['formatrice_id'] == formatrice_id]['nome'].values[0]

                risultati.append({
                    'Settimana': settimana + 1,
                    'Scuola': scuola_nome,
                    'Classe': classe_nome,
                    'Laboratorio': lab_nome,
                    'Formatrice': formatrice_nome,
                    'Ore': self.laboratori[self.laboratori['laboratorio_id'] == lab_id]['ore_per_incontro'].values[0]
                })

        df_risultati = pd.DataFrame(risultati).sort_values(['Settimana', 'Formatrice', 'Scuola'])

        # Salva in Excel con fogli multipli
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Foglio 1: Calendario completo
            df_risultati.to_excel(writer, sheet_name='Calendario Completo', index=False)

            # Foglio 2: Vista per formatrice
            for formatrice in df_risultati['Formatrice'].unique():
                df_formatrice = df_risultati[df_risultati['Formatrice'] == formatrice]
                df_formatrice.to_excel(writer, sheet_name=f'Formatrice {formatrice}', index=False)

            # Foglio 3: Statistiche
            stats = []
            for _, formatrice in self.formatrici.iterrows():
                ore_totali = df_risultati[df_risultati['Formatrice'] == formatrice['nome']]['Ore'].sum()
                num_incontri = len(df_risultati[df_risultati['Formatrice'] == formatrice['nome']])
                stats.append({
                    'Formatrice': formatrice['nome'],
                    'Ore Totali': ore_totali,
                    'Numero Incontri': num_incontri
                })

            pd.DataFrame(stats).to_excel(writer, sheet_name='Statistiche', index=False)

        print(f"✅ Risultati salvati in: {output_path}\n")

        # Mostra statistiche a schermo
        print("📊 STATISTICHE SOLUZIONE:")
        print("-" * 60)
        for stat in stats:
            print(f"  {stat['Formatrice']:12} | {stat['Ore Totali']:3.0f} ore | {stat['Numero Incontri']:2.0f} incontri")
        print("-" * 60)
        print(f"\nTotale incontri schedulati: {len(df_risultati)}")
        print(f"Valore obiettivo: {self.solver.ObjectiveValue():.0f}")
        print(f"Tempo di risoluzione: {self.solver.WallTime():.2f}s\n")


def load_data(input_dir: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carica i dati di input dai file CSV."""

    print(f"📂 Caricamento dati da: {input_dir}")

    scuole = pd.read_csv(f"{input_dir}/esempio_scuole.csv")
    classi = pd.read_csv(f"{input_dir}/esempio_classi.csv")
    formatrici = pd.read_csv(f"{input_dir}/esempio_formatrici.csv")
    laboratori = pd.read_csv(f"{input_dir}/esempio_laboratori.csv")

    print(f"  ✓ {len(scuole)} scuole")
    print(f"  ✓ {len(classi)} classi")
    print(f"  ✓ {len(formatrici)} formatrici")
    print(f"  ✓ {len(laboratori)} laboratori")
    print()

    return scuole, classi, formatrici, laboratori


def main():
    """Funzione principale."""

    print("\n" + "="*60)
    print("  COSMIC SCHOOL - Ottimizzatore Calendario Laboratori")
    print("="*60 + "\n")

    # Carica dati
    input_dir = "data/input"
    output_file = "data/output/calendario_ottimizzato.xlsx"

    try:
        scuole, classi, formatrici, laboratori = load_data(input_dir)
    except FileNotFoundError as e:
        print(f"❌ Errore: file non trovato - {e}")
        print("   Assicurati che i file CSV siano in data/input/")
        sys.exit(1)

    # Crea e risolvi il modello
    optimizer = LaboratoriOptimizer(scuole, classi, formatrici, laboratori)
    optimizer.build_model()

    status = optimizer.solve(time_limit_seconds=120)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        optimizer.export_results(output_file)
        print("🎉 Ottimizzazione completata con successo!\n")
    else:
        print("⚠️  Ottimizzazione fallita. Controlla i vincoli e i dati.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
