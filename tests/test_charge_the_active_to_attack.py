"""Tests of the rule "ATTACKING WITH THE ACTIVE IS THE FIRST THING".

Before handing out the turn's energy, the agent must ask itself whether the ACTIVE
can reach its ATTACK COST using ALL the charging routes still
alive for it (the manual attachment + abilities that can point at it: Ripening Charge from
any Hydrapple ex, Teal Dance if the active itself is the Ogerpon). If it gets there
and the attack does damage, the energy goes to the ACTIVE:

  * `_charge_active_finishes` (the attack KNOCKS OUT)  -> SCORE_CHARGE_ACTIVE_FINISHER,
    ahead of charging a BENCH attacker to promote it (41000) and of
    Ogerpon's charging focus (41700);
  * `_charge_active_enables_attack` (only a chip, but without that charge the turn
    would be STERILE) -> SCORE_CHARGE_ACTIVE_ATTACK, above Teal Dance (31500) and the
    retreat pivots by ability (31600).

The originating case (user, episode 88433181, registro_006 step 67 vs Marnie's
Grimmsnarl, WON with a mistake): a Hydrapple ex ACTIVE just evolved at 0
energies, THREE Grass in hand, the manual attachment unspent, two live Ripening Charge
and the rival active (Munkidori) at 10 HP. The agent charged the BENCH
Hydrapple and sent the abilities to a bench Ogerpon: a turn without attacking with the
KO on a plate. On top of that the bench plan was IMPOSSIBLE -- promoting it required retreating
the active Hydrapple (cost 3) with 0 energies on it.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from cg.api import AreaType, OptionType
from state_builder import G, Scenario, pk

APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
MEOWTH = m.Meowth_ex
FEZA = m.Fezandipiti_ex
ENERGY = m.Basic_Grass_Energy

_FIXTURE = ROOT / "tests" / "fixtures" / "grimmsnarl_step67_carga_activo_para_syrup.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    """This file had no reset and worked only because it sorted FIRST in
    the suite, inheriting the clean globals from the import. Any file that
    sorted before it left `op_is_crustle_deck` / `meganium_in_play` / ...
    switched on from the previous game and knocked it down. The same reset as its
    siblings: the suite's order stops mattering."""
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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs_step67():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _attach_options(obs):
    """{position: 'activo'|'banca-k'} for the menu's ATTACH options."""
    destinos = {}
    for i, opt in enumerate(obs["select"]["option"]):
        if opt.get("type") != OptionType.ATTACH:
            continue
        if opt.get("inPlayArea") == AreaType.ACTIVE:
            destinos[i] = "activo"
        else:
            destinos[i] = f"banca-{opt.get('inPlayIndex')}"
    return destinos


def test_step67_charges_the_active_not_the_bench_hydrapple():
    """The real record: the Grass goes to the ACTIVE Hydrapple ex (Syrup Storm = KO)."""
    obs = _obs_step67()
    cur = obs["current"]
    mio = cur["players"][cur["yourIndex"]]

    # The scenario must be the record's for the test to mean anything.
    assert mio["active"][0]["id"] == HYDRAPPLE
    assert mio["active"][0]["energies"] == []
    assert cur["energyAttached"] is False
    assert sum(1 for c in mio["hand"] if c["id"] == ENERGY) >= 2

    destinos = _attach_options(obs)
    assert "activo" in destinos.values()
    assert any(d.startswith("banca") for d in destinos.values())

    choice = m.agent(obs)

    assert len(choice) == 1 and choice[0] in destinos, (
        f"esperaba un ATTACH, obtuvo {choice} (destinos={destinos})")
    assert destinos[choice[0]] == "activo", (
        f"la energia debia ir al ACTIVO, fue a {destinos[choice[0]]}")


def test_step67_ripening_charge_aims_at_the_active():
    """With the manual attachment already spent, Ripening Charge completes the cost."""
    obs = _obs_step67()
    cur = obs["current"]
    mio = cur["players"][cur["yourIndex"]]

    # Simulating the next step: the manual attachment already put 1 Grass on the active
    # (1 is left for the cost of Syrup Storm, which the ability must supply).
    energy = next(c for c in mio["hand"] if c["id"] == ENERGY)
    mio["hand"] = [c for c in mio["hand"] if c is not energy]
    mio["handCount"] = len(mio["hand"])
    mio["active"][0]["energies"] = [G]
    mio["active"][0]["energyCards"] = [energy]
    cur["energyAttached"] = True
    # A menu with only the live abilities (each Hydrapple's Ripening) and END.
    obs["select"]["option"] = [
        {"type": int(OptionType.ABILITY), "area": int(AreaType.ACTIVE), "index": 0},
        {"type": int(OptionType.ABILITY), "area": int(AreaType.BENCH), "index": 0},
        {"type": int(OptionType.ABILITY), "area": int(AreaType.BENCH), "index": 4},
        {"type": int(OptionType.END)},
    ]

    choice = m.agent(obs)

    assert choice and choice[0] in (0, 1), (
        f"esperaba activar Ripening Charge (opt 0/1), obtuvo {choice}")


def test_step67_with_the_active_charged_it_attacks():
    """Closing the chain: with the 2 Grass on it, Syrup Storm fires."""
    obs = _obs_step67()
    cur = obs["current"]
    mio = cur["players"][cur["yourIndex"]]

    energies = [c for c in mio["hand"] if c["id"] == ENERGY][:2]
    mio["hand"] = [c for c in mio["hand"] if c not in energies]
    mio["handCount"] = len(mio["hand"])
    mio["active"][0]["energies"] = [G, G]
    mio["active"][0]["energyCards"] = energies
    cur["energyAttached"] = True
    obs["select"]["option"] = [
        {"type": int(OptionType.ATTACK), "attackId": 195},
        {"type": int(OptionType.END)},
    ]

    assert m.agent(obs) == [0], "con Syrup Storm listo y el rival a 10 PV, ATACA"


# --- A deck-agnostic generalisation (synthetic scenarios) ------------------

def test_an_active_ogerpon_charges_itself_to_finish():
    """An ACTIVE Ogerpon ex at 2 energies: the 3rd (Myriad) finishes -> it goes to the ACTIVE.

    On the bench there is a Hydrapple ex at 0 energies, the "development" target that
    used to take the Grass.
    """
    obs = (Scenario(turn=8, step=90, tac=2)
           .my_active(pk(OGERPON, energies=[G, G]))
           .my_bench(pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN]), MEOWTH)
           .my_hand(ENERGY, ENERGY)
           .op_active(pk(m.Munkidori, hp=40))
           .op_bench(pk(m.Froslass, pre_evo=[m.Snorunt]))
           .op_zones(hand=4, deck=30, prizes=4)
           .menu_attach_energy()
           .build())

    destinos = _attach_options(obs)
    choice = m.agent(obs)

    assert destinos[choice[0]] == "activo", (
        f"la Planta debia ir al Ogerpon ACTIVO (remata), fue a "
        f"{destinos[choice[0]]}")


def test_no_finisher_but_a_sterile_turn_also_charges_the_active():
    """With no KO available, charging the active is the only way to attack today."""
    obs = (Scenario(turn=8, step=90, tac=2)
           .my_active(pk(HYDRAPPLE, energies=[G], pre_evo=[APPLIN, DIPPLIN]))
           .my_bench(pk(APPLIN), MEOWTH)
           .my_hand(ENERGY)
           .op_active(pk(m.Grimmsnarl_ex, hp=320,
                         energies=[G, G, G]))
           .op_zones(hand=4, deck=30, prizes=5)
           .menu_attach_energy()
           .build())

    destinos = _attach_options(obs)
    choice = m.agent(obs)

    assert destinos[choice[0]] == "activo", (
        f"sin la carga al activo el turno seria esteril; fue a "
        f"{destinos[choice[0]]}")


def test_an_active_that_already_attacks_does_not_hog_the_energy():
    """A negative control: if the active ALREADY reaches its cost, the rule does not fire.

    The active Hydrapple ex with 2 energies already attacks; the Grass must follow the
    normal distribution (bench development), not stay on the active.
    """
    obs = (Scenario(turn=8, step=90, tac=2)
           .my_active(pk(HYDRAPPLE, energies=[G, G], pre_evo=[APPLIN, DIPPLIN]))
           .my_bench(pk(OGERPON), MEOWTH)
           .my_hand(ENERGY)
           .op_active(pk(m.Grimmsnarl_ex, hp=320,
                         energies=[G, G, G]))
           .op_zones(hand=4, deck=30, prizes=5)
           .menu_attach_energy()
           .build())

    destinos = _attach_options(obs)
    choice = m.agent(obs)

    assert destinos[choice[0]] != "activo", (
        "el activo ya podia atacar: la energia debia ir a la banca")
