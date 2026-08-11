"""Against a MILL deck the forced discard keeps the card that feeds our deck.

Scenario (`records/registro_009_pasos_072_hasta_078.json`, episode 91837627,
step 77, turn 9 vs Comfey/Brambleghast -- LOST while AHEAD on prizes, 4 to 6,
which is what losing to deck-out looks like):

    US (seat 1)                               RIVAL (the mill)
    active  Ogerpon ex 210/210, 4 energy      active  Comfey
    bench   Meganium, Tapu Bulu, Meowth ex,   bench   Brambleghast, 2x Comfey,
            Ogerpon ex                                2x Bramblin
    hand    16 cards, among them              hand    Xerosic's Machinations,
            **Lillie's Determination**,               Hilda, Energy Recycler,
            3x Basic Grass, 2x Xerosic,               Poke Pad
            the whole Applin/Chikorita line
    deck    **17**                            deck    26
    prizes  4 left                            prizes  6 left

Their deck does not race us for prizes: it makes us draw until our deck runs
out, and it runs Xerosic's Machinations to stop the cards it made us draw from
ever going back in. Here that Xerosic cut our hand of sixteen down to three.

Twelve of the thirteen cards the agent let go were right -- our own two Xerosic
are dead against a hand there is nothing to cap, the line pieces had no seat --
and the thirteenth was Lillie's Determination: "shuffle your hand into your
deck, then draw 6". It is the only card in that hand that answers their plan on
both ends, the only one that puts cards BACK into the deck they are emptying and
the only way a three-card hand becomes a hand again. Two turns later (step 100,
same episode) their next Xerosic found a hand with no refill in it at all.

It was not a judgement, it was a hole in a table. The anti-Comfey ladder names
six cards and sends everything else to one number, so Lillie's came out at 850
-- tied with a spare Applin -- while the general ladder sixty lines above had
already priced that same copy at 2 ("the last refill", `_protect_refresh
_supporter`). The matchup table was speaking about a card it had never measured.

Hence the rule (user, August 2026): vs a mill deck the HAND RECYCLER is the top
of the keep ladder, above the energy. It is read off the printed text
(`HAND_TO_DECK_PLAY_IDS`: "shuffle your hand into your deck") and not by name,
and only ONE copy is kept -- the first one shuffles the spares back into the
deck anyway. See `DISCARD_CF_HAND_RECYCLER`.

Keeping it is not the same as playing it, and in this matchup the two halves
already fit: the refill draws 6, so on the three-card hand their Xerosic leaves
us with it would BURN four cards off the clock it is kept for -- and the play
scorer knows, vetoing it until the hand is fat again (`comfey_short_hand`,
hand < 10 -> SCORE_VETO), which is the band where the shuffle NETS deck cards.
The discard buys the option; that veto picks the turn.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m  # noqa: E402
import ptcg.turn.options.card as card_options  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "comfey_t9_the_forced_discard_keeps_the_hand_recycler_step77.json")

LILLIE = m.Lillie_Determination
GRASS = m.Basic_Grass_Energy
STAMP = m.Unfair_Stamp
XEROSIC = m.Xerosic_Machinations

# The hand of the record, in the order the select offers it.
_HAND = [m.Fezandipiti_ex, m.Forest_of_Vitality, XEROSIC, m.Dipplin, m.Tapu_Bulu,
         m.Applin, m.Applin, m.Chikorita, m.Boss_Orders, m.Teal_Mask_Ogerpon_ex,
         XEROSIC, m.Ultra_Ball, GRASS, GRASS, LILLIE, GRASS]
_LILLIE_INDEX = _HAND.index(LILLIE)
_SPARE_SLOT = 5          # an Applin: the slot the negative controls reuse


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agent(m)
    yield
    reset_agent(m)


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _kept(obs, choice):
    """The ids that SURVIVE the cut (the menu is one option per hand card)."""
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    discarded = {obs["select"]["option"][i]["index"] for i in choice}
    return [c["id"] for i, c in enumerate(hand) if i not in discarded]


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_of_step_77_is_the_one_from_the_record():
    obs = _load()
    cur = obs["current"]
    yo = cur["yourIndex"]
    mine, op = cur["players"][yo], cur["players"][1 - yo]

    assert [c["id"] for c in mine["hand"]] == _HAND
    # thirteen of the sixteen go, and every card in hand is an option
    assert obs["select"]["minCount"] == obs["select"]["maxCount"] == 13
    assert len(obs["select"]["option"]) == len(_HAND)

    # it is THEIR card doing the cutting -- the forced horizon, not our own cost
    assert obs["select"]["effect"]["id"] == XEROSIC
    assert obs["select"]["effect"]["playerIndex"] == 1 - yo

    # and the clock that decides the matchup: we are AHEAD on prizes and BEHIND
    # on deck, which is the only race this opponent is running
    assert len(mine["prize"]) < len(op["prize"])
    assert mine["deckCount"] < op["deckCount"]


def test_the_matchup_is_read_as_the_mill():
    """The premise of the whole rule: this ladder only speaks vs Comfey."""
    captured = {}
    real = m.score_option

    def spy(tcp, option, score):
        captured.setdefault("comfey", getattr(tcp, "op_is_comfey_deck", None))
        return real(tcp, option, score)

    m.score_option = spy
    try:
        m.agent(_load())
    finally:
        m.score_option = real

    assert captured["comfey"] is True


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_forced_discard_no_longer_throws_away_the_refill():
    obs = _load()
    choice = m.agent(obs)
    assert _LILLIE_INDEX not in choice, (
        "Lillie's Determination is the only card in hand that puts cards back "
        f"into the deck the mill is emptying; it was discarded ({choice})")
    assert LILLIE in _kept(obs, choice)


def test_it_costs_one_energy_and_nothing_else():
    """A pure permutation inside the hand: the recycler takes the slot of a
    THIRD Basic Grass, and the other twelve discards are the ones the record
    already made."""
    obs = _load()
    saved = card_options.HAND_TO_DECK_PLAY_IDS
    card_options.HAND_TO_DECK_PLAY_IDS = frozenset()   # the rule switched off
    try:
        reset_agent(m)
        before = m.agent(_load())
    finally:
        card_options.HAND_TO_DECK_PLAY_IDS = saved
    reset_agent(m)
    after = m.agent(obs)

    assert before != after, "the fixture does not discriminate"
    assert sorted(_kept(obs, before)) == sorted([GRASS, GRASS, GRASS])
    assert sorted(_kept(obs, after)) == sorted([LILLIE, GRASS, GRASS])
    # twelve of the thirteen were already right and stay untouched
    assert len(set(before) & set(after)) == 12


# ---------------------------------------------------------------------------
# 3. The rule keeps ONE copy, and only the recycler
# ---------------------------------------------------------------------------

def test_a_spare_copy_of_the_refill_is_still_fodder():
    """One turn plays one Supporter, and the first copy shuffles the rest back
    into the deck: the second copy is not a second answer to anything."""
    obs = _load()
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    hand[_SPARE_SLOT]["id"] = LILLIE

    choice = m.agent(obs)
    assert _kept(obs, choice).count(LILLIE) == 1, (
        f"exactly one copy is the recycler; kept {_kept(obs, choice)}")


def test_the_unfair_stamp_keeps_its_own_rung():
    """The Stamp shuffles the hand into the deck too, so the printed text alone
    would put it here -- but it is playable only after they knock one of our
    Pokemon out, which against a mill deck may never happen. It stays on the
    conditional rung it already had (500), below the refill."""
    obs = _load()
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    hand[_SPARE_SLOT]["id"] = STAMP

    kept = _kept(obs, m.agent(obs))
    assert LILLIE in kept and STAMP not in kept, (
        f"the refill outranks the Stamp on this ladder; kept {kept}")


# ---------------------------------------------------------------------------
# 4. The card we KEEP and the card we would PLAY do not disagree
# ---------------------------------------------------------------------------

def test_the_play_scorer_does_not_burn_the_refill_on_the_short_hand():
    """The other half of the plan, pinned so the two cannot drift apart: the
    discard keeps the recycler and the play scorer refuses to spend it until
    the hand is fat enough for the shuffle to NET deck cards."""
    rule = next((r for r in m._RULES_LILLIE_PLAY
                 if r.name == "comfey_short_hand"), None)
    assert rule is not None, (
        "the keep only makes sense paired with the veto that picks the turn")

    class _Ctx:
        op_is_comfey_deck = True
        hand_len = 3          # what their Xerosic leaves us with
    assert rule.when(_Ctx()) and rule.value(_Ctx()) == m.SCORE_VETO

    _Ctx.hand_len = 10        # the band where the refill returns cards
    assert not rule.when(_Ctx())

    # ...and that band is exactly the one the arithmetic asks for: the refill
    # draws 6, so it only feeds the deck from a hand of 8 upwards.
    assert m._refill_deck_delta(20, 3, 4) < 0
    assert m._refill_deck_delta(20, 10, 4) > 0


# ---------------------------------------------------------------------------
# 5. It says nothing outside the mill matchup
# ---------------------------------------------------------------------------

def test_outside_the_mill_the_general_ladder_still_decides():
    """The rung lives inside the `op_is_comfey_deck` block. With the matchup
    off, the same hand is priced by the ordinary ladder -- which protects the
    last refill by its own rule (2) and reaches a different keep-set."""
    obs = _load()
    real = card_options.score_play

    def no_mill(tc, o, score):
        tc.op_is_comfey_deck = False
        return real(tc, o, score)

    card_options.score_play = no_mill
    try:
        import ptcg.turn.scoring as scoring
        saved = scoring._TABLE[3]      # OptionType.CARD
        scoring._TABLE[3] = no_mill
        try:
            kept = _kept(obs, m.agent(obs))
        finally:
            scoring._TABLE[3] = saved
    finally:
        card_options.score_play = real

    # the general ladder protects the last refill on its own merits
    assert LILLIE in kept
    # ...and it does NOT reach the mill's keep-set: the energy is not the
    # matchup's plan there, so the three cards are not two Grass and Lillie's
    assert sorted(kept) != sorted([LILLIE, GRASS, GRASS])
