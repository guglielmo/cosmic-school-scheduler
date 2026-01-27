#!/usr/bin/env python3
"""
Generate different CSV views from the optimizer output.

Creates:
1. Per-class calendars (data/output/views/classi/)
2. Per-trainer calendars (data/output/views/formatrici/)
3. Per-lab calendars (data/output/views/laboratori/)
4. Daily calendar with grouped classes (data/output/views/calendario_giornaliero.csv)
"""

import pandas as pd
from pathlib import Path
from collections import defaultdict

def main():
    # Load main calendar
    input_file = Path("data/output/calendario.csv")
    output_dir = Path("data/output/views")

    if not input_file.exists():
        print(f"Error: {input_file} not found")
        return

    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} rows from {input_file}")

    # Fix: Ricalcola i nomi dei giorni dalle date effettive e aggiungi colonna date per ordinamento
    italian_weekdays = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    from datetime import datetime

    dates = []
    for idx, row in df.iterrows():
        date_str = row['data_ora'].split()[0]  # Extract date part
        date = datetime.strptime(date_str, '%d/%m/%Y')
        correct_weekday = italian_weekdays[date.weekday()]
        df.at[idx, 'giorno_nome'] = correct_weekday
        dates.append(date)

    df['_date_sort'] = dates  # Temporary column for sorting
    print(f"  ✓ Ricalcolati nomi giorni dalle date")

    # Create output directories
    (output_dir / "classi").mkdir(parents=True, exist_ok=True)
    (output_dir / "formatrici").mkdir(parents=True, exist_ok=True)
    (output_dir / "laboratori").mkdir(parents=True, exist_ok=True)

    # 1. Vista per classe
    print("\n1. Generating per-class views...")
    for class_id in df['classe_id'].unique():
        class_df = df[df['classe_id'] == class_id].copy()
        class_name = class_df['classe_nome'].iloc[0]
        school_name = class_df['scuola_nome'].iloc[0]

        # Sort by date (correct chronological order)
        class_df = class_df.sort_values(['settimana', '_date_sort', 'fascia_num'])

        # Select relevant columns
        output = class_df[[
            'laboratorio_nome', 'incontro_num',
            'settimana', 'giorno_nome', 'fascia_nome',
            'data_ora', 'formatrice_nome', 'accorpata_con'
        ]].copy()

        output.columns = [
            'Laboratorio', 'Incontro N.',
            'Settimana', 'Giorno', 'Fascia Oraria',
            'Data e Ora', 'Formatrice', 'Accorpata Con'
        ]

        # Safe filename
        safe_name = class_name.replace('/', '-').replace(' ', '_')
        filename = f"{safe_name}_{school_name.replace(' ', '_')}.csv"
        output_path = output_dir / "classi" / filename
        output.to_csv(output_path, index=False)
        print(f"  ✓ {class_name} ({school_name}): {len(output)} incontri")

    # 2. Vista per formatrice (collassa accorpamenti)
    print("\n2. Generating per-trainer views...")
    for trainer_id in df['formatrice_id'].unique():
        trainer_df = df[df['formatrice_id'] == trainer_id].copy()
        trainer_name = trainer_df['formatrice_nome'].iloc[0]

        # Create unique meeting identifier (slot + lab)
        trainer_df['meeting_key'] = trainer_df.apply(
            lambda r: (r['settimana'], r['giorno_num'], r['fascia_num'], r['laboratorio_id']),
            axis=1
        )

        # Collapse groupings
        trainer_records = []
        for meeting_key, group in trainer_df.groupby('meeting_key'):
            row = group.iloc[0]

            # Collect all classes (sorted)
            classes = sorted(group['classe_nome'].unique())
            classes_str = ", ".join(classes)

            # Collect schools (should be same for grouped classes)
            schools = group['scuola_nome'].unique()
            school_str = schools[0] if len(schools) == 1 else ", ".join(schools)

            # Is grouped?
            is_grouped = len(classes) > 1

            trainer_records.append({
                'Classi': classes_str,
                'N. Classi': len(classes),
                'Scuola': school_str,
                'Laboratorio': row['laboratorio_nome'],
                'Settimana': row['settimana'],
                'Giorno': row['giorno_nome'],
                'Fascia Oraria': row['fascia_nome'],
                'Data e Ora': row['data_ora'],
                'Accorpamento': 'Sì' if is_grouped else 'No'
            })

        output = pd.DataFrame(trainer_records)
        # Add date column for proper sorting
        output['_date_sort'] = output['Data e Ora'].apply(
            lambda x: datetime.strptime(x.split()[0], '%d/%m/%Y')
        )
        output = output.sort_values(['Settimana', '_date_sort', 'Fascia Oraria'])
        output = output.drop(columns=['_date_sort'])

        output_path = output_dir / "formatrici" / f"{trainer_name}.csv"
        output.to_csv(output_path, index=False)
        print(f"  ✓ {trainer_name}: {len(output)} incontri fisici")

    # 3. Vista per laboratorio (collassa accorpamenti)
    print("\n3. Generating per-lab views...")
    for lab_id in df['laboratorio_id'].unique():
        lab_df = df[df['laboratorio_id'] == lab_id].copy()
        lab_name = lab_df['laboratorio_nome'].iloc[0]

        # Create unique meeting identifier (slot + trainer for this lab)
        lab_df['meeting_key'] = lab_df.apply(
            lambda r: (r['settimana'], r['giorno_num'], r['fascia_num'], r['formatrice_id']),
            axis=1
        )

        # Collapse groupings
        lab_records = []
        for meeting_key, group in lab_df.groupby('meeting_key'):
            row = group.iloc[0]

            # Collect all classes (sorted)
            classes = sorted(group['classe_nome'].unique())
            classes_str = ", ".join(classes)

            # Collect schools (should be same for grouped classes)
            schools = group['scuola_nome'].unique()
            school_str = schools[0] if len(schools) == 1 else ", ".join(schools)

            # Is grouped?
            is_grouped = len(classes) > 1

            lab_records.append({
                'Classi': classes_str,
                'N. Classi': len(classes),
                'Scuola': school_str,
                'Settimana': row['settimana'],
                'Giorno': row['giorno_nome'],
                'Fascia Oraria': row['fascia_nome'],
                'Data e Ora': row['data_ora'],
                'Formatrice': row['formatrice_nome'],
                'Accorpamento': 'Sì' if is_grouped else 'No'
            })

        output = pd.DataFrame(lab_records)
        # Add date column for proper sorting
        output['_date_sort'] = output['Data e Ora'].apply(
            lambda x: datetime.strptime(x.split()[0], '%d/%m/%Y')
        )
        output = output.sort_values(['Settimana', '_date_sort', 'Fascia Oraria'])
        output = output.drop(columns=['_date_sort'])

        safe_name = lab_name.replace('/', '-').replace(' ', '_')
        output_path = output_dir / "laboratori" / f"Lab_{lab_id}_{safe_name}.csv"
        output.to_csv(output_path, index=False)
        print(f"  ✓ Lab {lab_id} ({lab_name}): {len(output)} incontri fisici")

    # 4. Vista giornaliera (collassa accorpamenti)
    print("\n4. Generating daily calendar view...")

    # Group by slot to collapse groupings
    daily_records = []

    # Create unique meeting identifier
    df['slot_key'] = df.apply(
        lambda r: (r['settimana'], r['giorno_num'], r['fascia_num'],
                   r['laboratorio_id'], r['formatrice_id']),
        axis=1
    )

    # Group by slot_key
    for slot_key, group in df.groupby('slot_key'):
        settimana, giorno_num, fascia_num, lab_id, trainer_id = slot_key

        # Get common info
        row = group.iloc[0]

        # Collect all classes (sorted)
        classes = sorted(group['classe_nome'].unique())
        classes_str = ", ".join(classes)

        # Collect schools (should be same for grouped classes)
        schools = group['scuola_nome'].unique()
        school_str = schools[0] if len(schools) == 1 else ", ".join(schools)

        # Check if grouped
        is_grouped = len(classes) > 1

        daily_records.append({
            'Settimana': settimana,
            'Giorno': row['giorno_nome'],
            'Fascia Oraria': row['fascia_nome'],
            'Data e Ora': row['data_ora'],
            'Classi': classes_str,
            'N. Classi': len(classes),
            'Scuola': school_str,
            'Laboratorio': row['laboratorio_nome'],
            'Formatrice': row['formatrice_nome'],
            'Accorpamento': 'Sì' if is_grouped else 'No'
        })

    daily_df = pd.DataFrame(daily_records)
    # Add date column for proper sorting
    daily_df['_date_sort'] = daily_df['Data e Ora'].apply(
        lambda x: datetime.strptime(x.split()[0], '%d/%m/%Y')
    )
    daily_df = daily_df.sort_values(['Settimana', '_date_sort', 'Fascia Oraria'])
    daily_df = daily_df.drop(columns=['_date_sort'])

    output_path = output_dir / "calendario_giornaliero.csv"
    daily_df.to_csv(output_path, index=False)
    print(f"  ✓ Calendario giornaliero: {len(daily_df)} slot unici")

    # Statistics
    grouped_count = daily_df[daily_df['Accorpamento'] == 'Sì'].shape[0]
    print(f"    - Incontri singoli: {len(daily_df) - grouped_count}")
    print(f"    - Incontri accorpati: {grouped_count}")

    print(f"\n✅ All views generated in: {output_dir}")
    print(f"   - {len(df['classe_id'].unique())} class calendars")
    print(f"   - {len(df['formatrice_id'].unique())} trainer calendars")
    print(f"   - {len(df['laboratorio_id'].unique())} lab calendars")
    print(f"   - 1 daily calendar with {len(daily_df)} unique meetings")


if __name__ == '__main__':
    main()
