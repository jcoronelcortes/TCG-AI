"""MATCH POINT: with one prize left, the turn is for ENDING the game.

Scenario (user, episode 89616806 -- the competition's own validation game, our
agent against itself -- registro_013 step 126, WON suboptimally):

    US (seat 1)                              RIVAL (the mirror)
    active  Teal Mask Ogerpon ex 210 (4e)    active  Hydrapple ex 330 (2e)
    bench   Meganium 160 (0e),               bench   Meganium 160 (0e),
            Tapu Bulu 140 (4e)                       Meowth ex 170 (0e),
    hand    Unfair Stamp, Boss's Orders,              Teal Mask Ogerpon ex 210 (4e),
            Chikorita, Ogerpon ex, Grass,             Tapu Bulu 140 (2e),
            Bug Catching Set                          Fezandipiti ex 210 (0e)
    prizes  1 - 1   <- MUTUAL match point

Myriad Leaf Shower does 30 + 30 for each Energy attached to BOTH actives
(see [[ogerpon-myriad-cuenta-ambos-activos]]). With our 4 energies the gust was
already lethal against two different bodies on that bench, WITHOUT charging
anything:

    Boss's -> their Ogerpon ex (4e): 30 + 30 x (4+4) = 270 >= 210  -> 2 prizes
    Boss's -> their Tapu Bulu (2e):  30 + 30 x (4+2) = 210 >= 140  -> 1 prize

One prize was missing. Either of them ended the game on the SECOND action of the
turn. The agent instead played Bug Catching Set, benched two Ogerpon, used two
Teal Dances, an Ultra Ball, an Unfair Stamp -- which handed the opponent a fresh
hand while they were also one prize away -- and a Fezandipiti, and only won on
action nineteen, by stacking eight energies onto the active to reach exactly the
330 of the opposing Hydrapple ex. One energy short and the reply wins.

THE BUG: AN ORDERING VETO THAT NEVER ASKED WHAT THE TURN WAS FOR
----------------------------------------------------------------
The winning gust WAS detected: `_win_via_boss_gust` was True and the target
scorer had `wins_now` ready to add its 100000. What killed it was the rule
ABOVE it in `_RULES_BOSS_PLAY`:

    yields_to_unfair_stamp -> SCORE_VETO   (boss->play = -1)

`_stamp_pendiente` was true (we had been knocked out, the Stamp was in hand,
their hand was large), and "the Stamp goes first" is a good rule -- for a turn
about resources. This turn was about ending the game, and no rule in the file
was in a position to tell the difference: every "does this win?" flag lived
alone, consulted by whichever rule remembered it.

THE FIX: `ptcg/turn/game_plan.py`
---------------------------------
A TURN PLAN built once per observation, before the first decision, that puts the
prize count in front of the turn and answers three questions: is there a route
that CLOSES the game (and which), how many prizes do we take today, how many do
they take on the reply. Two consumers here:

  * `_stamp_pendiente` returns False when the plan has a lethal route, so EVERY
    ordering veto that reads it (Boss's, Lillie's, Lana's, Dawn, Xerosic, the
    Meowth chain, Flip the Script) steps back at once instead of one by one.
  * the gust that IS the finisher gets `_TIER_WIN_ATTACK` in the play order, the
    same tier as the winning attack, because gust and attack are two halves of
    one play. Without it Boss's scored 20000 and still lost by ORDER to a Bug
    Catching Set (tier BUG_SET) and a Teal Dance (tier ENERGY).

The second consumer is deliberately narrow (`gust_closes_it_now`): it only fires
when the target dies to the energy ALREADY on the attacker. When the KO is one
charge away the charge goes first -- that is the Myriad combo of registro_012
step 227, covered in tests/test_state_builder.py, which this rule must not break.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from ptcg.turn import game_plan as gp

BOSS = m.Boss_Orders
STAMP = m.Unfair_Stamp
BCS = m.Bug_Catching_Set
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu

_FIX = ROOT / "tests" / "fixtures" / "mirror_match_point_gust_wins_step126.json"


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


def _idx_play(obs, card_id):
    yo = obs["current"]["yourIndex"]
    hand = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == card_id:
            return i
    return -1


# ---------------------------------------------------------------------------
# The board: that the mate really existed, measured with the engine's evaluators
# ---------------------------------------------------------------------------

def test_the_mate_existed_two_bench_bodies_died_to_the_current_energy():
    obs = m.to_observation_class(_fixture())
    st = obs.current
    yo, opponent = st.players[1], st.players[0]

    assert len(yo.prize) == 1, "nos faltaba UN premio"
    assert len(opponent.prize) == 1, "al rival tambien: match point mutuo"

    ogerpon = yo.active[0]
    assert ogerpon.id == OGERPON and len(ogerpon.energies) == 4
    assert not st.supporterPlayed and any(
        c.id == BOSS for c in yo.hand), "el Boss's estaba en la mano"

    total_grass = sum(len(p.energies) for p in (yo.active + yo.bench)
                      if p is not None)
    letales = []
    for cuerpo in opponent.bench:
        if cuerpo is None:
            continue
        base = m._attacker_base_damage(
            ogerpon.id, cuerpo, len(ogerpon.energies),
            grass_scale=total_grass, teal_self_energy=len(ogerpon.energies),
            bench_count=len(yo.bench))
        if base >= (cuerpo.hp or 0) > 0:
            letales.append((cuerpo.id, m.prize_count_op(cuerpo)))

    # Their charged Ogerpon ex (2 prizes) and their Tapu Bulu (1): either one
    # closes a game that needs ONE prize.
    assert (OGERPON, 2) in letales and (TAPU, 1) in letales, letales

    # And the rival ACTIVE was NOT lethal: 30 + 30 x (4+2) = 210 < 330. That is
    # why the turn had to go through the bench, and why the agent's line needed
    # eight energies to work.
    opa = opponent.active[0]
    assert m._attacker_base_damage(
        ogerpon.id, opa, len(ogerpon.energies), grass_scale=total_grass,
        teal_self_energy=len(ogerpon.energies),
        bench_count=len(yo.bench)) < (opa.hp or 0)


# ---------------------------------------------------------------------------
# The plan: the turn is read as WIN_NOW through the gust, with nothing to charge
# ---------------------------------------------------------------------------

def test_the_plan_reads_the_turn_as_a_win_through_the_gust():
    m.agent(_fixture())
    plan = m.AGENT_STATE.turn_plan

    assert plan.mode == gp.MODE_WIN_NOW
    assert plan.win_route == gp.ROUTE_GUST
    assert plan.win_needs_supporter, "la ruta gasta el Supporter del turno"
    assert not plan.win_needs_charge, (
        "el objetivo muere con la energia que el atacante YA lleva")
    assert plan.gust_closes_it_now
    assert plan.prizes_today == 2, "el mejor KO de hoy vale 2 premios"


def test_the_opening_plan_of_the_turn_is_kept():
    obs = _fixture()
    m.agent(obs)
    assert m.AGENT_STATE.turn_plan_open is m.AGENT_STATE.turn_plan, (
        "la primera decision del turno fija la frase de apertura")


# ---------------------------------------------------------------------------
# The decision: Boss's Orders, not the engine
# ---------------------------------------------------------------------------

def test_it_gusts_instead_of_playing_the_engine():
    obs = _fixture()
    i_boss, i_bcs, i_stamp = (_idx_play(obs, BOSS), _idx_play(obs, BCS),
                              _idx_play(obs, STAMP))
    assert i_boss >= 0 and i_bcs >= 0 and i_stamp >= 0

    choice = m.agent(obs)

    assert choice == [i_boss], (
        f"esperaba Boss's Orders (idx {i_boss}), eligio {choice}")


def test_the_stamp_no_longer_vetoes_the_winning_boss():
    """The exact mechanism of the bug, isolated.

    `_stamp_pendiente` is the SINGLE source of every ordering veto that steps
    aside for the Unfair Stamp. On a turn with a lethal route it has to answer
    False -- otherwise Boss's dies at -1 again, and so does every other Supporter
    the winning line might need.
    """
    obs = _fixture()
    m.agent(obs)

    plan = m.AGENT_STATE.turn_plan
    assert plan.wins_this_turn

    class _Ctx:
        ko_last_turn = True
        hand_counts = {STAMP: 1}
        op_hand_count = 11
        my_hand_len = 6
        turn_plan = plan

    assert not m._stamp_pendiente(_Ctx()), (
        "con ruta ganadora el Sello deja de tener prioridad de orden")

    _Ctx.turn_plan = gp.NO_PLAN
    assert m._stamp_pendiente(_Ctx()), (
        "sin ruta ganadora el Sello conserva su prioridad de siempre")
