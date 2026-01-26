#!/usr/bin/env python3
"""
Optimizer V3 - Aggiunge Date Escluse e Fissate

Vincoli da V2:
- H1: Ogni classe completa ogni lab
- H1b: Accorpamenti (max 2 classi stessa scuola)
- H2: Max 1 incontro/settimana per classe
- H5-H7: Giorni e sabato
- H9: No sovrapposizioni formatrice
- H10: Fasce generiche globali (mattino1, mattino2, pomeriggio)
- H11: Fasce disponibili per classe
- H15: Budget ore formatrice (upper bound only)

Vincoli nuovi V3:
- H12: Date escluse per classe (da date_escluse_classi.csv)
- H13: Date fissate (da laboratori_classi.csv colonna date_fissate)
"""

import pandas as pd
from ortools.sat.python import cp_model
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
import sys
import re


class DataLoaderV3:
    """Carica dati incluse date escluse"""

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
        self.date_escluse_classi = pd.read_csv(self.input_dir / "date_escluse_classi.csv")

        print(f"  {len(self.scuole)} scuole")
        print(f"  {len(self.classi)} classi")
        print(f"  {len(self.laboratori)} laboratori")
        print(f"  {len(self.formatrici)} formatrici")
        print(f"  {len(self.date_escluse_classi)} classi con date escluse")
        print()

        return self


class DateParser:
    """Parser per date nel formato italiano"""

    # Periodo: 28/1/2026 - 16/5/2026 con gap Pasqua 2-12/4/2026
    DATA_INIZIO = datetime(2026, 1, 28)
    DATA_FINE = datetime(2026, 5, 16)
    PASQUA_INIZIO = datetime(2026, 4, 2)
    PASQUA_FINE = datetime(2026, 4, 12)

    MESI = {
        'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
        'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
        'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
    }

    GIORNI_SETTIMANA = {
        0: 'lun', 1: 'mar', 2: 'mer', 3: 'gio', 4: 'ven', 5: 'sab', 6: 'dom'
    }

    # Fasce generiche (semplificazione)
    FASCE_GENERICHE = {'mattino1', 'mattino2', 'pomeriggio'}

    # Mapping tipo_giornata -> fasce generiche
    fasce_per_tipo = {
        'mattina': {'mattino1', 'mattino2'},
        'pomeriggio': {'pomeriggio'}
    }

    # Info fasce per mapping in export (ora_inizio, ora_fine, tipo)
    fasce_info = {}  # Popolato da load_fasce_info per output

    @classmethod
    def load_fasce_info(cls, fasce_orarie_scuole_df):
        """Carica info fasce da fasce_orarie_scuole.csv per mapping in export

        Con le fasce generiche, questo serve solo per mappare fascia generica
        -> fascia specifica nell'output. Le fasce_per_tipo sono hardcoded.
        """
        cls.fasce_info = {}

        for _, row in fasce_orarie_scuole_df.iterrows():
            fascia_id = int(row['fascia_id'])

            # Già processata questa fascia? Skip
            if fascia_id in cls.fasce_info:
                continue

            tipo = row['tipo_giornata'].lower().strip()

            # Parse orari
            ora_inizio = cls._parse_ora(row['ora_inizio'])
            ora_fine = cls._parse_ora(row['ora_fine'])

            cls.fasce_info[fascia_id] = (ora_inizio, ora_fine, tipo)

    @classmethod
    def _parse_ora(cls, ora_str) -> float:
        """Converte '09:00' o '9:00' in ore decimali (9.0)"""
        if pd.isna(ora_str):
            return 0
        ora_str = str(ora_str).strip()
        match = re.match(r'(\d+)[:\.]?(\d*)', ora_str)
        if match:
            ore = int(match.group(1))
            minuti = int(match.group(2)) if match.group(2) else 0
            return ore + minuti / 60
        return 0

    @classmethod
    def get_fasce_in_range(cls, ora_inizio: float, ora_fine: float) -> set:
        """Trova fasce generiche compatibili con range orario [ora_inizio, ora_fine]

        Con fasce generiche:
        - Se range include ore mattutine (< 14:00): includi mattino1, mattino2
        - Se range include ore pomeridiane (>= 14:00): includi pomeriggio
        """
        fasce_valide = set()

        # Logica semplificata per fasce generiche
        if ora_inizio < 14.0:  # Range include mattina
            fasce_valide.add('mattino1')
            fasce_valide.add('mattino2')
        if ora_fine > 14.0:  # Range include pomeriggio
            fasce_valide.add('pomeriggio')

        return fasce_valide

    @classmethod
    def get_fasce_per_tipo(cls, tipo: str) -> set:
        """Ritorna set di fasce generiche per tipo_giornata (mattina/pomeriggio)"""
        return cls.fasce_per_tipo.get(tipo.lower(), set())

    @classmethod
    def data_to_settimana_giorno(cls, data: datetime) -> tuple:
        """Converte data in (settimana, giorno) nel nostro schema"""
        if data < cls.DATA_INIZIO or data > cls.DATA_FINE:
            return None, None

        # Calcola giorni dall'inizio
        delta = (data - cls.DATA_INIZIO).days

        # Gestisci gap Pasqua
        if data >= cls.PASQUA_INIZIO and data <= cls.PASQUA_FINE:
            return None, None  # Durante Pasqua

        # Se dopo Pasqua, sottrai i giorni del gap
        if data > cls.PASQUA_FINE:
            giorni_pasqua = (cls.PASQUA_FINE - cls.PASQUA_INIZIO).days + 1
            delta -= giorni_pasqua

        settimana = delta // 7
        giorno = cls.GIORNI_SETTIMANA[data.weekday()]

        return settimana, giorno

    @classmethod
    def parse_data_singola(cls, text: str, anno: int = 2026) -> datetime:
        """Parsa '15 gennaio' o '5 febbraio' → datetime"""
        text = text.strip().lower()
        # Rimuovi parti come 'pomeriggio', 'mattina', orari
        text = re.sub(r'\s+(pomeriggio|mattina|sera).*', '', text)
        text = re.sub(r'\s+\d+-\d+', '', text)  # Rimuovi orari tipo 9-13

        match = re.match(r'(\d+)\s+(\w+)', text)
        if match:
            giorno = int(match.group(1))
            mese_nome = match.group(2)
            mese = cls.MESI.get(mese_nome)
            if mese:
                try:
                    return datetime(anno, mese, giorno)
                except ValueError:
                    pass
        return None

    @classmethod
    def parse_range_date(cls, text: str, anno: int = 2026) -> list:
        """Parsa '2-6 marzo' o '8-23 gennaio' → lista di datetime"""
        text = text.strip().lower()
        # Rimuovi parti come 'pomeriggio', 'mattina'
        ha_pomeriggio = 'pomeriggio' in text
        ha_mattina = 'mattina' in text
        text = re.sub(r'\s+(pomeriggio|mattina|sera).*', '', text)

        # Pattern: "N-M mese"
        match = re.match(r'(\d+)-(\d+)\s+(\w+)', text)
        if match:
            giorno_inizio = int(match.group(1))
            giorno_fine = int(match.group(2))
            mese_nome = match.group(3)
            mese = cls.MESI.get(mese_nome)
            if mese:
                date = []
                for g in range(giorno_inizio, giorno_fine + 1):
                    try:
                        d = datetime(anno, mese, g)
                        date.append((d, ha_pomeriggio, ha_mattina))
                    except ValueError:
                        pass
                return date
        return []

    @classmethod
    def parse_date_escluse(cls, text: str) -> list:
        """Parsa stringa date escluse → lista di (settimana, giorno, fasce_escluse)

        fasce_escluse è un set di fascia_id da escludere, o None per tutte
        """
        if pd.isna(text):
            return []

        risultati = []
        # Split per virgola
        parti = str(text).split(',')

        for parte in parti:
            parte = parte.strip()
            if not parte:
                continue

            ha_pomeriggio = 'pomeriggio' in parte.lower()
            ha_mattina = 'mattina' in parte.lower()

            # Determina fasce da escludere basandosi su tipo_giornata
            fasce_escluse = None  # None = tutte
            if ha_pomeriggio and not ha_mattina:
                fasce_escluse = cls.get_fasce_per_tipo('pomeriggio')
            elif ha_mattina and not ha_pomeriggio:
                fasce_escluse = cls.get_fasce_per_tipo('mattina')
            elif ha_mattina and ha_pomeriggio:
                # "mattina e pomeriggio" = tutte
                fasce_escluse = None

            # Prova range
            date_range = cls.parse_range_date(parte)
            if date_range:
                for data, pom, mat in date_range:
                    sett, giorno = cls.data_to_settimana_giorno(data)
                    if sett is not None:
                        # Se il range aveva pomeriggio/mattina, usa quello
                        fe = fasce_escluse
                        if fe is None and pom:
                            fe = cls.get_fasce_per_tipo('pomeriggio')
                        elif fe is None and mat:
                            fe = cls.get_fasce_per_tipo('mattina')
                        risultati.append((sett, giorno, fe))
            else:
                # Prova data singola
                data = cls.parse_data_singola(parte)
                if data:
                    sett, giorno = cls.data_to_settimana_giorno(data)
                    if sett is not None:
                        risultati.append((sett, giorno, fasce_escluse))

        return risultati

    @classmethod
    def parse_date_fissate(cls, text: str) -> list:
        """Parsa stringa date fissate → lista di (settimana, giorno, fasce_valide)

        fasce_valide è un set di fascia_id validi per quell'incontro, o None per tutte
        """
        if pd.isna(text):
            return []

        risultati = []
        # Split per virgola o punto
        parti = re.split(r'[,.]', str(text))

        for parte in parti:
            parte = parte.strip()
            if not parte:
                continue

            # Pattern: "26 febbraio 9-13" o "4 maggio" o "26 febbraio 14-18"
            match = re.match(r'(\d+)\s+(\w+)(?:\s+(\d+)-(\d+))?', parte)
            if match:
                giorno = int(match.group(1))
                mese_nome = match.group(2).lower()
                ora_inizio_str = match.group(3)
                ora_fine_str = match.group(4)

                mese = cls.MESI.get(mese_nome)
                if mese:
                    try:
                        data = datetime(2026, mese, giorno)
                        sett, giorno_sett = cls.data_to_settimana_giorno(data)
                        if sett is not None:
                            # Determina fasce valide dal range orario
                            fasce_valide = None  # None = tutte
                            if ora_inizio_str and ora_fine_str:
                                ora_inizio = float(ora_inizio_str)
                                ora_fine = float(ora_fine_str)
                                fasce_valide = cls.get_fasce_in_range(ora_inizio, ora_fine)
                            risultati.append((sett, giorno_sett, fasce_valide))
                    except ValueError:
                        pass

        return risultati


class OptimizerV3:
    """Optimizer con date escluse e fissate"""

    NUM_SETTIMANE = 15
    GIORNI_FERIALI = ['lun', 'mar', 'mer', 'gio', 'ven']
    SABATO = 'sab'

    # Fasce orarie generiche (semplificazione)
    FASCE = ['mattino1', 'mattino2', 'pomeriggio']

    def __init__(self, data: DataLoaderV3):
        self.data = data
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        self.solo = {}
        self.insieme = {}

        # Indici per accesso veloce
        self.vars_by_formatrice_slot = defaultdict(list)
        self.vars_by_classe_lab = defaultdict(list)
        self.vars_by_classe_settimana = defaultdict(list)

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
        print("Costruzione modello V3 con date escluse/fissate...")

        # ===================
        # PREPROCESSING DATI
        # ===================

        # Carica info fasce per il parser
        DateParser.load_fasce_info(self.data.fasce_orarie_scuole)
        print(f"  Fasce mattina: {sorted(DateParser.fasce_per_tipo.get('mattina', set()))}")
        print(f"  Fasce pomeriggio: {sorted(DateParser.fasce_per_tipo.get('pomeriggio', set()))}")

        lab_ids_validi = set(self.data.laboratori['laboratorio_id'].values)

        labs_per_classe = defaultdict(list)
        for _, row in self.data.laboratori_classi.iterrows():
            if row['laboratorio_id'] in lab_ids_validi:
                labs_per_classe[row['classe_id']].append(row['laboratorio_id'])

        scuola_per_classe = {}
        for _, row in self.data.classi.iterrows():
            scuola_per_classe[row['classe_id']] = row['scuola_id']

        # H10: Fasce generiche globali (tutte le scuole accettano tutte le fasce)
        print(f"  H10: Fasce generiche globali: {self.FASCE}")

        # H11: Fasce disponibili per classe
        fasce_per_classe = {}
        for _, row in self.data.fasce_orarie_classi.iterrows():
            fasce_classe = self._parse_fasce_disponibili(row['fasce_disponibili'])
            fasce_per_classe[row['classe_id']] = fasce_classe
        print(f"  H11: Fasce per classe caricate ({len(fasce_per_classe)} classi)")

        # H5/H6: Scuole con sabato
        scuole_con_sabato = set()
        for _, row in self.data.scuole.iterrows():
            if str(row['sabato_disponibile']).lower() in ['si', 'sì', 'yes', '1', 'true']:
                scuole_con_sabato.add(row['scuola_id'])

        # H7: Formatrici con sabato
        formatrici_con_sabato = set()
        for _, row in self.data.formatrici.iterrows():
            if str(row['lavora_sabato']).lower() in ['si', 'sì', 'yes', '1', 'true']:
                formatrici_con_sabato.add(int(row['formatrice_id']))

        # ----------------------------------------------
        # H12: Date escluse per classe
        # Fonte: date_escluse_classi.csv
        # ----------------------------------------------
        date_escluse = defaultdict(list)  # classe_id -> [(settimana, giorno, fascia_tipo)]
        for _, row in self.data.date_escluse_classi.iterrows():
            classe_id = row['classe_id']
            parsed = DateParser.parse_date_escluse(row['date_escluse'])
            date_escluse[classe_id].extend(parsed)
        print(f"  H12: {len(date_escluse)} classi con date escluse")

        # ----------------------------------------------
        # H13: Date fissate per (classe, lab)
        # Fonte: laboratori_classi.csv colonna date_fissate
        # ----------------------------------------------
        date_fissate = defaultdict(list)  # (classe_id, lab_id) -> [(settimana, giorno, fascia)]
        for _, row in self.data.laboratori_classi.iterrows():
            if pd.notna(row.get('date_fissate')):
                classe_id = row['classe_id']
                lab_id = row['laboratorio_id']
                if lab_id in lab_ids_validi:
                    parsed = DateParser.parse_date_fissate(row['date_fissate'])
                    date_fissate[(classe_id, lab_id)].extend(parsed)
        print(f"  H13: {len(date_fissate)} combinazioni (classe,lab) con date fissate")

        # Coppie accorpamento
        coppie_accorpamento = set()
        classi_per_scuola = defaultdict(list)
        for _, row in self.data.classi.iterrows():
            classi_per_scuola[row['scuola_id']].append(row['classe_id'])

        for scuola_id, classi_scuola in classi_per_scuola.items():
            for i, c1 in enumerate(classi_scuola):
                for c2 in classi_scuola[i+1:]:
                    coppie_accorpamento.add((c1, c2))

        tutte_formatrici = list(self.data.formatrici['formatrice_id'].astype(int))

        ore_per_lab = {}
        num_incontri_lab = {}
        for _, lab in self.data.laboratori.iterrows():
            ore_per_lab[lab['laboratorio_id']] = int(lab['ore_per_incontro'])
            num_incontri_lab[lab['laboratorio_id']] = int(lab['num_incontri'])

        # ===================
        # CREA VARIABILI (filtrate per H5-H12)
        # ===================
        print("  Creazione variabili (filtrate per vincoli H5-H12)...")
        n_solo = 0
        n_insieme = 0
        n_escluse_h12 = 0

        for classe_id in labs_per_classe.keys():
            scuola_id = scuola_per_classe.get(classe_id)
            fasce_valide = fasce_per_classe.get(classe_id, set(self.FASCE))
            escluse_classe = date_escluse.get(classe_id, [])

            giorni_validi = list(self.GIORNI_FERIALI)
            if scuola_id in scuole_con_sabato:
                giorni_validi.append(self.SABATO)

            for lab_id in labs_per_classe[classe_id]:
                for formatrice_id in tutte_formatrici:
                    giorni_formatrice = list(self.GIORNI_FERIALI)
                    if formatrice_id in formatrici_con_sabato and scuola_id in scuole_con_sabato:
                        giorni_formatrice.append(self.SABATO)

                    giorni_effettivi = [g for g in giorni_validi if g in giorni_formatrice]

                    for settimana in range(self.NUM_SETTIMANE):
                        for giorno in giorni_effettivi:
                            for fascia in fasce_valide:
                                # H12: Verifica date escluse
                                esclusa = False
                                for sett_excl, giorno_excl, fasce_escluse in escluse_classe:
                                    if sett_excl == settimana and giorno_excl == giorno:
                                        if fasce_escluse is None:
                                            # Tutte le fasce escluse
                                            esclusa = True
                                            break
                                        elif fascia in fasce_escluse:
                                            # Questa fascia specifica è esclusa
                                            esclusa = True
                                            break

                                if esclusa:
                                    n_escluse_h12 += 1
                                    continue

                                key = (classe_id, lab_id, formatrice_id, settimana, giorno, fascia)
                                var_name = f"solo_c{classe_id}_l{lab_id}_f{formatrice_id}_w{settimana}_d{giorno}_fa{fascia}"
                                var = self.model.NewBoolVar(var_name)
                                self.solo[key] = var
                                n_solo += 1
                                self.vars_by_formatrice_slot[(formatrice_id, settimana, giorno, fascia)].append(var)
                                self.vars_by_classe_lab[(classe_id, lab_id)].append(var)
                                self.vars_by_classe_settimana[(classe_id, settimana)].append(var)

        # Variabili 'insieme'
        for c1, c2 in coppie_accorpamento:
            labs_c1 = set(labs_per_classe[c1])
            labs_c2 = set(labs_per_classe[c2])
            labs_comuni = labs_c1 & labs_c2

            scuola_id = scuola_per_classe.get(c1)

            fasce_c1 = fasce_per_classe.get(c1, set(self.FASCE))
            fasce_c2 = fasce_per_classe.get(c2, set(self.FASCE))
            fasce_comuni = fasce_c1 & fasce_c2

            if not fasce_comuni:
                continue

            escluse_c1 = date_escluse.get(c1, [])
            escluse_c2 = date_escluse.get(c2, [])

            giorni_validi = list(self.GIORNI_FERIALI)
            if scuola_id in scuole_con_sabato:
                giorni_validi.append(self.SABATO)

            for lab_id in labs_comuni:
                for formatrice_id in tutte_formatrici:
                    giorni_formatrice = list(self.GIORNI_FERIALI)
                    if formatrice_id in formatrici_con_sabato and scuola_id in scuole_con_sabato:
                        giorni_formatrice.append(self.SABATO)

                    giorni_effettivi = [g for g in giorni_validi if g in giorni_formatrice]

                    for settimana in range(self.NUM_SETTIMANE):
                        for giorno in giorni_effettivi:
                            for fascia in fasce_comuni:
                                # H12: Verifica date escluse per entrambe le classi
                                esclusa = False
                                for escluse in [escluse_c1, escluse_c2]:
                                    for sett_excl, giorno_excl, fasce_escluse in escluse:
                                        if sett_excl == settimana and giorno_excl == giorno:
                                            if fasce_escluse is None:
                                                # Tutte le fasce escluse
                                                esclusa = True
                                                break
                                            elif fascia in fasce_escluse:
                                                # Questa fascia specifica è esclusa
                                                esclusa = True
                                                break
                                    if esclusa:
                                        break

                                if esclusa:
                                    n_escluse_h12 += 1
                                    continue

                                key = (c1, c2, lab_id, formatrice_id, settimana, giorno, fascia)
                                var_name = f"ins_c{c1}_c{c2}_l{lab_id}_f{formatrice_id}_w{settimana}_d{giorno}_fa{fascia}"
                                var = self.model.NewBoolVar(var_name)
                                self.insieme[key] = var
                                n_insieme += 1
                                self.vars_by_formatrice_slot[(formatrice_id, settimana, giorno, fascia)].append(var)
                                self.vars_by_classe_lab[(c1, lab_id)].append(var)
                                self.vars_by_classe_lab[(c2, lab_id)].append(var)
                                self.vars_by_classe_settimana[(c1, settimana)].append(var)
                                self.vars_by_classe_settimana[(c2, settimana)].append(var)

        print(f"    Variabili 'solo': {n_solo:,}")
        print(f"    Variabili 'insieme': {n_insieme:,}")
        print(f"    Variabili escluse da H12: {n_escluse_h12:,}")
        print(f"    Totale: {n_solo + n_insieme:,}")

        # ===================
        # VINCOLI
        # ===================

        # H1: Completamento
        print("  Vincolo H1: completamento laboratori")
        n_vincoli_h1 = 0
        for classe_id, labs in labs_per_classe.items():
            for lab_id in labs:
                num_incontri = num_incontri_lab.get(lab_id, 1)
                vars_totali = self.vars_by_classe_lab.get((classe_id, lab_id), [])

                if vars_totali:
                    self.model.Add(sum(vars_totali) == num_incontri)
                    n_vincoli_h1 += 1
                else:
                    print(f"    ⚠️  Nessuna variabile per classe {classe_id}, lab {lab_id}")
        print(f"    Creati {n_vincoli_h1:,} vincoli H1")

        # H2: Max 1/settimana
        print("  Vincolo H2: max 1 incontro/settimana per classe")
        n_vincoli_h2 = 0
        for (classe_id, settimana), vars_list in self.vars_by_classe_settimana.items():
            if vars_list:
                self.model.Add(sum(vars_list) <= 1)
                n_vincoli_h2 += 1
        print(f"    Creati {n_vincoli_h2:,} vincoli H2")

        # H9: No sovrapposizioni
        print("  Vincolo H9: no sovrapposizioni formatrice")
        n_vincoli_h9 = 0
        for slot_key, vars_slot in self.vars_by_formatrice_slot.items():
            if len(vars_slot) > 1:
                self.model.Add(sum(vars_slot) <= 1)
                n_vincoli_h9 += 1
        print(f"    Creati {n_vincoli_h9:,} vincoli H9")

        # ----------------------------------------------
        # H13: Date fissate
        # Per ogni (classe, lab) con date fissate, forza le variabili
        # fasce_valide è un set di fascia_id validi dal range orario (es. "9-13")
        # ----------------------------------------------
        print("  Vincolo H13: date fissate")
        n_vincoli_h13 = 0
        for (classe_id, lab_id), date_list in date_fissate.items():
            for sett, giorno, fasce_valide in date_list:
                if sett is None:
                    continue
                # Trova variabili corrispondenti (filtrate per fasce_valide se specificato)
                vars_match = []
                for key, var in self.solo.items():
                    c, l, f, s, g, fa = key
                    if c == classe_id and l == lab_id and s == sett and g == giorno:
                        if fasce_valide is None or fa in fasce_valide:
                            vars_match.append(var)
                for key, var in self.insieme.items():
                    c1, c2, l, f, s, g, fa = key
                    if (c1 == classe_id or c2 == classe_id) and l == lab_id and s == sett and g == giorno:
                        if fasce_valide is None or fa in fasce_valide:
                            vars_match.append(var)

                if vars_match:
                    # Almeno una di queste deve essere vera
                    self.model.Add(sum(vars_match) >= 1)
                    n_vincoli_h13 += 1
                else:
                    # Nessuna variabile trovata per questa data fissata
                    classe_nome = self.data.classi[self.data.classi['classe_id'] == classe_id]['nome'].iloc[0]
                    lab_nome = self.data.laboratori[self.data.laboratori['laboratorio_id'] == lab_id]['nome'].iloc[0]
                    print(f"    ⚠️  Nessuna variabile per data fissata: {classe_nome}, {lab_nome}, sett={sett}, {giorno}, fasce={fasce_valide}")
        print(f"    Creati {n_vincoli_h13:,} vincoli H13")

        # Budget ore formatrice (H15: upper bound only, S6: soft maximize in V5)
        ORE_GENERALI = {1: 292, 2: 128, 3: 160, 4: 128}
        print("  Vincolo H15: budget ore formatrice (hard upper bound only)")

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
                self.model.Add(sum(ore_totali) <= ore_max)
                print(f"    {formatrice['nome']}: max {ore_max} ore")

        print("  Modello V3 costruito!")
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
    print("  OPTIMIZER V3 - Date Escluse e Fissate")
    print("=" * 60)
    print()

    input_dir = "data/input"
    output_file = "data/output/calendario_V3.csv"

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    try:
        data = DataLoaderV3(input_dir).load_all()
    except FileNotFoundError as e:
        print(f"Errore: {e}")
        sys.exit(1)

    optimizer = OptimizerV3(data)
    optimizer.build_model()

    status = optimizer.solve(time_limit_seconds=300)

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        optimizer.export_results(output_file)
        print("\nOttimizzazione V3 completata!")
    else:
        print("Ottimizzazione fallita.")
        sys.exit(1)


if __name__ == "__main__":
    main()
