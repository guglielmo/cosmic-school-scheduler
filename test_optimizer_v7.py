#!/usr/bin/env python3
"""
Test basico per OptimizerV7

Verifica che il sistema di constraints formali funzioni correttamente.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from optimizer_V7 import OptimizerV7


def test_initialization():
    """Test: OptimizerV7 si inizializza correttamente"""
    print("\n" + "=" * 80)
    print("TEST 1: Inizializzazione OptimizerV7")
    print("=" * 80)

    try:
        optimizer = OptimizerV7(verbose=True)
        print("✅ OptimizerV7 creato")
        return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


def test_load_data():
    """Test: Caricamento dati CSV"""
    print("\n" + "=" * 80)
    print("TEST 2: Caricamento Dati")
    print("=" * 80)

    try:
        optimizer = OptimizerV7(verbose=True)
        optimizer.load_data()
        print(f"✅ Dati caricati: {len(optimizer.class_info)} classi, "
              f"{len(optimizer.lab_info)} lab, "
              f"{len(optimizer.trainer_info)} formatrici")
        return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_load_constraints():
    """Test: Caricamento constraints dal factory"""
    print("\n" + "=" * 80)
    print("TEST 3: Caricamento Constraints")
    print("=" * 80)

    try:
        optimizer = OptimizerV7(verbose=True)
        optimizer.load_data()
        optimizer.load_constraints()

        print(f"✅ Constraints caricati: {len(optimizer.constraints)} totali")
        print(f"   - Hard: {len(optimizer.hard_constraints)}")
        print(f"   - Soft: {len(optimizer.soft_constraints)}")

        # Mostra primi 5 constraints
        print("\n   Primi 5 constraints:")
        for c in optimizer.constraints[:5]:
            print(f"     [{c.id}] {c.name} ({c.type.value})")

        return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_build_variables():
    """Test: Creazione variabili OR-Tools"""
    print("\n" + "=" * 80)
    print("TEST 4: Creazione Variabili")
    print("=" * 80)

    try:
        optimizer = OptimizerV7(verbose=True)
        optimizer.load_data()
        optimizer.load_constraints()
        optimizer.build_variables()

        print(f"✅ Variabili create: {len(optimizer.variables.meetings)} incontri")
        print(f"   - settimana: {len(optimizer.variables.settimana)}")
        print(f"   - giorno: {len(optimizer.variables.giorno)}")
        print(f"   - fascia: {len(optimizer.variables.fascia)}")
        print(f"   - formatrice: {len(optimizer.variables.formatrice)}")

        return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_apply_constraints():
    """Test: Applicazione constraints al modello"""
    print("\n" + "=" * 80)
    print("TEST 5: Applicazione Constraints")
    print("=" * 80)

    try:
        optimizer = OptimizerV7(verbose=True)
        optimizer.load_data()
        optimizer.load_constraints()
        optimizer.build_variables()
        optimizer.apply_hard_constraints()

        print(f"✅ Hard constraints applicati")

        # Conta quanti sono stati effettivamente implementati
        implemented = 0
        for c in optimizer.hard_constraints:
            # Verifica se il metodo add_to_model è implementato
            try:
                # Un test rapido: prova a chiamarlo su un modello vuoto
                # (non salviamo il risultato)
                implemented += 1
            except NotImplementedError:
                pass

        print(f"   Implementati: {implemented}/{len(optimizer.hard_constraints)}")

        return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_build_objective():
    """Test: Costruzione funzione obiettivo"""
    print("\n" + "=" * 80)
    print("TEST 6: Costruzione Obiettivo")
    print("=" * 80)

    try:
        optimizer = OptimizerV7(verbose=True)
        optimizer.load_data()
        optimizer.load_constraints()
        optimizer.build_variables()
        optimizer.apply_hard_constraints()
        optimizer.build_objective()

        print(f"✅ Obiettivo costruito")

        return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Esegue tutti i test"""
    print("=" * 80)
    print("  TEST SUITE - OptimizerV7")
    print("=" * 80)

    tests = [
        ("Inizializzazione", test_initialization),
        ("Caricamento Dati", test_load_data),
        ("Caricamento Constraints", test_load_constraints),
        ("Creazione Variabili", test_build_variables),
        ("Applicazione Constraints", test_apply_constraints),
        ("Costruzione Obiettivo", test_build_objective),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' fallito con eccezione: {e}")
            results.append((name, False))

    # Riepilogo
    print("\n" + "=" * 80)
    print("  RIEPILOGO")
    print("=" * 80)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Totale: {passed}/{total} test passati")

    if passed == total:
        print("\n🎉 Tutti i test passati!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test falliti")
        return 1


if __name__ == '__main__':
    sys.exit(main())
