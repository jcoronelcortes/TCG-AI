"""The Supporter went to the refill while their hand sat at ten cards.

Scenario (user, `records/registro_006_pasos_062_hasta_085.json`, episode
91851762, step 71, turn 6 vs Alakazam -- LOST):

    US (6 prizes)                          RIVAL (5 prizes, TEN cards in hand)
    active  Tapu Bulu 140/140, NO energy   active  Tapu Bulu... no: Dipplin 140
    bench   Ogerpon ex x2, Meowth ex,      bench   Alakazam line
            Applin
    hand    Meganium, Lillie's             (our Supporter slot still FREE)
            Determination, Xerosic's
            Machinations

Our active had just been promoted after a knockout with nothing attached, so
there was no attack this turn under any line. The menu was exactly {play
Lillie's Determination, play Xerosic's Machinations, end turn} and the agent
spent the turn's Supporter on the **Lillie's**:

    [reglas xerosic->play] alakazam_yields_to_lillie_short_hand=20
    [reglas lillie->play]  refresh_short_hand=5000

`alakazam_yields_to_lillie_short_hand` is the rule, and its premise was never
wrong -- "no attack and a short hand: development is worth more than
disruption". What it never did was ask HOW BIG THEIR HAND WAS. Powerful Hand
reads 20 x (their hand + 2), so at ten cards it was projecting 240 and the cap
would have taken it to 100. The rule answered the same thing at six cards and at
twenty, and between the two the card stops being a luxury and becomes the
matchup.

THE FIX is the reading, not the rule: `op_hand_count < XEROSIC_BIG_HAND`. No new
number -- that is the ONE constant the play scorer (`generic_very_big_hand`,
which pays 3380 for the cap from seven cards up) and the discard scorer
(`DISCARD_XEROSIC_CAPS_A_FAT_HAND`, which stops treating it as fodder at the
same seven) already share. A card we refuse to throw away cannot be a card we
refuse to play.

With `_xr_gate_alakazam` imposing its floor of six, the yield now lives in
exactly ONE window -- an opposing hand of six, where the cap discards three
cards and the refill really is worth more -- and above it the cap takes the turn
while the Lillie's waits for the next one. It is the same blind spot that got
`alakazam_yields_to_lillie_tiny_opponent_hand` removed in August 2026, read from
the other end of the same axis.
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
from ptcg.cards import ids
from ptcg.decision.disruption import _RULES_XEROSIC_PLAY

XEROSIC = m.Xerosic_Machinations
LILLIE = m.Lillie_Determination
MEGANIUM = m.Meganium

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_step71_the_cap_takes_the_turn_we_cannot_attack.json")


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


def _record_obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _hand_ids(obs):
    yo = obs["current"]["yourIndex"]
    return [c["id"] for c in obs["current"]["players"][yo]["hand"]]


def _played(obs, choice):
    o = obs["select"]["option"][choice[0]]
    if o["type"] != int(m.OptionType.PLAY):
        return None
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["hand"][o["index"]]["id"]


def _rule(name):
    return next(r for r in _RULES_XEROSIC_PLAY if r.name == name)


class _Ctx:
    """The fields this one rule reads, and nothing else -- the house shape for
    a predicate test (`plan_of` answers `NO_PLAN` for a context without one)."""

    def __init__(self, *, op_hand_count, hand_counts, active_cant_attack=True,
                 op_is_alakazam_deck=True):
        self.op_hand_count = op_hand_count
        self.hand_counts = hand_counts
        self.active_cant_attack = active_cant_attack
        self.op_is_alakazam_deck = op_is_alakazam_deck


# ---------------------------------------------------------------------------
# 1. The record's own board
# ---------------------------------------------------------------------------

def test_the_record_spends_the_supporter_on_the_cap():
    obs = _record_obs()
    assert sorted(_hand_ids(obs)) == sorted([MEGANIUM, LILLIE, XEROSIC])
    assert obs["current"]["players"][0]["handCount"] == 10
    assert obs["current"]["supporterPlayed"] is False

    assert _played(obs, m.agent(obs)) == XEROSIC, (
        "con su mano a 10 (Powerful Hand proyectando 240) y sin ataque posible, "
        "el turno es del cap, no del refill")


# ---------------------------------------------------------------------------
# 2. The rule's own predicate: where the yield still lives
# ---------------------------------------------------------------------------

def test_the_yield_survives_at_the_floor_of_six():
    """The window the rule was written for is untouched: at six cards the cap
    discards three and the refill really is the better turn."""
    assert _rule("alakazam_yields_to_lillie_short_hand").when(
        _Ctx(op_hand_count=6, hand_counts={XEROSIC: 1, LILLIE: 1, MEGANIUM: 1}))


def test_the_yield_stops_at_the_shared_constant():
    """`XEROSIC_BIG_HAND` and not a number of its own: it is the same threshold
    the play scorer and the discard scorer already read."""
    assert ids.XEROSIC_BIG_HAND == 7
    for _op_hand in (ids.XEROSIC_BIG_HAND, 10, 18):
        assert not _rule("alakazam_yields_to_lillie_short_hand").when(
            _Ctx(op_hand_count=_op_hand,
                 hand_counts={XEROSIC: 1, LILLIE: 1, MEGANIUM: 1})), (
            f"con su mano en {_op_hand} el cap ya se paga su propio Supporter")


def test_the_other_clauses_are_untouched():
    """The reading is ADDED, it replaces nothing: a hand of four, an active that
    can attack, no Lillie's or another deck across the table each still cancel
    the yield on their own."""
    _short = {XEROSIC: 1, LILLIE: 1, MEGANIUM: 1}
    _yield = _rule("alakazam_yields_to_lillie_short_hand").when
    assert _yield(_Ctx(op_hand_count=6, hand_counts=_short))
    assert not _yield(_Ctx(op_hand_count=6,
                           hand_counts={XEROSIC: 1, LILLIE: 1, MEGANIUM: 2}))
    assert not _yield(_Ctx(op_hand_count=6, hand_counts=_short,
                           active_cant_attack=False))
    assert not _yield(_Ctx(op_hand_count=6,
                           hand_counts={XEROSIC: 1, MEGANIUM: 1}))
    assert not _yield(_Ctx(op_hand_count=6, hand_counts=_short,
                           op_is_alakazam_deck=False))


# ---------------------------------------------------------------------------
# 3. The board, moved to the window where the yield still holds
# ---------------------------------------------------------------------------

def test_at_six_cards_the_record_board_still_plays_the_refill():
    """Same board, their hand cut to the floor: the Lillie's takes the turn
    again. The fix is a boundary, not a reversal."""
    obs = _record_obs()
    obs["current"]["players"][0]["handCount"] = 6
    assert _played(obs, m.agent(obs)) == LILLIE
