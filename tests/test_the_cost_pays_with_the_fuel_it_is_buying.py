"""What makes energy cheap is the quantity, not the access.

`registro_002` step 15 (episode 91529732, turn 2 vs Cynthia's Garchomp ex,
LOST). The hand was {Bayleef 50, Grass 80, Meganium 40, Hydrapple ex 3,
Grass 80} and the cost of an Ultra Ball took BOTH Grass -- highest score falls
first -- to buy a Teal Mask Ogerpon ex whose only route to doing anything is
Teal Dance: attach a Grass FROM HAND and draw. It kept a Bayleef and a Meganium
that could not enter play for two turns, with no Chikorita in play and none in
hand.

The ladder prices energy as the cheapest fodder because there are twelve in the
deck. But the quantity is not the ACCESS: with no Lillie's and no Night
Stretcher there is no way to touch another one this turn or the next, while an
orphaned evolution is a genuinely dead card. `_ub_real_fodder` already counts
that Bayleef and that Meganium as real fodder, so the two modules disagree.

`utils/fodder_ladder_audit.py` measures the disagreement instead of arguing it:
on the frozen corpus, TWELVE of 118 discard menus drop an energy ahead of an
evolution the agent itself calls orphaned. This file pins the comparison, which
is the part that can quietly be wrong -- the orphan reading comes from the
agent's own `_evo_link_state` and the scores from its own ladder, so the only
thing this tool invents is the `>`.

It measures. It does not fix: re-ordering the ladder touches every forced
discard, not just the Ultra Ball cost, and 10 % of menus is a policy change with
its own record, census and gate.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from duplicate_protection_audit import Captura
from fodder_ladder_audit import contradicciones

GRASS, MEGANIUM, BAYLEEF, CHIKORITA = 1, 710, 709, 93


def _menu(opciones, huerfanas=(), forzado=False):
    captura = Captura("registro_de_prueba", 2, 15, forzado, huerfanas)
    for card_id, nombre, score in opciones:
        captura.opciones.append((card_id, nombre, score))
    return captura


def test_la_energia_que_cae_antes_que_la_carta_muerta_es_la_inversion():
    # The record's own shape: the energy at 80 falls before a Meganium at 40
    # that cannot be played for two turns.
    menu = _menu([(GRASS, "Basic {G} Energy", 80), (MEGANIUM, "Meganium", 40)],
                 huerfanas=[MEGANIUM])
    inversiones, energias = contradicciones(menu, GRASS)
    assert energias == 1
    assert inversiones == [(80, MEGANIUM, "Meganium", 40)]


def test_si_la_evolucion_cae_primero_no_hay_nada_que_decir():
    menu = _menu([(GRASS, "Basic {G} Energy", 40), (MEGANIUM, "Meganium", 80)],
                 huerfanas=[MEGANIUM])
    assert contradicciones(menu, GRASS)[0] == []


def test_el_empate_no_es_una_inversion():
    # Strictly higher, because equal scores are the ladder saying the two are
    # interchangeable and that claim is not what this audit is about.
    menu = _menu([(GRASS, "Basic {G} Energy", 40), (MEGANIUM, "Meganium", 40)],
                 huerfanas=[MEGANIUM])
    assert contradicciones(menu, GRASS)[0] == []


def test_una_evolucion_CON_su_pre_evolucion_no_es_huerfana():
    # The whole point of asking the agent rather than guessing: a Meganium with
    # a Bayleef under it is a card that plays this turn, and dropping the energy
    # ahead of it can be perfectly correct.
    menu = _menu([(GRASS, "Basic {G} Energy", 80), (MEGANIUM, "Meganium", 40)],
                 huerfanas=[])
    assert contradicciones(menu, GRASS)[0] == []


def test_cada_copia_de_energia_cuenta_como_su_propio_par():
    # Three Grass over one dead Meganium is ONE inversion seen three times; the
    # report collapses them and this is where the three come from.
    menu = _menu([(GRASS, "Basic {G} Energy", 80),
                  (GRASS, "Basic {G} Energy", 80),
                  (GRASS, "Basic {G} Energy", 80),
                  (MEGANIUM, "Meganium", 40)],
                 huerfanas=[MEGANIUM])
    inversiones, energias = contradicciones(menu, GRASS)
    assert energias == 3
    assert len(inversiones) == 3
    assert {i[1] for i in inversiones} == {MEGANIUM}


def test_la_ultima_energia_de_la_mano_es_el_caso_que_importa():
    # `energias` is reported next to every row precisely because the argument is
    # about access: dropping one of five is not the event, dropping the last one
    # is.
    menu = _menu([(GRASS, "Basic {G} Energy", 45), (MEGANIUM, "Meganium", 40)],
                 huerfanas=[MEGANIUM])
    _, energias = contradicciones(menu, GRASS)
    assert energias == 1


def test_la_energia_no_se_compara_consigo_misma():
    # A Basic Energy is not an evolution, so even if it somehow appeared in the
    # orphan set it cannot be its own dead card.
    menu = _menu([(GRASS, "Basic {G} Energy", 80), (GRASS, "Basic {G} Energy", 40)],
                 huerfanas=[GRASS])
    assert contradicciones(menu, GRASS)[0] == []


def test_varias_huerfanas_en_la_misma_mano_se_reportan_todas():
    menu = _menu([(GRASS, "Basic {G} Energy", 85),
                  (MEGANIUM, "Meganium", 40),
                  (BAYLEEF, "Bayleef", 75)],
                 huerfanas=[MEGANIUM, BAYLEEF])
    inversiones, _ = contradicciones(menu, GRASS)
    assert {i[1] for i in inversiones} == {MEGANIUM, BAYLEEF}
