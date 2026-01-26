"""
Date Parser - Modulo per parsing date in formato italiano

Gestisce:
- Conversione settimana/giorno ↔ data
- Parsing date escluse (es. "2-6 marzo", "15 gennaio pomeriggio")
- Parsing date fissate (es. "26 febbraio 9-13")
"""

import re
import pandas as pd
from datetime import datetime, date, timedelta


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

    GIORNI_SETTIMANA_INT = {
        0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6  # lun=0, ..., sab=5, dom=6
    }

    # Fasce generiche (semplificazione)
    # Mapping tipo_giornata -> fasce generiche (numeri)
    fasce_per_tipo = {
        'mattina': {1, 2},      # mattino1, mattino2
        'pomeriggio': {3}       # pomeriggio
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

            if fascia_id in cls.fasce_info:
                continue

            tipo = row['tipo_giornata'].lower().strip()
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

        Con fasce generiche (1=mattino1, 2=mattino2, 3=pomeriggio):
        - Se range include ore mattutine (< 14:00): includi 1, 2
        - Se range include ore pomeridiane (>= 14:00): includi 3
        """
        fasce_valide = set()

        # Logica semplificata per fasce generiche
        if ora_inizio < 14.0:  # Range include mattina
            fasce_valide.add(1)  # mattino1
            fasce_valide.add(2)  # mattino2
        if ora_fine > 14.0:  # Range include pomeriggio
            fasce_valide.add(3)  # pomeriggio

        return fasce_valide

    @classmethod
    def get_fasce_per_tipo(cls, tipo: str) -> set:
        """Ritorna set di fasce generiche (numeri) per tipo_giornata"""
        return cls.fasce_per_tipo.get(tipo.lower(), set())

    @classmethod
    def data_to_settimana_giorno(cls, data: datetime) -> tuple:
        """Converte data in (settimana, giorno_int) nel nostro schema

        Returns: (settimana, giorno) dove giorno è int 0-5 (lun-sab)
        """
        if data < cls.DATA_INIZIO or data > cls.DATA_FINE:
            return None, None

        # Durante Pasqua
        if data >= cls.PASQUA_INIZIO and data <= cls.PASQUA_FINE:
            return None, None

        delta = (data - cls.DATA_INIZIO).days

        # Se dopo Pasqua, sottrai i giorni del gap
        if data > cls.PASQUA_FINE:
            giorni_pasqua = (cls.PASQUA_FINE - cls.PASQUA_INIZIO).days + 1
            delta -= giorni_pasqua

        settimana = delta // 7
        giorno_int = data.weekday()  # 0=lun, ..., 5=sab

        return settimana, giorno_int

    @classmethod
    def settimana_giorno_to_data(cls, settimana: int, giorno: int) -> date:
        """Converte (settimana 0-14, giorno 0-4/5) in data reale"""
        if settimana <= 9:
            # Prima del gap di Pasqua
            offset = settimana * 7 + giorno
            return cls.DATA_INIZIO.date() + timedelta(days=offset)
        else:
            # Dopo il gap di Pasqua (settimana 10+ inizia il 13/4/2026)
            data_post_pasqua = date(2026, 4, 13)
            offset_post = (settimana - 10) * 7 + giorno
            return data_post_pasqua + timedelta(days=offset_post)

    @classmethod
    def parse_data_singola(cls, text: str, anno: int = 2026) -> datetime:
        """Parsa '15 gennaio' o '5 febbraio' → datetime"""
        text = text.strip().lower()
        text = re.sub(r'\s+(pomeriggio|mattina|sera).*', '', text)
        text = re.sub(r'\s+\d+-\d+', '', text)

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
        """Parsa '2-6 marzo' o '8-23 gennaio' → lista di (datetime, ha_pom, ha_mat)"""
        text = text.strip().lower()
        ha_pomeriggio = 'pomeriggio' in text
        ha_mattina = 'mattina' in text
        text = re.sub(r'\s+(pomeriggio|mattina|sera).*', '', text)

        match = re.match(r'(\d+)-(\d+)\s+(\w+)', text)
        if match:
            giorno_inizio = int(match.group(1))
            giorno_fine = int(match.group(2))
            mese_nome = match.group(3)
            mese = cls.MESI.get(mese_nome)
            if mese:
                date_list = []
                for g in range(giorno_inizio, giorno_fine + 1):
                    try:
                        d = datetime(anno, mese, g)
                        date_list.append((d, ha_pomeriggio, ha_mattina))
                    except ValueError:
                        pass
                return date_list
        return []

    @classmethod
    def parse_date_escluse(cls, text: str) -> list:
        """Parsa stringa date escluse → lista di (settimana, giorno_int, fasce_escluse)

        fasce_escluse è un set di fascia_id da escludere, o None per tutte
        """
        if pd.isna(text):
            return []

        risultati = []
        parti = str(text).split(',')

        for parte in parti:
            parte = parte.strip()
            if not parte:
                continue

            ha_pomeriggio = 'pomeriggio' in parte.lower()
            ha_mattina = 'mattina' in parte.lower()

            fasce_escluse = None
            if ha_pomeriggio and not ha_mattina:
                fasce_escluse = cls.get_fasce_per_tipo('pomeriggio')
            elif ha_mattina and not ha_pomeriggio:
                fasce_escluse = cls.get_fasce_per_tipo('mattina')

            date_range = cls.parse_range_date(parte)
            if date_range:
                for data, pom, mat in date_range:
                    sett, giorno = cls.data_to_settimana_giorno(data)
                    if sett is not None:
                        fe = fasce_escluse
                        if fe is None and pom:
                            fe = cls.get_fasce_per_tipo('pomeriggio')
                        elif fe is None and mat:
                            fe = cls.get_fasce_per_tipo('mattina')
                        risultati.append((sett, giorno, fe))
            else:
                data = cls.parse_data_singola(parte)
                if data:
                    sett, giorno = cls.data_to_settimana_giorno(data)
                    if sett is not None:
                        risultati.append((sett, giorno, fasce_escluse))

        return risultati

    @classmethod
    def parse_date_fissate(cls, text: str) -> list:
        """Parsa stringa date fissate → lista di (settimana, giorno_int, fasce_valide)

        fasce_valide è un set di fascia_id validi, o None per tutte
        """
        if pd.isna(text):
            return []

        risultati = []
        parti = re.split(r'[,.]', str(text))

        for parte in parti:
            parte = parte.strip()
            if not parte:
                continue

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
                            fasce_valide = None
                            if ora_inizio_str and ora_fine_str:
                                ora_inizio = float(ora_inizio_str)
                                ora_fine = float(ora_fine_str)
                                fasce_valide = cls.get_fasce_in_range(ora_inizio, ora_fine)
                            risultati.append((sett, giorno_sett, fasce_valide))
                    except ValueError:
                        pass

        return risultati

    @classmethod
    def parse_date_disponibili(cls, text: str) -> list:
        """Parsa stringa date_disponibili (formato Margherita) → lista di (settimana, giorno, fasce_valide)

        Formato input: "13 Gennaio 10.00-14.00; 15 Gennaio 10.00-14.00; ..."
        """
        if pd.isna(text) or not text:
            return []

        risultati = []
        # Split per ";" separatore tra date
        parti = str(text).split(';')

        for parte in parti:
            parte = parte.strip()
            if not parte:
                continue

            # Match: "13 Gennaio 10.00-14.00" o "13 Gennaio 08.00-10.00"
            match = re.match(r'(\d+)\s+(\w+)\s+(\d+)[\.:]+(\d+)-(\d+)[\.:]+(\d+)', parte)
            if match:
                giorno_mese = int(match.group(1))
                mese_nome = match.group(2).lower()
                ora_inizio_h = int(match.group(3))
                ora_inizio_m = int(match.group(4))
                ora_fine_h = int(match.group(5))
                ora_fine_m = int(match.group(6))

                mese = cls.MESI.get(mese_nome)
                if mese:
                    try:
                        data = datetime(2026, mese, giorno_mese)
                        sett, giorno_sett = cls.data_to_settimana_giorno(data)
                        if sett is not None:
                            ora_inizio = ora_inizio_h + ora_inizio_m / 60
                            ora_fine = ora_fine_h + ora_fine_m / 60
                            fasce_valide = cls.get_fasce_in_range(ora_inizio, ora_fine)
                            if fasce_valide:
                                risultati.append((sett, giorno_sett, fasce_valide))
                    except ValueError:
                        pass

        return risultati
