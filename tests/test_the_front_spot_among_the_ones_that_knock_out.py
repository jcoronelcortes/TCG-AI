"""Two bodies take the same prize; the front seat goes to the one that is left
standing.

Scenario (`records/registro_012_pasos_156_hasta_175.json`, steps 170-172, turn
12, LOST vs Alakazam -- episode 91919734). Two prizes to TWO:

    US (2 prizes)                             RIVAL (2 prizes)
    active  Dipplin 80/80, 2 en.              active  Alakazam 140/140
    bench   Meowth ex 170/170, 0 en.                  (Powerful Hand: 20 x hand)
            Teal Mask Ogerpon ex 210/210, 4   hand    3 cards -> 100 projected
            Hydrapple ex **140**/330, 2 en.
            Fezandipiti ex 210/210, 0 en.
            Meganium 160/160, 0 en.

We retreat the Dipplin and TWO of those bodies finish the Alakazam: the Teal
Mask Ogerpon ex (Myriad Leaf Shower, 180 on a 140 HP body) and the Hydrapple ex,
carved down to 140 of its 330 (Syrup Storm, 210). The agent promoted the
HYDRAPPLE. It did take the prize -- and it left the front seat at 140 HP and
worth the exact two prizes they still needed, with a 210 HP body that takes the
same prize sitting on the bench.

Cause: nothing strategic chose it. `PROMO_KO_BONUS` says "among several knockers
the base score decides", and that base score is 500 for "it attacks now" plus
`hp // 10` plus the energy count plus a bonus per species -- 597 for the
Hydrapple against 595 for the Ogerpon. HP is in there and it is worth SEVEN
points; the flavour on top of it is worth ninety.

And the rule written for exactly this shape one record earlier
(`test_the_front_spot_at_match_point_goes_to_the_body_that_lives`, registro_014,
the same matchup) could not see it: it asks whether their reply REMOVES the
candidate, their reply is projected onto the active we are about to knock out,
and our own Xerosic had just cut their hand to three. Powerful Hand read
20 x (3+2) = 100 and all five candidates outlasted it. The body that answers on
their NEXT turn is not on the board yet, so no survival reading can reach it.
Raw HP can.

Fix, deck-agnostic: THE FRONT SPOT AMONG THE ONES THAT KNOCK OUT. The knockers
are grouped by price (`ko_front_price_rung`) and, INSIDE each group, the ones a
taller knocker outlives pay `PROMO_KO_FRONT`. It is a penalty on the dominated
body, never a bonus on the chosen one: it reorders inside the +20000 band, so it
can never promote a body that takes no prize and never changes what the front
seat costs us.

WHERE IT DELIBERATELY STOPS:

  * ACROSS PRICES it says nothing. The user's rung above this one -- "first a
    one-prize body that beats them, a Meganium, a Tapu Bulu" -- is already
    decided by rules measured one board at a time (prize denial, the basic-wall
    family, the Meganium designated against this matchup, the Crustle/Kangaskhan
    split). Reordering across prices was tried first and moved two frozen-corpus
    decisions from a Teal Mask Ogerpon ex to the Tapu Bulu those matchups keep
    on the bench on purpose.
  * a body that cannot LEAVE the front does not set the bar: against Cubchoo a
    310 HP Hydrapple ex nailed down by its retreat cost does not get to demote
    the 210 HP Ogerpon ex that the anti-Cubchoo rule promotes.

Coverage:
  * the record's board and its arithmetic: both bodies finish the same
    Alakazam, and every survival reading says both are safe;
  * the record's decision: the Ogerpon ex comes up, not the wounded Hydrapple,
    and the turn still retreats;
  * the rung above it: with a charged Meganium the 1-prize body goes first;
  * the boundaries: different prices are not reordered, non-knockers are never
    raised, and a nailed-down body does not set the bar.
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

import main as m
from cg.api import OptionType
from patching import parcheado

OGERPON = m.Teal_Mask_Ogerpon_ex       # 210/210, 4 energies, 2 prizes
HYDRA = m.Hydrapple_ex                 # 140 of 330, 2 energies, 2 prizes
MEGANIUM = m.Meganium                  # 160/160, 1 prize
MEOWTH = m.Meowth_ex
FEZ = m.Fezandipiti_ex
OP_ALAKAZAM = m.Alakazam_ex            # id 743, "Alakazam": 140 HP, 1 prize

_FIX_SWITCH = (ROOT / "tests" / "fixtures"
               / "alakazam_step172_the_front_spot_among_the_ones_that_knock_out.json")
_FIX_MAIN = (ROOT / "tests" / "fixtures"
             / "alakazam_step170_the_retreat_before_the_front_spot.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._prev_op_prize = 6
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _bench_index(obs, card_id):
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return next(i for i, b in enumerate(mine["bench"])
                if b and b["id"] == card_id)


def _bench(obs, card_id):
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return next(b for b in mine["bench"] if b and b["id"] == card_id)


def _scores(obs):
    """{card id: score} for the whole promotion menu, spying on the ranking."""
    out = {}

    def spy(context, select, sc, o, my_index, top_n=3):
        for i, opt in enumerate(select.option):
            card = m.get_card(o, opt.area, opt.index, my_index)
            if card is not None:
                out.setdefault(card.id, sc[i])

    with parcheado("_debug_log_decision", spy):
        m.agent(copy.deepcopy(obs))
    return out


def _charge(body, n):
    body["energies"] = [1] * n
    body["energyCards"] = [{"id": 1, "playerIndex": 0, "serial": 900 + i}
                           for i in range(n)]
    return body


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_the_records_one():
    obs = _obs(_FIX_SWITCH)
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert len(mine["prize"]) == 2 and len(theirs["prize"]) == 2, (
        "two prizes each: their next knockout on a 2-prize body ends the game")

    ogerpon, hydra = _bench(obs, OGERPON), _bench(obs, HYDRA)
    assert ogerpon["hp"] == 210 and len(ogerpon["energies"]) == 4
    assert hydra["hp"] == 140 and hydra["maxHp"] == 330, (
        "the Hydrapple is the WOUNDED body: 140 of 330, current HP and not the "
        "printed one is what the rule reads")
    assert theirs["active"][0]["id"] == OP_ALAKAZAM
    assert theirs["active"][0]["hp"] == 140


def test_both_bodies_finish_the_same_alakazam():
    """The knockout is not what is being chosen here -- only who takes it."""
    obs = _obs(_FIX_SWITCH)
    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        if not seen:
            seen["kos"] = tc._promo_kos_op
            seen["bench"] = tc.my_state.bench
        return original(tc, o, score)

    m.score_option = spy
    try:
        m.agent(copy.deepcopy(obs))
    finally:
        m.score_option = original

    kos = {b.id: seen["kos"](b) for b in seen["bench"] if b is not None}
    assert kos[OGERPON] and kos[HYDRA], "both finish the Alakazam"
    assert not any(kos[i] for i in (MEOWTH, FEZ, MEGANIUM)), (
        "and nobody else does: three bodies with no energy on them")


def test_every_survival_reading_says_both_are_safe():
    """Why the match-point rule of registro_014 could not catch this one: our
    own Xerosic left them three cards, Powerful Hand projects 100, and 100 goes
    through neither of the two candidates."""
    obs = _obs(_FIX_SWITCH)
    theirs = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    assert theirs["handCount"] == 3

    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        if not seen:
            seen["op"] = tc._promo_op_act
            seen["bench"] = tc.my_state.bench
        return original(tc, o, score)

    m.score_option = spy
    try:
        m.agent(copy.deepcopy(obs))
    finally:
        m.score_option = original

    for body in seen["bench"]:
        if body is None or body.id not in (OGERPON, HYDRA):
            continue
        reply = max(m._op_active_attack_damage_to(seen["op"], body),
                    m._op_active_attack_damage_to(seen["op"], body,
                                                  op_hand_count=3))
        assert 0 < reply < (body.hp or 0), (
            f"{body.id}: their projected reply ({reply}) leaves it standing, so "
            f"no survival criterion separates the two")


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_front_spot_goes_to_the_ogerpon_that_lives():
    obs = _obs(_FIX_SWITCH)
    assert m.agent(copy.deepcopy(obs)) == [_bench_index(obs, OGERPON)], (
        "same prize, same turn, 70 more HP standing in front of them")


def test_the_turn_still_retreats_the_dipplin():
    """The fix changes WHO comes up, never whether we retreat: the 80 HP Dipplin
    in front does not finish the Alakazam and the relay does."""
    obs = _obs(_FIX_MAIN)
    chosen = obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]
    assert chosen["type"] == int(OptionType.RETREAT), chosen


def test_the_wounded_knocker_pays_exactly_the_tie_break():
    """A penalty on the dominated body, and only that: the Hydrapple keeps the
    whole knockout band minus `PROMO_KO_FRONT`, so it still outranks every body
    that takes no prize."""
    scores = _scores(_obs(_FIX_SWITCH))
    assert scores[OGERPON] > 20000, "the taller knocker is not touched"
    assert scores[OGERPON] - scores[HYDRA] > 0
    assert scores[HYDRA] > 20000 - m.PROMO_KO_FRONT - 1000, (
        "the wounded knocker is demoted, not vetoed")
    assert scores[HYDRA] > max(scores[MEOWTH], scores[FEZ]) + 9500, (
        "and it stays far above the highest band of a body that takes no prize")


# ---------------------------------------------------------------------------
# 3. The rung above it, which this rule does NOT re-decide
# ---------------------------------------------------------------------------

def test_a_one_prize_body_that_finishes_them_goes_first():
    """The user's first rung, already decided by the rules that were measured
    for it. Charge the Meganium on that same bench and the 1-prize body takes
    the front over both ex."""
    obs = _obs(_FIX_SWITCH)
    _charge(_bench(obs, MEGANIUM), 4)
    assert m.agent(copy.deepcopy(obs)) == [_bench_index(obs, MEGANIUM)]


def test_across_prices_the_tie_break_is_silent():
    """It groups by price and orders inside the group. With the Meganium
    charged, the 1-prize body and the two ex sit on different rungs (their pile
    is at TWO), so the HP tie-break cannot move anything between them."""
    obs = _obs(_FIX_SWITCH)
    _charge(_bench(obs, MEGANIUM), 4)
    scores = _scores(obs)
    # The Meganium is 160 HP, below the 210 of the Ogerpon: if the rule read HP
    # across prices, it would be the one demoted.
    assert scores[MEGANIUM] > scores[OGERPON]


# ---------------------------------------------------------------------------
# 4. Boundaries
# ---------------------------------------------------------------------------

def test_it_never_raises_a_body_that_takes_no_prize():
    """A penalty on the dominated knocker and never a bonus on anyone: the three
    bodies with no energy on that bench stay exactly where the rest of the chain
    left them, far below the knockout band."""
    scores = _scores(_obs(_FIX_SWITCH))
    for card_id in (MEOWTH, FEZ):
        assert scores[card_id] < 20000, "they take no prize"
    assert scores[MEGANIUM] < 0, "the Meganium line does not go active"


_FIX_CUBCHOO = (ROOT / "tests" / "fixtures"
                / "cubchoo_promueve_ogerpon_letal_tras_retirar.json")


def test_a_body_nailed_down_does_not_set_the_bar():
    """Anti-Cubchoo (registro_036 step 146). The 310 HP Hydrapple ex that cannot
    pay its retreat cost against a deck that locks the active does not get to
    demote the 210 HP Ogerpon ex that rule exists to promote."""
    with open(_FIX_CUBCHOO, encoding="utf-8") as f:
        cub = json.load(f)
    cub = cub.get("observation", cub)
    mine = cub["current"]["players"][cub["current"]["yourIndex"]]
    hydra = next(b for b in mine["bench"] if b and b["id"] == HYDRA)
    oger = next(b for b in mine["bench"] if b and b["id"] == OGERPON)
    assert hydra["hp"] > oger["hp"], "the nailed-down body is the taller one"
    assert len(hydra["energies"]) < m.RETREAT_COST[HYDRA], "and it is nailed down"

    picked = cub["select"]["option"][m.agent(copy.deepcopy(cub))[0]]
    assert mine["bench"][picked["index"]]["id"] == OGERPON, (
        "mobility beats HP against a deck that locks the active")
