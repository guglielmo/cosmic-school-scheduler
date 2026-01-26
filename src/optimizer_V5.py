#!/usr/bin/env python3
"""
Optimizer V5 - Scheduling laboratori con CP-SAT + Vincoli Soft

Variabili per ogni incontro (classe, lab, k):
- settimana[c,l,k] = IntVar(0..15)
- giorno[c,l,k] = IntVar(0..5) per lun-sab
- fascia[c,l,k] = IntVar(1..3) <- FASCE GENERICHE: 1=mattino1, 2=mattino2, 3=pomeriggio
- formatrice[c,l,k] = IntVar(1..4)

Per accorpamenti:
- accorpa[c1,c2,lab] = BoolVar

Vincoli Hard (da V4):
- H1: Completamento (automatico)
- H1b: Accorpamenti (max 2 classi per incontro)
- H2: Max 1 incontro/settimana per classe
- H3: Presentazione manuali ultimo
- H4: Sequenzialità laboratori
- H5-H7: Sabato (solo 2 scuole, solo formatrice 4)
- H9: No sovrapposizioni formatrice (stesso slot)
- H12: Date escluse per classe
- H13: Date fissate
- H14: Disponibilità formatrice
- Budget ore formatrici

Vincoli Soft (obiettivo):
- S1: Continuità formatrice (stessa formatrice per tutti i lab di una classe)
- S1b: Accorpamenti preferenziali (da classi.csv)
- S2: Classi quinte prioritarie (finiscono prima)
- S3: Ordine ideale lab (sensibilizzazione → citizen science → orientamento)
"""

import argparse
import pandas as pd
from ortools.sat.python import cp_model
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta
import sys

from date_parser import DateParser


def settimana_giorno_to_data(settimana: int, giorno: int) -> date:
    """Converte (settimana 0-14, giorno 0-5) in data reale."""
    data_inizio = date(2026, 1, 26)

    if settimana <= 9:
        offset = settimana * 7 + giorno
        return data_inizio + timedelta(days=offset)
    else:
        data_post_pasqua = date(2026, 4, 13)  # Lunedì dopo Pasqua
        offset_post = (settimana - 10) * 7 + giorno
        return data_post_pasqua + timedelta(days=offset_post)


class DataLoader:
    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)

    def load_all(self):
        self.scuole = pd.read_csv(self.input_dir / "scuole.csv")
        self.classi = pd.read_csv(self.input_dir / "classi.csv")
        self.laboratori = pd.read_csv(self.input_dir / "laboratori.csv")
        self.laboratori_classi = pd.read_csv(self.input_dir / "laboratori_classi.csv")
        self.formatrici = pd.read_csv(self.input_dir / "formatrici.csv")
        self.fasce_orarie_scuole = pd.read_csv(self.input_dir / "fasce_orarie_scuole.csv")
        self.fasce_orarie_classi = pd.read_csv(self.input_dir / "fasce_orarie_classi.csv")
        self.date_escluse_classi = pd.read_csv(self.input_dir / "date_escluse_classi.csv")
        return self


class OptimizerV5:
    NUM_SETTIMANE = 16  # 16 settimane: gio 29/1 - gio 21/5
    NUM_GIORNI = 6
    LAB_PRESENTAZIONE_MANUALI = 8
    ORE_GENERALI = {1: 292, 2: 128, 3: 160, 4: 128}
    SCUOLE_SABATO = {10, 13}
    FORMATRICE_SABATO = 4

    # Fasce generiche (semplificazione)
    FASCE_GENERICHE = {'mattino1': 1, 'mattino2': 2, 'pomeriggio': 3}
    FASCE_INVERSE = {1: 'mattino1', 2: 'mattino2', 3: 'pomeriggio'}

    # Pesi per vincoli soft
    PESO_S1_CONTINUITA = 100       # Stessa formatrice per tutti i lab di una classe
    PESO_S1B_ACCORPAMENTO_PREF = 50  # Accorpamento con classe preferenziale
    PESO_S2_QUINTE_PRIMA = 10      # Classi quinte finiscono prima (per settimana)
    PESO_S3_ORDINE_IDEALE = 20     # Ordine ideale: sensibilizzazione → citizen → orientamento

    # Ordine ideale laboratori (sequenza preferita)
    # 7 = sensibilizzazione, 9 = sensibilizzazione pt.2, 4 = citizen science, 5 = orientamento
    ORDINE_IDEALE_LAB = {7: 1, 9: 2, 4: 3, 5: 4}  # lab_id -> posizione ideale

    def __init__(self, data: DataLoader, verbose: bool = False, enable_soft: bool = True):
        self.data = data
        self.verbose = verbose
        self.enable_soft = enable_soft
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        self.settimana = {}
        self.giorno = {}
        self.fascia = {}
        self.formatrice = {}
        self.accorpa = {}
        self.slot = {}
        self.is_formatrice = {}
        self.ore_per_formatrice = {}

        # Dati preprocessati (salvati per verifica)
        self.labs_per_classe = None
        self.scuola_per_classe = None
        self.ore_per_lab = None
        self.num_incontri_lab = None
        self.tutti_incontri = None
        self.anno_per_classe = None
        self.accorpamento_preferenziale = None

    def build_model(self):
        print("Costruzione modello...")

        DateParser.load_fasce_info(self.data.fasce_orarie_scuole)

        # Preprocessing
        lab_ids_validi = set(self.data.laboratori['laboratorio_id'].values)

        # Identifica lab GSSI (non gestiti dalle formatrici FOP)
        tutti_lab_ids = set(self.data.laboratori_classi['laboratorio_id'].values)
        lab_ids_gssi = tutti_lab_ids - lab_ids_validi
        print(f"  Lab FOP: {sorted(lab_ids_validi)}, Lab GSSI: {sorted(lab_ids_gssi)}")

        # Raccogli settimane GSSI da escludere per ogni classe
        # Se una classe ha un lab GSSI in una settimana, non può fare lab FOP quella settimana
        # settimane_gssi[classe_id] = set di settimane occupate
        self.settimane_gssi = defaultdict(set)
        n_slot_gssi = 0
        for _, row in self.data.laboratori_classi.iterrows():
            lab_id = row['laboratorio_id']
            if lab_id not in lab_ids_gssi:
                continue
            if pd.isna(row.get('date_fissate')) or row['date_fissate'] == '':
                continue

            classe_id = row['classe_id']
            parsed = DateParser.parse_date_fissate(row['date_fissate'])
            for sett, giorno, fasce_valide in parsed:
                if sett is not None:
                    self.settimane_gssi[classe_id].add(sett)
                    n_slot_gssi += 1

        tot_settimane_bloccate = sum(len(s) for s in self.settimane_gssi.values())
        print(f"  Settimane GSSI bloccate: {tot_settimane_bloccate} (per {len(self.settimane_gssi)} classi)")

        self.labs_per_classe = defaultdict(list)
        for _, row in self.data.laboratori_classi.iterrows():
            if row['laboratorio_id'] in lab_ids_validi:
                self.labs_per_classe[row['classe_id']].append(row['laboratorio_id'])

        self.scuola_per_classe = {}
        self.anno_per_classe = {}
        self.accorpamento_preferenziale = {}
        for _, row in self.data.classi.iterrows():
            self.scuola_per_classe[row['classe_id']] = row['scuola_id']
            self.anno_per_classe[row['classe_id']] = int(row['anno'])
            # Accorpamento preferenziale: cerca la classe con quel nome nella stessa scuola
            acc_pref = row.get('accorpamento_preferenziale', '')
            if pd.notna(acc_pref) and acc_pref != '':
                # Trova classe_id dal nome nella stessa scuola
                scuola_id = row['scuola_id']
                classe_pref = self.data.classi[
                    (self.data.classi['nome'] == acc_pref) &
                    (self.data.classi['scuola_id'] == scuola_id)
                ]
                if len(classe_pref) > 0:
                    self.accorpamento_preferenziale[row['classe_id']] = int(classe_pref.iloc[0]['classe_id'])

        fasce_per_classe = {}
        for _, row in self.data.fasce_orarie_classi.iterrows():
            fasce_str = row.get('fasce_disponibili', '')
            if pd.isna(fasce_str) or fasce_str == '':
                # Default: tutte le fasce generiche
                fasce = [1, 2, 3]
            else:
                # Parse fasce generiche (es: "mattino1, mattino2, pomeriggio")
                fasce = []
                for part in str(fasce_str).lower().split(','):
                    part = part.strip()
                    if part in self.FASCE_GENERICHE:
                        fasce.append(self.FASCE_GENERICHE[part])
                if not fasce:
                    fasce = [1, 2, 3]  # Default
            fasce_per_classe[row['classe_id']] = fasce

        self.ore_per_lab = {}
        self.num_incontri_lab = {}
        for _, lab in self.data.laboratori.iterrows():
            self.ore_per_lab[lab['laboratorio_id']] = int(lab['ore_per_incontro'])
            self.num_incontri_lab[lab['laboratorio_id']] = int(lab['num_incontri'])

        tutte_formatrici = list(self.data.formatrici['formatrice_id'].astype(int))
        min_f, max_f = min(tutte_formatrici), max(tutte_formatrici)

        # Coppie accorpamento
        classi_per_scuola = defaultdict(list)
        for _, row in self.data.classi.iterrows():
            classi_per_scuola[row['scuola_id']].append(row['classe_id'])

        coppie_per_lab = defaultdict(list)
        for scuola_id, classi_scuola in classi_per_scuola.items():
            for i, c1 in enumerate(classi_scuola):
                for c2 in classi_scuola[i+1:]:
                    labs_c1 = set(self.labs_per_classe[c1])
                    labs_c2 = set(self.labs_per_classe[c2])
                    for lab_id in labs_c1 & labs_c2:
                        coppie_per_lab[lab_id].append((c1, c2))

        # Mappa: (classe, lab) -> lista di accorpa_var in cui appare
        accorpa_per_classe_lab = defaultdict(list)

        # Crea variabili
        self.tutti_incontri = []

        for classe_id, labs in self.labs_per_classe.items():
            fasce_classe = fasce_per_classe.get(classe_id, [1, 2, 3])  # Default: tutte le fasce

            for lab_id in labs:
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                for k in range(num_inc):
                    key = (classe_id, lab_id, k)
                    self.tutti_incontri.append(key)

                    self.settimana[key] = self.model.NewIntVar(
                        0, self.NUM_SETTIMANE - 1, f"sett_{classe_id}_{lab_id}_{k}"
                    )

                    scuola_id = self.scuola_per_classe[classe_id]
                    max_giorno = 5 if scuola_id in self.SCUOLE_SABATO else 4
                    self.giorno[key] = self.model.NewIntVar(
                        0, max_giorno, f"giorno_{classe_id}_{lab_id}_{k}"
                    )

                    self.fascia[key] = self.model.NewIntVarFromDomain(
                        cp_model.Domain.FromValues(fasce_classe),
                        f"fascia_{classe_id}_{lab_id}_{k}"
                    )

                    self.formatrice[key] = self.model.NewIntVar(
                        min_f, max_f, f"form_{classe_id}_{lab_id}_{k}"
                    )

                    self.slot[key] = self.model.NewIntVar(
                        0, self.NUM_SETTIMANE * 60 + self.NUM_GIORNI * 12 + 12,
                        f"slot_{classe_id}_{lab_id}_{k}"
                    )
                    self.model.Add(
                        self.slot[key] ==
                        self.settimana[key] * 60 + self.giorno[key] * 12 + self.fascia[key]
                    )

        # Variabili accorpamento
        for lab_id, coppie in coppie_per_lab.items():
            for c1, c2 in coppie:
                acc_var = self.model.NewBoolVar(f"acc_{c1}_{c2}_{lab_id}")
                self.accorpa[(c1, c2, lab_id)] = acc_var
                accorpa_per_classe_lab[(c1, lab_id)].append(acc_var)
                accorpa_per_classe_lab[(c2, lab_id)].append(acc_var)

        print(f"  {len(self.tutti_incontri)} incontri, {len(self.accorpa)} var accorpamento")

        # =================== VINCOLI ===================

        # H1b-extra: Ogni classe può essere accorpata con AL MASSIMO un'altra classe per ogni lab
        n_h1b_extra = 0
        for (classe_id, lab_id), acc_vars in accorpa_per_classe_lab.items():
            if len(acc_vars) > 1:
                self.model.Add(sum(acc_vars) <= 1)
                n_h1b_extra += 1

        # Vincolo inizio: settimana 0 solo da giovedì (giorno >= 3)
        # Questo sposta l'inizio effettivo da lunedì 26 a giovedì 29 gennaio
        n_inizio = 0
        for key in self.tutti_incontri:
            is_sett_0 = self.model.NewBoolVar(f"sett0_{key[0]}_{key[1]}_{key[2]}")
            self.model.Add(self.settimana[key] == 0).OnlyEnforceIf(is_sett_0)
            self.model.Add(self.settimana[key] != 0).OnlyEnforceIf(is_sett_0.Not())
            # Se settimana 0, giorno deve essere >= 3 (giovedì o dopo)
            self.model.Add(self.giorno[key] >= 3).OnlyEnforceIf(is_sett_0)
            n_inizio += 1

        # Vincolo fine: ultima settimana (15) solo fino a giovedì (giorno <= 3)
        # Questo fa finire il calendario giovedì 21 maggio
        n_fine = 0
        for key in self.tutti_incontri:
            is_sett_ultima = self.model.NewBoolVar(f"settU_{key[0]}_{key[1]}_{key[2]}")
            self.model.Add(self.settimana[key] == self.NUM_SETTIMANE - 1).OnlyEnforceIf(is_sett_ultima)
            self.model.Add(self.settimana[key] != self.NUM_SETTIMANE - 1).OnlyEnforceIf(is_sett_ultima.Not())
            # Se ultima settimana, giorno deve essere <= 3 (fino a giovedì)
            self.model.Add(self.giorno[key] <= 3).OnlyEnforceIf(is_sett_ultima)
            n_fine += 1

        # Vincolo Pasqua: settimana 9 solo fino a mercoledì (giorno <= 2)
        # Esclude 2-4 aprile (gio-sab settimana 9), poi gap fino al 13 aprile
        n_pasqua = 0
        for key in self.tutti_incontri:
            is_sett_9 = self.model.NewBoolVar(f"sett9_{key[0]}_{key[1]}_{key[2]}")
            self.model.Add(self.settimana[key] == 9).OnlyEnforceIf(is_sett_9)
            self.model.Add(self.settimana[key] != 9).OnlyEnforceIf(is_sett_9.Not())
            # Se settimana 9, giorno deve essere <= 2 (fino a mercoledì 1 aprile)
            self.model.Add(self.giorno[key] <= 2).OnlyEnforceIf(is_sett_9)
            n_pasqua += 1

        # H7: Sabato solo formatrice 4
        n_h7 = 0
        for key in self.tutti_incontri:
            classe_id = key[0]
            scuola_id = self.scuola_per_classe[classe_id]
            if scuola_id in self.SCUOLE_SABATO:
                is_sabato = self.model.NewBoolVar(f"is_sab_{key[0]}_{key[1]}_{key[2]}")
                self.model.Add(self.giorno[key] == 5).OnlyEnforceIf(is_sabato)
                self.model.Add(self.giorno[key] != 5).OnlyEnforceIf(is_sabato.Not())
                self.model.Add(self.formatrice[key] == self.FORMATRICE_SABATO).OnlyEnforceIf(is_sabato)
                n_h7 += 1

        # H2: Max 1 incontro/settimana per classe
        n_h2 = 0
        for classe_id, labs in self.labs_per_classe.items():
            settimane_classe = []
            for lab_id in labs:
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                for k in range(num_inc):
                    settimane_classe.append(self.settimana[(classe_id, lab_id, k)])
            if len(settimane_classe) > 1:
                self.model.AddAllDifferent(settimane_classe)
                n_h2 += 1

        # Ordinamento incontri stesso lab
        n_ord = 0
        for classe_id, labs in self.labs_per_classe.items():
            for lab_id in labs:
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                for k in range(num_inc - 1):
                    self.model.Add(
                        self.settimana[(classe_id, lab_id, k)] <
                        self.settimana[(classe_id, lab_id, k + 1)]
                    )
                    n_ord += 1

        # H4: Sequenzialità laboratori
        n_h4 = 0
        for classe_id, labs in self.labs_per_classe.items():
            labs_senza_8 = [l for l in labs if l != self.LAB_PRESENTAZIONE_MANUALI]
            for i, lab_a in enumerate(labs_senza_8):
                for lab_b in labs_senza_8[i+1:]:
                    num_a = self.num_incontri_lab.get(lab_a, 1)
                    num_b = self.num_incontri_lab.get(lab_b, 1)
                    ultimo_a = self.settimana[(classe_id, lab_a, num_a - 1)]
                    primo_b = self.settimana[(classe_id, lab_b, 0)]
                    ultimo_b = self.settimana[(classe_id, lab_b, num_b - 1)]
                    primo_a = self.settimana[(classe_id, lab_a, 0)]

                    ordine = self.model.NewBoolVar(f"ord_{classe_id}_{lab_a}_{lab_b}")
                    self.model.Add(ultimo_a < primo_b).OnlyEnforceIf(ordine)
                    self.model.Add(ultimo_b < primo_a).OnlyEnforceIf(ordine.Not())
                    n_h4 += 1

        # H3: Presentazione manuali ultimo
        n_h3 = 0
        for classe_id, labs in self.labs_per_classe.items():
            if self.LAB_PRESENTAZIONE_MANUALI not in labs:
                continue
            altri_labs = [l for l in labs if l != self.LAB_PRESENTAZIONE_MANUALI]
            if not altri_labs:
                continue
            primo_8 = self.settimana[(classe_id, self.LAB_PRESENTAZIONE_MANUALI, 0)]
            for altro_lab in altri_labs:
                num_inc = self.num_incontri_lab.get(altro_lab, 1)
                ultimo_altro = self.settimana[(classe_id, altro_lab, num_inc - 1)]
                self.model.Add(ultimo_altro < primo_8)
                n_h3 += 1

        # H1b: Accorpamenti - se attivo, stessi valori
        n_acc = 0
        for (c1, c2, lab_id), accorpa_var in self.accorpa.items():
            num_inc = self.num_incontri_lab.get(lab_id, 1)
            for k in range(num_inc):
                self.model.Add(
                    self.settimana[(c1, lab_id, k)] == self.settimana[(c2, lab_id, k)]
                ).OnlyEnforceIf(accorpa_var)
                self.model.Add(
                    self.giorno[(c1, lab_id, k)] == self.giorno[(c2, lab_id, k)]
                ).OnlyEnforceIf(accorpa_var)
                self.model.Add(
                    self.fascia[(c1, lab_id, k)] == self.fascia[(c2, lab_id, k)]
                ).OnlyEnforceIf(accorpa_var)
                self.model.Add(
                    self.formatrice[(c1, lab_id, k)] == self.formatrice[(c2, lab_id, k)]
                ).OnlyEnforceIf(accorpa_var)
                n_acc += 4

        # H9: No sovrapposizioni formatrice
        # NOTA: Vincolo H9 disabilitato nel modello per ridurre complessità.
        # La verifica delle sovrapposizioni sarà fatta post-hoc con verify_constraints().
        # L'analisi capacità mostra che il problema è fattibile con ~3 slot/giorno.

        # Prepara mapping fascia_id -> (start_minuti, end_minuti) per verifica post-hoc
        fascia_orari = {}
        for _, row in self.data.fasce_orarie_scuole.iterrows():
            fid = int(row['fascia_id'])
            if fid in fascia_orari:
                continue
            ora_inizio = str(row['ora_inizio'])
            ora_fine = str(row['ora_fine'])
            h_i, m_i = map(int, ora_inizio.replace('.', ':').split(':'))
            h_f, m_f = map(int, ora_fine.replace('.', ':').split(':'))
            fascia_orari[fid] = (h_i * 60 + m_i, h_f * 60 + m_f)
        self.fascia_orari = fascia_orari

        print(f"    Fasce orarie: {len(fascia_orari)} (es. fascia 1: {fascia_orari.get(1)})")
        print(f"    H9: DISABILITATO nel modello (verifica post-hoc)")

        # Identifica incontri "secondi" in accorpamenti
        secondo_in_coppia = defaultdict(list)
        for (c1, c2, lab_id), acc_var in self.accorpa.items():
            for k in range(self.num_incontri_lab.get(lab_id, 1)):
                secondo_in_coppia[(c2, lab_id, k)].append(acc_var)

        is_accorpato = {}
        for key, acc_vars in secondo_in_coppia.items():
            if acc_vars:
                c, l, k = key
                is_acc = self.model.NewBoolVar(f"isacc_{c}_{l}_{k}")
                self.model.AddMaxEquality(is_acc, acc_vars)
                is_accorpato[key] = is_acc
        self.is_accorpato = is_accorpato

        # Crea variabili is_formatrice per ogni (f_id, key) - necessarie per budget
        for f_id in tutte_formatrici:
            for key in self.tutti_incontri:
                c, l, k = key
                is_f = self.model.NewBoolVar(f"isf_{f_id}_{c}_{l}_{k}")
                self.model.Add(self.formatrice[key] == f_id).OnlyEnforceIf(is_f)
                self.model.Add(self.formatrice[key] != f_id).OnlyEnforceIf(is_f.Not())
                self.is_formatrice[(f_id, key)] = is_f

        n_h9 = 0  # Nessun vincolo H9 nel modello

        # H12: Date escluse
        date_escluse = defaultdict(list)
        for _, row in self.data.date_escluse_classi.iterrows():
            classe_id = row['classe_id']
            parsed = DateParser.parse_date_escluse(row['date_escluse'])
            date_escluse[classe_id].extend(parsed)

        n_h12 = 0
        for classe_id, escluse_list in date_escluse.items():
            if classe_id not in self.labs_per_classe:
                continue

            for lab_id in self.labs_per_classe[classe_id]:
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                for k in range(num_inc):
                    key = (classe_id, lab_id, k)
                    if key not in self.settimana:
                        continue

                    for sett, giorno_esc, fasce_escluse in escluse_list:
                        if sett is None:
                            continue

                        slot_escluso = sett * 6 + giorno_esc

                        if fasce_escluse is None:
                            self.model.Add(
                                self.settimana[key] * 6 + self.giorno[key] != slot_escluso
                            )
                        else:
                            is_data = self.model.NewBoolVar(f"h12_{n_h12}")
                            self.model.Add(
                                self.settimana[key] * 6 + self.giorno[key] == slot_escluso
                            ).OnlyEnforceIf(is_data)
                            self.model.Add(
                                self.settimana[key] * 6 + self.giorno[key] != slot_escluso
                            ).OnlyEnforceIf(is_data.Not())

                            for fascia_id in fasce_escluse:
                                self.model.Add(self.fascia[key] != fascia_id).OnlyEnforceIf(is_data)
                        n_h12 += 1

        # GSSI: Escludi settimane occupate da lab GSSI
        # Se una classe ha lab GSSI in settimana X, non può fare lab FOP in settimana X
        n_gssi = 0
        for classe_id, settimane_bloccate in self.settimane_gssi.items():
            if classe_id not in self.labs_per_classe:
                continue

            for lab_id in self.labs_per_classe[classe_id]:
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                for k in range(num_inc):
                    key = (classe_id, lab_id, k)
                    if key not in self.settimana:
                        continue

                    for sett_gssi in settimane_bloccate:
                        self.model.Add(self.settimana[key] != sett_gssi)
                        n_gssi += 1

        # H13: Date fissate
        n_h13 = 0
        for _, row in self.data.laboratori_classi.iterrows():
            if pd.isna(row.get('date_fissate')) or row['date_fissate'] == '':
                continue

            classe_id = row['classe_id']
            lab_id = row['laboratorio_id']
            parsed = DateParser.parse_date_fissate(row['date_fissate'])

            if not parsed:
                continue

            num_inc = self.num_incontri_lab.get(lab_id, 1)

            for k, (sett, giorno_fix, fasce_valide) in enumerate(parsed[:num_inc]):
                if sett is None:
                    continue

                key = (classe_id, lab_id, k)
                if key not in self.settimana:
                    continue

                self.model.Add(self.settimana[key] == sett)
                self.model.Add(self.giorno[key] == giorno_fix)

                if fasce_valide:
                    self.model.AddAllowedAssignments(
                        [self.fascia[key]],
                        [[f] for f in fasce_valide]
                    )
                n_h13 += 1

        # H14: Disponibilità formatrice (mattina/pomeriggio per giorno + date specifiche)
        n_h14 = 0
        giorni_map = {'lun': 0, 'mar': 1, 'mer': 2, 'gio': 3, 'ven': 4, 'sab': 5}

        # Mappa fascia -> tipo (mattina/pomeriggio)
        fasce_mattina = DateParser.get_fasce_per_tipo('mattina')
        fasce_pomeriggio = DateParser.get_fasce_per_tipo('pomeriggio')

        # Prepara disponibilità per ogni formatrice
        self.disponibilita_formatrice = {}  # f_id -> dict con info disponibilità

        for _, formatrice in self.data.formatrici.iterrows():
            f_id = int(formatrice['formatrice_id'])

            # Estrai giorni mattina disponibili
            mattine_str = formatrice.get('mattine_disponibili', '')
            if pd.isna(mattine_str) or mattine_str == '':
                mattine_giorni = None  # Nessuna info = usa date_disponibili
            else:
                mattine_giorni = set()
                for g in str(mattine_str).split(','):
                    g = g.strip().lower()
                    if g in giorni_map:
                        mattine_giorni.add(giorni_map[g])

            # Estrai giorni pomeriggio disponibili
            pomeriggi_str = formatrice.get('pomeriggi_disponibili', '')
            if pd.isna(pomeriggi_str) or pomeriggi_str == '':
                pomeriggi_giorni = None
            else:
                pomeriggi_giorni = set()
                for g in str(pomeriggi_str).split(','):
                    g = g.strip().lower()
                    if g in giorni_map:
                        pomeriggi_giorni.add(giorni_map[g])

            # Aggiungi sabato se lavora_sabato = si
            lavora_sab = str(formatrice.get('lavora_sabato', 'no')).strip().lower()
            if lavora_sab == 'si':
                if mattine_giorni is not None:
                    mattine_giorni.add(5)
                if pomeriggi_giorni is not None:
                    pomeriggi_giorni.add(5)

            # Estrai date_disponibili (per Margherita)
            date_disp_str = formatrice.get('date_disponibili', '')
            if pd.isna(date_disp_str) or date_disp_str == '':
                slot_specifici = None
            else:
                parsed = DateParser.parse_date_disponibili(date_disp_str)
                # Converti in set di (sett, giorno, fascia)
                slot_specifici = set()
                for sett, giorno, fasce in parsed:
                    for fascia in fasce:
                        slot_specifici.add((sett, giorno, fascia))

            self.disponibilita_formatrice[f_id] = {
                'mattine': mattine_giorni,
                'pomeriggi': pomeriggi_giorni,
                'slot_specifici': slot_specifici,
                'nome': formatrice['nome']
            }

        # Applica vincoli H14 usando AddForbiddenAssignments (nessuna nuova variabile)
        for f_id, disp in self.disponibilita_formatrice.items():
            mattine = disp['mattine']
            pomeriggi = disp['pomeriggi']
            slot_specifici = disp['slot_specifici']

            # Caso 1: Ha slot specifici (es. Margherita)
            if slot_specifici is not None:
                # Costruisci tuple vietate: (sett, giorno, fascia, f_id)
                slot_permessi = set(slot_specifici)
                forbidden_tuples = []
                for sett in range(self.NUM_SETTIMANE):
                    for giorno in range(6):
                        for fascia in [1, 2, 3]:  # Fasce generiche: mattino1, mattino2, pomeriggio
                            if (sett, giorno, fascia) not in slot_permessi:
                                forbidden_tuples.append([sett, giorno, fascia, f_id])

                print(f"    {disp['nome']}: {len(slot_permessi)} slot permessi, {len(forbidden_tuples)} tuple vietate")

                for key in self.tutti_incontri:
                    self.model.AddForbiddenAssignments(
                        [self.settimana[key], self.giorno[key], self.fascia[key], self.formatrice[key]],
                        forbidden_tuples
                    )
                    n_h14 += 1

            # Caso 2: Ha disponibilità mattina/pomeriggio per giorno
            else:
                # Calcola combo (giorno, fascia) VIETATE per questa formatrice
                # Fasce generiche: 1=mattino1, 2=mattino2, 3=pomeriggio
                forbidden_tuples = []
                for giorno_no in range(6):
                    for fascia in [1, 2, 3]:
                        is_mattina = fascia in [1, 2]  # mattino1, mattino2
                        is_pomeriggio = fascia == 3    # pomeriggio
                        mattina_ok = (not is_mattina) or (mattine is None) or (giorno_no in mattine)
                        pomeriggio_ok = (not is_pomeriggio) or (pomeriggi is None) or (giorno_no in pomeriggi)
                        if not (mattina_ok and pomeriggio_ok):
                            forbidden_tuples.append([giorno_no, fascia, f_id])

                if not forbidden_tuples:
                    continue

                print(f"    {disp['nome']}: {len(forbidden_tuples)} combo (giorno,fascia,formatrice) vietate")

                for key in self.tutti_incontri:
                    self.model.AddForbiddenAssignments(
                        [self.giorno[key], self.fascia[key], self.formatrice[key]],
                        forbidden_tuples
                    )
                    n_h14 += 1

        # Budget ore formatrici
        for _, formatrice in self.data.formatrici.iterrows():
            f_id = int(formatrice['formatrice_id'])
            ore_max = self.ORE_GENERALI.get(f_id, 100)

            contributi = []
            for key in self.tutti_incontri:
                c, l, k = key
                ore = self.ore_per_lab.get(l, 2)
                is_f = self.is_formatrice[(f_id, key)]
                contributi.append(ore * is_f)

            # Sottrai duplicati per accorpamenti
            duplicati = []
            for (c1, c2, lab_id), accorpa_var in self.accorpa.items():
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                ore = self.ore_per_lab.get(lab_id, 2)
                for k in range(num_inc):
                    key_c2 = (c2, lab_id, k)
                    is_f_c2 = self.is_formatrice[(f_id, key_c2)]

                    dup = self.model.NewIntVar(0, 1, f"dup_{f_id}_{c1}_{c2}_{lab_id}_{k}")
                    self.model.AddMultiplicationEquality(dup, [accorpa_var, is_f_c2])
                    duplicati.append(ore * dup)

            ore_effettive = sum(contributi) - sum(duplicati)
            self.model.Add(ore_effettive <= ore_max)
            self.ore_per_formatrice[f_id] = ore_effettive

        # =================== VINCOLI SOFT (OBIETTIVO) ===================
        if self.enable_soft:
            print("\n  Costruzione obiettivo (vincoli soft)...")
            objective_terms = []

            # S1: Continuità formatrice - stessa formatrice per tutti i lab di una classe
            # Per ogni classe, bonus se tutti gli incontri hanno la stessa formatrice
            n_s1 = 0
            for classe_id, labs in self.labs_per_classe.items():
                incontri_classe = []
                for lab_id in labs:
                    num_inc = self.num_incontri_lab.get(lab_id, 1)
                    for k in range(num_inc):
                        incontri_classe.append((classe_id, lab_id, k))

                if len(incontri_classe) <= 1:
                    continue

                # Per ogni coppia di incontri, bonus se stessa formatrice
                primo_incontro = incontri_classe[0]
                for altro_incontro in incontri_classe[1:]:
                    stessa_f = self.model.NewBoolVar(f"s1_{classe_id}_{altro_incontro[1]}_{altro_incontro[2]}")
                    self.model.Add(
                        self.formatrice[primo_incontro] == self.formatrice[altro_incontro]
                    ).OnlyEnforceIf(stessa_f)
                    self.model.Add(
                        self.formatrice[primo_incontro] != self.formatrice[altro_incontro]
                    ).OnlyEnforceIf(stessa_f.Not())
                    objective_terms.append(self.PESO_S1_CONTINUITA * stessa_f)
                    n_s1 += 1
            print(f"    S1 (continuità formatrice): {n_s1} termini")

            # S1b: Accorpamenti preferenziali
            # Bonus per accorpamenti con la classe preferenziale indicata in classi.csv
            n_s1b = 0
            for classe_id, classe_pref_id in self.accorpamento_preferenziale.items():
                # Cerca se esiste la variabile accorpa per questa coppia
                c1, c2 = min(classe_id, classe_pref_id), max(classe_id, classe_pref_id)
                for lab_id in self.labs_per_classe.get(classe_id, []):
                    if (c1, c2, lab_id) in self.accorpa:
                        objective_terms.append(self.PESO_S1B_ACCORPAMENTO_PREF * self.accorpa[(c1, c2, lab_id)])
                        n_s1b += 1
            print(f"    S1b (accorpamenti preferenziali): {n_s1b} termini")

            # S2: Classi quinte prioritarie - devono finire prima
            # Penalità per ogni settimana di ritardo (solo per classi anno=5)
            n_s2 = 0
            for classe_id, labs in self.labs_per_classe.items():
                if self.anno_per_classe.get(classe_id) != 5:
                    continue
                # Trova l'ultima settimana della classe (ultimo incontro)
                for lab_id in labs:
                    num_inc = self.num_incontri_lab.get(lab_id, 1)
                    for k in range(num_inc):
                        key = (classe_id, lab_id, k)
                        # Più bassa la settimana, meglio è (massimizziamo -settimana)
                        # Equivalente: minimizziamo settimana = massimizziamo (MAX_SETT - settimana)
                        inv_sett = self.model.NewIntVar(0, self.NUM_SETTIMANE - 1, f"inv_sett_{classe_id}_{lab_id}_{k}")
                        self.model.Add(inv_sett == self.NUM_SETTIMANE - 1 - self.settimana[key])
                        objective_terms.append(self.PESO_S2_QUINTE_PRIMA * inv_sett)
                        n_s2 += 1
            print(f"    S2 (quinte prima): {n_s2} termini")

            # S3: Ordine ideale laboratori
            # Bonus se l'ordine rispetta: sensibilizzazione (7,9) → citizen science (4) → orientamento (5)
            n_s3 = 0
            for classe_id, labs in self.labs_per_classe.items():
                labs_con_ordine = [(l, self.ORDINE_IDEALE_LAB.get(l, 99)) for l in labs if l != self.LAB_PRESENTAZIONE_MANUALI]
                labs_con_ordine.sort(key=lambda x: x[1])

                for i in range(len(labs_con_ordine) - 1):
                    lab_a, ord_a = labs_con_ordine[i]
                    lab_b, ord_b = labs_con_ordine[i + 1]

                    if ord_a >= ord_b or ord_a == 99 or ord_b == 99:
                        continue  # Non c'è ordine preferito o è lo stesso

                    # Bonus se lab_a finisce prima di lab_b (rispetta ordine ideale)
                    num_a = self.num_incontri_lab.get(lab_a, 1)
                    ultimo_a = self.settimana[(classe_id, lab_a, num_a - 1)]
                    primo_b = self.settimana[(classe_id, lab_b, 0)]

                    ordine_rispettato = self.model.NewBoolVar(f"s3_{classe_id}_{lab_a}_{lab_b}")
                    self.model.Add(ultimo_a < primo_b).OnlyEnforceIf(ordine_rispettato)
                    self.model.Add(ultimo_a >= primo_b).OnlyEnforceIf(ordine_rispettato.Not())
                    objective_terms.append(self.PESO_S3_ORDINE_IDEALE * ordine_rispettato)
                    n_s3 += 1
            print(f"    S3 (ordine ideale lab): {n_s3} termini")

            # Obiettivo finale: massimizza somma pesata
            if objective_terms:
                self.model.Maximize(sum(objective_terms))
                print(f"    Totale termini obiettivo: {len(objective_terms)}")
            else:
                print("    ATTENZIONE: Nessun termine nell'obiettivo!")
        else:
            print("\n  Vincoli soft DISABILITATI (--no-soft)")

        print(f"\n  Vincoli Hard: H1b-extra={n_h1b_extra}, H2={n_h2}, H3={n_h3}, H4={n_h4}, H7={n_h7}, H9={n_h9}, H12={n_h12}, GSSI={n_gssi}, H13={n_h13}, H14={n_h14}")
        print(f"  Vincoli Calendario: inizio_gio={n_inizio}, fine_gio={n_fine}, pasqua={n_pasqua}")

        # Diagnostica capacità
        print("\n  === DIAGNOSTICA CAPACITÀ ===")
        print(f"  Incontri totali: {len(self.tutti_incontri)}")
        ore_totali = sum(self.ore_per_lab.get(key[1], 2) for key in self.tutti_incontri)
        print(f"  Ore totali richieste: {ore_totali}h")
        print(f"  Budget formatrici: {self.ORE_GENERALI} = {sum(self.ORE_GENERALI.values())}h")

        # Conta fasce non sovrapposte per giorno
        fasce_non_sovr = set()  # (tipo_giornata, gruppo_orario)
        for fid, (start, dur) in fascia_orari.items():
            # Raggruppa fasce che non si sovrappongono
            # Mattina: 8-10, 10-12, 11-13 si sovrappongono molto
            # Pomeriggio: 14-16, 16-18, etc.
            # Stima conservativa: 2-3 slot non sovrapposti per mattina/pomeriggio
            pass
        print(f"  Giorni disponibili: ~{(self.NUM_SETTIMANE - 2) * 5} (escluse settimana 0 e 9)")
        print(f"  Slot effettivi stimati per giorno per formatrice: ~3-4")
        print(f"  Capacità stimata: {sum(self.ORE_GENERALI.values())}h (se nessuna sovrapposizione)")
        print("  ===========================")

    def solve(self, time_limit_seconds: int = 300):
        print(f"\nSolver (timeout: {time_limit_seconds}s)...")
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.log_search_progress = self.verbose
        self.solver.parameters.num_search_workers = 12

        status = self.solver.Solve(self.model)

        status_name = self.solver.StatusName()
        wall_time = self.solver.WallTime()
        print(f"  Status: {status_name}, Tempo: {wall_time:.2f}s")

        return status if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None

    def find_h9_overlaps(self):
        """
        Trova tutte le coppie di incontri che si sovrappongono per la stessa formatrice.

        Returns:
            Lista di tuple (key1, key2, form_id, sett, giorno) per ogni sovrapposizione
        """
        # Identifica incontri secondi in accorpamenti attivi
        incontri_secondi = set()
        for (c1, c2, lab_id), acc_var in self.accorpa.items():
            if self.solver.Value(acc_var) == 1:
                for k in range(self.num_incontri_lab.get(lab_id, 1)):
                    incontri_secondi.add((c2, lab_id, k))

        # Raggruppa incontri per formatrice e giorno
        incontri_per_formatrice_giorno = defaultdict(list)
        for key in self.tutti_incontri:
            if key in incontri_secondi:
                continue
            form_id = self.solver.Value(self.formatrice[key])
            sett = self.solver.Value(self.settimana[key])
            giorno = self.solver.Value(self.giorno[key])
            fascia = self.solver.Value(self.fascia[key])
            incontri_per_formatrice_giorno[(form_id, sett, giorno)].append((key, fascia))

        overlaps = []
        for (form_id, sett, giorno), meetings in incontri_per_formatrice_giorno.items():
            if len(meetings) <= 1:
                continue

            for i, (key1, fascia1) in enumerate(meetings):
                for key2, fascia2 in meetings[i+1:]:
                    s1, e1 = self.fascia_orari.get(fascia1, (480, 600))
                    s2, e2 = self.fascia_orari.get(fascia2, (480, 600))
                    if s1 < e2 and s2 < e1:  # Overlap!
                        overlaps.append((key1, key2, form_id, sett, giorno, fascia1, fascia2))

        return overlaps

    def add_h9_constraints_for_overlaps(self, overlaps):
        """
        Aggiunge vincoli per vietare le sovrapposizioni specifiche trovate.

        Per ogni (key1, key2) che si sovrappone nella soluzione corrente:
        - Vieta: stessa formatrice E stesso giorno E fasce sovrapposte

        Args:
            overlaps: lista da find_h9_overlaps()

        Returns:
            Numero di vincoli aggiunti
        """
        n_added = 0

        # Precomputa coppie di fasce sovrapposte
        fasce_sovrapposte_set = set()
        for f1 in self.fascia_orari:
            for f2 in self.fascia_orari:
                s1, e1 = self.fascia_orari[f1]
                s2, e2 = self.fascia_orari[f2]
                if s1 < e2 and s2 < e1:
                    fasce_sovrapposte_set.add((f1, f2))

        fasce_sovrapposte_list = [[f1, f2] for (f1, f2) in fasce_sovrapposte_set]

        for key1, key2, form_id, sett, giorno, fascia1, fascia2 in overlaps:
            # Vincolo: NOT (formatrice[key1] == formatrice[key2] AND
            #               settimana[key1] == settimana[key2] AND
            #               giorno[key1] == giorno[key2] AND
            #               fasce sovrapposte)
            #
            # Equivalente: se stessa formatrice E stesso giorno -> fasce non sovrapposte

            # Crea variabile "stesso giorno"
            same_day = self.model.NewBoolVar(f"sd_h9_{n_added}")
            day_slot_1 = self.settimana[key1] * 6 + self.giorno[key1]
            day_slot_2 = self.settimana[key2] * 6 + self.giorno[key2]
            self.model.Add(day_slot_1 == day_slot_2).OnlyEnforceIf(same_day)
            self.model.Add(day_slot_1 != day_slot_2).OnlyEnforceIf(same_day.Not())

            # Crea variabile "stessa formatrice"
            same_form = self.model.NewBoolVar(f"sf_h9_{n_added}")
            self.model.Add(self.formatrice[key1] == self.formatrice[key2]).OnlyEnforceIf(same_form)
            self.model.Add(self.formatrice[key1] != self.formatrice[key2]).OnlyEnforceIf(same_form.Not())

            # Se same_day AND same_form -> fasce non sovrapposte
            conflict = self.model.NewBoolVar(f"cf_h9_{n_added}")
            self.model.AddBoolAnd([same_day, same_form]).OnlyEnforceIf(conflict)
            self.model.AddBoolOr([same_day.Not(), same_form.Not()]).OnlyEnforceIf(conflict.Not())

            self.model.AddForbiddenAssignments(
                [self.fascia[key1], self.fascia[key2]],
                fasce_sovrapposte_list
            ).OnlyEnforceIf(conflict)

            n_added += 1

        return n_added

    def verify_constraints(self):
        """Verifica esplicita di tutti i vincoli sulla soluzione."""
        print("\n" + "=" * 60)
        print("VERIFICA VINCOLI")
        print("=" * 60)

        errors = []
        warnings = []

        # Identifica accorpamenti attivi
        accorpamenti_attivi = set()
        for (c1, c2, lab_id), acc_var in self.accorpa.items():
            if self.solver.Value(acc_var) == 1:
                accorpamenti_attivi.add((c1, c2, lab_id))

        incontri_secondi = set()
        for (c1, c2, lab_id) in accorpamenti_attivi:
            for k in range(self.num_incontri_lab.get(lab_id, 1)):
                incontri_secondi.add((c2, lab_id, k))

        # H2: Max 1 incontro/settimana per classe
        print("\n[H2] Max 1 incontro/settimana per classe")
        h2_violations = 0
        for classe_id, labs in self.labs_per_classe.items():
            settimane_usate = []
            for lab_id in labs:
                for k in range(self.num_incontri_lab.get(lab_id, 1)):
                    key = (classe_id, lab_id, k)
                    sett = self.solver.Value(self.settimana[key])
                    settimane_usate.append(sett)
            if len(settimane_usate) != len(set(settimane_usate)):
                h2_violations += 1
                errors.append(f"H2: Classe {classe_id} ha più incontri nella stessa settimana")
        print(f"  {'OK' if h2_violations == 0 else 'ERRORE'}: {h2_violations} violazioni")

        # H3: Presentazione manuali ultimo
        print("\n[H3] Presentazione manuali ultimo")
        h3_violations = 0
        for classe_id, labs in self.labs_per_classe.items():
            if self.LAB_PRESENTAZIONE_MANUALI not in labs:
                continue
            sett_pm = self.solver.Value(self.settimana[(classe_id, self.LAB_PRESENTAZIONE_MANUALI, 0)])
            for lab_id in labs:
                if lab_id == self.LAB_PRESENTAZIONE_MANUALI:
                    continue
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                sett_ultimo = self.solver.Value(self.settimana[(classe_id, lab_id, num_inc - 1)])
                if sett_ultimo >= sett_pm:
                    h3_violations += 1
                    errors.append(f"H3: Classe {classe_id}, lab {lab_id} finisce dopo presentazione manuali")
        print(f"  {'OK' if h3_violations == 0 else 'ERRORE'}: {h3_violations} violazioni")

        # H4: Sequenzialità laboratori
        print("\n[H4] Sequenzialità laboratori")
        h4_violations = 0
        for classe_id, labs in self.labs_per_classe.items():
            labs_senza_8 = [l for l in labs if l != self.LAB_PRESENTAZIONE_MANUALI]
            for i, lab_a in enumerate(labs_senza_8):
                for lab_b in labs_senza_8[i+1:]:
                    num_a = self.num_incontri_lab.get(lab_a, 1)
                    num_b = self.num_incontri_lab.get(lab_b, 1)
                    ultimo_a = self.solver.Value(self.settimana[(classe_id, lab_a, num_a - 1)])
                    primo_b = self.solver.Value(self.settimana[(classe_id, lab_b, 0)])
                    ultimo_b = self.solver.Value(self.settimana[(classe_id, lab_b, num_b - 1)])
                    primo_a = self.solver.Value(self.settimana[(classe_id, lab_a, 0)])
                    # Deve essere: ultimo_a < primo_b OPPURE ultimo_b < primo_a
                    if not (ultimo_a < primo_b or ultimo_b < primo_a):
                        h4_violations += 1
                        errors.append(f"H4: Classe {classe_id}, lab {lab_a} e {lab_b} si sovrappongono")
        print(f"  {'OK' if h4_violations == 0 else 'ERRORE'}: {h4_violations} violazioni")

        # H5-H7: Sabato
        print("\n[H5-H7] Sabato")
        h5_violations = 0
        h7_violations = 0
        for key in self.tutti_incontri:
            classe_id = key[0]
            giorno = self.solver.Value(self.giorno[key])
            if giorno == 5:  # Sabato
                scuola_id = self.scuola_per_classe[classe_id]
                if scuola_id not in self.SCUOLE_SABATO:
                    h5_violations += 1
                    errors.append(f"H5: Scuola {scuola_id} lavora sabato (non permesso)")
                form_id = self.solver.Value(self.formatrice[key])
                if form_id != self.FORMATRICE_SABATO:
                    h7_violations += 1
                    errors.append(f"H7: Formatrice {form_id} lavora sabato (solo {self.FORMATRICE_SABATO} permessa)")
        print(f"  H5 (scuole sabato): {'OK' if h5_violations == 0 else 'ERRORE'}: {h5_violations} violazioni")
        print(f"  H7 (formatrice sabato): {'OK' if h7_violations == 0 else 'ERRORE'}: {h7_violations} violazioni")

        # H9: No sovrapposizioni formatrice (verifica OVERLAP REALE, non solo stesso slot)
        print("\n[H9] No sovrapposizioni formatrice (overlap reale)")
        h9_violations = 0
        h9_details = []

        # Raggruppa incontri per formatrice e giorno
        incontri_per_formatrice_giorno = defaultdict(list)
        for key in self.tutti_incontri:
            if key in incontri_secondi:
                continue
            form_id = self.solver.Value(self.formatrice[key])
            sett = self.solver.Value(self.settimana[key])
            giorno = self.solver.Value(self.giorno[key])
            fascia = self.solver.Value(self.fascia[key])
            incontri_per_formatrice_giorno[(form_id, sett, giorno)].append((key, fascia))

        # Per ogni (formatrice, giorno), verifica che le fasce non si sovrappongano
        for (form_id, sett, giorno), meetings in incontri_per_formatrice_giorno.items():
            if len(meetings) <= 1:
                continue

            # Controlla tutte le coppie
            for i, (key1, fascia1) in enumerate(meetings):
                for key2, fascia2 in meetings[i+1:]:
                    # Controlla overlap temporale
                    s1, e1 = self.fascia_orari.get(fascia1, (480, 600))
                    s2, e2 = self.fascia_orari.get(fascia2, (480, 600))
                    if s1 < e2 and s2 < e1:  # Overlap!
                        h9_violations += 1
                        data = settimana_giorno_to_data(sett, giorno)
                        nome_f = self.data.formatrici[self.data.formatrici['formatrice_id'] == form_id]['nome'].iloc[0]
                        h9_details.append(f"H9: {nome_f} il {data}: fascia {fascia1} ({s1//60}:{s1%60:02d}-{e1//60}:{e1%60:02d}) e fascia {fascia2} ({s2//60}:{s2%60:02d}-{e2//60}:{e2%60:02d})")
                        errors.append(h9_details[-1])

        if h9_violations == 0:
            print(f"  OK: nessuna sovrapposizione")
        else:
            print(f"  ERRORE: {h9_violations} sovrapposizioni")
            # Mostra dettagli raggruppati per formatrice
            for detail in h9_details[:10]:
                print(f"    {detail}")
            if len(h9_details) > 10:
                print(f"    ... e altre {len(h9_details) - 10}")

        # H1b: Accorpamenti corretti
        print("\n[H1b] Accorpamenti")
        h1b_violations = 0
        for (c1, c2, lab_id) in accorpamenti_attivi:
            for k in range(self.num_incontri_lab.get(lab_id, 1)):
                key1, key2 = (c1, lab_id, k), (c2, lab_id, k)
                s1, s2 = self.solver.Value(self.settimana[key1]), self.solver.Value(self.settimana[key2])
                g1, g2 = self.solver.Value(self.giorno[key1]), self.solver.Value(self.giorno[key2])
                f1, f2 = self.solver.Value(self.fascia[key1]), self.solver.Value(self.fascia[key2])
                fo1, fo2 = self.solver.Value(self.formatrice[key1]), self.solver.Value(self.formatrice[key2])
                if s1 != s2 or g1 != g2 or f1 != f2 or fo1 != fo2:
                    h1b_violations += 1
                    errors.append(f"H1b: Accorpamento {c1},{c2} lab {lab_id} k={k} non allineato")
        print(f"  {'OK' if h1b_violations == 0 else 'ERRORE'}: {h1b_violations} violazioni")
        print(f"  Accorpamenti attivi: {len(accorpamenti_attivi)}")

        # H12: Date escluse
        print("\n[H12] Date escluse per classe")
        h12_violations = 0
        date_escluse = defaultdict(list)
        for _, row in self.data.date_escluse_classi.iterrows():
            classe_id = row['classe_id']
            parsed = DateParser.parse_date_escluse(row['date_escluse'])
            date_escluse[classe_id].extend(parsed)

        for classe_id, escluse_list in date_escluse.items():
            if classe_id not in self.labs_per_classe:
                continue
            for lab_id in self.labs_per_classe[classe_id]:
                for k in range(self.num_incontri_lab.get(lab_id, 1)):
                    key = (classe_id, lab_id, k)
                    if key not in self.settimana:
                        continue
                    sett = self.solver.Value(self.settimana[key])
                    giorno = self.solver.Value(self.giorno[key])
                    fascia = self.solver.Value(self.fascia[key])

                    for sett_esc, giorno_esc, fasce_escluse in escluse_list:
                        if sett_esc is None:
                            continue
                        if sett == sett_esc and giorno == giorno_esc:
                            if fasce_escluse is None:
                                h12_violations += 1
                                data_esc = settimana_giorno_to_data(sett, giorno)
                                errors.append(f"H12: Classe {classe_id} lab {lab_id} in data esclusa {data_esc}")
                            elif fascia in fasce_escluse:
                                h12_violations += 1
                                data_esc = settimana_giorno_to_data(sett, giorno)
                                errors.append(f"H12: Classe {classe_id} lab {lab_id} in data/fascia esclusa {data_esc} fascia {fascia}")
        print(f"  {'OK' if h12_violations == 0 else 'ERRORE'}: {h12_violations} violazioni")

        # GSSI: Settimane occupate da lab GSSI
        print("\n[GSSI] Settimane GSSI non usate da lab FOP")
        gssi_violations = 0
        for classe_id, settimane_bloccate in self.settimane_gssi.items():
            if classe_id not in self.labs_per_classe:
                continue
            for lab_id in self.labs_per_classe[classe_id]:
                for k in range(self.num_incontri_lab.get(lab_id, 1)):
                    key = (classe_id, lab_id, k)
                    if key not in self.settimana:
                        continue
                    sett = self.solver.Value(self.settimana[key])

                    if sett in settimane_bloccate:
                        gssi_violations += 1
                        errors.append(f"GSSI: Classe {classe_id} lab {lab_id} in settimana {sett+1} (occupata da GSSI)")
        print(f"  {'OK' if gssi_violations == 0 else 'ERRORE'}: {gssi_violations} violazioni")

        # H13: Date fissate
        print("\n[H13] Date fissate")
        h13_violations = 0
        h13_checked = 0
        for _, row in self.data.laboratori_classi.iterrows():
            if pd.isna(row.get('date_fissate')) or row['date_fissate'] == '':
                continue
            classe_id = row['classe_id']
            lab_id = row['laboratorio_id']
            parsed = DateParser.parse_date_fissate(row['date_fissate'])
            if not parsed:
                continue

            num_inc = self.num_incontri_lab.get(lab_id, 1)
            for k, (sett_fix, giorno_fix, fasce_valide) in enumerate(parsed[:num_inc]):
                if sett_fix is None:
                    continue
                key = (classe_id, lab_id, k)
                if key not in self.settimana:
                    continue

                sett = self.solver.Value(self.settimana[key])
                giorno = self.solver.Value(self.giorno[key])
                fascia = self.solver.Value(self.fascia[key])
                h13_checked += 1

                if sett != sett_fix or giorno != giorno_fix:
                    h13_violations += 1
                    errors.append(f"H13: Classe {classe_id} lab {lab_id} k={k} non in data fissata (sett={sett} vs {sett_fix}, g={giorno} vs {giorno_fix})")
                elif fasce_valide and fascia not in fasce_valide:
                    h13_violations += 1
                    errors.append(f"H13: Classe {classe_id} lab {lab_id} k={k} fascia {fascia} non in fasce valide {fasce_valide}")
        print(f"  {'OK' if h13_violations == 0 else 'ERRORE'}: {h13_violations} violazioni (su {h13_checked} fissate)")

        # H14: Disponibilità formatrice (mattina/pomeriggio + slot specifici)
        print("\n[H14] Disponibilità formatrice")
        h14_violations = 0
        giorni_nome_map = {0: 'lun', 1: 'mar', 2: 'mer', 3: 'gio', 4: 'ven', 5: 'sab'}
        fasce_mattina = DateParser.get_fasce_per_tipo('mattina')
        fasce_pomeriggio = DateParser.get_fasce_per_tipo('pomeriggio')

        for key in self.tutti_incontri:
            form_id = self.solver.Value(self.formatrice[key])
            sett = self.solver.Value(self.settimana[key])
            giorno = self.solver.Value(self.giorno[key])
            fascia = self.solver.Value(self.fascia[key])

            disp = self.disponibilita_formatrice.get(form_id)
            if disp is None:
                continue

            nome = disp['nome']
            slot_specifici = disp['slot_specifici']
            mattine = disp['mattine']
            pomeriggi = disp['pomeriggi']

            # Caso 1: Slot specifici (Margherita)
            if slot_specifici is not None:
                if (sett, giorno, fascia) not in slot_specifici:
                    h14_violations += 1
                    data = settimana_giorno_to_data(sett, giorno)
                    errors.append(f"H14: {nome} lavora {data} fascia {fascia} ma non in slot disponibili")
            # Caso 2: Mattine/Pomeriggi
            else:
                is_mattina = fascia in fasce_mattina
                is_pomeriggio = fascia in fasce_pomeriggio

                if is_mattina and mattine is not None and giorno not in mattine:
                    h14_violations += 1
                    errors.append(f"H14: {nome} lavora {giorni_nome_map[giorno]} mattina ma non disponibile")
                if is_pomeriggio and pomeriggi is not None and giorno not in pomeriggi:
                    h14_violations += 1
                    errors.append(f"H14: {nome} lavora {giorni_nome_map[giorno]} pomeriggio ma non disponibile")

        print(f"  {'OK' if h14_violations == 0 else 'ERRORE'}: {h14_violations} violazioni")

        # Budget ore formatrici
        print("\n[BUDGET] Ore formatrici")
        budget_violations = 0
        for _, form in self.data.formatrici.iterrows():
            f_id = int(form['formatrice_id'])
            ore_max = self.ORE_GENERALI.get(f_id, 100)

            ore_effettive = 0
            for key in self.tutti_incontri:
                if self.solver.Value(self.formatrice[key]) == f_id:
                    if key not in incontri_secondi:
                        ore_effettive += self.ore_per_lab.get(key[1], 2)

            status = "OK" if ore_effettive <= ore_max else "SUPERATO"
            if ore_effettive > ore_max:
                budget_violations += 1
                errors.append(f"BUDGET: {form['nome']} ha {ore_effettive}h > max {ore_max}h")
            print(f"  {form['nome']}: {ore_effettive}h / {ore_max}h [{status}]")

        # Riepilogo
        print("\n" + "=" * 60)
        if errors:
            print(f"ERRORI TROVATI: {len(errors)}")
            for err in errors[:10]:
                print(f"  - {err}")
            if len(errors) > 10:
                print(f"  ... e altri {len(errors) - 10}")
        else:
            print("TUTTI I VINCOLI RISPETTATI")
        print("=" * 60)

        return len(errors) == 0

    def verify_soft_constraints(self):
        """Verifica e mostra statistiche sui vincoli soft."""
        print("\n" + "=" * 60)
        print("STATISTICHE VINCOLI SOFT")
        print("=" * 60)

        # S1: Continuità formatrice
        print("\n[S1] Continuità formatrice per classe")
        continuita_totale = 0
        continuita_ok = 0
        classi_con_cambio = []

        for classe_id, labs in self.labs_per_classe.items():
            formatrici_usate = set()
            for lab_id in labs:
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                for k in range(num_inc):
                    key = (classe_id, lab_id, k)
                    f_id = self.solver.Value(self.formatrice[key])
                    formatrici_usate.add(f_id)

            if len(formatrici_usate) == 1:
                continuita_ok += 1
            else:
                classe_nome = self.data.classi[self.data.classi['classe_id'] == classe_id]['nome'].iloc[0]
                nomi_f = [self.data.formatrici[self.data.formatrici['formatrice_id'] == f]['nome'].iloc[0]
                          for f in formatrici_usate]
                classi_con_cambio.append((classe_nome, nomi_f))
            continuita_totale += 1

        print(f"  Classi con stessa formatrice: {continuita_ok}/{continuita_totale} ({100*continuita_ok/continuita_totale:.1f}%)")
        if classi_con_cambio and len(classi_con_cambio) <= 10:
            for classe, formatrici in classi_con_cambio:
                print(f"    {classe}: {', '.join(formatrici)}")
        elif classi_con_cambio:
            print(f"    ... {len(classi_con_cambio)} classi con cambi formatrice")

        # S1b: Accorpamenti preferenziali
        print("\n[S1b] Accorpamenti preferenziali")
        acc_pref_totali = len(self.accorpamento_preferenziale)
        acc_pref_attivi = 0

        for classe_id, classe_pref_id in self.accorpamento_preferenziale.items():
            c1, c2 = min(classe_id, classe_pref_id), max(classe_id, classe_pref_id)
            # Verifica se almeno un lab è accorpato
            for lab_id in self.labs_per_classe.get(classe_id, []):
                if (c1, c2, lab_id) in self.accorpa:
                    if self.solver.Value(self.accorpa[(c1, c2, lab_id)]) == 1:
                        acc_pref_attivi += 1
                        break

        print(f"  Coppie preferenziali attivate: {acc_pref_attivi}/{acc_pref_totali//2}")  # Diviso 2 perché bidirezionale

        # S2: Classi quinte - settimana di fine
        print("\n[S2] Classi quinte - settimana conclusione")
        settimane_quinte = []
        settimane_altre = []

        for classe_id, labs in self.labs_per_classe.items():
            max_sett = 0
            for lab_id in labs:
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                key = (classe_id, lab_id, num_inc - 1)
                sett = self.solver.Value(self.settimana[key])
                max_sett = max(max_sett, sett)

            if self.anno_per_classe.get(classe_id) == 5:
                settimane_quinte.append(max_sett + 1)
            else:
                settimane_altre.append(max_sett + 1)

        if settimane_quinte:
            media_quinte = sum(settimane_quinte) / len(settimane_quinte)
            print(f"  Quinte: media sett. {media_quinte:.1f}, max sett. {max(settimane_quinte)}, min sett. {min(settimane_quinte)}")
        if settimane_altre:
            media_altre = sum(settimane_altre) / len(settimane_altre)
            print(f"  Altre:  media sett. {media_altre:.1f}, max sett. {max(settimane_altre)}, min sett. {min(settimane_altre)}")

        # S3: Ordine ideale laboratori
        print("\n[S3] Ordine ideale laboratori (sensibilizzazione → citizen → orientamento)")
        ordine_rispettato = 0
        ordine_totale = 0

        for classe_id, labs in self.labs_per_classe.items():
            labs_con_ordine = [(l, self.ORDINE_IDEALE_LAB.get(l, 99)) for l in labs if l != self.LAB_PRESENTAZIONE_MANUALI]
            labs_con_ordine.sort(key=lambda x: x[1])

            for i in range(len(labs_con_ordine) - 1):
                lab_a, ord_a = labs_con_ordine[i]
                lab_b, ord_b = labs_con_ordine[i + 1]

                if ord_a >= ord_b or ord_a == 99 or ord_b == 99:
                    continue

                num_a = self.num_incontri_lab.get(lab_a, 1)
                ultimo_a = self.solver.Value(self.settimana[(classe_id, lab_a, num_a - 1)])
                primo_b = self.solver.Value(self.settimana[(classe_id, lab_b, 0)])

                ordine_totale += 1
                if ultimo_a < primo_b:
                    ordine_rispettato += 1

        if ordine_totale > 0:
            print(f"  Ordine rispettato: {ordine_rispettato}/{ordine_totale} ({100*ordine_rispettato/ordine_totale:.1f}%)")
        else:
            print("  Nessuna coppia con ordine preferito")

        # Riepilogo accorpamenti
        print("\n[ACCORPAMENTI] Riepilogo")
        accorpamenti_attivi = []
        for (c1, c2, lab_id), acc_var in self.accorpa.items():
            if self.solver.Value(acc_var) == 1:
                accorpamenti_attivi.append((c1, c2, lab_id))

        print(f"  Accorpamenti attivi: {len(accorpamenti_attivi)}")

        # Conta per scuola
        acc_per_scuola = defaultdict(int)
        for c1, c2, lab_id in accorpamenti_attivi:
            scuola_id = self.scuola_per_classe[c1]
            scuola_nome = self.data.scuole[self.data.scuole['scuola_id'] == scuola_id]['nome'].iloc[0]
            acc_per_scuola[scuola_nome] += 1

        for scuola, count in sorted(acc_per_scuola.items(), key=lambda x: -x[1]):
            print(f"    {scuola}: {count}")

        print("=" * 60)

    def _map_fascia_generica_a_specifica(self, fascia_generica_num, scuola_id):
        """Mappa fascia generica (1/2/3) a fascia specifica per output

        1 -> mattino1 -> prima fascia mattutina della scuola
        2 -> mattino2 -> seconda fascia mattutina della scuola
        3 -> pomeriggio -> fisso "14-16"
        """
        if fascia_generica_num == 3:  # pomeriggio
            return '14-16'

        # Per mattino1 e mattino2, prende la prima e seconda fascia della scuola
        fasce_scuola = self.data.fasce_orarie_scuole[
            self.data.fasce_orarie_scuole['scuola_id'] == scuola_id
        ].sort_values('fascia_id')

        if fascia_generica_num == 1 and len(fasce_scuola) >= 1:  # mattino1
            return fasce_scuola.iloc[0]['nome']
        elif fascia_generica_num == 2 and len(fasce_scuola) >= 2:  # mattino2
            return fasce_scuola.iloc[1]['nome']
        else:
            # Fallback
            return self.FASCE_INVERSE.get(fascia_generica_num, str(fascia_generica_num))

    def export_results(self, output_path: str):
        giorni_nome = ['01-lun', '02-mar', '03-mer', '04-gio', '05-ven', '06-sab']
        risultati = []

        accorpamenti_attivi = {}
        secondi_da_saltare = set()

        for (c1, c2, lab_id), acc_var in self.accorpa.items():
            if self.solver.Value(acc_var) == 1:
                num_inc = self.num_incontri_lab.get(lab_id, 1)
                for k in range(num_inc):
                    accorpamenti_attivi[(c1, lab_id, k)] = c2
                    secondi_da_saltare.add((c2, lab_id, k))

        for key, sett_var in self.settimana.items():
            classe_id, lab_id, k = key

            if key in secondi_da_saltare:
                continue

            sett = self.solver.Value(sett_var)
            giorno = self.solver.Value(self.giorno[key])
            fascia = self.solver.Value(self.fascia[key])
            form_id = self.solver.Value(self.formatrice[key])

            data_incontro = settimana_giorno_to_data(sett, giorno)

            classe_row = self.data.classi[self.data.classi['classe_id'] == classe_id].iloc[0]
            lab_row = self.data.laboratori[self.data.laboratori['laboratorio_id'] == lab_id].iloc[0]
            form_row = self.data.formatrici[self.data.formatrici['formatrice_id'] == form_id].iloc[0]
            scuola_row = self.data.scuole[self.data.scuole['scuola_id'] == classe_row['scuola_id']].iloc[0]

            classi_list = [classe_row['nome']]
            if key in accorpamenti_attivi:
                altra_classe_id = accorpamenti_attivi[key]
                altra_classe_row = self.data.classi[self.data.classi['classe_id'] == altra_classe_id].iloc[0]
                classi_list.append(altra_classe_row['nome'])

            classi_str = ','.join(sorted(classi_list))

            # Mapping fascia generica (1/2/3) -> fascia specifica
            fascia_specifica = self._map_fascia_generica_a_specifica(fascia, classe_row['scuola_id'])
            fascia_generica_nome = self.FASCE_INVERSE.get(fascia, str(fascia))

            risultati.append({
                'settimana': sett + 1,
                'giorno': giorni_nome[giorno],
                'data': data_incontro.strftime('%d/%m/%Y'),
                'fascia': fascia_specifica,
                'fascia_generica': fascia_generica_nome,
                '_fascia_id': fascia,  # Per ordinamento
                'classi': classi_str,
                'scuola': scuola_row['nome'],
                'citta': scuola_row['citta'],
                'laboratorio': lab_row['nome'],
                'incontro': k + 1,
                'formatrice': form_row['nome'],
            })

        df = pd.DataFrame(risultati)
        df = df.sort_values(['settimana', 'giorno', '_fascia_id', 'scuola', 'classi'])
        df = df.drop(columns=['_fascia_id'])
        df.to_csv(output_path, index=False)
        print(f"\nEsportato: {output_path} ({len(df)} incontri)")


def main():
    parser = argparse.ArgumentParser(description='Optimizer V5 - Con vincoli soft')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostra log dettagliato del solver')
    parser.add_argument('--timeout', '-t', type=int, default=300, help='Timeout solver in secondi (default: 300)')
    parser.add_argument('--output', '-o', type=str, default='data/output/calendario_V5.csv', help='File output')
    parser.add_argument('--no-soft', action='store_true', help='Disabilita vincoli soft (solo hard constraints)')
    parser.add_argument('--max-iterations', type=int, default=10, help='Max iterazioni per eliminare sovrapposizioni H9')
    args = parser.parse_args()

    enable_soft = not args.no_soft
    mode = "Con Vincoli Soft" if enable_soft else "SOLO Hard Constraints"

    print("=" * 60)
    print(f"  OPTIMIZER V5 - {mode}")
    print("=" * 60)

    data = DataLoader("data/input").load_all()
    optimizer = OptimizerV5(data, verbose=args.verbose, enable_soft=enable_soft)
    optimizer.build_model()

    # Approccio iterativo: risolvi, trova sovrapposizioni, aggiungi vincoli, ripeti
    for iteration in range(args.max_iterations):
        print(f"\n{'='*60}")
        print(f"  ITERAZIONE {iteration + 1}")
        print(f"{'='*60}")

        if not optimizer.solve(time_limit_seconds=args.timeout):
            print("\nNessuna soluzione trovata.")
            sys.exit(1)

        # Trova sovrapposizioni H9
        overlaps = optimizer.find_h9_overlaps()

        if not overlaps:
            print(f"\n  Nessuna sovrapposizione H9! Soluzione valida trovata.")
            break

        print(f"\n  Trovate {len(overlaps)} sovrapposizioni H9.")

        if iteration == args.max_iterations - 1:
            print(f"  Raggiunto max iterazioni ({args.max_iterations}). Esporto comunque.")
            break

        # Aggiungi vincoli per queste sovrapposizioni
        n_added = optimizer.add_h9_constraints_for_overlaps(overlaps)
        print(f"  Aggiunti {n_added} vincoli anti-sovrapposizione. Ri-eseguo...")

    optimizer.verify_constraints()
    if enable_soft:
        optimizer.verify_soft_constraints()
    optimizer.export_results(args.output)
    print("\nCompletato!")


if __name__ == "__main__":
    main()
