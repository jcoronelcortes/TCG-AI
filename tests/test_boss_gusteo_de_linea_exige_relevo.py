"""Gusting an EVOLUTION LINE with no KO: only if it RELIEVES an attacker.

A generalisation of [[boss-no-regalar-la-linea-alakazam]] (registro_002 step 20) to
the other six line decks. `evaluate_supporters` had six twin branches that
paid 690-730 for Boss's Orders **for the mere fact that there was a piece of
their line on the rival bench**, without requiring ANY KO:

    op_has_dreepy_line          700   if `bench_stage > active_stage`
    op_has_typhlosion/ethan     700   if `bench_stage > active_stage`
    op_is_gardevoir_deck        730   if there is a Ralts/Kirlia on the bench
    op_is_slowking_deck         710   if there is a Slowpoke on the bench
    op_is_dragapult_dusknoir    700   if there is a Duskull/Dusclops on the bench
    op_is_zoroark_deck          690   if there is a Zorua on the bench

The first two were the worst: `bench_stage > active_stage` PREFERS bringing up the
most evolved piece, which is exactly the one the rival wants in front to
evolve and attack with. The clean case is in the test below: with their
**Dragapult ex attacking** and a **Drakloak** on the bench, the old code spent
the Supporter swapping one for the other -- and the Drakloak evolves into another
Dragapult ex in the active spot.

Now all six go through `_gust_releva_al_atacante`: with no KO, a gust only
costs the rival a turn when it swaps a body that ATTACKS for one that cannot
pay for its attack. Discarded as relief are Dunsparce (a forbidden target) and
threat pre-evolutions (they evolve IN THE ACTIVE SPOT and attack with the new
body). The gusts that DO cash in are still scored separately, with the KO already
checked: `_bo_deny_evo_target` (965), `_bo_gust_key_bench` (975),
`_boss_ko_ex_value` (985) and `_boss_prize_rank`.

The predicate is measured by attack COST and never by damage: the PRINTED damage lies
in this environment -- Powerful Hand (Alakazam), Cruel Arrow (Fezandipiti ex) and the
two attacks of Gardevoir ex are listed with 0 in `attack_table`.

Golden corpus: 0 flips (no local record has a board of these lines
with the gust in play), which is why the scenario is FABRICATED with StateBuilder.
"""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk, G

OGERPON = m.Teal_Mask_Ogerpon_ex
BOSS = m.Boss_Orders
DRAGAPULT, DRAKLOAK, DREEPY = m.Dragapult_ex, m.Drakloak, m.Dreepy
DUSCLOPS = m.Dusclops
DUNSPARCE = 305


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
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
    m._init_cartas_tracking()


def _pkm(card_id, energias=0):
    return SimpleNamespace(id=card_id, energies=[1] * energias)


def _op(activo, banca):
    return SimpleNamespace(active=[activo] if activo else [], bench=list(banca))


# ---------------------------------------------------------------------------
# 1. The body predicate: by COST, never by printed damage
# ---------------------------------------------------------------------------

def test_el_dano_impreso_miente_y_por_eso_se_mide_el_coste():
    """Three REAL attacks are listed with damage 0 in `attack_table`. If the predicate
    looked at the damage, all three bodies would pass for harmless."""
    for cid in (m.Alakazam_ex, m.Fezandipiti_ex, m.Gardevoir_ex):
        datos = m.card_table[cid]
        assert all((m.attack_table[a].damage or 0) == 0 for a in datos.attacks)

    # Powerful Hand costs 1: a bare Alakazam attacks on its next turn.
    assert not m._op_cuerpo_inofensivo(_pkm(m.Alakazam_ex, 0))
    # Cruel Arrow costs 3: a bare Fezandipiti ex does not.
    assert m._op_cuerpo_inofensivo(_pkm(m.Fezandipiti_ex, 0))
    assert not m._op_cuerpo_inofensivo(_pkm(m.Fezandipiti_ex, 2))


def test_cuerpo_inofensivo_es_conservador_con_lo_que_no_sabe():
    assert not m._op_cuerpo_inofensivo(None)
    assert not m._op_cuerpo_inofensivo(_pkm(-12345, 0))     # an unknown card
    # Budew attacks for cost 0: it is never harmless.
    assert not m._op_cuerpo_inofensivo(_pkm(m.Budew, 0))
    # A card WITHOUT `energies` (what `get_card` can return outside the
    # field) must not blow up: an exception in `agent()` is a forfeit.
    assert not m._op_cuerpo_inofensivo(SimpleNamespace(id=m.Boss_Orders))
    assert m._op_cuerpo_inofensivo(SimpleNamespace(id=m.Fezandipiti_ex))


# ---------------------------------------------------------------------------
# 2. The generic relief
# ---------------------------------------------------------------------------

def test_relevo_exige_atacante_delante_y_cuerpo_muerto_detras():
    # Their Dragapult ex attacks (Jet Headbutt costs 1) and the bench Dusclops cannot
    # pay for its cost-2 attack: swapping one for the other costs them the turn.
    assert m._gust_releva_al_atacante(
        _op(_pkm(DRAGAPULT, 1), [_pkm(DUSCLOPS)]))
    # If their active no longer attacks there is nothing to relieve (and the gust also
    # gives them the free retreat).
    assert not m._gust_releva_al_atacante(
        _op(_pkm(m.Fezandipiti_ex, 0), [_pkm(DUSCLOPS)]))


def test_una_preevo_de_amenaza_no_es_relevo():
    """The Drakloak cannot attack today, but it evolves IN THE ACTIVE SPOT into another
    Dragapult ex and attacks with it: it is the same mistake as Abra -> Kadabra."""
    assert DRAKLOAK in m.EX_PREEVO_IDS
    assert not m._gust_releva_al_atacante(
        _op(_pkm(DRAGAPULT, 1), [_pkm(DRAKLOAK)]))
    # ...but if behind it there is ALSO a genuinely dead body, the relief exists.
    assert m._gust_releva_al_atacante(
        _op(_pkm(DRAGAPULT, 1), [_pkm(DRAKLOAK), _pkm(DUSCLOPS)]))


def test_dunsparce_nunca_es_relevo():
    assert not m._gust_releva_al_atacante(
        _op(_pkm(DRAGAPULT, 1), [_pkm(DUNSPARCE)]))


# ---------------------------------------------------------------------------
# 3. The full board: the `op_has_dreepy_line` branch
# ---------------------------------------------------------------------------

def _tablero(banca_extra=()):
    """Our turn with no attacker (Ogerpon ex at 1/3) and with Boss's Orders as the
    only card in hand: the menu is PLAY Boss's | END."""
    return (Escenario(turno=6, paso=70, tac=2, premios_propios=5)
            .mi_activo(pk(OGERPON, energias=[G], fisicas=1))
            .mi_banca(pk(OGERPON))
            .op_activo(pk(DRAGAPULT, hp=320, max_hp=320, energias=[G]))
            .op_banca(*([pk(DRAKLOAK, hp=90, max_hp=90)] + list(banca_extra)))
            .op_zonas(mano=5, mazo=30, prizes=5)
            .mi_mano(BOSS)
            .mazo()
            .resto_al_descarte()
            .menu_mano()
            .construir())


def test_el_tablero_sintetico_no_tiene_ni_ko_ni_ataque():
    obs = _tablero()
    yo = obs["current"]["yourIndex"]
    mio = obs["current"]["players"][yo]
    riv = obs["current"]["players"][1 - yo]

    # No body of ours reaches the 3 energies of Myriad Leaf Shower.
    assert all(len(p["energies"]) < m.ATTACK_ENERGY_REQ[OGERPON]
               for p in mio["active"] + [b for b in mio["bench"] if b])
    # Their Dragapult ex DOES attack (Jet Headbutt costs 1) -> there is something to relieve.
    assert not m._op_cuerpo_inofensivo(_pkm(DRAGAPULT, 1))
    assert riv["active"][0]["id"] == DRAGAPULT
    # The menu only offers the Boss's (0) and the END (1).
    assert [o["type"] for o in obs["select"]["option"]] == [7, 14]


def test_no_se_cambia_su_dragapult_por_el_drakloak_que_lo_reemplaza():
    obs = _tablero()
    assert m.agent(copy.deepcopy(obs)) == [1], (
        "sin KO, subir el Drakloak solo adelanta su siguiente Dragapult ex: "
        "el Boss's se guarda")


def test_con_un_cuerpo_muerto_detras_el_relevo_si_se_juega():
    obs = _tablero(banca_extra=(pk(DUSCLOPS, hp=90, max_hp=90),))
    assert m.agent(copy.deepcopy(obs)) == [0], (
        "el Dusclops pelado no puede pagar su ataque de coste 2: subirlo manda "
        "a la banca al Dragapult ex energizado y les cuesta el turno")
