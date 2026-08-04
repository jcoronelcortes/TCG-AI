"""Promotion after a KO: the MATCH POINT veto and the tie-break among survivors.

It closes off the priorities the user set for "who to bring up" when they
knock out our active, in this order:

    (1) that it SURVIVES the blow             -> `_promo_survives` + Festival Lead
    (2) not exposing the Wild Growth multiplier -> the veto "the Meganium line does
        not go to the active spot" (already existed)
    (3) the one CLOSEST to being able to attack
    (4) all else equal, the one that gives away FEWER prizes

**Item 4 — MATCH POINT.** When it is enough for the rival to knock out that body to
take the last prize, bringing up a doomed one is not a bad trade: it is
losing the game. Survival stops being a *penalty*
(`PROMO_DOOMED_PENALTY`, 6000) and becomes a **veto**
(`PROMO_MATCH_POINT_VETO`), below `SCORE_NEVER` so that it does not tie with
the other promotion vetoes.

The case that makes it necessary is that of log 88971843 without the Tapu Bulu: the only
body that survives is the **Meganium**, which carries its own veto at −10000 for being
the Wild Growth engine. With only the penalty, the doomed Dipplin (−2595)
beat it and handed over the game. Giving away the last prize is worse than exposing
the multiplier.

**Item 5 — the tie-break.** Priorities (3) and (4) were already decisive, and in that
same order, inside `_promote_setup_ko_attacker` (`_ps_key`), but that rule
requires the completed attack to FINISH OFF the rival active. This adjustment covers
the gap it leaves: the survivors whose attack does not finish. It is bounded to 0..450
— it rules over the promotion's BASE score (150-250, which orders by LIFE, the
criterion the user puts below these two) and stays well below
any decisive rule. With the 60 points of the first version it was not enough:
measured, a 210 HP Ogerpon ex THREE attachments away from attacking still beat a
140 HP Tapu Bulu TWO away.
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
            / "festival_lead_promover_tapu_no_dipplin_step117.json")

MEGANIUM = m.Meganium
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
GRIMMSNARL = 648                # Marnie's Grimmsnarl ex: Shadow Bullet 180


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
    m._op_bench_count = 0
    m._festival_grounds_in_play = False
    yield
    m._init_cards_tracking()


def _pk(cid, hp, energies=0, serial=900):
    """A synthetic bench Pokemon (energies already EFFECTIVE, as in the observation)."""
    return {"appearThisTurn": False,
            "energies": [1] * energies,
            "energyCards": ([{"id": m.Basic_Grass_Energy, "playerIndex": 0,
                              "serial": serial}] if energies else []),
            "hp": hp, "id": cid, "maxHp": hp, "playerIndex": 0,
            "preEvolution": [], "serial": serial, "tools": []}


def _base(bench=None, without_stadium=False, op_active=None, op_prizes=None):
    """The real fixture of step 117 with the bench / rival active replaced."""
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]
    if without_stadium:
        o["current"]["stadium"] = []
    if op_active is not None:
        op_active = dict(op_active, playerIndex=1 - yo)
        riv["active"] = [op_active]
    if op_prizes is not None:
        riv["prize"] = [None] * op_prizes
    if bench is not None:
        mio["bench"] = [dict(b, playerIndex=yo) for b in bench]
    o["select"]["option"] = [
        {"area": 5, "index": k, "playerIndex": yo, "type": 3}
        for k in range(len(mio["bench"]))]
    return o


def _elegido(obs):
    yo = obs["current"]["yourIndex"]
    opt = obs["select"]["option"][m.agent(obs)[0]]
    return obs["current"]["players"][yo]["bench"][opt["index"]]


# ---------------------------------------------------------------------------
# Item 4 - MATCH POINT
# ---------------------------------------------------------------------------

def test_el_veto_de_match_point_esta_por_debajo_de_los_demas_vetos():
    """If it tied with SCORE_NEVER, the tie-break would be left to the option order
    right between the body that survives and the one that makes us lose."""
    assert m.PROMO_MATCH_POINT_VETO < m.SCORE_NEVER
    assert m.PROMO_MATCH_POINT_VETO < -m.PROMO_KO_BONUS


def test_prefiere_el_motor_vetado_antes_que_regalar_el_ultimo_premio():
    """The real case without the Tapu Bulu: the only survivor is the Meganium,
    which carries its own veto for being the Wild Growth multiplier."""
    o = _base()
    yo = o["current"]["yourIndex"]
    bench = [b for b in o["current"]["players"][yo]["bench"] if b["id"] != TAPU]
    o = _base(bench=bench)

    riv = o["current"]["players"][1 - yo]
    assert len(riv["prize"]) == 1                      # match point
    assert [b["id"] for b in o["current"]["players"][yo]["bench"]] == [
        MEGANIUM, DIPPLIN, CHIKORITA]
    # Meganium (160) survives the 100; Dipplin (80) and Chikorita (70) do not.
    assert _elegido(o)["id"] == MEGANIUM


def test_sin_match_point_el_condenado_sigue_siendo_una_opcion():
    """Boundary: with the rival at 3 prizes, a KO does not close the game and the
    penalty rules again (which is graduable), not the veto."""
    o = _base()
    yo = o["current"]["yourIndex"]
    bench = [b for b in o["current"]["players"][yo]["bench"] if b["id"] != TAPU]
    o = _base(bench=bench, op_prizes=3)
    # With 3 prizes the rival does not win by knocking out a 1-prize body: the Dipplin stops
    # being vetoed and its score competes with the Meganium's again.
    assert len(o["current"]["players"][1 - yo]["prize"]) == 3
    assert _elegido(o)["id"] == DIPPLIN


def test_si_no_aguanta_nadie_no_se_veta_la_banca_entera():
    """Boundary: with no survivors the game is lost anyway and the prize rule
    rules; vetoing everyone would leave the choice to chance."""
    o = _base(bench=[_pk(DIPPLIN, 80, 2, 901), _pk(CHIKORITA, 70, 0, 902)],
              op_prizes=1)
    yo = o["current"]["yourIndex"]
    # Both die to Do the Wave's 100.
    for b in o["current"]["players"][yo]["bench"]:
        assert b["hp"] <= 100
    elegido = _elegido(o)
    assert elegido["id"] in (DIPPLIN, CHIKORITA)       # it is chosen, not blocked


def test_match_point_es_deck_agnostico():
    """It does not depend on Festival Lead: the same veto against Marnie's Grimmsnarl ex
    (Shadow Bullet 180) and with no stadium on the table."""
    o = _base(without_stadium=True,
              op_active={"appearThisTurn": False, "energies": [2, 2],
                         "energyCards": [], "hp": 320, "id": GRIMMSNARL,
                         "maxHp": 320, "preEvolution": [], "serial": 800,
                         "tools": []},
              op_prizes=1,
              bench=[_pk(HYDRAPPLE, 330, 0, 901), _pk(TAPU, 140, 2, 902)])
    yo = o["current"]["yourIndex"]
    op_act = m.to_observation_class(o).current.players[1 - yo].active[0]
    tapu = m.to_observation_class(o).current.players[yo].bench[1]
    hydra = m.to_observation_class(o).current.players[yo].bench[0]
    assert m._op_active_attack_damage_to(op_act, tapu) >= 140    # it dies
    assert m._op_active_attack_damage_to(op_act, hydra) < 330    # it survives
    assert _elegido(o)["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# Item 5 - the tie-break among survivors
# ---------------------------------------------------------------------------

def test_entre_supervivientes_manda_estar_cerca_de_atacar_y_ceder_menos():
    """A 140 HP Tapu Bulu TWO attachments away from Wood Hammer (1 prize) comes up
    ahead of a 210 HP Ogerpon ex THREE away from Myriad (2 prizes), even with
    70 HP less: life is the criterion of LAST resort."""
    o = _base(bench=[_pk(OGERPON, 210, 0, 901), _pk(TAPU, 140, 2, 902)])
    yo = o["current"]["yourIndex"]
    bench = m.to_observation_class(o).current.players[yo].bench
    op_act = m.to_observation_class(o).current.players[1 - yo].active[0]

    # Both SURVIVE the blow: the tie-break is not decided by survival.
    for pk_ in bench:
        assert m._op_active_attack_damage_to(op_act, pk_) < (pk_.hp or 0)
    # And neither finishes off: it is not decided by the KO either.
    assert 210 > 0 and m.ATTACK_ENERGY_REQ[OGERPON] > 0

    elegido = _elegido(o)
    assert elegido["id"] == TAPU
    assert m.prize_count(bench[1]) < m.prize_count(bench[0])


def test_el_desempate_no_puede_comprar_una_regla_decisiva():
    """Bounded to 0..450: below the +4000 of the best attacker, of the named
    branches (8000-9500) and of the +20000 of the one that knocks out."""
    assert 450 < 4000 < m.PROMO_KO_BONUS


def test_el_desempate_no_cambia_la_decision_del_registro():
    """A non-regression control: step 117 still brings up the Tapu Bulu."""
    o = _base()
    assert _elegido(o)["id"] == TAPU
