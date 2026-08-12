"""At match point the price tag stops being information: the front spot goes to
whoever their reply cannot remove.

Scenario (`records/registro_014_pasos_122_hasta_136.json`, steps 127-130, turn
14, LOST vs Alakazam -- episode 90350002). Four prizes to ONE:

    US (4 prizes)                            RIVAL (1 prize)
    active  Hydrapple ex **170**/330, 0 en.  active  Alakazam 140/140
    bench   Teal Mask Ogerpon ex 210/210, 4          (Powerful Hand: 20 x hand)
            Meganium 160/160                 hand    8 cards -> 200 projected
            Fezandipiti ex 210/210
            Meowth ex 170/170
            Tapu Bulu **140**/140, 4 en.

Three of our bodies finish that Alakazam. The agent retreated the Hydrapple and
promoted the TAPU BULU -- one prize instead of the Ogerpon's two -- Wood Hammer
left it at 110 of 140, and their next attacker took the last prize they needed.
The Ogerpon ex takes the same knockout from 210 and stands up to the 200 of
Powerful Hand.

Cause: two rules argued for the cheap body, and BOTH are written on a discount
that does not exist at match point.

  * `+3000` prize denial when promoting (`op_prize <= 2` -> a 1-prize body that
    can attack): its own comment says "so that an opposing KO does not close the
    game". With their pile at ONE, the 1-prize body hands over exactly the prize
    that closes it. The bonus buys nothing and steers the front spot to the
    fragile body.
  * `_alakazam_pivot_1prize`: "if it is then knocked out we concede 1 prize
    instead of 2" -- the same sentence, equally false at `op_prize == 1`.

And the criterion those two outbid -- survival -- was asleep twice over:
`PROMO_KO_BONUS` exempts every body that knocks out ("among several knockers the
base score decides", and that base score ranks prizes before HP), and
`_promo_survives` reads the projector the ordinary way, which is where Powerful
Hand prints 0 damage and every candidate looks immortal.

Fix, in three parts and deck-agnostic:

  1. the denial has to DENY: `prize_count(card) < op_prize`;
  2. the pivot has to DISCOUNT: `op_prize > 1`;
  3. MATCH POINT AMONG THE ONES THAT KNOCK OUT: when their next knockout on this
     body takes their last prize, the knocker that does NOT outlast their reply
     pays the ordinary doomed penalty after all -- unless OUR knockout closes the
     game first. The reading is `_mp_outlasts`, which takes the maximum of the
     ordinary projection and the one that counts their hand.

It is a penalty and not a veto, and the same size as the ordinary doomed one: it
reorders INSIDE the +20000 band, so a knocker that dies still outranks any body
that takes no prize at all. The knockout is never surrendered; only the body
that takes it changes.

Measured: ONE flip in the whole record corpus (this step), and 3 firings in
266372 decisions of self-play -- 300 mirror games plus 120 against each of the
18 opposing decks -- all three of them on boards at 1-1 prizes.

Coverage:
  * the record's board and its arithmetic: both bodies finish the same Alakazam,
    their reply removes one of them and not the other;
  * the record's decision: the Ogerpon ex comes up, not the Tapu Bulu;
  * each of the three parts on its own, through the score;
  * the boundaries -- away from match point the cheap body is still preferred
    (the +3000 keeps its board), a knockout that WINS the game is never
    demoted, and with an unreadable attack nobody is penalised.
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

OGERPON = m.Teal_Mask_Ogerpon_ex      # 210 HP, 2 prizes
TAPU = m.Tapu_Bulu                    # 140 HP, 1 prize
HYDRA = m.Hydrapple_ex                # ours, active at 170/330
OP_ALAKAZAM = m.Alakazam_ex           # id 743, "Alakazam": 140 HP, 1 prize

_FIX_SWITCH = (ROOT / "tests" / "fixtures"
               / "alakazam_step130_the_front_spot_at_match_point.json")
_FIX_MAIN = (ROOT / "tests" / "fixtures"
             / "alakazam_step127_the_discount_that_buys_nothing.json")


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


def _bench_index(obs, card_id, hp=None):
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    return next(i for i, b in enumerate(mine["bench"])
                if b and b["id"] == card_id and (hp is None or b["hp"] == hp))


def _stub(card_id, hp, energies=0):
    from types import SimpleNamespace
    return SimpleNamespace(id=card_id, hp=hp, maxHp=hp, tools=[],
                           energies=[1] * energies, energyCards=[])


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_the_records_one():
    obs = _obs(_FIX_SWITCH)
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert len(mine["prize"]) == 4 and len(theirs["prize"]) == 1, (
        "match point is the premise: their next knockout takes their last prize")
    assert mine["active"][0]["id"] == HYDRA and mine["active"][0]["hp"] == 170

    ogerpon = mine["bench"][_bench_index(obs, OGERPON)]
    tapu = mine["bench"][_bench_index(obs, TAPU)]
    assert ogerpon["hp"] == 210 and len(ogerpon["energies"]) == 4
    assert tapu["hp"] == 140 and len(tapu["energies"]) == 4

    alakazam = theirs["active"][0]
    assert alakazam["id"] == OP_ALAKAZAM and alakazam["hp"] == 140

    # Both finish it, so the knockout is not what is being chosen here.
    for body in (ogerpon, tapu):
        pk = _stub(body["id"], body["hp"], len(body["energies"]))
        base = m._attacker_base_damage(pk.id, _stub(OP_ALAKAZAM, 140),
                                       len(pk.energies), grass_scale=8,
                                       teal_self_energy=len(pk.energies),
                                       bench_count=4)
        assert m._our_effective_damage(pk, _stub(OP_ALAKAZAM, 140), base,
                                       False, False) >= 140, body["id"]


def test_their_reply_removes_one_of_the_two_and_not_the_other():
    """Powerful Hand prints 0 damage; counting their hand of eight it is 200."""
    alakazam = _stub(OP_ALAKAZAM, 140, energies=1)
    assert m._op_active_attack_damage_to(alakazam, _stub(TAPU, 140)) == 0
    seen = m._op_active_attack_damage_to(alakazam, _stub(TAPU, 140),
                                         op_hand_count=8)
    assert seen >= 140, "it goes through the Tapu Bulu"
    assert seen < 210, "and it stops at the Ogerpon ex"


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_front_spot_goes_to_the_ogerpon_that_lives():
    obs = _obs(_FIX_SWITCH)
    assert m.agent(copy.deepcopy(obs)) == [_bench_index(obs, OGERPON)], (
        "at match point the 1-prize Tapu Bulu is not cheaper: it is the game")


def test_the_turn_still_retreats_the_wounded_hydrapple():
    """The pivot that argued for the retreat loses its argument, and the retreat
    stands on the one that never depended on the prize count: the body in front
    is at 170 against a projected 200 and the relay finishes the same target."""
    obs = _obs(_FIX_MAIN)
    chosen = obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]
    assert chosen["type"] == int(OptionType.RETREAT), chosen


# ---------------------------------------------------------------------------
# 3. Each of the three parts, on its own
# ---------------------------------------------------------------------------

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


def _their_prizes(obs, n):
    obs = copy.deepcopy(obs)
    obs["current"]["players"][1 - obs["current"]["yourIndex"]]["prize"] = [None] * n
    return obs


def _their_hand(obs, n):
    obs = copy.deepcopy(obs)
    obs["current"]["players"][1 - obs["current"]["yourIndex"]]["handCount"] = n
    return obs


def test_the_two_halves_of_the_rule_read_on_the_same_body():
    """A ladder of three boards on the SAME Tapu Bulu isolates each half.

        unreadable reply, match point   ->  neither fires (the baseline)
        readable reply, TWO prizes      ->  +3000: the denial denies again
        readable reply, ONE prize       ->  -6000: the knocker that dies yields

    The baseline carries ONE term that is not part of this rule and does not
    depend on their attack: `PROMO_KO_FRONT` (user, registro_012 step 172), the
    tie-break that gives the front seat to the taller of two EQUALLY PRICED
    knockers. At match point every price is clamped onto one rung -- which is
    this file's whole thesis -- so the 210 HP Ogerpon and the 140 HP Tapu Bulu
    share it and the Tapu pays 1200. It cancels out of both differences below;
    it is written into the baseline so the ladder still reads as three boards on
    one body. Off match point (two prizes) the two bodies sit on different rungs
    and it is silent, which is why the +3000 comes out clean.
    """
    obs = _obs(_FIX_SWITCH)
    baseline = _scores(_their_hand(obs, 0))[TAPU]
    off_match_point = _scores(_their_prizes(obs, 2))[TAPU]
    at_match_point = _scores(obs)[TAPU]

    assert off_match_point - (baseline + m.PROMO_KO_FRONT) == 3000, (
        "with two prizes on their side the cheap body denies a real prize")
    assert baseline - at_match_point == m.PROMO_DOOMED_PENALTY, (
        "at match point the knocker that does not outlast their reply pays the "
        "ordinary doomed penalty")


def test_away_from_match_point_the_cheap_knocker_still_comes_up():
    """The boundary. With two prizes on their side the 1-prize body denies a
    real prize and the rule that prefers it keeps its board."""
    obs = _obs(_FIX_SWITCH)
    theirs = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    theirs["prize"] = [None, None]
    assert m.agent(copy.deepcopy(obs)) == [_bench_index(obs, TAPU)]


def test_the_pivot_needs_a_discount_to_exist():
    """`_alakazam_pivot_1prize` is one sentence: concede 1 prize instead of 2.
    Read on the record's MAIN menu it must be silent at match point and awake
    one prize later."""
    obs = _obs(_FIX_MAIN)
    seen = {}
    original = m.score_option

    def spy(tc, o, score):
        seen.setdefault("pivot", tc._alakazam_pivot_1prize)
        return original(tc, o, score)
    m.score_option = spy
    try:
        m.agent(copy.deepcopy(obs))
        assert seen["pivot"] is False, "at op_prize == 1 there is nothing to save"

        seen.clear()
        wider = copy.deepcopy(obs)
        theirs = wider["current"]["players"][1 - wider["current"]["yourIndex"]]
        theirs["prize"] = [None, None, None]
        m.agent(wider)
        assert seen["pivot"] is True, "with three prizes the saving is real"
    finally:
        m.score_option = original


def test_a_knockout_that_wins_the_game_is_never_demoted():
    """The exemption. With our own last prize on the table our knockout closes
    the game before their reply exists: the fragile knocker is not demoted, and
    both finishers stay in the winning band."""
    obs = _obs(_FIX_SWITCH)
    obs["current"]["players"][obs["current"]["yourIndex"]]["prize"] = [None]
    scores = _scores(obs)

    assert scores[TAPU] > 30000 and scores[OGERPON] > 30000, (
        "both bodies close the game this turn")
    assert abs(scores[OGERPON] - scores[TAPU]) < m.PROMO_DOOMED_PENALTY, (
        "no penalty separates them: whichever comes up, the game ends")


def test_with_an_unreadable_attack_nobody_is_penalised():
    """The same guard `PROMO_MATCH_POINT_VETO` is written with. An empty hand
    makes Powerful Hand unreadable, there is no evidence that anybody dies, and
    the SURVIVAL half stays quiet -- the prize half, which is about their pile
    and not about their attack, goes on applying.

    What the Tapu Bulu still pays here is `PROMO_KO_FRONT` and nothing else: the
    tie-break between equally priced knockers reads HP, a fact about OUR body,
    so an unreadable attack does not silence it -- that is the point of it (user,
    registro_012 step 172, where every survival reading said the wounded body
    was safe). The assertion is that the -6000 of THIS rule did not fire.
    """
    obs = _obs(_FIX_SWITCH)
    scores = _scores(_their_hand(obs, 0))
    assert scores[TAPU] > 20000 - m.PROMO_KO_FRONT, (
        "it keeps the knockout band: no survival penalty, only the HP tie-break")
    assert abs(scores[OGERPON] - scores[TAPU]) < m.PROMO_DOOMED_PENALTY
