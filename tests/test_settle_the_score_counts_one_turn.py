"""Okidogi's Settle the Score: the prizes of ONE turn, not of the game.

    Settle the Score  {F}{F}{C}  80
        This attack does 60 more damage for each Prize card your opponent took
        during their last turn.

The attacker is the opponent, so "your opponent" is US: the attack is priced in
OUR tempo. Two prizes cashed on our turn hand it 80 + 120 = **200**, which kills
an Ogerpon ex the projector was calling a 80-damage inconvenience.

WHY IT NEEDED A NEW COUNTER. `prizes_we_took` already existed for Pecharunt ex's
Irritated Outburst -- but that one counts the prizes of the WHOLE GAME, and the
observation carries it for free as "six minus the pile". This one counts the
prizes of ONE TURN, and a turn boundary is not in the observation. It has to be
remembered: `AGENT_STATE._prize_pile_at_turn_start`, frozen on the same line
that already detects the turn change, and the counter is that minus the pile now.

WHAT IT DELIBERATELY DOES NOT READ. The prize that the attack we are currently
SCORING would cash is not in the counter. In our deck a knockout ends the turn,
so most of the time this reads zero and the attack stays at its printed 80 --
a FLOOR, which is the direction this table is allowed to be wrong in (see the
exclusions at the top of `ptcg/cards/op_scaling.py`: projecting a maximum makes
every turn look lost). Reading our own pending knockout into their damage is a
projection over an action that has not happened; it belongs to the rule that
decides whether to cash the prize, and it is measured there.

NOT the Okidogi of `test_adrena_power_reads_the_darkness_energy`. That one is
**116**, a Fighting basic whose ability adds a flat +100. This is **890**, a
Fighting basic of 140 HP whose attack costs {F}{F}{C}. Same name, different card, different job -- and the
first thing that was checked, because a shared card would have meant the two
bonuses stack.
"""

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m  # noqa: E402
import ptcg.cards.op_scaling as sc  # noqa: E402
from ptcg.calc.opponent import build_op_scale  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402
from state_builder import G, Scenario, pk  # noqa: E402

SETTLE_THE_SCORE = 1284
OKIDOGI_SETTLE = 890
FIGHTING = 6
COLORLESS = 0

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
CHIKORITA = m.Chikorita


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)


def _scale(**counters):
    """An EMPTY_SCALE with only the counters under test moved."""
    return dataclasses.replace(sc.EMPTY_SCALE, **counters)


# ---------------------------------------------------------------------------
# The formula
# ---------------------------------------------------------------------------

def test_the_damage_is_eighty_plus_sixty_for_each_prize_of_the_turn():
    attacker = pk(OKIDOGI_SETTLE, energies=[FIGHTING, FIGHTING, COLORLESS])
    for prizes, expected in ((0, 80), (1, 140), (2, 200), (3, 260)):
        got = sc.op_scaled_damage(
            SETTLE_THE_SCORE, 80, attacker,
            _scale(prizes_we_took_this_turn=prizes))
        assert got == expected, (
            f"con {prizes} premios tomados este turno el ataque hace {expected}, "
            f"no {got}")


def test_without_a_reading_it_stays_at_its_printed_value():
    """The floor. An observation outside our turn, or a caller that never built a
    scale, must leave the attack exactly where the card prints it."""
    attacker = pk(OKIDOGI_SETTLE, energies=[FIGHTING, FIGHTING, COLORLESS])
    assert sc.op_scaled_damage(SETTLE_THE_SCORE, 80, attacker,
                               sc.EMPTY_SCALE) == 80


def test_it_does_not_read_the_prizes_of_the_whole_game():
    """The trap this counter exists to avoid: Pecharunt's counter is the game's
    total and would report 4 on the turn we take our fifth."""
    attacker = pk(OKIDOGI_SETTLE, energies=[FIGHTING, FIGHTING, COLORLESS])
    game_long = _scale(prizes_we_took=4, prizes_we_took_this_turn=1)
    assert sc.op_scaled_damage(SETTLE_THE_SCORE, 80, attacker, game_long) == 140
    # ... and the neighbouring entry keeps reading the total, undisturbed.
    assert sc.op_scaled_damage(184, 0, attacker, game_long) == 240


# ---------------------------------------------------------------------------
# The counter: where a turn starts
# ---------------------------------------------------------------------------

def _board(prizes, turn=8, step=41):
    """Our board with a fixed shape; only the prize pile moves."""
    return (Scenario(turn=turn, step=step, own_prizes=prizes)
            .my_active(pk(OGERPON, energies=[G, G], fisicas=2))
            .my_bench(pk(TAPU), pk(CHIKORITA))
            .op_active(pk(OKIDOGI_SETTLE,
                          energies=[FIGHTING, FIGHTING, COLORLESS]))
            .op_zones(hand=4, deck=30, prizes=3)
            .my_hand(m.Basic_Grass_Energy)
            .deck(m.Basic_Grass_Energy, m.Basic_Grass_Energy)
            .rest_to_discard()
            .menu_hand()
            .build())


def _counter_after(obs):
    m.agent(obs)
    return m.AGENT_STATE.op_scale.prizes_we_took_this_turn


def test_the_counter_is_zero_on_the_first_decision_of_a_turn():
    assert _counter_after(_board(prizes=4)) == 0


def test_a_prize_cashed_inside_the_turn_is_counted():
    """The real sequence: the first menu of the turn sees the pile at four, a
    later menu of the SAME turn sees three. One prize, this turn."""
    assert _counter_after(_board(prizes=4)) == 0
    assert _counter_after(_board(prizes=3, step=42)) == 1
    assert _counter_after(_board(prizes=2, step=43)) == 2


def test_the_counter_resets_when_the_turn_changes():
    """Two prizes taken last turn are worth nothing to an attack that asks about
    THIS one -- and the pile does not go back up, so only the boundary can say so."""
    assert _counter_after(_board(prizes=4)) == 0
    assert _counter_after(_board(prizes=2, step=43)) == 2
    assert _counter_after(_board(prizes=2, turn=9, step=44)) == 0


def test_the_game_long_counter_still_reads_the_whole_game():
    """The two counters live side by side and must not be confused: with the pile
    at two we have taken four prizes in the game and two in this turn."""
    _counter_after(_board(prizes=4))
    _counter_after(_board(prizes=2, step=43))
    assert m.AGENT_STATE.op_scale.prizes_we_took == 4
    assert m.AGENT_STATE.op_scale.prizes_we_took_this_turn == 2


# ---------------------------------------------------------------------------
# The projector: the number the defensive rules actually see
# ---------------------------------------------------------------------------

def test_the_projector_reads_the_scaled_number_off_the_board():
    """`_op_active_attack_damage_to` is what every defensive rule hangs off. With
    two prizes cashed this turn the Okidogi hits our Ogerpon ex for 200 under the
    `scaled` reading -- and for the printed 80 without it.

    That split is not this entry's doing: `scaled` is OPT-IN for the whole table
    (the docstring of the projector says why -- the thresholds downstream were
    fitted to the blind number, and turning it on everywhere measured negative
    three times out of three). Today the only consumer is the turn plan. So this
    entry, like the other seventeen, is read by `op_prizes_next` and by nothing
    else, and that is asserted here rather than assumed."""
    m.agent(_board(prizes=4))
    obs = _board(prizes=2, step=43)
    m.agent(obs)
    st = m.to_observation_class(obs).current
    mine, theirs = st.players[st.yourIndex], st.players[1 - st.yourIndex]
    assert m._op_active_attack_damage_to(
        theirs.active[0], mine.active[0], scaled=True) == 200
    assert m._op_active_attack_damage_to(
        theirs.active[0], mine.active[0]) == 80


def test_the_snapshot_is_built_with_the_boundary_the_agent_remembers():
    """The counter cannot be recomputed from the observation alone: same board,
    same piles, and the answer depends on where the turn started."""
    obs = _board(prizes=3)
    st = m.to_observation_class(obs).current
    mine, theirs = st.players[st.yourIndex], st.players[1 - st.yourIndex]
    assert build_op_scale(mine, theirs).prizes_we_took_this_turn == 0
    assert build_op_scale(
        mine, theirs, prize_pile_at_turn_start=5).prizes_we_took_this_turn == 2
