"""One Applin wears ONE Hydrapple ex: the second copy is what pays the Ultra Ball.

Scenario (`records/registro_002_pasos_016_hasta_031.json`, step 26, turn 2 going
second -- OUR first turn --, LOST vs Marnie, episode 90181011):

    US (6 prizes)                          OPPONENT (6 prizes)
    active  Teal Mask Ogerpon ex, 1 {G}    active  Morgrem line 70, 1 {G}
    bench   Chikorita, **Applin** 1 {G}    bench   4 bodies
    hand    **Hydrapple ex x2**, Dipplin,  stadium theirs (Spikemuth Gym)
            Dawn, Xerosic, **Ultra Ball**
    (energy already attached, Supporter still free, NO Forest of Vitality)

The menu offered exactly two plays: Dawn and Ultra Ball. The agent played
**Dawn**, which with no Forest in play searches an evolution line we cannot
evolve for two more turns -- and which the next Lillie's shuffles back into the
deck. The line the board was asking for is Ultra Ball -> Meowth ex ->
Last-Ditch Catch -> Lillie's Determination: the refill that actually opens the
turn, and the one that matters most against a deck whose Marnie's line is weak
to Grass, where having an attacker ready NEXT turn decides the race.

Cause: the Ultra Ball scored **-1**, vetoed by `_ub_cancel_no_surplus`
(`_ub_real_fodder` = 1 < 2). The count was right about every card but one. Of a
hand of six it protected: both Hydrapple ex (an Applin in play), the Dipplin
(the same Applin), Dawn (the lone refill Supporter) -- leaving the Xerosic as
the single discardable card. But **one Applin can only ever wear one Hydrapple
ex**: the second copy could not reach the field by any route, and it was
precisely the card the cost should have eaten. With the veto down the Ultra Ball
scores 11900 and beats Dawn's 2680.

Fix, deck-agnostic and in the two places that have to agree on it:

  * `_evo_copies_usable` (ptcg/cards/lines.py) counts the SEATS an evolution
    has -- bodies in play at a stage below it, plus basics of its line the bench
    still fits -- reading the stages off `EVO_LINES`, naming no card;
  * `_ub_real_fodder` adds the copies beyond those seats as fodder, so the
    cancel-by-cost family stops protecting cardboard;
  * the `SelectContext.DISCARD` scorer moves the surplus copies to
    `DISCARD_EVO_SPARE_COPY` (55), the same band the Hydrapple branch already
    used for a spare copy when one is in play. Without this half the veto would
    lift and the cost would then burn the **Dipplin** -- the live link -- while
    keeping both Stage 2s.

The two halves are tested apart because they fail apart.
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
            / "marnie_t2_the_spare_stage2_pays_the_ultra_ball_step26.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
CHIKORITA = m.Chikorita
APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
DAWN = m.Dawn
XEROSIC = m.Xerosic_Machinations
ULTRA_BALL = m.Ultra_Ball
POKE_PAD = m.Poke_Pad
BCS = m.Bug_Catching_Set
GRASS = m.Basic_Grass_Energy

# The opponent's board in the record (Marnie's line). Only its shape matters
# here: a 70 HP active and four bodies on the bench.
OP_ACTIVE = 860
OP_BENCH = 646
OP_STADIUM = 1259

SEAT = 1                       # our seat in the record


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


# ---------------------------------------------------------------------------
# 1. `_evo_copies_usable`: the seat arithmetic on its own
# ---------------------------------------------------------------------------

def test_one_applin_seats_a_single_hydrapple():
    """The record's board: one Applin on the bench, no Applin in hand."""
    assert m._evo_copies_usable(
        HYDRAPPLE, {HYDRAPPLE: 2, DIPPLIN: 1}, {APPLIN: 1}, free_bench=3) == 1


def test_the_dipplin_in_hand_does_not_add_a_seat():
    """It goes ON TOP of the Applin already in play: it is the same line, not a
    second one. Counting pieces instead of bodies is what over-protected the
    hand."""
    assert m._evo_copies_usable(
        HYDRAPPLE, {HYDRAPPLE: 2, DIPPLIN: 2}, {APPLIN: 1}, free_bench=3) == 1


def test_a_basic_in_hand_adds_a_seat_when_the_bench_fits_it():
    assert m._evo_copies_usable(
        HYDRAPPLE, {HYDRAPPLE: 2, APPLIN: 1}, {APPLIN: 1}, free_bench=3) == 2
    # ...and none at all with the bench full: that Applin never comes down.
    assert m._evo_copies_usable(
        HYDRAPPLE, {HYDRAPPLE: 2, APPLIN: 1}, {APPLIN: 1}, free_bench=0) == 1


def test_the_intermediate_link_counts_its_own_seats():
    """Dipplin sits on an Applin: two Applin in play seat two Dipplin."""
    assert m._evo_copies_usable(DIPPLIN, {DIPPLIN: 2}, {APPLIN: 2},
                                free_bench=3) == 2
    assert m._evo_copies_usable(DIPPLIN, {DIPPLIN: 2}, {APPLIN: 1},
                                free_bench=3) == 1


def test_the_other_line_and_the_cards_outside_a_line():
    """Deck-agnostic: the stages come from `EVO_LINES`. A basic or a card that
    is not an evolution of ours answers None -- the caller has nothing to cap."""
    assert m._evo_copies_usable(MEGANIUM, {MEGANIUM: 2}, {BAYLEEF: 1},
                                free_bench=3) == 1
    assert m._evo_copies_usable(MEGANIUM, {MEGANIUM: 1}, {CHIKORITA: 1,
                                                          BAYLEEF: 1},
                                free_bench=3) == 2
    assert m._evo_copies_usable(APPLIN, {APPLIN: 2}, {APPLIN: 1},
                                free_bench=3) is None
    assert m._evo_copies_usable(LILLIE, {LILLIE: 2}, {}, free_bench=3) is None


# ---------------------------------------------------------------------------
# 2. The record's step: the Ultra Ball is played instead of the Dawn
# ---------------------------------------------------------------------------

def test_step26_plays_the_ultra_ball_instead_of_the_dawn():
    obs = _record_obs()
    assert sorted(_hand_ids(obs)) == sorted(
        [HYDRAPPLE, HYDRAPPLE, DIPPLIN, DAWN, XEROSIC, ULTRA_BALL])
    assert _played(obs, m.agent(obs)) == ULTRA_BALL, (
        "con DOS Hydrapple ex en mano y UN solo Applin en banca, la copia "
        "sobrante paga la Ultra Ball: el motor UB->Meowth->Lillie's vale mas "
        "que una Dawn sin Forest en juego")


def test_with_a_single_stage_two_in_hand_the_cost_veto_still_stands():
    """CONTROL: take one Hydrapple ex away and the hand has no surplus again --
    every remaining card is protected for a reason -- so the Ultra Ball goes
    back to being vetoed and the turn falls to Dawn. The rule only speaks about
    copies the board cannot seat."""
    obs = _record_obs()
    me = obs["current"]["players"][SEAT]
    # The LAST copy goes: the menu's options address the hand by index, and
    # removing an earlier card would repoint them at another card.
    assert me["hand"][4]["id"] == HYDRAPPLE
    del me["hand"][4]
    me["handCount"] = len(me["hand"])
    assert _played(obs, m.agent(obs)) == DAWN


def test_a_second_applin_on_the_bench_seats_both_stage_twos():
    """CONTROL: with TWO Applin in play both Hydrapple ex have a body waiting,
    the surplus disappears and the veto by cost stands. What the rule reads is
    the board, not the number of copies."""
    obs = _record_obs()
    me = obs["current"]["players"][SEAT]
    extra = copy.deepcopy(me["bench"][1])          # the Applin of the record
    extra["serial"] = 58
    extra["energies"] = []
    extra["energyCards"] = []
    me["bench"].append(extra)
    assert _played(obs, m.agent(obs)) == DAWN


# ---------------------------------------------------------------------------
# 3. The other half: WHICH two cards pay for it
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
        "effect": {"id": ULTRA_BALL, "playerIndex": SEAT, "serial": 97},
        "minCount": how_many, "maxCount": how_many,
        "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"type": 3, "area": 2, "index": i, "playerIndex": SEAT}
                   for i in range(len(hand))]}
    return obs


def test_the_cost_is_paid_with_the_spare_stage_two_not_with_the_live_link():
    obs = _discard_menu(_record_obs())
    hand = obs["current"]["players"][SEAT]["hand"]
    chosen = [hand[obs["select"]["option"][i]["index"]]["id"]
              for i in m.agent(obs)]
    assert sorted(chosen) == sorted([XEROSIC, HYDRAPPLE]), (
        f"el coste sale del excedente (Xerosic + la 2a Hydrapple ex), no del "
        f"eslabon vivo; descarto {chosen}")
    assert DIPPLIN not in chosen, (
        "el Dipplin es el UNICO eslabon que convierte el Applin de la banca")
    assert DAWN not in chosen, "el Supporter de refresco no paga el coste"


def test_the_surplus_copy_is_not_touched_when_the_board_seats_it():
    """CONTROL of the same prompt: with a second Applin on the bench both
    Stage 2s are protected again and the cost has to fall elsewhere."""
    obs = _record_obs()
    me = obs["current"]["players"][SEAT]
    extra = copy.deepcopy(me["bench"][1])
    extra["serial"] = 58
    extra["energies"] = []
    extra["energyCards"] = []
    me["bench"].append(extra)
    obs = _discard_menu(obs)
    hand = obs["current"]["players"][SEAT]["hand"]
    chosen = [hand[obs["select"]["option"][i]["index"]]["id"]
              for i in m.agent(obs)]
    assert chosen.count(HYDRAPPLE) <= 1, (
        f"con dos Applin en banca ninguna Hydrapple ex es excedente; "
        f"descarto {chosen}")


# ---------------------------------------------------------------------------
# 4. The chain the Ultra Ball buys, menu by menu
# ---------------------------------------------------------------------------
# The record stops at step 26 (the agent played Dawn), so from the cost onwards
# the position is rebuilt with StateBuilder on the same board.

def _field(esc, meowth=False):
    bench = [pk(CHIKORITA), pk(APPLIN, energies=[G], fisicas=1)]
    if meowth:
        bench.append(pk(MEOWTH))
    return (esc
            .my_active(pk(OGERPON, energies=[G], fisicas=1))
            .my_bench(*bench)
            .op_active(pk(OP_ACTIVE, energies=[G], fisicas=1))
            .op_bench(OP_ACTIVE, OP_BENCH, OP_BENCH, OP_BENCH)
            .op_zones(hand=7, deck=42, prizes=6)
            .stadium(OP_STADIUM, of_the_opponent=True))


# The visible deck of the fetch prompts. It is built from what is LEFT in the
# pool once the board, the hand and the discard are placed, so the accounting
# closes on its own; six Grass stay behind as the face-down prizes. Declaring a
# short deck by hand would switch on the deck-out brake and measure something
# else.
def _deck_from_pool(esc, first, reserve=(ULTRA_BALL,)):
    pool = Counter(esc._pool)
    for _cid in reserve:                 # the card `fetch_ultra_ball()` spends
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


def test_the_paid_search_brings_the_meowth_ex():
    esc = (_field(Scenario(turn=2, step=27, tac=13, first_player=1,
                           energy_played=True))
           .my_hand(HYDRAPPLE, DAWN, DIPPLIN)
           .my_discard(POKE_PAD, BCS, XEROSIC, HYDRAPPLE))
    obs = (esc.deck(*_deck_from_pool(esc, (MEOWTH, LILLIE, BOSS)))
              .fetch_ultra_ball()
              .build())
    sel = obs["select"]
    brought = [sel["deck"][sel["option"][i]["index"]]["id"] for i in m.agent(obs)]
    assert brought == [MEOWTH], (
        f"sin atacante para manana la Ultra Ball cava el motor de mano, "
        f"no un cuerpo; trajo {brought}")


def test_the_meowth_goes_down_the_same_turn():
    obs = (_field(Scenario(turn=2, step=28, tac=14, first_player=1,
                           energy_played=True))
           .my_hand(HYDRAPPLE, DAWN, DIPPLIN, MEOWTH)
           .my_discard(POKE_PAD, BCS, XEROSIC, HYDRAPPLE, ULTRA_BALL)
           .menu_hand()
           .build())
    assert _played(obs, m.agent(obs)) == MEOWTH


def test_the_last_ditch_catch_brings_the_lillie():
    esc = (_field(Scenario(turn=2, step=29, tac=15, first_player=1,
                           energy_played=True), meowth=True)
           .my_hand(HYDRAPPLE, DAWN, DIPPLIN)
           .my_discard(POKE_PAD, BCS, XEROSIC, HYDRAPPLE, ULTRA_BALL))
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
                     if c["id"] in (LILLIE, DAWN, XEROSIC, BOSS, m.Lanas_Aid)]
    brought = [sel["deck"][sel["option"][i]["index"]]["id"] for i in m.agent(obs)]
    assert brought == [LILLIE], (
        f"el Meowth del primer turno existe para traer la Lillie's; "
        f"trajo {brought}")


def test_and_the_lillie_is_played_over_the_dawn_that_started_all_this():
    obs = (_field(Scenario(turn=2, step=30, tac=16, first_player=1,
                           energy_played=True), meowth=True)
           .my_hand(HYDRAPPLE, DAWN, DIPPLIN, LILLIE)
           .my_discard(POKE_PAD, BCS, XEROSIC, HYDRAPPLE, ULTRA_BALL)
           .menu_hand()
           .build())
    # `menu_hand()` carries no legality filter: the simulator does NOT offer the
    # evolutions here (our first turn, and the Applin came down this very turn).
    hand = obs["current"]["players"][0]["hand"]
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o["type"] != int(m.OptionType.PLAY)
        or hand[o["index"]]["id"] not in (HYDRAPPLE, DIPPLIN)]
    assert _played(obs, m.agent(obs)) == LILLIE, (
        "sin Forest of Vitality en juego, refrescar la mano vale mas que "
        "armar una linea evolutiva que no podemos evolucionar")
