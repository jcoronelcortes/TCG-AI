"""Festival Grounds + Dipplin: el rival ATACA DOS VECES, así que el promovido
tiene que llegar vivo a nuestro turno.

Escenario (log 88971843, paso 117, turno 9, PERDIDA vs *Festival Lead*):

    NOSOTROS (3 premios)                 RIVAL (**1 premio**)
    activo  -- (nos acaban de noquear    activo  Dipplin 80 PV, 1 Planta,
            el Teal Mask Ogerpon ex)             **Brave Bangle**
    banca   Meganium  160 PV, 0 en       banca   5 Pokémon
            Dipplin    80 PV, 2 en       estadio **Festival Grounds** (suyo)
            Chikorita  70 PV, 0 en
            Tapu Bulu 140 PV, 2 en

*Do the Wave* = 20 × SU banca = **20·5 = 100**; +30 de *Brave Bangle* contra
nuestros ex = 130, que fue lo que remató al Ogerpon ex a 70 PV (log: `-130`).
Y *Festival Lead* — "si el primer ataque noquea, ataca **otra vez** tras elegir
el nuevo Activo" — le da un segundo *Do the Wave* de 100 **antes de que
juguemos**. Con el rival a 1 premio, cualquier cuerpo que muera ahí pierde la
partida.

El agente subía el **Dipplin de 80 PV** (muere a los 100) teniendo detrás un
**Tapu Bulu de 140** que aguanta y que, con un solo adjunte (×2 por *Wild
Growth*), llega a 4 energías y remata con *Wood Hammer* 220.

Tres ceguera encadenadas, las tres corregidas aquí:

1. *Do the Wave* tiene **daño impreso 0** en `attack_table` (es "20×"), así que
   `_op_active_attack_damage_to` proyectaba **0** contra los cuatro candidatos y
   toda la maquinaria de supervivencia (`_promo_survives`, la prudencia de
   `_pb_key`, `_ev_survivor_asis`, `_ko_prefer_basic_general`) se apagaba en
   silencio. Es el mismo agujero que ya se tapó para *Powerful Hand*; ahora la
   escala viaja en el flag por turno `_op_bench_count`.
2. **Brave Bangle** (+30 al ex activo, portador sin Rule Box) era invisible:
   solo se modelaba Maximum Belt.
3. La rama de promoción está escrita sobre la premisa *"la promoción ocurre en
   el turno RIVAL, donde nadie ataca ya"*. Bajo Festival Lead es **falsa**:
   `op_double_attack_pending` la apaga — el condenado deja de ser candidato a
   "mejor atacante" y pierde las dos exenciones (`PROMO_KO_BONUS` y el remate
   garantizado de `_promote_setup_ko_attacker`).

Además, `_promo_kos_op` proyectaba *Do the Wave* del PROMOVIDO con la banca sin
descontar el propio cuerpo (20·4 = 80 en vez de 20·3 = 60): creía que el Dipplin
noqueaba al Dipplin rival de 80 PV y le regalaba `PROMO_KO_BONUS`. Los otros dos
sitios que proyectan a un promovido ya restaban 1.
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
    m._op_bench_count = 0
    m._festival_grounds_in_play = False
    yield
    m._init_cartas_tracking()


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    if mut.get("sin_estadio"):
        # Mismo tablero SIN Festival Grounds: sin el estadio no hay Festival
        # Lead y el segundo ataque no existe.
        o["current"]["stadium"] = []
    if mut.get("rival_sin_bangle"):
        o["current"]["players"][1 - yo]["active"][0]["tools"] = []
    return o


def _banca(obs):
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["bench"]


def _elegido(obs, eleccion):
    """Carta de banca que corresponde a la opción elegida."""
    opt = obs["select"]["option"][eleccion[0]]
    return _banca(obs)[opt["index"]]


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_la_promocion_bajo_festival_grounds():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    rival = o["current"]["players"][1 - yo]

    assert not mio["active"]                       # nos noquearon el activo
    assert o["select"]["context"] == 4             # menu de promocion

    # Festival Grounds en mesa -- y es del RIVAL: el estadio es COMPARTIDO.
    assert [c["id"] for c in o["current"]["stadium"]] == [m.Festival_Grounds]
    assert o["current"]["stadium"][0]["playerIndex"] == 1 - yo

    # Su activo es el Dipplin con Festival Lead y Brave Bangle.
    assert rival["active"][0]["id"] == DIPPLIN
    assert DIPPLIN in m.FESTIVAL_LEAD_IDS
    assert [t["id"] for t in rival["active"][0]["tools"]] == [m.Brave_Bangle]
    assert not m._tiene_rule_box(DIPPLIN)          # el Bangle SI le aplica

    # Rival a MATCH POINT: un KO mas y perdemos.
    assert len(rival["prize"]) == 1

    # La banca: dos que aguantan 100 (Meganium, Tapu) y dos que no.
    assert [(b["id"], b["hp"]) for b in mio["bench"]] == [
        (MEGANIUM, 160), (DIPPLIN, 80), (CHIKORITA, 70), (TAPU, 140)]
    assert len(rival["bench"]) == 5                # Do the Wave = 20 x 5 = 100


def test_do_the_wave_tiene_dano_impreso_cero():
    """La causa raíz: sin modelarlo, la proyección era 0 contra todos."""
    assert (m.attack_table[m.DO_THE_WAVE_ATTACK_ID].damage or 0) == 0
    assert m.card_table[DIPPLIN].attacks == [m.DO_THE_WAVE_ATTACK_ID]


# ---------------------------------------------------------------------------
# 2. La proyección de daño
# ---------------------------------------------------------------------------

def test_proyecta_do_the_wave_y_el_brave_bangle():
    obs = _obs()
    m.agent(obs)                                   # refresca los flags por turno
    assert m._op_bench_count == 5
    assert m._festival_grounds_in_play is True

    yo = obs["current"]["yourIndex"]
    op_act = m.to_observation_class(obs).current.players[1 - yo].active[0]

    # 20 x 5 = 100 contra cualquier cuerpo NO-ex...
    for pk in m.to_observation_class(obs).current.players[yo].bench:
        if pk.id not in m.OUR_EX_IDS:
            assert m._op_active_attack_damage_to(op_act, pk) == 100

    # ...y 130 contra un ex nuestro (Brave Bangle +30), que es el golpe REAL
    # que remató al Teal Mask Ogerpon ex (log: value -130).
    assert m._op_active_attack_damage_to(op_act, m._ProjTarget(OGERPON)) == 130

    # Sin el Bangle vuelve a ser 100 tambien contra el ex.
    obs2 = _obs(rival_sin_bangle=True)
    m.agent(obs2)
    op_act2 = m.to_observation_class(obs2).current.players[1 - yo].active[0]
    assert m._op_active_attack_damage_to(op_act2, m._ProjTarget(OGERPON)) == 100


def test_brave_bangle_no_suma_si_el_portador_tiene_rule_box():
    """La tool solo cuenta si el portador NO tiene Rule Box."""
    assert m._tiene_rule_box(OGERPON) is True      # Pokemon ex
    assert m._tiene_rule_box(TAPU) is False
    assert m._tiene_rule_box(MEGANIUM) is False


# ---------------------------------------------------------------------------
# 3. La decisión
# ---------------------------------------------------------------------------

def test_promueve_el_tapu_que_aguanta_y_no_el_dipplin_condenado():
    obs = _obs()
    elegido = _elegido(obs, m.agent(obs))
    assert elegido["id"] == TAPU, (
        "bajo Festival Lead el promovido come un Do the Wave ANTES de que "
        "juguemos: el Dipplin de 80 PV muere y con el rival a 1 premio eso es "
        "la partida")
    assert elegido["hp"] > 100                     # sobrevive al segundo golpe


def test_el_tapu_promovido_remata_al_turno_siguiente():
    """No es solo el más tanque: con un adjunte llega a Wood Hammer."""
    obs = _obs()
    yo = obs["current"]["yourIndex"]
    tapu = next(b for b in _banca(obs) if b["id"] == TAPU)
    rival_act = obs["current"]["players"][1 - yo]["active"][0]

    # Meganium en juego -> Wild Growth: una Planta fisica vale 2 efectivas.
    assert any(b["id"] == MEGANIUM for b in _banca(obs))
    assert len(tapu["energies"]) + 2 >= m.ATTACK_ENERGY_REQ[TAPU]
    assert 220 >= rival_act["hp"]                  # Wood Hammer lo remata


# ---------------------------------------------------------------------------
# 4. El contra-estadio: Forest of Vitality apaga Festival Lead de raíz
# ---------------------------------------------------------------------------

def test_festival_grounds_hace_urgente_el_contra_estadio():
    """`_contra_estadio_urgente` gobierna las DOS caras: no soltar el Forest en
    un descarte forzado y no vetar su jugada."""
    # Estadio hostil y sin Forest nuestro en mesa -> urgente.
    assert m._contra_estadio_urgente(False, False, False, True) is True
    # Con nuestro Forest ya en mesa no hay nada que levantar.
    assert m._contra_estadio_urgente(False, False, True, True) is False
    # Sin la línea Applin/Dipplin rival el flag llega apagado: el estadio es de
    # DOBLE FILO y quitarlo apagaría también nuestro Dipplin.
    assert m._contra_estadio_urgente(False, False, False, False) is False
    # No rompe a los dos hermanos que ya estaban.
    assert m._contra_estadio_urgente(True, False, False, False) is True
    assert m._contra_estadio_urgente(False, True, False, False) is True


def test_apagar_festival_lead_va_antes_que_la_cadena_evolutiva():
    """Prioridad de la jugada del Forest: la cadena se cobra el próximo turno,
    el doble ataque nos mata en este. Por debajo del motor Meowth, que además
    es irreversible."""
    nombres = [r.nombre for r in m._REGLAS_FOREST_PLAY]
    assert nombres.index("reactivar_motor_meowth_vs_watchtower") \
        < nombres.index("apagar_festival_lead") \
        < nombres.index("habilita_cadena_evolutiva") \
        < nombres.index("reemplazar_estadio_rival")


def test_el_flag_hostil_exige_la_linea_rival():
    """El fixture tiene Dipplin rival en el activo -> hostil. Sin ningún
    Applin/Dipplin suyo a la vista, el estadio deja de contar como hostil."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv = o["current"]["players"][1 - yo]
    assert riv["active"][0]["id"] == DIPPLIN

    # Sin línea rival visible: activo neutro, banca sin Applin/Dipplin y
    # descarte limpio de la línea.
    o2 = _obs()
    riv2 = o2["current"]["players"][1 - yo]
    riv2["active"][0]["id"] = CHIKORITA
    riv2["bench"] = [b for b in riv2["bench"]
                     if b["id"] not in (DIPPLIN, m.Applin)]
    riv2["discard"] = [c for c in riv2["discard"]
                       if c["id"] not in (DIPPLIN, m.Applin)]
    m.agent(o2)
    # El estadio sigue en mesa (el flag de proyección no cambia)...
    assert m._festival_grounds_in_play is True
    # ...pero ya no hay nadie que aproveche Festival Lead: sin Dipplin rival la
    # proyección de Do the Wave no aplica a su activo.
    op_act2 = m.to_observation_class(o2).current.players[1 - yo].active[0]
    tapu = next(b for b in m.to_observation_class(o2).current.players[yo].bench
                if b.id == TAPU)
    assert m._op_active_attack_damage_to(op_act2, tapu) < 100


def test_sin_festival_grounds_no_se_apaga_la_premisa():
    """Control: el veto es del ESTADIO, no del matchup.

    Sin Festival Grounds no hay segundo ataque, la promoción se resuelve al
    final del turno rival y volvemos a la conducta de siempre -- el candidato
    condenado deja de estar vetado como "mejor atacante".
    """
    obs = _obs(sin_estadio=True)
    m.agent(obs)
    assert m._festival_grounds_in_play is False
