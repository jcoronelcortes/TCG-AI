"""The Last-Ditch Catch fetched a gust for a turn that could not attack at all.

Scenario (user, `records/registro_008_pasos_046_hasta_054.json`, episode
92492874, turn 8 step 51 vs a **Crustle** deck -- LOST):

    US (6 prizes)                          RIVAL (5 prizes)
    active  Teal Mask Ogerpon ex           active  Crustle 170/170, 3 energies
            90/210, **ZERO energy**                (our ex cannot touch it)
    bench   Applin    40, **0 energy**     bench   Crustle 170, 1 energy
            Meganium 160, **0 energy**             Dwebble  70, 0 energy
            Teal Mask Ogerpon ex 210,
                      **0 energy**         stadium theirs
            Meowth ex 170 (just benched)
    hand    **EMPTY**

    energyAttached False, supporterPlayed False

An Ultra Ball had just spent the hand's last two cards to fetch the Meowth ex,
the Meowth went down, and its Last-Ditch Catch was asked which Supporter to
bring. It brought **Boss's Orders**, gusted their benched Crustle -- and the
very next menu of the record offers exactly ONE option: **END TURN**. Two
prizes of Meowth ex on the bench, an Ultra Ball, two discards and the turn's
only Supporter slot, all spent to rearrange the opponent's bench. Their reply
knocked our active over for two more prizes.

WHICH RULE, AND WHY IT WAS WRONG HERE. `boss_beats_the_untouchable_active`
(1270) beat `lillie_development` (1250). That rule is written around a true
sentence -- "their active cannot be touched, the body behind it can, so the
only Supporter that turns this turn into damage is Boss's Orders" -- and on
this board the sentence is false in its last clause: NOTHING of ours could pay
an attack cost. Four bodies at zero energy, an empty hand, and therefore no
manual attachment, no Teal Dance and no Ripening Charge either, because all
three take their Grass FROM HAND.

THE BLINDNESS IS THE SAME SHAPE AS THE ONE THE RULE WAS WRITTEN TO FIX, POINTING
THE OTHER WAY. `strong_attacker` is a SPECIES reading -- "is a Hydrapple ex or a
Teal Mask Ogerpon ex in play" -- so it was **True** on a board of four bodies at
zero energy, and every `no_attacker*` cap below stayed silent. The rule that
fires needs its own reading of whether an attack exists at all, and
`_a_body_can_attack_this_turn` is that reading: our own arithmetic over every
attack cost, the retreat of the body in front and the one Grass the turn can
still put down. No card names, no matchup list -- it answers the same against
every deck.

MEASUREMENT. Local records (`utils/log_replay.py`): exactly ONE divergence, this
step, Boss's Orders -> Lillie's Determination. Frozen corpus: zero further
flips. The board the rule came from (episode 90325863, a charged Hydrapple ex
whose Syrup Storm was resolving for zero against a hidden Marill) answers True
and is untouched -- see `test_the_coin_that_hides_the_marill.py`.
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
from rule_trace import reason, resolve

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_t8_the_gust_with_no_attack_step51.json")

BOSS = m.Boss_Orders
LILLIE = m.Lillie_Determination
GRASS = m.Basic_Grass_Energy
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    cur = o["current"]
    me = cur["players"][cur["yourIndex"]]
    if mut.get("grass_in_hand"):
        me["hand"] = (me["hand"] or []) + [
            {"id": GRASS, "playerIndex": 0, "serial": 900}]
        me["handCount"] = len(me["hand"])
    if mut.get("charged_active"):
        # Three Grass on the active Ogerpon ex: Myriad Leaf Shower is payable,
        # so the gust has a real attack behind it.
        me["active"][0]["energies"] = [7, 7, 7]
        me["active"][0]["energyCards"] = [
            {"id": GRASS, "playerIndex": 0, "serial": 910 + i} for i in range(3)]
    return o


def _fetched(obs):
    """The card id the Last-Ditch Catch brings out of the deck."""
    choice = list(m.agent(obs))
    opt = obs["select"]["option"][choice[0]]
    return obs["select"]["deck"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The record's board, end to end through `agent()`
# ---------------------------------------------------------------------------

def test_the_fetch_refills_the_hand_when_no_body_can_attack():
    """The record's own board: the fetch must bring the refill, not the gust."""
    assert _fetched(_obs()) == LILLIE


def test_the_same_board_with_an_attack_still_brings_the_gust():
    """The CONTROL, and the half that keeps the original rule alive.

    One thing changes -- three Grass on the active, so Myriad Leaf Shower is
    payable -- and the sentence the rule is built on becomes true again: their
    Crustle blanks our ex, their bench does not, and the gust is the only card
    that turns the turn into damage. The fetch has to go back to the Boss's.

    Without this the fix would be indistinguishable from deleting the rule.
    """
    assert _fetched(_obs(charged_active=True)) == BOSS


# ---------------------------------------------------------------------------
# 2. The rule, by name
# ---------------------------------------------------------------------------

def _value(card_id, *, gust_flag=True, can_attack=True, sv=None):
    ctx = m._CtxMeowthFetch(
        card_id,
        {BOSS: 740, LILLIE: 800}.get(card_id, 0) if sv is None else sv,
        {}, {LILLIE: 800}, 0, True, 5, True,
        False, False, False, True, False, False, True,
        gust_flag, False, 0, can_attack)
    return resolve(m._RULES_MEOWTH_FETCH, [], ctx, 50)


def test_the_rule_names_itself_on_both_sides_of_the_new_guard():
    """A renumbering must not be able to hide which rule decided."""
    seeing, why_seeing = _value(BOSS, can_attack=True)
    assert (seeing, reason(why_seeing)) == (
        1270, "boss_beats_the_untouchable_active"), (
        "with an attack behind it the gust still outranks the refill")

    blind, why_blind = _value(BOSS, can_attack=False)
    assert reason(why_blind) == "short_hand", (
        "with no attack behind it the gust falls to the generic caps -- it is "
        "not vetoed, because the prompt still forces us to pick a card")
    assert blind <= 100

    refill, why_refill = _value(LILLIE, can_attack=False)
    assert reason(why_refill) == "lillie_development"
    assert refill > blind, "and the refill is what the fetch ends up bringing"


def test_only_the_gust_reads_the_new_guard():
    """It is a guard on ONE rung, not a new cap over the whole ladder."""
    for flag in (True, False):
        assert _value(LILLIE, can_attack=flag)[0] == 1250
        assert _value(m.Lanas_Aid, can_attack=flag, sv=950)[0] == \
            _value(m.Lanas_Aid, can_attack=not flag, sv=950)[0]


# ---------------------------------------------------------------------------
# 3. The reading itself: `_a_body_can_attack_this_turn`
# ---------------------------------------------------------------------------

class _Pk:
    def __init__(self, card_id, energies=0, cards=0):
        self.id = card_id
        self.energies = [7] * energies
        self.energyCards = [type("C", (), {"id": GRASS})()
                            for _ in range(cards or energies)]
        self.serial = card_id


class _Me:
    def __init__(self, active=None, bench=()):
        self.active = [active] if active is not None else []
        self.bench = list(bench)
        self.hand = []


class _St:
    def __init__(self, energy_attached=False):
        self.energyAttached = energy_attached


def _can(me, hand=None, energy_attached=False, field=None):
    return m._a_body_can_attack_this_turn(
        me, _St(energy_attached), hand or {}, field or {})


def test_the_reading_says_no_on_a_board_of_empty_bodies():
    """The record's board, reduced to its arithmetic: four bodies at zero
    energy and an empty hand. Nothing reaches a cost, this turn or at all."""
    me = _Me(_Pk(OGERPON), [_Pk(m.Applin), _Pk(MEGANIUM), _Pk(OGERPON)])
    assert _can(me) is False


def test_the_turns_attachment_counts_but_only_with_a_card_and_a_route():
    """One Grass short is a plan; one Grass short with an empty hand is not.

    The three ways to spend a Grass -- the manual attachment, Teal Dance and
    Ripening Charge -- all take it FROM HAND, so the card and the route are two
    separate questions and the reading has to ask both.
    """
    me = _Me(_Pk(OGERPON, energies=2))          # Myriad Leaf Shower costs 3
    assert _can(me) is False, "no Grass in hand: nothing to attach"
    assert _can(me, hand={GRASS: 1}) is True, "one attachment away, and it is free"
    assert _can(me, hand={GRASS: 1}, energy_attached=True) is False, (
        "the card is there but the turn's attachment is spent and no charging "
        "ability is in play")


def test_a_charged_body_at_the_back_needs_the_front_to_step_aside():
    """`listo != utilizable`: a body that cannot reach the front is not an
    attacker, which is the same reading three other routes already make."""
    charged = _Pk(OGERPON, energies=3)
    # Meganium's retreat is payable only with energy on it.
    assert _can(_Me(_Pk(MEGANIUM), [charged])) is False
    assert _can(_Me(_Pk(MEGANIUM, energies=2), [charged])) is True


def test_the_body_that_is_the_attack_can_still_be_in_hand():
    """The energy travels UP with the evolution, so a body that cannot attack
    today can be an attack today anyway.

    Bayleef is deliberately the pre-evolution used here: it is not in
    `MAIN_ATTACKERS` at all, so the only thing that can make this board answer
    True is the evolution branch -- there is no neighbouring reason to pass for.
    """
    bayleef = _Me(_Pk(m.Bayleef, energies=2))
    assert _can(bayleef) is False, (
        "the control: a Bayleef is not an attacker, however charged it is")
    assert _can(bayleef, hand={MEGANIUM: 1}) is True, (
        "with the Meganium in hand those TWO physical Grass are Solar Beam: "
        "Wild Growth switches on with the evolution itself and doubles what is "
        "already underneath it (`energy_after_evolution`), so 2 -> 4 = the cost")
    assert _can(_Me(_Pk(m.Bayleef, energies=1)), hand={MEGANIUM: 1}) is False, (
        "and the arithmetic still has to add up: one Grass doubles to two, "
        "and nothing in hand can attach a second")
