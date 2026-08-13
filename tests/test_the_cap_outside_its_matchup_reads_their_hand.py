"""Outside Alakazam the cap was a fixed 60, and 60 asks nothing.

In the DISCARD ladder, Xerosic's Machinations was priced `5` against Alakazam --
the card that answers Powerful Hand, protected like the Meganium line -- and a
flat `60` against everything else. Sixty with their hand at twelve, sixty with
their hand at four.

The PLAY scorer has never agreed. `_RULES_XEROSIC_PLAY.generic_very_big_hand`
gives the same card `XEROSIC_SCORE_GENERIC` (3380) once their hand reaches
`XEROSIC_BIG_HAND`, and `XEROSIC_SCORE_LAST_RESORT` (20) below it. So the two
scorers of one card contradicted each other in both directions: with their hand
at twelve the cap was middling fodder, and with their hand at four it was kept
just the same. That is the doctrine the Supporter block already applies to the
other four -- the card we KEEP and the card we would PLAY cannot disagree.

The reading is asked SECOND and only SUBTRACTS: the 60 is still what answers on
a thin hand, the Alakazam branch is untouched, and the threshold is the play
rule's own constant so the two cannot drift apart.

WHAT IT WAS MEASURED WITH, and what that measurement is allowed to claim.
`utils/gate_the_cap_reads_their_hand.py --census` replays the frozen corpus
through both arms: ONE decision of 3 580 changes (0.03%). That is the ceiling of
any winrate effect, and it is two orders of magnitude below what self-play can
resolve -- so no games were played, and none should be. The defence of this rule
is the corpus flip below and the contradiction it removes, never a winrate.

THE FLIP, reviewed rather than waved through. `registro_029_crustle_wall_9`
turn 6, the cost of our own Ultra Ball, two cards to pay:

    Meowth ex 82   Boss's Orders 36   Night Stretcher 30   Xerosic 22   Lillie's 2

The baseline paid with the Meowth ex and the Xerosic (60). It now pays with the
Meowth ex and the Boss's Orders -- and the Boss's is sitting at 36, which is
`DISCARD_SUPPORTER_DEAD_DROP`: `_supp_values` had already priced that gust as
worth NOTHING on this board. Keeping a gust the play scorer calls dead over a
cap it prices at 3380 is the same self-contradiction 5040fa9 removed from the
other half of the Ultra Ball.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import golden_corpus as gc
import selfplay as sp
from duplicate_protection_audit import instrumentar
from gate_the_cap_reads_their_hand import neutralise

REGISTRO = "registro_029_crustle_wall_9"
TURNO, ACCION = 6, 14


@pytest.fixture(scope="module")
def agente():
    return sp.load_agent(ROOT / "main.py", "cap_lee_su_mano")


def _menus(agent, prefijo):
    """Every DISCARD menu of one frozen record, with the ladder's own scores."""
    records = gc.frozen_records()
    nombre = next((n for n in records if n.startswith(prefijo)), None)
    if nombre is None:
        pytest.skip(f"el bundle congelado no trae {prefijo}")
    capturas = []
    restaurar = instrumentar(agent, capturas)
    try:
        gc.replay_data(agent, records[nombre])
    finally:
        restaurar()
    return [c for c in capturas if c.opciones]


def _menu_del_flip(agent):
    for captura in _menus(agent, REGISTRO):
        if captura.turno == TURNO and captura.accion == ACCION:
            return captura
    pytest.skip(f"{REGISTRO} turno {TURNO} accion {ACCION} no esta en el bundle")


# ---------------------------------------------------------------------------
# 1. One threshold, two scorers
# ---------------------------------------------------------------------------

def test_los_dos_puntuadores_comparten_el_mismo_umbral(agente):
    """The number that decides whether to PLAY the cap is the number that
    decides whether to KEEP it. Two literals would drift apart on the first day
    somebody tuned one of them."""
    card = agente.score_option.__globals__['card']
    from ptcg.cards import ids
    from ptcg.decision import disruption

    assert card.XEROSIC_BIG_HAND == ids.XEROSIC_BIG_HAND == 7
    assert disruption.XEROSIC_BIG_HAND is ids.XEROSIC_BIG_HAND


def test_la_lectura_solo_puede_BAJAR_el_precio(agente):
    """A second question that could raise the score would be a new rule, not a
    reading: 60 is what still answers on a thin hand."""
    from ptcg.cards import ids

    assert ids.DISCARD_XEROSIC_CAPS_A_FAT_HAND < 60
    # And not into the strongest band either: 2 is reserved for the best live
    # Supporter in hand, and a generic cap is not that.
    assert ids.DISCARD_XEROSIC_CAPS_A_FAT_HAND > ids.DISCARD_SUPPORTER_LIVE_KEEP


# ---------------------------------------------------------------------------
# 2. The board the rule was written on
# ---------------------------------------------------------------------------

def test_el_cap_queda_protegido_en_el_tablero_del_flip(agente):
    captura = _menu_del_flip(agente)
    scores = {nombre: score for _, nombre, score in captura.opciones}
    cap = next(n for n in scores if n.startswith("Xerosic"))
    from ptcg.cards import ids
    assert scores[cap] == ids.DISCARD_XEROSIC_CAPS_A_FAT_HAND


def test_el_gusteo_que_ya_estaba_muerto_es_el_que_paga(agente):
    """36 is `DISCARD_SUPPORTER_DEAD_DROP`: `_supp_values` had already priced
    that gust at nothing. It is the card that should fall."""
    captura = _menu_del_flip(agente)
    scores = {nombre: score for _, nombre, score in captura.opciones}
    from ptcg.cards import ids
    boss = next(n for n in scores if n.startswith("Boss"))
    cap = next(n for n in scores if n.startswith("Xerosic"))
    assert scores[boss] == ids.DISCARD_SUPPORTER_DEAD_DROP
    assert scores[boss] > scores[cap], (
        "the dead gust has to fall before the cap the play scorer prices at 3380")


def test_es_el_coste_de_una_busqueda_NUESTRA_no_un_descarte_forzado(agente):
    """The horizon matters to the reading, so the record has to be the one the
    rule was written on and not its mirror image."""
    assert _menu_del_flip(agente).forzado is False


# ---------------------------------------------------------------------------
# 3. Both directions: switch the reading off and the old price comes back
# ---------------------------------------------------------------------------

def test_sin_la_regla_el_cap_vuelve_a_valer_sesenta():
    """The sensitivity half. With the threshold out of reach of any hand the
    branch behaves exactly as it did, which is also what the gate's baseline arm
    measures against."""
    base = neutralise(sp.load_agent(ROOT / "main.py", "cap_sin_regla"))
    captura = _menu_del_flip(base)
    scores = {nombre: score for _, nombre, score in captura.opciones}
    cap = next(n for n in scores if n.startswith("Xerosic"))
    assert scores[cap] == 60


def test_la_rama_alakazam_no_se_toca(agente):
    """The matchup the card exists for was already measured and pinned
    (`tests/test_their_discard_does_not_eat_our_cap.py`). This reading must not
    have moved it: against Alakazam the cap is priced by its OWN branch, fat
    hand or not, and never by the generic one.

    THE BRANCH HAS TWO RUNGS SINCE registro_009 (see
    `DISCARD_XEROSIC_CAP_IS_THE_ANSWER`): the ordinary 5, and 1 when the copy in
    hand is the last access to the cap -- there the discard pile is one way and
    the cap is kept before any other Supporter. What this test is about is
    WHICH branch answers, so it asserts the band and not one number: both rungs
    are the matchup's, and the generic prices (22 and 60) are the failure it
    watches for.
    """
    from ptcg.cards import ids
    banda = {5, ids.DISCARD_XEROSIC_CAP_IS_THE_ANSWER}
    vistos = set()
    for captura in _menus(agente, "registro_001_alakazam"):
        for _, nombre, score in captura.opciones:
            if nombre.startswith("Xerosic"):
                vistos.add(score)
    if not vistos:
        pytest.skip("ese registro no trae ningun menu con el cap en la mano")
    assert vistos <= banda, f"la rama Alakazam cambio de precio: {sorted(vistos)}"
    assert not (vistos & {ids.DISCARD_XEROSIC_CAPS_A_FAT_HAND, 60})
