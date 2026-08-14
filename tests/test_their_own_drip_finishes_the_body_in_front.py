"""registro_006 step 90 vs Marnie's Grimmsnarl ex, episode 92871474, LOST.

THE BOARD. Their Grimmsnarl ex had just knocked out our Teal Mask Ogerpon ex
and taken the prizes that left both piles at FOUR. The forced promotion menu
offered exactly two bodies:

    Meowth ex   130/170, no energy          -- Last-Ditch Catch, no attack
    Meganium     50/160, 2 Grass = 4 eff.   -- Solar Beam, 140

and in front of them a Grimmsnarl ex at 320/320 with four Darkness. On their
bench, two Froslass and two Munkidori.

WHAT THE AGENT DID. It promoted the Meowth ex (-1461 against the Meganium's
-6000) and the turn had no attack in it at all.

WHY. The Meganium line is vetoed out of the active spot -- SCORE_NEVER, it is
the Wild Growth engine and it doubles every Grass on our board from the bench --
with ONE exemption: the KO-aware selector points at it AND its hit knocks the
opposing active out next turn. Solar Beam is 140, doubled by their Darkness
weakness = 280, and 280 < 320. The exemption did not open.

WHAT THE 40 MISSING POINTS WERE. Freezing Shroud does not say "your opponent's
Pokemon". It puts a counter on EACH Pokemon in play that has an Ability, and
Marnie's Grimmsnarl ex has one (Punk Up) -- the estate already knew it, in the
note next to FREEZING_SHROUD_COUNTER, and used it only to count how much
ammunition Adrena-Brain has. Two Froslass, two checkups between this menu and
their next turn (the one that opens our turn, the one that follows our attack):
40. Their 320 HP body is 280 to us, and 280 is exactly what the Meganium does.

THE LINE THE BOARD HAD. Promote Meganium; the checkup leaves it at 30 and their
Grimmsnarl ex at 300; Solar Beam takes it to 20; the next checkup takes the last
20 and hands us TWO prizes, before they can heal it, retreat it or move the
damage off it with Adrena-Brain -- the counters land between turns, where they
cannot act.

The first test pins the arithmetic, the second the choice, the third the attack
that cashes it, and the rest the boundaries: no Froslass, no Ability, the
Froslass themselves, and one Froslass instead of two.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m                                             # noqa: E402
import golden_corpus as gc                                   # noqa: E402
from state_builder import Scenario, pk, G                    # noqa: E402
from ptcg.calc.damage import (_has_ability, _op_hp_for_our_ko,   # noqa: E402
                              _shroud_damage_to)
from ptcg.state.agent_state import AGENT_STATE               # noqa: E402

GRIMMSNARL_EX = m.Grimmsnarl_ex        # 320 HP, 2 prizes, weak to Grass
IMPIDIMP = m.Marnies_Impidimp          # 70 HP, NO Ability
MUNKIDORI = m.Munkidori                # 110 HP, Adrena-Brain
FROSLASS = m.Froslass                  # 90 HP, Freezing Shroud
DARK = int(m.EnergyType.DARKNESS)

# Solar Beam (140) through their Darkness weakness.
MEGANIUM_HIT = 280


def _their_bench(froslass=2):
    """Their bench at the record's step 90, with `froslass` Froslass on it."""
    out = [pk(MUNKIDORI, hp=110, energies=[DARK]),
           pk(MUNKIDORI, hp=110, energies=[DARK])]
    out += [pk(FROSLASS, hp=90) for _ in range(froslass)]
    return out


def _the_promotion(froslass=2, op_active=None, meganium_hp=50):
    """registro_006 step 90: the active spot is EMPTY and the menu is the bench.

    `promote_from_bench()` keeps an active (the builder demands one); the forced
    promotion after a knockout has an EMPTY spot, which is what
    `_forced_ko_promote` reads, so it is emptied here exactly as the record
    shows it -- and the placeholder is a body the record does not have on the
    field, so it cannot take part in the menu.
    """
    obs = (Scenario(turn=6, step=90, tac=26, own_prizes=4,
                     supporter_played=True)
            .my_active(pk(m.Applin))
            .my_bench(pk(m.Meowth_ex, hp=130),
                      pk(m.Meganium, hp=meganium_hp, energies=[G] * 4, fisicas=2,
                         pre_evo=[m.Chikorita, m.Bayleef]))
            .my_hand(m.Lanas_Aid, m.Basic_Grass_Energy)
            .op_active(op_active if op_active is not None
                       else pk(GRIMMSNARL_EX, hp=320,
                               energies=[DARK] * 4, fisicas=4))
            .op_bench(*_their_bench(froslass))
            .op_zones(hand=6, deck=18, prizes=4)
            .deck(m.Basic_Grass_Energy, m.Basic_Grass_Energy)
            .rest_to_discard()
            .promote_from_bench()
            .build())
    obs["current"]["players"][0]["active"] = []
    return obs


def _promoted(obs, choice):
    opt = obs["select"]["option"][choice[0]]
    return m.get_card(m.to_observation_class(obs),
                      opt["area"], opt["index"], 0).id


def _the_turn_after(froslass=2):
    """Our turn, one checkup later: Meganium in front at 30, theirs at 300."""
    return (Scenario(turn=7, step=92, tac=0, own_prizes=4)
            .my_active(pk(m.Meganium, hp=30, energies=[G] * 4, fisicas=2,
                          pre_evo=[m.Chikorita, m.Bayleef]))
            .my_bench(pk(m.Meowth_ex, hp=110))
            .my_hand(m.Lanas_Aid, m.Basic_Grass_Energy)
            .op_active(pk(GRIMMSNARL_EX, hp=300, max_hp=320,
                          energies=[DARK] * 4, fisicas=4))
            .op_bench(*_their_bench(froslass))
            .op_zones(hand=6, deck=18, prizes=4)
            .deck(m.Basic_Grass_Energy, m.Basic_Grass_Energy)
            .rest_to_discard()
            .menu_hand(with_attack=True)
            .build())


@pytest.fixture(autouse=True)
def _reset():
    gc.reset_agent(m)


# --------------------------------------------------------------------------
# 1. The arithmetic
# --------------------------------------------------------------------------
def test_the_drip_falls_on_their_own_board_too():
    """40 of their own Froslass over the two checkups this menu is followed by."""
    obs = _the_promotion()
    m.agent(obs)                        # refreshes the drip counters

    st = m.to_observation_class(obs).current
    grimm = st.players[1].active[0]

    assert AGENT_STATE._op_chip_per_checkup == 20, "two Froslass, one checkup"
    assert AGENT_STATE._op_chip_per_round == 40, "two checkups in the round"
    assert _has_ability(GRIMMSNARL_EX), "Punk Up"
    assert _shroud_damage_to(grimm, m.CHECKUPS_PER_ROUND) == 40
    # 320 printed, 280 to us -- exactly Solar Beam through their weakness.
    assert _op_hp_for_our_ko(grimm, m.CHECKUPS_PER_ROUND) == MEGANIUM_HIT


def test_the_bodies_the_drip_does_not_touch():
    """No Ability, and Froslass itself, pay nothing -- and neither does anyone
    on a board without a Froslass on it."""
    obs = _the_promotion()
    m.agent(obs)
    st = m.to_observation_class(obs).current
    op = st.players[1]

    assert not _has_ability(IMPIDIMP), "Marnie's Impidimp prints no Ability"
    assert _shroud_damage_to(SimpleNamespace(id=IMPIDIMP, hp=70), 2) == 0

    froslass = next(p for p in op.bench if p.id == FROSLASS)
    assert _shroud_damage_to(froslass, 2) == 0, "the card excludes its own kind"
    assert _op_hp_for_our_ko(froslass, 2) == 90

    # No Froslass on the field: the printed HP, untouched. This is the property
    # that makes the reading safe to wire into the knockout tests themselves.
    obs = _the_promotion(froslass=0)
    m.agent(obs)
    grimm = m.to_observation_class(obs).current.players[1].active[0]
    assert AGENT_STATE._op_chip_per_checkup == 0
    assert _op_hp_for_our_ko(grimm, m.CHECKUPS_PER_ROUND) == 320


# --------------------------------------------------------------------------
# 2. The choice
# --------------------------------------------------------------------------
def test_the_meganium_takes_the_front_spot():
    """The record's decision, the other way round."""
    obs = _the_promotion()
    assert _promoted(obs, m.agent(obs)) == m.Meganium, \
        "the body that cashes the two prizes comes up"


def test_without_their_froslass_the_veto_stands():
    """The boundary: 280 against a printed 320 is not a knockout, the Wild
    Growth engine stays on the bench and the mute ex takes the blow."""
    obs = _the_promotion(froslass=0)
    assert _promoted(obs, m.agent(obs)) == m.Meowth_ex


def test_one_froslass_is_not_enough():
    """20 of drip over the round leaves 300 against 280: still not lethal, so
    nothing about the Meganium veto moves."""
    obs = _the_promotion(froslass=1)
    m.agent(obs)
    grimm = m.to_observation_class(obs).current.players[1].active[0]
    assert _op_hp_for_our_ko(grimm, m.CHECKUPS_PER_ROUND) == 300 > MEGANIUM_HIT

    obs = _the_promotion(froslass=1)
    assert _promoted(obs, m.agent(obs)) == m.Meowth_ex


def test_a_body_with_no_ability_in_front_is_read_at_its_printed_hp():
    """Their Impidimp takes no counters, so nothing is discounted from it."""
    obs = _the_promotion(op_active=pk(IMPIDIMP, hp=70))
    m.agent(obs)
    front = m.to_observation_class(obs).current.players[1].active[0]
    assert _op_hp_for_our_ko(front, m.CHECKUPS_PER_ROUND) == 70


# --------------------------------------------------------------------------
# 3. The attack that cashes it
# --------------------------------------------------------------------------
def test_the_turn_after_reads_the_knockout_and_attacks():
    """One checkup left after the attack: 280 against 300 IS a knockout."""
    obs = _the_turn_after()
    m.agent(obs)

    st = m.to_observation_class(obs).current
    grimm = st.players[1].active[0]
    assert _op_hp_for_our_ko(grimm, 1) == MEGANIUM_HIT
    assert AGENT_STATE.plan.attacker == 0, "the Meganium in front is the attacker"
    assert AGENT_STATE.plan.remain_hp is not None
    assert AGENT_STATE.plan.remain_hp <= 0, (
        "the hit falls 20 short of the printed HP and their own checkup pays it")


def test_the_turn_after_without_froslass_is_not_a_knockout():
    """The same board with their drip switched off: 280 against 300 is a chip."""
    obs = _the_turn_after(froslass=0)
    m.agent(obs)
    assert AGENT_STATE.plan.remain_hp is not None
    assert AGENT_STATE.plan.remain_hp > 0


def test_the_promoted_body_has_to_survive_the_checkup_first():
    """The mirror of the same rule, and the hole this reading would open on its
    own: the candidate takes the checkup that opens our turn BEFORE it swings.

    A Meganium at 20 is removed by the same 20 that softens their Grimmsnarl ex.
    It never attacks, so it is not a knocker -- it is a free prize -- and the
    veto that keeps the Wild Growth engine off the front spot stands.
    """
    obs = _the_promotion(meganium_hp=20)
    assert _promoted(obs, m.agent(obs)) == m.Meowth_ex

    # One point above the drip it survives, swings, and comes up again.
    obs = _the_promotion(meganium_hp=30)
    assert _promoted(obs, m.agent(obs)) == m.Meganium
