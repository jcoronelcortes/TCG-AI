"""The energy that TAKES A PRIZE TODAY is not development.

Scenario (`records/registro_008_pasos_083_hasta_098.json`, step 85, episode
89630419 -- LOST):

    US                                     RIVAL
    active  Teal Mask Ogerpon ex  2 energy  active  Mega Kangaskhan ex 90/300
    bench   Meowth ex                               (3 energy, 3 prizes)
            Teal Mask Ogerpon ex  2 energy  bench   one 70 HP body
            Teal Mask Ogerpon ex  2 energy
            Fezandipiti ex
    hand    Ultra Ball, Dawn, Bayleef, Meganium, Boss's Orders, Forest
    turn's energy: UNSPENT.  Teal Dance: UNSPENT.  Six Grass in the DISCARD.

Myriad Leaf Shower costs three: the active was one short and did zero. One Grass
out of the discard, attached by Teal Dance (an ABILITY -- it does not even touch
the turn's attachment), takes it to 3 and the attack does 30 + 30 x (3 own + 3
theirs) = 210 against 90 HP: a KO worth THREE prizes, against an opponent sitting
on 2 prizes left.

The agent played the Night Stretcher and recovered an **Applin**. It then spent
the turn evolving a bench line and ended without attacking at all.

Why. The fetch tables price the Grass as DEVELOPMENT. The best rule that fired
for it was `active_needs_energy` (900) -- "the active is short of energy", which
says nothing about what that energy BUYS. Meanwhile the Applin took
`start_the_hydra_line` (700) + 100 for being the last copy outside the deck +
150 from the cross-cutting bonus for a card with no copies left = **950**. A
starter for a line that would attack in two turns' time outscored a prize on the
table, by 50 points, because nothing in the table could tell the two apart.

Rule: **a recovered energy that, placed on the ACTIVE, turns an attack that does
not knock out -- or that cannot even be paid for -- into a KO this turn, is not
development: it goes into the band of a prize TODAY (1400), above every
development target.**

Implementation: `_grass_on_active_enables_ko` in
`ptcg/decision/night_stretcher.py`, wired into `_ctx_ns_fetch` as
`grass_makes_the_active_ko` and into the three grass fetch tables
(`_RULES_NS_GRASS`, `_RULES_BCS_GRASS`, `_RULES_DAWN_GRASS`).

Deck-agnostic and card-agnostic by construction: the arithmetic is delegated to
`_attacker_base_damage` (which returns 0 below `ATTACK_ENERGY_REQ`, so the SAME
comparison covers "it falls short of the KO" and "it cannot attack at all") and
to `_our_effective_damage` (weakness, resistance, Neutralization Zone and the
immunities of Crustle/Cornerstone/Drednaw/Sturdy). An unreachable target can
therefore never make it fire, and no matchup guard is needed on top. The
synthetic pair below deliberately uses a **Tapu Bulu**, an attacker with NO
charging ability, so the line does not depend on Teal Dance existing.

The sibling that was already there, `grass_makes_syrup_storm_lethal`, only
covered the active Hydrapple ex whose Syrup Storm was already payable and fell
short. This one covers the rest of the board and, above all, the active that is
BELOW its cost -- which is where the whole turn dies.
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
from tests.state_builder import Scenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "kangaskhan_t8_night_stretcher_takes_the_energy_step85.json")

GRASS = m.Basic_Grass_Energy
APPLIN = m.Applin
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
MEOWTH = m.Meowth_ex
NIGHT_STRETCHER = m.Night_Stretcher

MEGA_KANGASKHAN = 756          # the rival active of the record: 300 HP, 3 prizes


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


def _obs_step85():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _chosen_id(obs):
    """The id of the discard card the fetch picks."""
    cur = obs["current"]
    discard = cur["players"][cur["yourIndex"]]["discard"]
    choice = m.agent(obs)
    assert len(choice) == 1, f"esperaba una sola carta, obtuvo {choice}"
    return discard[obs["select"]["option"][choice[0]]["index"]]["id"]


# ----------------------------------------------------------------------
# The record
# ----------------------------------------------------------------------

def test_step85_the_scenario_is_the_one_of_the_record():
    """Without these preconditions the test below measures nothing."""
    obs = _obs_step85()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    op = cur["players"][1 - cur["yourIndex"]]

    assert mine["active"][0]["id"] == OGERPON
    assert len(mine["active"][0]["energies"]) == 2      # Myriad Leaf Shower costs 3
    assert cur["energyAttached"] is False               # Teal Dance and the attachment, both alive
    assert not any(c["id"] == GRASS for c in mine["hand"])
    assert op["active"][0]["hp"] == 90

    offered = {mine["discard"][o["index"]]["id"] for o in obs["select"]["option"]}
    assert GRASS in offered and APPLIN in offered, (
        "el menu no ofrece las dos alternativas: no mide la eleccion")


def test_step85_recovers_the_energy_and_not_the_applin():
    """The historical bug: it recovered an Applin and ended the turn without attacking."""
    assert _chosen_id(_obs_step85()) == GRASS


# ----------------------------------------------------------------------
# Deck-agnostic: an attacker with NO charging ability
# ----------------------------------------------------------------------

def _scenario_tapu(op_hp):
    """Active Tapu Bulu one energy short of Wood Hammer (220), turn's attachment
    unspent, no Grass in hand and both Applin in the discard.

    Tapu Bulu has no ability: the only route to the active is the MANUAL
    attachment, so nothing here depends on Teal Dance or Ripening Charge. With
    both Applin outside the deck the development branch is at its ceiling (700 +
    100 + 150 = 950), which is exactly what beat the energy in the record.
    """
    req = m.AGENT_STATE.ATTACK_ENERGY_REQ[TAPU]
    return (Scenario(turn=8, step=85, tac=4, first_player=1)
            .my_active(pk(TAPU, energies=req - 1))
            .my_bench(pk(MEOWTH), pk(OGERPON))
            .my_hand(m.Ultra_Ball)
            .my_discard(GRASS, GRASS, APPLIN, APPLIN)
            .op_active(pk(MEGA_KANGASKHAN, hp=op_hp, max_hp=300))
            .op_zones(hand=4, deck=39, prizes=2)
            .fetch_discard(NIGHT_STRETCHER, only=(GRASS, APPLIN))
            .build())


def test_the_energy_that_kos_beats_the_development_with_no_ability_involved():
    """220 of Wood Hammer against 200 HP: the Grass IS the prize."""
    assert _chosen_id(_scenario_tapu(op_hp=200)) == GRASS


def test_without_the_ko_the_development_still_wins():
    """The same board with the rival out of reach (250 HP > 220): the energy goes
    back to being development and the line starter wins, as before.

    This is the control: without it the test above would pass with a rule that
    simply always prefers the energy.
    """
    assert _chosen_id(_scenario_tapu(op_hp=250)) == APPLIN


def test_with_the_route_to_the_active_closed_the_rule_does_not_fire():
    """Same lethal board, but the turn's attachment is SPENT and no charging
    ability can reach a Tapu Bulu: the Grass cannot get onto the active this
    turn, so it stops being a prize today."""
    req = m.AGENT_STATE.ATTACK_ENERGY_REQ[TAPU]
    obs = (Scenario(turn=8, step=85, tac=4, first_player=1,
                     energy_played=True)
           .my_active(pk(TAPU, energies=req - 1))
           .my_bench(pk(MEOWTH), pk(m.Fezandipiti_ex))
           .my_hand(m.Ultra_Ball)
           .my_discard(GRASS, GRASS, APPLIN, APPLIN)
           .op_active(pk(MEGA_KANGASKHAN, hp=200, max_hp=300))
           .op_zones(hand=4, deck=39, prizes=2)
           .fetch_discard(NIGHT_STRETCHER, only=(GRASS, APPLIN))
           .build())
    assert _chosen_id(obs) == APPLIN


# ----------------------------------------------------------------------
# The rest of the chain: the recovered energy is not left dead in hand
# ----------------------------------------------------------------------

def _board_of_the_record(active_energy, hand, menu):
    """The board of step 85 with the recovered Grass already in hand.

    Three Teal Mask Ogerpon ex at two energies each and the rival Mega
    Kangaskhan ex at 90 HP with three energies of its own: Myriad Leaf Shower
    with three of ours does 30 + 30 x (3 + 3) = 210.
    """
    esc = (Scenario(turn=8, step=86, tac=5, first_player=1)
           .my_active(pk(OGERPON, energies=active_energy))
           .my_bench(pk(OGERPON, energies=2), pk(OGERPON, energies=2),
                     pk(MEOWTH))
           .my_hand(*hand)
           .my_discard(APPLIN, APPLIN)
           .op_active(pk(MEGA_KANGASKHAN, hp=90, max_hp=300, energies=3))
           .op_zones(hand=4, deck=39, prizes=2))
    return menu(esc).build()


def test_the_recovered_energy_goes_to_the_active_and_not_to_the_bench():
    """Two energies on the active, one short: the Grass (by hand or by Teal
    Dance) has to end up on the ACTIVE, which is the one that knocks out."""
    obs = _board_of_the_record(
        active_energy=2, hand=(GRASS,),
        menu=lambda e: e.menu_teal_dance_options())
    opt = obs["select"]["option"][m.agent(obs)[0]]
    tipo = opt.get("type")
    if tipo == int(m.OptionType.ATTACH):
        assert opt.get("inPlayArea") == int(m.AreaType.ACTIVE), (
            f"la Planta fue a la banca: {opt}")
    else:
        assert tipo == int(m.OptionType.ABILITY), f"esperaba carga, obtuvo {opt}"
        assert opt.get("area") == int(m.AreaType.ACTIVE), (
            f"Teal Dance se uso en un Ogerpon de banca: {opt}")


def test_with_the_active_already_charged_the_turn_ends_attacking():
    """The other end of the chain: with the three energies paid, the agent
    attacks instead of ending the turn."""
    obs = _board_of_the_record(
        active_energy=3, hand=(m.Ultra_Ball,),
        menu=lambda e: e.menu_hand(with_attack=True, with_retreat=True))
    opt = obs["select"]["option"][m.agent(obs)[0]]
    assert opt.get("type") == int(m.OptionType.ATTACK), (
        f"con el remate en la mesa eligio {opt}")
