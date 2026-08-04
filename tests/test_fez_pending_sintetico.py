"""El traspaso de `_ub_fez_pending` ENTRE menús, reconstruido con StateBuilder.

Cubre lo único que quedó dormido al rotar los registros locales: la cadena
**Ultra Ball → Fezandipiti ex → bajarlo**, que por definición necesita DOS menús
consecutivos y por eso no cabe en un fixture de una sola observación.

El test original (`test_fez_cadena_ultra_ball_flip_the_script.py`) reproducía esa
secuencia desde `registros/registro_006_pasos_086_hasta_104.json`. Los registros
son datos locales transitorios —`utils/split_turns.py` los reescribe con cada
partida nueva— y el episodio 88710543 ya no está ni en `registros/` ni en
`log/`, así que aquel test quedó en `skipif`. Aquí la secuencia se FABRICA, que
además la hace inmune a la próxima rotación.

Escenario (misma forma que el registro_006 pasos 90-91 vs Mega Lucario):

    NOSOTROS                                  RIVAL
    activo  Hydrapple ex, 2 {G}               activo  Mega Lucario ex 340/340
    banca   Meowth ex, Meganium,              banca   Riolu
            Teal Mask Ogerpon ex x2
    Nos noquearon el turno anterior -> Flip the Script VIVA.

**Menú A** — se juega la Ultra Ball y el fetch elige **Fezandipiti ex**: eso
arma `_ub_fez_pending`, la marca de "esta búsqueda YA está pagada".

**Menú B** — el MAIN siguiente, con la mano reducida a **Unfair Stamp +
Fezandipiti ex**: el bug original era que el Sello se jugaba primero y barajaba
de vuelta al mazo el Fezandipiti recién cavado, con la Ultra Ball ya pagada.

**Hallazgo al reconstruirlo:** apagando `_ub_fez_pending` a mano, el Fezandipiti
se baja IGUAL. La cadena tiene DOS defensas independientes y la primera basta en
todos los estados que se pueden construir:

  1. `_us_pokemon_jugable`, dentro del scorer del propio Sello: con un Pokémon
     JUGABLE en la mano (aquí el Fez), el Sello cae a su banda baja (**2000**)
     en vez de la alta (**7500** = "la mano no tiene nada mejor que hacer"), y
     ya solo por eso pierde contra bajar el cuerpo.
  2. `_ub_fez_pending` (22000, aplicado DESPUÉS de todos los vetos de la rama —
     que son justo los que contradicen una búsqueda ya pagada): la red para
     cuando algún veto de ORDEN tumbe el PLAY.

Por eso el control NO es "sin el flag gana el Sello" (sería falso): se fija la
BANDA del Sello, que es observable y sí discrimina — 2000 con el Fez jugable,
7500 con la banca llena, donde el Fez ya no se puede bajar.

Nota de estado: `ko_last_turn` no se puede inyectar directamente (`agent()` lo
recalcula de `_ko_detected_this_turn` y de los logs), y se reinicia al detectar
cambio de turno. Se fija `pre_turn` al turno en curso para que ese reinicio no
dispare, igual que con `_grass_attaches_this_turn` en el test de Cruel Arrow.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import instalar
from state_builder import Escenario, pk, G

FEZ = m.Fezandipiti_ex
STAMP = m.Unfair_Stamp
HYDRA = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
APPLIN = m.Applin
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEGA_LUCARIO = 678
RIOLU = m.Riolu

TURNO = 6


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
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _armar_turno():
    """Deja el estado de turno como si el rival nos hubiera noqueado: Flip the
    Script viva y sin que `agent()` reinicie el turno al primer menu."""
    m.pre_turn = TURNO
    m._ko_detected_this_turn = True


def _campo(esc, banca_llena=False):
    """El tablero comun a los dos menus."""
    extra = (m.Tapu_Bulu,) if banca_llena else ()
    return (esc
            .mi_activo(pk(HYDRA, energias=[G, G], fisicas=2,
                          pre_evo=[APPLIN, DIPPLIN]))
            .mi_banca(MEOWTH,
                      pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                      pk(OGERPON, energias=[G, G, G, G], fisicas=4),
                      OGERPON, *extra)
            .op_activo(pk(MEGA_LUCARIO, hp=340, max_hp=340))
            .op_banca(RIOLU)
            .op_zonas(mano=5, mazo=30, premios=4))


def _menu_fetch():
    """Menu A: el fetch de la Ultra Ball, con Fezandipiti ex en el mazo."""
    esc = Escenario(turno=TURNO, paso=90, tac=5, premios_propios=3)
    return (_campo(esc)
            .mi_mano(STAMP)
            .mazo(FEZ, CHIKORITA, APPLIN)
            # `fetch_ultra_ball()` consume una Ultra Ball del pool (la carta "en
            # efecto"), asi que va ANTES de `resto_al_descarte()`, que se lleva
            # todo lo que sobra. Al reves, la contabilidad estricta del builder
            # se queda sin copias y aborta.
            .fetch_ultra_ball()
            .resto_al_descarte()
            .construir())


def _menu_bajar(banca_llena=False):
    """Menu B: el MAIN siguiente. Mano FINA (Sello + Fez) para que el Sello
    puntue en su banda alta y el test discrimine de verdad."""
    esc = Escenario(turno=TURNO, paso=91, tac=6, premios_propios=3)
    return (_campo(esc, banca_llena=banca_llena)
            .mi_mano(STAMP, FEZ)
            .mazo(CHIKORITA, APPLIN)      # `resto_al_descarte()` lo exige
            .resto_al_descarte()
            .menu_mano()
            .construir())


def _jugada(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    if o["type"] == int(m.OptionType.PLAY):
        yo = obs["current"]["yourIndex"]
        return ("PLAY", obs["current"]["players"][yo]["hand"][o["index"]]["id"])
    if o["type"] == int(m.OptionType.CARD):
        return ("CARTA", obs["select"]["deck"][o["index"]]["id"])
    return (o["type"], None)


# ---------------------------------------------------------------------------
# 1. El escenario: sin estas condiciones la cadena no existe
# ---------------------------------------------------------------------------

def test_el_escenario_tiene_flip_the_script_viva_y_hueco_en_banca():
    _armar_turno()
    obs = _menu_fetch()
    m.agent(obs)
    assert m.ko_last_turn is True                 # condicion de Flip the Script
    yo = obs["current"]["yourIndex"]
    mio = obs["current"]["players"][yo]
    assert len([b for b in mio["bench"] if b]) < 5          # cabe el Fez
    assert not any(b and b["id"] == FEZ for b in mio["bench"])
    assert any(o["type"] == int(m.OptionType.CARD)
               for o in obs["select"]["option"])


# ---------------------------------------------------------------------------
# 2. La cadena, menu a menu
# ---------------------------------------------------------------------------

def test_menuA_la_ultra_ball_busca_el_fezandipiti_y_arma_el_pendiente():
    _armar_turno()
    obs = _menu_fetch()
    assert _jugada(obs, m.agent(obs)) == ("CARTA", FEZ)
    assert m._ub_fez_pending is True


def test_menuB_el_cuerpo_pagado_baja_antes_que_el_sello():
    _armar_turno()
    m.agent(_menu_fetch())                # arma `_ub_fez_pending`
    obs = _menu_bajar()
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ)


# ---------------------------------------------------------------------------
# 3. Las DOS defensas de la cadena
# ---------------------------------------------------------------------------
# Al reconstruir el escenario se comprobó algo que el test del registro no
# distinguía: apagando `_ub_fez_pending` a mano, el Fezandipiti se baja IGUAL.
# La cadena está protegida por dos mecanismos independientes y el primero basta
# en los estados alcanzables:
#
#   1) `_us_pokemon_jugable` dentro del scorer del Sello: con un Pokémon
#      JUGABLE en la mano (aquí el propio Fez), el Sello cae a su banda baja
#      (2000) en vez de la alta (7500 = "la mano no tiene nada mejor que
#      hacer"). Solo por eso ya pierde contra bajar el cuerpo.
#   2) `_ub_fez_pending` (22000, después de todos los vetos de la rama): la
#      red de seguridad para cuando algún veto de ORDEN tumbe el PLAY.
#
# Por eso el control NO puede ser "sin el flag gana el Sello": sería falso. Lo
# que sí se puede fijar —y es lo que de verdad protege la cadena— es la banda
# del Sello, que es observable y discrimina.

def test_el_sello_cede_al_cuerpo_jugable_y_esa_es_la_primera_defensa():
    """Primera línea: con el Fez JUGABLE el Sello puntúa en banda baja."""
    _armar_turno()
    m._ub_fez_pending = False
    assert _score_del_sello(_menu_bajar()) == 2000


def test_con_la_banca_llena_el_sello_recupera_su_banda_alta():
    """Contrafactual que prueba que el 2000 lo causa el cuerpo jugable y no
    otra cosa: con la banca a 5 el Fez ya no se puede bajar, la mano se queda
    sin nada que hacer y el Sello sube a su defecto (7500)."""
    _armar_turno()
    m._ub_fez_pending = False
    assert _score_del_sello(_menu_bajar(banca_llena=True)) == 7500


def _score_del_sello(obs):
    visto = {}
    orig = m._score_unfair_stamp_play

    def espia(ctx):
        r = orig(ctx)
        visto.setdefault("s", r)
        return r

    _rest_score_unfair_stamp_play = instalar("_score_unfair_stamp_play", espia)
    try:
        m.agent(obs)
    finally:
        _rest_score_unfair_stamp_play()
    return visto.get("s")
