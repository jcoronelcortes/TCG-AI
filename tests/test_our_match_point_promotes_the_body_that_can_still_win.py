"""One prize from the game, and the promotion picked the body that cannot attack.

Scenario (`records/registro_013_pasos_113_hasta_116.json`, episode 91191469 vs
`mega_lucario`, turn 13, LOST; the fixture is the promotion menu of that step):

    US (1 prize left)                      RIVAL (1 prize left)
    active  -- just knocked out            active  Mega Lucario ex **40**/340
    bench   Meowth ex 0e                           2 Fighting (Mega Brave 270)
            Fezandipiti ex 0e
            Meowth ex 0e
            **Meganium 2e** (1 physical
              Grass, x2 Wild Growth)
            Teal Mask Ogerpon ex 0e
    hand    Poke Pad, Ultra Ball, Forest, Xerosic, Dipplin,
            Hydrapple ex, Ogerpon ex, Unfair Stamp   (NO Grass)

Their Mega Lucario ex is at 40 HP and we need ONE prize. Knocking it out next
turn does not trade well -- it ENDS THE GAME. Meganium is the only body within
reach of doing it: Solar Beam costs 4 and it already carries 2 effective, so a
single physical Grass (worth {G}{G} under its own Wild Growth) completes it and
its 140 buries a 40 HP active. Every other candidate is at zero energy, two
attachments away from anything at all.

The agent promoted a **Meowth ex**. It then spent the whole turn putting bodies
down and playing an Ultra Ball, never attacked, retreated into a Fezandipiti ex
at zero energy (registro_014), and handed the game over on the reply.

Cause. Two rules, both correct on their own turf, disagreeing about a board
neither was written for:

  * `_lucario_ko_prefer_basic` -- vs Mega Lucario with no ready attacker, put up
    a cheap 1-prize basic instead of a 2-prize ex.
  * `_promote_setup_ko_attacker` -- the deck-agnostic selector that promotes the
    body ONE attachment away from a lethal hit (+9500, above every wall).

The second is gated on `not _lucario_ko_prefer_basic`, so vs this one deck the
general rule never ran. And the wall argument is the wrong argument here: a
cheap body is worth handing over because it buys a LATER TURN. At our own match
point our knockout resolves first -- the promotion lands at the end of THEIR
turn, ours comes next -- so there is no later turn to buy, and the only question
left is the user's: which body is closest to landing the kill, counted in
attachments still owed.

Fix: `_promo_ko_wins_the_game` (deck-agnostic -- `my_prize <=
prize_count_op(their active)`, read off the prize piles and their body's own
price) lifts the Lucario veto off the general selector, exempts the chosen
finisher from `PROMO_MATCH_POINT_VETO` (which reads `_promo_kos_op`, i.e. TODAY's
energy, and therefore sank the very play that wins), and opens route (e): at
match point the turn's own draw counts as a way to find the Grass, because the
alternative -- a wall -- wins with probability zero.

Flip diff over the golden corpus (16 records): ONE flip, this decision, Meowth
ex -> Meganium. Nothing else moved.
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
from golden_corpus import reset_agent
from patching import instalar

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "mega_lucario_our_match_point_promotes_meganium_step116.json")

MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
FEZ = m.Fezandipiti_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGA_LUCARIO = 678


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)


def _obs(their_hp=None, meganium_energies=None, our_prizes=None):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]
    if their_hp is not None:
        theirs["active"][0]["hp"] = their_hp
    if meganium_energies is not None:
        for b in mine["bench"]:
            if b and b["id"] == MEGANIUM:
                b["energies"] = b["energies"][:meganium_energies]
    if our_prizes is not None:
        mine["prize"] = [None] * our_prizes
    return o


def _bench_index(obs, card_id):
    """The menu index whose option points at `card_id` on our bench."""
    cur = obs["current"]
    bench = cur["players"][cur["yourIndex"]]["bench"]
    for i, opt in enumerate(obs["select"]["option"]):
        body = bench[opt["index"]]
        if body and body["id"] == card_id:
            return i
    raise AssertionError(f"{card_id} is not in this menu")


def _scores(obs):
    """The score of each menu option, spying on `_debug_log_decision`."""
    seen = {}
    orig = m._debug_log_decision

    def spy(context, select, scores, obs_, my_index, top_n=3):
        seen["scores"] = list(scores)
        return orig(context, select, scores, obs_, my_index, top_n)

    restore = instalar("_debug_log_decision", spy)
    prev = m.DEBUG_DECISIONS
    m.DEBUG_DECISIONS = True
    try:
        m.agent(obs)
    finally:
        restore()
        m.DEBUG_DECISIONS = prev
    return seen["scores"]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_our_match_point_with_one_reachable_finisher():
    o = _obs()
    cur = o["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    # A FORCED promotion: our active spot is empty and the menu only offers bench.
    assert mine["active"] == []
    assert {opt["type"] for opt in o["select"]["option"]} == {int(m.OptionType.CARD)}

    # Our match point: one prize left and their active is worth at least that.
    assert len(mine["prize"]) == 1
    assert theirs["active"][0]["id"] == MEGA_LUCARIO
    assert theirs["active"][0]["hp"] == 40

    # Meganium is ONE physical Grass from Solar Beam; nobody else carries energy.
    meganium = next(b for b in mine["bench"] if b and b["id"] == MEGANIUM)
    assert len(meganium["energies"]) == 2
    assert m.ATTACK_ENERGY_REQ[MEGANIUM] == 4
    assert all(len(b["energies"]) == 0 for b in mine["bench"]
               if b and b["id"] != MEGANIUM)

    # And there is no Grass in hand: the old "can it attack" filter had to fail.
    assert all(c["id"] != m.Basic_Grass_Energy for c in mine["hand"])


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_the_meganium_that_can_still_take_the_last_prize():
    obs = _obs()
    assert m.agent(obs) == [_bench_index(obs, MEGANIUM)]


def test_the_finisher_outranks_every_wall_in_the_menu():
    obs = _obs()
    scores = _scores(obs)
    meganium = scores[_bench_index(obs, MEGANIUM)]
    for other in (MEOWTH, FEZ, OGERPON):
        assert meganium > scores[_bench_index(obs, other)], scores


def test_the_match_point_flag_is_what_opens_it():
    """If `_promo_ko_wins_the_game` were False the Lucario wall rule would still
    own the slot, and the two tests above would pass for the wrong reason."""
    capt = {}

    def tr(frame, ev, arg):
        if frame.f_code.co_name != "agent":
            return None
        if ev == "return":
            for k in ("_promo_ko_wins_the_game", "_lucario_ko_prefer_basic",
                      "_best_promote_card", "_promote_setup_ko_attacker"):
                if k in frame.f_locals:
                    capt[k] = frame.f_locals[k]
        return tr

    # Restore whatever was tracing BEFORE us: a bare `settrace(None)` uninstalls
    # coverage's tracer for the rest of the process.
    previous_tracer = sys.gettrace()
    sys.settrace(tr)
    try:
        m.agent(_obs())
    finally:
        sys.settrace(previous_tracer)

    assert capt.get("_promo_ko_wins_the_game") is True, capt
    # The two rules really were in conflict: the wall rule fired because no body
    # could attack today, and the general selector still found the finisher.
    assert capt.get("_lucario_ko_prefer_basic") is True, capt
    assert capt.get("_best_promote_card") is None, capt
    assert getattr(capt.get("_promote_setup_ko_attacker"), "id", None) == MEGANIUM, capt


# ---------------------------------------------------------------------------
# 3. What is NOT broken: the exemption is match point, not "always the finisher"
# ---------------------------------------------------------------------------

def test_away_from_match_point_the_cheap_wall_keeps_the_slot():
    """With four prizes still to take, knocking their active out buys a turn --
    it does not end the game -- and the measured Lucario rule governs again:
    hand over a cheap body, keep the engine on the bench.

    FOUR and not three: the flag is not "we are at one prize", it is
    `my_prize <= prize_count_op(their active)`, and their Mega ex is worth
    THREE. At three prizes this knockout still empties our pile, and the rule is
    right to fire -- which is the whole reason it is written off the opposing
    body's own price and not off a hardcoded 1."""
    assert m.card_table[MEGA_LUCARIO].megaEx is True  # a Mega ex: 3 prizes
    assert m.agent(_obs(our_prizes=3)) == [_bench_index(_obs(), MEGANIUM)]

    obs = _obs(our_prizes=4)
    assert m.agent(obs) != [_bench_index(obs, MEGANIUM)]


def test_a_finisher_that_does_not_finish_does_not_take_the_slot():
    """Solar Beam is 140. Against a full-health Mega Lucario ex (340) completing
    the Meganium wins nothing, so the wall argument is the right one again."""
    obs = _obs(their_hp=340)
    assert m.agent(obs) != [_bench_index(obs, MEGANIUM)]


def test_a_body_more_than_one_attachment_away_is_not_reachable():
    """The rule promotes what the turn can COMPLETE, not what we wish for: one
    manual attachment (x2 under Wild Growth). Strip the Meganium to zero and no
    candidate is within reach, so the wall keeps the slot."""
    obs = _obs(meganium_energies=0)
    assert m.agent(obs) != [_bench_index(obs, MEGANIUM)]


# ---------------------------------------------------------------------------
# 4. The other half of the line: the turn the promotion buys
# ---------------------------------------------------------------------------
#
# The promotion is only worth what the NEXT turn does with it, and the record
# says exactly what that turn had in hand. In registro_014 (turn 14, the same
# game) the agent played Dawn, drew a Bug Catching Set, and the Set fetched the
# last Basic {G} out of the deck -- so the Grass this rule bets on really did
# arrive. What it did with it, with a Meowth ex in front, could not win:
#
#   * put the Grass on the benched Meganium -> it reaches Solar Beam, but the
#     Meowth ex at 0 energy cannot pay its retreat (cost 1 = one WHOLE card =
#     2 effective under Wild Growth), so the finisher never reaches the front;
#   * put it on the Meowth ex -> now it can retreat, but the retreat DISCARDS
#     that same card, so whoever comes up is empty again. That is what it did.
#
# The turn was already lost when the promotion resolved: the sterile turn is a
# consequence, not a second defect. This fixture is that attach menu, and the
# test asks the only question the fix changes -- with the finisher IN FRONT,
# does the last Grass go to it?

_FIXTURE_ATTACH = (ROOT / "tests" / "fixtures"
                   / "mega_lucario_the_last_grass_goes_to_the_finisher_step122.json")


def _attach_obs(promote_meganium):
    """The turn-14 attach menu, with the promotion of the previous step applied.

    `promote_meganium=False` is the record as played (Meowth ex in front);
    True swaps in the body this rule promotes.
    """
    o = copy.deepcopy(json.load(open(_FIXTURE_ATTACH, encoding="utf-8"))["observation"])
    mine = o["current"]["players"][o["current"]["yourIndex"]]
    if promote_meganium:
        i = next(i for i, b in enumerate(mine["bench"]) if b and b["id"] == MEGANIUM)
        mine["active"][0], mine["bench"][i] = mine["bench"][i], mine["active"][0]
    return o


def _attach_target(obs, choice):
    """Which body the chosen ATTACH option loads."""
    opt = obs["select"]["option"][choice[0]]
    assert opt["type"] == int(m.OptionType.ATTACH), opt
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    body = (mine["active"][0] if opt["inPlayArea"] == 4
            else mine["bench"][opt["inPlayIndex"]])
    return body["id"]


def test_the_turn_really_did_find_the_grass_this_rule_bets_on():
    """Without this the test above measures a promotion into an empty turn."""
    mine = _attach_obs(False)["current"]["players"][1]
    assert sum(c["id"] == m.Basic_Grass_Energy for c in mine["hand"]) == 1
    meganium = next(b for b in mine["bench"] if b and b["id"] == MEGANIUM)
    assert len(meganium["energies"]) == 2          # one attachment short
    assert len(mine["active"][0]["energies"]) == 0  # ...and the front cannot retreat


def test_with_the_finisher_in_front_the_last_grass_completes_it():
    obs = _attach_obs(promote_meganium=True)
    assert _attach_target(obs, m.agent(obs)) == MEGANIUM
