"""Within an evolution line you knock out the HIGHEST STAGE you can.

Scenario (user, `registros/registro_008_pasos_088_hasta_097.json` step 93,
episode 89013104, turn 8, vs Cynthia's Garchomp ex, WON with a mistake):

    US (seat 1, 3 prizes)                    RIVAL (6 prizes)
    active  Hydrapple ex 230/330, 2e         active  Cynthia's Gabite 100 HP,
    bench   Ogerpon ex 4e, Meganium,                 **0 energies** (Stage 1)
            Meowth ex, Ogerpon ex 2e,        bench   Cynthia's Roselia,
            Tapu Bulu                                **Cynthia's Gible 1e**,
    hand    2x Ultra Ball, Bayleef, Applin,           Roselia, Roselia
            Dipplin, Hydrapple ex, Ogerpon ex,
            Fezandipiti ex, **Boss's Orders**

The Hydrapple ex knocks out either of the two bodies. The agent played
**Boss's Orders** to bring up the **Gible** (a Basic) and knock it out. It is a
triple mistake:

  * both KOs take **the same prize** (both are 1-prize bodies);
  * the **Gabite is already active**: knocking it out is FREE -- it costs neither the Boss's
    nor the turn's Supporter, which are left for the next turn;
  * and above all, the Gabite is **one step higher**. The line is
    Gible -> Gabite -> **Cynthia's Garchomp ex** (Stage 2, 330 HP, 2 prizes):
    the rival deck depends on that Stage 2 to attack. By killing the Gabite the rival
    has to rebuild **two** steps; by killing the Gible, the Gabite evolves
    the next turn all the same.

RULE: when the rival line is Basic -> Stage 1 -> Stage 2, you ALWAYS knock out
the highest reachable stage. You never spend Boss's Orders bringing down the
LOWER stage of a line whose upper stage is already in front and dies anyway.

Why it fired
------------
In the deny-evo loop of the Boss's evaluation, the Gible satisfied
`_bo_pe_is_ex_preevo_energized` (a pre-evo of an ex line, with energy, equal
prizes) and with the active BARE the exception
`_bo_pe_is_energized_preevo_vs_bare_wall` switched on, which skipped the guard of "the active
dominates". That exception was written for the **INVERSE** case of the Marnie
line (an active **Impidimp**, a bare BASIC, with a charged **Morgrem** STAGE 1 on the bench): there
gusting DOES go up a step. It only looked at the active's ENERGY, never at its STAGE.

The fix is a stage veto (`_supera_en_evolucion`, deck-agnostic: it comes from
`basic`/`stage1`/`stage2` and from the `evolvesFrom` chain of the card data) that
overrides the three exceptions when the active is a more evolved link of the
SAME line and does not yield fewer prizes.

A census of flips over the 117 decisions of episode 89013104: **1 flip**, this
step's. The golden corpus unchanged.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "garchomp_step93_no_gustear_el_gible_con_gabite_activo.json")

GIBLE = m.Cynthias_Gible
GABITE = m.Cynthias_Gabite
GARCHOMP = m.Cynthias_Garchomp_ex
HYDRAPPLE = m.Hydrapple_ex
BOSS = m.Boss_Orders
ROSELIA = 341
IMPIDIMP = m.Marnies_Impidimp
MORGREM = m.Marnies_Morgrem


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


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _pkm(card_id, energies=0):
    return SimpleNamespace(id=card_id, energies=[1] * energies, energyCards=[],
                           tools=[])


def _idx(obs, **campos):
    """Index of the menu option that satisfies all the given fields."""
    return next(i for i, o in enumerate(obs["select"]["option"])
                if all(o.get(k) == v for k, v in campos.items()))


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_paso_93_con_la_fase_1_delante():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    assert o["current"]["turn"] == 8 and not o["current"]["supporterPlayed"]

    # Us: a Hydrapple ex in the active spot, with the Boss's in hand and the menu
    # offering BOTH things (playing it or attacking).
    assert mio["active"][0]["id"] == HYDRAPPLE
    assert any(c["id"] == BOSS for c in mio["hand"])
    assert _idx(o, type=13) >= 0 and _idx(o, type=7, index=8) >= 0

    # The rival: a BARE Gabite (Stage 1) active and the Gible (a Basic) on the bench
    # WITH energy -- both bodies of the same line, both worth 1 prize.
    assert riv["active"][0]["id"] == GABITE and riv["active"][0]["energies"] == []
    bench = [b["id"] for b in riv["bench"] if b]
    assert bench == [ROSELIA, GIBLE, ROSELIA, ROSELIA]
    assert len(riv["bench"][1]["energies"]) == 1
    assert (m.prize_count_op(_pkm(GABITE)) == m.prize_count_op(_pkm(GIBLE)) == 1)

    # ...and the line ends in a 2-prize ex: that is why cutting it is worth it.
    assert m.prize_count_op(_pkm(GARCHOMP)) == 2


def test_el_hydrapple_noquea_a_los_dos_cuerpos():
    """The veto only makes sense if the KO on the active is REAL: if the Gabite did
    not die, gusting the Gible would still be the only route to a prize."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    assert riv["active"][0]["hp"] == 100 and riv["bench"][1]["hp"] == 70


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_no_se_gustea_el_gible_teniendo_el_gabite_de_activo():
    o = _obs()
    assert m.agent(o) == [_idx(o, type=13)], (
        "con la Fase 1 de la linea ya de activo y noqueable, se ATACA: mismo "
        "premio, corta la linea mas arriba y no gasta el Boss's ni el Supporter")


def test_control_con_el_basico_delante_el_boss_si_se_juega():
    """Control (the Marnie case, inverted on the same board): if the one in the
    active spot is the bare BASIC and the charged STAGE 1 is on the bench,
    gusting DOES go up a step -- and the Boss's is played again."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    active, bench = riv["active"][0], riv["bench"][1]
    active["id"], bench["id"] = GIBLE, GABITE
    active["hp"] = active["maxHp"] = 70
    bench["hp"] = bench["maxHp"] = 100
    active["preEvolution"] = []
    bench["preEvolution"] = [{"id": GIBLE, "playerIndex": 0, "serial": 4}]

    assert m.agent(o) == [_idx(o, type=7, index=8)], (
        "activo Basico desnudo + Fase 1 energizada en banca: el gusteo corta la "
        "linea un escalon MAS ARRIBA, que es justo lo que motiva el deny-evo")


# ---------------------------------------------------------------------------
# 3. The stage/line predicates, in isolation (deck-agnostic)
# ---------------------------------------------------------------------------

def test_la_etapa_sale_del_dato_de_carta():
    assert m._evolution_stage(GIBLE) == 0
    assert m._evolution_stage(GABITE) == 1
    assert m._evolution_stage(GARCHOMP) == 2
    # Our own line and Marnie's, without touching EVO_LINES.
    assert [m._evolution_stage(c) for c in (m.Applin, m.Dipplin, HYDRAPPLE)] == [0, 1, 2]
    assert [m._evolution_stage(c) for c in (IMPIDIMP, MORGREM,
                                            m.Grimmsnarl_ex)] == [0, 1, 2]
    # What is not a Pokemon (or does not exist) has no stage.
    assert m._evolution_stage(BOSS) is None
    assert m._evolution_stage(-12345) is None


def test_la_linea_se_reconstruye_subiendo_por_evolves_from():
    assert m._same_evolution_line(GIBLE, GARCHOMP)
    assert m._same_evolution_line(GARCHOMP, GABITE)
    assert m._same_evolution_line(GIBLE, GIBLE)
    # Cynthia's Roselia -> Roserade is ANOTHER line of the SAME deck.
    assert not m._same_evolution_line(GIBLE, ROSELIA)
    # And the homonymous lines of another trainer do not mix with ours.
    assert not m._same_evolution_line(GABITE, m.Dipplin)


def test_supera_en_evolucion_exige_misma_linea_y_etapa_mayor():
    assert m._is_more_evolved_than(_pkm(GABITE), _pkm(GIBLE))
    assert m._is_more_evolved_than(_pkm(GARCHOMP), _pkm(GIBLE))
    assert m._is_more_evolved_than(_pkm(MORGREM), _pkm(IMPIDIMP))
    # The other way round NO: it is precisely the case the deny-evo exists for.
    assert not m._is_more_evolved_than(_pkm(GIBLE), _pkm(GABITE))
    # The same stage, or stages of DIFFERENT lines: there is no step to compare.
    assert not m._is_more_evolved_than(_pkm(GABITE), _pkm(GABITE))
    assert not m._is_more_evolved_than(_pkm(GABITE), _pkm(ROSELIA))
    assert not m._is_more_evolved_than(_pkm(m.Dipplin), _pkm(GIBLE))
    assert not m._is_more_evolved_than(None, _pkm(GIBLE))
    assert not m._is_more_evolved_than(_pkm(GABITE), None)
