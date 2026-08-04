"""Boss's Orders: do not give away the active spot when the gust achieves nothing.

Scenario (`registros/registro_002_pasos_015_hasta_022.json`, step 20, turn 2,
LOST vs Alakazam -- episode 88906640):

    US (6 prizes)                            RIVAL (6 prizes)
    active  Teal Mask Ogerpon ex 1/3         active  Fezandipiti ex 210 HP,
    bench   Teal Mask Ogerpon ex 2/3                 **0 energies**
    hand    Lana's Aid, Boss's Orders,       bench   Abra x4, Dunsparce
            Hydrapple ex, Unfair Stamp,      hand    ...with the Kadabra in it
            Tapu Bulu

No body of ours can attack (Myriad Leaf Shower costs 3). The menu only
offered four things: Boss's Orders, playing Tapu Bulu (vetoed: no Meganium in
play), retreating and ending the turn. The agent played **Boss's Orders** and brought up an
**Abra**. The rival evolved that very Abra into Kadabra and started attacking with the
body we had put in front of them.

Two independent mistakes in the same play:

1. **The gust achieved nothing.** Boss's Orders is, for the rival, a
   FREE RETREAT. Giving it to them only pays off to take a prize we would not take
   head-on, or to get out of the way the body that is going to hit us. Here there
   was no KO available and their active could not attack on their turn: *Cruel Arrow* costs
   3 energies and the Fezandipiti ex was bare (with one attachment it reaches 1).
   -> `gusteo_sin_proposito`, deck-agnostic.

2. **In THIS matchup bringing up the line is doing their work for them.** Abra -> Kadabra ->
   Alakazam is the deck's only attacking line. The only gust without a KO that
   pays off is the reverse one -- their Kadabra/Alakazam is already active WITH energy and we
   send it to the bench in exchange for a body that does not attack (`relevo`).
   -> `no_regalar_linea_alakazam`.

The evaluation the gust came out of was the `elif op_is_alakazam_deck` branch
of `evaluate_supporters`: it scored 700 for "bring up the highest evolution of the line
on the bench" without requiring a KO (a bench Abra > the active Fezandipiti, which is not
in the line). The 700 got past the turn-2 ceiling (200) and reached the reserve
rule `valor_del_supporter`: 2400 + 200*1.4 = 2680, above the END.

Golden corpus: a single flip, this step's (1/93 decisions).
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

_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_boss_regala_abra_step20.json"

OGERPON = m.Teal_Mask_Ogerpon_ex
FEZ = m.Fezandipiti_ex
ABRA = m.Abra
KADABRA = m.Kadabra
ALAKAZAM = m.Alakazam_ex
DUNSPARCE = 305


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


def _pk(card_id, energies=0):
    return SimpleNamespace(id=card_id, energies=[1] * energies)


def _op(active, bench):
    return SimpleNamespace(active=[active] if active else [], bench=list(bench))


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_turno_2_sin_atacante():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    assert o["current"]["turn"] == 2 and not o["current"]["supporterPlayed"]

    # Us: two Ogerpon ex, neither at the 3 energies of Myriad Leaf Shower.
    assert mio["active"][0]["id"] == OGERPON
    assert len(mio["active"][0]["energies"]) < m.ATTACK_ENERGY_REQ[OGERPON]
    assert [b["id"] for b in mio["bench"] if b] == [OGERPON]
    assert len(mio["bench"][0]["energies"]) < m.ATTACK_ENERGY_REQ[OGERPON]

    # The rival: a BARE Fezandipiti ex in the active spot -- Cruel Arrow costs 3, so
    # not even by attaching one energy can it attack on their turn.
    assert riv["active"][0]["id"] == FEZ
    assert riv["active"][0]["energies"] == []
    assert m._min_attack_cost(FEZ) == 3

    # ...and their bench is only the Alakazam line (+ a Dunsparce, a FORBIDDEN target).
    assert sorted(b["id"] for b in riv["bench"] if b) == [DUNSPARCE] + [ABRA] * 4

    # The Boss's was in hand and the menu offered it (option 0).
    assert any(c["id"] == m.Boss_Orders for c in mio["hand"])
    assert o["select"]["option"][0] == {"index": 1, "type": 7}


def test_no_se_juega_el_boss_que_regala_el_abra():
    o = _obs()
    fin = next(i for i, opt in enumerate(o["select"]["option"])
               if opt.get("type") == 14)
    assert m.agent(o) == [fin], (
        "sin KO y con el activo rival incapaz de atacar, el Boss's se guarda: "
        "subir un Abra le entrega la pre-evolucion de su unico atacante")


# ---------------------------------------------------------------------------
# 2. The two predicates, in isolation
# ---------------------------------------------------------------------------

def test_activo_inofensivo_mide_el_coste_del_ataque():
    # Fezandipiti ex: Cruel Arrow costs 3. Bare it does not get there even with an attachment;
    # with 2 on it, it does -> it stops being harmless.
    assert m._op_active_is_harmless(_op(_pk(FEZ, 0), []))
    assert not m._op_active_is_harmless(_op(_pk(FEZ, 2), []))
    # Powerful Hand costs ONE energy: the Alakazam is never harmless.
    assert not m._op_active_is_harmless(_op(_pk(ALAKAZAM, 0), []))
    # An unknown card: it is not vetoed on suspicion.
    assert not m._op_active_is_harmless(_op(_pk(-12345, 0), []))
    assert not m._op_active_is_harmless(_op(None, []))


def test_relevo_solo_cambia_un_atacante_por_un_no_atacante():
    # The good case: their CHARGED Alakazam goes down to the bench and a bare Abra comes up.
    assert m._alakazam_attacker_relief(_op(_pk(ALAKAZAM, 1), [_pk(ABRA)]))
    assert m._alakazam_attacker_relief(_op(_pk(KADABRA, 1), [_pk(FEZ)]))
    # With no energy on it there is nothing to leave stranded on the bench.
    assert not m._alakazam_attacker_relief(_op(_pk(ALAKAZAM, 0), [_pk(ABRA)]))
    # Swapping one attacker for another relieves nothing.
    assert not m._alakazam_attacker_relief(
        _op(_pk(ALAKAZAM, 1), [_pk(KADABRA), _pk(ALAKAZAM)]))
    # Dunsparce never counts: it is a FORBIDDEN gust target.
    assert not m._alakazam_attacker_relief(_op(_pk(ALAKAZAM, 1), [_pk(DUNSPARCE)]))
    # The record's case: their active is OUTSIDE the line -> there is no relief,
    # only the gift.
    assert not m._alakazam_attacker_relief(_op(_pk(FEZ, 0), [_pk(ABRA)] * 4))


# ---------------------------------------------------------------------------
# 3. The rules of `_REGLAS_BOSS_PLAY`
# ---------------------------------------------------------------------------

def _boss_ctx(**over):
    from test_main import _make_boss_ctx
    return _make_boss_ctx(**over)


def test_veto_alakazam_y_veto_generico_sobre_la_regla_de_reserva():
    regalo = _boss_ctx(op_is_alakazam_deck=True,
                       op_state=_op(_pk(FEZ, 0), [_pk(ABRA)] * 4))
    assert m._score_boss_orders_play(regalo) == m.SCORE_VETO

    # Without the Alakazam matchup the veto that remains is the deck-agnostic one: the same
    # bare active that cannot attack.
    generico = _boss_ctx(op_state=_op(_pk(FEZ, 0), [_pk(m.Dreepy)]))
    assert m._score_boss_orders_play(generico) == m.SCORE_VETO


def test_el_relevo_del_atacante_no_esta_vetado():
    ctx = _boss_ctx(op_is_alakazam_deck=True,
                    op_state=_op(_pk(ALAKAZAM, 1), [_pk(ABRA)]))
    assert m._score_boss_orders_play(ctx) > 0


def test_un_activo_que_si_ataca_no_dispara_el_veto_generico():
    ctx = _boss_ctx(op_state=_op(_pk(FEZ, 3), [_pk(m.Dreepy)]))
    assert m._score_boss_orders_play(ctx) > 0


def test_los_motivos_con_premio_mandan_sobre_ambos_vetos():
    """No veto can cover up a finisher or a line cut WITH a KO."""
    board = dict(op_is_alakazam_deck=True,
                   op_state=_op(_pk(FEZ, 0), [_pk(ABRA)] * 4))
    assert (m._score_boss_orders_play(_boss_ctx(win_via_boss_gust=True, **board))
            == m.BOSS_SCORE_WIN_NOW)
    assert (m._score_boss_orders_play(_boss_ctx(gust_2prize_via_boss=True, **board))
            == m.BOSS_SCORE_GUST_2PRIZE)
    assert (m._score_boss_orders_play(_boss_ctx(boss_deny_alakazam_line=True, **board))
            == m.BOSS_SCORE_PRIZE_RANK_BASE)
    assert m._score_boss_orders_play(
        _boss_ctx(boss_prize_rank=3, **board)) >= m.BOSS_SCORE_PRIZE_RANK_BASE
    # The DEFENSIVE gust (they finish us off next turn) also survives.
    assert m._score_boss_orders_play(
        _boss_ctx(boss_defensive_gust=True, **board)) > 0


def test_una_preevo_de_amenaza_de_activo_no_dispara_el_veto_generico():
    """A Riolu does not attack today, but it evolves into Mega Lucario ex and attacks with the
    NEW body: its current attack cost says nothing."""
    ctx = _boss_ctx(op_state=_op(_pk(m.Riolu, 0), [_pk(m.Mega_Lucario_ex)]))
    assert m._score_boss_orders_play(ctx) > 0


# ---------------------------------------------------------------------------
# 4. The gust TARGET: with no KO no other attacker of the line is promoted
# ---------------------------------------------------------------------------

def _gust_ctx(card_id, can_ko=False, energy=0):
    return m._CtxGustObjetivo(
        card_id=card_id, energy=energy,
        rc0=m.RETREAT_COST.get(card_id, 0), rc1=m.RETREAT_COST.get(card_id, 1),
        stall_diff=m.RETREAT_COST.get(card_id, 0) - energy,
        is_ex=False, is_exmega=False, is_megaex=False, prizes=1, wins_now=False,
        is_stage1=(card_id == KADABRA), is_stage2=(card_id == ALAKAZAM),
        tiene_tool=False, can_ko=can_ko, tier_ko=5 if can_ko else 0,
        plan_target_match=False, regust_energized=False,
        line_rank=0, line_can_ko=False, op_alakazam=True,
        op_latias=False, op_dragapult_line=False, op_typhlosion_line=False)


def _estorbo(ctx):
    score, _ = m._resolve_rules(m._RULES_GUST_NUISANCE,
                                 m._ADJUST_GUST_NUISANCE, ctx, default=-200)
    return score


def test_sin_ko_no_se_sube_kadabra_ni_alakazam():
    assert _estorbo(_gust_ctx(KADABRA)) == m.SCORE_FORBID
    assert _estorbo(_gust_ctx(ALAKAZAM)) == m.SCORE_FORBID
    # The bare Abra is still a valid relief (the user's rule).
    assert _estorbo(_gust_ctx(ABRA)) > 0


def test_con_ko_se_levanta_la_prohibicion():
    """Gusting to KNOCK THEM OUT if it cuts the line: there all three are valid
    targets and the historical order (Kadabra >= Abra >= Alakazam) is kept."""
    kad = _estorbo(_gust_ctx(KADABRA, can_ko=True))
    abra = _estorbo(_gust_ctx(ABRA, can_ko=True))
    alk = _estorbo(_gust_ctx(ALAKAZAM, can_ko=True))
    assert min(kad, abra, alk) > 0
    assert kad >= abra >= alk
