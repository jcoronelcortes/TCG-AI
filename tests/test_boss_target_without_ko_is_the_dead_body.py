"""The gust target WITH NO KO: bring up the body that CANNOT attack.

The third piece of the [[boss-no-regalar-la-linea-alakazam]] family. The two
previous ones fixed WHEN Boss's Orders is played; this one fixes WHO it brings up
once it is played and there is no KO.

The two bands of `_gust_opponent_line` scored it backwards:

  * `_gust_evolution_line` gives **800 to the FINAL EVOLUTION** (Dragapult ex,
    Typhlosion, Alakazam) with no KO -- above the 700 of the stuck Stage 1,
    which its OWN docstring calls "the best disruption target";
  * `_gust_generic_tiers` gives **250 to a CHARGED ex**, the ceiling of its band
    with no KO, above any stuck body.

With no KO that is putting in front of us -- and for free, because Boss's pays their retreat --
exactly the body they wanted to attack with. And it contradicted the detector that
JUSTIFIES the play: the DEFENSIVE gust (`_bo_defensive_gust`, 940) is worth it because
there EXISTS on their bench a body that cannot finish us off... and then the selector
brought up another one.

`without_a_ko_prefer_the_dead_body` (+1500, in BOTH modes) puts ahead the
body that cannot pay for its attack even by attaching one energy. +1500 beats
the whole no-KO band (100-1200) and does not touch the KO tiers (>= 3000), which are
gated by `can_ko`.

`GUST_TRAP_IDS` is the mandatory exception: Crustle, Sylveon, Cornerstone and
Iron Thorns ex have **cost-3** attacks, so bare they pass for
"harmless" -- and they are exactly the bodies we do NOT want in front (they cancel
our attackers or switch off our abilities from the active spot).

Golden corpus: 0 flips (the local records barely reach the target prompt),
which is why the scenario is FABRICATED with StateBuilder.
"""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk, G

DRAGAPULT, DRAKLOAK, DREEPY = m.Dragapult_ex, m.Drakloak, m.Dreepy
DUSCLOPS = m.Dusclops
BAYLEEF, CHIKORITA = m.Bayleef, m.Chikorita


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
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _stub(card_id, energy=0):
    """A minimal Pokemon that `prize_count_op` and `_op_body_is_harmless` understand."""
    return SimpleNamespace(id=card_id, energies=[1] * energy,
                           energyCards=[], tools=[])


def _ctx(card_id, energy=0, can_ko=False, op_dragapult_line=False):
    """A `_CtxGustObjetivo` with the data DERIVED from the real card, so that the
    test does not stay glued to made-up numbers."""
    d = m.card_table.get(card_id)
    return m._CtxGustObjetivo(
        card_id=card_id, energy=energy,
        rc0=m.RETREAT_COST.get(card_id, 0), rc1=m.RETREAT_COST.get(card_id, 1),
        stall_diff=m.RETREAT_COST.get(card_id, 0) - energy,
        is_ex=bool(getattr(d, 'ex', False)), is_exmega=bool(getattr(d, 'ex', False)),
        is_megaex=bool(getattr(d, 'megaEx', False)),
        prizes=m.prize_count_op(_stub(card_id, energy)),
        wins_now=False,
        is_stage1=bool(getattr(d, 'stage1', False)),
        is_stage2=bool(getattr(d, 'stage2', False)),
        tiene_tool=False, can_ko=can_ko, tier_ko=5 if can_ko else 0,
        plan_target_match=False, regust_energized=False,
        line_rank=0, line_can_ko=False, op_alakazam=False,
        op_latias=False, op_dragapult_line=op_dragapult_line,
        op_typhlosion_line=False,
        body_is_harmless=m._op_body_is_harmless(_stub(card_id, energy)))


def _ofensivo(ctx):
    score, _ = m._resolve_rules([], m._ADJUST_GUST_OFFENSIVE, ctx, default=0)
    return score


def _estorbo(ctx):
    score, _ = m._resolve_rules(m._RULES_GUST_NUISANCE,
                                 m._ADJUST_GUST_NUISANCE, ctx, default=-200)
    return score


# ---------------------------------------------------------------------------
# 1. The old band preferred the fattest piece: the test's control
# ---------------------------------------------------------------------------

def test_the_no_ko_band_used_to_reward_the_final_evolution():
    """`_gust_evolution_line` still gives 800 to the final one and 700 to the stuck
    Stage 1: the contribution has NOT been touched, it has been overlaid."""
    final = m._gust_evolution_line(_ctx(DRAGAPULT, energy=1),
                                    DRAGAPULT, DRAKLOAK, DREEPY)
    medio = m._gust_evolution_line(_ctx(DRAKLOAK), DRAGAPULT, DRAKLOAK, DREEPY)
    assert final == 800 and medio == 700


# ---------------------------------------------------------------------------
# 2. OFFENSIVE mode
# ---------------------------------------------------------------------------

def test_with_no_ko_the_dead_body_beats_the_final_evolution():
    # Their 2nd Dragapult ex with 1 energy ALREADY attacks (Jet Headbutt costs 1).
    attacker = _ctx(DRAGAPULT, energy=1, op_dragapult_line=True)
    # The bare Dusclops cannot pay for its cost-2 attack.
    dead = _ctx(DUSCLOPS, op_dragapult_line=True)
    assert not attacker.body_is_harmless and dead.body_is_harmless
    assert _ofensivo(dead) > _ofensivo(attacker)


def test_with_a_ko_the_tiers_rule_and_the_dead_body_does_not_override():
    """The bonus is gated by `not can_ko`: knocking out a 2-prize ex still
    beats bringing up a dead body."""
    ko_ex = _ctx(DRAGAPULT, energy=1, can_ko=True, op_dragapult_line=True)
    dead = _ctx(DUSCLOPS, op_dragapult_line=True)
    assert _ofensivo(ko_ex) > _ofensivo(dead)


def test_the_walls_and_the_locker_do_not_get_the_bonus():
    """Cost 3 => bare they pass for harmless, but bringing them up is the trap:
    they cancel our attackers or switch off our abilities from the active spot."""
    for trampa in sorted(m.GUST_TRAP_IDS):
        c = _ctx(trampa)
        assert c.body_is_harmless, f"{trampa} deberia ser 'inofensivo' por coste"
        without_bonus = _ofensivo(c)
        assert without_bonus < _ofensivo(_ctx(DUSCLOPS)), (
            f"{trampa} esta en GUST_TRAMPA_IDS: no puede cobrar los +1500")


# ---------------------------------------------------------------------------
# 3. NUISANCE mode
# ---------------------------------------------------------------------------

def test_nuisance_breaks_the_tie_towards_the_one_that_cannot_attack():
    """`net_stuck` only looks at who cannot pay their RETREAT. With the same
    stuckness (both retreat 2, no energy), it decides who cannot pay for their
    ATTACK: the Gardevoir ex attacks for 1, the Dusclops needs 2."""
    assert m.RETREAT_COST[m.Gardevoir_ex] == m.RETREAT_COST[DUSCLOPS] == 2
    ataca = _ctx(m.Gardevoir_ex)
    dead = _ctx(DUSCLOPS)
    assert not ataca.body_is_harmless and dead.body_is_harmless
    assert _estorbo(dead) > _estorbo(ataca)


def test_nuisance_does_not_rescue_a_forbidden_target():
    """The `s > 0` guard: a Budew (free retreat) is still FORBIDDEN even if the
    bonus existed."""
    assert _estorbo(_ctx(m.Budew)) == m.SCORE_FORBID


# ---------------------------------------------------------------------------
# 4. The full board
# ---------------------------------------------------------------------------

def _board(active_energies):
    """An active Bayleef (60 damage: it knocks out nothing on the board) against a
    Dragapult ex. On their bench, another Dragapult ex with 1 energy -- ready to
    attack -- and a bare Dusclops."""
    return (Escenario(turn=8, step=80, tac=4, own_prizes=4)
            .my_active(pk(BAYLEEF, energies=[G] * active_energies,
                          fisicas=active_energies, pre_evo=[CHIKORITA]))
            .my_bench(pk(CHIKORITA))
            .op_active(pk(DRAGAPULT, hp=320, max_hp=320, energies=[G, G]))
            .op_bench(pk(DRAGAPULT, hp=320, max_hp=320, energies=[G]),
                      pk(DUSCLOPS, hp=90, max_hp=90))
            .op_zonas(hand=5, deck=25, prizes=4)
            .deck()
            # `menu_gust()` consumes a Boss's Orders from the pool (the card "in
            # effect"), so it goes BEFORE `rest_to_discard()`.
            .menu_gust()
            .rest_to_discard()
            .build())


def test_the_synthetic_board_has_no_ko_at_all():
    obs = _board(2)
    assert m.ATTACK_ENERGY_REQ[BAYLEEF] == 2      # with 2 energies it DOES attack
    # 60 damage knocks out neither the Dragapult ex (320) nor the Dusclops (90).
    riv = obs["current"]["players"][1]
    assert [p["hp"] for p in riv["bench"]] == [320, 90]
    # The menu offers both bodies from their bench.
    assert [o["index"] for o in obs["select"]["option"]] == [0, 1]


def test_the_dusclops_comes_up_not_the_second_dragapult():
    assert m.agent(copy.deepcopy(_board(2))) == [1], (
        "con nuestro activo atacando pero sin KO, subir su 2o Dragapult ex le "
        "pone delante el cuerpo con el que ataca; el Dusclops pelado no puede")


def test_en_modo_estorbo_tambien():
    assert m.agent(copy.deepcopy(_board(1))) == [1]
