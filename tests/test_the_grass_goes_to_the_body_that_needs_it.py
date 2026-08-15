"""Three ways of ending a turn with nothing ready for the next one.

THE BOARD (user, `records/registro_005_pasos_061_hasta_077.json`, episode
93173834, turn 5 vs Marnie's Grimmsnarl -- LOST). Their Grimmsnarl ex had just
hit our Teal Mask Ogerpon ex for 180 and left it at 30 of 210. Our attack that
turn knocks the Grimmsnarl out for two prizes, so everything else the turn does
is buying the NEXT one -- the turn after which our 30 HP active is not coming
back:

    US                                          RIVAL
    active  Teal Mask Ogerpon ex 30/210         active  Grimmsnarl ex 320/320
            3 Grass -- it KNOCKS OUT this turn          5 energy
    bench   Dipplin 1 Grass                     bench   Munkidori, Snorunt,
            Bayleef 0   (evolved THIS turn)             Munkidori, Impidimp
            Teal Mask Ogerpon ex 2 Grass
            Applin 0
    hand    Dawn, a Grass, Fezandipiti ex...

Three decisions of that one turn, and all three end it with less on the board
than the cards in hand could have put there:

  * STEP 70, the Grass. It went to the Bayleef. The second Ogerpon ex sat at 2
    of the 3 that Myriad Leaf Shower costs -- one card from being the attacker
    that takes the front the moment the body in front dies -- and the
    development band that decides these attachments only looked at bodies with
    ZERO energy, so it never saw it: it fell to the generic tail at 8250 and
    lost to a Bayleef, which is worth 25000 for being empty and cannot attack at
    any amount of energy. "Empty" was standing in for "still needs it".

  * STEP 74, Dawn's Stage 2. Dawn searches out a Basic, a Stage 1 and a Stage 2;
    for the Stage 2 the board offered a Meganium (Bayleef on the bench, 1000)
    and a Hydrapple ex (Dipplin on the bench, 980), both scored under the name
    `immediate_evo`. Only one of them was immediate: that Bayleef had been
    evolved out of a Chikorita on THIS VERY TURN, so nothing could go on top of
    it until tomorrow. The agent took the Meganium, it slept in hand, and a 330
    HP Hydrapple ex that could have been on the board that same turn was not.

  * STEP 75, the last seat. Bench of four with one seat free, Fezandipiti ex in
    hand, and an active that was not surviving the turn. Flip the Script reads
    OUR LAST turn, so `ko_last_turn` was false and every rung priced the card as
    a 2-prize body with a dead ability: `SCORE_VETO`. The agent attacked, they
    knocked the Ogerpon out, and the ability that would have drawn 3 on the turn
    we needed rebuilding was still in hand -- with the seat it wanted gone.

The three fixes are named switches (`CHARGE_THE_BODY_THAT_NEEDS_IT`,
`DAWN_SEAT_WAITS_A_TURN`, `FEZ_ABILITY_BEFORE_THE_KNOCKOUT`) so the census, the
gate and the corpus can put exactly one difference between their arms.

FLIP DIFF over the frozen corpus (3 580 decisions, 50 games): ONE, and it is
this same reading on another board -- `registro_003_alakazam_3` turn 4, a Grass
that went to a fresh Applin while a benched Ogerpon ex sat at 2 of 3. The Dawn
ceiling and the Fezandipiti seat flip nothing there at all.
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

_FIX_GRASS = (ROOT / "tests" / "fixtures"
              / "marnie_step070_the_grass_goes_to_the_body_that_needs_it.json")
_FIX_DAWN = (ROOT / "tests" / "fixtures"
             / "marnie_step074_the_seat_that_is_not_free_until_tomorrow.json")
_FIX_FEZ = (ROOT / "tests" / "fixtures"
            / "marnie_step075_the_ability_before_the_knockout.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
BAYLEEF = m.Bayleef
CHIKORITA = m.Chikorita
APPLIN = m.Applin
DIPPLIN = m.Dipplin
MEGANIUM = m.Meganium
HYDRAPPLE = m.Hydrapple_ex
FEZ = m.Fezandipiti_ex


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.AGENT_STATE.ko_last_turn = False
    m.AGENT_STATE._field_at_turn_start = None
    yield
    m._init_cards_tracking()


def _obs(path):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _opponent(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _chosen(obs):
    return obs["select"]["option"][m.agent(obs)[0]]


def _turn_start_of_step_74():
    """The field as turn 5 STARTED, which is the whole point of the Dawn rung.

    The fixture is one menu, and a menu replayed from cold takes its own board
    as the start of the turn -- with that snapshot the Bayleef looks like a body
    that has been sitting there, which is exactly the reading the rule exists to
    correct. The turn really started with the CHIKORITA that Bayleef was evolved
    out of on step 62, so the snapshot has to say so.
    """
    return {OGERPON: 2, DIPPLIN: 1, CHIKORITA: 1}


# ---------------------------------------------------------------------------
# 1. The Grass goes to the body that needs it
# ---------------------------------------------------------------------------

def test_step70_the_board_is_a_half_built_attacker_among_empty_bodies():
    """Without this the test measures nothing: the scenario itself."""
    obs = _obs(_FIX_GRASS)
    mine, opponent = _mine(obs), _opponent(obs)

    # The active takes the prize this turn, so the Grass is pure development...
    assert mine["active"][0]["id"] == OGERPON
    assert len(mine["active"][0]["energies"]) == 3
    assert opponent["active"][0]["hp"] == 320
    assert int(m.OptionType.ATTACK) in {o["type"] for o in obs["select"]["option"]}

    # ...and the bench holds ONE body a single Grass short of its cost next to
    # two the deck does not attack with (their chip attacks put them in
    # `ATTACK_ENERGY_REQ`; one energy does not make attackers of them).
    bench = {p["id"]: len(p["energies"]) for p in mine["bench"]}
    assert bench == {DIPPLIN: 1, BAYLEEF: 0, OGERPON: 2, APPLIN: 0}
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ[OGERPON] == 3
    assert BAYLEEF not in m.MAIN_ATTACKERS and APPLIN not in m.MAIN_ATTACKERS


def test_step70_the_grass_finishes_the_benched_ogerpon():
    obs = _obs(_FIX_GRASS)
    chosen = _chosen(obs)

    assert chosen["type"] == int(m.OptionType.ATTACH), (
        f"se esperaba el adjunte del turno; salio {chosen}")
    assert chosen["inPlayArea"] == int(m.AreaType.BENCH)
    target = _mine(obs)["bench"][chosen["inPlayIndex"]]
    assert target["id"] == OGERPON and len(target["energies"]) == 2, (
        "el Grass va al cuerpo que ESTE adjunte deja a su coste, no al que "
        f"esta vacio; fue a {target['id']} con {len(target['energies'])}")


def test_step70_a_body_already_at_its_cost_is_still_not_overcharged():
    """The control of the same reading: the band admits the body that NEEDS the
    energy, not any body that happens to carry some."""
    obs = _obs(_FIX_GRASS)
    for p in _mine(obs)["bench"]:
        if p["id"] == OGERPON:                 # already at Myriad's three
            p["energies"] = [1, 1, 1]
            p["energyCards"] = p["energyCards"] + p["energyCards"][:1]
    chosen = _chosen(obs)
    if chosen["type"] == int(m.OptionType.ATTACH):
        target = _mine(obs)["bench"][chosen["inPlayIndex"]]
        assert not (target["id"] == OGERPON and len(target["energies"]) >= 3), (
            "un cuerpo que YA puede atacar no recibe el adjunte de desarrollo")


# ---------------------------------------------------------------------------
# 2. The seat that is not free until tomorrow
# ---------------------------------------------------------------------------

def test_step74_the_menu_offers_both_stage_twos():
    obs = _obs(_FIX_DAWN)
    assert obs["select"]["effect"]["id"] == m.Dawn
    offered = {obs["select"]["deck"][o["index"]]["id"]
               for o in obs["select"]["option"]}
    assert offered == {MEGANIUM, HYDRAPPLE}
    # Both pre-evolutions ARE on the bench -- which is all `field_counts` sees.
    bench = {p["id"] for p in _mine(obs)["bench"]}
    assert BAYLEEF in bench and DIPPLIN in bench


def test_step74_dawn_takes_the_stage_two_that_can_be_worn_today():
    obs = _obs(_FIX_DAWN)
    m.AGENT_STATE._field_at_turn_start = _turn_start_of_step_74()
    chosen = _chosen(obs)
    picked = obs["select"]["deck"][chosen["index"]]["id"]
    assert picked == HYDRAPPLE, (
        "con el Bayleef bajado ESTE turno, el Meganium es una evolucion de "
        f"manana y no debe ganarle al Hydrapple ex de hoy; eligio {picked}")


def test_step74_with_the_seat_free_since_before_the_turn_meganium_wins_again():
    """The control: the rule is about WHEN the body can be worn, nothing else.
    With the Bayleef already in play when the turn started, the table's own
    order (Meganium 1000 over Hydrapple ex 980) stands untouched."""
    obs = _obs(_FIX_DAWN)
    start = _turn_start_of_step_74()
    start.pop(CHIKORITA)
    start[BAYLEEF] = 1
    m.AGENT_STATE._field_at_turn_start = start
    chosen = _chosen(obs)
    assert obs["select"]["deck"][chosen["index"]]["id"] == MEGANIUM


# ---------------------------------------------------------------------------
# 3. The ability that pays after their knockout
# ---------------------------------------------------------------------------

def test_step75_the_turn_is_down_to_the_last_seat_and_the_attack():
    obs = _obs(_FIX_FEZ)
    mine = _mine(obs)
    assert len(mine["bench"]) == 4 and mine["benchMax"] == 5
    assert FEZ in {c["id"] for c in mine["hand"]}
    assert not m.AGENT_STATE.ko_last_turn        # Flip the Script is asleep
    types = {o["type"] for o in obs["select"]["option"]}
    assert types == {int(m.OptionType.PLAY), int(m.OptionType.ATTACK), 12, 14}
    # The body in front does not survive their turn: that is what wakes it up.
    assert mine["active"][0]["hp"] == 30


def test_step75_the_body_takes_the_seat_before_the_knockout_lands():
    obs = _obs(_FIX_FEZ)
    chosen = _chosen(obs)
    assert chosen["type"] == int(m.OptionType.PLAY), (
        f"el asiento libre se ocupa antes de cerrar el turno; salio {chosen}")
    assert _mine(obs)["hand"][chosen["index"]]["id"] == FEZ


def test_step75_with_the_active_out_of_danger_the_turn_just_attacks():
    """The control: the seat is bought by the knockout that is COMING, not by
    the free slot. Heal the active and the same menu attacks, as it did."""
    obs = _obs(_FIX_FEZ)
    active = _mine(obs)["active"][0]
    active["hp"] = active["maxHp"]
    chosen = _chosen(obs)
    assert chosen["type"] == int(m.OptionType.ATTACK), (
        f"sin la amenaza no hay habilidad que despertar; salio {chosen}")
