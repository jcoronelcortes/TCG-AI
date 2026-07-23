"""Test del corpus dorado: ninguna decision historica cambia sin quererlo.

Reproduce TODOS los registros locales a traves de `main.agent()` y compara
contra el snapshot `registros/decisiones_dorado.json`.

Politica:
  - Sin registros (clon fresco) -> skip.
  - Sin snapshot -> se crea (bootstrap) y skip; la proxima corrida compara.
  - Registros REEMPLAZADOS/nuevos/borrados (md5 distinto): no hay nada valido
    que comparar en esos archivos -> el snapshot se auto-cura silenciosamente
    (son datos locales transitorios de split_turns.py), siempre que no haya
    flips en los registros intactos.
  - FLIPS (mismo registro, decision distinta) -> FALLO con el diff exacto:
    un cambio de main.py volteo decisiones historicas. Si el cambio es
    buscado, aceptalo conscientemente con:
        python tests/golden_corpus.py --actualizar
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import golden_corpus as gc


def test_corpus_dorado_sin_flips():
    if not gc.archivos_registro():
        pytest.skip("no hay registros locales que reproducir")

    actual = gc.generar_corpus()
    dorado = gc.cargar_snapshot()

    if dorado is None:
        gc.guardar_snapshot(actual)
        pytest.skip(
            "snapshot dorado creado (bootstrap); la proxima corrida compara")

    cambiados, faltantes, nuevos, flips = gc.comparar(dorado, actual)

    assert not flips, (
        "DECISIONES HISTORICAS VOLTEADAS con los mismos registros (un cambio "
        "de codigo altero decisiones que antes eran otras). Revisa cada flip; "
        "si es buscado, acepta con `python tests/golden_corpus.py "
        "--actualizar`:\n" + gc.formatear_flips(flips))

    if cambiados or faltantes or nuevos:
        # Datos locales reemplazados: sin comparacion posible, re-snapshot.
        gc.guardar_snapshot(actual)
