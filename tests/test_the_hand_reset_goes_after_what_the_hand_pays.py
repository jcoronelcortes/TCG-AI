"""A refill that shuffles the hand away goes AFTER the abilities that spend it.

Record (user, episode 90595441, `records/registro_002_pasos_017_hasta_034.json`,
turn 2 vs Marnie's Grimmsnarl, LOST -- step 29, the 13th action of the turn):

    US                                          RIVAL
    active Teal Mask Ogerpon ex, 1 Grass         active Marnie's Impidimp
           (its own Teal Dance, spent)
    bench  Chikorita, Meowth ex, Applin,
           **Teal Mask Ogerpon ex, 0 energy,
             Teal Dance UNUSED**
    hand   Dawn, Xerosic's Machinations,
           **Lillie's Determination**,
           **1 Basic {G} Energy**, Chikorita

The menu offered the benched Ogerpon's Teal Dance, the manual attachment of that
last Grass, and the Lillie's. The ranking was

    Lillie's 8000  >  Teal Dance 7500  >  attachment 7000

and the agent REFILLED. Lillie's Determination shuffles your hand into your deck,
so the only Grass left went back into the deck: the benched Ogerpon closed the
turn empty, the ability's free draw was never taken, and the turn's attachment had
nothing left to attach.

None of the three numbers is wrong on its own, and that is what makes it an ORDER
bug rather than a value one:

  * Teal Dance sits at 7500 through the reserve band -- "the Grass is being saved
    for the ACTIVE, do not spend it on a benched body";
  * the attachment sits at 7000 because it yielded to that very Teal Dance
    (`_attach_yields_to_teal_dance`);
  * Lillie's sits at 8000 through `_ld_supp_comprometido`, the floor that forces
    playing the Supporter a Last-Ditch Catch paid a 2-prize body for -- the Meowth
    ex had fetched it seven menus earlier, on action 5 of this same turn.

A reserve is a bet on a card STAYING IN HAND, and a hand reset is exactly the play
that cancels that bet: once the refill is on the menu there is no later to save
the Grass for. The commitment floor, for its part, says WHETHER the Supporter gets
played, never WHEN. And no score can settle it, because both plays live in tier 0
-- Supporters always do, and a DEGRADED charging ability does too (its
`_TIER_ENERGY` promotion asks for >= 29000) -- so inside the tier the bigger number
wins whatever the numbers mean.

Fix (`finalizar`, "WHAT THE HAND PAYS GOES BEFORE THE HAND IS SHUFFLED AWAY"): the
plays that pay with a card from the hand are lifted just above the refill by a
SHARED delta, so their order among themselves is untouched and the refill drops
exactly one notch -- it wins the next menu, with the ability spent and one card
fewer to shuffle away.

Deck-agnostic on both halves, and read off the PRINTED TEXT rather than a curated
list (`HAND_RESET_PLAY_IDS` / `HAND_COST_ABILITY_IDS`): any refill that empties the
hand (Lillie's, Lacey, Judge, Carmine, the Unfair Stamp) yields to any ability that
pays with a card out of it (Teal Dance, Ripening Charge, Inferno Fandango...).

It does NOT invert the opposite order, which is also right: an ability that
PRODUCES cards -- Fezandipiti ex's Flip the Script -- goes AFTER the refill, since
drawing first only feeds those three cards back into the deck. That half already
exists (`_lillie_blocks_fez_ability`, `_stamp_blocks_supp_chain`) and the two never
collide: the discriminator is which way the cards flow.

Coverage:
  * the record's board, both halves of it, and the decision it flips;
  * the refill is not lost: once the ability is spent it wins the next menu;
  * the control -- with no refill on the menu the ability keeps its 7500, so the
    net only ever fires against a hand reset;
  * the two sets as PROPERTIES: the refills that empty the hand against the
    searchers that do not, the abilities that pay with a card against the triggers
    that merely name the hand and against the draw abilities, which keep the
    opposite order.
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
from golden_corpus import reset_agent

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step29_the_hand_reset_goes_last.json")

LILLIE = m.Lillie_Determination
OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
MEOWTH = m.Meowth_ex
FEZ = m.Fezandipiti_ex
HYDRAPPLE = m.Hydrapple_ex
STAMP = m.Unfair_Stamp

_LACEY, _JUDGE, _CARMINE, _AMARYS = 1199, 1213, 1192, 1207
_DAWN, _ULTRA_BALL, _BUG_SET, _POKE_PAD = 1231, 1121, 1094, 1152


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return (copy.deepcopy(data["previous_observation"]),
            copy.deepcopy(data["observation"]))


def _replay(dec=None):
    """Replays the record's menu and returns (choice, the observation used).

    The Last-Ditch mark is set by hand instead of replaying the seven earlier
    menus of the turn: the fetch happened on action 5 and what this test measures
    is the ORDER at action 13, not how the commitment got there.
    """
    previous, recorded = _load()
    if dec is None:
        dec = recorded
    m.agent(previous)
    m.AGENT_STATE._ld_supp_comprometido = LILLIE
    return m.agent(dec), dec


def _option(obs, i):
    return obs["select"]["option"][i]


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


# ---------------------------------------------------------------------------
# 1. The board: without these two halves there is no order to fix
# ---------------------------------------------------------------------------

def test_step29_the_hand_holds_the_refill_and_the_grass_it_would_shuffle():
    _, dec = _load()
    hand = [c["id"] for c in _mine(dec)["hand"]]
    assert hand.count(LILLIE) == 1, "the refill has to be on the menu"
    assert hand.count(GRASS) == 1, (
        "one single Grass: it is the card the refill shuffles away and the one "
        "Teal Dance pays with")
    assert dec["current"]["supporterPlayed"] is False


def test_step29_the_benched_ogerpon_still_has_its_teal_dance():
    _, dec = _load()
    bench = _mine(dec)["bench"]
    ogerpon = [i for i, p in enumerate(bench) if p["id"] == OGERPON]
    assert ogerpon == [3] and not bench[3]["energies"], (
        "the benched Ogerpon ex is empty; its Teal Dance is the play that pays "
        "with the Grass")
    ability = [o for o in dec["select"]["option"]
               if o["type"] == int(m.OptionType.ABILITY)]
    assert len(ability) == 1 and ability[0]["index"] == 3, (
        "the ACTIVE Ogerpon already spent its own Teal Dance on action 10: the "
        "only ability left on the menu is the benched one")


# ---------------------------------------------------------------------------
# 2. The decision it flips
# ---------------------------------------------------------------------------

def test_step29_the_ability_is_played_before_the_refill():
    choice, dec = _replay()
    o = _option(dec, choice[0])
    assert o["type"] == int(m.OptionType.ABILITY), (
        f"the turn's Grass is spent before the hand is shuffled away; chose {o}")
    assert o["index"] == 3 and o["area"] == int(m.AreaType.BENCH)


def test_step29_the_refill_is_not_lost_it_only_waits_its_turn():
    """The net is a SWAP, not a veto: with the ability spent -- the Grass on the
    benched Ogerpon and one card drawn -- the refill wins the next menu with its
    Supporter slot still free."""
    choice, dec = _replay()
    mine = _mine(dec)

    grass = next(c for c in mine["hand"] if c["id"] == GRASS)
    mine["hand"].remove(grass)
    mine["bench"][3]["energies"] = [7]
    mine["bench"][3]["energyCards"] = [grass]
    # The ability's draw. A Poke Pad is the worst case for the test: another card
    # in hand competing for the action, and none of it a Grass that would put a
    # second charging play back on the menu.
    mine["hand"].append({"id": _POKE_PAD, "playerIndex": 1, "serial": 104})
    mine["handCount"] = len(mine["hand"])
    mine["deckCount"] -= 1
    dec["current"]["turnActionCount"] += 1
    dec["logs"] = []
    # The menu the engine offers next: no Teal Dance (spent) and no attachment
    # (no Grass left in hand).
    dec["select"]["option"] = [
        {"index": i, "type": int(m.OptionType.PLAY)}
        for i in range(len(mine["hand"]))
        if mine["hand"][i]["id"] != m.Xerosic_Machinations
    ] + [{"type": int(m.OptionType.ATTACK)}, {"type": int(m.OptionType.END)}]

    reset_agent(m)
    m.AGENT_STATE._ld_supp_comprometido = LILLIE
    choice = m.agent(dec)
    o = _option(dec, choice[0])
    assert o["type"] == int(m.OptionType.PLAY)
    assert mine["hand"][o["index"]]["id"] == LILLIE, (
        "the refill has to close the turn: its slot is free and it was paid for "
        "with a 2-prize body")


# ---------------------------------------------------------------------------
# 3. The control: the net only fires against a hand reset
# ---------------------------------------------------------------------------

def test_without_a_refill_on_the_menu_the_ability_keeps_its_reserve_band():
    """The lift is not a boost for charging abilities: with the Lillie's out of
    the menu the degraded Teal Dance stays exactly where its own scorer left it,
    and it wins that menu on its own merits."""
    previous, dec = _load()
    lillie_i = next(
        i for i, o in enumerate(dec["select"]["option"])
        if o["type"] == int(m.OptionType.PLAY)
        and _mine(dec)["hand"][o["index"]]["id"] == LILLIE)
    dec["select"]["option"].pop(lillie_i)

    seen = {}

    def spy(context, select, scores, obs, my_index):
        if context == m.SelectContext.MAIN:
            seen["scores"] = list(scores)
            seen["options"] = list(select.option)

    from patching import instalar
    restore = instalar("_debug_log_decision", spy)
    try:
        m.agent(previous)
        m.AGENT_STATE._ld_supp_comprometido = LILLIE
        m.agent(dec)
    finally:
        restore()

    ability = [i for i, o in enumerate(seen["options"])
               if o.type == m.OptionType.ABILITY]
    assert len(ability) == 1
    assert seen["scores"][ability[0]] == 7500, (
        "with nothing about to shuffle the hand away, the reserve band is the "
        "right price and the net must not touch it")


# ---------------------------------------------------------------------------
# 4. The two sets are PROPERTIES OF THE PRINTED TEXT, not card lists
# ---------------------------------------------------------------------------

def test_the_refills_that_empty_the_hand_are_the_ones_listed():
    for cid in (LILLIE, _LACEY, _JUDGE, _CARMINE, STAMP):
        assert cid in m.HAND_RESET_PLAY_IDS, m.card_table[cid].name


def test_a_searcher_that_leaves_the_hand_standing_is_not_a_reset():
    """Dawn, the Ultra Ball, the Bug Catching Set and the Poke Pad all shuffle the
    DECK, not the hand: nothing already in hand dies to them."""
    for cid in (_DAWN, _ULTRA_BALL, _BUG_SET, _POKE_PAD):
        assert cid not in m.HAND_RESET_PLAY_IDS, m.card_table[cid].name


def test_a_discard_at_the_end_of_the_turn_is_not_a_reset():
    """Amarys discards the hand "at the end of this turn": nothing played DURING
    the turn loses its cost to it, so it imposes no order."""
    assert _AMARYS not in m.HAND_RESET_PLAY_IDS


def test_the_abilities_that_pay_with_a_card_from_hand():
    for cid in (OGERPON, HYDRAPPLE):
        assert cid in m.HAND_COST_ABILITY_IDS, m.card_table[cid].name


def test_a_trigger_that_only_names_the_hand_does_not_pay_with_it():
    """Meowth ex's Last-Ditch Catch reads "when you play this Pokemon FROM YOUR
    HAND onto your Bench": the hand is where the BODY comes from, not a card the
    ability spends."""
    assert MEOWTH not in m.HAND_COST_ABILITY_IDS


def test_a_draw_ability_keeps_the_opposite_order():
    """Flip the Script RECEIVES cards, so it goes AFTER the refill -- the half
    `_lillie_blocks_fez_ability` already owns. If it entered this set the two
    rules would deadlock on each other."""
    assert FEZ not in m.HAND_COST_ABILITY_IDS
