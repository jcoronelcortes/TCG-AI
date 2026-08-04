"""The energy from the DISCARD that pays the active's retreat and frees the finisher.

Scenario (user, registro_021 turn 21, log 88359220): the ACTIVE cannot
attack and cannot even RETREAT (0 energies, cost 1), but on the bench
an attacker is waiting ALREADY READY that knocks out the rival active. The only Grass is in
the DISCARD and we have a Night Stretcher in hand. The right play is the
five-step chain:

    Night Stretcher -> Grass to hand -> attach to the ACTIVE -> RETREAT ->
    promote the finisher -> KO

The agent ended the turn (END). Cause: `_ns_e_activo_paga_retirada` -- the
deck-agnostic detector of that line -- was only wired to the FULL BENCH
cut-off (`_ns_banca_llena_guardar`), never to `_ESC_NS_RECUPERACION`, which is the
list that produces the SCORE. With the bench not full the ARGMAX gave 0 and the
Night Stretcher's scorer returned SCORE_VETO.

The tests are deck-agnostic on purpose: the case that failed uses a bench
finisher WITHOUT a charging ability (Tapu Bulu), because with a Teal Mask Ogerpon ex
in play the Night Stretcher was played anyway by CHANCE, via the scenario
`energia_activo_sin_teal` -- which has nothing to do with the retreat.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

FEZANDIPITI = m.Fezandipiti_ex     # a blocked active: 0 energies, cost 1
TAPU = m.Tapu_Bulu                 # a bench finisher WITHOUT a charging ability
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
NIGHT_STRETCHER = m.Night_Stretcher
ULTRA_BALL = m.Ultra_Ball
GRASS = m.Basic_Grass_Energy

COMFEY = 164                       # 70 HP: Wood Hammer (220) knocks it out


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _escenario(mano, banca=None, energia_activo=0, descarte=(GRASS, GRASS),
               energia_jugada=False, retirado=False, op_hp=70):
    banca = banca if banca is not None else [pk(TAPU, energias=[G, G, G, G]),
                                             pk(MEOWTH)]
    return (Escenario(turno=12, paso=40, energia_jugada=energia_jugada,
                      retirado=retirado)
            .mi_activo(pk(FEZANDIPITI, energias=[G] * energia_activo))
            .mi_banca(*banca)
            .mi_mano(*mano)
            .mi_descarte(*descarte)
            .op_activo(pk(COMFEY, hp=op_hp))
            .op_zonas(mano=5, mazo=20, prizes=3))


def _elegida(obs, eleccion, mano):
    o = obs["select"]["option"][eleccion[0]]
    if o["type"] == int(m.OptionType.PLAY):
        return ("PLAY", mano[o["index"]])
    if o["type"] == int(m.OptionType.END):
        return ("END", None)
    if o["type"] == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if o["type"] == int(m.OptionType.ATTACH):
        return ("ATTACH", o["inPlayArea"])
    return (o["type"], None)


# ---------------------------------------------------------------------------
# Step 1: play the card that brings the energy
# ---------------------------------------------------------------------------

def test_night_stretcher_se_juega_para_pagar_la_retirada():
    """The record's case: with no Grass in hand and the finisher on the table, the
    Night Stretcher is played instead of ending the turn."""
    mano = [NIGHT_STRETCHER, ULTRA_BALL]
    obs = _escenario(mano).menu_mano().construir()
    assert _elegida(obs, m.agent(obs), mano) == ("PLAY", NIGHT_STRETCHER)


def test_deck_agnostico_el_rematador_no_necesita_habilidad_de_carga():
    """With a bench Teal Mask Ogerpon ex the play already came out right by
    chance (the `energia_activo_sin_teal` scenario). The rule must hold
    equally with any finisher -- here, both."""
    for banca in ([pk(TAPU, energias=[G, G, G, G]), pk(MEOWTH)],
                  [pk(OGERPON, energias=[G, G, G]), pk(MEOWTH)]):
        m._init_cartas_tracking()
        m._cartas_first_scan_done = False
        m._field_at_turn_start = {}
        mano = [NIGHT_STRETCHER, ULTRA_BALL]
        obs = _escenario(mano, banca=banca).menu_mano().construir()
        assert _elegida(obs, m.agent(obs), mano) == ("PLAY", NIGHT_STRETCHER)


def test_sin_energia_en_el_descarte_no_se_gasta_la_night_stretcher():
    """Boundary: if no Grass is left in the discard, the chain does not exist
    and the Night Stretcher must not be played through this rule."""
    mano = [NIGHT_STRETCHER, ULTRA_BALL]
    obs = _escenario(mano, descarte=(ULTRA_BALL, ULTRA_BALL)).menu_mano().construir()
    assert _elegida(obs, m.agent(obs), mano) != ("PLAY", NIGHT_STRETCHER)


def test_con_planta_ya_en_mano_la_cadena_no_necesita_la_night_stretcher():
    """Boundary: with the Grass already in hand the first link is superfluous; what rules is the
    attachment to the ACTIVE (`_attach_enable_retreat_ko`, 41000)."""
    mano = [NIGHT_STRETCHER, GRASS]
    obs = _escenario(mano).menu_mano(con_adjunte=True).construir()
    tipo, destino = _elegida(obs, m.agent(obs), mano)
    assert tipo == "ATTACH" and destino == int(m.AreaType.ACTIVE)


# ---------------------------------------------------------------------------
# Steps 2-5: the complete chain
# ---------------------------------------------------------------------------

def test_la_night_stretcher_recupera_la_energia_y_no_un_pokemon():
    obs = (_escenario([ULTRA_BALL], descarte=(GRASS, GRASS, ULTRA_BALL))
           .fetch_descarte(NIGHT_STRETCHER).construir())
    eleccion = m.agent(obs)
    idx = obs["select"]["option"][eleccion[0]]["index"]
    assert obs["current"]["players"][0]["discard"][idx]["id"] == GRASS


def test_la_planta_recuperada_va_al_activo_no_a_la_banca():
    mano = [GRASS, ULTRA_BALL]
    obs = _escenario(mano).menu_mano(con_adjunte=True).construir()
    tipo, destino = _elegida(obs, m.agent(obs), mano)
    assert tipo == "ATTACH" and destino == int(m.AreaType.ACTIVE)


def test_con_la_energia_puesta_se_retira():
    mano = [ULTRA_BALL]
    obs = (_escenario(mano, energia_activo=1, energia_jugada=True)
           .menu_mano(con_retirada=True).construir())
    assert _elegida(obs, m.agent(obs), mano) == ("RETREAT", None)


# ---------------------------------------------------------------------------
# The useful-energy threshold on the ACTIVE (`_ns_umbral_energia_util`)
# ---------------------------------------------------------------------------

def _umbral_viejo(cid, e):
    """A LITERAL copy of the `if act.id == ...` chain that existed before
    extracting the threshold into tables. It is the equivalence oracle."""
    eff = e * m._grass_mult()
    if cid == m.Hydrapple_ex:
        return eff < 2 and e < 2
    if cid == m.Dipplin:
        return e < 1
    if cid == m.Teal_Mask_Ogerpon_ex:
        return eff < 3 and e < 3
    if cid == m.Tapu_Bulu:
        return eff < 4 and e < 4
    if cid == m.Pinsir:
        return eff < 2 and e < 2
    if cid in (m.Chikorita, m.Bayleef, m.Meganium):
        return e < m.RETREAT_COST.get(cid, 1)
    return False


def _umbral_nuevo(cid, e):
    umbral = m._ns_umbral_energia_util(cid)
    if umbral is None:
        return False
    return (e * m._grass_mult()) < umbral and e < umbral


@pytest.mark.parametrize("card_id", sorted(m._DECK_POKEMON_IDS))
def test_umbral_equivale_al_original_para_todo_el_mazo(card_id):
    """The refactor to tables + fallback does NOT change a single decision of the current
    deck: it is compared against the oracle for 0..10 energies."""
    for e in range(11):
        assert _umbral_nuevo(card_id, e) == _umbral_viejo(card_id, e), (
            f"flip en {card_id} con {e} energias")


def test_cuerpos_del_mazo_excluidos_siguen_excluidos():
    """Meowth ex and Fezandipiti ex DO have an attack, but the curated configuration
    leaves them out on purpose (utility bodies). The fallback by card
    data must not resurrect them."""
    for cid in (m.Meowth_ex, m.Fezandipiti_ex):
        assert m._coste_de_ataque_min(cid) is not None   # they do have an attack...
        assert m._ns_umbral_energia_util(cid) is None    # ...but they do not count


def test_cuerpo_fuera_del_mazo_usa_el_dato_de_carta():
    """The deck-agnostic branch: a body the configuration does not know stops
    returning False blindly and reasons with the real cost of its attack."""
    crustle = 345
    assert crustle not in m._DECK_POKEMON_IDS
    assert m._ns_umbral_energia_util(crustle) == m._coste_de_ataque_min(crustle)
    assert m._ns_umbral_energia_util(crustle) > 0


def test_coste_de_ataque_min_desconocido_es_none():
    """With no card data no threshold is invented."""
    assert m._coste_de_ataque_min(-12345) is None
    assert m._ns_umbral_energia_util(-12345) is None


def test_tras_retirar_se_promueve_al_rematador():
    obs = (_escenario([ULTRA_BALL], energia_activo=1, energia_jugada=True,
                      retirado=True)
           .promocion_desde_banca().construir())
    eleccion = m.agent(obs)
    idx = obs["select"]["option"][eleccion[0]]["index"]
    assert obs["current"]["players"][0]["bench"][idx]["id"] == TAPU
