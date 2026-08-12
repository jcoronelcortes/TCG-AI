"""Festival Lead grants TWO waves per turn, not a standing threat.

Scenario (episode 92355371, turn 3, step 62, LOST vs *Festival Lead*):

    US (6 prizes)                         OPPONENT (5 prizes)
    active  -- (their Dipplin has just    active  Dipplin 80 HP, 1 Grass,
            knocked out our Tapu Bulu)            **Deluxe Bomb**
    bench   Chikorita        70 HP        bench   5 bodies (Volbeat 70,
            Meowth ex       170 HP                Thwackey 100, Thwackey 100,
            Teal Mask Ogerpon ex 210, 1 en        Applin 40, Applin 40)
            **Applin**       40 HP        stadium **Festival Grounds** (theirs)
            Teal Mask Ogerpon ex 210, 1 en
    hand    Meowth ex, Xerosic, **Dipplin x2**, Applin, **1 Grass**, Ultra Ball

The knockout did NOT come from their first wave. Their Dipplin threw *Do the
Wave* TWICE at the same Tapu Bulu -- 140 -> 40 -> discard, the two ATTACK logs
of serial 87 are in the batch that carries this very promotion menu -- and only
then did we choose a replacement. Under *Festival Lead* ("this Pokemon may use
an attack it has **twice**") two is the CEILING OF THE TURN: nothing was owed to
us.

`op_double_attack_pending` fired anyway, because it read the board (stadium +
Dipplin in the active spot + a forced promotion) and the board cannot tell the
two cases apart. Only the log dates the waves. It cost the turn twice:

  1. it struck off every candidate that does not survive a 100 that was never
     coming -- the Applin of 40 and the Chikorita of 70;
  2. and, above all, it switched off `_promo_evo_koer`, the branch written for
     exactly this shape: bring up the pre-evolution that the evolution in hand
     turns into the finisher. That Applin evolves into Dipplin, the single Grass
     pays *Do the Wave* ({G}) and 20 x 4 benched = **80** buries their 80 HP
     Dipplin -- a one-prize attacker cashing a prize while BOTH Teal Mask
     Ogerpon ex stay on the bench, where their *Tera* prevents all damage.

Instead an Ogerpon ex left the bench to stand in front, and the record shows the
price: it came back to 90/210 (the Deluxe Bomb) as a 2-prize body in range of a
Do the Wave engine.

THE FIX is a SECOND read that only ever LOWERS the flag:
`AGENT_STATE._op_attack_waves_this_turn` counts the ATTACK logs of the turn by
serial, and `op_double_attack_pending` requires the count to be below
`FESTIVAL_LEAD_MAX_WAVES`. With no evidence in the log the count is 0 and the
guard behaves exactly as it did before -- which is the other half this file
measures: with ONE wave in the log (their first knocked us out, the second is
still coming) the old behaviour has to survive untouched, and it is the reason
`tests/test_festival_lead_double_attack_promotion.py` still passes.

WHAT THIS TEST DOES NOT CLAIM. The *second* wave of our own Dipplin is not free
here: their active carries a **Deluxe Bomb** (12 damage counters on the
attacker), so an 80 HP Dipplin does not survive its own first *Do the Wave* and
never gets to throw the second. The promotion is right for the reason written
above -- a one-prize body cashes the prize and the untouchable exes stay
untouchable -- not because two prizes are on the table. Deluxe Bomb is not
modelled anywhere yet.
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "festival_lead_t3_both_waves_already_thrown_step62.json")

APPLIN = m.Applin
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
MEOWTH = m.Meowth_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
DELUXE_BOMB = 1167
THEIR_DIPPLIN_SERIAL = 87
DOS_OLEADAS = 2


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
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    m._op_bench_count = 0
    m._festival_grounds_in_play = False
    m._op_attack_waves_this_turn = {}
    yield
    m._init_cards_tracking()


def _obs(waves=2, stadium=True):
    """The recorded board. `waves` says how many of their ATTACK logs survive:
    2 = as it happened (the turn is spent), 1 = the first one knocked us out and
    the second is still owed to us."""
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    if not stadium:
        o["current"]["stadium"] = []
    if waves < 2:
        vistos = 0
        podados = []
        for log in o["logs"]:
            if (log.get("type") == 15
                    and log.get("serial") == THEIR_DIPPLIN_SERIAL):
                vistos += 1
                if vistos > waves:
                    continue
            podados.append(log)
        o["logs"] = podados
    return o


def _bench(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]["bench"]


def _promovido(obs, choice):
    return _bench(obs)[obs["select"]["option"][choice[0]]["index"]]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_promotion_after_both_waves():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio, suyo = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    assert not mio["active"]                       # they knocked out our active
    assert o["select"]["context"] == 4             # promotion menu

    # The stadium is on the table and it is THEIRS -- it is SHARED all the same.
    assert [c["id"] for c in o["current"]["stadium"]] == [m.Festival_Grounds]
    assert o["current"]["stadium"][0]["playerIndex"] == 1 - yo
    assert suyo["active"][0]["id"] == DIPPLIN
    assert DIPPLIN in m.FESTIVAL_LEAD_IDS

    # THE FACT THE BOARD DOES NOT CARRY: both waves are already thrown, and only
    # the log says so.
    oleadas = [lg for lg in o["logs"]
               if lg.get("type") == 15
               and lg.get("serial") == THEIR_DIPPLIN_SERIAL]
    assert len(oleadas) == DOS_OLEADAS
    assert {lg["attackId"] for lg in oleadas} == {m.DO_THE_WAVE_ATTACK_ID}

    # The bench holds the Applin, and the hand the Dipplin plus the single Grass
    # that pays for Do the Wave.
    assert [(b["id"], b["hp"]) for b in mio["bench"]] == [
        (CHIKORITA, 70), (MEOWTH, 170), (OGERPON, 210),
        (APPLIN, 40), (OGERPON, 210)]
    mano = [c["id"] for c in mio["hand"]]
    assert mano.count(DIPPLIN) == 2
    assert mano.count(m.Basic_Grass_Energy) == 1
    assert m.card_table[DIPPLIN].evolvesFrom == m.card_table[APPLIN].name
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ.get(DIPPLIN) == 1

    # And what makes the second wave of OUR Dipplin anything but free.
    assert [t["id"] for t in suyo["active"][0]["tools"]] == [DELUXE_BOMB]


def test_the_ceiling_is_two_and_it_is_written_down():
    assert m.FESTIVAL_LEAD_MAX_WAVES == DOS_OLEADAS


# ---------------------------------------------------------------------------
# 2. The read: the log dates the waves
# ---------------------------------------------------------------------------

def test_it_counts_the_waves_of_the_turn_by_serial():
    obs = _obs()
    m.agent(obs)
    assert m._op_attack_waves_this_turn == {THEIR_DIPPLIN_SERIAL: 2}


def test_with_a_single_wave_in_the_log_the_count_is_one():
    obs = _obs(waves=1)
    m.agent(obs)
    assert m._op_attack_waves_this_turn == {THEIR_DIPPLIN_SERIAL: 1}


def test_the_counter_is_per_turn():
    """It is reset on the turn change, like every other log accumulator: two is
    the ceiling of ONE turn, and next turn the pair starts over."""
    obs = _obs()
    m.agent(obs)
    assert m._op_attack_waves_this_turn
    siguiente = _obs()
    siguiente["current"]["turn"] += 2
    siguiente["logs"] = []
    m.agent(siguiente)
    assert m._op_attack_waves_this_turn == {}


# ---------------------------------------------------------------------------
# 3. The decision, and the half that must NOT move
# ---------------------------------------------------------------------------

def test_it_brings_up_the_applin_the_dipplin_in_hand_finishes_with():
    obs = _obs()
    elegido = _promovido(obs, m.agent(obs))
    assert elegido["id"] == APPLIN, (
        "with both waves spent the promotion is the pre-evolution that the "
        "Dipplin in hand turns into the knockout, not a Tera ex leaving the "
        "bench")
    assert elegido["serial"] == 14


def test_the_projection_that_wins_it_is_do_the_wave_over_their_dipplin():
    """20 x 4 benched after the promotion = 80 against an 80 HP Dipplin: the
    knockout is found even with the conservative count (it does not add the body
    we can still play from hand, which would make it 100)."""
    obs = _obs()
    m.agent(obs)
    suyo = m.to_observation_class(obs).current.players[
        1 - obs["current"]["yourIndex"]]
    assert suyo.active[0].hp == 80
    assert m._attacker_base_damage(DIPPLIN, suyo.active[0], 1,
                                   grass_scale=0, teal_self_energy=1,
                                   bench_count=4) == 80


def test_with_the_second_wave_still_owed_nothing_moves():
    """The other half. One wave in the log = their first knocked us out and the
    second lands as soon as we promote: the guard has to fire exactly as before,
    the 40 HP Applin is struck off and a body that survives the 100 comes up."""
    obs = _obs(waves=1)
    elegido = _promovido(obs, m.agent(obs))
    assert elegido["id"] != APPLIN
    assert elegido["hp"] > 100


def test_without_the_stadium_the_guard_never_had_anything_to_say():
    """No Festival Grounds, no Festival Lead and no waves to count: the promotion
    goes back to the ordinary rules and the evolution branch is free again."""
    obs = _obs(stadium=False)
    elegido = _promovido(obs, m.agent(obs))
    assert elegido["id"] == APPLIN
