"""The turn's Supporter cannot go to a card that does not buy what the turn lacks.

Scenario (`records/registro_009_pasos_116_hasta_120.json`, step 116, turn 9,
episode 93210930 vs Festival Lead -- WON in spite of this):

    US (3 prizes)                          RIVAL (3 prizes)
    active  Hydrapple ex 190/330, **0 e**  active  Thwackey 100/100
    bench   Meganium 160/160, 0 e          bench   Dipplin (1 e), Thwackey x2,
            Teal Mask Ogerpon ex x2, 0 e           Dipplin, Applin
    hand    Bayleef, DAWN, ULTRA BALL      stadium Forest of Vitality (ours)

        [0] DAWN         2680   <-- played
        [2] END             0
        [1] ULTRA BALL     -1   `_ub_cancel_no_surplus`

NOT ONE ENERGY on the whole board, and none in hand: no body of ours could
attack whatever we did with the turn. The turn's only Supporter went to Dawn --
"search your deck for a Basic, a Stage 1 and a Stage 2" -- which brought a Tapu
Bulu and a second Hydrapple ex. The Tapu was benched and the turn ended: zero
energy attached, zero damage, three Pokemon cards in hand.

Dawn cannot produce an energy: it is out of `GRASS_DIGGER_REACH` for exactly
that reason. And playing it CLOSED the only door, because a turn plays one
Supporter: the deck still held three Lillie's Determination -- a fresh hand of
six out of twenty-seven cards with eight Basic {G} among them -- one Meowth ex
away (Last-Ditch Catch fetches a Supporter), which is one Ultra Ball away.

Cause: the Ultra Ball was ALREADY worth more than the Dawn on that board (12400
against 2680). The only thing between the two was `_ub_cancel_no_surplus`, whose
count of real fodder came out at ONE in a hand of three because `_ub_real_fodder`
protects a lone refill Supporter -- so the agent kept, as tomorrow's refill, the
one card whose printed text could not answer today's question. Its own DISCARD
scorer did not agree: with Meganium and Hydrapple ex both in play it prices that
same Dawn at 75, ordinary fodder.

Fix (`THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN`): a Supporter of
`POKEMON_SEARCH_SUPPORTER_IDS` stops being protected fodder on a turn where
nothing can attack, no card in hand reaches a Basic Energy, and the route that
does reach one -- Ultra Ball -> Meowth ex -> a refill Supporter -- is walkable
today, step by step. It names no opposing deck.

Golden corpus: ONE flip, this step. The frozen corpus (3 580 decisions) does not
move.
"""

import copy
import json
import sys
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
            / "festival_lead_the_body_search_cannot_buy_the_energy_step116.json")

DAWN = m.Dawn
ULTRA_BALL = m.Ultra_Ball
MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
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
    """Index of the option that PLAYS `card_id` from hand."""
    cur = obs["current"]
    mano = cur["players"][cur["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY):
            carta = mano[o["index"]]
            if carta["id"] == card_id:
                return i
    raise AssertionError(f"no hay opcion de jugar {card_id}")


def _end_idx(obs):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(m.OptionType.END))


# ---------------------------------------------------------------------------
# 1. The board: without it the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_a_turn_with_no_energy_anywhere():
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    mio = cur["players"][yo]

    # Not one energy attached to any body of ours, and none in hand.
    cuerpos = [p for p in (mio["active"] + mio["bench"]) if p]
    assert cuerpos and all(not p["energies"] for p in cuerpos)
    mano = sorted(c["id"] for c in mio["hand"])
    assert mano == sorted([m.Bayleef, DAWN, ULTRA_BALL])
    assert not cur["energyAttached"] and not cur["supporterPlayed"]

    # The two bodies that make the refill worth it are already down...
    assert mio["active"][0]["id"] == HYDRAPPLE
    assert any(p and p["id"] == MEGANIUM for p in mio["bench"])
    # ...so the DISCARD scorer itself prices this Dawn as ordinary fodder (75),
    # which is the sentence `_ub_real_fodder` was contradicting.

    # Dawn cannot produce an energy; that is why it is out of the table.
    assert DAWN in POKEMON_SEARCH_SUPPORTER_IDS
    assert DAWN not in GRASS_DIGGER_REACH
    assert ULTRA_BALL not in GRASS_DIGGER_REACH

    # No body of ours can attack this turn, by the agent's own reading.
    cls = m.to_observation_class(o).current
    mio_cls = cls.players[yo]
    from collections import defaultdict
    manos = defaultdict(int)
    for c in mio["hand"]:
        manos[c["id"]] += 1
    campo = defaultdict(int)
    for p in cuerpos:
        campo[p["id"]] += 1
    assert not m._a_body_can_attack_this_turn(mio_cls, cls, manos, campo)

    # The menu really offers both cards.
    assert _play_idx(o, DAWN) is not None
    assert _play_idx(o, ULTRA_BALL) is not None


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_turn_buys_the_route_to_an_energy_instead_of_more_bodies():
    o = _obs()
    assert m.agent(o) == [_play_idx(o, ULTRA_BALL)], (
        "Dawn compra cuerpos y el turno no tiene ni una energia: la ranura del "
        "Supporter es la puerta a la Lillie's del mazo, y se abre con la Ultra "
        "Ball -> Meowth ex -> Last-Ditch")


def test_without_the_rule_the_recorded_dawn_comes_back():
    """The arm the gate and the oracle measure against."""
    o = _obs()
    previo = ub_mod.THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN
    ub_mod.THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN = False
    try:
        assert m.agent(o) == [_play_idx(o, DAWN)]
    finally:
        ub_mod.THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN = previo


# ---------------------------------------------------------------------------
# 3. The route is checked step by step, not assumed
# ---------------------------------------------------------------------------

def _ctx_of(obs):
    """The DecisionContext the scoring built for this menu."""
    caja = {}
    orig = ub_mod._the_body_search_cannot_buy_the_energy

    def espia(ctx, ub_in_hand=None):
        caja["ctx"] = ctx
        return orig(ctx, ub_in_hand)

    ub_mod._the_body_search_cannot_buy_the_energy = espia
    try:
        m.agent(obs)
    finally:
        ub_mod._the_body_search_cannot_buy_the_energy = orig
    assert "ctx" in caja, "la regla no llego a preguntarse por este tablero"
    return caja["ctx"]


def test_a_grass_in_hand_is_an_energy_plan_and_the_rule_stays_silent():
    """With a Basic {G} in hand the turn is not blocked: Dawn keeps its slot.

    The same reading covers every card of `GRASS_DIGGER_REACH` in hand -- there
    the hand can unblock itself and the Supporter is free to buy a body.
    """
    assert ub_mod._the_body_search_cannot_buy_the_energy(_ctx_of(_obs()))

    con_grass = _obs()
    mio = con_grass["current"]["players"][con_grass["current"]["yourIndex"]]
    mio["hand"].append({"id": GRASS, "playerIndex": 0, "serial": 49})
    mio["handCount"] = len(mio["hand"])
    assert not ub_mod._the_body_search_cannot_buy_the_energy(_ctx_of(con_grass))


def test_without_a_meowth_left_in_the_deck_there_is_no_route_to_buy():
    """The chain is what pays for the Dawn: with no Meowth ex, no chain."""
    o = _obs()
    ctx = _ctx_of(o)
    assert ub_mod._the_body_search_cannot_buy_the_energy(ctx)

    class _SinMeowth:
        def __init__(self, c):
            self.c = c
            self.cards_in_deck = dict(c.cards_in_deck)
            self.cards_in_deck[MEOWTH] = {"DECK": 0, "BENCH": 0, "HAND": 0,
                                          "PRIZE": 0, "DISCARD": 2}

        def __getattr__(self, n):
            return getattr(self.c, n)

    assert not ub_mod._the_body_search_cannot_buy_the_energy(_SinMeowth(ctx))


def test_without_a_refill_left_in_the_deck_there_is_nothing_to_fetch():
    o = _obs()
    ctx = _ctx_of(o)

    class _SinRelleno:
        def __init__(self, c):
            self.c = c
            self.cards_in_deck = dict(c.cards_in_deck)
            for sid in (LILLIE, m.Lanas_Aid):
                self.cards_in_deck[sid] = {"DECK": 0, "BENCH": 0, "HAND": 0,
                                           "PRIZE": 0, "DISCARD": 0}

        def __getattr__(self, n):
            return getattr(self.c, n)

    assert not ub_mod._the_body_search_cannot_buy_the_energy(_SinRelleno(ctx))


def test_with_the_last_ditch_already_spent_the_meowth_fetches_nothing():
    o = _obs()
    ctx = _ctx_of(o)

    class _LDGastado:
        meowth_ld_free = False

        def __init__(self, c):
            self.c = c

        def __getattr__(self, n):
            return getattr(self.c, n)

    assert not ub_mod._the_body_search_cannot_buy_the_energy(_LDGastado(ctx))


def test_with_the_supporter_already_played_there_is_no_slot_to_argue_about():
    ctx = _ctx_of(_obs())

    class _SlotGastado:
        def __init__(self, c):
            self.c = c
            self.state = _EstadoGastado(c.state)

        def __getattr__(self, n):
            return getattr(self.c, n)

    class _EstadoGastado:
        supporterPlayed = True

        def __init__(self, s):
            self.s = s

        def __getattr__(self, n):
            return getattr(self.s, n)

    assert not ub_mod._the_body_search_cannot_buy_the_energy(_SlotGastado(ctx))


# ---------------------------------------------------------------------------
# 4. What the turn does with what it bought
# ---------------------------------------------------------------------------

def test_the_ultra_ball_this_unlocks_fetches_the_meowth_ex():
    """The search is only worth the body it names: it names the engine."""
    o = _obs()
    m.agent(o)                       # se juega la Ultra Ball

    mazo = [
        {"id": 1227, "playerIndex": 0, "serial": 26},
        {"id": GRASS, "playerIndex": 0, "serial": 59},
        {"id": m.Chikorita, "playerIndex": 0, "serial": 8},
        {"id": m.Tapu_Bulu, "playerIndex": 0, "serial": 22},
        {"id": HYDRAPPLE, "playerIndex": 0, "serial": 18},
        {"id": m.Teal_Mask_Ogerpon_ex, "playerIndex": 0, "serial": 3},
        {"id": MEOWTH, "playerIndex": 0, "serial": 19},
        {"id": MEGANIUM, "playerIndex": 0, "serial": 12},
    ]
    cur = o["current"]
    mio = cur["players"][cur["yourIndex"]]
    for c in list(mio["hand"]):
        mio["discard"].append(c)
    mio["hand"] = []
    mio["handCount"] = 0

    o["select"] = {
        "context": 7, "contextCard": None, "deck": mazo,
        "effect": {"id": ULTRA_BALL, "playerIndex": 0, "serial": 37},
        "maxCount": 1, "minCount": 1,
        "option": [{"area": 1, "index": i, "playerIndex": 0, "type": 3}
                   for i in range(len(mazo)) if mazo[i]["id"] != GRASS
                   and mazo[i]["id"] != 1227],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1,
    }
    elegido = m.agent(o)[0]
    idx = o["select"]["option"][elegido]["index"]
    assert mazo[idx]["id"] == MEOWTH


def test_two_grass_out_of_the_refill_knock_their_active_out():
    """What the six cards are worth: Wild Growth doubles and Syrup Storm scales.

    It is the arithmetic that makes the slot worth fighting for, and it is read
    with the agent's own calculators rather than asserted."""
    o = _obs()
    m.agent(o)
    cls = m.to_observation_class(o).current
    yo = cls.players[cls.yourIndex]
    riv = cls.players[1 - cls.yourIndex]
    act, op_act = yo.active[0], riv.active[0]

    assert m._grass_attach_unit() == 2          # Meganium en juego
    danos = []
    for fisicas in (1, 2):
        eff = fisicas * m._grass_attach_unit()
        base = m._attacker_base_damage(act.id, op_act, eff, grass_scale=eff,
                                       teal_self_energy=eff, bench_count=3)
        danos.append(m._our_effective_damage(act, op_act, base, True, False))
    assert danos == [90, 150]
    assert danos[0] < op_act.hp <= danos[1]     # una Grass no llega, dos si
