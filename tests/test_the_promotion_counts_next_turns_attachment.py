"""THE ATTACHMENT THE PROMOTION COUNTS IS **OURS**, NOT THIS TURN'S.

Scenario (user, episode 90898627, `records/registro_007_pasos_111_hasta_135.json`
step 135, turn 7 vs Marnie's Grimmsnarl ex, **LOST**):

    US (seat 1, 2 prizes)                    RIVAL (2 prizes)
    active  -- (just Knocked Out)            active  **Marnie's Grimmsnarl ex
    bench   Fezandipiti ex 170, BARE                 320/320, 3 energies**,
            **Teal Mask Ogerpon ex 170,              Grass WEAKNESS, 2 prizes
            2 energies** (x2)                bench   five bodies
            Tapu Bulu 140, **1 energy**
    hand    **Basic Grass**, Boss's Orders

Their Grimmsnarl ex knocked out our Hydrapple ex and, with the splash, the
Meganium behind it: Wild Growth died with it, so every Grass on our board went
back to providing one and both Ogerpon ex read 2 of Myriad Leaf Shower's 3.

The line the board offered closed the game on the spot: promote an Ogerpon ex,
attach the Grass we hold and swing Myriad Leaf Shower. It counts the Energy on
BOTH actives ([[ogerpon-myriad-cuenta-ambos-activos]]): 30 + 30 x (3 ours + 3
theirs) = 210, doubled by the Darkness weakness = **420 on a 320 HP body**. It is
a Pokemon ex: **2 prizes**, exactly the two we had left, and it happens on OUR
turn -- the promotion is resolved at the end of THEIRS -- so their reply never
exists.

The agent promoted the **Tapu Bulu**: four energies of cost with one attached, so
it neither attacked nor could retreat (cost 3), and the turn was handed back.

THE BUG: A FLAG ABOUT THE OTHER PLAYER'S TURN
--------------------------------------------
Every rule that could have promoted the Ogerpon was overruled by the same
-30000, `PROMO_MATCH_POINT_VETO`: at their match point a 2-prize body their blow
removes (180 through a wounded 170 HP Ogerpon) IS the game. Both veto sites carry
the one exemption written for this board -- the body that KNOCKS OUT and with
that closes OUR count first -- and both ask `_promo_kos_op` for it.

It answered NO, and the reason was arithmetic, not strategic:

    if not state.energyAttached and hand_counts.get(Basic_Grass_Energy, 0) >= 1:
        _pe += _grass_attach_unit()

`state.energyAttached` belongs to the turn IN PROGRESS, and the turn in progress
is THEIRS: they had already attached and attacked with it. The body we are
choosing does not attack today, it attacks on our next turn, which arrives with
its attachment intact. Read at 2 energy the Ogerpon does not reach Myriad's cost,
`_attacker_base_damage` returns 0 by contract, and a 420-damage finisher was
priced at zero -- so the veto took it, the other ex with it, and the only body
left standing in the menu was the mute Tapu Bulu.

`_best_promote_card` DID see that finisher: its own reading of the same question
(`_prom_can_attach`) never looks at the flag, because it is guarded by
`_forced_ko_promote`. The two halves of one question disagreed and the half with
the veto behind it was the blind one.

THE FIX (deck-agnostic, one reading for both projections)
--------------------------------------------------------
`_promo_attach_open`: the flag is believed only while there IS a body in the
active spot -- the VOLUNTARY retreat (SWITCH), which really does spend today's
attachment on the body it brings up. With the spot EMPTY the promotion is forced,
what is being projected is next turn, and the attachment counts. It is the same
sentence `_ref_can_attach` already carries (`not state.energyAttached or
_ref_forced_promote`) and the one `_prom_can_attach` uses. It names no card and
no matchup: any body one attachment away from a lethal attack is now visible to
the exemptions, in any deck.

Measured: the golden corpus was RED on exactly this decision (snapshot: Teal Mask
Ogerpon ex; current: Tapu Bulu) and goes green with the fix -- it is the only
historical decision that moves. Suite green.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import AreaType, OptionType
from state_builder import G, Scenario, pk

OGERPON = m.Teal_Mask_Ogerpon_ex     # 210 HP, Myriad Leaf Shower: cost 3
TAPU = m.Tapu_Bulu                   # 140 HP, 1 prize, cost 4, retreat 3
FEZ = m.Fezandipiti_ex               # 210 HP, bare
HYDRAPPLE = m.Hydrapple_ex           # 330 HP: the tank of the SWITCH control
GRIMMSNARL = 648                     # Marnie's Grimmsnarl ex, 320 HP, Grass-weak
MYRIAD_LEAF_SHOWER = 120

_FIX = (ROOT / "tests" / "fixtures"
        / "marnie_the_finisher_attaches_next_turn_step135.json")


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
    with open(_FIX, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _promoted(obs):
    """The bench card the agent brings up to the active spot."""
    choice = m.agent(copy.deepcopy(obs))
    option = obs["select"]["option"][choice[0]]
    assert option["area"] == int(AreaType.BENCH), option
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["bench"][option["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. The board: without these numbers the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_a_forced_promotion_at_their_match_point():
    obs = _obs()
    cur = obs["current"]
    yo = cur["yourIndex"]
    mine, rival = cur["players"][yo], cur["players"][1 - yo]

    # The active spot is EMPTY: the promotion is forced, and it is resolved
    # inside THEIR turn -- which is why the flag below lies.
    assert mine["active"] == []
    assert cur["energyAttached"] is True

    # Two Ogerpon ex one attachment short of Myriad Leaf Shower, and the Grass
    # that completes them in hand.
    ogerpon = [b for b in mine["bench"] if b["id"] == OGERPON]
    assert len(ogerpon) == 2
    assert all(len(b["energies"]) == 2 and b["hp"] == 170 for b in ogerpon)
    assert m.ATTACK_ENERGY_REQ[OGERPON] == 3
    assert [c["id"] for c in mine["hand"]].count(m.Basic_Grass_Energy) == 1

    # The mute alternative: 1 of the 4 energies it needs, retreat 3.
    tapu = [b for b in mine["bench"] if b["id"] == TAPU][0]
    assert len(tapu["energies"]) == 1
    assert m.ATTACK_ENERGY_REQ[TAPU] == 4 and m.RETREAT_COST[TAPU] == 3

    # Both piles at TWO: the 2-prize ex in front is the whole game, in both
    # directions.
    assert len(mine["prize"]) == 2 and len(rival["prize"]) == 2
    assert rival["active"][0]["id"] == GRIMMSNARL
    assert (rival["active"][0]["hp"], len(rival["active"][0]["energies"])) == (320, 3)


def test_the_finisher_only_exists_with_next_turns_attachment():
    """2 energies -> 0 by contract (it does not reach the cost); 3 -> 420 on a
    320 HP body, and those are the last two prizes."""
    obs = m.to_observation_class(_obs())
    st = obs.current
    mine, rival = st.players[1], st.players[0]
    ogerpon = mine.bench[1]
    grimmsnarl = rival.active[0]

    def _myriad(energy):
        base = m._attacker_base_damage(
            ogerpon.id, grimmsnarl, energy, grass_scale=0,
            teal_self_energy=energy, bench_count=len(mine.bench) - 1)
        return m._our_effective_damage(ogerpon, grimmsnarl, base, False, False)

    assert _myriad(2) == 0                      # blind reading: a mute body
    assert _myriad(3) == 420 >= grimmsnarl.hp   # with the Grass we hold
    assert m.prize_count_op(grimmsnarl) == 2 == len(mine.prize)


# ---------------------------------------------------------------------------
# 2. The decision of the record
# ---------------------------------------------------------------------------

def test_the_promotion_is_the_finisher_and_not_the_mute_body():
    assert _promoted(_obs()) == OGERPON, (
        "sube el Ogerpon ex que remata el turno siguiente, no el Tapu Bulu que "
        "no ataca ni puede retirarse")


# ---------------------------------------------------------------------------
# 3. Scope, on synthetic boards
# ---------------------------------------------------------------------------
#
# The same shape as step 135, rebuilt so each gate can be switched off on its
# own. `promote_from_bench()` keeps an active (the builder demands one); the
# forced promotion after a KO has an EMPTY spot, which is what
# `_forced_ko_promote` reads, so it is emptied here exactly as the record shows
# it.

def _ko_promotion(hand=(m.Basic_Grass_Energy, m.Boss_Orders), energy_played=True):
    obs = (Scenario(turn=7, step=135, tac=25, own_prizes=2,
                    supporter_played=False, energy_played=energy_played)
           .my_active(pk(HYDRAPPLE))
           .my_bench(pk(FEZ, hp=170),
                     pk(OGERPON, hp=170, energies=[G, G], fisicas=2),
                     pk(OGERPON, hp=170, energies=[G, G], fisicas=2),
                     pk(TAPU, energies=[G], fisicas=1))
           .op_active(pk(GRIMMSNARL, energies=[G, G, G], fisicas=3))
           .op_bench(pk(m.Munkidori), pk(m.Froslass))
           .op_zones(hand=5, deck=22, prizes=2)
           .my_hand(*hand)
           .deck()
           .rest_to_discard()
           .promote_from_bench()
           .build())
    obs["current"]["players"][0]["active"] = []
    return obs


def test_the_synthetic_board_reproduces_the_promotion():
    assert _promoted(_ko_promotion()) == OGERPON


def test_without_the_grass_in_hand_nothing_is_invented():
    """The fix credits an attachment we HOLD, not an imaginary one: with no Grass
    in hand the Ogerpon stays mute, the veto stands and the cheap body takes the
    front."""
    assert _promoted(_ko_promotion(hand=(m.Boss_Orders,))) == TAPU


def test_with_the_attachment_still_unspent_it_behaves_as_it_always_did():
    """The other side of the flag: when it really says "available" the reading
    never changed."""
    assert _promoted(_ko_promotion(energy_played=False)) == OGERPON


def test_the_voluntary_retreat_still_believes_todays_flag():
    """SCOPE. The SWITCH context is our OWN turn with a body in the active spot:
    there `energyAttached` is the truth -- the attachment is spent and the body
    that comes up will NOT be completed today. The exemption must not leak into
    it."""
    obs = (Scenario(turn=8, step=140, tac=6, own_prizes=2,
                    supporter_played=False, energy_played=True)
           .my_active(pk(TAPU, energies=[G], fisicas=1))
           .my_bench(pk(OGERPON, hp=170, energies=[G, G], fisicas=2),
                     pk(FEZ, hp=170),
                     pk(HYDRAPPLE))
           .op_active(pk(GRIMMSNARL, energies=[G, G, G], fisicas=3))
           .op_bench(pk(m.Munkidori))
           .op_zones(hand=5, deck=22, prizes=2)
           .my_hand(m.Basic_Grass_Energy, m.Boss_Orders)
           .deck()
           .rest_to_discard()
           .promote_after_retreat(fee=0)
           .build())
    assert _promoted(obs) != OGERPON, (
        "en la retirada voluntaria el adjunte de HOY ya se gasto: el cuerpo que "
        "sube no se completa este turno")


# ---------------------------------------------------------------------------
# 4. The turn the promotion opens
# ---------------------------------------------------------------------------

def _our_turn(active_energies, energy_played, with_attachment, with_attack):
    hand = ([m.Basic_Grass_Energy, m.Boss_Orders] if with_attachment
            else [m.Boss_Orders])
    return (Scenario(turn=8, step=140, tac=1, own_prizes=2,
                     supporter_played=False, energy_played=energy_played)
            .my_active(pk(OGERPON, hp=170, energies=[G] * active_energies,
                          fisicas=active_energies))
            .my_bench(pk(FEZ, hp=170),
                      pk(OGERPON, hp=170, energies=[G, G], fisicas=2),
                      pk(TAPU, energies=[G], fisicas=1))
            .op_active(pk(GRIMMSNARL, energies=[G, G, G], fisicas=3))
            .op_bench(pk(m.Munkidori), pk(m.Froslass))
            .op_zones(hand=5, deck=22, prizes=2)
            .my_hand(*hand)
            .deck()
            .rest_to_discard()
            .menu_hand(with_attachment=with_attachment, with_attack=with_attack)
            .build())


def test_next_turn_the_grass_goes_on_the_promoted_body():
    obs = _our_turn(2, energy_played=False, with_attachment=True, with_attack=True)
    choice = m.agent(copy.deepcopy(obs))
    option = obs["select"]["option"][choice[0]]
    assert option["type"] == int(OptionType.ATTACH), option
    assert option["inPlayArea"] == int(AreaType.ACTIVE), option


def test_and_then_it_swings_the_attack_that_closes_the_game():
    obs = _our_turn(3, energy_played=True, with_attachment=False, with_attack=True)
    choice = m.agent(copy.deepcopy(obs))
    option = obs["select"]["option"][choice[0]]
    assert option["type"] == int(OptionType.ATTACK), option
    assert option["attackId"] == MYRIAD_LEAF_SHOWER
