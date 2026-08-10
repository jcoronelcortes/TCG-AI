"""A forced discard is priced by OUR next turn, not by what the opponent spent.

Found by reading the `SelectContext.DISCARD` block after the step-99 loss
(`tests/test_the_forced_discard_keeps_the_counter_stadium.py`) and confirmed by
running it. That one menu serves two callers with opposite time horizons:

  * the COST of our own Ultra Ball -- our turn, and "what does the hand still
    have to spend TODAY" is exactly the right question;
  * a discard FORCED by their card -- Xerosic's Machinations cuts us to three --
    which happens on THEIR turn. The hand that survives is the hand we START our
    next turn with.

The block could not tell them apart, and three findings came out of that.

1. THE TURN-SCOPED FLAGS WERE THE OPPONENT'S. Measured on the step-99
   observation: `supporterPlayed=True`, `energyAttached=True`. Both describe what
   THEY spent. The block reads them as ours, and `_protect_last_supporter` is
   gated on `not state.supporterPlayed` -- while Xerosic's Machinations IS a
   Supporter, so that flag is always True by the time we are asked. The
   protection of our last playable Supporter was dead code on every forced
   discard the agent had ever answered.

2. A PLAY-CONTEXT SENTENCE WAS PRICING A DISCARD. The Night Stretcher branch
   opened with "if the only recoverable target is basic Energy we cannot use this
   turn, `SCORE_VETO`". In the PLAY scorer that means "do not play it". Here the
   scale is inverted: a NEGATIVE score means "keep this above everything", second
   only to the Unfair Stamp. The branch handed its strongest protection to the
   card it had just judged useless -- measured at -1, ranked above the last
   playable Supporter (5) and above the critical counter-stadium (2), the one
   card that lifts a Neutralization Zone. It had been there since the first
   commit and no test covered it. It is deleted rather than re-signed: the
   reading survives neither caller (on a forced discard the spent attachment is
   theirs; on an Ultra Ball cost the pile it measures is about to be fed by the
   cost itself).

3. TWO PROTECTIONS, AND THE LADDER TESTED THE WEAKER ONE FIRST. `Lillie's` and
   `Dawn` both check "the last Supporter I can still play" before "the last
   refill", and score it HIGHER -- so a card satisfying both came out less
   protected for having one more reason to be kept. Invisible while finding 1
   kept the first gate dead; the moment the horizon read revived it, the frozen
   corpus caught a Lillie's Determination falling against the Crustle wall.

And the seat, once more: `Meowth ex` was priced fodder by
`bench_count >= 5 and supporterPlayed`. The two halves are not the same claim --
the spent slot only says the Last-Ditch chain cannot cash out today, while the
FULL BENCH says the card cannot enter play at all, this turn or the next. Only
the second half makes the copy dead, and it is the question
`_ub_target_has_no_seat` already asks before the Ultra Ball will pay two cards
for a body.

None of this names a card: the discriminator asks whose card is making us
discard, so it holds for any opposing hand-cutter.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m  # noqa: E402
from patching import instalar  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_t6_forced_discard_keeps_the_counter_stadium_step99.json")

FOREST = m.Forest_of_Vitality
NS = m.Night_Stretcher
LANA = m.Lanas_Aid
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex


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
    yield
    m._init_cards_tracking()


def _load(strip_pokemon_from_discard=False):
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    previa = copy.deepcopy(data["observacion_previa"])
    dec = copy.deepcopy(data["observation"])
    if strip_pokemon_from_discard:
        # The board the Night Stretcher branch was written about: nothing but
        # basic Energy and trainers to recover, so its "dead energy" reading is
        # TRUE. The record's own pile holds a Tapu Bulu and a Bayleef, which is
        # why the misfire never showed up there.
        for obs in (previa, dec):
            us = obs["current"]["players"][1]
            us["discard"] = [
                c for c in us["discard"]
                if not (m.card_table.get(c["id"]) is not None
                        and m.card_table[c["id"]].cardType == m.CardType.POKEMON)]
    return previa, dec


def _scores_and_action(strip_pokemon_from_discard=False):
    """The score of every option of the DISCARD menu, and the choice."""
    seen = {}
    orig = m._debug_log_decision

    def spy(context, select, scores, obs_, my_index, top_n=3):
        if int(context) == int(m.SelectContext.DISCARD):
            seen["scores"] = list(scores)
        return orig(context, select, scores, obs_, my_index, top_n)

    previa, dec = _load(strip_pokemon_from_discard)
    restore = instalar("_debug_log_decision", spy)
    try:
        m.agent(previa)
        action = m.agent(dec)
    finally:
        restore()
    hand = dec["current"]["players"][1]["hand"]
    by_id = {}
    for i, card in enumerate(hand):
        by_id.setdefault(card["id"], []).append(seen["scores"][i])
    return by_id, action, [hand[i]["id"] for i in action]


# ---------------------------------------------------------------------------
# The premise: this menu is on the OPPONENT's turn
# ---------------------------------------------------------------------------

def test_the_flags_of_this_observation_belong_to_the_opponent():
    """Which is what made the block price our hand by resources we never spent."""
    _, dec = _load()
    cur = dec["current"]
    assert dec["select"]["effect"]["playerIndex"] != cur["yourIndex"]
    # Xerosic's Machinations IS a Supporter, so this is True on every forced
    # discard it produces -- there is no board where the old gate could fire.
    assert cur["supporterPlayed"] is True
    assert cur["energyAttached"] is True


# ---------------------------------------------------------------------------
# 1. The last playable Supporter is protected again
# ---------------------------------------------------------------------------

def test_the_last_supporter_is_protected_on_a_forced_discard():
    """Lana's Aid is the only Supporter in that hand, and next turn we can play it.

    `_protect_last_supporter` prices it at 12; the static `len(discard) > 2`
    branch it used to fall through to prices it at 35. The gate was unreachable
    on a forced discard before, so the number is the whole assertion.
    """
    scores, _, _ = _scores_and_action()
    assert scores[LANA] == [12], (
        "the last Supporter of the hand must be priced by the slot that is FREE "
        f"next turn, not by the one the opponent spent: got {scores[LANA]}")


# ---------------------------------------------------------------------------
# 2. The Night Stretcher is not treasure for having nothing to fetch
# ---------------------------------------------------------------------------

def test_the_stretcher_with_nothing_to_fetch_is_not_the_most_protected_card():
    scores, _, _ = _scores_and_action(strip_pokemon_from_discard=True)
    assert scores[NS][0] > 0, (
        "a negative score in this context means 'keep above everything'; the "
        f"Stretcher must not be priced there: got {scores[NS]}")


def test_the_counter_stadium_outranks_the_stretcher_for_keeping():
    """The measured inversion, stated as the ordering it broke.

    Under their Neutralization Zone the Forest is the only card in the deck that
    restores our damage. It is kept at 2. The Stretcher was kept at -1 -- ABOVE
    it -- for the crime of having nothing useful to recover.
    """
    scores, _, _ = _scores_and_action(strip_pokemon_from_discard=True)
    assert min(scores[FOREST]) < scores[NS][0], (
        f"Forest {scores[FOREST]} must be kept before Night Stretcher "
        f"{scores[NS]}")


def test_the_record_board_still_keeps_the_out_and_the_recovery():
    """The step-99 answer does not move: this change is about the other boards."""
    _, _, discarded = _scores_and_action()
    assert sorted(discarded) == sorted([MEGANIUM, OGERPON, FOREST])


# ---------------------------------------------------------------------------
# 3. Two reasons to keep a card must not make it less protected
# ---------------------------------------------------------------------------

def test_the_refill_protection_wins_over_the_last_supporter_one():
    """A card that is BOTH the last refill and the last playable Supporter.

    The step-99 hand holds exactly one Supporter, so swapping it for a Lillie's
    Determination makes both gates true at once. It must come out at the refill's
    price (2) -- the stronger claim -- and not at the weaker "last Supporter" one
    (5), which is what the ladder used to answer for having tested it first. This
    is the ordering the frozen corpus caught in `registro_021_crustle_wall_18`.

    `Dawn` carries the same reordering for the same reason and is not asserted
    here: on this board its first branch fires (Meganium in play with a
    Hydrapple ex), which is the right answer for a different reason.
    """
    card_id, refill_price, weaker_price = m.Lillie_Determination, 2, 5
    seen = {}
    orig = m._debug_log_decision

    def spy(context, select, scores, obs_, my_index, top_n=3):
        if int(context) == int(m.SelectContext.DISCARD):
            seen["scores"] = list(scores)
        return orig(context, select, scores, obs_, my_index, top_n)

    previa, dec = _load()
    for obs in (previa, dec):
        for entry in obs["current"]["players"][1]["hand"]:
            if entry["id"] == LANA:
                entry["id"] = card_id
    restore = instalar("_debug_log_decision", spy)
    try:
        m.agent(previa)
        m.agent(dec)
    finally:
        restore()

    hand = [c["id"] for c in dec["current"]["players"][1]["hand"]]
    got = [seen["scores"][i] for i, cid in enumerate(hand) if cid == card_id]
    assert got == [refill_price], (
        f"the last refill must keep its own price ({refill_price}); "
        f"{weaker_price} is the weaker gate winning by position: got {got}")
