"""THE RETREAT IS NOT ONLY A COST: it is what puts the energy in the discard.

Scenario (user, episode 89640089 -- registro_004 step 45, vs Mega Lucario ex,
LOST):

    US (seat 0)                             RIVAL
    active  Teal Mask Ogerpon ex  80/210    active  Solrock 110 (2e)   weak {G}
            (1 physical Grass = 2 eff.)     bench   Lunatone 110       weak {G}
    bench   Applin 40 (1e),                         Makuhita 80, Solrock 110,
            Teal Mask Ogerpon ex 210 (1e),          Riolu 80, Riolu 80
            Meganium 160 (0e)              hand    8 cards, two Mega Lucario ex
    hand    Boss's Orders, Unfair Stamp,
            Night Stretcher, Bayleef,
            Forest of Vitality, Xerosic's
    discard Poke Pad, Lillie's, Bug Catching Set   <- NO energy
    prizes  6 - 6

Myriad Leaf Shower costs three energies. Our active carries two effective and
the fresh Ogerpon on the bench another two: NOBODY could attack, there was no
Grass in hand and no Grass in the discard, so the Night Stretcher was not even
offered by the simulator. The agent evolved the Meganium line, spent Boss's
Orders on a gust with no attack behind it and ended the turn. The board it
handed over: an ex at 80 HP in front of two Mega Lucario ex in hand.

THE LINE IT DID NOT SEE
-----------------------
    RETREAT -> NIGHT STRETCHER -> TEAL DANCE -> ATTACK

The retreat is what makes the rest legal. Paying it discards the Grass off the
retreating Ogerpon -- and THAT is the card the Stretcher brings back for Teal
Dance to attach to the promoted one: two physical Grass = four effective with
Meganium's Wild Growth, one more than Myriad needs. 30 + 30 x (4 + 2) = 210,
doubled by the {G} weakness of the Solrock family. Every body on that bench
dies. And the wounded ex is not hidden by the retreat, it is HEALED: on the
bench the Tera ability prevents all damage done to it.

Driven through the real simulator with `cg.api.search_begin/search_step` from
this same state, the fixed agent plays exactly that line and the attack log
reads `-300` on the Lunatone: one prize, from a turn that took none.

THE BUG: A DEFINITION, NOT A MISSING RULE
-----------------------------------------
"Available energy" meant `Basic_Grass_Energy in hand and not energyAttached`,
copied into four scorers. Energy sitting in the discard with a Stretcher in hand
is exactly as available -- and so is the energy the retreat under evaluation is
about to put there. Two consequences on this board:

  * `ptcg/turn/options/retreat.py`, `_has_ready_bench`: it only counted the
    energy a benched body ALREADY carried, so nobody was "ready", and the
    retreat scored SCORE_VETO. Step 47 is the proof that this was not a
    question of ordering: with the Supporter already spent and the Lunatone
    gusted into the Active Spot, the retreat still opened a free prize and the
    agent chose END.
  * `ptcg/turn/game_plan.py`, `_prizes_we_can_take`: it left retreat pivots out
    entirely, so `prizes_today` was 0 and the turn read DEVELOP -- which is what
    let the Supporter be spent before anyone asked what the turn was for.

THE FIX: `_reachable_grass_for` (ptcg/calc/energy.py)
-----------------------------------------------------
One primitive answering "how much Grass can still reach THIS body this turn",
over three sources (hand, discard through Night Stretcher, and the retreat's own
payment) capped by the routes that reach that body (the manual attachment,
Ripening Charge, and Teal Dance for the Ogerpon itself). The four scorers now
read the same answer, and the plan gained the PROMOTE route in `prizes_today`.

BOUNDARY: the reachable path does NOT fire on our first turn going first --
nobody may attack then, so promoting a body that "becomes ready" only throws an
energy away. Guarded in the retreat scorer and watched by
tests/test_state_builder.py::test_abomasnow_first_turn_going_first_it_does_not_sacrifice.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from ptcg.calc.energy import (_reachable_grass_for, _retreat_grass_to_discard,
                              _retreat_payable)
from ptcg.turn import game_plan as gp

OGERPON = m.Teal_Mask_Ogerpon_ex
GRASS = m.Basic_Grass_Energy
NS = m.Night_Stretcher
LUNATONE = 675
SOLROCK = 676

_FIX45 = ROOT / "tests" / "fixtures" / \
    "mega_lucario_t4_the_retreat_feeds_the_stretcher_step45.json"
_FIX47 = ROOT / "tests" / "fixtures" / \
    "mega_lucario_t4_the_retreat_feeds_the_stretcher_step47.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _fixture(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _counts(cards):
    out = {}
    for c in cards or []:
        out[c.id] = out.get(c.id, 0) + 1
    return out


def _sides(obs):
    st = m.to_observation_class(obs).current
    return st, st.players[st.yourIndex], st.players[1 - st.yourIndex]


# ---------------------------------------------------------------------------
# The board: the Stretcher had NOTHING to fetch until the retreat was paid
# ---------------------------------------------------------------------------

def test_the_discard_holds_no_energy_before_retreating():
    _, mine, _ = _sides(_fixture(_FIX45))

    assert not any(c.id == GRASS for c in mine.discard), (
        "la premisa del escenario: sin energia en el descarte la Night "
        "Stretcher no tiene nada que recuperar")
    assert not any(c.id == GRASS for c in mine.hand), "ni en la mano"
    assert any(c.id == NS for c in mine.hand), "la Night Stretcher SI estaba"


def test_nobody_could_attack_with_the_energy_already_on_the_board():
    _, mine, _ = _sides(_fixture(_FIX45))
    req = m.AGENT_STATE.ATTACK_ENERGY_REQ[OGERPON]

    assert len(mine.active[0].energies) < req, "el activo, a una energia"
    bench = [p for p in mine.bench if p is not None and p.id == OGERPON]
    assert bench and len(bench[0].energies) < req, "y el de banca, tambien"


# ---------------------------------------------------------------------------
# The primitive: the retreat's own payment is what unlocks the charge
# ---------------------------------------------------------------------------

def test_the_retreat_pays_one_grass_into_the_discard():
    obs = _fixture(_FIX45)
    m.agent(obs)
    _, mine, _ = _sides(obs)
    active = mine.active[0]

    assert _retreat_payable(active), "la retirada es pagable con lo que lleva"
    assert _retreat_grass_to_discard(active) == 1, (
        "una carta de Planta entera va al descarte, no 'una unidad'")


def test_the_bench_ogerpon_is_only_chargeable_thanks_to_that_payment():
    obs = _fixture(_FIX45)
    m.agent(obs)
    state, mine, _ = _sides(obs)
    hand_counts = _counts(mine.hand)
    field_counts = _counts([p for p in (mine.active + mine.bench)
                            if p is not None])
    bench = [p for p in mine.bench if p is not None and p.id == OGERPON][0]

    sin_retirada = _reachable_grass_for(bench, state, mine, hand_counts,
                                        field_counts)
    con_retirada = _reachable_grass_for(
        bench, state, mine, hand_counts, field_counts,
        extra_discard_grass=_retreat_grass_to_discard(mine.active[0]))

    assert sin_retirada == 0, (
        "sin retirar no hay energia alcanzable: ni mano ni descarte")
    assert con_retirada == 1, (
        "la Planta que paga la retirada vuelve con la Stretcher y la pega el "
        "Teal Dance")


def test_with_no_stretcher_in_hand_the_retreat_unlocks_nothing():
    """The other half of the primitive: the discard is only reachable THROUGH a
    recovery card. Without it the old reading was the right one."""
    obs = _fixture(_FIX45)
    m.agent(obs)
    state, mine, _ = _sides(obs)
    hand_counts = _counts(mine.hand)
    hand_counts.pop(NS)
    field_counts = _counts([p for p in (mine.active + mine.bench)
                            if p is not None])
    bench = [p for p in mine.bench if p is not None and p.id == OGERPON][0]

    assert _reachable_grass_for(
        bench, state, mine, hand_counts, field_counts,
        extra_discard_grass=_retreat_grass_to_discard(mine.active[0])) == 0


# ---------------------------------------------------------------------------
# The KO was real: Myriad with two physical Grass, doubled by weakness
# ---------------------------------------------------------------------------

def test_the_promoted_ogerpon_knocks_out_their_whole_board():
    obs = _fixture(_FIX45)
    m.agent(obs)
    state, mine, opponent = _sides(obs)
    bench = [p for p in mine.bench if p is not None and p.id == OGERPON][0]

    # After the retreat, the Stretcher and the Teal Dance: two physical Grass,
    # four effective with Wild Growth.
    efectiva = len(bench.energies) + m._grass_attach_unit()
    assert efectiva >= m.AGENT_STATE.ATTACK_ENERGY_REQ[OGERPON]

    for cuerpo in list(opponent.active) + [p for p in opponent.bench if p is not None]:
        if cuerpo.id not in (LUNATONE, SOLROCK):
            continue
        base = m._attacker_base_damage(
            OGERPON, cuerpo, efectiva,
            grass_scale=sum(len(p.energies) for p in (mine.active + mine.bench)
                            if p is not None),
            teal_self_energy=efectiva, bench_count=len(mine.bench))
        dano = m._our_effective_damage(bench, cuerpo, base,
                                       m.AGENT_STATE.meganium_in_play, False)
        assert dano >= (cuerpo.hp or 0), (
            f"la familia Solrock es DEBIL a Planta: {cuerpo.id} deberia caer "
            f"({dano} vs {cuerpo.hp})")


# ---------------------------------------------------------------------------
# The plan: the turn stops being a DEVELOP the moment the pivot is counted
# ---------------------------------------------------------------------------

def test_the_plan_sees_the_prize_through_the_promote_route():
    m.agent(_fixture(_FIX45))
    plan = m.AGENT_STATE.turn_plan

    assert plan.prizes_today == 1, (
        "el premio existe: retirar, recuperar, cargar y atacar")
    assert plan.mode == gp.MODE_RACE, (
        f"un turno que se lleva un premio no es DEVELOP; leyo {plan.mode}")


# ---------------------------------------------------------------------------
# The decision: with the Supporter already spent, the retreat beats ending
# ---------------------------------------------------------------------------

def test_it_retreats_instead_of_ending_a_sterile_turn():
    obs = _fixture(_FIX47)
    tipos = [o["type"] for o in obs["select"]["option"]]
    i_retreat = tipos.index(int(m.OptionType.RETREAT))
    i_end = tipos.index(int(m.OptionType.END))

    choice = m.agent(obs)

    assert choice == [i_retreat], (
        f"esperaba RETREAT (idx {i_retreat}), eligio {choice} "
        f"(END era {i_end})")
