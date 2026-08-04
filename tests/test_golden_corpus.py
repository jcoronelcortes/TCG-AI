"""Golden corpus test: no historical decision changes unintentionally.

It replays ALL the local records through `main.agent()` and compares
against the snapshot `registros/decisiones_dorado.json`.

Policy:
  - No records (a fresh clone) -> skip.
  - No snapshot -> it is created (bootstrap) and skipped; the next run compares.
  - REPLACED/new/deleted records (a different md5): there is nothing valid
    to compare in those files -> the snapshot self-heals silently
    (they are transient local data from split_turns.py), as long as there are no
    flips in the untouched records.
  - FLIPS (the same record, a different decision) -> FAILURE with the exact diff:
    a change to main.py flipped historical decisions. If the change is
    intended, accept it consciously with:
        python tests/golden_corpus.py --actualizar
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import golden_corpus as gc


def test_golden_corpus_has_no_flips():
    if not gc.record_files():
        pytest.skip("no hay registros locales que reproducir")

    actual = gc.build_corpus()
    dorado = gc.load_snapshot()

    if dorado is None:
        gc.save_snapshot(actual)
        pytest.skip(
            "snapshot dorado creado (bootstrap); la proxima corrida compara")

    cambiados, faltantes, nuevos, flips = gc.comparar(dorado, actual)

    assert not flips, (
        "DECISIONES HISTORICAS VOLTEADAS con los mismos registros (un cambio "
        "de codigo altero decisiones que antes eran otras). Revisa cada flip; "
        "si es buscado, acepta con `python tests/golden_corpus.py "
        "--actualizar`:\n" + gc.formatear_flips(flips))

    if cambiados or faltantes or nuevos:
        # Local data replaced: with no comparison possible, re-snapshot.
        gc.save_snapshot(actual)
