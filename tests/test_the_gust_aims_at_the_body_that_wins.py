"""The Boss's promised the game and cashed one prize.

Scenario (`records/registro_014_pasos_145_hasta_166.json`, episode 90605790,
steps 154-155, turn 14 vs Alakazam, game WON in spite of this):

    US (2 prizes left)                        THEM (2 prizes left)
    active  Teal Mask Ogerpon ex 210/210,     active  Alakazam ex 140/140, 1
            4 effective energy                bench   **Fezandipiti ex 210/210, 0**
    bench   Fezandipiti ex, Meganium 160/4,           Dunsparce 60/0
            Teal Mask Ogerpon ex 210/4,               Abra 50/0
            Meowth ex
    hand    **Boss's Orders x2**, Poke Pad, Forest,
            Ogerpon ex, Hydrapple ex, **Xerosic's**,
            **1 Basic Grass**, Night Stretcher

Two prizes on our side and a two-prize body on their bench: the turn is a
finisher. Myriad Leaf Shower counts the energy on BOTH actives and ours is the
EFFECTIVE one (Meganium's Wild Growth doubles every Grass), so the active
Ogerpon at 4 does 30 + 30 x 4 = 150 on a 210 HP Fezandipiti ex -- and its own
Teal Dance, still unused and with a Grass in hand, takes it to 6: **30 + 30 x 6
= 210, the exact printed HP**. Gust it, dance, attack: the last two prizes.

WHAT THE AGENT DID. It played the Boss's -- and gusted the Abra, for one prize.

WHY IT FIRED: TWO MODELS OF THE SAME ATTACK. The winning-gust detector
(`_win_via_boss_gust`, in agent()) projects the pending charges of the turn,
Teal Dance included, and correctly read 210 on the Fezandipiti ex: it scored the
Boss's `winning_gust` = 20000 and, on the strength of that promise, the rule
`alakazam_yields_to_winning_gust` VETOED the Xerosic's Machinations that caps
Powerful Hand (the user's rule: "Boss's Orders only takes priority when it wins
the game"). One step later the gust TARGET scorer (`_ctx_gust_target`) rebuilt
the same damage with its own inline copy, which counted the manual attachment
RAW and did not know Teal Dance existed: 150 on 210 -> `can_ko = False` ->
`without_a_ko_prefer_the_dead_body` 1750 for the Fezandipiti ex against
`tier_ko` 3400 for the Abra. The turn spent the Supporter that could have won
the game AND the Supporter slot that could have capped Powerful Hand.

THE FIX. `_pending_grass_extra_eff` (ptcg/calc/energy.py) is now the single
source of truth for "what our active can still charge this turn", and both the
detector and the target scorer read it. The projection can only ever ADD
knockable targets, and it cannot promise energy the ability scorer will refuse
to attach: every matchup cap on Teal Dance (Alakazam, Hop's, Cubchoo, Crustle)
makes an exception for the attachment that ENABLES the KO on the opposing
active, which is exactly the case that flips `can_ko` here.

The two halves stay coherent by construction: where the projection is NOT
available -- test 4 below takes the Teal Dance away -- the detector stops seeing
a win, the Boss's drops out of `winning_gust`, and the Supporter slot goes back
to the Xerosic (`alakazam_priority_over_boss`, 7300).

Measured: 1 flip in the golden corpus (this one, step 155), 1594 tests green.
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
from cg.api import OptionType

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_t14_the_gust_aims_at_the_body_that_wins_step154.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
FEZANDIPITI = m.Fezandipiti_ex
BOSS_ORDERS = m.Boss_Orders
XEROSIC = m.Xerosic_Machinations
GRASS = m.Basic_Grass_Energy
ALAKAZAM, ABRA = 743, 741
MYRIAD_LEAF_SHOWER = 120

# Their bench at step 155, in the order the menu offers it.
GUST_FEZANDIPITI, GUST_DUNSPARCE, GUST_ABRA = 0, 1, 2


@pytest.fixture(autouse=True)
def reset_main_state():
    """The bug lives across two calls -- the MAIN menu that promises the win and
    the target menu that aims the gust -- so every test starts cold and replays
    the pair."""
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _frames():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return {item["step"]: copy.deepcopy(item["observation"])
            for item in data["sequence"]}


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _theirs(obs):
    cur = obs["current"]
    return cur["players"][1 - cur["yourIndex"]]


def _without_teal_dance(obs):
    """The same board with the active's ability already spent: the engine stops
    offering it, which is how the whole file detects a usable ability."""
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if not (o.get("type") == int(OptionType.ABILITY)
                and o.get("area") == int(m.AreaType.ACTIVE))]
    return obs


def _shape(o):
    """The identity of a menu option, readable from both the raw dict of the
    observation and the parsed object the scorer receives."""
    def field(name):
        return o.get(name) if isinstance(o, dict) else getattr(o, name, None)
    kind = field("type")
    return (int(kind) if kind is not None else None,
            field("area"), field("index"), field("attackId"),
            field("playerIndex"))


def _scores(obs):
    """{option index: score} exactly as agent() computed them."""
    import ptcg.turn.scoring as sc
    order = []
    original = sc.score_option

    def traced(tc, o, score):
        result = original(tc, o, score)
        order.append((_shape(o), result))
        return result

    sc.score_option = traced
    m.score_option = traced
    try:
        m.agent(obs)
    finally:
        sc.score_option = original
        m.score_option = original
    by_shape = dict(order)
    return {i: by_shape[_shape(o)]
            for i, o in enumerate(obs["select"]["option"])
            if _shape(o) in by_shape}


def _play_index_of(obs, card_id):
    """The menu index that PLAYS `card_id` from hand."""
    hand = _mine(obs)["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if (o.get("type") == int(OptionType.PLAY)
                and hand[o["index"]]["id"] == card_id):
            return i
    raise AssertionError(f"card {card_id} is not playable on this menu")


# ---------------------------------------------------------------------------
# 1. The board is the one that was recorded
# ---------------------------------------------------------------------------

def test_the_board_of_step_154_is_a_finisher():
    obs = _frames()[154]
    mine, theirs = _mine(obs), _theirs(obs)

    assert len(mine["prize"]) == 2, "our last two prizes are on the table"
    active = mine["active"][0]
    assert active["id"] == OGERPON and len(active["energies"]) == 4, (
        "4 EFFECTIVE energy: two physical Grass doubled by Wild Growth")

    target = theirs["bench"][GUST_FEZANDIPITI]
    assert target["id"] == FEZANDIPITI and target["hp"] == 210
    assert m.card_table[FEZANDIPITI].ex, (
        "two prizes on their bench: exactly what we have left")

    hand = [c["id"] for c in mine["hand"]]
    assert BOSS_ORDERS in hand and XEROSIC in hand and GRASS in hand
    assert not obs["current"]["supporterPlayed"]


def test_the_arithmetic_of_myriad_leaf_shower_lands_on_the_printed_hp():
    """4 effective + Teal Dance (one physical Grass doubled) = 6 -> 210."""
    assert m.attack_table[MYRIAD_LEAF_SHOWER].energies == [1, 1, 1]
    m.AGENT_STATE.meganium_in_play = True
    assert m._grass_attach_unit() == 2
    assert 30 + 30 * (4 + 2) == 210 == _frames()[154]["current"][
        "players"][1]["bench"][GUST_FEZANDIPITI]["hp"]


# ---------------------------------------------------------------------------
# 2. The decision that was broken: the gust aims at the body that wins
# ---------------------------------------------------------------------------

def test_the_boss_is_played_as_the_finisher_of_the_turn():
    frames = _frames()
    choice = m.agent(frames[154])
    opt = frames[154]["select"]["option"][choice[0]]
    assert opt.get("type") == int(OptionType.PLAY)
    assert _mine(frames[154])["hand"][opt["index"]]["id"] == BOSS_ORDERS


def test_the_gust_brings_up_the_fezandipiti_ex_and_not_the_abra():
    frames = _frames()
    m.agent(frames[154])
    assert m.agent(frames[155]) == [GUST_FEZANDIPITI], (
        "the body the detector promised the game on is the body the gust has "
        "to aim at; the Abra is one prize and leaves the game alive")


def test_the_target_scorer_ranks_the_two_prize_body_over_the_abra():
    frames = _frames()
    m.agent(frames[154])
    scores = _scores(frames[155])
    assert scores[GUST_FEZANDIPITI] > scores[GUST_ABRA], (
        f"Fezandipiti ex {scores[GUST_FEZANDIPITI]} has to beat Abra "
        f"{scores[GUST_ABRA]}: it is a knockable two-prize body")


# ---------------------------------------------------------------------------
# 3. The chain after the gust: dance, then finish
# ---------------------------------------------------------------------------

def _board_after_gusting_the_fezandipiti():
    """Step 156's MAIN menu with their active and their benched Fezandipiti ex
    swapped: the board the corrected gust produces."""
    frames = _frames()
    m.agent(frames[154])
    m.agent(frames[155])
    obs = frames[156]
    theirs = _theirs(obs)
    theirs["active"][0], theirs["bench"][0] = (theirs["bench"][0],
                                               theirs["active"][0])
    return obs


def test_after_the_gust_the_active_dances_for_the_sixth_energy():
    obs = _board_after_gusting_the_fezandipiti()
    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    assert (opt.get("type") == int(OptionType.ABILITY)
            and opt.get("area") == int(m.AreaType.ACTIVE)), (
        f"Teal Dance is the energy that turns 150 into 210; got {opt}")


def test_with_the_sixth_energy_on_board_it_attacks_for_the_last_two_prizes():
    obs = _board_after_gusting_the_fezandipiti()
    mine = _mine(obs)
    active = mine["active"][0]
    # Teal Dance resolved: the physical Grass leaves the hand and Wild Growth
    # doubles it on the way in.
    active["energies"] = [1] * 6
    active["energyCards"].append({"id": GRASS, "playerIndex": 0, "serial": 52})
    mine["hand"] = [c for c in mine["hand"] if c["id"] != GRASS]
    mine["handCount"] = len(mine["hand"])
    _without_teal_dance(obs)

    choice = m.agent(obs)
    opt = obs["select"]["option"][choice[0]]
    assert opt.get("attackId") == MYRIAD_LEAF_SHOWER, (
        f"210 damage on a 210 HP two-prize body with two prizes left; got {opt}")


# ---------------------------------------------------------------------------
# 4. The other half: no projection, no win, and the cap gets the slot back
# ---------------------------------------------------------------------------

def test_without_the_teal_dance_the_supporter_slot_goes_to_the_xerosic():
    """Counterfactual -- the ability already spent this turn. Without the sixth
    energy Myriad Leaf Shower stays at 150 on a 210 HP body: there is no winning
    gust, the Boss's stops being 20000 and the Xerosic that caps Powerful Hand
    (their hand is 12 cards = 240 damage) recovers the Supporter slot.
    """
    obs = _without_teal_dance(_frames()[154])
    scores = _scores(obs)
    boss = _play_index_of(obs, BOSS_ORDERS)
    xerosic = _play_index_of(obs, XEROSIC)
    assert scores[xerosic] > scores[boss], (
        f"Xerosic {scores[xerosic]} has to beat the Boss's {scores[boss]}: "
        "a gust that does not win the game never outranks capping Powerful Hand")
    assert scores[boss] < 20000, "no winning gust without the sixth energy"
