"""The GIFT WINDOW: Froslass's drip and Munkidori's movable damage.

Scenario (`registros/marnie/partida_2`, step 121, turn 10, LOST):

    US (4 prizes)                           OPPONENT (5 prizes)
    active  Hydrapple ex   70/330, S2       active  Grimmsnarl ex 300/320, S2
    bench   Meganium        90/160          bench   Froslass  90/90
            Ogerpon ex      80/210, E10             Morgrem  100/100, E2
            Ogerpon ex     130/210, E6              Froslass  90/90
            Meowth ex       70/170                  Munkidori 80/110, E1
            Fezandipiti ex 170/210                  Munkidori 90/110, no energy

The agent chose **Teal Dance on the benched Ogerpon ex at 80 HP**. That body
died that same turn —20 from Freezing Shroud + 60 moved by two Munkidori—
taking **2 prizes and 5 Grass Energies** to the discard. The active Hydrapple's
Ripening Charge was available and unused: +30 would have left it at 110, outside the
window of 100.

Cause: `_ripen_heal_serial` measured the threat to the bench with
`_op_bench_snipe_dmg` = **30** (Shadow Bullet's snipe only). No body
above 30 HP ever entered the detector, so across three games we used
the healing **once** while taking 410/620/60 damage from counters.

The three missing pieces, now in `_ventana_de_regalo`:

1. **Freezing Shroud fires on EVERY Pokémon Checkup and there are TWO per round** (the end
   of our turn and the end of theirs): `10 × n_froslass × 2`. Only the
   bodies in `OUR_ABILITY_IDS` pay it.
2. **Adrena-Brain moves up to 30 to ANY body of ours**, once per
   charged Munkidori — and a dry Munkidori on the field is worth one more activation,
   because the opponent still has their attachment for the turn (which is exactly what happened).
3. The **Tera** of a benched Ogerpon prevents damage *from attacks*: it cuts the 30
   snipe, never the counters placed or the ones moved.

And the tie-break between candidates becomes **prizes first**: denying the 2 of the
Ogerpon ex is worth more than denying the 1 of the Meganium.
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
    m._init_cards_tracking()


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
# Phase A: perception
# --------------------------------------------------------------------------

def test_percepcion_mide_el_goteo_y_el_dano_movible():
    """Two Froslass = 40 per round; two Adrena-Brain activations = 60."""
    _correr_fixture()
    assert m._op_chip_per_round == 40, "10 x 2 Froslass x 2 chequeos"
    # One Munkidori with energy + one dry (the opponent still has their attachment).
    assert m._op_movable_dmg == 60, "30 x 2 activaciones de Adrena-Brain"


def test_la_ventana_del_ogerpon_de_banca_lo_alcanza():
    """80 HP inside a window of 100; with +30 it leaves (110 > 100)."""
    _correr_fixture()

    class _P:
        pass
    p = _P()
    p.id = OGERPON
    p.hp, p.maxHp = 80, 210
    # The Tera cancels the snipe on the bench: the window is chip + movable.
    ventana = m._ventana_de_regalo(p, False, m._op_bench_snipe_dmg)
    assert ventana == 100
    assert p.hp <= ventana                       # inside the window
    assert min(p.maxHp, p.hp + m.RIPENING_HEAL) > ventana   # with +30 it leaves


def test_el_tera_en_banca_no_para_los_contadores():
    """The Tera cuts the snipe (attack damage), never the drip or the movable damage."""
    _correr_fixture()

    class _P:
        pass
    og, meg = _P(), _P()
    og.id, og.hp, og.maxHp = OGERPON, 80, 210
    meg.id, meg.hp, meg.maxHp = MEGANIUM, 90, 160
    # The same position (bench) and the same projected snipe: the Ogerpon saves the
    # 30 of the snipe, but pays the same drip and the same movable damage.
    assert m._ventana_de_regalo(og, False, 30) == 40 + 60
    assert m._ventana_de_regalo(meg, False, 30) == 30 + 40 + 60


def test_sin_habilidad_no_se_paga_el_peaje_de_froslass():
    """Tapu Bulu, Chikorita, Bayleef and Applin are not in OUR_ABILITY_IDS."""
    _correr_fixture()

    class _P:
        pass
    for cid in (TAPU, CHIKORITA, BAYLEEF, APPLIN):
        p = _P()
        p.id, p.hp, p.maxHp = cid, 100, 140
        assert m._ventana_de_regalo(p, False, 30) == 30 + 60, m.card_table[cid].name


# --------------------------------------------------------------------------
# Phase B: the healing denies the prize
# --------------------------------------------------------------------------

def test_usa_ripening_charge_en_vez_de_teal_dance():
    """The chosen ability is that of the active Hydrapple, not the Teal Dance."""
    obs, eleccion = _correr_fixture()
    o = _opcion(obs, eleccion)
    assert o["type"] == int(m.OptionType.ABILITY), o
    assert o["area"] == int(m.AreaType.ACTIVE), (
        "Teal Dance sobre el Ogerpon de banca condenado en vez de Ripening Charge")


def test_la_planta_va_al_ogerpon_ex_no_al_meganium():
    """Tie-break by PRIZES: the 2 of the Ogerpon ex before the 1 of the Meganium.

    The board of game 2 with the bench trimmed to the two candidates. Both
    are inside their window and both LEAVE it with +30:

        Ogerpon ex  80/210, window 100 (Tera: no snipe) -> 110 > 100, 2 prizes
        Meganium   110/160, window 130 (30 + 40 + 60)   -> 140 > 130, 1 prize

    The third Ogerpon (130 HP) is OUTSIDE its window of 100 and does not compete.
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
           .op_zonas(mano=5, mazo=17, prizes=5)
           .mazo()
           .resto_al_descarte()
           .objetivo_carga_habilidad()
           .construir())
    eleccion = m.agent(obs)
    o = _opcion(obs, eleccion)
    assert o["area"] == int(m.AreaType.BENCH) and o["index"] == 1, (
        "la Planta debe curar al Ogerpon ex (2 premios) dentro de la ventana")


def test_el_dano_movible_es_elastico_no_condena_a_media_mesa():
    """The GUARANTEED window and the COMPLETE one are not the same thing.

    (`registros/marnie/partida_1`, step 167, turn 14.) With 1 Froslass and 1
    Munkidori: chip 20, movable 30.

        Meganium    30/160 bench, guaranteed 50, complete 80 -> +30 = 60 > 50
        Ogerpon ex  20/210 bench, guaranteed 20, complete 50 -> +30 = 50 > 20

    Neither leaves the COMPLETE window: measured only with the ceiling, both
    would be "doomed" and the healing would switch off — the same failure as
    measuring it only with the snipe, mirrored. But Adrena-Brain only kills ONE
    body per turn, so healing is still worth it: it forces the opponent to spend it.
    Between the two, the one worth MORE PRIZES wins, the Ogerpon ex.
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
           .op_zonas(mano=4, mazo=18, prizes=3)
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
# Non-regression: without Froslass or Munkidori the window is the usual hit
# --------------------------------------------------------------------------

def test_sin_froslass_ni_munkidori_la_ventana_no_cambia():
    """Against a deck without those pieces, chip and movable damage are 0."""
    obs = (Escenario(turno=8, paso=60, tac=3)
           .mi_activo(pk(HYDRAPPLE, hp=300, energias=[G, G],
                         fisicas=1, pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(MEGANIUM, hp=90, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, hp=80, energias=[G, G, G], fisicas=3))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(GRIMMSNARL, hp=320, max_hp=320, energias=[D, D]))
           .op_banca(pk(IMPIDIMP, hp=70, max_hp=70))
           .op_zonas(mano=5, mazo=20, prizes=5)
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


# --------------------------------------------------------------------------
# The window is measured by CARD, not by archetype
# --------------------------------------------------------------------------
# Measured over the real top-100 of the leaderboard (decks_competidores/, Aug 2026):
# Munkidori is NOT exclusive to Marnie. It appears in 55 of the 100 decks, and of
# those, 6 are not Marnie: the FIVE Dragapult decks of the top-100 run it (5 of
# 5) plus one Crustle. Froslass IS exclusive to the archetype (49 of 49).
#
# The plan's "Containment" note (docs/plan-matchup-marnie-froslass-munkidori)
# said that only the two Marnie decks of deck/rivales/ carried these pieces,
# so no other matchup measurement could move. Against the real meta
# that no longer holds: touching the window also moves the Dragapult matchup.
#
# The code ALREADY does the right thing (the window is computed from the CARDS on the
# field, not from the archetype). This PINS it: if somebody "optimises" it by gating the
# window on the Marnie deck, these tests catch it.
#
# CAREFUL with the ammunition, which is what makes this matchup different: Adrena-Brain
# only moves counters that ALREADY exist on the opposing board. In Marnie the
# ammunition is renewable (their own Froslass loads 10 per checkup onto each
# body with an ability, their Munkidori included). In a Dragapult deck WITHOUT
# Froslass the only ammunition is the counters WE have put there:
# with their board intact the movable damage is 0 -- and that is correct, not a bug.

def test_munkidori_enciende_la_ventana_tambien_fuera_de_marnie():
    """A Dragapult opponent with Munkidori: without a single Marnie Pokemon on the field."""
    obs = (Escenario(turno=8, paso=60, tac=3)
           .mi_activo(pk(HYDRAPPLE, hp=300, energias=[G, G],
                         fisicas=1, pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(MEGANIUM, hp=90, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, hp=80, energias=[G, G, G], fisicas=3))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(m.Dragapult_ex, hp=200, max_hp=320, energias=[D, D]))
           .op_banca(pk(MUNKIDORI, hp=110, max_hp=110, energias=[D]))
           .op_zonas(mano=5, mazo=20, prizes=5)
           .mazo()
           .resto_al_descarte()
           .objetivo_carga_habilidad()
           .construir())
    m.agent(obs)
    assert m._op_chip_per_round == 0, (
        "sin Froslass no hay goteo: el chip es exclusivo de esa carta")
    assert m._op_movable_dmg <= 120, "no puede mover mas contadores de los que hay"
    assert m._op_movable_dmg == 30, (
        "Adrena-Brain amenaza igual desde un mazo Dragapult: la ventana se "
        "mide por la CARTA en mesa, no por el arquetipo rival")


def test_la_ventana_crece_con_munkidori_sin_marnie_en_mesa():
    """The movable damage enters the window even if the opponent is not Marnie."""
    obs = (Escenario(turno=8, paso=60, tac=3)
           .mi_activo(pk(HYDRAPPLE, hp=300, energias=[G, G],
                         fisicas=1, pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(MEGANIUM, hp=90, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, hp=80, energias=[G, G, G], fisicas=3))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(m.Dragapult_ex, hp=200, max_hp=320, energias=[D, D]))
           .op_banca(pk(MUNKIDORI, hp=110, max_hp=110, energias=[D]))
           .op_zonas(mano=5, mazo=20, prizes=5)
           .mazo()
           .resto_al_descarte()
           .objetivo_carga_habilidad()
           .construir())
    m.agent(obs)

    class _P:
        pass
    p = _P()
    p.id, p.hp, p.maxHp = MEGANIUM, 90, 160
    ventana = m._ventana_de_regalo(p, False, m._op_bench_snipe_dmg)
    assert ventana == m._op_bench_snipe_dmg + 30, (
        "la ventana suma los 30 dirigibles de Adrena-Brain aunque enfrente no "
        "haya ni un Pokemon de Marnie")


def test_sin_froslass_el_munkidori_sin_municion_no_amenaza():
    """Control for the previous one: the same board, but with the opponent INTACT.

    Adrena-Brain only moves existing counters. With no Froslass to
    manufacture them and no damage of ours on their board, there is nothing to move: the
    movable damage is 0 and the window goes back to the bare snipe. It is the real
    difference between the Marnie matchup (renewable ammunition) and a Dragapult that
    simply runs Munkidori.
    """
    obs = (Escenario(turno=8, paso=60, tac=3)
           .mi_activo(pk(HYDRAPPLE, hp=300, energias=[G, G],
                         fisicas=1, pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(MEGANIUM, hp=90, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, hp=80, energias=[G, G, G], fisicas=3))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(m.Dragapult_ex, hp=320, max_hp=320, energias=[D, D]))
           .op_banca(pk(MUNKIDORI, hp=110, max_hp=110, energias=[D]))
           .op_zonas(mano=5, mazo=20, prizes=5)
           .mazo()
           .resto_al_descarte()
           .objetivo_carga_habilidad()
           .construir())
    m.agent(obs)
    assert m._op_movable_dmg == 0, (
        "con el tablero rival intacto no hay contadores que mover")
