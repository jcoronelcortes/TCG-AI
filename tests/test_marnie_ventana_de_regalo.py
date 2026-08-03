"""La VENTANA DE REGALO: el goteo de Froslass y el daño movible de Munkidori.

Escenario (`registros/marnie/partida_2`, paso 121, turno 10, PERDIDA):

    NOSOTROS (4 premios)                    RIVAL (5 premios)
    activo  Hydrapple ex   70/330, E2       activo  Grimmsnarl ex 300/320, E2
    banca   Meganium        90/160          banca   Froslass  90/90
            Ogerpon ex      80/210, E10             Morgrem  100/100, E2
            Ogerpon ex     130/210, E6              Froslass  90/90
            Meowth ex       70/170                  Munkidori 80/110, E1
            Fezandipiti ex 170/210                  Munkidori 90/110, sin energía

El agente eligió **Teal Dance sobre el Ogerpon ex de banca a 80 PV**. Ese cuerpo
murió ese mismo turno —20 de Freezing Shroud + 60 movidos por dos Munkidori—
llevándose **2 premios y 5 Energías Planta** al descarte. La Ripening Charge del
Hydrapple activo estaba disponible y sin usar: +30 lo dejaba en 110, fuera de la
ventana de 100.

Causa: `_ripen_heal_serial` medía la amenaza a la banca con
`_op_bench_snipe_dmg` = **30** (solo el snipe de Shadow Bullet). Ningún cuerpo
por encima de 30 PV entraba jamás al detector, así que en tres partidas usamos
la curación **una** vez mientras encajábamos 410/620/60 de daño de contadores.

Las tres piezas que faltaban, ahora en `_ventana_de_regalo`:

1. **Freezing Shroud dispara en CADA Chequeo Pokémon y hay DOS por ronda** (fin
   de nuestro turno y fin del suyo): `10 × n_froslass × 2`. Solo lo pagan los
   cuerpos de `OUR_ABILITY_IDS`.
2. **Adrena-Brain mueve hasta 30 a CUALQUIER cuerpo nuestro**, una vez por
   Munkidori energizado — y un Munkidori seco en mesa vale una activación más,
   porque al rival le queda su adjunte del turno (es exactamente lo que pasó).
3. El **Tera** del Ogerpon en banca previene daño *de ataques*: corta el snipe
   de 30, nunca los contadores puestos ni los movidos.

Y el desempate entre candidatos pasa a ser **premios primero**: negar los 2 del
Ogerpon ex vale más que negar el 1 del Meganium.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m
from golden_corpus import reset_agente
from state_builder import G, Escenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_ripening_cura_el_ogerpon_de_banca_step121.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
APPLIN = m.Applin
DIPPLIN = m.Dipplin
TAPU = m.Tapu_Bulu
FROSLASS = m.Froslass
MUNKIDORI = m.Munkidori
GRIMMSNARL = m.Grimmsnarl_ex
IMPIDIMP = m.Marnies_Impidimp
D = int(m.EnergyType.DARKNESS)


@pytest.fixture(autouse=True)
def reset_main_state():
    reset_agente(m)
    yield
    m._init_cartas_tracking()


def _fixture_obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8")))


def _correr_fixture():
    d = _fixture_obs()
    if d.get("observacion_previa"):
        m.agent(d["observacion_previa"])
    obs = d["observation"]
    return obs, m.agent(obs)


def _opcion(obs, eleccion):
    return obs["select"]["option"][eleccion[0]]


# --------------------------------------------------------------------------
# Fase A: percepción
# --------------------------------------------------------------------------

def test_percepcion_mide_el_goteo_y_el_dano_movible():
    """Dos Froslass = 40 por ronda; dos activaciones de Adrena-Brain = 60."""
    _correr_fixture()
    assert m._op_chip_per_round == 40, "10 x 2 Froslass x 2 chequeos"
    # Un Munkidori con energía + uno seco (al rival le queda su adjunte).
    assert m._op_movable_dmg == 60, "30 x 2 activaciones de Adrena-Brain"


def test_la_ventana_del_ogerpon_de_banca_lo_alcanza():
    """80 PV dentro de una ventana de 100; con +30 sale (110 > 100)."""
    _correr_fixture()

    class _P:
        pass
    p = _P()
    p.id = OGERPON
    p.hp, p.maxHp = 80, 210
    # El Tera anula el snipe en banca: la ventana es chip + movible.
    ventana = m._ventana_de_regalo(p, False, m._op_bench_snipe_dmg)
    assert ventana == 100
    assert p.hp <= ventana                       # dentro de la ventana
    assert min(p.maxHp, p.hp + m.RIPENING_HEAL) > ventana   # con +30 sale


def test_el_tera_en_banca_no_para_los_contadores():
    """El Tera corta el snipe (daño de ataque), nunca el goteo ni lo movible."""
    _correr_fixture()

    class _P:
        pass
    og, meg = _P(), _P()
    og.id, og.hp, og.maxHp = OGERPON, 80, 210
    meg.id, meg.hp, meg.maxHp = MEGANIUM, 90, 160
    # Mismo puesto (banca) y mismo snipe proyectado: el Ogerpon se ahorra los
    # 30 del snipe, pero paga el mismo goteo y el mismo daño movible.
    assert m._ventana_de_regalo(og, False, 30) == 40 + 60
    assert m._ventana_de_regalo(meg, False, 30) == 30 + 40 + 60


def test_sin_habilidad_no_se_paga_el_peaje_de_froslass():
    """Tapu Bulu, Chikorita, Bayleef y Applin no están en OUR_ABILITY_IDS."""
    _correr_fixture()

    class _P:
        pass
    for cid in (TAPU, CHIKORITA, BAYLEEF, APPLIN):
        p = _P()
        p.id, p.hp, p.maxHp = cid, 100, 140
        assert m._ventana_de_regalo(p, False, 30) == 30 + 60, m.card_table[cid].name


# --------------------------------------------------------------------------
# Fase B: la curación niega el premio
# --------------------------------------------------------------------------

def test_usa_ripening_charge_en_vez_de_teal_dance():
    """La habilidad elegida es la del Hydrapple activo, no la Teal Dance."""
    obs, eleccion = _correr_fixture()
    o = _opcion(obs, eleccion)
    assert o["type"] == int(m.OptionType.ABILITY), o
    assert o["area"] == int(m.AreaType.ACTIVE), (
        "Teal Dance sobre el Ogerpon de banca condenado en vez de Ripening Charge")


def test_la_planta_va_al_ogerpon_ex_no_al_meganium():
    """Desempate por PREMIOS: 2 del Ogerpon ex antes que 1 del Meganium.

    Tablero de la partida 2 con la banca recortada a los dos candidatos. Ambos
    están dentro de su ventana y ambos SALEN con +30:

        Ogerpon ex  80/210, ventana 100 (Tera: sin snipe) -> 110 > 100, 2 premios
        Meganium   110/160, ventana 130 (30 + 40 + 60)    -> 140 > 130, 1 premio

    El tercer Ogerpon (130 PV) queda FUERA de su ventana de 100 y no compite.
    """
    obs = (Escenario(turno=10, paso=121, tac=6)
           .mi_activo(pk(HYDRAPPLE, hp=70, energias=[G, G],
                         fisicas=1, pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(MEGANIUM, hp=110, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, hp=80, energias=[G] * 4, fisicas=2),
                     pk(OGERPON, hp=130, energias=[G, G], fisicas=1))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(GRIMMSNARL, hp=300, max_hp=320, energias=[D, D]))
           .op_banca(pk(FROSLASS, hp=90, max_hp=90),
                     pk(FROSLASS, hp=90, max_hp=90),
                     pk(MUNKIDORI, hp=80, max_hp=110, energias=[D]),
                     pk(MUNKIDORI, hp=90, max_hp=110))
           .op_zonas(mano=5, mazo=17, premios=5)
           .mazo()
           .resto_al_descarte()
           .objetivo_carga_habilidad()
           .construir())
    eleccion = m.agent(obs)
    o = _opcion(obs, eleccion)
    assert o["area"] == int(m.AreaType.BENCH) and o["index"] == 1, (
        "la Planta debe curar al Ogerpon ex (2 premios) dentro de la ventana")


def test_el_dano_movible_es_elastico_no_condena_a_media_mesa():
    """La ventana GARANTIZADA y la COMPLETA no son lo mismo.

    (`registros/marnie/partida_1`, paso 167, turno 14.) Con 1 Froslass y 1
    Munkidori: chip 20, movible 30.

        Meganium    30/160 banca, garantizada 50, completa 80 -> +30 = 60 > 50
        Ogerpon ex  20/210 banca, garantizada 20, completa 50 -> +30 = 50 > 20

    Ninguno sale de la ventana COMPLETA: medido solo con el techo, los dos
    quedarían "condenados" y la curación se apagaría — el mismo fallo que tenía
    medirla solo con el snipe, en espejo. Pero Adrena-Brain solo mata a UN
    cuerpo por turno, así que curar sigue valiendo: obliga al rival a gastarlo.
    Entre los dos gana el de MÁS PREMIOS, el Ogerpon ex.
    """
    obs = (Escenario(turno=14, paso=167, tac=5, premios_propios=3)
           .mi_activo(pk(HYDRAPPLE, hp=110, energias=[G, G],
                         fisicas=1, pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(MEGANIUM, hp=30, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, hp=20, energias=[G] * 6, fisicas=3))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(GRIMMSNARL, hp=310, max_hp=320, energias=[D, D]))
           .op_banca(pk(FROSLASS, hp=90, max_hp=90),
                     pk(MUNKIDORI, hp=60, max_hp=110, energias=[D]))
           .op_zonas(mano=4, mazo=18, premios=3)
           .mazo()
           .resto_al_descarte()
           .objetivo_carga_habilidad()
           .construir())
    eleccion = m.agent(obs)
    o = _opcion(obs, eleccion)
    assert m._op_chip_per_round == 20 and m._op_movable_dmg == 30
    assert o["area"] == int(m.AreaType.BENCH) and o["index"] == 1, (
        "cura el Meganium de 1 premio en vez del Ogerpon ex de 2")


# --------------------------------------------------------------------------
# No-regresión: sin Froslass ni Munkidori la ventana es el golpe de siempre
# --------------------------------------------------------------------------

def test_sin_froslass_ni_munkidori_la_ventana_no_cambia():
    """Contra un mazo sin esas piezas, chip y movible valen 0."""
    obs = (Escenario(turno=8, paso=60, tac=3)
           .mi_activo(pk(HYDRAPPLE, hp=300, energias=[G, G],
                         fisicas=1, pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(MEGANIUM, hp=90, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, hp=80, energias=[G, G, G], fisicas=3))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(GRIMMSNARL, hp=320, max_hp=320, energias=[D, D]))
           .op_banca(pk(IMPIDIMP, hp=70, max_hp=70))
           .op_zonas(mano=5, mazo=20, premios=5)
           .mazo()
           .resto_al_descarte()
           .objetivo_carga_habilidad()
           .construir())
    m.agent(obs)
    assert m._op_chip_per_round == 0
    assert m._op_movable_dmg == 0

    class _P:
        pass
    p = _P()
    p.id, p.hp, p.maxHp = MEGANIUM, 90, 160
    assert m._ventana_de_regalo(p, False, m._op_bench_snipe_dmg) == m._op_bench_snipe_dmg
