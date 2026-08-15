"""The promotion buys a SEAT, and the seat comes with its own charging ability.

Scenario (user, `records/registro_004_pasos_038_hasta_047.json` step 47, turn 4,
episode 93166555 vs a Teal Mask Ogerpon ex deck, **LOST**):

    US (6 prizes)                          RIVAL (5 prizes)
    active  -- just knocked out --         active  **Teal Mask Ogerpon ex
    bench   Applin 40, bare                        210/210, FOUR energies**
            Chikorita 70, bare             bench   Teal Mask Ogerpon ex 210, 2e
            **Teal Mask Ogerpon ex 210, 1e**
    hand    Boss's Orders, Meganium, **2 Basic Grass**

Their Ogerpon ex knocked out our Tapu Bulu and the menu asked which body comes
up. The line the board offered closes the exchange on the spot: promote our own
Teal Mask Ogerpon ex, attach one Grass by hand and dance the other. Three energy
is exactly Myriad Leaf Shower's cost, and the attack counts the Energy on BOTH
Active Pokemon ([[ogerpon-myriad-cuenta-ambos-activos]]): 30 + 30 x (3 ours + 4
theirs) = **240 over a 210 HP body**. It is a Pokemon ex -- two prizes -- and the
promotion resolves at the end of THEIR turn, so it happens on ours, before they
can answer.

The agent brought up the **Applin**: 40 HP, bare, one prize handed over for
nothing.

THE BUG: THE ABILITY THE BENCH CANNOT USE
-----------------------------------------
Every projection of a promotion priced the body it brings up with ONE charge,
the manual attachment. *Teal Dance* is the other half and it is the half the
promotion itself creates: "once during your turn, IF THIS POKEMON IS IN THE
ACTIVE SPOT, you may attach a Basic Grass Energy from your hand to it". On the
bench it is dead wood; the seat is what switches it on.

Read with one route the Ogerpon sits at 1/3 with one Grass to pay for two, so it
never reaches Myriad's cost, `_attacker_base_damage` returns 0 by contract below
the requirement, and `_best_promote_card` dropped it from the loop as MUTE. With
no candidate able to attack the menu fell through to ordinary survival points,
where a 40 HP basic that concedes one prize outranks a 210 HP ex that concedes
two -- 392 against 294 -- and the finisher lost the seat to the fodder.

A second, quieter half of the same defect sat two lines below: the Ogerpon
branch of that loop scaled Myriad with the bare `len(energies)` while the cost
gate above it had already projected the attachment. A body could therefore pass
as an attacker and still be priced with the energy it had BEFORE paying for the
attack.

THE FIX (deck-agnostic, one reading for every projection)
---------------------------------------------------------
`_promoted_grass_charges_eff` (`ptcg/calc/energy.py`) is the single answer to
"what can the body we promote put on itself before it swings", and the three
sites that used to add `_grass_attach_unit()` by hand now ask it:
`_best_promote_card`, `_promo_kos_op` and `_promo_damage_to_op`. It names no
card: the bearers come from `ACTIVE_SEAT_GRASS_CHARGER_IDS`, so any deck whose
active-only charger is another Pokemon gets the same sentence.

TWO GUARDS KEEP IT HONEST, and both are pinned below:

  * the charge is claimed only while the body is still MUTE without it
    (`deficit`). An attacker that already reaches its cost is projected exactly
    as before -- spending the rest of the hand on it to make an existing attack
    hit harder is an investment decision, not a promotion one, and projecting it
    flipped a measured board (a six-energy Ogerpon ex taking the seat from the
    Dipplin whose Hydrapple ex kills the same Mega Lopunny ex with no attachment
    at all: `test_the_evolution_that_knocks_out_at_its_boundaries.py`);
  * only on the FORCED promotion (`_forced_ko_promote`). On the voluntary
    retreat the dance is legal too, but that turn is already half spent and the
    Grass in hand may be owed to a play this projection cannot see.

Measured. Golden corpus: 79 decisions compared between the two arms, **1 flip**,
and it is this step 47. Census (`utils/census_the_seat_unlocks_its_charge.py`):
the dance arms a body that was mute 0.23 times per game vs Mega Lucario, 0.20 vs
Dragapult, ~0.00 vs Marnie and Alakazam. Self-play gate
(`utils/gate_the_seat_unlocks_its_charge.py`, paired seeds, n=1000 per deck):
**+0.00 pp** on both high-exposure lists against a control floor of exactly
0.00 -- NEUTRAL in winrate against these bots, which is what an event this rare
looks like. It enters on the census and on the record.
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
from cg.api import AreaType

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "ogerpon_the_seat_unlocks_teal_dance_step47.json")

OGERPON = m.Teal_Mask_Ogerpon_ex   # 210 HP, Myriad Leaf Shower: cost 3
APPLIN = m.Applin                  # 40 HP, the body the agent brought up
CHIKORITA = m.Chikorita
TAPU = m.Tapu_Bulu                 # not a seat charger: the control species
GRASS = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.meganium_in_play = False
    m.forest_in_play = False
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m.op_is_starmie_deck = False
    yield
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _promoted(obs):
    """The card id the agent brings up out of this TO_ACTIVE menu."""
    choice = m.agent(copy.deepcopy(obs))[0]
    option = obs["select"]["option"][choice]
    assert option["area"] == int(AreaType.BENCH), option
    return _mine(obs)["bench"][option["index"]]["id"]


def _keep_grass(obs, n):
    """Leave exactly `n` basic Grass in hand, everything else untouched."""
    hand, kept = _mine(obs)["hand"], 0
    out = []
    for card in hand:
        if card["id"] == GRASS:
            kept += 1
            if kept > n:
                continue
        out.append(card)
    _mine(obs)["hand"] = out
    _mine(obs)["handCount"] = len(out)


# --- the board itself --------------------------------------------------------

def test_the_board_is_the_one_the_record_lost_on():
    """No assertion below means anything if the fixture drifts."""
    obs = _obs()
    bench = [(b["id"], b["hp"], len(b["energies"])) for b in _mine(obs)["bench"]]
    assert bench == [(APPLIN, 40, 0), (CHIKORITA, 70, 0), (OGERPON, 210, 1)]
    assert sum(1 for c in _mine(obs)["hand"] if c["id"] == GRASS) == 2
    rival = obs["current"]["players"][1 - obs["current"]["yourIndex"]]["active"][0]
    assert (rival["id"], rival["hp"], len(rival["energies"])) == (OGERPON, 210, 4)
    # The turn in progress is THEIRS: they have already attached and attacked.
    assert obs["current"]["energyAttached"] is True
    assert not _mine(obs)["active"]


def test_the_arithmetic_of_the_seat_lands_on_the_printed_hp():
    """Three energy is the cost AND the reason the hit kills: 30+30x(3+4)."""
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ[OGERPON] == 3
    ours, theirs = 1, 4

    def myriad(charges):
        return 30 + 30 * (ours + charges + theirs)

    assert myriad(1) == 210          # the manual attachment alone: 2/3, MUTE
    assert myriad(2) == 240 >= 210   # with the dance: at cost, and lethal


def test_the_finisher_comes_up_and_not_the_fodder():
    assert _promoted(_obs()) == OGERPON


def test_without_the_reading_the_fodder_comes_back():
    """The control arm, and the named flag is what makes it measurable."""
    m.PROMOTE_SEAT_UNLOCKS_ITS_CHARGE = False
    try:
        assert _promoted(_obs()) == APPLIN
    finally:
        m.PROMOTE_SEAT_UNLOCKS_ITS_CHARGE = True


def test_one_grass_pays_for_one_charge_and_the_body_stays_mute():
    """The rule never invents energy: both routes come out of the SAME hand.

    With a single Grass the dance and the attachment are the same card, the
    Ogerpon stops at 2 of its 3, and the promotion goes back to what it was.
    """
    obs = _obs()
    _keep_grass(obs, 1)
    assert _promoted(obs) == APPLIN


# --- the helper, at its boundaries -------------------------------------------

def _pk(card_id, energies=0):
    from types import SimpleNamespace
    return SimpleNamespace(id=card_id, energies=[1] * energies,
                           energyCards=[], hp=210, serial=1)


@pytest.mark.parametrize("hand_grass,expected", [(0, 0), (1, 1), (2, 2), (3, 2)])
def test_the_hand_is_the_ceiling_of_both_routes(hand_grass, expected):
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 1), hand_grass, True, deficit=2) == expected


def test_a_body_without_the_ability_only_gets_the_attachment():
    """Deck-agnostic through the SET, not through a species test."""
    assert OGERPON in m.ACTIVE_SEAT_GRASS_CHARGER_IDS
    assert TAPU not in m.ACTIVE_SEAT_GRASS_CHARGER_IDS
    assert m._promoted_grass_charges_eff(
        _pk(TAPU, 1), 3, True, deficit=3) == 1


def test_the_dance_is_not_claimed_by_a_body_that_already_attacks():
    """`deficit` == 0: nothing to unlock, so the projection is the old one."""
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 6), 3, True, deficit=0) == 1


def test_the_ability_lock_takes_the_second_route_and_never_the_first():
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 1), 2, True, abilities_off=True, deficit=2) == 1
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 1), 2, False, abilities_off=True, deficit=2) == 0


def test_the_voluntary_retreat_does_not_claim_the_seat():
    """`seat_unlocks=False` is the scope the SWITCH context passes."""
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 1), 2, True, seat_unlocks=False, deficit=2) == 1


def test_with_the_attachment_spent_the_dance_still_pays():
    """The routes are INDEPENDENT: the ability does not need the attachment.

    On the forced promotion `manual_open` is True whatever today's flag says
    (the body attacks next turn), but the helper must also answer the case where
    it is genuinely closed -- the dance alone still puts one Grass down.
    """
    assert m._promoted_grass_charges_eff(
        _pk(OGERPON, 1), 2, False, deficit=2) == 1
