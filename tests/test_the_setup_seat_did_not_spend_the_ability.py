"""The seat the SETUP gave did not spend the ability.

Origin (user, `records/registro_001_pasos_005_hasta_010.json`, steps 5-10,
episode 93488655 vs **Zoroark ex** -- LOST):

    US (6 prizes)                        RIVAL (6 prizes)
    active  Meowth ex 170/170, no {G}    active  N's Zekrom 70/70
    bench   --                           bench   --
    hand    Xerosic's, Forest x2,        stadium --
            ULTRA BALL, Basic {G},
            Bayleef, Dipplin             turn 1, WE GO FIRST

        [1] PLAY Forest of Vitality
        [2] PLAY Ultra Ball        score 31450   <-- played
        [3] PLAY Forest of Vitality
        [4] ATTACH Basic {G}
        [5] END

Our turn 1 had no attacker and no line to start: the two Stage 1s in hand had
nothing to sit on. The Ultra Ball was played and it was played AT THE RIGHT
PRICE -- 31450 is `_ub_engine_refresh_pivot`, the UB -> Meowth ex -> Last-Ditch
Catch -> Lillie's engine, and scoring it ARMS `_ub_engine_pivot_turn` precisely
so that the later fetch menu completes the chain. Then the fetch bought a
**Chikorita** (1050), benched it and put the turn's energy on it. `ub->meowth`
had scored **10**.

WHY. `_meowth_ld_free` asks whether some Meowth ex in play `appearThisTurn`,
because a Meowth benched earlier in the turn has already spent the turn's only
Last-Ditch. Our starting active WAS a Meowth ex, and everything the SETUP deals
carries `appearThisTurn` on turn 1 -- so the rule read "the ability is already
spent" about a body that never used it. The setup plays nothing: no ability
fires there, and the record's own menu proves it (no Supporter was searched).
`last_ditch_produces_nothing` then fired at the top of `_RULES_UB_MEOWTH` and
the two menus of the same Ultra Ball contradicted each other -- exactly the
failure `ptcg/decision/ultra_ball.py` warns about in its header.

THE CORRECTION IS DECK-AGNOSTIC BY CONSTRUCTION, because it is a fact of the
LOG and not of the card: the engine writes a `PLAY` entry for a card played from
hand and a `MOVE_CARD` for the setup's placement (and for a body an effect puts
down straight from the deck), and the two never land on the same serial.
`AGENT_STATE._in_play_without_a_play` collects the serials that got their seat
without being played, so any come-into-play ability of any deck can ask the
question the same way. `fromArea` is what decides: a promotion after a knockout
and a retreat are MOVE_CARD entries into the active spot too, and a body walking
from the bench to the front did not get a new seat.
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

import main as m  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402
from state_builder import (BASIC_GRASS, FOREST_OF_VITALITY, Scenario,  # noqa: E402
                           pk)

BAYLEEF = m.Bayleef
CHIKORITA = m.Chikorita
DIPPLIN = m.Dipplin
LILLIE = m.Lillie_Determination
MEOWTH = m.Meowth_ex
XEROSIC = m.Xerosic_Machinations
ZEKROM = 292                       # their opening active in the record

_RECORD = ROOT / "records" / "registro_001_pasos_005_hasta_010.json"


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)
    yield
    reset_agent(m)


def _fetched(obs, choice):
    """Which card a TO_HAND choice takes out of the deck view."""
    option = obs["select"]["option"][choice[0]]
    return obs["select"]["deck"][option["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The record: the log says the setup did not PLAY anything
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _RECORD.exists(), reason="records/ is git-ignored")
def test_the_record_seats_the_meowth_with_a_move_and_never_plays_it():
    record = json.loads(_RECORD.read_text(encoding="utf-8"))
    obs = record["steps"][0][0]["observation"]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    active = mine["active"][0]

    # Turn 1, we go first, and the body in front is the ability's own body,
    # flagged as having appeared this turn like everything the setup deals.
    assert cur["turn"] == 1 and cur["firstPlayer"] == cur["yourIndex"]
    assert active["id"] == MEOWTH and active["appearThisTurn"] is True

    seat = cur["yourIndex"]
    moved = [lg for lg in obs["logs"]
             if lg.get("playerIndex") == seat
             and lg.get("serial") == active["serial"]
             and lg.get("type") == int(m.LogType.MOVE_CARD)]
    played = [lg for lg in obs["logs"]
              if lg.get("playerIndex") == seat
              and lg.get("serial") == active["serial"]
              and lg.get("type") == int(m.LogType.PLAY)]
    assert len(moved) == 1 and not played
    assert moved[0]["fromArea"] == int(m.AreaType.HAND)
    assert moved[0]["toArea"] == int(m.AreaType.ACTIVE)


@pytest.mark.skipif(not _RECORD.exists(), reason="records/ is git-ignored")
def test_the_record_buys_the_engine_and_now_completes_it():
    """The Ultra Ball was bought at 31450 -- the price of the Meowth engine --
    and the fetch that follows has to be the body that engine needs."""
    record = json.loads(_RECORD.read_text(encoding="utf-8"))
    fetched = None
    for pair in record["steps"]:
        item = pair[0]
        obs = item["observation"]
        if item.get("status") != "ACTIVE" or not obs.get("select"):
            continue
        choice = m.agent(copy.deepcopy(obs))
        if obs.get("step") == 5:
            # The play menu: the Ultra Ball, and the engine armed by its price.
            assert m.AGENT_STATE._ub_engine_pivot_turn is True
        if obs.get("step") == 7:
            fetched = _fetched(obs, choice)

    assert fetched == MEOWTH
    # ...and the reason it could be: the setup's serial is on the record.
    assert 20 in m.AGENT_STATE._in_play_without_a_play


# ---------------------------------------------------------------------------
# 2. The reading on its own: which entries into play are not plays
# ---------------------------------------------------------------------------

def _board(logs, active_appeared=True):
    """Turn 1 going first, the record's board, with `logs` attached."""
    esc = Scenario(turn=1, step=7, tac=3, first_player=0)
    obs = (esc
           .my_active(pk(MEOWTH, aparecio=active_appeared))
           .my_hand(XEROSIC, BASIC_GRASS, BAYLEEF, DIPPLIN)
           .my_discard(FOREST_OF_VITALITY, FOREST_OF_VITALITY)
           .op_active(pk(ZEKROM))
           .op_zones(hand=6, deck=47, prizes=6)
           .deck(CHIKORITA, MEOWTH, LILLIE, BAYLEEF, DIPPLIN)
           .fetch_ultra_ball()
           .rest_to_discard()
           .build())
    serial = obs["current"]["players"][0]["active"][0]["serial"]
    obs["logs"] = [dict(lg, serial=serial) for lg in logs]
    return obs, serial


def _setup_log():
    return [{"type": int(m.LogType.MOVE_CARD), "playerIndex": 0,
             "cardId": MEOWTH, "fromArea": int(m.AreaType.HAND),
             "toArea": int(m.AreaType.ACTIVE)}]


def _play_log():
    return [{"type": int(m.LogType.PLAY), "playerIndex": 0, "cardId": MEOWTH}]


def _promotion_log():
    return [{"type": int(m.LogType.MOVE_CARD), "playerIndex": 0,
             "cardId": MEOWTH, "fromArea": int(m.AreaType.BENCH),
             "toArea": int(m.AreaType.ACTIVE)}]


def test_the_setup_seat_is_remembered_and_a_played_body_is_not():
    obs, serial = _board(_setup_log())
    m.agent(obs)
    assert serial in m.AGENT_STATE._in_play_without_a_play

    reset_agent(m)
    obs, serial = _board(_play_log())
    m.agent(obs)
    assert serial not in m.AGENT_STATE._in_play_without_a_play


def test_a_body_walking_from_the_bench_to_the_front_got_no_new_seat():
    """A promotion after a knockout and a retreat are MOVE_CARD entries into the
    active spot as well. Counting them would hand back the turn's ability to a
    body that had already played it."""
    obs, serial = _board(_promotion_log())
    m.agent(obs)
    assert serial not in m.AGENT_STATE._in_play_without_a_play


def test_the_play_wins_over_the_move_on_the_same_serial():
    """Defensive: if a serial ever arrived by both routes, the PLAY decides."""
    obs, serial = _board(_setup_log() + _play_log())
    m.agent(obs)
    assert serial not in m.AGENT_STATE._in_play_without_a_play


# ---------------------------------------------------------------------------
# 3. The fetch: the reading is what changes the card
# ---------------------------------------------------------------------------

def test_the_search_buys_the_body_that_brings_the_supporter():
    obs, _ = _board(_setup_log())
    assert _fetched(obs, m.agent(obs)) == MEOWTH


def test_the_control_is_a_meowth_we_really_played_this_turn():
    """The counterfactual that says the reading is the cause: the SAME board
    with the same body flagged `appearThisTurn`, and a PLAY log on its serial.
    There the turn's Last-Ditch really is spent and the search goes back to
    starting a line."""
    obs, _ = _board(_play_log())
    assert _fetched(obs, m.agent(obs)) == CHIKORITA
