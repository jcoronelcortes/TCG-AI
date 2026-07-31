"""Con la mano rival GIGANTE, Xerosic va ANTES del Unfair Stamp.

Escenario (user, episodio 88704504, registro_008 paso 90, turno 8 vs Alakazam):

    NOSOTROS                                    RIVAL
    activo  Tapu Bulu (cargado)                 activo  Alakazam
    mano    Meganium, **Unfair Stamp**, Planta, banca   Fezandipiti ex 210, ...
            Teal Mask Ogerpon ex,               mano    **18 cartas**
            **Xerosic's Machinations**, Meowth ex
    Nos noquearon el turno anterior -> el Sello es jugable.

Las dos cartas caben en el MISMO turno: **Unfair Stamp es un Item** (ACE SPEC)
y **Xerosic's Machinations un Supporter**. Aquí no se elige carta, se elige
ORDEN — y hacen cosas distintas con esas 18 cartas:

    Unfair Stamp   "Each player shuffles their hand into their deck. Then, you
                    draw 5 cards, and your opponent draws 2 cards."
    Xerosic        "Your opponent discards cards from their hand until they
                    have 3 cards in their hand."

- **Sello -> Xerosic** (conducta vieja): las 18 vuelven a su mazo, roba 2, y
  Xerosic ya no hace nada (le quedan 2 <= 3). Peor aún: el Sello baraja
  **nuestra** mano, así que se lleva el propio Xerosic (en el registro se llevó
  también el Boss's y solo se recuperó uno por suerte).
- **Xerosic -> Sello** (correcto): descarta hasta dejarle 3 → **15 cartas al
  descarte PARA SIEMPRE**; el Sello lo deja igualmente en 2. Mismo tablero al
  cerrar el turno, con medio mazo rival muerto.

Por qué fallaba: `cede_a_unfair_stamp` en `_REGLAS_XEROSIC_PLAY` vetaba a
Xerosic **siempre** que el Sello fuera jugable. Ese veto es correcto para
Lillie's/Dawn/Lana's (el Sello barajaría lo que acaban de traer) pero no para
Xerosic, cuyo efecto es inmediato e irreversible y el Sello no puede deshacer.

Arreglo (`_xr_antes_del_sello`, deck-agnóstico): con el Sello jugable, Xerosic
en mano, el hueco de Supporter libre y la mano rival >=
`XEROSIC_STAMP_ORDEN_MIN_OP_HAND` (10), se invierte el orden — Xerosic conserva
su score y es el **Sello** el que cede (`cede_el_orden_a_xerosic`). Es un veto
de ORDEN y se **auto-revoca**: en cuanto Xerosic se juega, `supporterPlayed`
pasa a True, el predicado se apaga y el Sello se juega en el mismo turno.

El umbral 10 sale del coste real: el hueco de Supporter se gasta ANTES del
refresco del Sello, así que las 5 cartas nuevas ya no pueden pagar otro
Supporter. Lo que se gana son `op_hand - 3` cartas quemadas; solo compensa
cuando eso supera una mano entera (>= 7 cartas → mano rival >= 10).

Efecto lateral corregido: los `_AJUSTES_STAMP_PLAY` no comprobaban el score, así
que `bonus_matchup` (+400 vs Alakazam) sacaba al Sello vetado del resolver en
**+399** — justo en el matchup donde vive este veto. Ahora todos los ajustes
exigen `s > 0`: bonifican jugadas que se van a hacer, no resucitan vetos.
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
            / "alakazam_step90_no_meowth_boss_con_unfair_stamp.json")

UNFAIR_STAMP = m.Unfair_Stamp
XEROSIC = m.Xerosic_Machinations


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
    m._ub_engine_pivot_turn = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _obs(op_hand=None, supporter_played=None, sin_xerosic=False):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    if op_hand is not None:
        o["current"]["players"][1 - yo]["handCount"] = op_hand
    if supporter_played is not None:
        o["current"]["supporterPlayed"] = supporter_played
    if sin_xerosic:
        # Se SUSTITUYE (no se quita) para no descolocar los `index` de las
        # opciones PLAY del menú, que apuntan a posiciones de la mano.
        for c in o["current"]["players"][yo]["hand"]:
            if c["id"] == XEROSIC:
                c["id"] = m.Meganium
    return o


def _scores(obs):
    """Devuelve {'stamp': score, 'xerosic': score} de la decisión real."""
    visto = {}
    originales = {}
    for clave, nombre in (("stamp", "_score_unfair_stamp_play"),
                          ("xerosic", "_score_xerosic_play")):
        originales[nombre] = getattr(m, nombre)

        def espia(ctx, _orig=originales[nombre], _clave=clave):
            r = _orig(ctx)
            visto[_clave] = r
            return r

        setattr(m, nombre, espia)
    try:
        m.agent(obs)
    finally:
        for nombre, orig in originales.items():
            setattr(m, nombre, orig)
    return visto


# ---------------------------------------------------------------------------
# 1. El caso real: mano rival de 18
# ---------------------------------------------------------------------------

def test_con_mano_rival_gigante_el_sello_cede_el_orden_a_xerosic():
    s = _scores(_obs())
    assert s["xerosic"] > 0, s
    assert s["stamp"] <= 0, s
    assert s["xerosic"] > s["stamp"], s


def test_el_veto_del_sello_no_lo_resucitan_los_ajustes():
    """`bonus_matchup` (+400 vs Alakazam) sacaba el veto (−1) a +399."""
    s = _scores(_obs())
    assert s["stamp"] <= 0, s


def test_tras_jugar_xerosic_el_sello_se_juega_el_mismo_turno():
    """El veto es de ORDEN y se auto-revoca: con el hueco de Supporter ya
    gastado, el Sello recupera su score normal."""
    s = _scores(_obs(supporter_played=True))
    assert s["stamp"] > 0, s


# ---------------------------------------------------------------------------
# 2. Los bordes del umbral
# ---------------------------------------------------------------------------

def test_justo_en_el_umbral_el_orden_se_invierte():
    s = _scores(_obs(op_hand=m.XEROSIC_STAMP_ORDEN_MIN_OP_HAND))
    assert s["xerosic"] > 0 and s["stamp"] <= 0, s


def test_bajo_el_umbral_vuelve_la_conducta_antigua():
    """Con la mano rival pequeña el mill no paga el hueco de Supporter: manda
    el Sello y Xerosic cede, como antes."""
    s = _scores(_obs(op_hand=m.XEROSIC_STAMP_ORDEN_MIN_OP_HAND - 1))
    assert s["stamp"] > 0, s
    assert s["xerosic"] <= 0, s


# ---------------------------------------------------------------------------
# 3. Controles: el veto es del ORDEN, no del Sello
# ---------------------------------------------------------------------------

def test_sin_xerosic_en_mano_el_sello_se_juega_normal():
    s = _scores(_obs(sin_xerosic=True))
    assert s["stamp"] > 0, s


def test_si_xerosic_no_va_a_jugarse_el_sello_no_cede():
    """Guard de `cede_el_orden_a_xerosic`: si algún otro rail tumba a Xerosic a
    `XEROSIC_SCORE_LAST_RESORT` (p.ej. `alakazam_cede_a_gusteo_ganador`, donde
    el turno lo decide un Boss's), el Sello no le cede el paso a nadie."""
    orig = m._score_xerosic_play
    m._score_xerosic_play = lambda ctx: m.XEROSIC_SCORE_LAST_RESORT
    try:
        obs = _obs()
        visto = {}
        orig_stamp = m._score_unfair_stamp_play

        def espia(ctx):
            r = orig_stamp(ctx)
            visto["stamp"] = r
            return r

        m._score_unfair_stamp_play = espia
        try:
            m.agent(obs)
        finally:
            m._score_unfair_stamp_play = orig_stamp
    finally:
        m._score_xerosic_play = orig
    assert visto["stamp"] > 0, visto


def test_el_fixture_tiene_de_verdad_las_dos_cartas_y_la_mano_gigante():
    """Sin Sello + Xerosic en mano y mano rival grande el test no mide nada."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    mano = [c["id"] for c in o["current"]["players"][yo]["hand"]]
    assert UNFAIR_STAMP in mano, mano
    assert XEROSIC in mano, mano
    assert o["current"]["players"][1 - yo]["handCount"] >= 18
    assert o["current"]["supporterPlayed"] is False
