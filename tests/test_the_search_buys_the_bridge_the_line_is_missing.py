"""Four rules read the hand the search was about to change, and none bought the bridge.

Scenario (`records/registro_004_pasos_040_hasta_055.json` steps 44-45, turn 4 vs
Mega Lucario ex, episode 93428975 -- LOST):

    US (6 prizes)                        OPPONENT (6 prizes)
    active  Teal Mask Ogerpon ex, 2 {G}  active  Solrock, 1 {F}
    bench   Applin, Chikorita,           bench   Hariyama, Riolu + Hero's Cape,
            Teal Mask Ogerpon ex 1 {G}           Lunatone, Makuhita
    hand    Boss's Orders, Hydrapple ex, stadium OUR Forest of Vitality
            Meganium, Dawn,
            **Lillie's Determination**   (Supporter slot free, attachment unspent)
    played  Teal Dance, Forest of Vitality, **Ultra Ball**

The turn had one line and it was in reach. Under our own Forest of Vitality a
{G} Pokemon may evolve the turn it is played, so a Bayleef out of the deck was
Chikorita -> Bayleef -> **Meganium** in one turn; Wild Growth then doubles every
Grass and the two on the Active pay for a Myriad Leaf Shower that costs three;
and the Lillie's Determination in hand draws **8** at exactly six prizes.

What happened instead: the cost took the Boss's Orders (36) and the **Lillie's
Determination** (8), the fetch bought a **Meowth ex** (1150), its Last-Ditch
Catch fetched a Lana's Aid, and the Supporter slot went to that. The turn ended
with a 2-prize body on the bench, three cards in hand, the Chikorita still
unevolved and the Bayleef still in the deck.

FOUR rules decided it and all four asked the same wrong question -- "what can
this hand do today?" -- of a hand the very card being resolved was about to
change:

  1. the COST, `DISCARD_SUPPORTER_LIVE_KEEP`: it ranks the Supporters of the
     hand on `_supp_values`, a FETCH scale, which on this board read Dawn 900
     over Lillie's 750 (with a Forest in play it lifts Dawn above the refill).
     The PLAY scale, asked in the same tick, said Lillie's 5000. The keep floor
     went to the card the turn would not play.
  2. the FETCH, `_ub_mega_dead_prefer_meowth`: it reads the missing bridge ONLY
     in hand, so it called the Meganium line dead -- while the discard ladder of
     that same menu was keeping the Meganium at `DISCARD_LINK_THE_SEARCH_BUYS`
     *because the search can buy the Bayleef*. One Ultra Ball, two halves,
     opposite answers.
  3. `_ub_no_attacker_prefer_meowth` and 4. `refill_after_a_ko`
     (`_RULES_UB_FEZ`): both gated on the refill being in the DECK, both silent
     the moment the cost put ours in the DISCARD. The price had erased its own
     vetoes.

TWO fixes shipped, both deck-agnostic and both measured:

  * `THE_COST_KEEPS_THE_SUPPORTER_THE_TURN_PLAYS` -- the keep floor of
    `DISCARD_SUPPORTER_LIVE_KEEP` is decided by `_best_supporter_in_hand`, the
    PLAY scale, instead of `_supp_values`. It closes 1 above and, with it, 3 and
    4: both of those are gated on the refill being in the deck, and the refill
    only left the hand because the cost took it.
  * `the_turns_refill_is_already_in_hand` in `_RULES_UB_FEZ` -- a body bought
    for the cards it draws yields to a Supporter already in hand that draws
    more, the sentence `_RULES_UB_MEOWTH` already carries one ladder over.

Neither names a card: the Supporters come from the real play scorers
(`_supp_play_score`) and the yield from `_supp_in_hand_takes_the_turn`.

WHAT WAS WRITTEN, MEASURED AND REVERTED: defect 2. Teaching
`_ub_mega_dead_prefer_meowth` to count a bridge the search still reaches in the
DECK (over `EVO_LINES`, plus a `GRASS_DOUBLER_IDS` clause for
`_ub_no_attacker_prefer_meowth`, since Wild Growth is what pays for the Active's
attack here) is the correct reading and it changed NO decision: with the refill
back in hand both flags are already silent through their own "Lillie's == 0"
clause, and on a hand with no refill at all the ladder hands the same fetch to
`no_attacker_prefers_meowth` (1250) and then to `refill_after_a_ko` (1050) --
same Meowth ex, different rule name. Dead by ordering, in the sense
`utils/rule_census.py` means it. It is not shipped: correcting the REASON a rule
gives, when the consequence never lands, is the folklore this estate reverts.
Reopening it means moving the whole refill family below a line the search can
complete, which is a re-pricing and needs its own measurement.

WHAT THE SECOND FIXTURE IS. The record cannot show the corrected fetch -- it
stores the board the WRONG cost produced, with the Lillie's already in the
discard. `..._step45.json` is that same observation with the one difference the
first fix makes: the Dawn paid the cost and the Lillie's is in hand. It is the
board the corrected turn actually reaches, and it is where rules 2, 3 and 4 are
measured.
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

_FIXTURE_COST = (ROOT / "tests" / "fixtures"
                 / "mega_lucario_t4_the_cost_keeps_the_supporter_the_turn_plays_step44.json")
_FIXTURE_FETCH = (ROOT / "tests" / "fixtures"
                  / "mega_lucario_t4_the_search_buys_the_bridge_step45.json")

BAYLEEF = m.Bayleef
BOSS = m.Boss_Orders
DAWN = m.Dawn
FEZ = m.Fezandipiti_ex
LILLIE = m.Lillie_Determination
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex

SEAT = 1                       # our seat in this record


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
    yield
    m._init_cards_tracking()


def _obs(path):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _picked_from_hand(obs):
    """The card ids the agent chooses out of a HAND menu (the Ultra Ball cost)."""
    hand = obs["current"]["players"][SEAT]["hand"]
    sel = obs["select"]
    return [hand[sel["option"][i]["index"]]["id"] for i in m.agent(obs)]


def _picked_from_deck(obs):
    """The card ids the agent chooses out of a DECK menu (the Ultra Ball fetch)."""
    deck = obs["select"]["deck"]
    sel = obs["select"]
    return [deck[sel["option"][i]["index"]]["id"] for i in m.agent(obs)]


# ---------------------------------------------------------------------------
# 1. The COST: it pays with the refill the turn would NOT play
# ---------------------------------------------------------------------------

def test_the_cost_does_not_eat_the_supporter_that_takes_the_turn():
    """The Lillie's Determination is the Supporter of this turn; it is not fodder.

    The whole point of the record: with the slot free and TWO refills in hand,
    the cost has to pay with the one the turn would not play.
    """
    picked = _picked_from_hand(_obs(_FIXTURE_COST))
    assert LILLIE not in picked, (
        "the Ultra Ball's cost took the Lillie's Determination, the Supporter "
        f"the PLAY scale ranks 5000 on this board; it discarded {picked}")


def test_the_cost_pays_with_the_other_refill_and_the_gust():
    """And it pays with exactly the two cards the turn has no use for."""
    picked = _picked_from_hand(_obs(_FIXTURE_COST))
    assert sorted(picked) == sorted([DAWN, BOSS]), picked


def test_the_cost_keeps_the_top_of_the_line_it_is_buying_the_bridge_for():
    """The Meganium is not fodder either: `_evo_top_unlocked_by_the_search`.

    It already held before this change and is asserted here because the whole
    finding is that the fetch then refused to buy the bridge this keep was for.
    """
    assert MEGANIUM not in _picked_from_hand(_obs(_FIXTURE_COST))


def test_the_predicate_names_the_lillie_on_the_play_scale(monkeypatch):
    """The predicate itself, under the menu that reads it.

    The keep floor used to be decided by `_supp_values`, which ranks Dawn over
    Lillie's on this board; `_best_supporter_in_hand` is the PLAY scale and it
    names the Lillie's. Pinning the predicate and not only the discard keeps the
    two apart: if the value layer is ever re-tuned, this test still says which
    scale the cost is supposed to obey.
    """
    seen = []
    original = m._best_supporter_in_hand

    def _record(ctx, hand_counts=None):
        answer = original(ctx, hand_counts)
        if hand_counts is None:
            seen.append(answer)
        return answer

    monkeypatch.setattr(m, "_best_supporter_in_hand", _record)
    m.agent(_obs(_FIXTURE_COST))

    assert seen, "the cost menu never asked which Supporter takes the turn"
    assert seen[0][0] == LILLIE, seen[0]


# ---------------------------------------------------------------------------
# 2. The FETCH: the bridge in the deck is not a missing bridge
# ---------------------------------------------------------------------------

def test_the_search_buys_the_bridge_that_completes_the_line():
    """Bayleef, not a body bought for the cards it draws.

    Chikorita on the bench since before this turn, Meganium in hand, our Forest
    of Vitality on the field: the search is one card away from a Stage 2 in
    play. The deck holds two Bayleef.
    """
    picked = _picked_from_deck(_obs(_FIXTURE_FETCH))
    assert picked == [BAYLEEF], picked


def test_the_search_does_not_buy_a_refill_body_the_hand_already_out_draws():
    """Neither Meowth ex nor Fezandipiti ex: both are bought for CARDS.

    The hand holds a Lillie's Determination that draws 8 at exactly six prizes.
    Both bodies would also hand the opponent a 2-prize target.
    """
    picked = _picked_from_deck(_obs(_FIXTURE_FETCH))
    assert MEOWTH not in picked and FEZ not in picked, picked


# ---------------------------------------------------------------------------
# 3. The guards: neither fix may fire where its premise is absent
# ---------------------------------------------------------------------------

def test_the_fez_rung_is_silent_when_the_hand_holds_no_refill():
    """No Supporter in hand, no yield: `refill_after_a_ko` keeps its board.

    `the_turns_refill_is_already_in_hand` reads
    `_supp_in_hand_takes_the_turn`, which is False the moment the hand holds no
    Supporter at all. The rung must not become a blanket veto on the Fezandipiti
    fetch -- that branch has its own record behind it.
    """
    obs = _obs(_FIXTURE_FETCH)
    me = obs["current"]["players"][SEAT]
    me["hand"] = [c for c in me["hand"] if c["id"] != LILLIE]
    me["handCount"] = len(me["hand"])
    picked = _picked_from_deck(obs)
    assert BAYLEEF not in picked, (
        "with no refill in hand the ladder is supposed to keep buying the "
        f"refill engine; the rung leaked into that board and picked {picked}")


def test_the_keep_floor_is_inert_once_the_supporter_slot_is_spent():
    """With the slot spent there is no job to protect and the ladder decides.

    `_supp_that_takes_the_turn` is None then, and the block reads exactly as it
    did before the change.
    """
    obs = _obs(_FIXTURE_COST)
    obs["current"]["supporterPlayed"] = True
    picked = _picked_from_hand(obs)
    assert len(picked) == 2, picked
