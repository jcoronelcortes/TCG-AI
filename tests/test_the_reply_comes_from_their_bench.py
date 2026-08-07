"""When we take the knockout, the reply comes off their BENCH -- and it was invisible.

WHAT WAS WRONG. `build_turn_plan` switched its whole defensive half off on every
board where our own attack finishes their active:

    if _we_knock_out_their_active(...):
        op_prizes_next, op_kos_our_active = 0, False

The reason is sound as far as it goes -- the body that would reply is on its way
to the discard -- and it leaves out the rest of the rule: a knockout does not end
their turn, it forces a PROMOTION. Unlike a bench swap or a gust, which need a
hand nobody can see, the bench they promote from is entirely in the observation.
So on exactly the boards where we cash a prize, the plan reported that nobody
replies, and their Ogerpon ex with four energies sitting one slot away was not
being read at all.

HOW IT WAS FOUND. Not by losing a game: by sweeping one
(`tests/test_grid_attack_or_retreat.py`). All 288 cells of that grid decide
identically at every value of their prize pile -- including their match point --
and the flag that should have separated them is zero on all of them.

WHAT SHIPPED. `_reply_after_promotion`, and two fields the plan publishes:
`op_prizes_after_ko` and `op_wins_after_ko`. They are DATA. Nothing that existed
before reads them, `mode` does not change, and the golden corpus reports zero
flips -- deliberately, because the defensive machinery of this agent has been
measured negative three separate times when it was made to fire more often, and a
projection that is newly correct is not a licence to repeat that.

WHY NO RULE WAS BUILT ON IT TONIGHT, with the number that decided it.
`utils/promoted_reply_census.py` counts the nested populations over real games.
In the mirror, 2485 decisions:

    we take the knockout                      678   27.3%
    ... the promoted body replies             300   12.1%
    ... and that closes their count            72    2.9%
    ... with a retreat on the menu             48    1.9%
    ... and a surviving relay had the same KO   2    0.08%

The last line is the population of any rule: two boards in twenty-five hundred
decisions, and on one of the two the agent already retreats. That is an order of
magnitude below what the self-play gate can resolve, so a rule there could only
ever be justified by argument, never by measurement. The reading is kept because
it corrects a value that was demonstrably wrong; the rule is not written because
nothing could tell whether it helped.

The 2.9% line is worth keeping in view for a different reason: those are boards
where the knockout we take hands them the game and NOTHING saves it -- no relay,
often no retreat. That is a lost position, not a decision.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from decision_grid import label  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402
from state_builder import G, Scenario, pk  # noqa: E402

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRA = m.Hydrapple_ex
APPLIN = m.Applin
DIPPLIN = m.Dipplin
DUNSPARCE = 144


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)


def _board(op_prizes=2, their_bench=None, their_energy=4):
    """Our Ogerpon ex knocks their Ogerpon ex out (Myriad 30+30*(3+4) = 240 on
    210 HP). What replies is whatever they promote."""
    bench = their_bench if their_bench is not None else [
        pk(OGERPON, energies=[G, G, G, G], fisicas=4), pk(DUNSPARCE)]
    scenario = (Scenario(turn=12, step=81, own_prizes=3)
                .my_active(pk(OGERPON, energies=[G, G, G], fisicas=3))
                .my_bench(pk(HYDRA, energies=[G, G, G], fisicas=3,
                             pre_evo=[APPLIN]))
                .op_active(pk(OGERPON, energies=[G] * their_energy,
                              fisicas=their_energy)))
    if bench:
        scenario = scenario.op_bench(*bench)
    return (scenario
            .op_zones(hand=5, deck=25, prizes=op_prizes)
            .deck(m.Basic_Grass_Energy, m.Basic_Grass_Energy)
            .rest_to_discard()
            .menu_hand(with_retreat=True, with_attack=True)
            .build())


def _plan(obs):
    m.agent(obs)
    return m.AGENT_STATE.turn_plan


# ---------------------------------------------------------------------------
# The reading
# ---------------------------------------------------------------------------

def test_the_active_reply_is_still_zero_when_we_knock_it_out():
    """The half that was already there and is still right: the body in front is
    not there tomorrow."""
    plan = _plan(_board())
    assert plan.op_prizes_next == 0 and plan.op_wins_next is False


def test_the_promoted_body_takes_the_prizes_our_active_is_worth():
    """Their benched Ogerpon ex with four energies hits for 30+30*(4+3) = 240
    against our 210 HP ex: two prizes, off a plan that used to say zero."""
    plan = _plan(_board(op_prizes=4))
    assert plan.op_prizes_after_ko == 2


def test_it_closes_their_count_only_when_the_pile_is_short_enough():
    """Two prizes are the game at two, and are not at three."""
    assert _plan(_board(op_prizes=3)).op_wins_after_ko is False
    assert _plan(_board(op_prizes=2)).op_wins_after_ko is True
    assert _plan(_board(op_prizes=1)).op_wins_after_ko is True


def test_a_bench_that_cannot_answer_reads_zero():
    """A bare Dunsparce and a bare Ogerpon reply with nothing: the projection has
    to stay quiet, or every knockout would look like a trap."""
    plan = _plan(_board(op_prizes=1, their_bench=[pk(DUNSPARCE), pk(OGERPON)]))
    assert plan.op_prizes_after_ko == 0 and plan.op_wins_after_ko is False


def test_an_empty_bench_is_not_a_reply_but_a_win():
    """Nothing to promote means the knockout wins by bench-out, and that route
    belongs to the offensive half. The defensive one says nothing."""
    plan = _plan(_board(op_prizes=1, their_bench=[]))
    assert plan.op_prizes_after_ko == 0 and plan.op_wins_after_ko is False


def test_their_bench_is_one_body_smaller_once_one_of_them_stands_up():
    """Do the Wave counts THEIR bench, and after the promotion that bench has
    lost the body doing the counting.

    Three bodies behind their active, one of them a Dipplin: promoted, Do the
    Wave counts the TWO that stay behind, 20x2 = 40 -- not the 60 the snapshot
    of this turn would give. Reading it uncorrected inflates their damage by 20,
    which is the direction that makes a defensive rule fire when it should not.
    It is the same arithmetic as `_promo_bench_after` on our side of the table.
    """
    bench = [pk(DIPPLIN, energies=[G], fisicas=1, pre_evo=[APPLIN]),
             pk(DUNSPARCE), pk(DUNSPARCE)]
    obs = _board(op_prizes=1, their_bench=bench)
    m.agent(obs)
    st = m.to_observation_class(obs).current
    mine = st.players[st.yourIndex]
    theirs = st.players[1 - st.yourIndex]
    dipplin = theirs.bench[0]
    our_active = mine.active[0]

    import dataclasses
    snapshot = m.AGENT_STATE.op_scale
    assert snapshot.op_bench == 3
    corrected = dataclasses.replace(snapshot, op_bench=2)

    assert m._op_active_attack_damage_to(
        dipplin, our_active, scaled=True, scale=snapshot) == 60
    assert m._op_active_attack_damage_to(
        dipplin, our_active, scaled=True, scale=corrected) == 40
    # Do the Wave is read whether `scaled` is on or not -- it predates the
    # table -- so the correction has to reach the branch above it too.
    assert m._op_active_attack_damage_to(
        dipplin, our_active, scale=corrected) == 40
    # ... and the plan used the corrected one: 40 does not knock out a 210 ex,
    # so the whole bench answers with nothing.
    assert m.AGENT_STATE.turn_plan.op_prizes_after_ko == 0


def test_the_default_scale_is_still_the_board_as_it_stands():
    """`scale=None` must keep meaning `AGENT_STATE.op_scale`: every existing
    caller passes nothing and asks about their next turn from this board."""
    obs = _board(op_prizes=1, their_bench=[
        pk(DIPPLIN, energies=[G], fisicas=1, pre_evo=[APPLIN]),
        pk(DUNSPARCE), pk(DUNSPARCE)])
    m.agent(obs)
    st = m.to_observation_class(obs).current
    dipplin = st.players[1 - st.yourIndex].bench[0]
    our_active = st.players[st.yourIndex].active[0]
    assert m._op_active_attack_damage_to(
        dipplin, our_active, scaled=True) == m._op_active_attack_damage_to(
            dipplin, our_active, scaled=True, scale=m.AGENT_STATE.op_scale)


# ---------------------------------------------------------------------------
# It is data: no decision moves
# ---------------------------------------------------------------------------

def test_the_decision_is_the_same_at_every_prize_count():
    """The whole point of shipping this as data. The agent takes the knockout at
    four prizes and at one, exactly as it did before the fields existed; what
    changed is that the plan can now SAY what happens next."""
    for op_prizes in (4, 3, 2, 1):
        obs = _board(op_prizes=op_prizes)
        choice = m.agent(obs)
        assert label(obs, choice) == "ATTACK", op_prizes
        reset_agent(m)


def test_do_the_wave_has_one_formula_in_two_places():
    """The branch in the projector and entry 115 of the table must agree.

    Do the Wave is handled ABOVE the `scaled` branch, because it was modelled
    before the table existed and is not opt-in -- which means entry 115 is never
    reached from `_op_active_attack_damage_to` and would drift unnoticed. Rather
    than delete a formula that documents itself, this pins the two together: any
    edit to one that the other does not follow turns this red.
    """
    import dataclasses

    import ptcg.cards.op_scaling as sc

    obs = _board(op_prizes=1, their_bench=[
        pk(DIPPLIN, energies=[G], fisicas=1, pre_evo=[APPLIN]),
        pk(DUNSPARCE), pk(DUNSPARCE)])
    m.agent(obs)
    st = m.to_observation_class(obs).current
    dipplin = st.players[1 - st.yourIndex].bench[0]
    our_active = st.players[st.yourIndex].active[0]
    for bench in range(0, 6):
        scale = dataclasses.replace(m.AGENT_STATE.op_scale, op_bench=bench)
        through_the_branch = m._op_active_attack_damage_to(
            dipplin, our_active, scale=scale)
        through_the_table = sc.op_scaled_damage(115, 0, dipplin, scale)
        assert through_the_branch == through_the_table == 20 * bench, bench
