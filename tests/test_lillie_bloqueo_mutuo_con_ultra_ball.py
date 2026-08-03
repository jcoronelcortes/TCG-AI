"""Lillie's <-> Ultra Ball: dos vetos que se ceden el paso y matan el turno.

Escenario (`registros/registro_010_pasos_103_hasta_116.json`, paso 116, turno 10,
PERDIDA vs Dragapult -- episodio 89079426):

    NOSOTROS                                   RIVAL
    activo Teal Mask Ogerpon ex 120/210, 4 ef. activo Dragapult ex 320, 2 en.
    banca  Fezandipiti ex, Meowth ex,          banca  Budew, Dragapult ex,
           Meganium, Meowth ex,                       Munkidori, Drakloak x2
           **Applin recién bajado**
    mano   **Ultra Ball x3**, Hydrapple ex,
           **Lillie's Determination**

La Lillie's venía del *Last-Ditch Catch* de un Meowth ex bajado ese mismo turno
(paso 107) y el turno se cerró **atacando**, con el Supporter muerto en la mano.

Causa: un **bloqueo mutuo** entre dos vetos que, cada uno por su lado, son
correctos:

  * `ultra_ball_completa_linea` (regla de Lillie's) -- "no juegues Lillie's:
    barajaría la Ultra Ball con la que voy a montar Applin → Dipplin →
    Hydrapple ex". Se enciende porque el hueco existe **sobre el papel**: Applin
    en juego, Hydrapple ex en mano, Dipplin en el mazo.
  * `_ub_cancel_lillie` (veto de la Ultra Ball) -- "no juegues la Ultra Ball: su
    coste de descartar 2 se llevaría la Lillie's".

Las dos disparan a la vez, ninguna carta se juega y el hueco de Supporter del
turno se tira a la basura. Es el mismo fallo que ya se corrigió en el par
Sello ↔ Supporter (`_sello_merece_jugarse`: «se cedía el paso a una carta que ya
no se iba a jugar»).

Lo tapaba de casualidad `_ld_supp_comprometido` -- el piso de score que obliga a
jugar el Supporter que trajo un *Last-Ditch* de ESTE turno --, así que el bloqueo
seguía vivo para cualquier Lillie's que no viniera de un Meowth ex. Por eso el
test principal comprueba la jugada **con la marca anulada**: mide la regla, no la
red que la tapaba.

Arreglo: la deferencia solo tiene sentido si la Ultra Ball puede jugarse por algo
que NO sea esta misma Lillie's. Con **dos guardas** que son justo lo que separa
este paso de los escenarios en que el veto sí debe aguantar:

  1. **Solo el veto circular.** No se consulta el score completo de la Ultra
     Ball: los demás vetos por COSTE son de este instante y se levantan solos
     dentro del turno. En el registro_004 paso 47 -- el caso que creó la regla --
     la Ultra Ball también está en −1, pero por `_ub_cancel_meowth`: el agente
     baja el Meowth ex primero y entonces la Ultra Ball ya es jugable. Un gate
     por score habría tirado esa línea (lo cubre
     `test_step47_does_not_shuffle_meganium_line_with_lillie`).
  2. **Solo si la Lillie's es el ÚNICO Supporter de la mano.** Con otro
     Supporter al lado el hueco del turno se usa igual, así que vetar la
     Lillie's no desperdicia nada y además conserva la línea (lo cubren los
     controles de `test_pesca_de_remate_probabilistica`, donde hay un Boss's
     Orders en la mano).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from golden_corpus import reset_agente

_REGISTRO = ROOT / "registros" / "registro_010_pasos_103_hasta_116.json"

LILLIE = m.Lillie_Determination
ULTRA_BALL = m.Ultra_Ball
HYDRAPPLE = m.Hydrapple_ex
APPLIN = m.Applin
BOSS = m.Boss_Orders

pytestmark = pytest.mark.skipif(
    not _REGISTRO.exists(),
    reason="registro local rotado (registros/ es transitorio)")


def _frames():
    data = json.load(open(_REGISTRO, encoding="utf-8"))
    return [it["observation"] for st in data["steps"] for it in st
            if it.get("status") == "ACTIVE"
            and isinstance(it.get("observation"), dict)
            and (it["observation"].get("current") or {}).get("yourIndex") == 0
            and it["observation"].get("select")]


def _replay(anular_marca_ld):
    """Reproduce el turno entero y devuelve (obs, elección) del último menú."""
    reset_agente(m)
    ultimo = None
    for obs in _frames():
        if anular_marca_ld:
            m._ld_supp_comprometido = 0
        ultimo = (obs, m.agent(obs))
    return ultimo


def _carta_jugada(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    if o.get("type") != int(m.OptionType.PLAY):
        return None
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["hand"][o["index"]]["id"]


# ---------------------------------------------------------------------------
# 1. El escenario: sin estas piezas no hay bloqueo que romper
# ---------------------------------------------------------------------------

def test_el_paso_116_tiene_las_dos_mitades_del_bloqueo():
    obs = _frames()[-1]
    yo = obs["current"]["players"][0]
    mano = [c["id"] for c in yo["hand"]]
    campo = [p["id"] for p in yo["active"] + [b for b in yo["bench"] if b]]

    # el hueco de línea que enciende `ultra_ball_completa_linea`...
    assert ULTRA_BALL in mano and HYDRAPPLE in mano
    assert APPLIN in campo and m.Dipplin not in campo
    # ...y la Lillie's como ÚNICO Supporter de la mano.
    assert mano.count(LILLIE) == 1
    assert not any(s in mano for s in m._SUPP_PLAY_IDS if s != LILLIE)
    assert obs["current"]["supporterPlayed"] is False
    # El Applin apareció este turno: por eso la Ultra Ball no monta nada hoy.
    assert next(b for b in yo["bench"] if b["id"] == APPLIN)["appearThisTurn"]


# ---------------------------------------------------------------------------
# 2. La corrección, medida SIN la red que la tapaba
# ---------------------------------------------------------------------------

def test_paso116_juega_lillie_aunque_no_venga_de_un_last_ditch():
    obs, eleccion = _replay(anular_marca_ld=True)
    assert _carta_jugada(obs, eleccion) == LILLIE, (
        "con la Lillie's como único Supporter y la Ultra Ball vetada por esa "
        "misma Lillie's, ceder el paso tira el hueco de Supporter del turno")


def test_paso116_tambien_la_juega_por_la_via_del_last_ditch():
    """La red `_ld_supp_comprometido` sigue en pie: las dos rutas coinciden."""
    obs, eleccion = _replay(anular_marca_ld=False)
    assert _carta_jugada(obs, eleccion) == LILLIE


# ---------------------------------------------------------------------------
# 3. Las dos guardas, cada una con su contraste
# ---------------------------------------------------------------------------

def _ctx_lillie_del_paso116(mutar=None):
    """Construye el `_CtxLillie` real del paso 116 y devuelve su flag."""
    reset_agente(m)
    frames = _frames()
    capturado = {}
    orig = m._CtxLillie

    class _Spy(orig):
        def __init__(self, ctx):
            super().__init__(ctx)
            capturado["v"] = self.ub_gapped_line

    for i, obs in enumerate(frames):
        if i == len(frames) - 1:
            if mutar is not None:
                obs = mutar(json.loads(json.dumps(obs)))
            m._CtxLillie = _Spy
            capturado.clear()
            try:
                m.agent(obs)
            finally:
                m._CtxLillie = orig
        else:
            m.agent(obs)
    return capturado.get("v")


def test_guarda2_con_otro_supporter_en_mano_el_veto_aguanta():
    """Contraste de la segunda guarda: basta añadir un Boss's Orders a la mano
    para que el hueco del turno deje de desperdiciarse -- y entonces conservar
    la línea vuelve a ser lo correcto."""
    def con_boss(obs):
        yo = obs["current"]["players"][0]
        yo["hand"].append({"id": BOSS, "playerIndex": 0, "serial": 31})
        return obs

    assert _ctx_lillie_del_paso116() is False, (
        "sin Supporter de repuesto el bloqueo se rompe")
    assert _ctx_lillie_del_paso116(mutar=con_boss) is True, (
        "con un Boss's al lado el Supporter del turno se juega igual: el veto "
        "de Lillie's no desperdicia nada y conserva la línea")


def test_guarda1_el_veto_por_coste_ajeno_no_rompe_el_bloqueo():
    """Contraste de la primera guarda, sobre el paso que creó la regla: allí la
    Ultra Ball también está vetada, pero por `_ub_cancel_meowth` (su coste se
    llevaría el Meowth ex), no por la Lillie's. Ese veto se levanta solo dentro
    del turno -- se baja el Meowth primero -- así que la línea se conserva."""
    fx = (ROOT / "tests" / "fixtures"
          / "alakazam_step47_ultraball_completes_line_before_lillie.json")
    obs = json.load(open(fx, encoding="utf-8"))["observation"]
    reset_agente(m)

    vistos = []
    _ub = m._score_ultra_ball_play
    m._score_ultra_ball_play = lambda c: (
        vistos.append((_ub(c), m._ub_cancel_lillie(c), m._ub_cancel_meowth(c)))
        or vistos[-1][0])
    try:
        eleccion = m.agent(obs)
    finally:
        m._score_ultra_ball_play = _ub

    # La Ultra Ball está vetada, pero NO por la Lillie's.
    reales = [v for v in vistos if v[0] <= 0]
    assert reales, "el escenario exige una Ultra Ball vetada"
    assert all(not cancel_lillie for _, cancel_lillie, _ in reales)
    assert any(cancel_meowth for _, _, cancel_meowth in reales)
    # ...así que la Lillie's SIGUE vetada y la línea se conserva.
    assert _carta_jugada(obs, eleccion) != LILLIE
