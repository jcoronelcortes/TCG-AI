"""The gust target WITHOUT a KO: what decides is the ATTACK COST, not the stage.

The real record of the criterion that `test_boss_objetivo_sin_ko_cuerpo_muerto.py`
already fabricates synthetically. That test builds the scenario
with the StateBuilder because the local records barely reached the target
prompt (context 3); this one anchors the **real step** in which the submitted
agent failed, so the rule cannot go back without a test firing.

Scenario (`registros/registro_006_pasos_063_hasta_066.json`, step 65, turn 6,
LOST vs Dragapult -- episode 89079426):

    US (6 prizes)                           OPPONENT (6 prizes)
    active Chikorita 60/70, 1 {G}           active  Budew 30
    bench  Fezandipiti ex 210, 0 {G}        bench   Drakloak 90 **1 en.**
    hand   Ultra Ball (blocked), Meganium,          **Dragapult ex 320, 0 en.**
           Grass x2, Meowth ex                      Munkidori 110, 1 en.
                                                    **Drakloak 90, 0 en.** x2

Playing the Boss's was correct (our active finishes nothing). The submitted agent
**brought up the Dragapult ex**: it is the biggest piece on the bench, but its attack
costs **1** energy, so with next turn's attachment it attacks from the
active spot -- and on top of that the Boss's had paid for the trip for free. We put
in front of us, for free, exactly the body they wanted to attack with.

The right target is a **bare Drakloak**: its attack costs **2**, so
not even with the turn's attachment can it hit; its only way out is to spend the turn's
energy paying the retreat. That is a whole opposing turn bought.

The three numbers that decide (the user's rule) and that this step separates:

    candidate        energies   attack cost   retreat cost   dead?
    Drakloak            1            2              1          NO (2<=1+1)
    Dragapult ex        0            1              1          NO (1<=0+1)
    Munkidori           1            2              1          NO (2<=1+1)
    Drakloak            0            2              1          **YES** (2>0+1)

Looking at attached energies and retreat cost is not enough: by those two numbers
the Dragapult ex and the bare Drakloak **tie** (both at 0 energies, both with
retreat 1). The only thing that separates them is how many energies they need to
**start attacking**, which is what `_op_cuerpo_inofensivo` measures -- by COST
read from the card data, never by printed damage (Powerful Hand, Cruel Arrow and
both attacks of Gardevoir ex are listed as 0 and all of them really hit).

The rule that applies it is `sin_ko_prefiere_cuerpo_muerto` (+1500, in both
modes of the selector), documented in `docs/strategy.md`. Here BOTH sides of the
contrast are also pinned, which is what really protects against
a regression: the bare Drakloak wins **and** the Dragapult ex stays below.
"""

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
            / "dragapult_boss_sube_drakloak_pelado_step65.json")

DRAGAPULT = m.Dragapult_ex
DRAKLOAK = m.Drakloak
DREEPY = m.Dreepy
MUNKIDORI = m.Munkidori


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
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _objetivo(obs, choice):
    """(id, energies) of the opposing benched Pokémon the gust chooses."""
    o = obs["select"]["option"][choice[0]]
    assert o["type"] == int(m.OptionType.CARD) and o["area"] == 5
    pk = obs["current"]["players"][o["playerIndex"]]["bench"][o["index"]]
    return pk["id"], len(pk["energies"])


def _pk(card_id, energias):
    return SimpleNamespace(id=card_id, energies=[m.EnergyType.GRASS] * energias)


# ---------------------------------------------------------------------------
# 1. The real step
# ---------------------------------------------------------------------------

def test_paso65_sube_un_drakloak_pelado_no_el_dragapult_ex():
    obs = _obs()
    assert _objetivo(obs, m.agent(obs)) == (DRAKLOAK, 0), (
        "sin KO se sube el cuerpo que NO puede pagar su ataque: el Drakloak "
        "pelado necesita 2 energías y solo puede retirarse; el Dragapult ex "
        "ataca con 1 y el Boss's le habría pagado la subida gratis")


def test_paso65_el_escenario_es_el_que_discrimina():
    """Without these three conditions the step would prove nothing."""
    obs = _obs()
    bench = obs["current"]["players"][1]["bench"]
    # (a) the Dragapult ex is on the bench and is eligible;
    assert any(p["id"] == DRAGAPULT for p in bench)
    # (b) by energies + retreat cost, the Dragapult ex and the bare Drakloak
    #     TIE: the only thing that separates them is the attack cost;
    drag = next(p for p in bench if p["id"] == DRAGAPULT)
    drak = next(p for p in bench if p["id"] == DRAKLOAK and not p["energies"])
    assert len(drag["energies"]) == len(drak["energies"]) == 0
    assert m.RETREAT_COST[DRAGAPULT] == m.RETREAT_COST[DRAKLOAK]
    # (c) and there is no KO available (if there were, the KO tiers would rule,
    #     >= 3000, and this criterion would never get to decide).
    assert m.plan.remain_hp in (-1, None) or m.plan.remain_hp > 0


# ---------------------------------------------------------------------------
# 2. The criterion, in isolation: energies + attack cost
# ---------------------------------------------------------------------------

def test_cuerpo_inofensivo_mide_el_coste_del_ataque_no_la_etapa():
    # Dragapult ex: a cost-1 attack -> bare it ALREADY attacks next turn.
    assert m._op_body_is_harmless(_pk(DRAGAPULT, 0)) is False
    # Drakloak: a cost-2 attack -> bare it does NOT attack even with the turn's attachment.
    assert m._op_body_is_harmless(_pk(DRAKLOAK, 0)) is True
    # ...but with one energy on it, it is no longer dead.
    assert m._op_body_is_harmless(_pk(DRAKLOAK, 1)) is False
    # Dreepy is a Basic and "smaller" than the Drakloak, but its attack costs
    # 1: the STAGE is not the criterion.
    assert m._op_body_is_harmless(_pk(DREEPY, 0)) is False
    # Munkidori with its energy reaches exactly the 2 it needs.
    assert m._op_body_is_harmless(_pk(MUNKIDORI, 1)) is False
    assert m._op_body_is_harmless(_pk(MUNKIDORI, 0)) is True


def test_budew_nunca_es_cuerpo_muerto_su_ataque_cuesta_cero():
    """Itchy Pollen costs 0: bare and all, it attacks. It is also the one already vetoed
    by `retirada_gratis` in nuisance mode (a retreat cost of 0)."""
    assert m._op_body_is_harmless(_pk(m.Budew, 0)) is False


# ---------------------------------------------------------------------------
# 3. The graduated axis: `_op_cuerpo_inofensivo` is a THRESHOLD of something measurable
# ---------------------------------------------------------------------------
# The boolean is not a primitive datum: it is `_op_deficit_de_ataque >= 2`. Having it
# separate is what made it visible that the horizon is ONE energy, and it is the datum
# on which the graduated tie-break inside the band was tested (and discarded as inert)
# -- see the "MEASURED AND REVERTED" note next to `_v_gust_traba_neta`.

def test_deficit_de_ataque_es_el_umbral_graduado_de_cuerpo_inofensivo():
    assert m._op_attack_deficit(_pk(DRAGAPULT, 0)) == 1     # it attacks with 1
    assert m._op_attack_deficit(_pk(DRAKLOAK, 0)) == 2      # dead by exactly one
    assert m._op_attack_deficit(_pk(DRAKLOAK, 1)) == 1
    assert m._op_attack_deficit(_pk(DRAKLOAK, 5)) == 0      # never negative
    assert m._op_attack_deficit(_pk(m.Dusknoir, 0)) == 3    # dead by a wide margin
    # The threshold and the graduated axis cannot drift apart: one is a function of the other.
    for cid in (DREEPY, DRAKLOAK, DRAGAPULT, MUNKIDORI, m.Dusknoir):
        for en in range(4):
            pk = _pk(cid, en)
            assert (m._op_body_is_harmless(pk)
                    is (m._op_attack_deficit(pk) >= 2))


def test_deficit_desconocido_no_inventa_nada():
    """With no readable attacks, neither "dead" nor "stuck" is concluded."""
    assert m._op_attack_deficit(None) is None
    assert m._op_attack_deficit(_pk(m.Basic_Grass_Energy, 0)) is None
    assert m._op_body_is_harmless(_pk(m.Basic_Grass_Energy, 0)) is False


def test_los_muros_pasan_por_muertos_y_por_eso_existe_gust_trampa_ids():
    """Crustle, Sylveon, Cornerstone and Iron Thorns ex have cost-3 attacks:
    bare they give a deficit of 3 and the criterion would call them "dead". They are exactly the
    bodies we do NOT want in front, which is why `GUST_TRAMPA_IDS` excludes them from
    `sin_ko_prefiere_cuerpo_muerto`. It pins the premise of that list."""
    for trampa in sorted(m.GUST_TRAP_IDS):
        pk = _pk(trampa, 0)
        assert m._op_attack_deficit(pk) >= 2
        assert m._op_body_is_harmless(pk) is True


def test_el_paso_65_lo_decide_el_umbral_no_un_desempate_graduado():
    """In this step ALL the dead bodies have a deficit of 2 (the minimum), so
    the correction leans on the threshold alone. That is what made inert the
    graduated tie-break that was tested and reverted."""
    obs = _obs()
    muertos = [_pk(p["id"], len(p["energies"]))
               for p in obs["current"]["players"][1]["bench"]]
    muertos = [pk for pk in muertos if m._op_body_is_harmless(pk)]
    assert muertos, "el paso tiene que tener algún cuerpo muerto"
    assert {m._op_attack_deficit(pk) for pk in muertos} == {2}
