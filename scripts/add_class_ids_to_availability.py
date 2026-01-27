#!/usr/bin/env python3
"""
Script per modificare l'header di class_availability.csv aggiungendo
gli ID classe e scuola nel formato: classe_id-scuola_id-nome
"""

import csv

def read_class_mapping():
    """Legge il mapping nome -> (classe_id, scuola_id)."""
    mapping = {}
    class_order = []

    with open('data/input/classi.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            classe_id = row['classe_id']
            scuola_id = row['scuola_id']
            nome = row['nome']

            # Per gestire i duplicati, usiamo una lista
            if nome not in mapping:
                mapping[nome] = []
            mapping[nome].append((classe_id, scuola_id))
            class_order.append((classe_id, scuola_id, nome))

    return mapping, class_order


def update_availability_header():
    """Aggiorna l'header del file class_availability.csv."""
    mapping, class_order = read_class_mapping()

    # Leggi tutto il file
    rows = []
    with open('data/output/class_availability.csv', 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("File vuoto!")
        return

    # Prima riga = header
    old_header = rows[0]
    print(f"Vecchio header: {len(old_header)} colonne")
    print(f"Ordine classi: {len(class_order)} classi")

    # Costruisci il nuovo header
    new_header = ['slot_id']  # Prima colonna rimane invariata

    # Per ogni colonna (esclusa slot_id)
    for i, col_name in enumerate(old_header[1:], start=1):
        # Trova la classe corrispondente nell'ordine
        if i-1 < len(class_order):
            classe_id, scuola_id, nome = class_order[i-1]
            new_col_name = f"{classe_id}-{scuola_id}-{nome}"
            new_header.append(new_col_name)

            if nome != col_name:
                print(f"⚠️  Colonna {i}: '{col_name}' -> '{new_col_name}' (nome diverso!)")
        else:
            print(f"⚠️  Colonna {i}: '{col_name}' non trovata nell'ordine classi")
            new_header.append(col_name)

    # Sostituisci l'header
    rows[0] = new_header

    # Scrivi il file aggiornato
    with open('data/output/class_availability.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"\n✅ File aggiornato con {len(new_header)} colonne")
    print(f"Esempi nuove colonne: {new_header[1:6]}")


if __name__ == '__main__':
    update_availability_header()
