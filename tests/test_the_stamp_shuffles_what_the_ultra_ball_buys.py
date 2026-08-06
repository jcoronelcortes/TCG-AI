"""The Unfair Stamp shuffles back whatever the Ultra Ball leaves in HAND.

Scenario (`records/registro_008_pasos_070_hasta_091.json`, step 70, turn 8,
episode 90090825 vs Marnie's Grimmsnarl -- WON in spite of this):

    US (6 prizes)                             RIVAL (5 prizes)
    active  Teal Mask Ogerpon ex 210, 3 {G}   active  Archaludon ex 320, 2 energy
    bench   Teal Mask Ogerpon ex 210, 1 {G}   bench   Duraludon x4, Duraludon(pre)
            Teal Mask Ogerpon ex 210, 1 {G}   hand    **6 cards**
            Chikorita 70
    hand    **Unfair Stamp**, Lana's Aid, Dipplin, Hydrapple ex,
            Night Stretcher, **Ultra Ball**
    one of ours was KNOCKED OUT last turn -> the Stamp is playable

The agent played the Ultra Ball, paid its cost with the Night Stretcher and the
Dipplin, fetched **Meowth ex**... and then played the Unfair Stamp, which
shuffles every hand into its deck. The Meowth ex went back to the deck without
ever touching the board. Three cards -- the Item and its two discards -- bought
nothing at all.

*"Each player shuffles their hand into their deck. Then, you draw 5 cards and
your opponent draws 2 cards."*

The seam was between the two halves of the Ultra Ball, which asked different
questions:

  * the SCORE already knew about the Stamp. `_eval_ub_best_target` gates the
    whole Meowth chain behind `_stamp_blocks_supp_chain`, so the 12250 that won
    the menu came from a different branch entirely: the Fezandipiti ex refill
    after a knockout (`refill_after_a_ko`, 1050);
  * the FETCH did not. `_RULES_UB_MEOWTH` ranked Meowth ex at 1000
    (`lillie_in_deck_refresh`) and, worse, the `no_attacker_prefer_meowth`
    premise pushed Fezandipiti ex down to its default of 10 -- so the Ultra
    Ball was spent on the one target its own score had already refused.

TWO RULES, both of the CARD and neither naming a matchup (the Stamp reads the
same against any opposing deck):

1. **`the_stamp_shuffles_the_last_ditch_supporter`** (`_RULES_UB_MEOWTH`): a
   third way for the Last-Ditch Catch to produce nothing, alongside "the
   Supporter is already spent" and "the Watchtower cancels the ability" -- only
   this one lives in the ORDER of the turn rather than on the board. With a
   Stamp that is going to be played (`_stamp_pendiente`) every `_SUPP_PLAY_IDS`
   scorer yields the turn to it, so no Supporter the Last-Ditch could bring is
   playable before the shuffle. It sits ABOVE `item_lock_tomorrow`: "tomorrow"
   never arrives for a card the Stamp returns to the deck today, and the score
   branch that buys the Ultra Ball for that purchase
   (`_ub_meowth_for_tomorrow`) is gated with it so both halves agree.

2. **The four `*_prefer_meowth` premises yield too** (ptcg/turn/options/card.py).
   They all state the same thing -- "the Meowth ex -> Last-Ditch -> Lillie's
   engine refills better than the body this fetch would otherwise bring" -- and
   each one SUPPRESSES a rival target (Ogerpon, Hydrapple, Meganium,
   Fezandipiti). With the engine unavailable the premise is false, and leaving
   it on is what made the Ultra Ball veto the very target it had been bought
   for.

What the rules do NOT say is "never play an Item before the Stamp". A card the
Ultra Ball puts on the BOARD is safe from the shuffle -- and emptying the hand
before the Stamp is exactly what makes its refresh clause pay
(`_stamp_worth_playing`). What is lost is what stays in HAND. With the fix the
turn reads: Ultra Ball -> fetch Fezandipiti ex -> put it down -> Unfair Stamp
-> Flip the Script, and nothing bought is shuffled away.
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

_FIX = ROOT / "tests" / "fixtures"
_STEP70 = _FIX / "marnie_t8_the_stamp_shuffles_what_the_ultra_ball_buys_step70.json"
_STEP72 = _FIX / "marnie_t8_the_ultra_ball_fetch_under_a_pending_stamp_step72.json"
_CONTROL = _FIX / "marnie_t8_the_ultra_ball_fetch_without_the_stamp_control_step72.json"


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
    m._ub_meowth_pending = False
    yield
    m._init_cards_tracking()


def _obs(path):
    return copy.deepcopy(json.load(open(path, encoding="utf-8"))["observation"])


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _fetched_id(obs):
    """The card id the Ultra Ball's search brings to hand."""
    chosen = m.agent(copy.deepcopy(obs))
    option = obs["select"]["option"][chosen[0]]
    return obs["select"]["deck"][option["index"]]["id"]


# ---------------------------------------------------------------------------
# The board of the record
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_turn_after_the_knockout_with_a_playable_stamp():
    obs = _obs(_STEP70)
    cur = obs["current"]
    mine = _mine(obs)

    assert cur["turn"] == 8 and not cur["supporterPlayed"]
    assert [c["id"] for c in mine["hand"]] == [
        m.Unfair_Stamp, m.Lanas_Aid, m.Dipplin, m.Hydrapple_ex,
        m.Night_Stretcher, m.Ultra_Ball]
    # The Stamp DISRUPTS: it leaves them at 2, so with 6 in hand it denies four.
    assert cur["players"][1 - cur["yourIndex"]]["handCount"] >= m.STAMP_MIN_OP_HAND
    # Both halves of the seam are in the menu: the Ultra Ball and the Stamp.
    hand_plays = [o["index"] for o in obs["select"]["option"]
                  if o["type"] == int(m.OptionType.PLAY)]
    played = {mine["hand"][i]["id"] for i in hand_plays}
    assert {m.Ultra_Ball, m.Unfair_Stamp} <= played

    # The promotion after the knockout is in the log, so a single observation is
    # enough to derive `ko_last_turn` -- the condition the Stamp is played on.
    m.agent(obs)
    assert m.ko_last_turn


# ---------------------------------------------------------------------------
# The rule: the search does not buy what the Stamp is about to shuffle
# ---------------------------------------------------------------------------

def test_the_search_does_not_buy_the_meowth_the_stamp_will_shuffle():
    assert _fetched_id(_obs(_STEP72)) != m.Meowth_ex, (
        "con un Unfair Stamp por jugar, el Meowth ex cavado vuelve al mazo "
        "antes de que su Last-Ditch pueda traer nada: la Ultra Ball y sus dos "
        "descartes se pagarian por una carta que no se juega")


def test_the_search_buys_the_body_the_ultra_ball_was_scored_for():
    """The score won the menu with `refill_after_a_ko` (Fezandipiti ex, 1050);
    the fetch has to spend the Item on that same body, which goes to the BOARD
    and therefore survives the shuffle."""
    assert _fetched_id(_obs(_STEP72)) == m.Fezandipiti_ex


# ---------------------------------------------------------------------------
# The control: with no Stamp the Meowth engine wins the search back
# ---------------------------------------------------------------------------

def test_without_a_playable_stamp_the_meowth_engine_keeps_the_search():
    """The same board, the same knockout, the Stamp removed from hand. If the
    fetch still refused Meowth ex the rule would be vetoing the engine itself
    instead of its ORDER."""
    control = _obs(_CONTROL)
    assert m.Unfair_Stamp not in [c["id"] for c in _mine(control)["hand"]]
    assert _fetched_id(control) == m.Meowth_ex
