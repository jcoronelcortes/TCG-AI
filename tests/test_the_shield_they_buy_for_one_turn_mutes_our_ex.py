"""Seven turns swinging into a wall that was never on the board.

THE GAME (user, episode 93163758 vs a Comfey/Chandelure deck -- LOST holding ONE
prize while they never left six). From turn 13 onward their board never changed:

    US (2 prizes, then 1)                 THEM (6 prizes)
    active  Teal Mask Ogerpon ex, 3 Grass  active  Comfey 70/70, 1 energy
    bench   Teal Mask Ogerpon ex, 7 Grass  bench   Chandelure 130, Chandelure 130
            ... and 9, and 10
    hand    BOSS'S ORDERS, Applin, Dipplin,
            Forest of Vitality, two Grass

Myriad Leaf Shower is 30 + 30 per energy, so every projection in this agent said
the Comfey died and `prizes_today` said one. The engine said otherwise:

    turn 13  `{"type": 16, "serial": 66, "value": 0}`
    turn 15  `{"type": 16, "serial": 66, "value": 0}`
    turn 19  `{"type": 16, "serial": 75, "value": 0}`

ACEROLA'S MISCHIEF (1228), played on their turn, every turn: "you can use this
card only if your opponent has 2 or fewer Prize cards remaining. Choose 1 of your
Pokemon in play. During your opponent's next turn, prevent all damage from and
effects of attacks done to that Pokemon by your opponent's Pokemon ex." Three
copies -- serials 120, 122 and 121 -- and its own text says when it arrives: at
two prizes, which is the turn the game is decided.

WHY NOTHING SAW IT. This agent knows three walls and reads all three off the
board: Crustle (`EX_IMMUNE_IDS`), Cornerstone (`ABILITY_IMMUNE_IDS`) and
Neutralization Zone (the missing Rule Box under a stadium anyone can see). This
one leaves NOTHING behind -- no tool, no ability, no stadium, and the protected
body looks exactly like the body it was. The single piece of evidence is the PLAY
log of their turn, which goes past once, in the batch that closes it.

AND THE ANSWER WAS IN HAND THE WHOLE TIME, because the shield is pinned to ONE
body and travels with it: Boss's Orders on a Chandelure leaves the Comfey
shielded on the bench and a 130 HP body in front that our ex may hit freely. One
prize with the active as it stood, and with the ten-energy twin promoted, the
game.

WHAT THE READING CHANGES, in flips over the recorded episode (7, all of them in
it, and 0 over the fifty frozen games -- the card appears in none of them):

    turn 13   dance on the BENCH, attack for 0   ->  dance on the ACTIVE, gust, KO
    turn 15   attack for 0                       ->  PLAY Boss's Orders
    turn 19   attack for 0 as action ONE         ->  spend the turn, then end it

The third one is the cost stated plainly: an attack ENDS THE TURN, so swinging
into the shield does not merely fail to knock anything out, it throws away every
card still in hand -- thirteen of them on that step.
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
from ptcg.calc.damage import (_our_effective_damage, _shield_mutes_our_ex,
                              _wall_mutes_our_ex)

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "comfey_step107_the_shield_they_buy_for_one_turn.json")
_TURN15 = (ROOT / "tests" / "fixtures"
           / "comfey_step118_the_gust_answers_the_shield.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
COMFEY_SERIAL = 66
# Their Chandelure: 130 HP, no Rule Box, and not a card this agent has ever had
# to name, so it travels here as the id the observation carries.
CHANDELURE = 98
CHANDELURE_HP = 130


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.AGENT_STATE.reset()
    yield
    m._init_cards_tracking()
    m.AGENT_STATE.reset()


def _obs(path=_FIXTURE):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _menus(path=_TURN15):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["menus"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _opponent(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _index_of(obs, option_type):
    return next(i for i, opt in enumerate(obs["select"]["option"])
                if opt["type"] == int(option_type))


def _card_option(obs, card_id):
    """The menu index that PLAYS `card_id` out of our hand."""
    hand = _mine(obs)["hand"]
    for i, opt in enumerate(obs["select"]["option"]):
        if (opt["type"] == int(m.OptionType.PLAY)
                and opt.get("index") is not None
                and opt["index"] < len(hand)
                and hand[opt["index"]]["id"] == card_id):
            return i
    raise AssertionError(f"{card_id} is not playable on this menu")


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


class _Body:
    """A Pokemon the damage model can price, with a serial and nothing else."""

    def __init__(self, card_id, serial, hp=130):
        self.id = card_id
        self.serial = serial
        self.hp = hp
        self.maxHp = hp
        self.energies = []
        self.energyCards = []
        self.tools = []


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_board_where_the_shield_is_up():
    obs = _obs()
    mine, opponent = _mine(obs), _opponent(obs)

    # Their turn is in the logs and it carries the Supporter.
    played = [lg for lg in obs["logs"]
              if lg.get("type") == int(m.LogType.PLAY)
              and lg.get("cardId") in m.OP_EX_SHIELD_IDS
              and lg.get("playerIndex") != obs["current"]["yourIndex"]]
    assert len(played) == 1, obs["logs"]

    # Its own precondition holds: we are at two prizes.
    assert len(mine["prize"]) <= m.OP_EX_SHIELD_MAX_PRIZES

    # The body it is pinned on is in front, and it is the one our attack reads
    # as dead: 70 HP against a Myriad Leaf Shower of 30 + 30 per energy.
    assert opponent["active"][0]["serial"] == COMFEY_SERIAL
    assert opponent["active"][0]["hp"] == 70
    assert mine["active"][0]["id"] == OGERPON
    assert OGERPON in m.OUR_EX_IDS

    # ...and the answer is in hand, with two unshielded bodies to aim it at.
    assert any(c["id"] == m.Boss_Orders for c in mine["hand"])
    assert [b["hp"] for b in opponent["bench"]] == [CHANDELURE_HP, CHANDELURE_HP]


def test_the_reading_pins_a_serial_and_a_turn():
    obs = _obs()
    m.agent(obs)
    assert m.AGENT_STATE.op_ex_shield_serial == COMFEY_SERIAL
    assert m.AGENT_STATE._op_ex_shield_turn == obs["current"]["turn"]
    # ...and that this deck holds the card, which outlives the turn.
    assert m.AGENT_STATE.op_has_ex_shield is True


# ---------------------------------------------------------------------------
# 2. The number the whole turn hangs on
# ---------------------------------------------------------------------------

def test_our_ex_reads_zero_into_the_shielded_body():
    m.AGENT_STATE.op_ex_shield_serial = COMFEY_SERIAL
    shielded = _Body(m.Comfey, COMFEY_SERIAL, hp=70)
    assert _our_effective_damage(_Body(OGERPON, 6, 210), shielded, 180) == 0


def test_the_shield_says_nothing_about_our_non_ex():
    """The card names our ex and only our ex: a Dipplin in the same spot goes
    through it untouched, which is the whole of the second answer to it."""
    m.AGENT_STATE.op_ex_shield_serial = COMFEY_SERIAL
    shielded = _Body(m.Comfey, COMFEY_SERIAL, hp=70)
    assert _our_effective_damage(_Body(m.Dipplin, 9, 80), shielded, 80) == 80


def test_the_shield_travels_with_the_body_and_not_with_the_spot():
    """The answer to the card depends on this: gust the shielded body away and
    the Pokemon that comes up in its place is ours to knock out."""
    m.AGENT_STATE.op_ex_shield_serial = COMFEY_SERIAL
    other = _Body(CHANDELURE, 75, hp=CHANDELURE_HP)
    assert _shield_mutes_our_ex(other) is False
    assert _our_effective_damage(_Body(OGERPON, 6, 210), other, 180) == 180


def test_a_body_without_a_serial_is_not_shielded():
    """Synthetic Pokemon and unreadable data take the same direction the
    stadium's sibling takes: we do not switch our own attackers off on evidence
    we do not have."""
    m.AGENT_STATE.op_ex_shield_serial = COMFEY_SERIAL
    nameless = _Body(CHANDELURE, None)
    assert _shield_mutes_our_ex(nameless) is False
    assert _shield_mutes_our_ex(None) is False


def test_the_routing_reads_both_walls_through_one_name():
    """`_wall_mutes_our_ex` is what the energy routing asks, and the two
    predicates it joins keep their own switches."""
    m.AGENT_STATE.op_ex_shield_serial = COMFEY_SERIAL
    assert _wall_mutes_our_ex(_Body(m.Comfey, COMFEY_SERIAL, 70), False) is True
    assert _wall_mutes_our_ex(_Body(m.Comfey, 999, 70), False) is False


# ---------------------------------------------------------------------------
# 3. The decision, and the turn behind it
# ---------------------------------------------------------------------------

def test_it_does_not_swing_into_the_shield():
    obs = _obs()
    scores = _scores(obs)
    assert scores[_index_of(obs, m.OptionType.ATTACK)] <= 0, scores
    assert (obs["select"]["option"][m.agent(_obs())[0]]["type"]
            != int(m.OptionType.ATTACK))


def test_the_turn_spends_the_supporter_on_a_body_the_shield_does_not_cover():
    """Turn 15, the three menus of the record in order. On the last one the
    agent used to attack for zero; the Boss's Orders was in hand on all three."""
    menus = _menus()
    for obs in menus[:-1]:
        m.agent(copy.deepcopy(obs))
    last = menus[-1]
    choice = m.agent(copy.deepcopy(last))
    assert choice[0] == _card_option(last, m.Boss_Orders), (
        last["select"]["option"][choice[0]])


# ---------------------------------------------------------------------------
# 4. The forced discard: the hand their cap leaves us
# ---------------------------------------------------------------------------

def _forced_discard_menu(obs, hand_ids):
    """Their Xerosic's Machinations cutting our hand down, as the engine asks
    it: a DISCARD context whose `effect` belongs to THEM."""
    obs = copy.deepcopy(obs)
    # No logs: a forced discard arrives in its own batch, and the shield has
    # already been read off the one that carried it (`op_has_ex_shield`).
    obs["logs"] = []
    mine = _mine(obs)
    mine["hand"] = [{"id": cid, "playerIndex": 0, "serial": 900 + i}
                    for i, cid in enumerate(hand_ids)]
    mine["handCount"] = len(hand_ids)
    obs["select"] = {
        "context": int(m.SelectContext.DISCARD), "contextCard": None,
        "deck": None, "maxCount": 1, "minCount": 1, "remainDamageCounter": 0,
        "remainEnergyCost": 0, "type": 1,
        "effect": {"id": m.Xerosic_Machinations, "playerIndex": 1, "serial": 7},
        "option": [{"area": 2, "index": i, "playerIndex": 0, "type": 3}
                   for i in range(len(hand_ids))],
    }
    return obs


_CAP_HAND = [m.Teal_Mask_Ogerpon_ex, m.Hydrapple_ex, m.Forest_of_Vitality,
             m.Ultra_Ball, m.Basic_Grass_Energy, m.Boss_Orders, m.Applin,
             m.Dipplin]


def test_their_cap_eats_the_ex_before_the_answer_to_the_shield():
    obs = _obs()
    m.agent(obs)                      # the shield is read off the logs here
    menu = _forced_discard_menu(obs, _CAP_HAND)
    scores = _scores(menu)
    by_card = dict(zip(_CAP_HAND, scores))

    # The three the shield makes expendable, in the order they are given up.
    assert by_card[m.Teal_Mask_Ogerpon_ex] > by_card[m.Forest_of_Vitality]
    assert by_card[m.Forest_of_Vitality] > by_card[m.Ultra_Ball]
    assert by_card[m.Hydrapple_ex] == by_card[m.Teal_Mask_Ogerpon_ex]

    # ...and the four that answer it, all of them kept under everything above.
    for kept in (m.Boss_Orders, m.Basic_Grass_Energy, m.Applin, m.Dipplin):
        assert by_card[kept] < by_card[m.Ultra_Ball], (kept, by_card)
    # The gust is the cheapest answer there is, so it is the last card to go.
    assert by_card[m.Boss_Orders] <= min(by_card[c] for c in
                                         (m.Basic_Grass_Energy, m.Applin,
                                          m.Dipplin))


def test_the_reordering_needs_the_shield_and_their_card_playing_it():
    """Off this matchup the hand is priced as it always was. Checked the only
    way that cannot lie: with the flag the reading itself sets."""
    obs = _obs()
    m.agent(obs)
    menu = _forced_discard_menu(obs, _CAP_HAND)
    with_shield = dict(zip(_CAP_HAND, _scores(menu)))
    m.AGENT_STATE.op_has_ex_shield = False
    without = dict(zip(_CAP_HAND, _scores(menu)))
    assert without[m.Teal_Mask_Ogerpon_ex] < with_shield[m.Teal_Mask_Ogerpon_ex]
    assert without[m.Boss_Orders] > with_shield[m.Boss_Orders]


# ---------------------------------------------------------------------------
# 5. The controls: what the reading must NOT move
# ---------------------------------------------------------------------------

def test_without_their_play_in_the_logs_nothing_changes():
    """The same board, minus the one line that is the whole evidence: the agent
    goes back to reading the Comfey as a body it can knock out."""
    obs = _obs()
    obs["logs"] = [lg for lg in obs["logs"]
                   if lg.get("cardId") not in m.OP_EX_SHIELD_IDS]
    scores = _scores(obs)
    assert m.AGENT_STATE.op_ex_shield_serial is None
    assert scores[_index_of(obs, m.OptionType.ATTACK)] > 0, scores


def test_the_shield_expires_with_the_turn_it_bought():
    """Their Supporter buys ONE of our turns. Read on the batch that already
    closes their turn it governs this one, and nothing after it."""
    obs = _obs()
    m.agent(obs)
    assert m.AGENT_STATE.op_ex_shield_serial == COMFEY_SERIAL
    later = _obs()
    later["logs"] = []
    later["current"]["turn"] += 2
    m.agent(later)
    assert m.AGENT_STATE.op_ex_shield_serial is None


def test_the_reading_is_switchable_and_the_switch_is_what_the_gate_flips():
    obs = _obs()
    import ptcg.calc.damage as dmg
    assert dmg.OP_EX_SHIELD_ROUTING is True
    dmg.OP_EX_SHIELD_ROUTING = False
    try:
        scores = _scores(_obs())
        assert scores[_index_of(obs, m.OptionType.ATTACK)] > 0, scores
    finally:
        dmg.OP_EX_SHIELD_ROUTING = True
    scores = _scores(_obs())
    assert scores[_index_of(obs, m.OptionType.ATTACK)] <= 0, scores
