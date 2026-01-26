#!/usr/bin/env python3
"""
Optimizer V2 - Aggiunge Fasce Orarie e Giorni

Variabili:
- solo[classe, lab, formatrice, settimana, giorno, fascia] = BoolVar
- insieme[c1, c2, lab, formatrice, settimana, giorno, fascia] = BoolVar
  dove fascia in {'mattino1', 'mattino2', 'pomeriggio'}  <- SOLO 3 FASCE GENERICHE

Vincoli da V1:
- H1: Ogni classe completa ogni lab
- H1b: Accorpamenti (max 2 classi stessa scuola)
- H2: Max 1 incontro/settimana per classe
- Budget ore totali formatrice

Vincoli nuovi V2:
- H5: Giorni lavoro lun-ven (sabato solo per scuole/formatrici abilitate)
- H6: Sabato solo scuole con sabato_disponibile=si
- H7: Sabato solo formatrice con lavora_sabato=si
- H9: No sovrapposizioni formatrice (stesso giorno+fascia)
- H10: Fasce generiche globali (tutte le scuole accettano tutte le fasce)
- H11: Fasce disponibili per classe (subset di {mattino1, mattino2, pomeriggio})
"""

import pandas as pd
from ortools.sat.python import cp_model
from pathlib import Path
from collections import defaultdict
import sys
import re


class DataLoaderV2:
    """Carica dati incluse fasce orarie"""

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
        self.fasce_orarie_scuole = pd.read_csv(self.input_dir / "fasce_orarie_scuole.csv")
        self.fasce_orarie_classi = pd.read_csv(self.input_dir / "fasce_orarie_classi.csv")

        print(f"  {len(self.scuole)} scuole")
        print(f"  {len(self.classi)} classi")
        print(f"  {len(self.laboratori)} laboratori")
        print(f"  {len(self.formatrici)} formatrici")
        print(f"  {len(self.fasce_orarie_scuole)} fasce orarie scuole")
        print(f"  {len(self.fasce_orarie_classi)} fasce orarie classi")
        print()

        return self


class OptimizerV2:
    """Optimizer con fasce orarie e giorni"""

    NUM_SETTIMANE = 15
    GIORNI_FERIALI = ['lun', 'mar', 'mer', 'gio', 'ven']
    SABATO = 'sab'

    # Fasce orarie generiche (semplificazione)
    FASCE = ['mattino1', 'mattino2', 'pomeriggio']

    def __init__(self, data: DataLoaderV2):
        self.data = data
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        self.solo = {}
        self.insieme = {}

        # Indici per accesso veloce ai vincoli
        self.vars_by_formatrice_slot = defaultdict(list)  # (f, w, g, fascia) -> [vars]
        self.vars_by_classe_lab = defaultdict(list)       # (classe, lab) -> [vars]
        self.vars_by_classe_settimana = defaultdict(list) # (classe, settimana) -> [vars]

    def _parse_fasce_disponibili(self, fasce_str):
        """Parsa stringa fasce disponibili (es: 'mattino1, mattino2, pomeriggio')"""
        if pd.isna(fasce_str):
            return set(self.FASCE)  # Default: tutte le fasce
        fasce_str = str(fasce_str).lower()
        fasce = set()
        for part in re.split(r'[,\s]+', fasce_str):
            part = part.strip()
            if part in self.FASCE:
                fasce.add(part)
        return fasce if fasce else set(self.FASCE)

    def build_model(self):
        """Costruisce il modello"""
        print("Costruzione modello V2 con fasce orarie...")

        # ===================
        # PREPROCESSING DATI
        # ===================

        # Lab validi (esclusi GSSI/GST/LNGS)
        lab_ids_validi = set(self.data.laboratori['laboratorio_id'].values)

        # Labs per classe
        labs_per_classe = defaultdict(list)
        for _, row in self.data.laboratori_classi.iterrows():
            if row['laboratorio_id'] in lab_ids_validi:
                labs_per_classe[row['classe_id']].append(row['laboratorio_id'])

        # Scuola per classe
        scuola_per_classe = {}
        for _, row in self.data.classi.iterrows():
            scuola_per_classe[row['classe_id']] = row['scuola_id']

        # ----------------------------------------------
        # H10: Fasce generiche globali (tutte le scuole accettano tutte le fasce)
        # Le fasce specifiche in fasce_orarie_scuole.csv servono solo per mapping in export
        # ----------------------------------------------
        print(f"  H10: Fasce generiche globali: {self.FASCE}")

        # ----------------------------------------------
        # H11: Fasce disponibili per classe
        # Fonte: fasce_orarie_classi.csv
        # Ogni classe specifica quali fasce può usare (subset di FASCE)
        # ----------------------------------------------
        fasce_per_classe = {}
        for _, row in self.data.fasce_orarie_classi.iterrows():
            fasce_classe = self._parse_fasce_disponibili(row['fasce_disponibili'])
            fasce_per_classe[row['classe_id']] = fasce_classe
        print(f"  H11: Fasce per classe caricate ({len(fasce_per_classe)} classi)")

        # ----------------------------------------------
        # H5/H6: Giorni lavoro e sabato per scuole
        # Fonte: scuole.csv colonna sabato_disponibile
        # ----------------------------------------------
        scuole_con_sabato = set()
        for _, row in self.data.scuole.iterrows():
            if str(row['sabato_disponibile']).lower() in ['si', 'sì', 'yes', '1', 'true']:
                scuole_con_sabato.add(row['scuola_id'])
        print(f"  H5/H6: {len(scuole_con_sabato)} scuole con sabato disponibile")

        # ----------------------------------------------
        # H7: Sabato solo per formatrice abilitata
        # Fonte: formatrici.csv colonna lavora_sabato
        # ----------------------------------------------
        formatrici_con_sabato = set()
        for _, row in self.data.formatrici.iterrows():
            if str(row['lavora_sabato']).lower() in ['si', 'sì', 'yes', '1', 'true']:
                formatrici_con_sabato.add(int(row['formatrice_id']))
        print(f"  H7: {len(formatrici_con_sabato)} formatrici lavorano sabato")

        # Coppie accorpamento (stessa scuola)
        coppie_accorpamento = set()
        classi_per_scuola = defaultdict(list)
        for _, row in self.data.classi.iterrows():
            classi_per_scuola[row['scuola_id']].append(row['classe_id'])

        for scuola_id, classi_scuola in classi_per_scuola.items():
            for i, c1 in enumerate(classi_scuola):
                for c2 in classi_scuola[i+1:]:
                    coppie_accorpamento.add((c1, c2))

        # Partner per classe
        partner_per_classe = defaultdict(set)
        for c1, c2 in coppie_accorpamento:
            partner_per_classe[c1].add(c2)
            partner_per_classe[c2].add(c1)

        # Formatrici e ore
        tutte_formatrici = list(self.data.formatrici['formatrice_id'].astype(int))

        ore_per_lab = {}
        num_incontri_lab = {}
        for _, lab in self.data.laboratori.iterrows():
            ore_per_lab[lab['laboratorio_id']] = int(lab['ore_per_incontro'])
            num_incontri_lab[lab['laboratorio_id']] = int(lab['num_incontri'])

        # ===================
        # CREA VARIABILI
        # Filtrate per: H5/H6/H7 (giorni), H10 (fasce scuola), H11 (fasce classe)
        # ===================
        print("  Creazione variabili (filtrate per vincoli H5-H11)...")
        n_solo = 0
        n_insieme = 0

        for classe_id in labs_per_classe.keys():
            scuola_id = scuola_per_classe.get(classe_id)
            fasce_valide = fasce_per_classe.get(classe_id, set(self.FASCE))

            # H5/H6: Determina giorni validi per questa classe
            giorni_validi = list(self.GIORNI_FERIALI)
            if scuola_id in scuole_con_sabato:
                giorni_validi.append(self.SABATO)

            for lab_id in labs_per_classe[classe_id]:
                for formatrice_id in tutte_formatrici:
                    # H7: Se sabato, solo formatrice abilitata
                    giorni_formatrice = list(self.GIORNI_FERIALI)
                    if formatrice_id in formatrici_con_sabato and scuola_id in scuole_con_sabato:
                        giorni_formatrice.append(self.SABATO)

                    giorni_effettivi = [g for g in giorni_validi if g in giorni_formatrice]

                    for settimana in range(self.NUM_SETTIMANE):
                        for giorno in giorni_effettivi:
                            for fascia in fasce_valide:
                                key = (classe_id, lab_id, formatrice_id, settimana, giorno, fascia)
                                var_name = f"solo_c{classe_id}_l{lab_id}_f{formatrice_id}_w{settimana}_d{giorno}_fa{fascia}"
                                var = self.model.NewBoolVar(var_name)
                                self.solo[key] = var
                                n_solo += 1
                                # Indicizza per vincoli
                                self.vars_by_formatrice_slot[(formatrice_id, settimana, giorno, fascia)].append(var)
                                self.vars_by_classe_lab[(classe_id, lab_id)].append(var)
                                self.vars_by_classe_settimana[(classe_id, settimana)].append(var)

        # Variabili 'insieme'
        for c1, c2 in coppie_accorpamento:
            labs_c1 = set(labs_per_classe[c1])
            labs_c2 = set(labs_per_classe[c2])
            labs_comuni = labs_c1 & labs_c2

            scuola_id = scuola_per_classe.get(c1)  # Stessa scuola per entrambe

            # H11: Fasce valide per entrambe (intersezione)
            fasce_c1 = fasce_per_classe.get(c1, set(self.FASCE))
            fasce_c2 = fasce_per_classe.get(c2, set(self.FASCE))
            fasce_comuni = fasce_c1 & fasce_c2

            if not fasce_comuni:
                continue

            # H5/H6: Giorni validi
            giorni_validi = list(self.GIORNI_FERIALI)
            if scuola_id in scuole_con_sabato:
                giorni_validi.append(self.SABATO)

            for lab_id in labs_comuni:
                for formatrice_id in tutte_formatrici:
                    # H7: Sabato solo se formatrice abilitata
                    giorni_formatrice = list(self.GIORNI_FERIALI)
                    if formatrice_id in formatrici_con_sabato and scuola_id in scuole_con_sabato:
                        giorni_formatrice.append(self.SABATO)

                    giorni_effettivi = [g for g in giorni_validi if g in giorni_formatrice]

                    for settimana in range(self.NUM_SETTIMANE):
                        for giorno in giorni_effettivi:
                            for fascia in fasce_comuni:
                                key = (c1, c2, lab_id, formatrice_id, settimana, giorno, fascia)
                                var_name = f"ins_c{c1}_c{c2}_l{lab_id}_f{formatrice_id}_w{settimana}_d{giorno}_fa{fascia}"
                                var = self.model.NewBoolVar(var_name)
                                self.insieme[key] = var
                                n_insieme += 1
                                # Indicizza per vincoli
                                self.vars_by_formatrice_slot[(formatrice_id, settimana, giorno, fascia)].append(var)
                                self.vars_by_classe_lab[(c1, lab_id)].append(var)
                                self.vars_by_classe_lab[(c2, lab_id)].append(var)
                                self.vars_by_classe_settimana[(c1, settimana)].append(var)
                                self.vars_by_classe_settimana[(c2, settimana)].append(var)

        print(f"    Variabili 'solo': {n_solo:,}")
        print(f"    Variabili 'insieme': {n_insieme:,}")
        print(f"    Totale: {n_solo + n_insieme:,}")

        # ===================
        # DIAGNOSTICA: Verifica variabili per classe
        # ===================
        print("\n  DIAGNOSTICA VARIABILI:")
        classi_senza_vars = []
        classi_con_poche_vars = []
        for classe_id, labs in labs_per_classe.items():
            for lab_id in labs:
                n_vars = len(self.vars_by_classe_lab.get((classe_id, lab_id), []))
                num_incontri = num_incontri_lab.get(lab_id, 1)
                if n_vars == 0:
                    classe_nome = self.data.classi[self.data.classi['classe_id'] == classe_id]['nome'].iloc[0]
                    lab_nome = self.data.laboratori[self.data.laboratori['laboratorio_id'] == lab_id]['nome'].iloc[0]
                    classi_senza_vars.append((classe_id, classe_nome, lab_id, lab_nome))
                elif n_vars < num_incontri:
                    classe_nome = self.data.classi[self.data.classi['classe_id'] == classe_id]['nome'].iloc[0]
                    lab_nome = self.data.laboratori[self.data.laboratori['laboratorio_id'] == lab_id]['nome'].iloc[0]
                    classi_con_poche_vars.append((classe_id, classe_nome, lab_id, lab_nome, n_vars, num_incontri))

        if classi_senza_vars:
            print(f"    ⚠️  {len(classi_senza_vars)} combinazioni (classe,lab) SENZA variabili!")
            for c_id, c_nome, l_id, l_nome in classi_senza_vars[:10]:
                fasce_c = fasce_per_classe.get(c_id, set())
                scuola_id = scuola_per_classe.get(c_id)
                print(f"       classe {c_id} ({c_nome}), lab {l_id} ({l_nome})")
                print(f"         scuola={scuola_id}, fasce_classe={fasce_c}")
            if len(classi_senza_vars) > 10:
                print(f"       ... e altre {len(classi_senza_vars) - 10}")
        else:
            print("    ✓ Tutte le combinazioni (classe,lab) hanno variabili")

        if classi_con_poche_vars:
            print(f"    ⚠️  {len(classi_con_poche_vars)} combinazioni con meno variabili di incontri necessari:")
            for c_id, c_nome, l_id, l_nome, n_vars, num_inc in classi_con_poche_vars[:5]:
                print(f"       classe {c_id} ({c_nome}), lab {l_id}: {n_vars} vars < {num_inc} incontri")

        # Calcola slot totali disponibili
        print("\n  CAPACITA' SLOT:")
        incontri_totali = sum(num_incontri_lab.get(l, 1) for c, labs in labs_per_classe.items() for l in labs)
        print(f"    Incontri totali necessari: {incontri_totali}")

        # Budget ore
        ore_totali_budget = 292 + 128 + 160 + 128  # 708
        incontri_possibili = ore_totali_budget // 2  # 354
        deficit = incontri_totali - incontri_possibili
        print(f"    Budget ore: {ore_totali_budget} → {incontri_possibili} incontri possibili")
        print(f"    Deficit: {deficit} incontri (da coprire con accorpamenti)")

        # Conta accorpamenti possibili (variabili insieme create)
        # Raggruppa per (c1, c2, lab) per vedere quanti slot condivisi ci sono
        accorpamenti_possibili = defaultdict(int)
        for key in self.insieme.keys():
            c1, c2, lab_id, _, _, _, _ = key
            accorpamenti_possibili[(c1, c2, lab_id)] += 1

        n_coppie_con_vars = len(accorpamenti_possibili)
        print(f"    Coppie (c1,c2,lab) con variabili insieme: {n_coppie_con_vars}")

        # Quanti incontri insieme sono NECESSARI per fattibilità?
        # Se una coppia fa N incontri insieme invece che 2×N separati, risparmia N incontri
        # Conta max incontri risparmiabili
        # Per ogni coppia di classi, conta quanti lab hanno in comune
        max_risparmio = 0
        for (c1, c2, lab_id), n_vars in accorpamenti_possibili.items():
            num_incontri = num_incontri_lab.get(lab_id, 1)
            if n_vars >= num_incontri:  # Possono fare tutti gli incontri insieme
                max_risparmio += num_incontri
        print(f"    Max incontri risparmiabili con accorpamenti: {max_risparmio}")
        print(f"    Fattibilità: {'✓ OK' if max_risparmio >= deficit else '✗ INSUFFICIENTE'}")

        # Slot unici per formatrice
        slot_per_formatrice = defaultdict(set)
        for key in self.solo.keys():
            _, _, formatrice_id, settimana, giorno, fascia = key
            slot_per_formatrice[formatrice_id].add((settimana, giorno, fascia))
        for key in self.insieme.keys():
            _, _, _, formatrice_id, settimana, giorno, fascia = key
            slot_per_formatrice[formatrice_id].add((settimana, giorno, fascia))

        print("    Slot unici per formatrice:")
        for f_id, slots in sorted(slot_per_formatrice.items()):
            f_nome = self.data.formatrici[self.data.formatrici['formatrice_id'] == f_id]['nome'].iloc[0]
            print(f"      {f_nome}: {len(slots)} slot")
        print()

        # ===================
        # VINCOLI
        # ===================

        # ----------------------------------------------
        # H1: Ogni classe completa ogni lab
        # Fonte: laboratori_classi.csv + laboratori.csv (num_incontri)
        # Usa indice pre-calcolato vars_by_classe_lab
        # ----------------------------------------------
        print("  Vincolo H1: completamento laboratori")
        n_vincoli_h1 = 0
        for classe_id, labs in labs_per_classe.items():
            for lab_id in labs:
                num_incontri = num_incontri_lab.get(lab_id, 1)
                vars_totali = self.vars_by_classe_lab.get((classe_id, lab_id), [])

                if vars_totali:
                    self.model.Add(sum(vars_totali) == num_incontri)
                    n_vincoli_h1 += 1
        print(f"    Creati {n_vincoli_h1:,} vincoli H1")

        # ----------------------------------------------
        # H2: Max 1 incontro/settimana per classe
        # Fonte: criteri.xlsx riga 25
        # Usa indice pre-calcolato vars_by_classe_settimana
        # ----------------------------------------------
        print("  Vincolo H2: max 1 incontro/settimana per classe")
        n_vincoli_h2 = 0
        for (classe_id, settimana), vars_list in self.vars_by_classe_settimana.items():
            if vars_list:
                self.model.Add(sum(vars_list) <= 1)
                n_vincoli_h2 += 1
        print(f"    Creati {n_vincoli_h2:,} vincoli H2")

        # ----------------------------------------------
        # H9: No sovrapposizioni formatrice
        # Una formatrice non può essere in 2 posti nello stesso slot
        # Fonte: implicito (vincolo fisico)
        # ----------------------------------------------
        print("  Vincolo H9: no sovrapposizioni formatrice")
        n_vincoli_h9 = 0
        for slot_key, vars_slot in self.vars_by_formatrice_slot.items():
            if len(vars_slot) > 1:
                self.model.Add(sum(vars_slot) <= 1)
                n_vincoli_h9 += 1
        print(f"    Creati {n_vincoli_h9:,} vincoli H9")

        # ----------------------------------------------
        # Budget ore totali per formatrice
        # Fonte: criteri.xlsx (ore_generali)
        # VINCOLO HARD: non superare ore_max (upper bound)
        # VINCOLO SOFT (da implementare in V5): massimizzare utilizzo ore
        # ----------------------------------------------
        ORE_GENERALI = {1: 292, 2: 128, 3: 160, 4: 128}
        print("  Vincolo: budget ore formatrice (hard upper bound only)")

        # Indicizza variabili per formatrice
        vars_by_formatrice = defaultdict(list)
        for key, var in self.solo.items():
            formatrice_id = key[2]
            lab_id = key[1]
            ore = ore_per_lab.get(lab_id, 2)
            vars_by_formatrice[formatrice_id].append((ore, var))

        for key, var in self.insieme.items():
            formatrice_id = key[3]
            lab_id = key[2]
            ore = ore_per_lab.get(lab_id, 2)
            vars_by_formatrice[formatrice_id].append((ore, var))

        for _, formatrice in self.data.formatrici.iterrows():
            formatrice_id = int(formatrice['formatrice_id'])
            ore_max = ORE_GENERALI.get(formatrice_id, 100)

            ore_totali = [ore * var for ore, var in vars_by_formatrice[formatrice_id]]

            if ore_totali:
                # Upper bound: non superare ore_max (HARD)
                self.model.Add(sum(ore_totali) <= ore_max)
                print(f"    {formatrice['nome']}: max {ore_max} ore")

        print("  Modello V2 costruito!")
        print()

    def solve(self, time_limit_seconds: int = 300):
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

    def _map_fascia_generica_a_specifica(self, fascia_generica, scuola_id):
        """Mappa fascia generica (mattino1/mattino2/pomeriggio) a fascia specifica per output"""
        if fascia_generica == 'pomeriggio':
            return '14-16'  # Fisso per tutte le scuole

        # Per mattino1 e mattino2, prende la prima e seconda fascia della scuola
        fasce_scuola = self.data.fasce_orarie_scuole[
            self.data.fasce_orarie_scuole['scuola_id'] == scuola_id
        ].sort_values('fascia_id')

        if fascia_generica == 'mattino1' and len(fasce_scuola) >= 1:
            return fasce_scuola.iloc[0]['nome']
        elif fascia_generica == 'mattino2' and len(fasce_scuola) >= 2:
            return fasce_scuola.iloc[1]['nome']
        else:
            # Fallback
            return fascia_generica

    def export_results(self, output_path: str):
        """Esporta risultati"""
        if self.solver.StatusName() not in ['OPTIMAL', 'FEASIBLE']:
            return

        print(f"Esportazione: {output_path}")
        risultati = []

        for key, var in self.solo.items():
            if self.solver.Value(var) == 1:
                classe_id, lab_id, formatrice_id, settimana, giorno, fascia_generica = key

                classe_row = self.data.classi[self.data.classi['classe_id'] == classe_id].iloc[0]
                lab_df = self.data.laboratori[self.data.laboratori['laboratorio_id'] == lab_id]
                if len(lab_df) == 0:
                    continue
                lab_row = lab_df.iloc[0]
                scuola_row = self.data.scuole[self.data.scuole['scuola_id'] == classe_row['scuola_id']].iloc[0]
                formatrice_row = self.data.formatrici[self.data.formatrici['formatrice_id'] == formatrice_id].iloc[0]

                # Mapping fascia generica -> specifica
                fascia_specifica = self._map_fascia_generica_a_specifica(fascia_generica, classe_row['scuola_id'])

                risultati.append({
                    'settimana': settimana + 1,
                    'giorno': giorno,
                    'fascia': fascia_specifica,
                    'fascia_generica': fascia_generica,
                    'tipo': 'solo',
                    'classe': classe_row['nome'],
                    'classe2': None,
                    'scuola': scuola_row['nome'],
                    'laboratorio': lab_row['nome'],
                    'formatrice': formatrice_row['nome'],
                    'ore': lab_row['ore_per_incontro'],
                })

        for key, var in self.insieme.items():
            if self.solver.Value(var) == 1:
                c1, c2, lab_id, formatrice_id, settimana, giorno, fascia_generica = key

                classe1_row = self.data.classi[self.data.classi['classe_id'] == c1].iloc[0]
                classe2_row = self.data.classi[self.data.classi['classe_id'] == c2].iloc[0]
                lab_df = self.data.laboratori[self.data.laboratori['laboratorio_id'] == lab_id]
                if len(lab_df) == 0:
                    continue
                lab_row = lab_df.iloc[0]
                scuola_row = self.data.scuole[self.data.scuole['scuola_id'] == classe1_row['scuola_id']].iloc[0]
                formatrice_row = self.data.formatrici[self.data.formatrici['formatrice_id'] == formatrice_id].iloc[0]

                # Mapping fascia generica -> specifica
                fascia_specifica = self._map_fascia_generica_a_specifica(fascia_generica, classe1_row['scuola_id'])

                risultati.append({
                    'settimana': settimana + 1,
                    'giorno': giorno,
                    'fascia': fascia_specifica,
                    'fascia_generica': fascia_generica,
                    'tipo': 'insieme',
                    'classe': classe1_row['nome'],
                    'classe2': classe2_row['nome'],
                    'scuola': scuola_row['nome'],
                    'laboratorio': lab_row['nome'],
                    'formatrice': formatrice_row['nome'],
                    'ore': lab_row['ore_per_incontro'],
                })

        df = pd.DataFrame(risultati)
        df = df.sort_values(['settimana', 'giorno', 'fascia', 'scuola'])
        df.to_csv(output_path, index=False)

        n_solo = len(df[df['tipo'] == 'solo'])
        n_insieme = len(df[df['tipo'] == 'insieme'])
        print(f"  {len(df)} incontri ({n_solo} singoli, {n_insieme} accorpati)")

        ORE_GENERALI = {1: 292, 2: 128, 3: 160, 4: 128}
        print("\nSTATISTICHE FORMATRICI:")
        print("-" * 60)
        for _, f in self.data.formatrici.iterrows():
            nome = f['nome']
            fid = int(f['formatrice_id'])
            budget = ORE_GENERALI.get(fid, 100)
            df_f = df[df['formatrice'] == nome]
            ore = df_f['ore'].sum()
            utilizzo_pct = (ore / budget * 100) if budget > 0 else 0

            print(f"  {nome:12} | {ore:3.0f}/{budget} ore ({utilizzo_pct:5.1f}%) | {len(df_f):3} incontri")

        # Totali
        ore_totali_usate = df['ore'].sum()
        ore_totali_budget = sum(ORE_GENERALI.values())
        utilizzo_totale = (ore_totali_usate / ore_totali_budget * 100) if ore_totali_budget > 0 else 0
        print("-" * 60)
        print(f"  {'TOTALE':12} | {ore_totali_usate:3.0f}/{ore_totali_budget} ore ({utilizzo_totale:5.1f}%)")
        print("-" * 60)


def main():
    print()
    print("=" * 60)
    print("  OPTIMIZER V2 - Fasce Orarie e Giorni")
    print("=" * 60)
    print()

    input_dir = "data/input"
    output_file = "data/output/calendario_V2.csv"

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    try:
        data = DataLoaderV2(input_dir).load_all()
    except FileNotFoundError as e:
        print(f"Errore: {e}")
        sys.exit(1)

    optimizer = OptimizerV2(data)
    optimizer.build_model()

    status = optimizer.solve(time_limit_seconds=300)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        optimizer.export_results(output_file)
        print("\nOttimizzazione V2 completata!")
    else:
        print("Ottimizzazione fallita.")
        sys.exit(1)


if __name__ == "__main__":
    main()
