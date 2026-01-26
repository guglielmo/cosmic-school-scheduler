#!/usr/bin/env python3
"""
Modulo per formattare l'output nel formato richiesto.
Genera 4 fogli: complessivo, per_formatore_sett_data, per_scuola_per_Classe, per_scuola_per_data
"""

import pandas as pd
from datetime import datetime, timedelta
import calendar


def get_week_number(date):
    """Calcola il numero della settimana ISO."""
    return date.isocalendar()[1]


def get_italian_weekday(date):
    """Restituisce il nome del giorno in italiano."""
    giorni = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
    return giorni[date.weekday()]


def settimana_a_data_inizio(settimana_num):
    """
    Converte numero settimana dell'optimizer in data del lunedì.
    Settimana 1 dell'optimizer = 28 gennaio 2026 (lunedì)
    """
    # Data di inizio del calendario: 28 gennaio 2026
    DATA_INIZIO = datetime(2026, 1, 26)  # Lunedì 26 gennaio 2026 (settimana 1)

    # Aggiungi settimane (settimana_num è 1-based dall'optimizer)
    target_date = DATA_INIZIO + timedelta(weeks=settimana_num - 1)
    return target_date


def giorno_a_data(settimana_num, giorno_nome):
    """Converte settimana + giorno in data."""
    giorni_map = {
        'lun': 0, 'mar': 1, 'mer': 2, 'gio': 3, 'ven': 4, 'sab': 5, 'dom': 6
    }

    lunedi = settimana_a_data_inizio(settimana_num)
    giorni_offset = giorni_map.get(giorno_nome, 0)
    return lunedi + timedelta(days=giorni_offset)


def fascia_a_orario(fascia_nome):
    """Converte nome fascia (es: '9-11' o '14.30-16.30') in orario inizio e fine."""
    if not fascia_nome or not isinstance(fascia_nome, str):
        return None, None

    # Se contiene "202" è probabilmente una data (es: "2025-10-08"), non un orario
    if '202' in fascia_nome:
        return None, None

    if '-' in fascia_nome:
        parti = fascia_nome.split('-')
        try:
            # Gestisce sia "9" che "9.30" (14.30 -> 14:30)
            ora_inizio_str = parti[0].replace('.', ':')
            ora_fine_str = parti[1].replace('.', ':')

            # Estrae solo l'ora (parte prima dei :)
            ora_inizio = int(ora_inizio_str.split(':')[0])
            ora_fine = int(ora_fine_str.split(':')[0])

            # Verifica che siano orari validi (0-24)
            if 0 <= ora_inizio <= 24 and 0 <= ora_fine <= 24:
                return ora_inizio, ora_fine
        except (ValueError, IndexError):
            pass

    return None, None


def genera_foglio_complessivo(df_calendario, scuole, classi, laboratori, formatrici, fasce_orarie_scuole):
    """
    Genera il foglio 'complessivo' con formato:
    Data | Giorno Settimana | Settimana | Mese | Scuola | Classe | Orario inizio | Orario fine |
    Attività (macro) | Attività (micro) | Partner | Nome formatore | Durata attività |
    Modalità erogazione | INCONTRO FATTO | MODULI POST ATTIVITA
    """

    risultati = []

    for _, row in df_calendario.iterrows():
        # Calcola data da settimana + giorno
        data = giorno_a_data(row['Settimana'], row['Giorno'])

        # Trova scuola
        scuola_id = classi[classi['nome'] == row['Classe']]['scuola_id'].values[0]
        scuola_nome = scuole[scuole['scuola_id'] == scuola_id]['nome'].values[0]

        # Estrai orario dal nome della fascia (es: "14-16", "9-11", "14.30-16.30")
        # Il campo ora_inizio/ora_fine nel CSV è spesso sbagliato
        ora_inizio, ora_fine = fascia_a_orario(row['Fascia'])

        # Se il parsing del nome fallisce, prova dal CSV
        if ora_inizio is None:
            fascia_row = fasce_orarie_scuole[
                (fasce_orarie_scuole['scuola_id'] == scuola_id) &
                (fasce_orarie_scuole['nome'] == row['Fascia'])
            ]
            if len(fascia_row) > 0:
                ora_inizio_str = fascia_row.iloc[0]['ora_inizio']
                ora_fine_str = fascia_row.iloc[0]['ora_fine']
                ora_inizio = float(ora_inizio_str.split(':')[0])
                ora_fine = float(ora_fine_str.split(':')[0])

        # Attività macro e micro (mappiamo da laboratorio a codice attività)
        attivita_map = {
            'Citizen Science': ('A3', 'citizen science', 'FOP'),
            'Discriminazioni di genere': ('A5', 'sensibilizzazione discriminazioni di genere', 'FOP'),
            'Orientamento e competenze': ('A6', 'orientamento e competenze', 'FOP'),
            'Presentazione manuali': ('A7', 'presentazione manuali', 'FOP')
        }

        attivita_macro, attivita_micro, partner = attivita_map.get(
            row['Laboratorio'],
            ('A1', row['Laboratorio'].lower(), 'FOP')
        )

        risultati.append({
            'Data': data,
            'Giorno Settimana': get_italian_weekday(data),
            'Settimana': get_week_number(data),
            'Mese': data.month,
            'Scuola': scuola_nome,
            'Classe': row['Classe'],
            'Orario inizio': ora_inizio,
            'Orario fine': ora_fine,
            'Attività (macro)': attivita_macro,
            'Attività (micro)': attivita_micro,
            'Partner': partner,
            'Nome formatore': row['Formatrice'],
            'Durata attivitá': row['Ore'],
            'Modalitá erogazione': 'formatore online',  # Default
            'INCONTRO FATTO': '',  # Da compilare manualmente
            'MODULI POST ATTIVITA': ''  # Da compilare manualmente
        })

    df = pd.DataFrame(risultati)
    df = df.sort_values(['Data', 'Orario inizio'])
    return df


def genera_foglio_per_formatore(df_calendario, scuole, classi, fasce_orarie_scuole):
    """
    Genera il foglio 'per_formatore_sett_data' con formato:
    Nome formatore | Settimana | Data | Giorno Settimana | Scuola | Classe |
    Attività (micro) | Orario inizio
    """

    risultati = []

    for _, row in df_calendario.iterrows():
        data = giorno_a_data(row['Settimana'], row['Giorno'])

        scuola_id = classi[classi['nome'] == row['Classe']]['scuola_id'].values[0]
        scuola_nome = scuole[scuole['scuola_id'] == scuola_id]['nome'].values[0]

        # Mappa laboratorio -> attività micro
        attivita_micro_map = {
            'Citizen Science': 'citizen science',
            'Discriminazioni di genere': 'sensibilizzazione discriminazioni di genere',
            'Orientamento e competenze': 'orientamento e competenze',
            'Presentazione manuali': 'presentazione manuali'
        }

        attivita_micro = attivita_micro_map.get(row['Laboratorio'], row['Laboratorio'].lower())

        # Estrai orario dal nome della fascia (es: "14-16")
        ora_inizio, _ = fascia_a_orario(row['Fascia'])

        # Se il parsing fallisce, prova dal CSV
        if ora_inizio is None:
            fascia_row = fasce_orarie_scuole[
                (fasce_orarie_scuole['scuola_id'] == scuola_id) &
                (fasce_orarie_scuole['nome'] == row['Fascia'])
            ]
            if len(fascia_row) > 0:
                ora_inizio_str = fascia_row.iloc[0]['ora_inizio']
                ora_inizio = float(ora_inizio_str.split(':')[0])

        risultati.append({
            'Nome formatore': row['Formatrice'],
            'Settimana': get_week_number(data),
            'Data': data,
            'Giorno Settimana': get_italian_weekday(data),
            'Scuola': scuola_nome,
            'Classe': row['Classe'],
            'Attività (micro)': attivita_micro,
            'Orario inizio': ora_inizio
        })

    df = pd.DataFrame(risultati)
    df = df.sort_values(['Nome formatore', 'Data'])

    # Aggiungi righe totale per formatrice
    df_con_totali = []
    for formatrice in df['Nome formatore'].unique():
        df_formatrice = df[df['Nome formatore'] == formatrice]
        df_con_totali.append(df_formatrice)

        # Riga totale
        df_con_totali.append(pd.DataFrame([{
            'Nome formatore': f'Totale {formatrice}',
            'Settimana': None,
            'Data': None,
            'Giorno Settimana': None,
            'Scuola': None,
            'Classe': None,
            'Attività (micro)': None,
            'Orario inizio': df_formatrice['Orario inizio'].median()
        }]))

    if df_con_totali:
        df_finale = pd.concat(df_con_totali, ignore_index=True)
    else:
        df_finale = df

    return df_finale


def genera_foglio_per_scuola_per_classe(df_calendario, scuole, classi, fasce_orarie_scuole):
    """
    Genera il foglio 'per_scuola_per_Classe' con formato:
    Scuola | Classe | Settimana | Data | Giorno Settimana | Attività (micro) |
    Partner | Nome formatore | Orario inizio
    """

    risultati = []

    for _, row in df_calendario.iterrows():
        data = giorno_a_data(row['Settimana'], row['Giorno'])

        scuola_id = classi[classi['nome'] == row['Classe']]['scuola_id'].values[0]
        scuola_nome = scuole[scuole['scuola_id'] == scuola_id]['nome'].values[0]

        attivita_micro_map = {
            'Citizen Science': 'citizen science',
            'Discriminazioni di genere': 'sensibilizzazione discriminazioni di genere',
            'Orientamento e competenze': 'orientamento e competenze',
            'Presentazione manuali': 'presentazione manuali'
        }

        attivita_micro = attivita_micro_map.get(row['Laboratorio'], row['Laboratorio'].lower())

        # Estrai orario dal nome della fascia (es: "14-16")
        ora_inizio, _ = fascia_a_orario(row['Fascia'])

        # Se il parsing fallisce, prova dal CSV
        if ora_inizio is None:
            fascia_row = fasce_orarie_scuole[
                (fasce_orarie_scuole['scuola_id'] == scuola_id) &
                (fasce_orarie_scuole['nome'] == row['Fascia'])
            ]
            if len(fascia_row) > 0:
                ora_inizio_str = fascia_row.iloc[0]['ora_inizio']
                ora_inizio = float(ora_inizio_str.split(':')[0])

        risultati.append({
            'Scuola': scuola_nome,
            'Classe': row['Classe'],
            'Settimana': get_week_number(data),
            'Data': data,
            'Giorno Settimana': get_italian_weekday(data),
            'Attività (micro)': attivita_micro,
            'Partner': 'FOP',
            'Nome formatore': row['Formatrice'],
            'Orario inizio': ora_inizio
        })

    df = pd.DataFrame(risultati)
    df = df.sort_values(['Scuola', 'Classe', 'Data'])
    return df


def genera_foglio_per_scuola_per_data(df_calendario, scuole, classi, fasce_orarie_scuole):
    """
    Genera il foglio 'per_scuola_per_data' con formato:
    Scuola | Settimana | Data | Giorno Settimana | Classe | Attività (micro) |
    Partner | Nome formatore | Orario inizio
    """

    risultati = []

    for _, row in df_calendario.iterrows():
        data = giorno_a_data(row['Settimana'], row['Giorno'])

        scuola_id = classi[classi['nome'] == row['Classe']]['scuola_id'].values[0]
        scuola_nome = scuole[scuole['scuola_id'] == scuola_id]['nome'].values[0]

        attivita_micro_map = {
            'Citizen Science': 'citizen science',
            'Discriminazioni di genere': 'sensibilizzazione discriminazioni di genere',
            'Orientamento e competenze': 'orientamento e competenze',
            'Presentazione manuali': 'presentazione manuali'
        }

        attivita_micro = attivita_micro_map.get(row['Laboratorio'], row['Laboratorio'].lower())

        # Estrai orario dal nome della fascia (es: "14-16")
        ora_inizio, _ = fascia_a_orario(row['Fascia'])

        # Se il parsing fallisce, prova dal CSV
        if ora_inizio is None:
            fascia_row = fasce_orarie_scuole[
                (fasce_orarie_scuole['scuola_id'] == scuola_id) &
                (fasce_orarie_scuole['nome'] == row['Fascia'])
            ]
            if len(fascia_row) > 0:
                ora_inizio_str = fascia_row.iloc[0]['ora_inizio']
                ora_inizio = float(ora_inizio_str.split(':')[0])

        risultati.append({
            'Scuola': scuola_nome,
            'Settimana': get_week_number(data),
            'Data': data,
            'Giorno Settimana': get_italian_weekday(data),
            'Classe': row['Classe'],
            'Attività (micro)': attivita_micro,
            'Partner': 'FOP',
            'Nome formatore': row['Formatrice'],
            'Orario inizio': ora_inizio
        })

    df = pd.DataFrame(risultati)
    df = df.sort_values(['Scuola', 'Data', 'Orario inizio'])
    return df


def esporta_formato_richiesto(df_calendario, scuole, classi, laboratori, formatrici,
                               fasce_orarie_scuole, output_path):
    """
    Esporta l'output nel formato richiesto con 4 fogli.
    """

    print("📝 Generazione output nel formato richiesto...")

    # Genera i 4 fogli
    print("  • Foglio 'complessivo'...")
    df_complessivo = genera_foglio_complessivo(df_calendario, scuole, classi,
                                                laboratori, formatrici, fasce_orarie_scuole)

    print("  • Foglio 'per_formatore_sett_data'...")
    df_per_formatore = genera_foglio_per_formatore(df_calendario, scuole, classi, fasce_orarie_scuole)

    print("  • Foglio 'per_scuola_per_Classe'...")
    df_per_scuola_classe = genera_foglio_per_scuola_per_classe(df_calendario, scuole, classi, fasce_orarie_scuole)

    print("  • Foglio 'per_scuola_per_data'...")
    df_per_scuola_data = genera_foglio_per_scuola_per_data(df_calendario, scuole, classi, fasce_orarie_scuole)

    # Salva in Excel
    print(f"  • Salvataggio in {output_path}...")
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_complessivo.to_excel(writer, sheet_name='complessivo', index=False)
        df_per_formatore.to_excel(writer, sheet_name='per_formatore_sett_data', index=False)
        df_per_scuola_classe.to_excel(writer, sheet_name='per_scuola_per_Classe', index=False)
        df_per_scuola_data.to_excel(writer, sheet_name='per_scuola_per_data', index=False)

    print(f"✅ Output salvato in: {output_path}\n")
