"""Against the wall that blanks ex, Meganium is an ATTACKER, not the doubler.

Two boards of the same lost game (episode 93251328, vs Crustle / Mega
Kangaskhan ex), fourteen turns apart, and the same sentence under both: the
turn's only Grass went to a body the wall had already switched off while the
one attacker we owned sat at zero.

BOARD ONE -- `records/registro_014_pasos_090_hasta_096.json`, step 92, turn 14:

    US (5 prizes)                         OPPONENT (5 prizes)
    active  Teal Mask Ogerpon ex, 4 eff.  active  Mega Kangaskhan ex 150/300
    bench   **Meganium 160, 0 energy**    bench   **Crustle 170, 3 energy**
            Meowth ex, Chikorita,                 **Crustle 170, 1 energy**
            **Teal Mask Ogerpon ex, 2 eff.**
    hand    Hydrapple ex, **one Basic {G} Energy**

The active Ogerpon knocks the Kangaskhan out this turn on the energy it already
carries. What comes up next is a Crustle, and *Mysterious Rock Inn* cancels all
damage from our Pokemon ex: of everything on that board only the Meganium can
ever touch it. The agent spent the Grass on **Teal Dance over the second
Ogerpon ex** -- 31500 against the attachment's 27000 -- charging a *second* ex
against the wall that blanks ex.

BOARD TWO -- `records/registro_020_pasos_136_hasta_141.json`, step 137, turn 20:

    US (1 prize)                          OPPONENT (2 prizes)
    active  Teal Mask Ogerpon ex, 4 eff.  active  **Crustle 190/190, 3 energy**
    bench   **Meganium 160, 0 energy**    bench   Crustle 150/150, 1 energy
            Meowth ex, Chikorita,
            Fezandipiti ex, **Applin 40** (benched THIS turn)
    hand    six Basic {G} Energy, Dawn, Lillie's Determination, Forest

Their Superb Scissors had just knocked our Tapu Bulu out. One prize from
winning, the turn's attachment went to the **Applin** (30000) over the Meganium
(27000) -- a 40 HP basic that came down this very turn, so it cannot evolve
until the next one, and whose Dipplin dies to one Scissors when it does.

THE TWO CAUSES, one reading.

1. THE RESERVATION DID NOT NAME MEGANIUM. `_wall_atk_needs_grass`
   (`ptcg/turn/options/ability.py`) already says "with a single Grass in hand
   the last one belongs to the body that can still hit the wall", and its
   Crustle creditor list read `(Tapu_Bulu, Dipplin, Pinsir)`. The comment above
   it justified the absence with "against Crustle and Cornerstone it is the
   doubler" -- true of Cornerstone, whose Stance blanks the bodies WITH an
   Ability, and false of Crustle, which blanks the bodies with a rule box.
   Meganium has no rule box: Solar Beam does its 140 into the wall.

2. THE LADDER RANKED IT LAST. In the Crustle band of `_energy_score_base`
   (`ptcg/turn/energy.py`) Meganium's `+19000` was paid only `if not
   _tapu_in_play_meg and not _dipplin_in_play_meg`, under Dipplin's `+23000`
   and Applin's `+22000`. The order is now the order of the attack, which is
   the order the user spelled out:

       Tapu Bulu  Wood Hammer  220   4 units   140 HP
       Meganium   Solar Beam   140   4 units   160 HP
       Dipplin    Do the Wave  20 per benched body (100 at a full bench)
                                     1 unit     80 HP

   The HP column decides what the damage column leaves open. Neither Meganium
   nor Dipplin one-shots a 150 HP Crustle, so the wall costs two swings either
   way -- and Superb Scissors does a flat 120 that "isn't affected by any
   effects on your opponent's Active Pokemon", which the Meganium survives and
   the Dipplin does not.

WHAT DID NOT CHANGE, and the controls below are what say so. The reservation is
about the LAST Grass (with two in hand the dance is free again) and about a
Meganium SHORT of Solar Beam (once it covers the cost it is owed nothing). Tapu
Bulu keeps the top of the ladder. And the Dipplin that yields is the BENCHED
one: an ACTIVE Dipplin that swings today still holds `_ctm_charge_active_dipplin`
at 50000, because a charge that attacks this turn was never development.
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
from cg.api import AreaType, OptionType
from tests.state_builder import Scenario, pk

_FIXTURES = ROOT / "tests" / "fixtures"
_STEP092 = _FIXTURES / "crustle_meganium_is_an_attacker_step092.json"
_STEP137 = _FIXTURES / "crustle_meganium_is_an_attacker_step137.json"

GRASS = m.Basic_Grass_Energy
TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
APPLIN = m.Applin
DIPPLIN = m.Dipplin
MEOWTH = m.Meowth_ex
HYDRAPPLE = m.Hydrapple_ex
FEZ = m.Fezandipiti_ex

CRUSTLE = m.Crustle_Grass          # the wall: our ex do 0 to it
MEGA_KANGASKHAN = 756              # 300 HP, 3 prizes
SOLAR_BEAM = 1028                  # 140, four units
SUPERB_SCISSORS = 479              # 120, and no effect of ours reduces it


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(path):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _chosen(obs):
    """('attach', card_id) / ('ability', card_id) / (type_name, None)."""
    choice = m.agent(obs)
    assert choice, "the agent played nothing"
    opt = obs["select"]["option"][choice[0]]
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]

    def body(area, index):
        return (mine["active"][0] if area == int(AreaType.ACTIVE)
                else mine["bench"][index])["id"]

    if opt["type"] == int(OptionType.ATTACH):
        return "attach", body(opt["inPlayArea"], opt.get("inPlayIndex", 0))
    if opt["type"] == int(OptionType.ABILITY):
        return "ability", body(opt["area"], opt.get("index", 0))
    return str(opt["type"]), None


# ----------------------------------------------------------------------
# 1. The arithmetic that makes Meganium an attacker against this wall
# ----------------------------------------------------------------------

def test_the_wall_blanks_our_ex_and_meganium_is_not_one():
    from ptcg.cards.tables import card_table

    assert CRUSTLE in m.EX_IMMUNE_IDS, "the wall is the ex-immune one"
    assert card_table[MEGANIUM].ex is False
    assert card_table[MEGANIUM].megaEx is False
    assert card_table[OGERPON].ex is True, "and the body it lost the Grass to is"


def test_solar_beam_hits_the_wall_and_survives_its_answer():
    from ptcg.cards.tables import attack_table

    assert attack_table[SOLAR_BEAM].damage == 140
    assert m.ATTACK_ENERGY_REQ[MEGANIUM] == 4, "two Grass cards under Wild Growth"
    # Their answer, and the reason the 160 HP body is the one worth building:
    # 120 flat kills a Dipplin (80) and leaves a Meganium (160) standing.
    assert attack_table[SUPERB_SCISSORS].damage == 120
    assert card_table_hp(MEGANIUM) == 160 > 120 >= card_table_hp(DIPPLIN) == 80


def card_table_hp(card_id):
    from ptcg.cards.tables import card_table
    return card_table[card_id].hp


# ----------------------------------------------------------------------
# 2. Board one: the second ex does not take the last Grass
# ----------------------------------------------------------------------

def test_step092_is_the_board_the_record_lost_on():
    obs = _obs(_STEP092)
    cur = obs["current"]
    mine, op = cur["players"][cur["yourIndex"]], cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 14 and cur["energyAttached"] is False
    assert mine["active"][0]["id"] == OGERPON
    assert [b["id"] for b in mine["bench"]] == [MEGANIUM, MEOWTH, CHIKORITA, OGERPON]
    assert len(mine["bench"][0]["energies"]) == 0, "the one attacker, at zero"
    assert len(mine["bench"][3]["energies"]) == 2, "the second ex, half charged"
    assert sum(1 for c in mine["hand"] if c["id"] == GRASS) == 1, (
        "ONE Grass: this is the reservation's board")
    assert op["active"][0]["id"] == MEGA_KANGASKHAN
    assert [b["id"] for b in op["bench"]] == [CRUSTLE, CRUSTLE], (
        "what comes up after the Kangaskhan dies is a wall")


def test_step092_the_matchup_flags_are_really_on():
    m.agent(_obs(_STEP092))
    assert m.AGENT_STATE.op_is_crustle_deck is True
    assert m.AGENT_STATE.meganium_in_play is True, "Wild Growth doubles the Grass"


def test_step092_the_grass_goes_to_the_meganium_not_to_the_second_ex():
    assert _chosen(_obs(_STEP092)) == ("attach", MEGANIUM), (
        "the recorded game danced it onto the benched Teal Mask Ogerpon ex")


# ----------------------------------------------------------------------
# 3. Board two: the attacker in play beats the basic that is not one
# ----------------------------------------------------------------------

def test_step137_is_the_board_the_record_lost_on():
    obs = _obs(_STEP137)
    cur = obs["current"]
    mine, op = cur["players"][cur["yourIndex"]], cur["players"][1 - cur["yourIndex"]]

    assert cur["turn"] == 20 and cur["energyAttached"] is False
    assert [b["id"] for b in mine["bench"]] == [MEGANIUM, MEOWTH, CHIKORITA, FEZ, APPLIN]
    assert len(mine["bench"][0]["energies"]) == 0
    assert mine["bench"][4]["appearThisTurn"] is True, (
        "the Applin came down this turn: it cannot evolve until the next one")
    assert len(mine["prize"]) == 1, "one prize from winning"
    assert op["active"][0]["id"] == CRUSTLE
    assert TAPU not in [b["id"] for b in mine["bench"]], (
        "their Superb Scissors knocked it out on the previous turn")


def test_step137_the_grass_goes_to_the_meganium_not_to_the_applin():
    assert _chosen(_obs(_STEP137)) == ("attach", MEGANIUM), (
        "the recorded game charged the Applin")


# ----------------------------------------------------------------------
# 4. The controls: what moved is the LAST Grass owed to a body SHORT of
#    its cost against a wall -- not "Meganium is on the bench"
# ----------------------------------------------------------------------

def _wall_board(grass_in_hand=1, meganium_energy=0, op_active=None):
    """Board one, rebuilt: an active Ogerpon ex that covers Myriad Leaf
    Shower, a second Ogerpon ex half charged on the bench, a Meganium, and the
    menu that offers both the dance and the attachment.
    """
    return (Scenario(turn=14, step=92, tac=3, own_prizes=5)
            .my_active(pk(OGERPON, energies=4, fisicas=2))
            .my_bench(pk(MEGANIUM, energies=meganium_energy,
                         fisicas=meganium_energy // 2),
                      pk(OGERPON, energies=2, fisicas=1))
            .my_hand(*([GRASS] * grass_in_hand))
            .op_active(op_active if op_active is not None
                       else pk(CRUSTLE, hp=170, max_hp=170, energies=3))
            .op_bench(pk(CRUSTLE, hp=170, max_hp=170, energies=1))
            .op_zones(hand=3, deck=25, prizes=5)
            .menu_teal_dance_options()
            .build())


def test_control_with_two_grass_in_hand_the_dance_is_free_again():
    """The reservation is about the LAST Grass. With a second one in hand the
    dance no longer costs the Meganium anything -- both are played."""
    assert _chosen(_wall_board(grass_in_hand=2)) == ("ability", OGERPON)


def test_control_a_meganium_that_covers_solar_beam_is_owed_nothing():
    """`_meg_eff < 4` is the whole claim: at four effective it is not short,
    so the Grass goes back to the dance."""
    assert _chosen(_wall_board(meganium_energy=4)) == ("ability", OGERPON)


def test_control_the_ladder_still_puts_tapu_bulu_first():
    obs = (Scenario(turn=14, step=92, tac=3, own_prizes=5)
           .my_active(pk(OGERPON, energies=4, fisicas=2))
           .my_bench(pk(MEGANIUM), pk(TAPU))
           .my_hand(GRASS)
           .op_active(pk(CRUSTLE, hp=170, max_hp=170, energies=3))
           .op_zones(hand=3, deck=25, prizes=5)
           .menu_attach_energy()
           .build())
    assert _chosen(obs) == ("attach", TAPU), (
        "Wood Hammer is 220: nothing outranks it against this wall")


def test_control_the_benched_dipplin_yields_to_the_meganium():
    """The half of the order the user asked for, and the one that changed."""
    obs = (Scenario(turn=14, step=92, tac=3, own_prizes=5)
           .my_active(pk(OGERPON, energies=4, fisicas=2))
           .my_bench(pk(MEGANIUM), pk(DIPPLIN))
           .my_hand(GRASS)
           .op_active(pk(CRUSTLE, hp=170, max_hp=170, energies=3))
           .op_zones(hand=3, deck=25, prizes=5)
           .menu_attach_energy()
           .build())
    assert _chosen(obs) == ("attach", MEGANIUM)


def test_control_the_applin_yields_to_the_meganium():
    obs = (Scenario(turn=14, step=92, tac=3, own_prizes=5)
           .my_active(pk(OGERPON, energies=4, fisicas=2))
           .my_bench(pk(MEGANIUM), pk(APPLIN))
           .my_hand(GRASS)
           .op_active(pk(CRUSTLE, hp=170, max_hp=170, energies=3))
           .op_zones(hand=3, deck=25, prizes=5)
           .menu_attach_energy()
           .build())
    assert _chosen(obs) == ("attach", MEGANIUM)


def test_control_a_wall_our_attack_already_removes_is_not_in_the_way():
    """`_ctm_wall_in_the_way`, first half. A fee is worth paying while it is
    owed: with a charged Tapu Bulu in front of the Crustle the wall is not an
    obstacle, it is a prize, and the ladder goes back to what it was.

    Graded by the rules oracle, this is where the wide reading cost the most
    (-7 pp on `registro_012_crustle_wall_1` turn 10, that exact board).
    """
    obs = (Scenario(turn=10, step=92, tac=3, own_prizes=5)
           .my_active(pk(TAPU, energies=6, fisicas=3))
           .my_bench(pk(MEGANIUM), pk(DIPPLIN))
           .my_hand(GRASS)
           .op_active(pk(CRUSTLE, hp=150, max_hp=150, energies=3))
           .op_zones(hand=3, deck=25, prizes=5)
           .menu_attach_energy()
           .build())
    assert _chosen(obs) == ("attach", DIPPLIN), (
        "Wood Hammer is 220 against a 150 HP wall: it dies this turn")


def test_control_no_wall_in_front_and_nothing_of_ours_removes_the_body():
    """`_ctm_wall_in_the_way`, second half. Their Mega Kangaskhan ex at full HP
    is a body our ex hit perfectly well, and no attack of ours takes it today:
    the wall is turns away and the reading has no business firing (-8 pp on
    `registro_023_crustle_wall_3` turn 6).

    THE NUMBERS ARE THE POINT, and the first version of this control got them
    wrong: Mega Kangaskhan ex is WEAK TO GRASS, so a Myriad Leaf Shower that
    prints 210 arrives as 420 and takes a 400 HP body off the table. At three
    effective and with no energy on their side it is 30+30x3 = 120, doubled to
    240 -- short of the 400, which is what makes this board the control it
    claims to be rather than the one below.
    """
    obs = (Scenario(turn=6, step=92, tac=3, own_prizes=6)
           .my_active(pk(OGERPON, energies=3, fisicas=3))
           .my_bench(pk(MEGANIUM), pk(APPLIN))
           .my_hand(GRASS)
           .op_active(pk(MEGA_KANGASKHAN, hp=400, max_hp=400, energies=0))
           .op_bench(pk(CRUSTLE, hp=150, max_hp=150))
           .op_zones(hand=3, deck=25, prizes=6)
           .menu_attach_energy()
           .build())
    assert _chosen(obs) == ("attach", APPLIN)


def test_control_the_wall_is_what_we_face_next_when_the_body_in_front_falls():
    """The other side of that same half, and it is the record's own board: a
    Mega Kangaskhan ex our active DOES knock out, with the wall behind it."""
    obs = (Scenario(turn=14, step=92, tac=3, own_prizes=5)
           .my_active(pk(OGERPON, energies=4, fisicas=2))
           .my_bench(pk(MEGANIUM), pk(APPLIN))
           .my_hand(GRASS)
           .op_active(pk(MEGA_KANGASKHAN, hp=150, max_hp=300, energies=0))
           .op_bench(pk(CRUSTLE, hp=170, max_hp=170))
           .op_zones(hand=3, deck=25, prizes=5)
           .menu_attach_energy()
           .build())
    assert _chosen(obs) == ("attach", MEGANIUM), (
        "Myriad Leaf Shower does 30+30x4 = 150 into a body at 150: the Crustle "
        "is what stands up next")


def test_control_the_active_dipplin_that_swings_today_keeps_its_priority():
    """A charge that attacks THIS turn was never development: the active
    Dipplin holds `_ctm_charge_active_dipplin` (50000) over the Meganium.
    """
    obs = (Scenario(turn=14, step=92, tac=3, own_prizes=5)
           .my_active(pk(DIPPLIN))
           .my_bench(pk(MEGANIUM), pk(OGERPON, energies=4, fisicas=2))
           .my_hand(GRASS)
           .op_active(pk(CRUSTLE, hp=170, max_hp=170, energies=1))
           .op_zones(hand=3, deck=25, prizes=5)
           .menu_attach_energy()
           .build())
    assert _chosen(obs) == ("attach", DIPPLIN)
