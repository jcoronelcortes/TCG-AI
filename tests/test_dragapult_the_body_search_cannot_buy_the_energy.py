"""The SECOND board of the same sentence, and the one that says what it means.

Scenario (`records/registro_005_pasos_035_hasta_044.json`, step 35, turn 5,
episode 93224301 vs **Dragapult** -- WON in spite of this):

    US (6 prizes)                            RIVAL (6 prizes)
    active  Hydrapple ex 330/330, **0 e**    active  Fezandipiti ex 210
    bench   Bayleef 110, 0 e                 bench   Drakloak, Dreepy x2,
            Teal Mask Ogerpon ex, **1 {G}**          Munkidori
            Teal Mask Ogerpon ex, **1 {G}**  stadium Forest of Vitality (ours)
    hand    ULTRA BALL, Forest of Vitality (dead, ours is already in play), DAWN

        [0] ULTRA BALL
        [1] DAWN     <-- played
        [2] END

WHY THIS BOARD AND NOT THE FIRST ONE. `test_the_body_search_cannot_buy_the_energy`
pins step 116 of episode 93210930, where there was not one energy anywhere.
Read alone it invites the wrong sentence -- "the rule is for empty boards" --
and the rule does not say that. **Here there are two energies on the table** and
the turn is blocked all the same:

    Hydrapple ex needs 2 and has 0 · Teal Mask Ogerpon ex needs 3 and has 1
    no Basic {G} in hand, so no attachment can move any of those numbers
    Teal Dance and Ripening Charge both take their Grass FROM HAND

What decides is `_a_body_can_attack_this_turn`, not a count of energies. And the
opponent is a different archetype from the board the rule was written on, which
is the other half of "deck-agnostic": the first board proves it by construction,
this one proves it in fact.

What the recorded Dawn bought: an Applin, a Bayleef and a Meganium; the Meganium
went down, the Applin was benched, and the turn ended with **nothing attached,
nothing attacked and two cards in hand**. What the Ultra Ball beside it opens:
Meowth ex -> *Last-Ditch Catch* -> Lillie's Determination -- and at SIX prizes
that Supporter draws **eight** cards, not six.

Measured (`utils/turn_yield_the_body_search_cannot_buy_the_energy.py`, 50
determinised worlds per arm, the agent finishing the turn in both):

    con la lectura   1.72 premios   +3.06 energias   mano 6.88   ataco 94 %
    sin ella         0.00 premios   +0.00 energias   mano 1.84   ataco  0 %
    43/50 mundos con MAS premios, 0/50 con menos

The winrate oracle is blind on this board and says so: both arms win 100/100
because the position is already won.
"""

import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402

import ptcg.decision.ultra_ball as ub_mod  # noqa: E402
from ptcg.cards.groups import POKEMON_SEARCH_SUPPORTER_IDS  # noqa: E402
from ptcg.cards.ids import GRASS_DIGGER_REACH  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "dragapult_the_body_search_cannot_buy_the_energy_step35.json")

DAWN = m.Dawn
ULTRA_BALL = m.Ultra_Ball
MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
FOREST = m.Forest_of_Vitality
GRASS = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)
    yield
    reset_agent(m)


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _play_idx(obs, card_id):
    cur = obs["current"]
    mano = cur["players"][cur["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and mano[o["index"]]["id"] == card_id:
            return i
    raise AssertionError(f"no hay opcion de jugar {card_id}")


# ---------------------------------------------------------------------------
# 1. The board: energy ON the table, and still nothing attacks
# ---------------------------------------------------------------------------

def test_the_board_has_energy_and_is_blocked_all_the_same():
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    mio = cur["players"][yo]

    # This is NOT the empty board of step 116: two bodies carry a Grass each.
    cargados = [p for p in mio["bench"] if p and p["energies"]]
    assert [p["id"] for p in cargados] == [OGERPON, OGERPON]
    assert all(len(p["energyCards"]) == 1 for p in cargados)

    # And yet nothing of ours can attack: the active is at zero of the two it
    # needs, the Ogerpon at one of three, and the hand holds no Grass to attach.
    assert mio["active"][0]["id"] == HYDRAPPLE
    assert not mio["active"][0]["energies"]
    assert sorted(c["id"] for c in mio["hand"]) == sorted([ULTRA_BALL, FOREST, DAWN])
    assert not any(c["id"] == GRASS for c in mio["hand"])
    assert not cur["energyAttached"] and not cur["supporterPlayed"]

    cls = m.to_observation_class(o).current
    manos = defaultdict(int)
    for c in mio["hand"]:
        manos[c["id"]] += 1
    campo = defaultdict(int)
    for p in (mio["active"] + mio["bench"]):
        if p:
            campo[p["id"]] += 1
    assert not m._a_body_can_attack_this_turn(cls.players[yo], cls, manos, campo)

    # Six prizes each: the refill this unlocks draws EIGHT, not six.
    assert len(mio["prize"]) == 6
    assert len(cur["players"][1 - yo]["prize"]) == 6

    # The card groups the sentence is written in, and the dead stadium beside
    # them: ours is already in play, which is why the menu offers only two cards.
    assert DAWN in POKEMON_SEARCH_SUPPORTER_IDS and DAWN not in GRASS_DIGGER_REACH
    assert cur["stadium"] and cur["stadium"][0]["id"] == FOREST
    assert len(o["select"]["option"]) == 3


def test_the_rule_reads_this_board_although_it_is_not_dry():
    """The predicate itself, not only the choice it produces."""
    caja = {}
    orig = ub_mod._the_body_search_cannot_buy_the_energy

    def espia(ctx, ub_in_hand=None):
        out = orig(ctx, ub_in_hand)
        caja.setdefault("ctx", ctx)
        caja["out"] = caja.get("out") or out
        return out

    ub_mod._the_body_search_cannot_buy_the_energy = espia
    try:
        m.agent(_obs())
    finally:
        ub_mod._the_body_search_cannot_buy_the_energy = orig
    assert caja.get("out") is True, (
        "la regla no leyo este tablero: hay energia en la mesa, pero la "
        "condicion es que NADA pueda atacar hoy")


# ---------------------------------------------------------------------------
# 2. The decision, and the arm the measurements compare against
# ---------------------------------------------------------------------------

def test_the_slot_goes_to_the_route_that_reaches_an_energy():
    o = _obs()
    assert m.agent(o) == [_play_idx(o, ULTRA_BALL)], (
        "Dawn compra cuerpos y en este turno ningun cuerpo puede atacar: la "
        "ranura del Supporter es la puerta a la Lillie's del mazo, y se abre "
        "con Ultra Ball -> Meowth ex -> Last-Ditch Catch")


def test_without_the_rule_the_recorded_dawn_comes_back():
    o = _obs()
    previo = ub_mod.THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN
    ub_mod.THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN = False
    try:
        assert m.agent(o) == [_play_idx(o, DAWN)]
    finally:
        ub_mod.THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN = previo


# ---------------------------------------------------------------------------
# 3. The search that was unlocked names the engine, not any body
# ---------------------------------------------------------------------------

def _same_board_with_hand(ids):
    """This board, with `ids` in hand and the menu the engine would offer.

    The Forest of Vitality is never playable here -- ours is already the stadium
    in play -- which is why the recorded menu has two cards and an END.
    """
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    mio = cur["players"][yo]
    mio["hand"] = [{"id": cid, "playerIndex": yo, "serial": 900 + i}
                   for i, cid in enumerate(ids)]
    mio["handCount"] = len(ids)
    o["select"]["option"] = (
        [{"index": i, "type": int(m.OptionType.PLAY)}
         for i, cid in enumerate(ids) if cid != FOREST]
        + [{"type": int(m.OptionType.END)}])
    return o


def test_the_slot_waits_for_the_route_even_with_no_ultra_ball_to_pay():
    """Same turn, the Meowth ex ALREADY in hand: the Supporter still waits.

    The recorded board reaches the refill through a cost -- Ultra Ball, two
    cards discarded -- and it would be easy to read the rule as being about that
    cost. It is not: what the turn is buying is the ORDER. Play the Meowth
    first and *Last-Ditch Catch* puts a Lillie's Determination in hand while the
    slot is still free; play the Dawn first and the Meowth's ability fetches a
    Supporter that can no longer be played today.
    """
    o = _same_board_with_hand([MEOWTH, FOREST, DAWN])
    assert m.agent(o) == [_play_idx(o, MEOWTH)]


def test_with_the_refill_already_in_hand_the_slot_is_not_spent_on_bodies():
    """The end of the same chain, with no chain left to walk: Lillie's over Dawn."""
    o = _same_board_with_hand([LILLIE, FOREST, DAWN])
    assert m.agent(o) == [_play_idx(o, LILLIE)]


def test_the_ultra_ball_fetches_the_meowth_ex():
    o = _obs()
    m.agent(o)                                   # se juega la Ultra Ball

    mazo = [
        {"id": LILLIE, "playerIndex": 0, "serial": 26},
        {"id": GRASS, "playerIndex": 0, "serial": 59},
        {"id": m.Chikorita, "playerIndex": 0, "serial": 8},
        {"id": m.Tapu_Bulu, "playerIndex": 0, "serial": 22},
        {"id": HYDRAPPLE, "playerIndex": 0, "serial": 19},
        {"id": OGERPON, "playerIndex": 0, "serial": 4},
        {"id": MEOWTH, "playerIndex": 0, "serial": 20},
        {"id": m.Meganium, "playerIndex": 0, "serial": 13},
    ]
    cur = o["current"]
    mio = cur["players"][cur["yourIndex"]]
    for c in list(mio["hand"]):
        mio["discard"].append(c)
    mio["hand"] = []
    mio["handCount"] = 0
    o["select"] = {
        "context": 7, "contextCard": None, "deck": mazo,
        "effect": {"id": ULTRA_BALL, "playerIndex": 0, "serial": 35},
        "maxCount": 1, "minCount": 1,
        "option": [{"area": 1, "index": i, "playerIndex": 0, "type": 3}
                   for i, c in enumerate(mazo)
                   if c["id"] not in (GRASS, LILLIE)],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1,
    }
    elegido = m.agent(o)[0]
    assert mazo[o["select"]["option"][elegido]["index"]]["id"] == MEOWTH
