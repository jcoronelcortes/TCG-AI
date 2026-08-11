"""Two copies of one card, one role: only one of them can be the reason.

A discard menu prices cards one at a time, so a protection written as "this is
our only out" is handed to EVERY copy of it in the hand. The protection is about
the ROLE, and only one card can play the role. It has cost this project twice in
one week -- the counter-stadium whose guard switched off at two copies
(ab1945a), and the corpus flip Wave 1 left standing, where a second Meowth ex
outranks a live Night Stretcher (6f98a9b).

`utils/duplicate_protection_audit.py` reads it off all 3 580 frozen decisions
instead of one board. This file pins the reading -- which is where a report of
this shape goes wrong, not in the capture.

WHAT IT FOUND ON ITS FIRST RUN, and the reason the reading has to be exact:
fourteen duplicate pairs share a keep-band score, and the biggest group is
`Lillie's Determination`, in four different records. The ladder DOES latch it
(`_lillie_protected_once`: protect one at 2, release the spare at 72) -- and
sixty lines further down a card-agnostic block re-protects the spare with
`score = min(score, DISCARD_SUPPORTER_LIVE_KEEP)`, which is 2, because "the best
Supporter I could still play" is just as true of the second copy as of the
first. The latch fires and the general rule undoes it. That is the same
duplicate-pricing shape one level deeper, and it is what a per-board reading
could not have shown.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from duplicate_protection_audit import UMBRAL_FORRAJE, Captura


def _menu(*opciones, forzado=False):
    captura = Captura("registro_de_prueba", 5, 3, forzado)
    for card_id, nombre, score in opciones:
        captura.opciones.append((card_id, nombre, score))
    return captura


def test_una_sola_copia_no_es_un_par():
    menu = _menu((1, "Lillie's", 2), (2, "Meganium", 40))
    assert menu.duplicados == {}


def test_dos_copias_con_el_mismo_score_son_el_hallazgo():
    menu = _menu((1, "Lillie's", 2), (2, "Hydrapple ex", 12), (1, "Lillie's", 2))
    assert menu.duplicados == {1: [2, 2]}


def test_dos_copias_con_scores_DISTINTOS_son_el_latch_funcionando():
    # What the repair looks like from outside: one protected, the spare released.
    # The audit still reports the pair as a duplicate, and the report is what
    # filters it -- `len(set(scores)) == 1` is the finding, not `len(scores) > 1`.
    menu = _menu((1, "Lillie's", 2), (1, "Lillie's", 72))
    assert menu.duplicados == {1: [2, 72]}
    assert len(set(menu.duplicados[1])) > 1


def test_el_par_que_empata_como_forraje_no_es_el_defecto():
    # In this menu HIGHER means discarded sooner. Two copies both heading for the
    # pile agree honestly: neither is protecting anything, so nobody is claiming
    # a role twice. The threshold is what separates the two readings.
    menu = _menu((3, "Basic {G} Energy", 80), (3, "Basic {G} Energy", 80))
    score = menu.duplicados[3][0]
    assert score > UMBRAL_FORRAJE


def test_el_par_que_empata_GUARDANDO_si_lo_es():
    menu = _menu((4, "Meowth ex", 2), (4, "Meowth ex", 2))
    assert menu.duplicados[4][0] <= UMBRAL_FORRAJE


def test_tres_copias_cuentan_como_un_solo_par():
    # `registro_028` holds three Lillie's. One finding, not three: the defect is
    # the shared role, and it is shared once however many copies share it.
    menu = _menu((1, "Lillie's", 2), (1, "Lillie's", 2), (1, "Lillie's", 2))
    assert list(menu.duplicados) == [1]
    assert len(menu.duplicados[1]) == 3


def test_el_menu_sabe_de_quien_es_el_turno():
    # The horizon matters to the reading: a forced discard happens on THEIR turn
    # and an Ultra Ball cost on ours, and a finding that cannot say which is a
    # finding nobody can act on (93a27eb).
    assert _menu((1, "x", 2), forzado=True).forzado is True
    assert _menu((1, "x", 2)).forzado is False


def test_el_nombre_sobrevive_al_informe():
    menu = _menu((7, "Unfair Stamp", -10000), (7, "Unfair Stamp", -10000))
    assert menu.nombre_de(7) == "Unfair Stamp"
    assert menu.nombre_de(999) == "999"
