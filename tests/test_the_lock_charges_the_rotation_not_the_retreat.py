"""Five turns frozen in front of a 70 HP Cubchoo, because the exemption was
closed by CARD ID and the body in front was the one it excluded.

THE BOARD (user, `records/registro_010_pasos_079_hasta_081.json` step 81,
episode 93149196 vs a Cubchoo/Dunsparce stall deck, WON). Our turn 10, the last
menu of the turn:

    US                                        RIVAL
    active  Teal Mask Ogerpon ex 200/210      active  Cubchoo 70/70, 1 energy
            4 Grass (8 effective),                    muting us with *Snotted Up*
            MUTED -- no ATTACK option
    bench   Meganium 1 Grass,                 bench   Cubchoo, Dunsparce x3,
            Hydrapple ex 2 Grass,                     Fan Rotom
            Teal Mask Ogerpon ex 2 Grass,
            Applin 0

*Snotted Up* leaves the Defending Pokemon unable to attack on our turn, so the
menu carries no ATTACK. The line was there: retreat the muted Ogerpon for ONE
Grass and promote its twin, whose Myriad Leaf Shower counts the energy on both
Actives (4 of ours + 1 of theirs) for 180 against 70 HP. A prize, and their
attacker off the board.

The agent chose END. And not once: the census over that whole episode
(`utils/census_the_lock_charges_the_rotation.py`) finds 18 menus with the mute on
and the retreat legal, 13 of them with a benched body that KNOCKS OUT and the
retreat at `SCORE_VETO`. Turns 10, 12, 14, 16 and 18 are the SAME frozen board
and the turn was handed over five times, prizes stuck at 3-6. It only unfroze on
turn 20, when a Meowth ex happened to be the body in front.

CAUSE, and it is the third time this shape appears. The anti-Cubchoo
conservation veto ([[anti-cubchoo-no-retirada-pivote-conservar-energia]]) has two
exemptions and BOTH are closed by card id: `_cubchoo_lock_stuck` on
`== Hydrapple_ex`, `_cubchoo_mute_cashes_prize` on
`NON_ATTACKER_ENERGY_WASTE_IDS`. The charged Teal Mask Ogerpon ex was excluded
from both on purpose -- "its Myriad scales with its OWN energy, those Grass ARE
investment" -- and it is the body that stands in front most of the time.

WHAT ACTUALLY SEPARATES THE TWO BOARDS. registro_004 p47 is also a charged Teal
Mask Ogerpon ex, muted, with a benched body that knocks out, so no reading of the
body in FRONT can tell them apart. The difference is the body the retreat
PROMOTES:

  * p47 -- the only bench body that finishes the Cubchoo is a Hydrapple ex,
    retreat cost 3. Promoting it jams our most expensive body into a lock that
    mutes whatever is in front: next turn's forced rotation costs 3 more energy.
    The PASS is right and it still stands.
  * p81 -- the body that finishes it is a second Teal Mask Ogerpon ex, retreat
    cost 1, the same as the body leaving. A twin rotation: one Grass for a prize
    today, the same fee to swap back tomorrow.

So against a deck whose whole plan is to re-mute our Active every turn, the fee
that decides is not this turn's retreat but NEXT turn's rotation.
`_cubchoo_mute_rotates` exempts the veto when the cheapest body that cashes the
prize is no more expensive to rotate out than the one we are retreating.

AND THE PROMOTION IS THE SAME QUESTION. Lifting the veto alone was not enough:
both the Hydrapple ex and the twin Ogerpon finish that Cubchoo, and the promotion
tie-break orders knockers by who OUTLIVES whom -- empty against an attacker that
does 10 -- so the seat went to the Hydrapple ex by 1272 points, the same prize
today for three times the fee tomorrow. `PROMO_KO_ROTATION` demotes the knocker
that is more expensive to rotate than the cheapest one, reading the SAME number
the retreat was priced with.

FLIP DIFF over the golden corpus: 6, all in this episode -- turns 10, 12, 14, 16
and 18 END -> RETREAT, and the turn 20 promotion Hydrapple ex -> Teal Mask
Ogerpon ex. No other record moves.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from patching import instalar

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "cubchoo_step081_the_lock_charges_the_rotation.json")
_FIXTURE_P47 = (ROOT / "tests" / "fixtures"
                / "cubchoo_step47_no_energy_wasting_retreat.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
CUBCHOO = m.Cubchoo


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
    m.op_has_mega_kangaskhan = False
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    m._grass_attaches_this_turn = 0
    yield
    m._init_cards_tracking()


def _obs(path=_FIXTURE):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _opponent(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _index_of(obs, option_type):
    return next(i for i, opt in enumerate(obs["select"]["option"])
                if opt["type"] == int(option_type))


def _type(obs, choice):
    return obs["select"]["option"][choice[0]]["type"]


def _scores(obs):
    """The score of each menu option, spying on `_debug_log_decision`."""
    seen = {}
    orig = m._debug_log_decision

    def spy(context, select, scores, obs_, my_index, top_n=3):
        seen["scores"] = list(scores)

    instalar("_debug_log_decision", spy)
    prev = m.DEBUG_DECISIONS
    m.DEBUG_DECISIONS = True
    try:
        m.agent(obs)
    finally:
        instalar("_debug_log_decision", orig)
        m.DEBUG_DECISIONS = prev
    return seen["scores"]


def _promotion_menu(obs):
    """The menu the engine asks NEXT: who takes the front seat.

    The retreat is already paid on it -- one whole Grass card leaves the Ogerpon,
    which under Wild Growth is two effective units -- and the body still sits in
    the Active slot while the bench is offered, which is the shape the recorded
    promotion menus have (`cubchoo_promueve_ogerpon_letal_tras_retirar.json`).
    """
    obs = copy.deepcopy(obs)
    mine = _mine(obs)
    act = mine["active"][0]
    assert m.RETREAT_COST[act["id"]] == 1
    act["energyCards"] = act["energyCards"][:-1]
    act["energies"] = act["energies"][:-2]
    obs["current"]["turnActionCount"] += 1
    obs["select"] = {
        "context": 3, "contextCard": None, "deck": None, "effect": None,
        "maxCount": 1, "minCount": 1, "remainDamageCounter": 0,
        "remainEnergyCost": 0, "type": 1,
        "option": [{"area": 5, "index": i, "playerIndex": 1, "type": 3}
                   for i in range(len(mine["bench"]))],
    }
    return obs


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_muted_ogerpon_with_its_twin_ready():
    obs = _obs()
    mine, opponent = _mine(obs), _opponent(obs)

    # The lock: their Cubchoo is in front and our menu has NO attack in it.
    assert opponent["active"][0]["id"] == CUBCHOO
    assert opponent["active"][0]["hp"] == 70
    types = {opt["type"] for opt in obs["select"]["option"]}
    assert int(m.OptionType.ATTACK) not in types
    assert int(m.OptionType.RETREAT) in types

    # Our active is the body BOTH existing exemptions exclude, and it carries a
    # surplus, which is what the conservation veto fires on.
    active = mine["active"][0]
    assert active["id"] == OGERPON
    assert OGERPON not in m.NON_ATTACKER_ENERGY_WASTE_IDS
    assert len(active["energyCards"]) > m.RETREAT_COST[OGERPON]

    # On the bench, a TWIN at the same retreat cost and already over its attack
    # cost, plus a Hydrapple ex that also knocks out but costs three to rotate.
    twin = next(b for b in mine["bench"] if b and b["id"] == OGERPON)
    assert len(twin["energies"]) >= m.ATTACK_ENERGY_REQ[OGERPON]
    assert m.RETREAT_COST[OGERPON] == m.RETREAT_COST[active["id"]]
    assert any(b and b["id"] == HYDRAPPLE for b in mine["bench"])
    assert m.RETREAT_COST[HYDRAPPLE] > m.RETREAT_COST[OGERPON]


# ---------------------------------------------------------------------------
# 2. The decision, and the one that follows it
# ---------------------------------------------------------------------------

def test_it_retreats_instead_of_handing_the_turn_over():
    obs = _obs()
    assert _type(obs, m.agent(obs)) == int(m.OptionType.RETREAT)


def test_the_conservation_veto_no_longer_kills_the_retreat():
    """The failure was a VETO (score -1), not a defeat on points: ENDING the turn
    scored 0 and every other option in that menu was already vetoed."""
    obs = _obs()
    scores = _scores(obs)
    assert scores[_index_of(obs, m.OptionType.RETREAT)] > 0, scores


def test_the_seat_goes_to_the_twin_and_not_to_the_hydrapple():
    """Lifting the veto is only half the turn: both bodies finish that Cubchoo,
    and the seat has to go to the one the lock can charge only 1 for."""
    obs = _promotion_menu(_obs())
    bench = _mine(obs)["bench"]
    choice = m.agent(obs)
    assert bench[choice[0]]["id"] == OGERPON, [b["id"] for b in bench]


def test_the_promotion_demotes_the_expensive_knocker_without_leaving_the_band():
    """`PROMO_KO_ROTATION` is a tie-break INSIDE the +20000 knocker band: the
    Hydrapple ex loses the seat but still outranks every body that takes no
    prize, so removing the twin would not cost us the knockout."""
    obs = _promotion_menu(_obs())
    bench = _mine(obs)["bench"]
    scores = _scores(obs)
    hydra = next(i for i, b in enumerate(bench) if b["id"] == HYDRAPPLE)
    twin = next(i for i, b in enumerate(bench) if b["id"] == OGERPON)
    assert scores[hydra] < scores[twin]
    assert scores[hydra] > m.PROMO_LAST_STAND, scores


# ---------------------------------------------------------------------------
# 3. The controls: what the reading must NOT move
# ---------------------------------------------------------------------------

def test_the_pass_of_p47_still_stands_on_its_own_board():
    """registro_004 p47, the real fixture. Same lock, same muted charged Ogerpon
    ex in front -- and the only bench body that knocks out is a Hydrapple ex at
    retreat 3. The rotation is the expensive one, so the veto holds and we PASS."""
    obs = _obs(_FIXTURE_P47)
    scores = _scores(obs)
    assert scores[_index_of(obs, m.OptionType.RETREAT)] <= 0, scores
    assert _type(obs, m.agent(obs)) != int(m.OptionType.RETREAT)


def test_without_a_body_that_knocks_out_the_veto_stands():
    """The exemption demands a benched attacker that KNOCKS OUT, not a bare
    pivot: strip the bench down to bodies below their attack cost and we keep the
    energy."""
    obs = _obs()
    for b in _mine(obs)["bench"]:
        if b:
            b["energies"] = []
            b["energyCards"] = []
    scores = _scores(obs)
    assert scores[_index_of(obs, m.OptionType.RETREAT)] <= 0, scores
    assert _type(obs, m.agent(obs)) != int(m.OptionType.RETREAT)


def test_the_reading_is_deck_specific():
    """Off this matchup there is no conservation veto to exempt from, so the
    switch has nothing to do: turning it off must not change this board's
    neighbours. Here it is checked the only way that cannot lie -- with the
    switch itself."""
    obs = _obs()
    assert m.CUBCHOO_MUTE_ROTATION is True
    m.CUBCHOO_MUTE_ROTATION = False
    try:
        assert _type(obs, m.agent(_obs())) == int(m.OptionType.END)
    finally:
        m.CUBCHOO_MUTE_ROTATION = True
    assert _type(obs, m.agent(_obs())) == int(m.OptionType.RETREAT)


def test_the_matchup_and_the_mute_really_are_switched_on():
    """If `op_is_cubchoo_deck` or the mute were False there would be no veto to
    exempt and the tests above would pass without testing anything."""
    obs = _obs()
    capt = {}

    def tr(frame, ev, arg):
        if frame.f_code.co_name != "agent":
            return None
        if ev == "return":
            for k in ("op_is_cubchoo_deck", "can_attack",
                      "_cubchoo_lock_stuck", "_cubchoo_mute_cashes_prize",
                      "_cubchoo_mute_rotates", "_cubchoo_ko_rotation_min"):
                if k in frame.f_locals:
                    capt[k] = frame.f_locals[k]
        return tr

    # Restore whatever was tracing BEFORE us: a bare `settrace(None)` uninstalls
    # coverage's tracer for the rest of the process.
    previous_tracer = sys.gettrace()
    sys.settrace(tr)
    try:
        m.agent(obs)
    finally:
        sys.settrace(previous_tracer)

    assert capt.get("op_is_cubchoo_deck") is True, capt
    assert capt.get("can_attack") is False, capt
    # Neither of the two older exemptions can see this board...
    assert capt.get("_cubchoo_lock_stuck") is False, capt
    assert capt.get("_cubchoo_mute_cashes_prize") is False, capt
    # ...and the new one reads the twin's retreat cost, not a card id.
    assert capt.get("_cubchoo_mute_rotates") is True, capt
    assert capt.get("_cubchoo_ko_rotation_min") == m.RETREAT_COST[OGERPON], capt
