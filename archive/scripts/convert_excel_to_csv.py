#!/usr/bin/env python3
"""
Script per convertire criteri.xlsx in CSV compatibili con optimizer_v3.py
"""

import pandas as pd
import sys
from pathlib import Path

INPUT_EXCEL = "criteri.xlsx"
OUTPUT_DIR = Path("data/input")


def pulisci_celle(df):
    """Rimuove CR/LF e altri caratteri problematici dalle celle di testo."""
    import re
    for col in df.columns:
        if df[col].dtype == 'object':  # Solo colonne di testo
            df[col] = df[col].apply(
                lambda x: re.sub(r'[\r\n\x0b\x0c]+', ' ', str(x)).strip()
                if pd.notna(x) else x
            )
    return df


def converti_scuole(xl_file):
    """Converte foglio scuole in scuole.csv"""
    print("Conversione scuole...")
    df = pulisci_celle(pd.read_excel(xl_file, sheet_name='scuole'))

    # Crea DataFrame con colonne richieste dall'optimizer
    scuole_csv = pd.DataFrame({
        'scuola_id': df['scuola_id'],
        'nome': df['nome'],
        'citta': df['cittá'],  # Nota: accento acuto nell'Excel
        'preferenza_orario': 'misto',  # Default, da verificare con Elena
        'sabato_disponibile': 'no'  # Default, solo poche scuole possono
    })

    output_path = OUTPUT_DIR / "scuole.csv"
    scuole_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(scuole_csv)} scuole)")
    return scuole_csv


def converti_classi(xl_file):
    """Converte foglio classi in classi.csv"""
    print("Conversione classi...")
    df = pulisci_celle(pd.read_excel(xl_file, sheet_name='classi'))

    # Estrai anno dalla nomenclatura classe (3A -> anno 3, 4B -> anno 4, ecc.)
    def estrai_anno(nome_classe):
        nome_str = str(nome_classe)
        # Prova a estrarre il primo numero
        for char in nome_str:
            if char.isdigit():
                anno = int(char)
                if anno in [3, 4, 5]:
                    return anno
        return 4  # Default

    # Determina priorità (alta per classi quinte)
    def determina_priorita(nome_classe):
        anno = estrai_anno(nome_classe)
        return 'alta' if anno == 5 else 'normale'

    # Colonna accorpamenti preferenziali
    col_accorpamenti = 'accorpamenti preferenziali (solo con classi della stessa scuola)'
    if col_accorpamenti in df.columns:
        accorpamenti = df[col_accorpamenti]
    else:
        accorpamenti = pd.Series([None] * len(df))
        print("  ⚠️  Colonna accorpamenti preferenziali non trovata")

    classi_csv = pd.DataFrame({
        'classe_id': df['classe_id'],
        'nome': df['nome'],
        'scuola_id': df['scuola_id'],
        'anno': df['nome'].apply(estrai_anno),
        'priorita': df['nome'].apply(determina_priorita),
        'accorpamento_preferenziale': accorpamenti
    })

    output_path = OUTPUT_DIR / "classi.csv"
    classi_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(classi_csv)} classi)")
    return classi_csv


def converti_formatrici(xl_file):
    """Converte foglio formatrici in formatrici.csv"""
    print("Conversione formatrici...")
    df = pulisci_celle(pd.read_excel(xl_file, sheet_name='formatrici'))

    # Rimuovi riga totale (ultima riga con NaN in formatrice_id)
    df = df[df['fomatrice_id'].notna()].copy()

    def estrai_giorni_da_testo(testo):
        """Estrae giorni da testo tipo 'lunedì, martedì, mercoledì'"""
        if pd.isna(testo):
            return None
        testo = str(testo).lower()
        # Se contiene riferimento a date specifiche, ritorna None (caso speciale)
        if 'vedi' in testo or 'date' in testo or 'solo' in testo:
            return None

        giorni = []
        if 'lun' in testo:
            giorni.append('lun')
        if 'mar' in testo:
            giorni.append('mar')
        if 'mer' in testo:
            giorni.append('mer')
        if 'gio' in testo or 'giov' in testo:  # "govedì" typo nell'Excel
            giorni.append('gio')
        if 'ven' in testo:
            giorni.append('ven')

        return ','.join(giorni) if giorni else None

    def estrai_mattine(row):
        return estrai_giorni_da_testo(row.get('mattine_disponibili'))

    def estrai_pomeriggi(row):
        return estrai_giorni_da_testo(row.get('pomeriggi_disponibili'))

    def estrai_date_disponibili(row):
        """Per Margherita: estrae le date_disponibili specifiche"""
        date_disp = row.get('date_disponibili')
        if pd.isna(date_disp):
            return None
        return str(date_disp).strip()

    formatrici_csv = pd.DataFrame({
        'formatrice_id': df['fomatrice_id'].astype(int),
        'nome': df['nome'],
        'ore_generali': df['ore_generali'].fillna(100),
        'lavora_sabato': df['lavora_sabato'].fillna('no'),
        'mattine_disponibili': df.apply(estrai_mattine, axis=1),
        'pomeriggi_disponibili': df.apply(estrai_pomeriggi, axis=1),
        'date_disponibili': df.apply(estrai_date_disponibili, axis=1)
    })

    output_path = OUTPUT_DIR / "formatrici.csv"
    formatrici_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(formatrici_csv)} formatrici)")

    # Mostra riepilogo disponibilità
    for _, row in formatrici_csv.iterrows():
        mattine = row['mattine_disponibili'] or '(date specifiche)'
        pomeriggi = row['pomeriggi_disponibili'] or '(date specifiche)'
        print(f"    {row['nome']}: mattine={mattine}, pomeriggi={pomeriggi}")

    return formatrici_csv


def converti_laboratori(xl_file, classi_df):
    """Converte foglio laboratori in laboratori.csv

    Nota: considera solo i laboratori gestiti da formatrici, non quelli di GSSI/GST/LNGS
    """
    print("Conversione laboratori...")
    df = pulisci_celle(pd.read_excel(xl_file, sheet_name='laboratori'))

    # Filtra solo laboratori gestiti da formatrici
    df_formatrici = df[df['formatori'] == 'formatrici'].copy()

    # Assegna sequenza basata su laboratorio_id
    laboratori_csv = pd.DataFrame({
        'laboratorio_id': df_formatrici['laboratorio_id'],
        'nome': df_formatrici['nome'],
        'num_incontri': df_formatrici['num_incontri'],
        'ore_per_incontro': df_formatrici['ore_per_incontro'],
        'sequenza': df_formatrici['laboratorio_id']  # Usa ID come sequenza per ora
    })

    output_path = OUTPUT_DIR / "laboratori.csv"
    laboratori_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(laboratori_csv)} laboratori)")
    print(f"  ℹ️  Nota: considerati solo laboratori gestiti da formatrici")
    print(f"      Laboratori GSSI/GST/LNGS dovranno essere gestiti separatamente")
    return laboratori_csv


def converti_fasce_orarie_scuole(xl_file, scuole_df):
    """Converte foglio fasce_orarie in fasce_orarie_scuole.csv

    Crea una matrice con tutte le fasce disponibili per ogni scuola.
    """
    print("Conversione fasce orarie scuole...")
    df_fasce = pulisci_celle(pd.read_excel(xl_file, sheet_name='fasce_orarie'))

    # Mappatura manuale per fasce con nomi errati (date invece di orari)
    # NOTA: Le fasce 1,2,3 nell'Excel hanno nomi come "2025-10-08" - errato!
    # Assumiamo siano fasce mattutine standard
    FASCE_CORREZIONE = {
        1: ('8-10', '08:00', '10:00', 'mattina'),
        2: ('9-11', '09:00', '11:00', 'mattina'),
        3: ('10-12', '10:00', '12:00', 'mattina'),
    }

    def estrai_orari_da_nome(nome_fascia, fascia_id, durata):
        """Estrae ora_inizio e ora_fine dal nome della fascia (es: '14-16')"""
        nome_str = str(nome_fascia)

        # Se la fascia ha una correzione manuale, usala
        if fascia_id in FASCE_CORREZIONE:
            nome_corretto, ora_inizio, ora_fine, tipo = FASCE_CORREZIONE[fascia_id]
            print(f"  ⚠️  Fascia {fascia_id}: nome errato '{nome_str}' → corretto in '{nome_corretto}'")
            return nome_corretto, ora_inizio, ora_fine, tipo

        # Prova a parsare dal nome (es: "14-16", "14.30-16.30")
        if '-' in nome_str and '202' not in nome_str:  # Non è una data
            parti = nome_str.split('-')
            try:
                # Gestisce "14" o "14.30"
                inizio_str = parti[0].replace('.', ':')
                fine_str = parti[1].replace('.', ':')

                # Aggiungi :00 se mancante
                if ':' not in inizio_str:
                    inizio_str += ':00'
                if ':' not in fine_str:
                    fine_str += ':00'

                # Determina tipo (mattina se ora < 13, pomeriggio altrimenti)
                ora_inizio_num = int(inizio_str.split(':')[0])
                tipo = 'mattina' if ora_inizio_num < 13 else 'pomeriggio'

                return nome_str, inizio_str, fine_str, tipo
            except (ValueError, IndexError):
                pass

        # Fallback: usa placeholder
        print(f"  ⚠️  Fascia {fascia_id}: impossibile parsare '{nome_str}', uso placeholder")
        return nome_str, '08:00', '10:00', 'misto'

    # Crea matrice scuola x fascia (ogni scuola ha tutte le fasce per semplicità)
    righe = []
    for _, scuola in scuole_df.iterrows():
        for _, fascia in df_fasce.iterrows():
            fascia_id = int(fascia['fascia_id'])
            durata = fascia.get('durata', 2)
            nome_pulito, ora_inizio, ora_fine, tipo = estrai_orari_da_nome(
                fascia['nome'], fascia_id, durata
            )

            righe.append({
                'scuola_id': scuola['scuola_id'],
                'fascia_id': fascia_id,
                'nome': nome_pulito,
                'ora_inizio': ora_inizio,
                'ora_fine': ora_fine,
                'tipo_giornata': tipo
            })

    fasce_csv = pd.DataFrame(righe)

    output_path = OUTPUT_DIR / "fasce_orarie_scuole.csv"
    fasce_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(fasce_csv)} righe)")
    print(f"  ℹ️  Nota: assegnate tutte le fasce a tutte le scuole (semplificazione)")
    return fasce_csv


def converti_date_escluse_classi(xl_file):
    """Converte foglio date_escluse_classi in date_escluse_classi.csv"""
    print("Conversione date escluse classi...")
    df = pulisci_celle(pd.read_excel(xl_file, sheet_name='date_escluse_classi'))

    # Mantieni solo classi con date effettivamente escluse
    df_filtered = df[df['data escluse'].notna()].copy()

    date_escluse_csv = pd.DataFrame({
        'classe_id': df_filtered['classe_id'],
        'nome_classe': df_filtered['nome'],
        'date_escluse': df_filtered['data escluse']
    })

    output_path = OUTPUT_DIR / "date_escluse_classi.csv"
    date_escluse_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(date_escluse_csv)} classi con date escluse)")
    return date_escluse_csv


def converti_fasce_orarie_classi(xl_file):
    """Converte foglio fasce_orarie_classi in fasce_orarie_classi.csv"""
    print("Conversione fasce orarie per classi...")
    df = pulisci_celle(pd.read_excel(xl_file, sheet_name='fasce_orarie_classi'))

    fasce_classi_csv = pd.DataFrame({
        'classe_id': df['classe_id'],
        'nome_classe': df['nome'],
        'fasce_disponibili': df['fascia'],  # Es: "1\n2\n3\n4\n5" o "6, 7"
        'preferenza': df['preferenza'],
        'giorni_settimana': df['giorni settimana']
    })

    output_path = OUTPUT_DIR / "fasce_orarie_classi.csv"
    fasce_classi_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(fasce_classi_csv)} classi)")
    return fasce_classi_csv


def converti_formatrici_classi(xl_file):
    """Converte foglio formatrici_classi in formatrici_classi.csv"""
    print("Conversione assegnamenti formatrici-classi...")
    df = pulisci_celle(pd.read_excel(xl_file, sheet_name='formatrici_classi'))

    formatrici_classi_csv = pd.DataFrame({
        'formatrice_id': df['fomatrice_id'],
        'nome_formatrice': df['nome_formatrice'],
        'classe_id': df['classe_id'],
        'nome_classe': df['nome_classe']
    })

    output_path = OUTPUT_DIR / "formatrici_classi.csv"
    formatrici_classi_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(formatrici_classi_csv)} assegnamenti)")
    return formatrici_classi_csv


def converti_laboratori_classi(xl_file):
    """Converte foglio laboratori_classi in laboratori_classi.csv"""
    print("Conversione laboratori per classi...")
    df = pulisci_celle(pd.read_excel(xl_file, sheet_name='laboratori_classi'))

    laboratori_classi_csv = pd.DataFrame({
        'classe_id': df['classe_id'],
        'nome_classe': df['nome'],
        'scuola_id': df['scuola_id'],
        'laboratorio_id': df['laboratorio_id'],
        'dettagli': df['dettagli_laboraotorio'],
        'date_fissate': df['date giá fissate']
    })

    output_path = OUTPUT_DIR / "laboratori_classi.csv"
    laboratori_classi_csv.to_csv(output_path, index=False)
    print(f"  ✓ Creato {output_path} ({len(laboratori_classi_csv)} laboratori-classe)")
    return laboratori_classi_csv


def main():
    """Converte tutti i fogli Excel in CSV"""

    print("="*60)
    print("Conversione Excel -> CSV per Optimizer V2 (COMPLETA)")
    print("="*60)
    print()

    # Verifica file input
    if not Path(INPUT_EXCEL).exists():
        print(f"❌ File non trovato: {INPUT_EXCEL}")
        sys.exit(1)

    # Crea directory output se non esiste
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Leggi Excel
    print(f"📂 Lettura {INPUT_EXCEL}...")
    xl_file = pd.ExcelFile(INPUT_EXCEL)
    print(f"   Fogli trovati: {', '.join(xl_file.sheet_names)}")
    print()

    # Converti fogli base
    scuole_df = converti_scuole(xl_file)
    print()

    classi_df = converti_classi(xl_file)
    print()

    formatrici_df = converti_formatrici(xl_file)
    print()

    laboratori_df = converti_laboratori(xl_file, classi_df)
    print()

    fasce_df = converti_fasce_orarie_scuole(xl_file, scuole_df)
    print()

    # Converti fogli con vincoli aggiuntivi
    print("="*60)
    print("VINCOLI AGGIUNTIVI")
    print("="*60)
    print()

    date_escluse_df = converti_date_escluse_classi(xl_file)
    print()

    fasce_classi_df = converti_fasce_orarie_classi(xl_file)
    print()

    formatrici_classi_df = converti_formatrici_classi(xl_file)
    print()

    laboratori_classi_df = converti_laboratori_classi(xl_file)
    print()

    print("="*60)
    print("✅ Conversione completata!")
    print("="*60)
    print()
    print("File CSV generati:")
    print("  Base:")
    print("    - scuole.csv, classi.csv, formatrici.csv")
    print("    - laboratori.csv, fasce_orarie_scuole.csv")
    print("  Vincoli:")
    print("    - date_escluse_classi.csv")
    print("    - fasce_orarie_classi.csv")
    print("    - formatrici_classi.csv")
    print("    - laboratori_classi.csv")
    print()
    print("Prossimi passi:")
    print("1. Verifica i CSV in data/input/")
    print("2. Aggiorna optimizer per usare i nuovi vincoli")
    print("3. Testa con subset ridotto")
    print()


if __name__ == "__main__":
    main()
