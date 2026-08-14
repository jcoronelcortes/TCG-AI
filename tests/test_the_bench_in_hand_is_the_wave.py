"""The turn Festival Grounds was ours, and we threw it away to play our own stadium.

Scenario (user, `records/registro_004_pasos_053_hasta_087.json`, episode
92669047, turn 4 step 61 vs *Festival Lead* -- LOST):

    US (6 prizes)                          RIVAL (5 prizes)
    active  Teal Mask Ogerpon ex           active  Dipplin  80/80, 1 {G}
            **80**/210, 2 {G}, retreat 1           + Brave Bangle
    bench   Teal Mask Ogerpon ex 210, 1{G} bench   Thwackey       100
            Meowth ex            170               Fezandipiti ex 210
            **Dipplin 80, 1 {G}**                  Applin          40
            Fezandipiti ex       210               Applin          40
    hand    Ultra Ball, **Tapu Bulu**,             Grookey         70
            **Forest of Vitality**, 1 {G},
            Hydrapple ex                   stadium **Festival Grounds** (theirs)

    energyAttached False, supporterPlayed False, bench 4/5

THE TURN THE BOARD WAS OFFERING. Festival Grounds is SHARED, so our benched
Dipplin -- already carrying its one Grass -- throws *Do the Wave* TWICE. Tapu
Bulu out of hand fills the fifth seat and the wave becomes 20 x 5 = **100**.
Retreat the Ogerpon ex (cost 1, it carries 2): the first wave buries their 80 HP
Dipplin and the second lands 100 on whatever they promote, which kills four of
their five bodies -- only the 210 HP Fezandipiti ex survives it. The prize is
cashed by a **1-prize** body, and the wounded ex goes to the bench, where its
*Tera* prevents all damage.

WHAT THE AGENT DID INSTEAD, and the three losses are one causal chain:

  1. it played **Forest of Vitality**, discarding their Festival Grounds -- which
     switched off our own double wave;
  2. that stadium is precisely what makes a Pokemon played this turn evolvable,
     so the just-evolved **Dipplin became Hydrapple ex**: the attacker of the
     plan stopped existing;
  3. and Tapu Bulu, the fifth body, was vetoed at -1 the whole time.

It then retreated the ex anyway and hit an 80 HP Dipplin with Syrup Storm for
**390**. One prize, 310 damage on the floor, no second wave, and a 2-prize body
left in the front seat.

THE READING WAS ALREADY THERE AND IT WAS ALREADY RIGHT. `_festival_sac_pivot`
had fired: from step 58 the plan named `attacker = 3`, the benched Dipplin, with
`remain_hp = 0`. `festival_lead_pays_us_now` was **True** on that very menu. What
failed is what the flag was allowed to forbid:

    _RULES_FOREST_PLAY:  switch_off_festival_lead   26000  <- stood down, correctly
                         enables_the_evolution_chain 22000  <- played it anyway

A ladder answers with the FIRST rung that matches, so a guard that silences one
rung forbids nothing: the three rungs below inherit the play. The exception now
lives at the TOP of the ladder as `their_stadium_is_paying_us_today`, which is
the general shape of the lesson -- an exception to "play this card" is an
exception to the CARD, not to one of the reasons for playing it.

The other two consequences of the same sentence, which had no predicate at all:

  * `ptcg/turn/options/evolve.py` -- the body that IS the attack does not get
    evolved. Hydrapple ex on top of the Dipplin is a bigger body and a smaller
    turn: one wave instead of two, two prizes in the front seat instead of one;
  * `ptcg/turn/options/play.py` -- the bench IS the attack. A 1-prize Basic into
    a free seat is +20 on each wave, and `_festival_wave_bench` counts it so the
    detector and the pivot price the same knockout.

MEASUREMENT. Frozen corpus (50 games, 3 580 decisions): **zero flips**. Local
records: exactly ONE, this step, Forest -> Tapu Bulu. Both are the expected
answer -- `_festival_grounds_in_play` closes every rule here and no other deck in
`deck/rivales/` puts that stadium on the field. Self-play has no signal in this
matchup (the generic OpponentBot cannot pilot `festival_lead.csv`, 98.9% in both
arms), which is written down in [[festival-grounds-dipplin-doble-ataque]].
"""

import copy
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from cg.api import to_observation_class
import ptcg.turn.finalize as finalize

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "festival_lead_t4_the_bench_is_the_wave_step61.json")

DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
FEZ = m.Fezandipiti_ex
TAPU = m.Tapu_Bulu
FOREST = m.Forest_of_Vitality
FESTIVAL_GROUNDS = m.Festival_Grounds
GRASS = m.Basic_Grass_Energy
ULTRA_BALL = m.Ultra_Ball

THWACKEY = 90        # 100 HP: the body a wave of 80 leaves alive and 100 does not


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _raw():
    return json.load(open(_FIXTURE, encoding="utf-8"))


def _obs(key="observation", **mut):
    o = copy.deepcopy(_raw()[key])
    cur = o["current"]
    yo = cur["yourIndex"]
    if mut.get("without_stadium"):
        cur["stadium"] = []
    if mut.get("festival_grounds"):
        cur["stadium"] = [{"id": FESTIVAL_GROUNDS, "playerIndex": 1 - yo,
                           "serial": 60}]
    if mut.get("without_tapu"):
        cur["players"][yo]["hand"] = [
            c for c in cur["players"][yo]["hand"] if c["id"] != TAPU]
        cur["players"][yo]["handCount"] = len(cur["players"][yo]["hand"])
    if mut.get("full_bench"):
        me = cur["players"][yo]
        me["bench"] = me["bench"] + [copy.deepcopy(me["bench"][1])]
        me["bench"][-1]["serial"] = 999
    return o


def _decide(obs):
    return list(m.agent(obs))


def _scores_of(obs):
    """The score the agent gave EVERY option of this menu.

    `TIER_CENSUS_SINK` is the hook `finalizar` already publishes for the tier
    census; borrowing it keeps the test out of the agent's internals and away
    from re-deriving a scoring call by hand.
    """
    captured = {}

    def sink(context, select, scores, tiers, obs_, my_index):
        captured.setdefault("scores", list(scores))

    previous = finalize.TIER_CENSUS_SINK
    finalize.TIER_CENSUS_SINK = sink
    try:
        m.agent(obs)
    finally:
        finalize.TIER_CENSUS_SINK = previous
    return captured["scores"]


def _forest_score(obs):
    cur = obs["current"]
    me = cur["players"][cur["yourIndex"]]
    idx = next(i for i, o in enumerate(obs["select"]["option"])
               if o["type"] == m.OptionType.PLAY
               and me["hand"][o["index"]]["id"] == FOREST)
    return _scores_of(obs)[idx]


def _played_card_id(obs, choice):
    """The hand card an option of the menu plays, by id."""
    opt = obs["select"]["option"][choice[0]]
    cur = obs["current"]
    me = cur["players"][cur["yourIndex"]]
    return me["hand"][opt["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The fixture is the board of the record
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_board_of_the_record():
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    me, rival = cur["players"][yo], cur["players"][1 - yo]

    # Festival Grounds on the table, and it is THEIRS: the stadium is SHARED.
    assert [c["id"] for c in cur["stadium"]] == [FESTIVAL_GROUNDS]
    assert cur["stadium"][0]["playerIndex"] == 1 - yo

    # Our active is a wounded Teal Mask Ogerpon ex that retreats for one.
    act = me["active"][0]
    assert act["id"] == OGERPON and act["hp"] == 80 and act["maxHp"] == 210
    assert len(act["energies"]) == 2 and m.RETREAT_COST[OGERPON] == 1

    # The Dipplin is on the bench, charged, with a seat still free next to it.
    assert [b["id"] for b in me["bench"]] == [OGERPON, MEOWTH, DIPPLIN, FEZ]
    assert len(me["bench"][2]["energies"]) == 1
    assert len(me["bench"]) == 4 and me["benchMax"] == 5

    # Hand: the fifth body, our own stadium, the evolution and a Grass.
    assert sorted(c["id"] for c in me["hand"]) == sorted(
        [ULTRA_BALL, TAPU, FOREST, GRASS, HYDRAPPLE])
    assert cur["energyAttached"] is False
    assert cur["supporterPlayed"] is False

    # Their active is the 80 HP Dipplin the wave has to reach.
    assert rival["active"][0]["id"] == DIPPLIN and rival["active"][0]["hp"] == 80
    # ...and a 100 HP Thwackey on their bench: the body that decides whether the
    # SECOND wave is worth growing the bench for.
    assert THWACKEY in [b["id"] for b in rival["bench"]]
    assert [b["hp"] for b in rival["bench"] if b["id"] == THWACKEY] == [100]

    # And what the record actually did with this menu: played hand index 2.
    assert _raw()["accion_del_registro"] == [2]
    assert o["select"]["option"][2] == {"index": 2, "type": 7}
    assert me["hand"][2]["id"] == FOREST


def test_the_wave_arithmetic_of_the_board():
    """20 x 4 = 80 reaches their Active and nothing else; 20 x 5 = 100 also
    buries the 100 HP body they promote after it."""
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    assert m.attack_table[m.DO_THE_WAVE_ATTACK_ID].name == "Do the Wave"
    assert (m.attack_table[m.DO_THE_WAVE_ATTACK_ID].damage or 0) == 0
    assert 20 * 4 == cur["players"][1 - yo]["active"][0]["hp"] == 80
    assert 20 * 5 == 100
    survivors_of_80 = [b["hp"] for b in cur["players"][1 - yo]["bench"]
                       if b["hp"] > 80]
    assert sorted(survivors_of_80) == [100, 210]
    survivors_of_100 = [b["hp"] for b in cur["players"][1 - yo]["bench"]
                        if b["hp"] > 100]
    assert survivors_of_100 == [210]


# ---------------------------------------------------------------------------
# 2. The counting: `_festival_wave_bench`
# ---------------------------------------------------------------------------

def _my_state(obs_dict):
    cur = to_observation_class(obs_dict).current
    return cur.players[cur.yourIndex]


def test_the_wave_counts_the_body_still_in_hand():
    state = _my_state(_obs())
    assert m._festival_wave_bench(state, Counter()) == 4     # the board as it stands
    assert m._festival_wave_bench(state, Counter({TAPU: 1})) == 5   # + the seat
    # An ex buys the same twenty and leaves a second prize on our bench: not in.
    assert m._festival_wave_bench(state, Counter({OGERPON: 1, FEZ: 2})) == 4
    # ...and it never invents seats that do not exist.
    assert m._festival_wave_bench(state, Counter({TAPU: 4})) == 5
    # With no hand at all it degrades to what every caller read before it existed.
    assert m._festival_wave_bench(state, None) == 4


def test_a_full_bench_counts_no_body_in_hand():
    state = _my_state(_obs(full_bench=True))
    assert m._festival_wave_bench(state, Counter({TAPU: 1})) == 5


# ---------------------------------------------------------------------------
# 3. The three consequences, on the record's own menu
# ---------------------------------------------------------------------------

def test_our_stadium_does_not_replace_the_one_that_is_paying_us():
    """The step the game was lost on: the Forest is not played today."""
    o = _obs()
    choice = _decide(o)
    assert _played_card_id(o, choice) != FOREST


def test_the_body_that_grows_the_wave_goes_down_first():
    """...and what it plays instead is the fifth body: +20 on each wave."""
    o = _obs()
    choice = _decide(o)
    assert _played_card_id(o, choice) == TAPU


def test_the_plan_is_still_the_benched_dipplin():
    """The pivot that was already right stays right -- and now nothing in the
    turn is allowed to dismantle it."""
    o = _obs()
    _decide(o)
    plan = m.AGENT_STATE.plan
    assert plan.attacker == 3               # my_cards[3] = bench[2] = the Dipplin
    assert plan.target == 0
    assert plan.remain_hp <= 0              # the wave knocks their Active out


def test_the_forest_is_played_again_once_the_stadium_is_not_theirs():
    """The veto is dated to the stadium, not a standing ban on our own: with
    Festival Grounds gone the Forest is a perfectly good play again.

    Asserted on the SCORE and not on the chosen action, because which play a
    turn makes first is the ordering tiers' business and this rule has no
    opinion about it -- what it claims is only that the card stops being
    forbidden.
    """
    assert _forest_score(_obs()) == m.SCORE_VETO
    assert _forest_score(_obs(without_stadium=True)) > 0


def test_without_the_fifth_body_the_turn_is_unchanged_except_for_the_stadium():
    """The bench envelope needs a body AND a seat: with Tapu Bulu out of hand the
    only thing left of the fix is the stadium the wave is cashing under."""
    o = _obs(without_tapu=True)
    choice = _decide(o)
    assert _played_card_id(o, choice) != FOREST


# ---------------------------------------------------------------------------
# 4. The evolution that would have thrown the attacker away
# ---------------------------------------------------------------------------

def test_the_body_that_is_the_attack_is_not_evolved():
    """Step 63 of the record, with the stadium the record had already discarded
    put back: Hydrapple ex does not go on top of the Dipplin that is attacking."""
    o = _obs("observacion_paso_63", festival_grounds=True)
    choice = _decide(o)
    opt = o["select"]["option"][choice[0]]
    assert opt["type"] != m.OptionType.EVOLVE


def test_and_it_is_evolved_again_the_moment_the_stadium_is_gone():
    """The record's own board -- Festival Grounds already discarded -- where
    Hydrapple ex is simply the upgrade it normally is. The veto is one turn
    long, not a rule about Dipplin."""
    o = _obs("observacion_paso_63")
    assert _raw()["accion_del_registro_paso_63"] == [2]
    choice = _decide(o)
    opt = o["select"]["option"][choice[0]]
    assert opt["type"] == m.OptionType.EVOLVE
    assert choice == [2]
