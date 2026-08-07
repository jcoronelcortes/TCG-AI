"""A line whose Basic is only in the DECK is not a line: it is cardboard.

Scenario (`records/registro_004_pasos_021_hasta_026.json`, step 26, turn 4,
LOST vs the Archaludon ex deck, episode 90339125):

    US (6 prizes)                          OPPONENT (6 prizes)
    active  Tapu Bulu 40/140, NO energy    active  160/160, 1 energy
    bench   Teal Mask Ogerpon ex, 2 {G}    bench   two bodies (one with 3)
    hand    Hydrapple ex, Forest of        stadium OURS (Forest of Vitality)
            Vitality, Dipplin, ULTRA BALL

The turn was already spent: the energy attached, the stadium played, no attack
possible (the active has no energy and cannot pay its retreat of 3, and the
Ogerpon on the bench came down this very turn). The menu offered exactly two
things -- PLAY Ultra Ball and END -- and the agent chose END, throwing away the
turn's SUPPORTER along with it: the only route to that Supporter was Ultra Ball
-> Meowth ex -> Last-Ditch Catch -> Lillie's Determination, the refill that
opens the next turn while a 40 HP active waits to be knocked out.

Cause: the Ultra Ball scored **-1**, vetoed by `_ub_cancel_no_surplus`
(`_ub_real_fodder` = 1 < 2). Of the three cards that could pay, the count
protected the Hydrapple ex AND the Dipplin, each for the same reason: "the other
half of the line is in hand, there is a Forest of Vitality on the field, and
there is an Applin IN THE DECK -- so this is one search away from being a whole
Basic -> Stage 1 -> Stage 2 chain in a single turn". Only the spare Forest
counted as fodder.

The protection was CIRCULAR. The Applin lived in the deck and the only card in
hand that could dig it out was the very Ultra Ball being vetoed -- and even if
it had been played for the Applin, its cost of two would have eaten the two
pieces the search existed to serve. The hand could not keep that promise by any
route, so the agent was protecting a line it could never assemble and paid for
it with the whole turn.

Fix, deck-agnostic and in the two places that have to agree (the same pairing as
`_evo_copies_usable`): `_line_base_benchable` (ptcg/cards/lines.py) reads the
stages off `EVO_LINES` and answers whether the line's BASIC is in HAND with a
bench slot to fit it. THE DECK IS NOT A SEAT -- the same doctrine
`_evo_copies_usable` states ("a line protects the seats, not the copies") and
`_evo_link_state` already applies when it calls a piece ORPHANED because its
pre-evolution is "neither in play nor in hand". Consumers:

  * `_ub_real_fodder`, so the cancel-by-cost family stops protecting cardboard;
  * the `SelectContext.DISCARD` scorer, so the cost is then paid with that same
    cardboard and not with a live card.

Note what does NOT change: a body of the line already ON THE BOARD keeps every
piece protected (that branch is read first and is untouched), which is the case
the whole family was built for. Only the promise that lives in the deck falls.

Golden corpus: exactly ONE flip in the 14 records, this step (`END` -> `PLAY
Ultra Ball`).
"""

import copy
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Scenario, pk, G

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "archaludon_step26_the_line_that_only_exists_in_the_deck.json")

TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
DAWN = m.Dawn
XEROSIC = m.Xerosic_Machinations
LANAS = m.Lanas_Aid
ULTRA_BALL = m.Ultra_Ball
FOREST = m.Forest_of_Vitality
GRASS = m.Basic_Grass_Energy

# The opponent's board in the record: a 160 HP active with one energy and two
# benched bodies, one of them charged. Only the shape matters here -- none of
# them can be knocked out by an active with no energy.
OP_ACTIVE = 666
OP_BENCH = 169

SEAT = 0                       # our seat in the record


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_engine_pivot_turn = False
    m._grass_attaches_this_turn = 0
    yield
    m._init_cards_tracking()


def _record_obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _played(obs, choice):
    o = obs["select"]["option"][choice[0]]
    if o["type"] == int(m.OptionType.PLAY):
        yo = obs["current"]["yourIndex"]
        return obs["current"]["players"][yo]["hand"][o["index"]]["id"]
    return None


def _hand_ids(obs):
    yo = obs["current"]["yourIndex"]
    return [c["id"] for c in obs["current"]["players"][yo]["hand"]]


def _is_end(obs, choice):
    return obs["select"]["option"][choice[0]]["type"] == int(m.OptionType.END)


# ---------------------------------------------------------------------------
# 1. `_line_base_benchable`: the predicate on its own
# ---------------------------------------------------------------------------

def test_the_basic_in_hand_with_a_free_bench_is_a_seat():
    assert m._line_base_benchable(HYDRAPPLE, {HYDRAPPLE: 1, APPLIN: 1},
                                  free_bench=3) is True
    assert m._line_base_benchable(DIPPLIN, {DIPPLIN: 1, APPLIN: 1},
                                  free_bench=1) is True


def test_the_basic_in_the_deck_is_not_a_seat():
    """The heart of the bug: the hand holds both halves of the line and the
    Applin exists -- but only in the deck, where nothing in hand can reach it."""
    assert m._line_base_benchable(HYDRAPPLE, {HYDRAPPLE: 1, DIPPLIN: 1},
                                  free_bench=4) is False
    assert m._line_base_benchable(DIPPLIN, {HYDRAPPLE: 1, DIPPLIN: 1},
                                  free_bench=4) is False


def test_with_the_bench_full_the_basic_in_hand_is_not_a_seat_either():
    """It has nowhere to land, so it dresses nothing: the same answer the
    `free_bench` term of `_evo_copies_usable` gives."""
    assert m._line_base_benchable(HYDRAPPLE, {HYDRAPPLE: 1, APPLIN: 1},
                                  free_bench=0) is False


def test_it_is_deck_agnostic_and_reads_the_stages_off_evo_lines():
    """The other line answers the same way, and a card outside every line (or
    the Basic itself, which has no line below it) answers False."""
    assert m._line_base_benchable(MEGANIUM, {CHIKORITA: 1}, free_bench=2) is True
    assert m._line_base_benchable(BAYLEEF, {MEGANIUM: 1}, free_bench=2) is False
    assert m._line_base_benchable(APPLIN, {APPLIN: 2}, free_bench=2) is False
    assert m._line_base_benchable(LILLIE, {APPLIN: 1}, free_bench=2) is False


# ---------------------------------------------------------------------------
# 2. The record's step: the dead turn buys its Supporter
# ---------------------------------------------------------------------------

def test_step26_plays_the_ultra_ball_instead_of_ending_the_turn():
    obs = _record_obs()
    assert sorted(_hand_ids(obs)) == sorted(
        [HYDRAPPLE, FOREST, DIPPLIN, ULTRA_BALL])
    assert [o["type"] for o in obs["select"]["option"]] == [
        int(m.OptionType.PLAY), int(m.OptionType.END)], (
        "el menu real de este paso: o se juega la Ultra Ball o se pasa")
    assert _played(obs, m.agent(obs)) == ULTRA_BALL, (
        "con el Applin solo en el MAZO, la linea Hydrapple no es una linea: la "
        "Ultra Ball es la unica ruta al Supporter del turno "
        "(UB -> Meowth ex -> Last-Ditch -> Lillie's)")


def test_an_applin_on_the_bench_puts_the_veto_back():
    """CONTROL: the branch that protects the pieces because a BODY of the line
    is already in play is untouched. With an Applin on the bench the Hydrapple
    and the Dipplin are both real, the hand has no surplus and the Ultra Ball
    goes back to being vetoed by cost -- which is the case the whole family of
    cost vetoes exists for."""
    obs = _record_obs()
    me = obs["current"]["players"][SEAT]
    me["bench"].append({"appearThisTurn": False, "energies": [],
                        "energyCards": [], "hp": 60, "id": APPLIN,
                        "maxHp": 60, "playerIndex": SEAT, "preEvolution": [],
                        "serial": 58, "tools": []})
    assert _is_end(obs, m.agent(obs)), (
        "con un Applin en banca las dos piezas visten un cuerpo real: el coste "
        "de la Ultra Ball se comeria la linea")


def test_the_applin_in_hand_also_puts_the_veto_back():
    """CONTROL, the other half of the predicate: with the Basic IN HAND the
    chain runs in a single turn under the Forest, so none of the three pieces
    is fodder and the veto stands. This is the case the old condition MISSED --
    it only looked at the deck -- and it is now covered."""
    obs = _record_obs()
    me = obs["current"]["players"][SEAT]
    me["hand"].append({"id": APPLIN, "playerIndex": SEAT, "serial": 59})
    me["handCount"] = len(me["hand"])
    obs["select"]["option"].insert(
        0, {"index": len(me["hand"]) - 1, "type": int(m.OptionType.PLAY)})
    choice = m.agent(obs)
    assert _played(obs, choice) != ULTRA_BALL, (
        "con el Applin en MANO la linea si es real: la Ultra Ball se pagaria "
        "con las piezas que iba a servir")


# ---------------------------------------------------------------------------
# 3. WHICH two cards pay for it
# ---------------------------------------------------------------------------

def _discard_menu(obs, how_many=2):
    """The DISCARD prompt of the Ultra Ball just played: it is no longer in
    hand, it is the card in effect."""
    me = obs["current"]["players"][SEAT]
    hand = [c for c in me["hand"] if c["id"] != ULTRA_BALL]
    me["hand"] = hand
    me["handCount"] = len(hand)
    obs["current"]["turnActionCount"] += 1
    obs["select"] = {
        "type": 1, "context": int(m.SelectContext.DISCARD),
        "contextCard": None, "deck": None,
        "effect": {"id": ULTRA_BALL, "playerIndex": SEAT, "serial": 45},
        "minCount": how_many, "maxCount": how_many,
        "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"type": 3, "area": 2, "index": i, "playerIndex": SEAT}
                   for i in range(len(hand))]}
    return obs


def test_the_cost_is_paid_with_the_spare_forest_and_the_orphan_link():
    """The discarder has to price the same cards the veto did, or the fix only
    moves the damage: with the Forest already ON the field the second copy is
    the cheapest card in hand (95), and the orphaned Dipplin follows it (18)."""
    obs = _discard_menu(_record_obs())
    hand = obs["current"]["players"][SEAT]["hand"]
    chosen = [hand[obs["select"]["option"][i]["index"]]["id"]
              for i in m.agent(obs)]
    assert sorted(chosen) == sorted([FOREST, DIPPLIN]), (
        f"el coste sale del carton: el Forest duplicado (ya hay uno en juego) "
        f"y el eslabon huerfano; descarto {chosen}")


# ---------------------------------------------------------------------------
# 4. The chain the Ultra Ball buys, menu by menu
# ---------------------------------------------------------------------------
# The record ends the turn at step 26, so from the search onwards the position
# is rebuilt with StateBuilder on the same board.

def _field(esc, meowth=False):
    bench = [pk(OGERPON, energies=[G, G], fisicas=2, aparecio=True)]
    if meowth:
        bench.append(pk(MEOWTH))
    return (esc
            .my_active(pk(TAPU, hp=40))
            .my_bench(*bench)
            .op_active(pk(OP_ACTIVE, energies=[G], fisicas=1))
            .op_bench(pk(OP_BENCH, energies=[G, G, G], fisicas=3),
                      pk(OP_BENCH))
            .op_zones(hand=3, deck=35, prizes=6)
            .stadium(FOREST))


def _deck_from_pool(esc, first, reserve=(ULTRA_BALL,)):
    """The visible deck of the fetch prompts, built from what is LEFT in the
    pool once the board, the hand and the discard are placed: the accounting
    closes on its own and six Grass stay behind as the face-down prizes.
    Declaring a short deck by hand would switch on the deck-out brake and
    measure something else."""
    pool = Counter(esc._pool)
    for _cid in reserve:
        pool[_cid] -= 1
    rest = []
    for _cid in first:
        if pool[_cid] <= 0:
            raise AssertionError(f"la carta {_cid} ya no esta en el pool")
        pool[_cid] -= 1
        rest.append(_cid)
    prizes = 6
    for _cid, _n in sorted(pool.items()):
        for _ in range(_n):
            if _cid == GRASS and prizes:
                prizes -= 1
                continue
            rest.append(_cid)
    assert prizes == 0
    return rest


def _scenario(step, tac, meowth=False):
    return _field(Scenario(turn=4, step=step, tac=tac, first_player=1,
                           energy_played=True, stadium_played=True),
                  meowth=meowth)


def test_the_paid_search_brings_the_meowth_ex():
    esc = (_scenario(27, 7)
           .my_hand(HYDRAPPLE)
           .my_discard(XEROSIC, FOREST, DIPPLIN))
    obs = (esc.deck(*_deck_from_pool(esc, (MEOWTH, LILLIE, BOSS)))
              .fetch_ultra_ball()
              .build())
    sel = obs["select"]
    brought = [sel["deck"][sel["option"][i]["index"]]["id"]
               for i in m.agent(obs)]
    assert brought == [MEOWTH], (
        f"sin atacante utilizable este turno la Ultra Ball cava el motor de "
        f"mano, no un cuerpo mas; trajo {brought}")


def test_the_meowth_goes_down_the_same_turn():
    obs = (_scenario(28, 8)
           .my_hand(HYDRAPPLE, MEOWTH)
           .my_discard(XEROSIC, FOREST, DIPPLIN, ULTRA_BALL)
           .menu_hand()
           .build())
    assert _played(obs, m.agent(obs)) == MEOWTH, (
        "cavar el Meowth no sirve de nada si no se baja: su Last-Ditch Catch "
        "es lo que busca el Supporter")


def test_the_last_ditch_catch_brings_the_lillie():
    esc = (_scenario(29, 9, meowth=True)
           .my_hand(HYDRAPPLE)
           .my_discard(XEROSIC, FOREST, DIPPLIN, ULTRA_BALL))
    obs = (esc.deck(*_deck_from_pool(esc, (MEOWTH, LILLIE, BOSS)))
              .fetch_ultra_ball()
              .build())
    # The same CARD prompt, but the card in effect is the Meowth ex and what it
    # offers are the Supporters of the deck (Last-Ditch Catch).
    sel = obs["select"]
    sel["effect"] = {"id": MEOWTH, "playerIndex": 0, "serial": 55}
    sel["minCount"] = 1
    sel["option"] = [{"type": 3, "area": 1, "index": i, "playerIndex": 0}
                     for i, c in enumerate(sel["deck"])
                     if c["id"] in (LILLIE, DAWN, XEROSIC, BOSS, LANAS)]
    brought = [sel["deck"][sel["option"][i]["index"]]["id"]
               for i in m.agent(obs)]
    assert brought == [LILLIE], (
        f"con la mano en dos cartas y ningun ataque posible, el refresco es "
        f"todo el turno; trajo {brought}")


def test_and_the_lillie_is_played_so_the_turn_is_not_wasted():
    obs = (_scenario(30, 10, meowth=True)
           .my_hand(HYDRAPPLE, LILLIE)
           .my_discard(XEROSIC, FOREST, DIPPLIN, ULTRA_BALL)
           .menu_hand()
           .build())
    # `menu_hand()` carries no legality filter: the simulator does NOT offer a
    # Stage 2 with no Dipplin in play to evolve -- that is exactly why the
    # Hydrapple ex was cardboard when the cost was decided.
    hand = obs["current"]["players"][0]["hand"]
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o["type"] != int(m.OptionType.PLAY)
        or hand[o["index"]]["id"] != HYDRAPPLE]
    assert _played(obs, m.agent(obs)) == LILLIE, (
        "el Supporter del turno seguia libre: terminar sin jugarlo era "
        "exactamente lo que costo el turno en el registro")
