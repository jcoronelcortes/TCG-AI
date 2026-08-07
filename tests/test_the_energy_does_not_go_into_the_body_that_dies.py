"""This turn's energy does not go into a body the opponent cashes in tonight.

Scenario (user, episode 90593852, turn 4 vs Cynthia's Garchomp, WON with this
turn wasted). Step 30, the first decision of the turn:

    US                                      THEM
    active  Tapu Bulu 70/140, 0 energy      active  Cynthia's Gabite, 1 energy
    bench   Applin 40, 1 energy                     (+70 HP tool)
            Fezandipiti ex 210, 0 energy    bench   Cynthia's Roserade 130
    hand    Lillie's Determination,                 Cynthia's Roselia 70
            4x Basic Grass, 2x Night                Cynthia's Gabite 100
            Stretcher, Tapu Bulu

The agent attached a Grass to the ACTIVE Tapu Bulu and the turn ended without
attacking. Wood Hammer costs four and there is no Meganium in play to double
them, so one of four neither attacks; Tapu Bulu's retreat costs three, so it does
not pay that either. The energy bought NOTHING this turn -- and their Gabite
knocked the Tapu out on the next one with our Grass still on it.

WHY THE RULE THAT EXISTS DID NOT FIRE. `_energy_score_base` already refuses to
charge a doomed active that can neither attack nor retreat with the energy. Its
gate was `active_ko_likely`, which hangs off `_op_best_damage_vs`: that reads
Dragonslice's PRINTED 40 against 70 HP and answers "it survives". The 30 that
kills it is on their BENCH -- Cynthia's Roserade, "Attacks used by your Cynthia's
Pokemon do 30 more damage to your opponent's Active Pokemon" -- a body the
projector never receives, because the projector receives the attacker.

So the fix is two halves and both are deck-agnostic:

  * the READING: OP_TEAM_DAMAGE_BUFF, the census of the abilities that a body IN
    PLAY grants to its team, read off the board like the tools already are. It
    ships opt-in (`team_buff=True`) at `_active_doomed_real`, the projection
    written to be honest, and not at `active_ko_likely`, the heuristic that was
    calibrated against the blind number;
  * the RULE: that branch now reads `active_ko_likely or _active_doomed_real`,
    and its demotion actually demotes. `score - 100` did not: the active carries
    a +10 bonus of its own, so the doomed Tapu came out at 7910 against a
    Fezandipiti ex at 7900 and took the Grass anyway. It is now capped at
    `SCORE_CHARGE_DOOMED`, the ceiling this file already puts on a body inside
    the opponent's gift window -- a ceiling and not a veto, so an empty bench
    still has somewhere to put the energy.

The Grass now goes to the Fezandipiti ex: 210 HP on the bench, out of reach, a
real attacker, and one more Grass on our field for Syrup Storm. It is also the
decision the GOLDEN CORPUS had recorded for this step.

Coverage:
  * the record's board, so a future fixture cannot quietly stop measuring it;
  * the reading -- what the buff adds, and that the blind projector missed it;
  * the decision at step 30;
  * the limits: no buff body on their field and the reading is zero; the bonus
    does not stack; it belongs to an OWNER and pays nothing to a team that is not
    theirs; and a charge that makes the active ATTACK today is never demoted;
  * deck-agnostic by construction: the same shape with Hop's Snorlax.
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

TAPU = m.Tapu_Bulu
FEZ = m.Fezandipiti_ex
APPLIN = m.Applin
GRASS = m.Basic_Grass_Energy
ROSERADE = m.Cynthias_Roserade
SNORLAX = m.Hops_Snorlax
GABITE = m.Cynthias_Gabite

DRAGONSLICE_PRINTED = 40        # what the card says their active does
CHEER_ON_TO_GLORY = 30          # what their bench adds to it

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "cynthia_step30_the_energy_does_not_go_into_the_doomed_body.json")


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


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return (copy.deepcopy(data["previous_observation"]),
            copy.deepcopy(data["observation"]))


def _obs_step30():
    return _load()[1]


def _decide(obs):
    """The real decision, with the previous menu replayed before it."""
    previous, _ = _load()
    m.agent(previous)
    return m.agent(obs)


def _mine(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


def _theirs(obs):
    cur = obs["current"]
    return cur["players"][1 - cur["yourIndex"]]


def _play(obs, choice):
    """('ATTACH', card id of the body receiving it) / ('PLAY', id) / ('END', None)."""
    assert choice, f"the agent chose nothing: {choice}"
    o = obs["select"]["option"][choice[0]]
    mine = _mine(obs)
    if o["type"] == int(OptionType.ATTACH):
        body = (mine["active"][0] if o["inPlayArea"] == 4
                else mine["bench"][o["inPlayIndex"]])
        return ("ATTACH", body["id"])
    if o["type"] == int(OptionType.PLAY):
        return ("PLAY", mine["hand"][o["index"]]["id"])
    if o["type"] == int(OptionType.END):
        return ("END", None)
    return (o["type"], None)


def _states(obs):
    """The parsed `my_state` / `op_state`, the way `agent()` sees them."""
    parsed = m.to_observation_class(obs).current
    me = parsed.yourIndex
    return parsed.players[me], parsed.players[1 - me]


def _pokemon(obs, area, index=0):
    """A body of the observation, as `_op_team_damage_buff` receives it."""
    _, op_state = _states(obs)
    return (op_state.active[0] if area == "active" else op_state.bench[index])


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step30_the_board_is_the_records_one():
    obs = _obs_step30()
    mine, theirs = _mine(obs), _theirs(obs)

    assert obs["current"]["turn"] == 4
    assert obs["current"]["turnActionCount"] == 1, "the turn's first decision"

    active = mine["active"][0]
    assert active["id"] == TAPU
    assert active["hp"] == 70 and active["maxHp"] == 140, "half its life"
    assert active["energies"] == [], "and nothing on it"
    assert m.RETREAT_COST[TAPU] == 3, (
        "one Grass does not pay this retreat either, which is why the energy "
        "buys nothing today")
    assert not m.AGENT_STATE.meganium_in_play, (
        "with a Meganium each Grass would count double and one of four would "
        "not be one of four")

    bench_ids = [b["id"] for b in mine["bench"]]
    assert bench_ids == [APPLIN, FEZ], bench_ids
    assert mine["bench"][1]["hp"] == 210 and mine["bench"][1]["energies"] == [], (
        "the Fezandipiti ex is the body that survives and it is empty")
    assert [c["id"] for c in mine["hand"]].count(GRASS) == 4

    assert theirs["active"][0]["id"] == GABITE
    assert len(theirs["active"][0]["energies"]) == 1, "it can attack right now"
    assert ROSERADE in [b["id"] for b in theirs["bench"]], (
        "the +30 that kills the Tapu is on their BENCH; without this body the "
        "record is another record")


# ---------------------------------------------------------------------------
# 2. The reading: what the projector could not see
# ---------------------------------------------------------------------------

def test_step30_their_bench_is_what_kills_the_tapu():
    obs = _obs_step30()
    _, op_state = _states(obs)
    assert m._op_team_damage_buff(op_state) == CHEER_ON_TO_GLORY


def test_step30_the_blind_projection_said_the_tapu_was_fine():
    """40 printed against 70 HP: every defensive reading answered "it lives"."""
    obs = _obs_step30()
    my_state, op_state = _states(obs)
    active = my_state.active[0]
    m.agent(copy.deepcopy(obs))          # publishes the per-turn snapshots

    blind = m._op_active_attack_damage_to(op_state.active[0], active,
                                          op_state.handCount, scaled=True)
    honest = m._op_active_attack_damage_to(op_state.active[0], active,
                                           op_state.handCount, scaled=True,
                                           team_buff=True)
    assert blind == DRAGONSLICE_PRINTED
    assert blind < active.hp, "this is why the rule that exists never fired"
    assert honest == DRAGONSLICE_PRINTED + CHEER_ON_TO_GLORY
    assert honest >= active.hp, "and this is the hit the engine actually dealt"


# ---------------------------------------------------------------------------
# 3. The decision
# ---------------------------------------------------------------------------

def test_step30_the_energy_goes_to_a_body_that_survives():
    obs = _obs_step30()
    choice = _decide(obs)
    assert _play(obs, choice) == ("ATTACH", FEZ), _play(obs, choice)


def test_step30_the_doomed_active_is_not_the_target():
    obs = _obs_step30()
    kind, body = _play(obs, _decide(obs))
    assert not (kind == "ATTACH" and body == TAPU), (
        "the Grass went to a body that cannot attack, cannot retreat and is "
        "knocked out before it can ever use it")


# ---------------------------------------------------------------------------
# 4. The limits
# ---------------------------------------------------------------------------

def test_without_the_buff_body_the_reading_is_zero():
    """It is the TABLE that fires, not the matchup: no Roserade, no +30."""
    obs = _obs_step30()
    theirs = _theirs(obs)
    theirs["bench"] = [b for b in theirs["bench"] if b["id"] != ROSERADE]
    _, op_state = _states(obs)
    assert m._op_team_damage_buff(op_state) == 0


def test_the_buff_does_not_stack():
    """Extra Helpings says so in print, and two Roserades are one +30."""
    obs = _obs_step30()
    theirs = _theirs(obs)
    dupe = copy.deepcopy(next(b for b in theirs["bench"] if b["id"] == ROSERADE))
    dupe["serial"] = dupe["serial"] + 1000
    theirs["bench"].append(dupe)
    _, op_state = _states(obs)
    assert m._op_team_damage_buff(op_state) == CHEER_ON_TO_GLORY


def test_the_buff_belongs_to_an_owner():
    """A Roserade pays nothing to an attacker that is not Cynthia's."""
    obs = _obs_step30()
    theirs = _theirs(obs)
    theirs["active"][0]["id"] = m.Budew      # a body outside the subset
    _, op_state = _states(obs)
    assert m._op_team_damage_buff(op_state) == 0


def test_the_reading_is_deck_agnostic():
    """The same shape with the other archetype in the table."""
    obs = _obs_step30()
    theirs = _theirs(obs)
    theirs["active"][0]["id"] = m.Hops_Phantump
    for b in theirs["bench"]:
        if b["id"] == ROSERADE:
            b["id"] = SNORLAX
    _, op_state = _states(obs)
    assert m._op_team_damage_buff(op_state) == 30


def test_a_charge_that_attacks_today_is_never_demoted():
    """The rule only touches energy that buys NOTHING this turn.

    The same doomed Tapu Bulu with three Grass already on it: the fourth pays
    Wood Hammer, so the charge is the turn's attack and the ceiling must not see
    it.
    """
    obs = _obs_step30()
    active = _mine(obs)["active"][0]
    active["energies"] = [1, 1, 1]
    active["energyCards"] = [{"id": GRASS, "playerIndex": 1, "serial": 900 + i}
                             for i in range(3)]
    kind, body = _play(obs, _decide(obs))
    assert (kind, body) == ("ATTACH", TAPU), (
        "with the attack one Grass away the doomed reading must not divert it")
