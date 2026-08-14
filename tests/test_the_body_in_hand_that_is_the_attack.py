"""THE BODY IN HAND THAT IS THE ATTACK: `ROUTE_ASSEMBLE`.

User, registro_010 step 133, episode 92720952 vs Mega Lucario ex. Our turn 10,
three prizes left for us and ONE for them -- their next knockout ends the game:

    US (3 prizes)                         THEM (1 prize)
    active Hydrapple ex, 2 Grass          active MEGA LUCARIO ex 340/340
    bench  Ogerpon ex 3, Ogerpon ex 2,           -- a Mega ex, THREE prizes
           Meowth ex, Fezandipiti ex
    hand   Chikorita, Bayleef, MEGANIUM, Boss's Orders x2, ...
    field  Forest of Vitality, bench 4/5

Seven Grass on our board, so Syrup Storm read 30 + 30x7 = 240 against 340 and
the plan printed `win_route=''`, `prizes_today=1`, mode RACE. But Wild Growth
makes every basic Grass count as {G}{G} and Forest of Vitality lifts the "it
came down this turn" restriction, so Chikorita -> Bayleef -> Meganium was three
actions out of that same hand and the field went to FOURTEEN: 30 + 30x14 = 450
>= 340, three prizes, the game. The agent spent the Supporter gusting a 150 HP
Hariyama instead, assembled the Meganium anyway, and threw those 450 at a body
worth ONE prize.

The hole was general and it was not about Meganium: every "can we knock this
out" reading prices our attack against the field AS IT STANDS, and none of them
asked whether a body still in HAND changes how hard WE hit. For an attack that
scales with the whole board, a card in hand is damage, not development.

The file covers the three layers the correction needed: the board primitives
(what the field is worth once the doubler lands, and whether it can land at
all), the ROUTE the plan publishes, and the turn the agent then plays on the
record's own observation.
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
from ptcg.calc import energy as ce
from ptcg.cards.groups import GRASS_DOUBLER_LINE_IDS
from ptcg.turn import finalize as fin
from ptcg.turn import game_plan as gp

RECORD = ROOT / "records" / "registro_010_pasos_126_hasta_140.json"
# The menu of step 133: the last one on which the whole line was still in hand
# and the Supporter still unspent.
PIVOTAL_STEP = 7
MEGA_LUCARIO = 678


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _pivotal_observation():
    """The record's own board, or a skip: `records/` is transient (R6).

    It is re-harvested, so the file that carries this turn may simply not be
    there. The board is worth replaying VERBATIM rather than rebuilt by hand --
    it is the one that cost the game -- but nothing here may go red because a
    harvest took it away, and the primitives above already pin the arithmetic
    on boards of their own.
    """
    if not RECORD.exists():
        pytest.skip("records/ is transient local data; this board is not on disk")
    steps = json.loads(RECORD.read_text(encoding="utf-8"))["steps"]
    if len(steps) <= PIVOTAL_STEP or len(steps[PIVOTAL_STEP]) < 2:
        pytest.skip("the harvested record does not carry this turn any more")
    obs = copy.deepcopy(steps[PIVOTAL_STEP][1].get("observation"))
    if not obs or not obs.get("select"):
        pytest.skip("the harvested record does not carry this menu any more")
    return obs


# ---------------------------------------------------------------------------
# The board primitives
# ---------------------------------------------------------------------------

def test_the_field_is_worth_double_once_the_doubler_lands():
    """Seven Grass on the field is fourteen with Wild Growth up: 240 -> 450."""
    obs = m.to_observation_class(_pivotal_observation())
    mine = obs.current.players[1]

    total = ce.count_total_grass_energy(mine)
    assert total == 7
    assert 30 + 30 * total == 240                     # what the turn read

    after = ce.field_grass_after_doubler(mine, total)
    assert after == 14
    assert 30 + 30 * after == 450                     # what it was worth
    assert 450 >= m.card_table[MEGA_LUCARIO].hp == 340


def test_the_doubling_is_not_applied_twice():
    """With a doubler ALREADY in play the observation has done the doubling.

    The same trap `calc_syrup_storm_damage` carries a pinned test against: the
    `energies` list is EFFECTIVE, so counting the cards again would report a
    board that does not exist.
    """
    obs = m.to_observation_class(_pivotal_observation())
    mine = obs.current.players[1]
    m.AGENT_STATE.meganium_in_play = True
    assert ce.field_grass_after_doubler(mine, 14) == 14


def test_the_three_routes_that_put_the_doubler_on_the_board():
    """Which assemblies are legal, and which the game's own rules refuse."""
    line = {m.Chikorita: 1, m.Bayleef: 1, m.Meganium: 1}

    # The Stage 2 onto a Stage 1 that was already there: no Forest needed.
    assert ce.grass_doubler_arrives(
        {m.Meganium: 1}, {m.Bayleef: 1}, {m.Bayleef: 1},
        forest_in_play=False, bench_free=0)

    # ... but not onto a Stage 1 that came down THIS turn.
    assert not ce.grass_doubler_arrives(
        {m.Meganium: 1}, {m.Bayleef: 1}, {m.Chikorita: 1},
        forest_in_play=False, bench_free=0)

    # The whole line out of hand: three actions, and only under Forest, because
    # both bodies it creates would be evolving on the turn they arrived.
    assert ce.grass_doubler_arrives(
        line, {}, {}, forest_in_play=True, bench_free=1)
    assert not ce.grass_doubler_arrives(
        line, {}, {}, forest_in_play=False, bench_free=1)

    # ... and not with the bench full: the Basic has nowhere to go.
    assert not ce.grass_doubler_arrives(
        line, {}, {}, forest_in_play=True, bench_free=0)

    # No Stage 2 in hand is no route, however much of the line is on the board.
    assert not ce.grass_doubler_arrives(
        {m.Chikorita: 1, m.Bayleef: 1}, {m.Chikorita: 1}, {m.Chikorita: 1},
        forest_in_play=True, bench_free=1)


def test_a_doubler_already_in_play_has_nothing_left_to_arrive():
    """Wild Growth does not stack, so the route switches itself off."""
    m.AGENT_STATE.meganium_in_play = True
    assert not ce.grass_doubler_arrives(
        {m.Chikorita: 1, m.Bayleef: 1, m.Meganium: 1}, {}, {},
        forest_in_play=True, bench_free=1)


def test_the_line_is_derived_from_the_deck_and_not_written_out():
    """`GRASS_DOUBLER_LINE_IDS` is the line that ENDS in a doubler, computed.

    A deck whose doubler sits on another line gets the same answer without an
    edit, which is the whole point of deriving it from `EVO_LINES`.
    """
    assert GRASS_DOUBLER_LINE_IDS == {m.Chikorita, m.Bayleef, m.Meganium}
    assert m.Applin not in GRASS_DOUBLER_LINE_IDS


# ---------------------------------------------------------------------------
# The route the plan publishes
# ---------------------------------------------------------------------------

def test_the_record_board_reads_as_a_turn_that_wins():
    """The plan the record printed as RACE is a WIN_NOW along ROUTE_ASSEMBLE."""
    m.agent(_pivotal_observation())
    plan = m.AGENT_STATE.turn_plan

    assert plan.win_route == gp.ROUTE_ASSEMBLE
    assert plan.mode == gp.MODE_WIN_NOW
    assert plan.wins_this_turn and plan.win_needs_assembly
    # It spends no Supporter -- which is exactly why it is chosen above a gust.
    assert not plan.win_needs_supporter
    # ... and the knockout is not on the board yet: nothing may attack first.
    assert plan.win_needs_charge


def test_the_route_only_fires_when_it_ENDS_the_game():
    """Three prizes left and a Mega ex in front is the whole licence.

    With one more prize to take than the target is worth, assembling is still
    good development -- but it is not a route, it does not rewrite the turn and
    it does not veto the Supporter.
    """
    obs = _pivotal_observation()
    obs["current"]["players"][1]["prize"].append(None)   # four prizes, not three
    m.agent(obs)
    assert m.AGENT_STATE.turn_plan.win_route != gp.ROUTE_ASSEMBLE


def test_without_the_stadium_the_line_is_not_a_route():
    """Forest of Vitality is what makes the three-card chain legal today.

    Without it the Bayleef the first evolution creates cannot be evolved until
    next turn, and a route that cannot be executed is worse than no route: it
    would put the whole turn under the wrong sentence.
    """
    obs = _pivotal_observation()
    obs["current"]["stadium"] = []
    m.agent(obs)
    assert m.AGENT_STATE.turn_plan.win_route != gp.ROUTE_ASSEMBLE


# ---------------------------------------------------------------------------
# The turn the agent plays
# ---------------------------------------------------------------------------

def _hand_ids(obs_dict):
    return [c["id"] for c in obs_dict["current"]["players"][1]["hand"]]


def test_the_turn_starts_by_benching_the_basic_of_the_line():
    """The record played Boss's Orders here. The line goes first."""
    obs = _pivotal_observation()
    choice = m.agent(obs)

    chosen = obs["select"]["option"][choice[0]]
    assert chosen["type"] == 7                      # PLAY, out of hand
    assert _hand_ids(obs)[chosen["index"]] == m.Chikorita


def test_the_gust_is_vetoed_while_the_assembly_is_the_turn(monkeypatch):
    """Gusting swaps their active away from the body worth our last prizes.

    It is not even an alternative: the assembly spends no Supporter, so the
    Boss's is still in hand either way. The scores are read through the debug
    hook, which is the one place the whole ranking of a menu passes through.
    """
    seen = {}
    monkeypatch.setattr(
        fin, "_debug_log_decision",
        lambda context, select, scores, obs, my_index, top_n=3:
            seen.update(scores=list(scores)))

    obs = _pivotal_observation()
    m.agent(obs)

    boss_options = [i for i, o in enumerate(obs["select"]["option"])
                    if o.get("type") == 7
                    and _hand_ids(obs)[o["index"]] == m.Boss_Orders]
    assert len(boss_options) == 2, "the record's menu offered two Boss's Orders"
    assert all(seen["scores"][i] <= 0 for i in boss_options)
    # ... and the line it yields to is above every band of the ladder.
    line_options = [i for i, o in enumerate(obs["select"]["option"])
                    if o.get("type") == 7
                    and _hand_ids(obs)[o["index"]] in GRASS_DOUBLER_LINE_IDS]
    assert line_options
    assert all(seen["scores"][i] == m.SCORE_ASSEMBLE_WINS_THE_GAME
               for i in line_options)


def test_once_the_doubler_is_down_the_attack_closes_it():
    """The board the assembly creates, rendered the way the engine renders it.

    Wild Growth is applied by the OBSERVATION -- each basic Grass appears twice
    in `energies` -- so this is the same board the simulator would hand back
    after the three plays, and on it the route becomes the ordinary one:
    attack with the active, three prizes, game.
    """
    obs = _pivotal_observation()
    mine = obs["current"]["players"][1]

    for body in [mine["active"][0]] + mine["bench"]:
        grass = sum(1 for c in body.get("energyCards", [])
                    if c["id"] == m.Basic_Grass_Energy)
        body["energies"] = body["energies"] + [m.EnergyType.GRASS] * grass
    mine["bench"].append({
        "appearThisTurn": True, "energies": [], "energyCards": [],
        "hp": 160, "id": m.Meganium, "maxHp": 160, "playerIndex": 1,
        "preEvolution": [{"id": m.Chikorita, "playerIndex": 1, "serial": 67},
                         {"id": m.Bayleef, "playerIndex": 1, "serial": 69}],
        "serial": 71, "tools": [],
    })
    ids = _hand_ids(obs)
    for card_id in (m.Meganium, m.Bayleef, m.Chikorita):
        mine["hand"].pop(ids.index(card_id))
        ids = _hand_ids(obs)
    mine["handCount"] = len(mine["hand"])
    obs["select"]["option"] = [
        {"type": 7, "index": 0},
        {"type": 13, "attackId": 195},
        {"type": 14},
    ]

    choice = m.agent(obs)
    assert m.AGENT_STATE.turn_plan.win_route == gp.ROUTE_ACTIVE
    assert m.AGENT_STATE.turn_plan.prizes_today == 3
    assert obs["select"]["option"][choice[0]]["type"] == 13     # ATTACK
