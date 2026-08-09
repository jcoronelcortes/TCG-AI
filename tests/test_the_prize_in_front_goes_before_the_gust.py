"""THE PRIZE IN FRONT, DOWN THE SAME ROUTE: the gust never trades prizes down.

Scenario (user, episode 91016422, `records/registro_006_pasos_085_hasta_104.json`
step 97, turn 6 vs Marnie's Grimmsnarl ex, **LOST**):

    US (seat 1, 5 prizes)                    RIVAL (3 prizes)
    active  Teal Mask Ogerpon ex 190,        active  **Marnie's Grimmsnarl ex
            **2 energies** (Myriad Leaf              310/320, 3 energies**,
            Shower asks for 3 -> mute)               Grass WEAKNESS, 2 prizes
    bench   Bayleef, **Teal Mask Ogerpon ex  bench   Munkidori 1e, Froslass,
            180 with 3 energies**, Meowth            Snorunt, **Marnie's Morgrem
            ex, Fezandipiti ex                       100 HP, 2 energies**,
    hand    Boss's x2, Hydrapple ex x2,              Munkidori 1e
            Bayleef, Xerosic, Dawn, Grass,
            Dipplin, Applin x2

The menu offered the two Boss's, Xerosic, Dawn, the two Applin, RETREAT and END.
The retreat of the active costs 1 and it carries 2 energies, so the whole chain
was payable:

    RETREAT the mute Ogerpon -> promote the one at 3 energies -> Myriad Leaf
    Shower on the Grimmsnarl ex.

Myriad Leaf Shower counts the Energy on BOTH actives
([[ogerpon-myriad-cuenta-ambos-activos]]): 30 + 30 x (3 ours + 3 theirs) = 210,
and the Grimmsnarl ex is Grass-WEAK -> 210 x 2 = **420 >= 310**. It is a Pokemon
ex: **2 prizes**.

What the agent played was **Boss's Orders on the Marnie's Morgrem**, then the
same retreat, the same promotion and the same attack -- against a 100 HP Stage 1.
The turn cashed **1 prize instead of 2**, spent the turn's Supporter, and left
the Grimmsnarl ex alive and fully charged to answer.

THE BUG: THE SAME ASYMMETRY, ONE STEP WIDER
-------------------------------------------
`_boss_prize_rank` grants the BENCH targets the retreat -- when the current
active does not knock them out it re-asks with `_bench_attacker_can_ko`, i.e.
with the body it would promote. For the rival ACTIVE it never does: that reading
is `_bpr_active_can_ko`, always with the body standing in the active spot TODAY.
With our Ogerpon at 2 energies that is 0 damage against everything, so the
2-prize ex in front counted as ZERO and the charged Morgrem (rank 7) won the
comparison with its single prize.

[[remate-ganador-al-activo-tras-retirar]] had already closed exactly this
asymmetry -- but only where the KO WINS the game on the spot
(`_win_ko_active_via_promote`, `prize_count_op(rival active) >= my_prize`). Here
we were at 5 prizes: 2 does not win, the guard did not fire, and the rigged
comparison went through untouched.

THE FIX: the dominance, not the win
-----------------------------------
`_promote_ko_active_prizes` (ptcg/calc/damage.py) answers, in ONE place, how
many prizes the KO on the rival ACTIVE is worth **through the retreat**, and
returns 0 when that route does not exist (the current active already knocks it
out -> then we ATTACK; the retreat cannot be paid; nobody on the bench finishes
it). `_win_ko_active_via_promote` becomes its special case "and those prizes
win", and the general reading feeds the two comparisons that were rigged:
`_bpr_active_prize_dominates` in `_boss_prize_rank` and `_bo_gust_prize_dominated`
in the Supporter valuation (deny-evo, key-bench, the mute-active bench scan and
`_bo_bench_prize_beats_active`).

A gust is a SWAP of the body we knock out, so the rule needs no deck: never pay
the Supporter to swap what is in front for something worth STRICTLY FEWER
prizes when the same retreat already finishes what is in front.

STRICT on purpose. On EQUAL prizes the gust keeps ruling -- that tie is what
every line cut lives on ([[boss-gust-mayor-evolucion-fase2]],
`_bo_pe_outranks_active`): same prize, but it removes the pre-evolution of their
attacker. And against IMMUNE walls (Crustle / Sylveon / Cornerstone) the whole
reading is switched off, because there the gust is preferred deliberately
([[boss-el-chip-al-activo-no-es-un-premio]], `_wall_ko_promote`).
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
from cg.api import AreaType, OptionType, SelectContext, SelectType

BOSS = m.Boss_Orders
OGERPON = m.Teal_Mask_Ogerpon_ex
GRIMMSNARL = 648
MORGREM = m.Marnies_Morgrem

_FIX = (ROOT / "tests" / "fixtures"
        / "marnie_the_prize_in_front_goes_before_the_gust_step97.json")


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


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)


def _types(obs):
    return [o["type"] for o in obs["select"]["option"]]


def _idx_of_type(obs, tipo):
    return _types(obs).index(int(tipo))


def _idx_play_boss(obs):
    yo = obs["current"]["yourIndex"]
    hand = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(m.OptionType.PLAY) and hand[o["index"]]["id"] == BOSS:
            return i
    return -1


# ---------------------------------------------------------------------------
# 1. The board: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_board_is_a_mute_active_with_the_finisher_on_the_bench():
    obs = _fixture()["observation"]
    cur = obs["current"]
    yo = cur["yourIndex"]
    mine, rival = cur["players"][yo], cur["players"][1 - yo]

    assert cur["turn"] == 6 and not cur["supporterPlayed"]

    # Our active is an Ogerpon ex one energy short of Myriad Leaf Shower...
    assert mine["active"][0]["id"] == OGERPON
    assert len(mine["active"][0]["energies"]) == 2
    assert m.ATTACK_ENERGY_REQ[OGERPON] == 3
    # ...and the finisher, already charged, is on the BENCH.
    assert [b["id"] for b in mine["bench"]][1] == OGERPON
    assert len(mine["bench"][1]["energies"]) == 3

    # In front: the 2-prize ex. On their bench, the 1-prize Stage 1.
    assert rival["active"][0]["id"] == GRIMMSNARL
    assert (rival["active"][0]["hp"], len(rival["active"][0]["energies"])) == (310, 3)
    assert rival["bench"][3]["id"] == MORGREM and rival["bench"][3]["hp"] == 100

    # The retreat is payable (cost 1, the active carries 2) and the menu offers
    # both the Boss's and the retreat: the decision is REAL.
    assert m.RETREAT_COST[OGERPON] == 1
    assert _idx_play_boss(obs) >= 0
    assert _idx_of_type(obs, m.OptionType.RETREAT) >= 0


def test_the_two_kos_are_real_and_one_is_worth_double():
    """420 >= 310 on the ex (2 prizes) against 360 >= 100 on the Morgrem (1)."""
    obs = m.to_observation_class(_fixture()["observation"])
    st = obs.current
    mine, rival = st.players[1], st.players[0]
    bench_ogerpon = mine.bench[1]
    grimmsnarl, morgrem = rival.active[0], rival.bench[3]

    def _myriad(target):
        base = m._attacker_base_damage(
            bench_ogerpon.id, target, len(bench_ogerpon.energies),
            grass_scale=0, teal_self_energy=len(bench_ogerpon.energies),
            bench_count=len(mine.bench))
        return m._our_effective_damage(bench_ogerpon, target, base, False, False)

    assert _myriad(grimmsnarl) >= grimmsnarl.hp
    assert _myriad(morgrem) >= morgrem.hp
    assert m.prize_count_op(grimmsnarl) == 2
    assert m.prize_count_op(morgrem) == 1


def test_the_route_prices_the_active_spot_at_two_prizes():
    """`_promote_ko_active_prizes`, read directly on the board."""
    obs = m.to_observation_class(_fixture()["observation"])
    st = obs.current
    assert m._promote_ko_active_prizes(
        st.players[1], st.players[0].active[0],
        True, False, False, 0, len(st.players[1].bench), False, False) == 2


def test_the_route_is_zero_when_the_current_active_already_finishes():
    """The contract of the 0: with the active charged the play is to ATTACK, not
    to retreat -- and `_bo_can_ko_active` is already reading that."""
    fx = _fixture()["observation"]
    fx["current"]["players"][1]["active"][0]["energies"] = [1, 1, 1, 1]
    obs = m.to_observation_class(fx)
    st = obs.current
    assert m._promote_ko_active_prizes(
        st.players[1], st.players[0].active[0],
        True, False, False, 0, len(st.players[1].bench), False, False) == 0


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_boss_is_not_played_the_turn_retreats():
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])

    m.agent(fx["observacion_previa"])
    choice = m.agent(decision)

    assert choice != [_idx_play_boss(decision)], (
        "el gusteo cambia un ex de 2 premios por una Fase 1 de 1: nunca se paga "
        "el Supporter para cobrar menos")


def test_the_promotion_brings_up_the_charged_ogerpon():
    """The other half of the chain: once retreated, the body that comes up is the
    one that finishes -- against the Grimmsnarl ex that the Boss's never moved."""
    fx = _fixture()
    promo = copy.deepcopy(fx["observation"])
    cur = promo["current"]
    yo = cur["yourIndex"]
    mine = cur["players"][yo]
    # The retreat is already paid: one energy less on the body coming out.
    mine["active"][0]["energies"] = [1]
    mine["active"][0]["energyCards"] = mine["active"][0]["energyCards"][:1]
    promo["select"] = {
        "type": int(SelectType.CARD), "context": int(SelectContext.SWITCH),
        "minCount": 1, "maxCount": 1,
        "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"type": int(OptionType.CARD), "area": int(AreaType.BENCH),
                    "index": k, "playerIndex": yo}
                   for k in range(len(mine["bench"]))],
        "deck": None, "contextCard": None, "effect": None,
    }

    m.agent(fx["observacion_previa"])
    chosen = m.agent(promo)
    assert mine["bench"][chosen[0]]["id"] == OGERPON
    assert len(mine["bench"][chosen[0]]["energies"]) == 3


# ---------------------------------------------------------------------------
# 3. The boundaries: the rule is a dominance, not a ban on gusting
# ---------------------------------------------------------------------------

def test_with_equal_prizes_the_gust_survives():
    """A 1-prize body in front: the retreat cashes what the gust cashes, so
    nothing is thrown away and the line cut keeps its reasons."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    active = decision["current"]["players"][0]["active"][0]
    active["id"] = MORGREM
    active["hp"] = active["maxHp"] = 100
    active["preEvolution"] = [{"id": m.Marnies_Impidimp, "playerIndex": 0,
                               "serial": 900}]

    m.agent(fx["observacion_previa"])
    assert m.agent(decision) == [_idx_play_boss(decision)]


def test_without_a_finisher_on_the_bench_the_gust_survives():
    """No route, no dominance: with the benched Ogerpon uncharged the retreat
    finishes nothing and the Boss's is the play again."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    bench_ogerpon = decision["current"]["players"][1]["bench"][1]
    bench_ogerpon["energies"] = [1]
    bench_ogerpon["energyCards"] = bench_ogerpon["energyCards"][:1]

    m.agent(fx["observacion_previa"])
    assert m.agent(decision) == [_idx_play_boss(decision)]


def test_the_rule_is_not_about_the_marnie_line():
    """Deck-agnostic: a Dragapult ex in front, wounded to 200 HP, resolves the
    same way -- and it does so WITHOUT the Grass weakness that made the
    Grimmsnarl's KO easy (Myriad Leaf Shower does 210 flat). Nothing in the rule
    reads a per-deck list: only prizes, HP and whether the retreat is payable."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    active = decision["current"]["players"][0]["active"][0]
    active["id"] = m.Dragapult_ex
    active["maxHp"] = 320
    active["hp"] = 200
    active["preEvolution"] = [{"id": m.Drakloak, "playerIndex": 0, "serial": 901}]

    m.agent(fx["observacion_previa"])
    choice = m.agent(decision)
    assert choice != [_idx_play_boss(decision)], choice
