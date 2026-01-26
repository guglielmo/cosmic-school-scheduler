#!/usr/bin/env python3
"""
Optimizer V6 - Scheduling laboratori con domini pre-calcolati e H9 pre-filtrato

Migliorie rispetto a V5:
1. Usa DomainPreprocessor per ridurre lo spazio di ricerca
2. Crea variabili solo per slot validi (non tutto il dominio)
3. Filtra coppie accorpamento incompatibili a priori
4. Pre-filtra coppie per vincolo H9 (no overlap formatrici)
5. Aggiunge H9 direttamente nel modello (niente iterazioni)
6. Statistiche dettagliate sulla riduzione

Variabili per ogni incontro (classe, lab, k):
- settimana[c,l,k] = IntVar con dominio ridotto
- giorno[c,l,k] = IntVar con dominio ridotto
- fascia[c,l,k] = IntVar con dominio ridotto
- formatrice[c,l,k] = IntVar(1..4)

Per accorpamenti (solo coppie compatibili):
- accorpa[c1,c2,lab] = BoolVar

Vincolo H9 (no overlap formatrici):
- Pre-filtra coppie usando intersezione domini
- Aggiunge vincoli solo per coppie potenzialmente sovrapposti
- Riduzione da O(N²) a O(k×N) con k << N
"""

import argparse
import pandas as pd
from ortools.sat.python import cp_model
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta
from typing import List, Tuple
import sys

from date_parser import DateParser
from domain_preprocessor import DomainPreprocessor, SlotDomain


def settimana_giorno_to_data(settimana: int, giorno: int) -> date:
    """Converte (settimana 0-15, giorno 0-5) in data reale."""
    data_inizio = date(2026, 1, 26)

    if settimana <= 9:
        offset = settimana * 7 + giorno
        return data_inizio + timedelta(days=offset)
    else:
        data_post_pasqua = date(2026, 4, 13)
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


class OptimizerV6:
    NUM_SETTIMANE = 16
    NUM_GIORNI = 6
    LAB_PRESENTAZIONE_MANUALI = 8
    ORE_GENERALI = {1: 292, 2: 128, 3: 160, 4: 128}
    SCUOLE_SABATO = {10, 13}
    FORMATRICE_SABATO = 4

    FASCE_GENERICHE = {'mattino1': 1, 'mattino2': 2, 'pomeriggio': 3}
    FASCE_INVERSE = {1: 'mattino1', 2: 'mattino2', 3: 'pomeriggio'}

    # Pesi vincoli soft
    PESO_S1_CONTINUITA = 100
    PESO_S1B_ACCORPAMENTO_PREF = 50
    PESO_S2_QUINTE_PRIMA = 10
    PESO_S3_ORDINE_IDEALE = 20

    ORDINE_IDEALE_LAB = {7: 1, 9: 2, 4: 3, 5: 4}

    def __init__(self, data: DataLoader, preprocessor: DomainPreprocessor,
                 verbose: bool = False, enable_soft: bool = True):
        self.data = data
        self.preprocessor = preprocessor
        self.verbose = verbose
        self.enable_soft = enable_soft
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Variabili
        self.settimana = {}
        self.giorno = {}
        self.fascia = {}
        self.formatrice = {}
        self.accorpa = {}
        self.slot = {}
        self.is_formatrice = {}
        self.ore_per_formatrice = {}

        # Dati preprocessati
        self.labs_per_classe = None
        self.scuola_per_classe = None
        self.ore_per_lab = None
        self.num_incontri_lab = None
        self.tutti_incontri = None
        self.anno_per_classe = None
        self.accorpamento_preferenziale = None

        # Statistiche
        self.stats = {
            'variabili_risparmiate': 0,
            'coppie_filtrate': 0,
            'slot_totali_originali': 0,
            'slot_totali_ridotti': 0
        }

    def build_model(self):
        print("=" * 60)
        print("  OPTIMIZER V6 - Con Domini Pre-calcolati")
        print("=" * 60)
        print("\nCostruzione modello...")

        DateParser.load_fasce_info(self.data.fasce_orarie_scuole)

        # Usa dati dal preprocessor
        self.labs_per_classe = self.preprocessor.labs_per_classe
        self.scuola_per_classe = self.preprocessor.scuola_per_classe
        self.anno_per_classe = self.preprocessor.anno_per_classe
        self.num_incontri_lab = self.preprocessor.num_incontri_lab

        # Carica ore per lab
        self.ore_per_lab = {}
        for _, lab in self.data.laboratori.iterrows():
            self.ore_per_lab[lab['laboratorio_id']] = int(lab['ore_per_incontro'])

        # Accorpamenti preferenziali
        self.accorpamento_preferenziale = {}
        for _, row in self.data.classi.iterrows():
            acc_pref = row.get('accorpamento_preferenziale', '')
            if pd.notna(acc_pref) and acc_pref != '':
                scuola_id = row['scuola_id']
                classe_pref = self.data.classi[
                    (self.data.classi['nome'] == acc_pref) &
                    (self.data.classi['scuola_id'] == scuola_id)
                ]
                if len(classe_pref) > 0:
                    self.accorpamento_preferenziale[row['classe_id']] = int(classe_pref.iloc[0]['classe_id'])

        # Identifica lab GSSI
        lab_ids_validi = set(self.data.laboratori['laboratorio_id'].values)
        tutti_lab_ids = set(self.data.laboratori_classi['laboratorio_id'].values)
        lab_ids_gssi = tutti_lab_ids - lab_ids_validi
        print(f"  Lab FOP: {sorted(lab_ids_validi)}, Lab GSSI: {sorted(lab_ids_gssi)}")

        # Raccogli settimane GSSI
        self.settimane_gssi = defaultdict(set)
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

        tot_settimane_bloccate = sum(len(s) for s in self.settimane_gssi.values())
        print(f"  Settimane GSSI bloccate: {tot_settimane_bloccate}")

        tutte_formatrici = list(self.data.formatrici['formatrice_id'].astype(int))
        min_f, max_f = min(tutte_formatrici), max(tutte_formatrici)

        # =================== CREAZIONE VARIABILI CON DOMINI RIDOTTI ===================
        print("\n  Creazione variabili con domini pre-calcolati...")

        self.tutti_incontri = []
        vars_created = 0
        vars_would_be_created = 0

        for classe_id, labs in self.labs_per_classe.items():
            if classe_id not in self.preprocessor.class_domains:
                continue

            cd = self.preprocessor.class_domains[classe_id]

            for lab_id in labs:
                num_inc = self.num_incontri_lab.get(lab_id, 1)

                for k in range(num_inc):
                    key = (classe_id, lab_id, k)
                    self.tutti_incontri.append(key)

                    # Ottieni dominio specifico per questo incontro
                    domain = self.preprocessor.get_domain_for_meeting(classe_id, lab_id, k)
                    valid_slots = domain.get_valid_slots()

                    # Statistiche
                    vars_would_be_created += self.NUM_SETTIMANE * self.NUM_GIORNI * 3
                    vars_created += len(valid_slots) if valid_slots else self.NUM_SETTIMANE * self.NUM_GIORNI * 3

                    if valid_slots and len(valid_slots) < self.NUM_SETTIMANE * self.NUM_GIORNI * 3:
                        # Dominio ridotto: crea variabili con domini specifici
                        valid_weeks = sorted(domain.weeks)
                        self.settimana[key] = self.model.NewIntVarFromDomain(
                            cp_model.Domain.FromValues(valid_weeks),
                            f"sett_{classe_id}_{lab_id}_{k}"
                        )

                        # Per giorno e fascia, usiamo il dominio completo ma
                        # aggiungiamo vincoli per combinazioni valide
                        all_days = set()
                        for w in valid_weeks:
                            all_days.update(domain.days_per_week.get(w, set()))

                        scuola_id = self.scuola_per_classe[classe_id]
                        max_giorno = 5 if scuola_id in self.SCUOLE_SABATO else 4
                        valid_days = sorted(d for d in all_days if d <= max_giorno)

                        if valid_days:
                            self.giorno[key] = self.model.NewIntVarFromDomain(
                                cp_model.Domain.FromValues(valid_days),
                                f"giorno_{classe_id}_{lab_id}_{k}"
                            )
                        else:
                            self.giorno[key] = self.model.NewIntVar(
                                0, max_giorno, f"giorno_{classe_id}_{lab_id}_{k}"
                            )

                        all_fasce = set()
                        for (w, d), fasce in domain.slots_per_day.items():
                            all_fasce.update(fasce)

                        if all_fasce:
                            self.fascia[key] = self.model.NewIntVarFromDomain(
                                cp_model.Domain.FromValues(sorted(all_fasce)),
                                f"fascia_{classe_id}_{lab_id}_{k}"
                            )
                        else:
                            self.fascia[key] = self.model.NewIntVarFromDomain(
                                cp_model.Domain.FromValues([1, 2, 3]),
                                f"fascia_{classe_id}_{lab_id}_{k}"
                            )

                        # Vincolo: combinazione (settimana, giorno, fascia) deve essere valida
                        valid_tuples = [[s, d, f] for (s, d, f) in valid_slots]
                        if valid_tuples:
                            self.model.AddAllowedAssignments(
                                [self.settimana[key], self.giorno[key], self.fascia[key]],
                                valid_tuples
                            )
                    else:
                        # Dominio completo (fallback)
                        self.settimana[key] = self.model.NewIntVar(
                            0, self.NUM_SETTIMANE - 1, f"sett_{classe_id}_{lab_id}_{k}"
                        )

                        scuola_id = self.scuola_per_classe[classe_id]
                        max_giorno = 5 if scuola_id in self.SCUOLE_SABATO else 4
                        self.giorno[key] = self.model.NewIntVar(
                            0, max_giorno, f"giorno_{classe_id}_{lab_id}_{k}"
                        )

                        self.fascia[key] = self.model.NewIntVarFromDomain(
                            cp_model.Domain.FromValues([1, 2, 3]),
                            f"fascia_{classe_id}_{lab_id}_{k}"
                        )

                    # Formatrice sempre dominio completo
                    self.formatrice[key] = self.model.NewIntVar(
                        min_f, max_f, f"form_{classe_id}_{lab_id}_{k}"
                    )

                    # Slot per vincoli H9
                    self.slot[key] = self.model.NewIntVar(
                        0, self.NUM_SETTIMANE * 60 + self.NUM_GIORNI * 12 + 12,
                        f"slot_{classe_id}_{lab_id}_{k}"
                    )
                    self.model.Add(
                        self.slot[key] ==
                        self.settimana[key] * 60 + self.giorno[key] * 12 + self.fascia[key]
                    )

        self.stats['slot_totali_originali'] = vars_would_be_created
        self.stats['slot_totali_ridotti'] = vars_created
        reduction_pct = 100 * (1 - vars_created / vars_would_be_created) if vars_would_be_created > 0 else 0
        print(f"    Variabili slot: {vars_would_be_created} -> {vars_created} ({reduction_pct:.1f}% riduzione)")

        # =================== VARIABILI ACCORPAMENTO (SOLO COPPIE COMPATIBILI) ===================
        print("\n  Creazione variabili accorpamento (solo coppie compatibili)...")

        accorpa_per_classe_lab = defaultdict(list)
        coppie_totali = 0
        coppie_create = 0

        # Raggruppa coppie compatibili per lab
        coppie_per_lab = defaultdict(list)
        for pair in self.preprocessor.grouping_pairs:
            coppie_per_lab[pair.lab_id].append((pair.class1_id, pair.class2_id, pair.compatibility_score))

        for lab_id, coppie in coppie_per_lab.items():
            for c1, c2, score in coppie:
                coppie_totali += 1

                # Filtra coppie con bassa compatibilità (opzionale)
                # if score < 0.3:
                #     self.stats['coppie_filtrate'] += 1
                #     continue

                acc_var = self.model.NewBoolVar(f"acc_{c1}_{c2}_{lab_id}")
                self.accorpa[(c1, c2, lab_id)] = acc_var
                accorpa_per_classe_lab[(c1, lab_id)].append(acc_var)
                accorpa_per_classe_lab[(c2, lab_id)].append(acc_var)
                coppie_create += 1

        print(f"    Coppie accorpamento: {coppie_create}/{coppie_totali} (filtrate: {self.stats['coppie_filtrate']})")
        print(f"  {len(self.tutti_incontri)} incontri, {len(self.accorpa)} var accorpamento")

        # =================== VINCOLI ===================
        print("\n  Aggiunta vincoli...")

        # H1b-extra: Max 1 accorpamento per classe-lab
        n_h1b_extra = 0
        for (classe_id, lab_id), acc_vars in accorpa_per_classe_lab.items():
            if len(acc_vars) > 1:
                self.model.Add(sum(acc_vars) <= 1)
                n_h1b_extra += 1

        # Vincolo inizio: settimana 0 solo da giovedì
        n_inizio = 0
        for key in self.tutti_incontri:
            is_sett_0 = self.model.NewBoolVar(f"sett0_{key[0]}_{key[1]}_{key[2]}")
            self.model.Add(self.settimana[key] == 0).OnlyEnforceIf(is_sett_0)
            self.model.Add(self.settimana[key] != 0).OnlyEnforceIf(is_sett_0.Not())
            self.model.Add(self.giorno[key] >= 3).OnlyEnforceIf(is_sett_0)
            n_inizio += 1

        # Vincolo fine: ultima settimana solo fino a giovedì
        n_fine = 0
        for key in self.tutti_incontri:
            is_sett_ultima = self.model.NewBoolVar(f"settU_{key[0]}_{key[1]}_{key[2]}")
            self.model.Add(self.settimana[key] == self.NUM_SETTIMANE - 1).OnlyEnforceIf(is_sett_ultima)
            self.model.Add(self.settimana[key] != self.NUM_SETTIMANE - 1).OnlyEnforceIf(is_sett_ultima.Not())
            self.model.Add(self.giorno[key] <= 3).OnlyEnforceIf(is_sett_ultima)
            n_fine += 1

        # Vincolo Pasqua: settimana 9 solo fino a mercoledì
        n_pasqua = 0
        for key in self.tutti_incontri:
            is_sett_9 = self.model.NewBoolVar(f"sett9_{key[0]}_{key[1]}_{key[2]}")
            self.model.Add(self.settimana[key] == 9).OnlyEnforceIf(is_sett_9)
            self.model.Add(self.settimana[key] != 9).OnlyEnforceIf(is_sett_9.Not())
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

        # Prepara mapping fascia -> orari per verifica post-hoc
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

        # Crea variabili is_formatrice
        for f_id in tutte_formatrici:
            for key in self.tutti_incontri:
                c, l, k = key
                is_f = self.model.NewBoolVar(f"isf_{f_id}_{c}_{l}_{k}")
                self.model.Add(self.formatrice[key] == f_id).OnlyEnforceIf(is_f)
                self.model.Add(self.formatrice[key] != f_id).OnlyEnforceIf(is_f.Not())
                self.is_formatrice[(f_id, key)] = is_f

        # H9: Pre-filtraggio e aggiunta vincoli no overlap
        print("\n  Pre-filtraggio coppie per H9 (no overlap formatrici)...")
        overlapping_pairs = self._precompute_potentially_overlapping_pairs()
        print(f"    Coppie potenzialmente sovrapposti: {len(overlapping_pairs)}")

        n_h9 = self._add_h9_constraints_prefiltered(overlapping_pairs, tutte_formatrici)
        print(f"    Vincoli H9 aggiunti: {n_h9}")

        # H12: Date escluse (già gestite nel preprocessor, ma aggiungiamo per sicurezza)
        n_h12 = 0
        # Le date escluse sono già incorporate nei domini ridotti

        # GSSI: Escludi settimane occupate
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

        # H14: Disponibilità formatrice
        n_h14 = 0
        giorni_map = {'lun': 0, 'mar': 1, 'mer': 2, 'gio': 3, 'ven': 4, 'sab': 5}
        self.disponibilita_formatrice = {}

        for _, formatrice in self.data.formatrici.iterrows():
            f_id = int(formatrice['formatrice_id'])

            mattine_str = formatrice.get('mattine_disponibili', '')
            if pd.isna(mattine_str) or mattine_str == '':
                mattine_giorni = None
            else:
                mattine_giorni = set()
                for g in str(mattine_str).split(','):
                    g = g.strip().lower()
                    if g in giorni_map:
                        mattine_giorni.add(giorni_map[g])

            pomeriggi_str = formatrice.get('pomeriggi_disponibili', '')
            if pd.isna(pomeriggi_str) or pomeriggi_str == '':
                pomeriggi_giorni = None
            else:
                pomeriggi_giorni = set()
                for g in str(pomeriggi_str).split(','):
                    g = g.strip().lower()
                    if g in giorni_map:
                        pomeriggi_giorni.add(giorni_map[g])

            lavora_sab = str(formatrice.get('lavora_sabato', 'no')).strip().lower()
            if lavora_sab == 'si':
                if mattine_giorni is not None:
                    mattine_giorni.add(5)
                if pomeriggi_giorni is not None:
                    pomeriggi_giorni.add(5)

            date_disp_str = formatrice.get('date_disponibili', '')
            if pd.isna(date_disp_str) or date_disp_str == '':
                slot_specifici = None
            else:
                parsed = DateParser.parse_date_disponibili(date_disp_str)
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

        # Applica vincoli H14
        for f_id, disp in self.disponibilita_formatrice.items():
            mattine = disp['mattine']
            pomeriggi = disp['pomeriggi']
            slot_specifici = disp['slot_specifici']

            if slot_specifici is not None:
                slot_permessi = set(slot_specifici)
                forbidden_tuples = []
                for sett in range(self.NUM_SETTIMANE):
                    for giorno in range(6):
                        for fascia in [1, 2, 3]:
                            if (sett, giorno, fascia) not in slot_permessi:
                                forbidden_tuples.append([sett, giorno, fascia, f_id])

                for key in self.tutti_incontri:
                    self.model.AddForbiddenAssignments(
                        [self.settimana[key], self.giorno[key], self.fascia[key], self.formatrice[key]],
                        forbidden_tuples
                    )
                    n_h14 += 1
            else:
                forbidden_tuples = []
                for giorno_no in range(6):
                    for fascia in [1, 2, 3]:
                        is_mattina = fascia in [1, 2]
                        is_pomeriggio = fascia == 3
                        mattina_ok = (not is_mattina) or (mattine is None) or (giorno_no in mattine)
                        pomeriggio_ok = (not is_pomeriggio) or (pomeriggi is None) or (giorno_no in pomeriggi)
                        if not (mattina_ok and pomeriggio_ok):
                            forbidden_tuples.append([giorno_no, fascia, f_id])

                if forbidden_tuples:
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

        # =================== VINCOLI SOFT ===================
        if self.enable_soft:
            print("\n  Costruzione obiettivo (vincoli soft)...")
            objective_terms = []

            # S1: Continuità formatrice
            n_s1 = 0
            for classe_id, labs in self.labs_per_classe.items():
                incontri_classe = []
                for lab_id in labs:
                    num_inc = self.num_incontri_lab.get(lab_id, 1)
                    for k in range(num_inc):
                        incontri_classe.append((classe_id, lab_id, k))

                if len(incontri_classe) <= 1:
                    continue

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
            n_s1b = 0
            for classe_id, classe_pref_id in self.accorpamento_preferenziale.items():
                c1, c2 = min(classe_id, classe_pref_id), max(classe_id, classe_pref_id)
                for lab_id in self.labs_per_classe.get(classe_id, []):
                    if (c1, c2, lab_id) in self.accorpa:
                        objective_terms.append(self.PESO_S1B_ACCORPAMENTO_PREF * self.accorpa[(c1, c2, lab_id)])
                        n_s1b += 1
            print(f"    S1b (accorpamenti preferenziali): {n_s1b} termini")

            # S2: Classi quinte prioritarie
            n_s2 = 0
            for classe_id, labs in self.labs_per_classe.items():
                if self.anno_per_classe.get(classe_id) != 5:
                    continue
                for lab_id in labs:
                    num_inc = self.num_incontri_lab.get(lab_id, 1)
                    for k in range(num_inc):
                        key = (classe_id, lab_id, k)
                        inv_sett = self.model.NewIntVar(0, self.NUM_SETTIMANE - 1, f"inv_sett_{classe_id}_{lab_id}_{k}")
                        self.model.Add(inv_sett == self.NUM_SETTIMANE - 1 - self.settimana[key])
                        objective_terms.append(self.PESO_S2_QUINTE_PRIMA * inv_sett)
                        n_s2 += 1
            print(f"    S2 (quinte prima): {n_s2} termini")

            # S3: Ordine ideale laboratori
            n_s3 = 0
            for classe_id, labs in self.labs_per_classe.items():
                labs_con_ordine = [(l, self.ORDINE_IDEALE_LAB.get(l, 99)) for l in labs if l != self.LAB_PRESENTAZIONE_MANUALI]
                labs_con_ordine.sort(key=lambda x: x[1])

                for i in range(len(labs_con_ordine) - 1):
                    lab_a, ord_a = labs_con_ordine[i]
                    lab_b, ord_b = labs_con_ordine[i + 1]

                    if ord_a >= ord_b or ord_a == 99 or ord_b == 99:
                        continue

                    num_a = self.num_incontri_lab.get(lab_a, 1)
                    ultimo_a = self.settimana[(classe_id, lab_a, num_a - 1)]
                    primo_b = self.settimana[(classe_id, lab_b, 0)]

                    ordine_rispettato = self.model.NewBoolVar(f"s3_{classe_id}_{lab_a}_{lab_b}")
                    self.model.Add(ultimo_a < primo_b).OnlyEnforceIf(ordine_rispettato)
                    self.model.Add(ultimo_a >= primo_b).OnlyEnforceIf(ordine_rispettato.Not())
                    objective_terms.append(self.PESO_S3_ORDINE_IDEALE * ordine_rispettato)
                    n_s3 += 1
            print(f"    S3 (ordine ideale lab): {n_s3} termini")

            if objective_terms:
                self.model.Maximize(sum(objective_terms))
                print(f"    Totale termini obiettivo: {len(objective_terms)}")

        print(f"\n  Vincoli Hard: H1b={n_h1b_extra}, H2={n_h2}, H3={n_h3}, H4={n_h4}, H7={n_h7}, GSSI={n_gssi}, H13={n_h13}, H14={n_h14}")

    def solve(self, time_limit_seconds: int = 300):
        print(f"\nSolver (timeout: {time_limit_seconds}s)...")
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.log_search_progress = self.verbose
        self.solver.parameters.num_search_workers = 12

        status = self.solver.Solve(self.model)

        status_name = self.solver.status_name(status)
        wall_time = self.solver.WallTime()
        print(f"  Status: {status_name}, Tempo: {wall_time:.2f}s")

        return status if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None

    def find_h9_overlaps(self):
        """Trova sovrapposizioni H9"""
        incontri_secondi = set()
        for (c1, c2, lab_id), acc_var in self.accorpa.items():
            if self.solver.Value(acc_var) == 1:
                for k in range(self.num_incontri_lab.get(lab_id, 1)):
                    incontri_secondi.add((c2, lab_id, k))

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
                    if s1 < e2 and s2 < e1:
                        overlaps.append((key1, key2, form_id, sett, giorno, fascia1, fascia2))

        return overlaps

    def add_h9_constraints_for_overlaps(self, overlaps):
        """Aggiunge vincoli per vietare sovrapposizioni trovate"""
        n_added = 0

        fasce_sovrapposte_set = set()
        for f1 in self.fascia_orari:
            for f2 in self.fascia_orari:
                s1, e1 = self.fascia_orari[f1]
                s2, e2 = self.fascia_orari[f2]
                if s1 < e2 and s2 < e1:
                    fasce_sovrapposte_set.add((f1, f2))

        fasce_sovrapposte_list = [[f1, f2] for (f1, f2) in fasce_sovrapposte_set]

        for key1, key2, form_id, sett, giorno, fascia1, fascia2 in overlaps:
            same_day = self.model.NewBoolVar(f"sd_h9_{n_added}")
            day_slot_1 = self.settimana[key1] * 6 + self.giorno[key1]
            day_slot_2 = self.settimana[key2] * 6 + self.giorno[key2]
            self.model.Add(day_slot_1 == day_slot_2).OnlyEnforceIf(same_day)
            self.model.Add(day_slot_1 != day_slot_2).OnlyEnforceIf(same_day.Not())

            same_form = self.model.NewBoolVar(f"sf_h9_{n_added}")
            self.model.Add(self.formatrice[key1] == self.formatrice[key2]).OnlyEnforceIf(same_form)
            self.model.Add(self.formatrice[key1] != self.formatrice[key2]).OnlyEnforceIf(same_form.Not())

            conflict = self.model.NewBoolVar(f"cf_h9_{n_added}")
            self.model.AddBoolAnd([same_day, same_form]).OnlyEnforceIf(conflict)
            self.model.AddBoolOr([same_day.Not(), same_form.Not()]).OnlyEnforceIf(conflict.Not())

            self.model.AddForbiddenAssignments(
                [self.fascia[key1], self.fascia[key2]],
                fasce_sovrapposte_list
            ).OnlyEnforceIf(conflict)

            n_added += 1

        return n_added

    def _precompute_potentially_overlapping_pairs(self) -> List[Tuple]:
        """
        Pre-filtra coppie di incontri che possono potenzialmente sovrapporsi.

        Due incontri possono sovrapporsi solo se:
        1. I loro domini (settimana, giorno) hanno intersezione non vuota
        2. Le fasce orarie si sovrappongono temporalmente
        3. Non sono lo stesso incontro
        4. Il secondo incontro non è già accorpato (sarà gestito separatamente)

        Returns:
            Lista di tuple (key1, key2) potenzialmente sovrapposti
        """
        # Identifica incontri "secondi" da escludere
        incontri_secondi = set()
        for (c1, c2, lab_id), acc_var in self.accorpa.items():
            for k in range(self.num_incontri_lab.get(lab_id, 1)):
                incontri_secondi.add((c2, lab_id, k))

        # Incontri primari (esclusi i secondi)
        incontri_primari = [key for key in self.tutti_incontri if key not in incontri_secondi]

        # Pre-calcola quali fasce si sovrappongono
        fasce_overlap = {}
        for f1 in [1, 2, 3]:
            for f2 in [1, 2, 3]:
                s1, e1 = self.fascia_orari.get(f1, (480, 720))
                s2, e2 = self.fascia_orari.get(f2, (480, 720))
                # Due fasce si sovrappongono se s1 < e2 AND s2 < e1
                fasce_overlap[(f1, f2)] = (s1 < e2 and s2 < e1)

        # Raggruppa incontri per (settimana, giorno) possibili
        incontri_per_day_slot = defaultdict(lambda: defaultdict(list))

        for key in incontri_primari:
            classe_id, lab_id, k = key
            domain = self.preprocessor.get_domain_for_meeting(classe_id, lab_id, k)

            # Per ogni slot valido nel dominio
            for (week, day, fascia) in domain.get_valid_slots():
                incontri_per_day_slot[(week, day)][fascia].append(key)

        # Trova coppie che condividono almeno un (week, day) con fasce sovrapposte
        pairs = set()

        for (week, day), fasce_dict in incontri_per_day_slot.items():
            # Controlla tutte le coppie di fasce che si sovrappongono
            for f1, keys1 in fasce_dict.items():
                for f2, keys2 in fasce_dict.items():
                    if not fasce_overlap.get((f1, f2), False):
                        continue

                    # Tutte le coppie di incontri in queste fasce possono sovrapporsi
                    for key1 in keys1:
                        for key2 in keys2:
                            if key1 < key2:  # Evita duplicati e stesso incontro
                                pairs.add((key1, key2))

        return list(pairs)

    def _add_h9_constraints_prefiltered(self, overlapping_pairs: List[Tuple],
                                       tutte_formatrici: List[int]) -> int:
        """
        Aggiunge vincoli H9 solo per le coppie pre-filtrate.

        Per ogni coppia potenzialmente sovrapposta, aggiungi vincolo:
        Se stessa formatrice E stesso giorno => fasce non sovrapposte

        Args:
            overlapping_pairs: Lista di (key1, key2) potenzialmente sovrapposti
            tutte_formatrici: Lista di ID formatrici

        Returns:
            Numero di vincoli aggiunti
        """
        if not overlapping_pairs:
            return 0

        # Pre-calcola coppie di fasce che si sovrappongono
        fasce_sovrapposte_set = set()
        for f1 in self.fascia_orari:
            for f2 in self.fascia_orari:
                s1, e1 = self.fascia_orari[f1]
                s2, e2 = self.fascia_orari[f2]
                if s1 < e2 and s2 < e1:
                    fasce_sovrapposte_set.add((f1, f2))

        fasce_sovrapposte_list = [[f1, f2] for (f1, f2) in fasce_sovrapposte_set]

        n_added = 0

        for key1, key2 in overlapping_pairs:
            # Variabile: stesso giorno (settimana + giorno)?
            same_day = self.model.NewBoolVar(f"sd_h9_{n_added}")
            day_slot_1 = self.settimana[key1] * 6 + self.giorno[key1]
            day_slot_2 = self.settimana[key2] * 6 + self.giorno[key2]
            self.model.Add(day_slot_1 == day_slot_2).OnlyEnforceIf(same_day)
            self.model.Add(day_slot_1 != day_slot_2).OnlyEnforceIf(same_day.Not())

            # Variabile: stessa formatrice?
            same_form = self.model.NewBoolVar(f"sf_h9_{n_added}")
            self.model.Add(self.formatrice[key1] == self.formatrice[key2]).OnlyEnforceIf(same_form)
            self.model.Add(self.formatrice[key1] != self.formatrice[key2]).OnlyEnforceIf(same_form.Not())

            # Se entrambe vere => conflitto
            conflict = self.model.NewBoolVar(f"cf_h9_{n_added}")
            self.model.AddBoolAnd([same_day, same_form]).OnlyEnforceIf(conflict)
            self.model.AddBoolOr([same_day.Not(), same_form.Not()]).OnlyEnforceIf(conflict.Not())

            # In caso di conflitto, vieta fasce sovrapposte
            self.model.AddForbiddenAssignments(
                [self.fascia[key1], self.fascia[key2]],
                fasce_sovrapposte_list
            ).OnlyEnforceIf(conflict)

            n_added += 1

        return n_added

    def verify_constraints(self):
        """Verifica vincoli sulla soluzione"""
        print("\n" + "=" * 60)
        print("VERIFICA VINCOLI")
        print("=" * 60)

        errors = []

        # Identifica accorpamenti attivi
        accorpamenti_attivi = set()
        for (c1, c2, lab_id), acc_var in self.accorpa.items():
            if self.solver.Value(acc_var) == 1:
                accorpamenti_attivi.add((c1, c2, lab_id))

        incontri_secondi = set()
        for (c1, c2, lab_id) in accorpamenti_attivi:
            for k in range(self.num_incontri_lab.get(lab_id, 1)):
                incontri_secondi.add((c2, lab_id, k))

        # H2: Max 1 incontro/settimana
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
        print(f"  {'OK' if h2_violations == 0 else 'ERRORE'}: {h2_violations} violazioni")

        # H9: Sovrapposizioni
        print("\n[H9] No sovrapposizioni formatrice")
        overlaps = self.find_h9_overlaps()
        print(f"  {'OK' if len(overlaps) == 0 else 'ERRORE'}: {len(overlaps)} sovrapposizioni")

        # Accorpamenti
        print(f"\n[ACCORPAMENTI] Attivi: {len(accorpamenti_attivi)}")

        # Budget
        print("\n[BUDGET] Ore formatrici")
        for _, form in self.data.formatrici.iterrows():
            f_id = int(form['formatrice_id'])
            ore_max = self.ORE_GENERALI.get(f_id, 100)
            ore_effettive = 0
            for key in self.tutti_incontri:
                if self.solver.Value(self.formatrice[key]) == f_id:
                    if key not in incontri_secondi:
                        ore_effettive += self.ore_per_lab.get(key[1], 2)
            status = "OK" if ore_effettive <= ore_max else "SUPERATO"
            print(f"  {form['nome']}: {ore_effettive}h / {ore_max}h [{status}]")

        print("=" * 60)
        return len(errors) == 0

    def _map_fascia_generica_a_specifica(self, fascia_generica_num, scuola_id):
        if fascia_generica_num == 3:
            return '14-16'
        fasce_scuola = self.data.fasce_orarie_scuole[
            self.data.fasce_orarie_scuole['scuola_id'] == scuola_id
        ].sort_values('fascia_id')
        if fascia_generica_num == 1 and len(fasce_scuola) >= 1:
            return fasce_scuola.iloc[0]['nome']
        elif fascia_generica_num == 2 and len(fasce_scuola) >= 2:
            return fasce_scuola.iloc[1]['nome']
        else:
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
            fascia_specifica = self._map_fascia_generica_a_specifica(fascia, classe_row['scuola_id'])

            risultati.append({
                'settimana': sett + 1,
                'giorno': giorni_nome[giorno],
                'data': data_incontro.strftime('%d/%m/%Y'),
                'fascia': fascia_specifica,
                '_fascia_id': fascia,
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
    parser = argparse.ArgumentParser(description='Optimizer V6 - Con domini pre-calcolati e pre-filtering H9')
    parser.add_argument('--verbose', '-v', action='store_true', help='Log dettagliato solver')
    parser.add_argument('--timeout', '-t', type=int, default=300, help='Timeout solver (default: 300s)')
    parser.add_argument('--output', '-o', type=str, default='data/output/calendario_V6.csv', help='File output')
    parser.add_argument('--no-soft', action='store_true', help='Disabilita vincoli soft')
    args = parser.parse_args()

    enable_soft = not args.no_soft

    # 1. Pre-processing
    print("=" * 60)
    print("  FASE 1: PRE-PROCESSING DOMINI")
    print("=" * 60)

    preprocessor = DomainPreprocessor()
    preprocessor.load_data()
    preprocessor.compute_class_domains()
    preprocessor.compute_grouping_pairs()

    # 2. Carica dati
    data = DataLoader("data/input").load_all()

    # 3. Costruisci modello (con H9 pre-filtrato)
    optimizer = OptimizerV6(data, preprocessor, verbose=args.verbose, enable_soft=enable_soft)
    optimizer.build_model()

    # 4. Risolvi una volta (H9 già nel modello)
    print(f"\n{'='*60}")
    print(f"  RISOLUZIONE MODELLO")
    print(f"{'='*60}")

    if not optimizer.solve(time_limit_seconds=args.timeout):
        print("\nNessuna soluzione trovata.")
        sys.exit(1)

    print(f"\n  Soluzione trovata!")

    # 5. Verifica e esporta
    optimizer.verify_constraints()
    optimizer.export_results(args.output)
    print("\nCompletato!")


if __name__ == "__main__":
    main()
