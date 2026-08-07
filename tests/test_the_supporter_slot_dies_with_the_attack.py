"""The Supporter of the turn is played BEFORE the attack that closes it.

Scenario (user, episode 90323613, turn 8 vs an Alakazam ex deck, WON with a
mistake). The turn opens at step 111 with everything already done -- Forest
answered, Ogerpon benched, Tapu Bulu benched, the Grass attached:

    US                                      RIVAL
    active  Fezandipiti ex 210, 4 energy    active  Alakazam ex 210, 4 energy
    bench   Meganium 160                    bench   Alakazam ex 140/140
            Meowth ex 10/170                        Kadabra 80/80
            Teal Mask Ogerpon ex 210 2e             Fezandipiti ex 210
            Teal Mask Ogerpon ex 210                Marill 70 (1 energy)
            Tapu Bulu 140                           Marill 70
    hand    Boss's Orders, XEROSIC'S MACHINATIONS, Ultra Ball, Lana's Aid,
            Dawn, 2 Grass, Teal Mask Ogerpon ex, Forest of Vitality
    the turn's Supporter: UNPLAYED        THEIR HAND: 19 CARDS

The menu offered the five plays plus Cruel Arrow, and the ranking was

    attack 8600  >  Xerosic 7300  >  Boss's 5240

The agent SNIPED and closed the turn. Their nineteen-card hand was left
untouched and the turn's Supporter slot went to the bin with it -- against
Alakazam that hand is also their damage (Powerful Hand hits for 20 per card),
and Xerosic's Machinations would have sent SIXTEEN of those cards to the
discard for good (`XEROSIC_HAND_CAP` = 3).

The mistake is not one of value, it is one of ORDER, and no score can fix it:
the two plays were never alternatives. A Supporter does not consume the attack
and the attack does not consume the Supporter -- but the attack ENDS THE TURN
and the Supporter slot does not accumulate. Comparing 8600 with 7300 answers
"which of the two is worth more"; the question that decides the turn is "which
of the two can still be played afterwards", and the answer is only ever the
attack. Both plays lived in tier 0, so the score decided and the free play was
thrown away.

The net lives in `finalizar` and only fires when the menu is ALREADY won by an
attack: it lifts the best live Supporter just above it and touches no tier, so
the winning finisher (`_TIER_WIN_ATTACK`) and anything parked in a higher tier
keep their turn untouched. Its two limits are about not burning a card for
nothing: the Supporter has to score ABOVE `SUPP_SCORE_LAST_RESORT_BAND` (at
that height the scorer is saying "I have no useful effect today"), and BOSS'S
ORDERS is excluded because gusting rewrites the board the attack acts on --
gust and attack really are alternatives, and its own ladder already decides
between them.

A SECOND RECORD, the same mistake one game earlier (user, episode 90341328,
turn 7 vs the same archetype, LOST). At step 81 the turn had already spent
itself digging for this exact card: Ultra Ball -> Meowth ex -> its Last-Ditch
Catch pulled XEROSIC'S MACHINATIONS out of the deck. The menu that followed
offered Lillie's, the Ultra Ball, the Xerosic and Cruel Arrow, and the ranking
was

    attack 8600  >  Xerosic 8000  >  Lillie's -1

-- and the agent SNIPED. The 8000 is not even Xerosic's own score (6200,
`alakazam_cap_the_hand`): it is `SCORE_LD_SUPP_COMPROMETIDO`, the floor that
exists precisely so that a Supporter ALREADY PAID FOR with a two-prize body
takes the slot it was dug for. That floor sits BELOW the snipe band
(`_active_snipe_ko_now` = 8500 + 100 per prize), so the whole chain -- item,
body, ability, deck search -- was thrown away by the very attack it had been
built around, and their thirteen-card hand went untouched into a turn where
Powerful Hand reads 20 per card.

Deck-agnostic on both sides of the board, and the second record is where that
is checked: swap their Alakazam line for a Dragapult one and Xerosic drops from
its matchup branch (6200) to the generic one (3380) -- the reorder is
identical, because it is decided by `cardType` and by which of the two plays
survives the turn, never by a score or a card list.

Coverage:
  * the record's board, so a future fixture cannot quietly stop measuring it;
  * step 111 plays Xerosic instead of sniping;
  * the prize is not lost: with the slot spent, the same board still closes the
    turn with Cruel Arrow;
  * the limits -- the slot already spent, a last-resort Supporter, and a Boss's
    Orders alone in hand, none of which reorder anything;
  * the winning finisher is not delayed by a live Supporter;
  * step 81 of the second record: the fetched Supporter goes before the snipe,
    the snipe is only delayed, and the same board reorders the same way against
    a different opposing deck.
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
from cg.api import OptionType

BOSS = m.Boss_Orders
XEROSIC = m.Xerosic_Machinations
ULTRA_BALL = m.Ultra_Ball
LANAS = m.Lanas_Aid
DAWN = m.Dawn
FEZ = m.Fezandipiti_ex
OGERPON = m.Teal_Mask_Ogerpon_ex

CRUEL_ARROW = 183                   # the attack of the record's active
OP_ALAKAZAM = m.Alakazam_ex
OP_KADABRA = m.Kadabra

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_step111_the_supporter_goes_before_the_attack.json")
_FIXTURE_STEP81 = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step81_the_fetched_supporter_goes_before_the_snipe.json")


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


def _obs_step111():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _obs_step81():
    with open(_FIXTURE_STEP81, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _play(obs, choice):
    """('PLAY', card id) / ('ATTACK', attackId) / ('END', None)..."""
    assert choice, f"the agent chose nothing: {choice}"
    o = obs["select"]["option"][choice[0]]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    if o["type"] == int(OptionType.PLAY):
        return ("PLAY", mine["hand"][o["index"]]["id"])
    if o["type"] == int(OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if o["type"] == int(OptionType.RETREAT):
        return ("RETREAT", None)
    if o["type"] == int(OptionType.END):
        return ("END", None)
    return (o["type"], None)


def _plays(obs):
    return [_play(obs, [i]) for i in range(len(obs["select"]["option"]))]


def _after_playing_the_supporter(obs, hand_index, op_hand):
    """The board the engine hands back once that Supporter has resolved.

    The card leaves our hand, the slot is spent and their hand is capped, so
    the menu the simulator emits no longer offers any Supporter: what is left
    is the Ultra Ball, the attack, the retreat and the pass.
    """
    after = copy.deepcopy(obs)
    cur = after["current"]
    mine = cur["players"][cur["yourIndex"]]
    del mine["hand"][hand_index]
    mine["handCount"] = len(mine["hand"])
    cur["supporterPlayed"] = True
    cur["players"][1 - cur["yourIndex"]]["handCount"] = op_hand
    ub = next(i for i, c in enumerate(mine["hand"]) if c["id"] == ULTRA_BALL)
    after["select"]["option"] = [
        {"index": ub, "type": int(OptionType.PLAY)},
        {"attackId": CRUEL_ARROW, "type": int(OptionType.ATTACK)},
        {"type": int(OptionType.RETREAT)},
        {"type": int(OptionType.END)},
    ]
    return after


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step111_the_board_is_the_records_one():
    obs = _obs_step111()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 8
    assert cur["supporterPlayed"] is False, "the slot of the turn is the point"
    assert mine["active"][0]["id"] == FEZ
    assert len(mine["active"][0]["energies"]) == 4, "Cruel Arrow is paid for"
    assert theirs["active"][0]["id"] == OP_ALAKAZAM
    assert OP_KADABRA in [p["id"] for p in theirs["bench"]]
    assert theirs["handCount"] == 19, (
        "nineteen cards is what Xerosic's Machinations was going to cut down "
        "to three -- and what Powerful Hand was going to hit us with")

    plays = _plays(obs)
    assert ("PLAY", XEROSIC) in plays, plays
    assert ("ATTACK", CRUEL_ARROW) in plays, plays
    assert ("PLAY", BOSS) in plays, plays


# ---------------------------------------------------------------------------
# 2. The mistake and its two halves
# ---------------------------------------------------------------------------

def test_step111_the_supporter_goes_before_the_snipe():
    obs = _obs_step111()
    assert _play(obs, m.agent(obs)) == ("PLAY", XEROSIC), (
        "the snipe closes the turn and the Supporter slot does not "
        "accumulate: capping their hand costs the attack nothing")


def test_step111_the_snipe_is_not_lost_only_delayed():
    """The reorder must not cost the prize: with the slot spent, the same
    board closes the turn with Cruel Arrow."""
    obs = _obs_step111()
    xerosic_i = next(i for i, c in enumerate(
        obs["current"]["players"][obs["current"]["yourIndex"]]["hand"])
        if c["id"] == XEROSIC)
    after = _after_playing_the_supporter(obs, xerosic_i, op_hand=3)
    assert _play(after, m.agent(after)) == ("ATTACK", CRUEL_ARROW)


# ---------------------------------------------------------------------------
# 3. The limits: what the net must NOT reorder
# ---------------------------------------------------------------------------

def test_the_slot_already_spent_reorders_nothing():
    """With `supporterPlayed` on there is nothing to save: the snipe wins the
    menu exactly as before."""
    obs = _obs_step111()
    obs["current"]["supporterPlayed"] = True
    # The simulator would not offer any Supporter either.
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    ub = next(i for i, c in enumerate(mine["hand"]) if c["id"] == ULTRA_BALL)
    obs["select"]["option"] = [
        {"index": ub, "type": int(OptionType.PLAY)},
        {"attackId": CRUEL_ARROW, "type": int(OptionType.ATTACK)},
        {"type": int(OptionType.END)},
    ]
    assert _play(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


def test_a_boss_orders_alone_does_not_delay_the_snipe():
    """A gust rewrites WHO the attack hits, so gust and attack really are
    alternatives: the net leaves that comparison to Boss's own ladder."""
    obs = _obs_step111()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    for _cid in (XEROSIC, LANAS, DAWN):
        _i = next((i for i, c in enumerate(mine["hand"]) if c["id"] == _cid),
                  None)
        if _i is not None:
            del mine["hand"][_i]
    mine["handCount"] = len(mine["hand"])
    boss = next(i for i, c in enumerate(mine["hand"]) if c["id"] == BOSS)
    ub = next(i for i, c in enumerate(mine["hand"]) if c["id"] == ULTRA_BALL)
    obs["select"]["option"] = [
        {"index": boss, "type": int(OptionType.PLAY)},
        {"index": ub, "type": int(OptionType.PLAY)},
        {"attackId": CRUEL_ARROW, "type": int(OptionType.ATTACK)},
        {"type": int(OptionType.END)},
    ]
    assert _play(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


def test_a_last_resort_supporter_is_not_burned_by_the_net():
    """A Supporter scoring in `SUPP_SCORE_LAST_RESORT_BAND` is saying "I have
    no useful effect today". The free slot is not a reason to spend the CARD:
    below and at that band the net does not lift anything."""
    obs = _obs_step111()
    xerosic_i = next(i for i, o in enumerate(obs["select"]["option"])
                     if o["type"] == int(OptionType.PLAY)
                     and obs["current"]["players"][
                         obs["current"]["yourIndex"]]["hand"][
                         o["index"]]["id"] == XEROSIC)

    import ptcg.turn.finalize as fin
    original = fin.finalizar

    def cap_the_supporters(tc):
        if tc.context == m.SelectContext.MAIN:
            for _i, _o in enumerate(tc.select.option):
                if (_o.type == OptionType.PLAY and _i < len(tc.scores)
                        and tc.scores[_i] > 0):
                    tc.scores[_i] = min(tc.scores[_i],
                                        m.SUPP_SCORE_LAST_RESORT_BAND)
        return original(tc)

    fin.finalizar = cap_the_supporters
    m.finalizar = cap_the_supporters
    try:
        choice = m.agent(obs)
    finally:
        fin.finalizar = original
        m.finalizar = original
    assert choice != [xerosic_i]
    assert _play(obs, choice) == ("ATTACK", CRUEL_ARROW)


def test_the_winning_finisher_is_not_delayed_by_a_supporter():
    """The finisher lives in `_TIER_WIN_ATTACK`, above every score: nothing
    matters after the game ends. With our prize count down to one, the snipe
    that takes it CLOSES the game and no Supporter gets in front of it."""
    obs = _obs_step111()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    mine["prize"] = mine["prize"][:1]
    assert _play(obs, m.agent(obs)) == ("ATTACK", CRUEL_ARROW)


# ---------------------------------------------------------------------------
# 4. The second record: the Supporter the turn had just dug for (step 81)
# ---------------------------------------------------------------------------

def test_step81_the_board_is_the_records_one():
    obs = _obs_step81()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 7
    assert cur["supporterPlayed"] is False, "the slot of the turn is the point"
    assert mine["active"][0]["id"] == FEZ
    assert len(mine["active"][0]["energies"]) == 3, "Cruel Arrow is paid for"
    assert m.Meowth_ex in [p["id"] for p in mine["bench"]], (
        "the Meowth ex whose Last-Ditch Catch pulled the Xerosic out of the "
        "deck THIS turn is still on the bench")
    assert theirs["active"][0]["id"] == OP_ALAKAZAM
    assert theirs["handCount"] == 13, (
        "thirteen cards is what Xerosic's Machinations was going to cut down "
        "to three -- and what Powerful Hand was going to hit us with")

    plays = _plays(obs)
    assert ("PLAY", XEROSIC) in plays, plays
    assert ("ATTACK", CRUEL_ARROW) in plays, plays


def test_step81_the_fetched_supporter_goes_before_the_snipe():
    """The recorded action was the snipe, and it buried the Ultra Ball ->
    Meowth ex -> Last-Ditch Catch chain that had just paid for this card."""
    obs = _obs_step81()
    assert _play(obs, m.agent(obs)) == ("PLAY", XEROSIC)


def test_step81_the_snipe_is_not_lost_only_delayed():
    """The reorder must not cost the prize. With the slot spent the agent
    still has the Ultra Ball in hand -- an item does not close the turn, so
    playing it first is not a loss and the menu after it is what has to end in
    Cruel Arrow. Both menus are checked: neither of them passes or retreats."""
    obs = _obs_step81()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    xerosic_i = next(i for i, c in enumerate(mine["hand"]) if c["id"] == XEROSIC)

    after = _after_playing_the_supporter(obs, xerosic_i, op_hand=3)
    assert _play(after, m.agent(after))[0] in ("PLAY", "ATTACK"), (
        "with the Supporter spent the turn keeps building or attacks; it "
        "neither passes nor retreats")

    # ... and with the item spent as well, the attack is the whole menu.
    ub_i = next(i for i, c in enumerate(
        after["current"]["players"][after["current"]["yourIndex"]]["hand"])
        if c["id"] == ULTRA_BALL)
    last = copy.deepcopy(after)
    last_mine = last["current"]["players"][last["current"]["yourIndex"]]
    del last_mine["hand"][ub_i]
    last_mine["handCount"] = len(last_mine["hand"])
    last["select"]["option"] = [
        {"attackId": CRUEL_ARROW, "type": int(OptionType.ATTACK)},
        {"type": int(OptionType.RETREAT)},
        {"type": int(OptionType.END)},
    ]
    assert _play(last, m.agent(last)) == ("ATTACK", CRUEL_ARROW)


def test_step81_the_reorder_does_not_depend_on_the_opposing_deck():
    """Same board, another archetype in front. Their Alakazam line becomes a
    Dragapult one, so the Xerosic scorer leaves its matchup branch (6200) for
    the generic one (3380) -- and the reorder is exactly the same, because
    what decides it is `cardType` and which of the two plays survives the
    turn, not the score and not a card list."""
    obs = _obs_step81()
    theirs = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    theirs["active"] = [dict(theirs["active"][0], id=m.Dragapult_ex,
                             hp=320, maxHp=320, preEvolution=[])]
    theirs["bench"] = [
        dict(p, id=_id, hp=_hp, maxHp=_hp, preEvolution=[])
        for p, _id, _hp in zip(
            theirs["bench"],
            (m.Dreepy, m.Dreepy, m.Drakloak, m.Dreepy, m.Drakloak),
            (70, 70, 90, 70, 90))]

    plays = _plays(obs)
    assert ("PLAY", XEROSIC) in plays and ("ATTACK", CRUEL_ARROW) in plays
    assert _play(obs, m.agent(obs)) == ("PLAY", XEROSIC)
