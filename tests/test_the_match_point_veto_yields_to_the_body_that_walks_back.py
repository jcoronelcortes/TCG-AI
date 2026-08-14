"""THEIR match point: the veto is priced on a reply the body can step out of.

Scenario (`records/registro_006_pasos_067_hasta_077.json`, step 77, turn 6,
episode 92848103, LOST vs Archaludon ex):

    US (6 prizes)                            RIVAL (2 prizes)
    active  -- (their Archaludon ex has      active  Archaludon ex **240**/400
            just knocked out our Ogerpon             (300 + Hero's Cape), 4 {M}
            ex with 220)                             **resists {G} -30**
    bench   Meganium 160, 0/4                bench   Cinderace, 2x Duraludon
            Teal Mask Ogerpon ex 210, **2/3**
            Meowth ex 170, 0
            Dipplin 80, 0
            Tapu Bulu 140, **0/4**, retreat 3
    hand    Teal Mask Ogerpon ex, **Lillie's Determination**

The benched Ogerpon ex is ONE attachment from finishing their Archaludon: with
Meganium's Wild Growth each Grass is worth two, so 2/3 completes to four and
Myriad Leaf Shower is 30+30x(4+4) = 270, which even through the Grass
RESISTANCE is exactly 240 on a 240 HP body -- their main attacker, two prizes,
on OUR turn. The hand holds a Lillie's Determination to go looking for the
Grass, and the Ogerpon carries the energy that pays its own retreat if it does
not come.

`_promote_setup_ko_attacker` saw all of that and named the Ogerpon: route (a),
a draw Supporter in hand with Grass still unseen, +9500. Then
`_mp_price_ends_the_game` overwrote it with -30000 -- their pile is at TWO and
a 2-prize ex their 220 removes IS their last two prizes -- and the front went
to the Tapu Bulu at 8514: four energy needed, none carried, three to retreat.
It could not attack, could not step aside, and the game went with it.

The veto is right about the arithmetic and wrong about WHEN it happens. This
promotion resolves at the END of their turn, so their blow only collects those
two prizes if the Ogerpon is still standing there when it arrives -- and that
is not a fact about the board, it is a choice we still hold. Next turn we
either complete the finisher and take the prize before the reply exists, or the
Grass does not come and we RETREAT (cost 1, and it carries two effective) and
the cheap body takes the front THEN.

That is `PROMOTE_BET_OUTLIVES_MATCH_POINT` / `_promo_bet_walks_back`: the
exemption reaches exactly the one body the selector already named, and only
while it can pay its own retreat and there is a cheaper body to walk back into.

Instruments: golden corpus 1 flip (this step), frozen fifty 0 flips, rules
oracle +14 pp / +1.09 margin over a per-board floor of 1 pp / 0.05.
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "archaludon_promote_walks_back_step77.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
MEGANIUM = m.Meganium
ARCHALUDON = 190                 # Archaludon ex, 300 HP + Hero's Cape, resists {G}


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
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs(nail_the_exit=False, one_energy_short=False):
    """The board of step 77.

    `nail_the_exit` empties the Ogerpon: with no energy on it the retreat is
    not payable, the bet stops being reversible and the veto is right again.

    `one_energy_short` takes ONE energy off their Archaludon, which is what
    separates the two readings of the damage: Myriad Leaf Shower becomes
    30+30x(4+3) = 240, and their Grass RESISTANCE takes it to 210 on a 240 HP
    body. Read with the resistance the selector must not name that Ogerpon at
    all; read the way this block used to -- weakness only -- it promises a
    knockout that lands 30 short.

    There is deliberately NO "take the cheap body away" control here. Pricing
    every benched body at their pile makes `_mp_cheaper_candidate` False, and
    that term is a guard of the SCALED veto itself: with it False the veto never
    fires, the Ogerpon keeps its +9500 with the rule switched off as well, and
    the board would be measuring nothing. See `_promo_bet_walks_back` for where
    that term does bite -- the plain veto one rung up, which asks for a survivor
    instead.
    """
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mine = o["current"]["players"][yo]
    if nail_the_exit:
        for pk in mine["bench"]:
            if pk["id"] == OGERPON:
                pk["energies"] = []
                pk["energyCards"] = []
    if one_energy_short:
        act = o["current"]["players"][1 - yo]["active"][0]
        act["energies"] = act["energies"][:-1]
        act["energyCards"] = act["energyCards"][:-1]
    return o


def _chosen(obs, choice):
    """The benched card behind the chosen option."""
    yo = obs["current"]["yourIndex"]
    opt = obs["select"]["option"][choice[0]]
    return obs["current"]["players"][yo]["bench"][opt["index"]]


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_forced_promotion_at_their_match_point():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine = o["current"]["players"][yo]
    them = o["current"]["players"][1 - yo]

    assert not mine["active"]                   # they knocked our active out
    assert o["select"]["context"] == 4          # promotion menu
    assert them["active"][0]["id"] == ARCHALUDON
    assert them["active"][0]["hp"] == 240

    # THEIR match point against a 2-prize ex: their pile is exactly what the
    # Ogerpon pays, which is the whole premise of the veto this rule lifts.
    assert len(them["prize"]) == 2
    assert len(mine["prize"]) == 6

    # And the hand holds the draw Supporter that keeps route (a) alive.
    assert any(c["id"] == m.Lillie_Determination for c in mine["hand"])


def test_the_completed_ogerpon_finishes_the_archaludon_through_resistance():
    """30+30x(4+4) = 270, minus the Grass resistance = 240 on a 240 HP body."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    them_act = o["current"]["players"][1 - yo]["active"][0]

    # Not weakness -- Archaludon ex is weak to {R} and RESISTS {G}, so this
    # knockout survives a reading the promotion selector does not even do.
    assert m.card_table[ARCHALUDON].weakness != m.card_table[OGERPON].energyType
    assert m.card_table[ARCHALUDON].resistance == m.card_table[OGERPON].energyType

    # Wild Growth: the Meganium on the bench makes each attachment worth two,
    # so 2/3 completes to FOUR.
    assert any(b["id"] == MEGANIUM for b in o["current"]["players"][yo]["bench"])
    assert (30 + 30 * (4 + len(them_act["energies"]))) - 30 >= them_act["hp"]


def test_the_bet_is_reversible_and_the_wall_is_not():
    """The Ogerpon can walk back; the Tapu Bulu cannot even do that."""
    o = _obs()
    mine = o["current"]["players"][o["current"]["yourIndex"]]
    oger = next(b for b in mine["bench"] if b["id"] == OGERPON)
    tapu = next(b for b in mine["bench"] if b["id"] == TAPU)

    assert m.ATTACK_ENERGY_REQ[OGERPON] - len(oger["energies"]) == 1
    assert m.RETREAT_COST[OGERPON] <= len(oger["energies"])   # it keeps its exit
    assert m.ATTACK_ENERGY_REQ[TAPU] - len(tapu["energies"]) == 4
    assert m.RETREAT_COST[TAPU] > len(tapu["energies"])       # nailed down


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_it_promotes_the_finisher_that_can_walk_back_not_the_mute_wall():
    obs = _obs()
    assert _chosen(obs, m.agent(obs))["id"] == OGERPON


# ---------------------------------------------------------------------------
# 3. The controls: take the exit away and the veto is right again
# ---------------------------------------------------------------------------

def test_with_no_energy_to_pay_the_retreat_the_veto_stands():
    """Nailed down, the Ogerpon really does hand them the game: wall instead."""
    obs = _obs(nail_the_exit=True)
    assert _chosen(obs, m.agent(obs))["id"] != OGERPON


def test_a_knockout_that_lands_short_through_resistance_is_not_a_knockout():
    """One energy less on their side and Myriad is 240 - 30 = 210 on 240 HP.

    The selector reads the damage through `_our_effective_damage` now, so the
    Ogerpon stops being a finisher and the exemption never opens. Read the way
    that block used to -- weakness doubling and nothing else -- 240 >= 240 and
    it would promise a knockout that lands 30 short.
    """
    obs = _obs(one_energy_short=True)
    them_act = obs["current"]["players"][1 - obs["current"]["yourIndex"]]["active"][0]
    assert (30 + 30 * (4 + len(them_act["energies"]))) >= them_act["hp"]   # blind
    assert (30 + 30 * (4 + len(them_act["energies"]))) - 30 < them_act["hp"]  # resisted
    assert _chosen(obs, m.agent(obs))["id"] != OGERPON


def test_the_switch_is_what_decides_it():
    """With `PROMOTE_BET_OUTLIVES_MATCH_POINT` off, the wall comes back."""
    obs = _obs()
    m.PROMOTE_BET_OUTLIVES_MATCH_POINT = False
    try:
        assert _chosen(obs, m.agent(obs))["id"] == TAPU
    finally:
        m.PROMOTE_BET_OUTLIVES_MATCH_POINT = True


# ---------------------------------------------------------------------------
# 4. The exemption is one body wide
# ---------------------------------------------------------------------------

def test_the_other_two_prize_ex_is_still_vetoed():
    """The Meowth ex pays their pile too and has no finisher's upside."""
    obs = _obs()
    assert _chosen(obs, m.agent(obs))["id"] != m.Meowth_ex
