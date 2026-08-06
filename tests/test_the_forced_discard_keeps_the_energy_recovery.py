"""A forced discard prices a Supporter by the BOARD, not by static proxies.

Scenario (`records/registro_009_pasos_120_hasta_135.json`, episode 90115646,
step 132, turn 9 vs Archaludon ex, LOST):

    US                                        RIVAL
    active  Ogerpon ex 210/210, 8 energy      active  --
    bench   Meowth ex, **Meganium**,          bench   Duraludon, **Archaludon
            Ogerpon ex (4 energy),                    ex 300/300, 3 energy**,
            Fezandipiti ex, Tapu Bulu                 Archaludon ex (freshly
    hand    Bayleef, **Lana's Aid**, Dawn,            evolved, 3 energy)
            Meganium, Ultra Ball x2,                  evolved, 3 energy)
            Boss's Orders, Applin, Forest     prizes  3 left -- the two they
    discard **4 Basic Grass**                         take for our Ogerpon ex
    prizes  2 left                                    later this same turn
                                                      leave them at 1

Their Xerosic's Machinations forced us to throw away SIX of those nine cards.
The `DISCARD` scorer prices every Supporter with static proxies and not one of
them reads the board:

  * Lana's Aid -> 35, because `len(discard) > 2`.
  * Dawn -> 3, because it is the last refill Supporter
    (`_protect_refresh_supporter`) -- on a bench that was already FULL, 5/5,
    with every line of the deck in play. It had nothing to search for.
  * Boss's Orders -> 20, because `op_prize <= 3`.

So Lana's Aid was the Supporter discarded. The value layer had read that same
board in that same decision and said exactly the opposite -- Lana's Aid 750,
Dawn 0, Boss's Orders 0 -- and nobody asked it.

What went with the card: our Ogerpon ex died that same turn and its four Grass
joined the four already down there, leaving EIGHT recoverable Grass. On turn 10
we promoted the benched Ogerpon ex with 4 effective energy against their active
Archaludon ex, and Myriad Leaf Shower needs 8 to knock it out:

    30 + 30 x (8 own + 3 theirs) = 360, -30 for Archaludon's Grass
    resistance = 330 on a 300 HP body.

Two more Grass -- Lana's Aid recovers three -- and Teal Dance plus the manual
attachment put them there for the last two prizes. With the single Grass we did
hold the attack stops at 270 and knocks out nothing. The agent gusted a 1-prize
body instead, took one prize, and handed over the game.

Hence the rule (user, August 2026): among the Supporters ACTUALLY IN HAND, a
forced discard follows the live value the agent already computes
(`_supp_values`) instead of the static proxies. It names no card, so it holds
for any deck, and it is confined to the Supporter band on purpose -- see
`DISCARD_SUPPORTER_LIVE_KEEP` / `DISCARD_SUPPORTER_DEAD_DROP`: it changes WHICH
Supporter is sacrificed, never how many non-Supporters are.
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
import ptcg.turn.options.card as card_options

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "archaludon_t9_the_forced_discard_keeps_the_energy_recovery_step132.json")

LANA = m.Lanas_Aid
DAWN = m.Dawn
BOSS = m.Boss_Orders
GRASS = m.Basic_Grass_Energy

# Hand of the record, in the order the select offers it.
_HAND = [m.Bayleef, LANA, DAWN, m.Meganium, m.Ultra_Ball, BOSS,
         m.Ultra_Ball, m.Applin, m.Forest_of_Vitality]
_LANA_INDEX = _HAND.index(LANA)
_DAWN_INDEX = _HAND.index(DAWN)


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


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return (copy.deepcopy(data["observacion_previa"]),
            copy.deepcopy(data["observation"]))


def _decision():
    previa, dec = _load()
    m.agent(previa)          # it brings the tracking of the opposing turn
    return m.agent(dec)


# ---------------------------------------------------------------------------
# 1. The record: the board that produced the mistake
# ---------------------------------------------------------------------------

def test_the_menu_of_step_132_is_the_one_from_the_record():
    _, dec = _load()
    cur = dec["current"]
    yo = cur["yourIndex"]
    mine, op = cur["players"][yo], cur["players"][1 - yo]

    assert [c["id"] for c in mine["hand"]] == _HAND
    # six of the nine cards go, and every one of them is an option
    assert dec["select"]["minCount"] == dec["select"]["maxCount"] == 6
    assert len(dec["select"]["option"]) == len(_HAND)

    # the premise of the whole line: the bench is FULL, so Dawn has nothing to
    # search for, and the discard is holding the Grass Lana's Aid recovers
    assert len([p for p in mine["bench"] if p]) == mine["benchMax"] == 5
    assert sum(1 for c in mine["discard"] if c["id"] == GRASS) >= 3

    # and the prize race that makes the energy decisive: they are at 3, and the
    # two they take for our Ogerpon ex later in this same turn leave them at 1
    assert len(mine["prize"]) == 2 and len(op["prize"]) == 3


def test_the_value_layer_already_preferred_lanas_aid():
    """The reading the discard scorer was ignoring: on this board Lana's Aid is
    the only Supporter in hand worth anything."""
    captured = {}
    real = m.score_option

    def spy(tcp, option, score):
        captured.setdefault("values", dict(getattr(tcp, "_supp_values", {}) or {}))
        return real(tcp, option, score)

    m.score_option = spy
    try:
        _decision()
    finally:
        m.score_option = real

    values = captured["values"]
    assert values.get(LANA, 0) > 0
    assert values.get(DAWN, 0) == 0
    assert values.get(BOSS, 0) == 0
    assert values[LANA] > max(values.get(DAWN, 0), values.get(BOSS, 0))


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_forced_discard_no_longer_throws_away_lanas_aid():
    choice = _decision()
    assert _LANA_INDEX not in choice, (
        "Lana's Aid is the only card that recovers the Grass the next turn "
        f"needs to reach 330 on their 300 HP ex; it was discarded ({choice})")


def test_the_supporter_sacrificed_is_the_one_the_board_cannot_use():
    """A pure permutation inside the Supporter set: someone still has to go,
    and it is the one with no live value (Dawn, on a full bench)."""
    choice = _decision()
    assert _DAWN_INDEX in choice


def test_it_does_not_change_how_many_non_supporters_are_discarded():
    """The constants are confined to the Supporter band on purpose: with the
    rule off and on, the same non-Supporters fall."""
    saved = card_options._SUPP_PLAY_IDS
    card_options._SUPP_PLAY_IDS = ()
    try:
        before = _decision()
    finally:
        card_options._SUPP_PLAY_IDS = saved
    after = _decision()

    supporters = {_HAND.index(sid) for sid in (LANA, DAWN, BOSS)
                  if sid in _HAND}
    assert sorted(set(before) - supporters) == sorted(set(after) - supporters)
    assert before != after       # the fixture really does discriminate


# ---------------------------------------------------------------------------
# 3. The rule is a strict no-op when the board has no preference
# ---------------------------------------------------------------------------

def test_a_lone_supporter_has_nothing_to_trade_against():
    """With a single Supporter in hand there is no permutation to make: the
    static branches keep the last word."""
    previa, dec = _load()
    hand = dec["current"]["players"][0]["hand"]
    dec["current"]["players"][0]["hand"] = [c for c in hand
                                            if c["id"] not in (DAWN, BOSS)]
    dec["select"]["option"] = dec["select"]["option"][:len(
        dec["current"]["players"][0]["hand"])]
    dec["select"]["minCount"] = dec["select"]["maxCount"] = 4
    m.agent(previa)
    choice = m.agent(dec)
    assert len(choice) == 4      # it still answers a legal selection


def test_the_band_of_the_constants_is_the_one_documented():
    """KEEP sits on the floor the branches already use for the last refill, and
    DROP between the highest single-copy Supporter (Lana's Aid, 35) and the
    cheapest generic item (a single Ultra Ball, 38). That is what makes the
    change a permutation among Supporters."""
    assert m.DISCARD_SUPPORTER_LIVE_KEEP == 2
    assert 35 < m.DISCARD_SUPPORTER_DEAD_DROP < 38
