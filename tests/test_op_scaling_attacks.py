"""The opposing attacks whose damage is not the number printed on the card.

`ptcg/cards/op_scaling.py` fixes a blind spot, not an estimate: for thirteen of
the fifteen scaling attacks that appear in the 406 opposing decks in the repo,
the projector used to return the placeholder printed on the card. The anchor of
this file is the one case where the engine wrote down the right answer for us:

    registro_013 (episode 89616806, the competition's validation game), turn 12.
    Their Hydrapple ex used Syrup Storm with EIGHT {G} on their board and the log
    records `value: -270`. The projector said 30 -- the printed damage.

So the first test is not a unit test of a lambda, it is a comparison against the
simulator. The rest cover the two things that are silent when wrong: the
PERSPECTIVE ("your" is theirs, "your opponent's" is ours) and the attacks that
are left out on purpose.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from ptcg.calc.opponent import build_op_scale
from ptcg.cards import op_scaling as sc

_FIX = ROOT / "tests" / "fixtures" / "mirror_match_point_gust_wins_step126.json"

SYRUP_STORM = 195
MYRIAD = 120
DO_THE_WAVE = 115
RESENTFUL_REFRAIN = 1240
TENACIOUS_TAIL = 425
RAGING_CURSE = 540
RAPID_FIRE_COMBO = 1092
BELLOWING_THUNDER = 72
ERASURE_BALL = 608


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)["observation"]


# ---------------------------------------------------------------------------
# The anchor: the number the engine actually dealt
# ---------------------------------------------------------------------------

def test_syrup_storm_matches_the_damage_the_engine_dealt():
    obs = _fixture()
    m.agent(obs)                      # builds AGENT_STATE.op_scale for this board
    st = m.to_observation_class(obs).current
    mine, theirs = st.players[1], st.players[0]

    # The board the log describes: 8 {G} spread over their six Pokemon.
    assert m.AGENT_STATE.op_scale.op_grass_on_field == 8

    ciega = m._op_active_attack_damage_to(
        theirs.active[0], mine.active[0], theirs.handCount)
    escalada = m._op_active_attack_damage_to(
        theirs.active[0], mine.active[0], theirs.handCount, scaled=True)

    assert ciega == 30, "el valor IMPRESO de Syrup Storm, que es un marcador"
    assert escalada == 270, (
        "30 + 30 x 8 = 270, exactamente el `value: -270` que registro el motor "
        "en el turno 12 de registro_013")


def test_the_plan_sees_the_lethal_reply_only_with_the_scale():
    """What the blind number cost: our Ogerpon ex (210 HP) eats 270 and they are
    at one prize. The defensive half of the plan could not see it."""
    obs = _fixture()
    m.agent(obs)
    plan = m.AGENT_STATE.turn_plan
    assert plan.op_prizes_next == 2 and plan.op_wins_next, (
        "si no cerramos el turno, su respuesta cierra la partida")


# ---------------------------------------------------------------------------
# The perspective: "your" is theirs, "your opponent's" is ours
# ---------------------------------------------------------------------------

def test_the_snapshot_reads_each_side_from_the_right_seat():
    obs = _fixture()
    m.agent(obs)
    st = m.to_observation_class(obs).current
    scale = build_op_scale(st.players[1], st.players[0])

    # THEIR side: five on the bench, four Basics in play, 8 Grass.
    assert scale.op_bench == 5
    assert scale.op_grass_on_field == 8
    # OUR side: two on the bench, six cards in hand, four energies on the active,
    # one Pokemon ex in play (the active Ogerpon; Meganium and Tapu Bulu are not).
    assert scale.my_bench == 2
    assert scale.my_hand == 6
    assert scale.my_active_energy == 4
    assert scale.my_ex_in_play == 1
    # Neither side plays a named-trainer subset in the mirror.
    assert scale.op_rocket_in_play == 0
    assert scale.op_cynthia_bench_counters == 0


def test_the_attacks_that_count_our_side_grow_with_our_board():
    """Resentful Refrain and Tenacious Tail scale with what WE build. Getting the
    seat backwards here reads zero and is silent."""
    obs = _fixture()
    m.agent(obs)
    st = m.to_observation_class(obs).current
    scale = build_op_scale(st.players[1], st.players[0])
    attacker = st.players[0].active[0]

    assert sc.op_scaled_damage(RESENTFUL_REFRAIN, 0, attacker, scale) == 50 * 6
    assert sc.op_scaled_damage(TENACIOUS_TAIL, 0, attacker, scale) == 60 * 1
    # Myriad counts BOTH actives: their 2 energies plus our 4.
    assert sc.op_scaled_damage(MYRIAD, 30, attacker, scale) == 30 + 30 * 6


# ---------------------------------------------------------------------------
# The guards
# ---------------------------------------------------------------------------

def test_a_scaling_entry_never_lowers_the_printed_damage():
    """An entry raises a floor. With an empty board Myriad must still be its
    printed 30, not 0 -- a table that could subtract would be a nerf hidden
    inside a fix."""
    obs = _fixture()
    attacker = m.to_observation_class(obs).current.players[0].active[0]
    assert sc.op_scaled_damage(MYRIAD, 30, attacker, sc.EMPTY_SCALE) >= 30
    assert sc.op_scaled_damage(SYRUP_STORM, 30, attacker, sc.EMPTY_SCALE) >= 30


def test_an_attack_outside_the_table_keeps_its_printed_damage():
    obs = _fixture()
    attacker = m.to_observation_class(obs).current.players[0].active[0]
    assert sc.op_scaled_damage(999999, 90, attacker, sc.EMPTY_SCALE) == 90


def test_the_scale_is_opt_in():
    """The default has to stay the old reading: forty-two call sites carry
    thresholds that were fitted to it. See the docstring of
    `_op_active_attack_damage_to` for the measurement that decided this."""
    obs = _fixture()
    m.agent(obs)
    st = m.to_observation_class(obs).current
    a, d = st.players[0].active[0], st.players[1].active[0]
    assert m._op_active_attack_damage_to(a, d) == 30
    assert m._op_active_attack_damage_to(a, d, scaled=True) == 270


def test_raging_curse_is_not_doubled_by_weakness():
    """Its own text says the damage is not affected by Weakness; the projector
    doubles at the end and would inflate it."""
    assert RAGING_CURSE in sc.OP_SCALING_IGNORES_WEAKNESS


def test_the_attacks_left_out_are_left_out_on_purpose():
    """Coin flips and the opponent's own discard choices are NOT in the table.

    They are not oversights: their scale is not on the board. Rapid-Fire Combo's
    +50 was already tried as an estimate and reverted by policy, and projecting
    the maximum of an Erasure Ball would make every turn look lost.
    """
    for aid in (RAPID_FIRE_COMBO, BELLOWING_THUNDER, ERASURE_BALL):
        assert aid not in sc.OP_SCALING_DAMAGE


def test_no_opposing_attack_scales_without_being_read():
    """The census is a gate, not a one-off.

    `utils/op_scaling_census.py` scans every opposing deck in the repo and splits
    the scaling attacks into modelled / knowingly excluded / unread. A new deck
    that brings a fourth bucket entry is exactly the failure this whole table
    exists to prevent, and it is invisible in a game: the agent does not crash,
    it walks into the hit. If this fails, run the tool, read the attack text and
    decide -- can the number be READ off the board, or would we be guessing?
    """
    sys.path.insert(0, str(ROOT / "utils"))
    import op_scaling_census as census

    rows, n_decks = census.census()
    missing = [(r[2], r[4], r[3]) for r in rows if r[0] == "SIN MODELAR"]
    assert n_decks > 100, "el censo no encontro los mazos rivales"
    assert not missing, (
        f"ataques rivales que escalan y nadie lee: {missing}. "
        "Ver utils/op_scaling_census.py")


def test_the_census_still_matches_the_card_database():
    """Every id in the table has to exist and to be a scaling attack.

    A table of magic numbers rots silently when the card pool moves; this reads
    the text back out of `attack_table` and checks it really scales.
    """
    for aid in sc.OP_SCALING_DAMAGE:
        atk = m.attack_table.get(aid)
        assert atk is not None, f"el ataque {aid} ya no existe en el entorno"
        assert "for each" in (atk.text or ""), (
            f"{aid} ({atk.name}) ya no escala: sobra de la tabla")
