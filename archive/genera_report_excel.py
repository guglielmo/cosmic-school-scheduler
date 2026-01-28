#!/usr/bin/env python3
"""
Genera report Excel per Elena con problemi e domande
"""

import pandas as pd
from pathlib import Path
import sys

INPUT_DIR = Path("data/input")
OUTPUT_FILE = "REPORT_VINCOLI_per_Elena.xlsx"


def main():
    """Genera report Excel"""

    print("📊 Generazione report Excel per Elena...")
    print()

    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:

        # FOGLIO 1: RIEPILOGO
        print("  • Foglio RIEPILOGO")
        riepilogo_data = {
            'Categoria': [
                'DIMENSIONI',
                '',
                '',
                '',
                '',
                '',
                'ORE DISPONIBILI',
                '',
                '',
                '',
                '',
                'TOTALE',
                '',
                'ORE RICHIESTE',
                '',
                'DEFICIT',
            ],
            'Descrizione': [
                'Classi totali',
                'Scuole',
                'Formatrici',
                'Laboratori (solo formatrici)',
                'Settimane',
                'Fasce orarie medie per scuola',
                'Anita (18h/sett × 20 sett)',
                'Andreea (8h/sett × 20 sett)',
                'Ida (10h/sett × 20 sett)',
                'Margherita (8h/sett × 20 sett)',
                '',
                'Ore disponibili totali',
                '',
                'Ore richieste (stimate)',
                '',
                'MANCANO (⚠️ PROBLEMA CRITICO)',
            ],
            'Valore': [
                87,
                13,
                4,
                5,
                20,
                12,
                360,
                160,
                200,
                160,
                '',
                880,
                '',
                962,
                '',
                -82,
            ],
            'Note': [
                '',
                '',
                '',
                'Esclusi GSSI/GST/LNGS',
                'Gennaio-Maggio',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                'Solo laboratori formatrici',
                '',
                '9.3% oltre disponibile',
            ]
        }
        df_riepilogo = pd.DataFrame(riepilogo_data)
        df_riepilogo.to_excel(writer, sheet_name='RIEPILOGO', index=False)

        # FOGLIO 2: PROBLEMI CRITICI
        print("  • Foglio PROBLEMI_CRITICI")
        problemi_data = {
            'ID': [1, 2, 3, 4, 5, 6],
            'Problema': [
                'DEFICIT ORE (-82 ore)',
                'Classi senza formatrice (20 classi)',
                'Distribuzione carico sbilanciata',
                'Date già fissate (96 incontri)',
                'Date escluse formati misti (23 classi)',
                'Fasce orarie limitate (21 classi critiche)'
            ],
            'Priorità': [
                'MASSIMA',
                'ALTA',
                'MEDIA',
                'ALTA',
                'ALTA',
                'MEDIA'
            ],
            'Impatto': [
                'Problema potrebbe non avere soluzione',
                'Non si sa a chi assegnarle',
                'Anita ha 40 classi, altre 14-17',
                'Vincoli hard da rispettare',
                'Serve standardizzazione o parsing complesso',
                '2-3 fasce disponibili = difficile schedulare'
            ],
            'Azione Richiesta': [
                'Aumentare ore o ridurre laboratori',
                'Assegnare manualmente o lasciare all\'optimizer?',
                'Verificare se intenzionale',
                'Vanno incluse nel calendario o sono fuori?',
                'Standardizzare formato in Excel',
                'Ampliare fasce disponibili se possibile'
            ]
        }
        df_problemi = pd.DataFrame(problemi_data)
        df_problemi.to_excel(writer, sheet_name='PROBLEMI_CRITICI', index=False)

        # FOGLIO 3: CLASSI SENZA FORMATRICE
        print("  • Foglio CLASSI_SENZA_FORMATRICE")
        classi = pd.read_csv(INPUT_DIR / "classi.csv")
        formatrici_classi = pd.read_csv(INPUT_DIR / "formatrici_classi.csv")

        classi_con_formatrice = set(formatrici_classi['classe_id'])
        classi_senza = classi[~classi['classe_id'].isin(classi_con_formatrice)].copy()

        df_senza = pd.DataFrame({
            'classe_id': classi_senza['classe_id'],
            'nome_classe': classi_senza['nome'],
            'scuola_id': classi_senza['scuola_id'],
            'anno': classi_senza['anno'],
            'AZIONE': ['Assegnare formatrice'] * len(classi_senza)
        })
        df_senza.to_excel(writer, sheet_name='CLASSI_SENZA_FORMATRICE', index=False)

        # FOGLIO 4: DISTRIBUZIONE CARICO
        print("  • Foglio CARICO_FORMATRICI")
        carico = formatrici_classi.groupby('nome_formatrice').agg({
            'classe_id': 'count'
        }).reset_index()
        carico.columns = ['Formatrice', 'N_Classi_Assegnate']

        formatrici = pd.read_csv(INPUT_DIR / "formatrici.csv")
        carico = carico.merge(
            formatrici[['nome', 'ore_settimanali_max']],
            left_on='Formatrice',
            right_on='nome',
            how='left'
        )
        carico['Ore_Totali_20sett'] = carico['ore_settimanali_max'] * 20
        carico = carico[['Formatrice', 'N_Classi_Assegnate', 'ore_settimanali_max', 'Ore_Totali_20sett']]
        carico.columns = ['Formatrice', 'Classi Assegnate', 'Ore/Settimana', 'Ore Totali (20 sett)']

        carico.to_excel(writer, sheet_name='CARICO_FORMATRICI', index=False)

        # FOGLIO 5: DATE GIÀ FISSATE
        print("  • Foglio DATE_FISSATE")
        laboratori_classi = pd.read_csv(INPUT_DIR / "laboratori_classi.csv")
        date_fissate = laboratori_classi[laboratori_classi['date_fissate'].notna()].copy()

        df_date_fissate = pd.DataFrame({
            'classe_id': date_fissate['classe_id'],
            'nome_classe': date_fissate['nome_classe'],
            'laboratorio_id': date_fissate['laboratorio_id'],
            'date_fissate': date_fissate['date_fissate'],
            'DOMANDA': ['Includere nel calendario finale?'] * len(date_fissate)
        })
        df_date_fissate.to_excel(writer, sheet_name='DATE_FISSATE', index=False)

        # FOGLIO 6: DATE ESCLUSE
        print("  • Foglio DATE_ESCLUSE")
        date_escluse = pd.read_csv(INPUT_DIR / "date_escluse_classi.csv")
        date_escluse['PROBLEMA'] = date_escluse['date_escluse'].apply(
            lambda x: 'Formato misto - serve standardizzare' if '\n' in str(x) or 'dal' in str(x) else 'OK'
        )
        date_escluse.to_excel(writer, sheet_name='DATE_ESCLUSE', index=False)

        # FOGLIO 7: FASCE LIMITATE
        print("  • Foglio FASCE_LIMITATE")
        fasce_classi = pd.read_csv(INPUT_DIR / "fasce_orarie_classi.csv")

        def conta_fasce(fasce_str):
            if pd.isna(fasce_str):
                return 0
            if '\n' in str(fasce_str):
                return len(str(fasce_str).split('\n'))
            elif ',' in str(fasce_str):
                return len(str(fasce_str).split(','))
            return 1

        fasce_classi['n_fasce'] = fasce_classi['fasce_disponibili'].apply(conta_fasce)
        fasce_limitate = fasce_classi[fasce_classi['n_fasce'] <= 3].copy()

        df_fasce_limitate = pd.DataFrame({
            'classe_id': fasce_limitate['classe_id'],
            'nome_classe': fasce_limitate['nome_classe'],
            'n_fasce_disponibili': fasce_limitate['n_fasce'],
            'fasce': fasce_limitate['fasce_disponibili'],
            'DOMANDA': ['Possibile ampliare fasce?'] * len(fasce_limitate)
        })
        df_fasce_limitate.to_excel(writer, sheet_name='FASCE_LIMITATE', index=False)

        # FOGLIO 8: DOMANDE PER ELENA
        print("  • Foglio DOMANDE")
        domande_data = {
            'ID': list(range(1, 10)),
            'Priorità': [
                'ALTA', 'ALTA', 'ALTA', 'MEDIA', 'MEDIA', 'MEDIA', 'BASSA', 'BASSA', 'BASSA'
            ],
            'Domanda': [
                'Come risolviamo deficit 82 ore? (aumentare ore formatrici / ridurre lab / estendere periodo / >1 incontro sett?)',
                'Le 20 classi senza formatrice: assegnare manualmente o lasciare all\'optimizer?',
                'Date già fissate: vanno incluse nel calendario finale o sono già fuori schedulazione?',
                'Laboratori GSSI/GST/LNGS: schedularli prima/dopo o integrarli nell\'optimizer?',
                'Citizen Science lab 4.0: schedulare 4 o 5 incontri? (3° è autonomo)',
                'Date escluse: possiamo standardizzare formato? (es: YYYY-MM-DD a YYYY-MM-DD)',
                'Correggere fasce orarie 1,2,3 con timestamp (dovrebbero essere orari)',
                'Preferenza_fasce formatrice Ida: correggere "1.2" in mattina/pomeriggio/misto',
                'Colonna "Unnamed: 3" nel foglio scuole: cosa significa?'
            ],
            'Risposta': [''] * 9,
            'Note': [''] * 9
        }
        df_domande = pd.DataFrame(domande_data)
        df_domande.to_excel(writer, sheet_name='DOMANDE', index=False)

        # FOGLIO 9: ANOMALIE DATI
        print("  • Foglio ANOMALIE_DATI")
        anomalie_data = {
            'Foglio_Excel': [
                'fasce_orarie',
                'fasce_orarie',
                'fasce_orarie',
                'formatrici',
                'scuole',
                'date_escluse_classi',
                'laboratori_classi'
            ],
            'Problema': [
                'Fascia 1 = "2025-10-08 00:00:00" invece di orario',
                'Fascia 2 = "2025-11-09 00:00:00" invece di orario',
                'Fascia 3 = "2025-12-10 00:00:00" invece di orario',
                'Ida ha preferenza_fasce = "1.2"',
                'Colonna "Unnamed: 3" con valori ok/no/NaN',
                'Formati date misti (timestamp, testuale, liste)',
                'Formati date misti in "date giá fissate"'
            ],
            'Correzione_Suggerita': [
                'Inserire orario es: "8-10" o "9-11"',
                'Inserire orario es: "11-13"',
                'Inserire orario es: "10-12" o "12-14"',
                'Cambiare in: "mattina", "pomeriggio" o "misto"',
                'Chiarire significato o rimuovere',
                'Standardizzare in YYYY-MM-DD (opzionale: mattina/pomeriggio)',
                'Standardizzare formato date'
            ],
            'Impatto': [
                'MEDIO - Parser può fallire',
                'MEDIO - Parser può fallire',
                'MEDIO - Parser può fallire',
                'BASSO - Valore ignorato',
                'BASSO - Colonna ignorata',
                'ALTO - Vincoli non applicabili',
                'ALTO - Vincoli non applicabili'
            ]
        }
        df_anomalie = pd.DataFrame(anomalie_data)
        df_anomalie.to_excel(writer, sheet_name='ANOMALIE_DATI', index=False)

    print()
    print(f"✅ Report generato: {OUTPUT_FILE}")
    print()
    print("Fogli creati:")
    print("  1. RIEPILOGO - Dimensioni e deficit ore")
    print("  2. PROBLEMI_CRITICI - Lista problemi prioritizzati")
    print("  3. CLASSI_SENZA_FORMATRICE - 20 classi da assegnare")
    print("  4. CARICO_FORMATRICI - Distribuzione classi per formatrice")
    print("  5. DATE_FISSATE - 96 incontri con date pre-definite")
    print("  6. DATE_ESCLUSE - 23 classi con date blackout")
    print("  7. FASCE_LIMITATE - 21 classi con 2-3 fasce")
    print("  8. DOMANDE - 9 domande per Elena con spazio risposte")
    print("  9. ANOMALIE_DATI - Correzioni dati da fare in Excel")
    print()


if __name__ == "__main__":
    main()
