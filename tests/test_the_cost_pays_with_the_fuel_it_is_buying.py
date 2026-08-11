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
on the frozen corpus it drops an energy ahead of an evolution the agent itself
calls orphaned. This file pins the comparison, which is the part that can
quietly be wrong -- the orphan reading comes from the agent's own
`_evo_link_state` and the scores from its own ladder, so the only thing this
tool invents is the `>`.

AND THE `>` WAS NOT THE ONLY THING IT INVENTED. Its first run reported TWELVE
inversions and that number went into the project's memory as a 10.2 %
population. FIVE of the twelve were the ladder being right, and the audit could
not see it because `_evo_link_state` is the COARSE reading -- "pre-evolution
neither in play nor in hand" -- while the ladder also asks whether the missing
link is one step away:

  * `registro_031` t4/t6, `registro_045` t2, `registro_007` t3: an **Applin on
    the bench**, the Dipplin still in the deck. The Hydrapple ex in hand has no
    pre-evolution, so it is an orphan by the coarse reading, and the ladder
    scores it 3 because the line is one link from complete;
  * `registro_037` t4: a **Chikorita in play**, the Bayleef in the deck, our own
    Ultra Ball paying. That is verbatim the board `DISCARD_LINK_THE_SEARCH_BUYS`
    was written for.

`lectura_de_eslabon` asks the agent that finer question with the agent's own
`_evo_top_unlocked_by_the_search`, and `clasificar` splits the report in two.
The rescued rows are PRINTED, not dropped: a tool that silently shrinks its own
finding reads as "there was less" when it means "we looked better".

    SEVEN of 118 menus (5.9 %), not twelve (10.2 %)

That is the fifth detector in this repository to report its own reading as a
defect of the agent, and the reason every one of them carries two halves.

It measures. It does not fix: re-ordering the ladder touches every forced
discard, not just the Ultra Ball cost, and it is a policy change with its own
record, census and gate.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from duplicate_protection_audit import Captura
from fodder_ladder_audit import clasificar, contradicciones

GRASS, MEGANIUM, BAYLEEF, CHIKORITA = 1, 710, 709, 93
HYDRAPPLE = 150


def _menu(opciones, huerfanas=(), forzado=False, a_un_eslabon=None):
    extra = None if a_un_eslabon is None else {
        "a_un_eslabon": frozenset(a_un_eslabon)}
    captura = Captura("registro_de_prueba", 2, 15, forzado, huerfanas, extra)
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


# ---------------------------------------------------------------------------
# The finer reading: half of the first number was this tool, not the agent
# ---------------------------------------------------------------------------

def test_la_pieza_a_un_eslabon_no_cuenta_como_carta_muerta():
    """`registro_031` in one menu: an Applin on the bench, the Dipplin in the
    deck, and a Hydrapple ex in hand that the coarse reading calls an orphan.
    The ladder scores it 3 because the line is one link from complete, and that
    is not the agent throwing fuel away to keep cardboard."""
    menu = _menu([(GRASS, "Basic {G} Energy", 85),
                  (HYDRAPPLE, "Hydrapple ex", 3)],
                 huerfanas=[HYDRAPPLE], a_un_eslabon=[HYDRAPPLE])
    muertas, vivas, _ = clasificar(menu, GRASS)
    assert muertas == []
    assert [v[1] for v in vivas] == [HYDRAPPLE]


def test_la_misma_mano_sin_el_eslabon_SI_es_la_inversion():
    """The control, and the only difference between the two boards: take the
    Applin off the bench and the same pair is the worklist again."""
    menu = _menu([(GRASS, "Basic {G} Energy", 85),
                  (HYDRAPPLE, "Hydrapple ex", 3)],
                 huerfanas=[HYDRAPPLE], a_un_eslabon=[])
    muertas, vivas, _ = clasificar(menu, GRASS)
    assert [mu[1] for mu in muertas] == [HYDRAPPLE]
    assert vivas == []


def test_una_huerfana_rescatada_no_tapa_a_la_otra():
    """Two orphans in one hand, one of them one link away. The report has to
    keep the dead one: this is where a rescue could quietly swallow a finding."""
    menu = _menu([(GRASS, "Basic {G} Energy", 85),
                  (HYDRAPPLE, "Hydrapple ex", 3),
                  (MEGANIUM, "Meganium", 40)],
                 huerfanas=[HYDRAPPLE, MEGANIUM], a_un_eslabon=[HYDRAPPLE])
    muertas, vivas, _ = clasificar(menu, GRASS)
    assert [mu[1] for mu in muertas] == [MEGANIUM]
    assert [v[1] for v in vivas] == [HYDRAPPLE]


def test_sin_la_lectura_el_informe_da_el_numero_VIEJO_no_uno_menor():
    """A capture taken without the hook has nothing to split on. It must fall
    back to the coarse answer -- the bigger one -- because an audit whose
    instrumentation silently failed would otherwise report a smaller number and
    read as progress."""
    menu = _menu([(GRASS, "Basic {G} Energy", 85),
                  (HYDRAPPLE, "Hydrapple ex", 3)],
                 huerfanas=[HYDRAPPLE])          # no `a_un_eslabon` at all
    muertas, vivas, _ = clasificar(menu, GRASS)
    assert [mu[1] for mu in muertas] == [HYDRAPPLE]
    assert vivas == []


def test_el_rescate_no_puede_inventar_una_huerfana():
    """It may only narrow the orphan set. A card the agent never called an
    orphan is not compared at all, so naming it here changes nothing -- and the
    audit's own auto-test fails if the reading ever widens the set."""
    menu = _menu([(GRASS, "Basic {G} Energy", 85),
                  (MEGANIUM, "Meganium", 40)],
                 huerfanas=[MEGANIUM], a_un_eslabon=[BAYLEEF])
    muertas, vivas, _ = clasificar(menu, GRASS)
    assert [mu[1] for mu in muertas] == [MEGANIUM]
    assert vivas == []
