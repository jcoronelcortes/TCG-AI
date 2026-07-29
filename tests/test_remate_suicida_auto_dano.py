"""El remate que se suicida no GANA: empata. Hay que retirar y rematar con otro.

Escenario (user, episodio 88696693 registro_016 paso 184 vs Marnie's Grimmsnarl,
EMPATE):

    NOSOTROS                          RIVAL
    activo  Tapu Bulu   20/140  6e    activo  Impidimp   70/70   0e
    banca   Meganium    80/160  0e    banca   5 cuerpos (llena)
            Ogerpon ex 100/210  6e
            Hydrapple  290/330  0e
    premios restantes: 1              premios restantes: 1

El agente ataco con Wood Hammer (220 >= 70): noqueo al Impidimp... y Wood Hammer
"also does 30 damage to itself", asi que los 20 PV de Tapu Bulu tampoco
sobrevivieron. Los dos KOs son SIMULTANEOS: cada jugador cobro su ULTIMO premio y
la partida acabo 0-0, EMPATE (`result=2` en el simulador).

La jugada ganadora estaba en la banca: retirar Tapu Bulu (coste 3) y promover al
Teal Mask Ogerpon ex, ya con 6 energias, para Myriad Leaf Shower = 30 + 30x6 =
210 >= 70. Verificado conduciendo el simulador real desde el paso 184 con
`cg.api.search_begin/search_step`: la linea del agente da `result=2` (empate) y
la de la retirada da `result=0` (VICTORIA nuestra).

Al agente le faltaban TRES piezas, que son las que fijan estos tests:

 1. el AUTO-DANO del ataque. No es un campo de `Attack`, vive en su TEXTO; ahora
    `_attack_self_damage` lo parsea (de los ~49 ataques de la base con auto-dano,
    distinguiendo obligatorio / opcional "You may" / moneda / por contadores).
 2. que el KO de NUESTRO cuerpo tambien PAGA PREMIOS: `_active_attack_wins_now`
    declaraba victoria mirando solo los premios que cobrabamos nosotros.
 3. que al retirar hay que promover al REMATADOR, no al cuerpo mas tanque: la
    promocion subia el Hydrapple ex de 290 PV (sin energia, no remata) por
    delante del Ogerpon ex cargado que cerraba la partida.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

TAPU = m.Tapu_Bulu             # 920: Wood Hammer 220, -30 a si mismo
OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
LANAS = m.Lanas_Aid
BAYLEEF = m.Bayleef
GRASS = m.Basic_Grass_Energy

WOOD_HAMMER = 1326
MYRIAD_LEAF_SHOWER = 120

IMPIDIMP = 646                 # 70 PV, 1 premio (linea Grimmsnarl)
ARCHALUDON_EX = 190           # 300 PV, resistencia a Planta (-30): aguanta 220
SPIKEMUTH_GYM = 1259           # estadio del rival en el registro


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


# ---------------------------------------------------------------------------
# 1. El dato que faltaba: el auto-dano sale del TEXTO del ataque
# ---------------------------------------------------------------------------

def test_wood_hammer_se_hace_30_a_si_mismo():
    assert m._attack_self_damage(WOOD_HAMMER) == 30


def test_myriad_leaf_shower_no_tiene_auto_dano():
    assert m._attack_self_damage(MYRIAD_LEAF_SHOWER) == 0


def test_el_auto_dano_opcional_no_se_asume():
    """"You may do 30 more damage. If you do, this Pokemon also does 30 damage
    to itself" (Superpower 144): la decision es NUESTRA, asi que el dano cierto
    es 0. Igual con la forma sin -s ("...also DO 60 damage to itself", 1171)."""
    assert m._attack_self_damage(144) == 0
    assert m._attack_self_damage(1171) == 0


def test_el_auto_dano_por_moneda_solo_cuenta_en_el_peor_caso():
    """Reckless Abandon (662): "Flip 2 coins. If both of them are tails, this
    Pokemon also does 90 damage to itself"."""
    assert m._attack_self_damage(662) == 0
    assert m._attack_self_damage(662, incierto=True) == 90


def test_el_auto_dano_por_contadores_usa_el_dano_recibido():
    """Vanguard Punch (51): 10 por CADA contador de dano sobre el atacante."""
    herido = _pkmn(51, hp=80, max_hp=130)
    assert m._attack_self_damage(51, herido) == 50   # 5 contadores


def test_una_moneda_posterior_no_convierte_el_auto_dano_en_azar():
    """Thump-Thump Boom (364): "This Pokemon does 100 damage to itself. Flip a
    coin..." -- la moneda es de OTRA frase y no toca al auto-dano."""
    assert m._attack_self_damage(364) == 100


def test_tapu_bulu_a_20_pv_se_noquea_con_su_propio_ataque():
    assert m._self_ko_by_own_attack(_pkmn(TAPU, hp=20, energias=6))
    assert not m._self_ko_by_own_attack(_pkmn(TAPU, hp=140, energias=6))


def test_sin_energia_para_pagar_el_ataque_no_hay_auto_dano():
    """El auto-dano solo cuenta si el ataque se puede USAR: Wood Hammer cuesta
    4 unidades, y con 2 energias no hay ataque (ni suicidio) que temer."""
    tapu = _pkmn(TAPU, hp=20, energias=2)
    assert m._self_damage_of_pokemon(tapu) == 0
    assert not m._self_ko_by_own_attack(tapu)


# ---------------------------------------------------------------------------
# 2. El paso 184: retirar en vez de firmar el empate
# ---------------------------------------------------------------------------

def _paso_184(op_premios=1, mis_premios=1, tapu_hp=20, ogerpon_energias=6):
    """El tablero exacto del paso 184. Meganium en banca => cada Planta fisica
    cuenta DOBLE, asi que 3 cartas de energia dan 6 unidades efectivas."""
    return (Escenario(turno=16, paso=184, tac=1,
                      premios_propios=mis_premios)
            .mi_activo(pk(TAPU, hp=tapu_hp, energias=[G] * 6, fisicas=3))
            .mi_banca(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]),
                      pk(OGERPON, hp=100, energias=[G] * ogerpon_energias,
                         fisicas=ogerpon_energias // 2),
                      pk(HYDRAPPLE, hp=290, pre_evo=[m.Applin, m.Dipplin]))
            .mi_mano(BAYLEEF, GRASS, LANAS)
            .estadio(SPIKEMUTH_GYM, del_rival=True)
            .op_activo(pk(IMPIDIMP))
            .op_banca(pk(IMPIDIMP), pk(IMPIDIMP), pk(IMPIDIMP),
                      pk(IMPIDIMP), pk(IMPIDIMP))
            .op_zonas(mano=4, mazo=25, premios=op_premios))


def _tipo_elegido(obs, eleccion):
    return obs["select"]["option"][eleccion[0]]["type"]


def test_con_un_premio_por_lado_se_retira_en_vez_de_rematar_suicida():
    """EL FALLO DEL REGISTRO. Antes: ATTACK (Wood Hammer) -> empate 0-0.
    Ahora: RETREAT, para promover al Ogerpon ex y ganar limpio."""
    obs = _paso_184().menu_mano(con_retirada=True, con_ataque=True).construir()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.RETREAT)


def test_el_remate_suicida_queda_vetado_mientras_exista_el_relevo():
    obs = _paso_184().menu_mano(con_retirada=True, con_ataque=True).construir()
    scores = _scores(obs)
    i_atk = _indice(obs, m.OptionType.ATTACK)
    i_ret = _indice(obs, m.OptionType.RETREAT)
    assert scores[i_atk] <= 0
    assert scores[i_ret] > 0


def test_sin_relevo_en_banca_el_empate_es_el_mejor_resultado_y_no_se_veta():
    """Sin nadie en la banca que remate, el empate es lo mejor disponible: el
    ataque NO se veta (pasar tambien acaba en empate, pero regala el turno).
    Se mide el veto y no la eleccion porque, con energia en la mano, adjuntarla
    puntua mas que atacar por reglas ANTERIORES a este cambio."""
    obs = (Escenario(turno=16, paso=184, tac=1, premios_propios=1)
           .mi_activo(pk(TAPU, hp=20, energias=[G] * 6, fisicas=3))
           .mi_banca(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]))
           .mi_mano(GRASS)
           .op_activo(pk(IMPIDIMP))
           .op_banca(pk(IMPIDIMP))
           .op_zonas(mano=4, mazo=25, premios=1)
           .menu_mano(con_retirada=True, con_ataque=True).construir())
    assert _scores(obs)[_indice(obs, m.OptionType.ATTACK)] > 0


def test_con_el_rival_lejos_del_final_el_remate_suicida_sigue_ganando():
    """El freno mira los premios DEL RIVAL, no el auto-dano en abstracto: con 3
    premios rivales nuestro cadaver (1 premio) no le cierra la cuenta, asi que
    Wood Hammer sigue siendo el remate ganador de maxima prioridad."""
    obs = _paso_184(op_premios=3).menu_mano(
        con_retirada=True, con_ataque=True).construir()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ATTACK)


def test_tapu_bulu_sano_no_se_suicida_y_remata_de_frente():
    """Mismo tablero con Tapu Bulu a 140/140: los 30 de auto-dano no lo matan,
    asi que no hay empate que evitar y ATACAR vuelve a ser lo primero."""
    obs = _paso_184(tapu_hp=140).menu_mano(
        con_retirada=True, con_ataque=True).construir()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ATTACK)


def test_el_remate_suicida_que_PIERDE_se_veta_aunque_no_haya_relevo():
    """Peor caso que el empate: nuestro ataque NO noquea (Duraludon de 380 PV
    aguanta los 220), asi que el auto-dano solo le REGALA al rival su ultimo
    premio. Ahi atacar es perder: se veta sin necesidad de relevo."""
    obs = (Escenario(turno=16, paso=184, tac=1, premios_propios=3)
           .mi_activo(pk(TAPU, hp=20, energias=[G] * 6, fisicas=3))
           .mi_banca(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]))
           .mi_mano(GRASS)
           .op_activo(pk(ARCHALUDON_EX, hp=300, max_hp=300))
           .op_banca(pk(IMPIDIMP))
           .op_zonas(mano=4, mazo=25, premios=1)
           .menu_mano(con_retirada=True, con_ataque=True).construir())
    scores = _scores(obs)
    assert scores[_indice(obs, m.OptionType.ATTACK)] <= 0


# ---------------------------------------------------------------------------
# 3. Al retirar, sube el REMATADOR (no el cuerpo mas tanque)
# ---------------------------------------------------------------------------

def test_la_promocion_tras_retirar_sube_al_que_gana_la_partida():
    """La otra mitad de la cadena: sin esto retirabamos bien y luego subiamos el
    Hydrapple ex de 290 PV (sin energia, no remata) en vez del Ogerpon ex
    cargado, y el turno se cerraba sin cobrar el premio."""
    obs = _paso_184().promocion_tras_retirada().construir()
    eleccion = m.agent(obs)
    idx = obs["select"]["option"][eleccion[0]]["index"]
    banca = obs["current"]["players"][0]["bench"]
    assert banca[idx]["id"] == OGERPON


def test_la_promocion_forzada_tras_un_KO_no_cambia_de_criterio():
    """El bono de "sube el rematador" es solo de la retirada VOLUNTARIA
    (contexto SWITCH, siempre en nuestro turno y antes de atacar). La promocion
    forzada tras un KO (TO_ACTIVE) puede caer en el turno rival, donde no se
    ataca y lo correcto sigue siendo el criterio de siempre."""
    obs = _paso_184().promocion_desde_banca().construir()
    eleccion = m.agent(obs)
    idx = obs["select"]["option"][eleccion[0]]["index"]
    banca = obs["current"]["players"][0]["bench"]
    assert banca[idx]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _pkmn(card_id, hp, max_hp=None, energias=0):
    """Pokemon suelto para los helpers de auto-dano (sin observacion completa)."""
    return m.Pokemon(id=card_id, serial=0, hp=hp,
                     maxHp=max_hp if max_hp is not None else hp,
                     appearThisTurn=False, energies=[G] * energias,
                     energyCards=[], tools=[], preEvolution=[])


def _indice(obs, tipo):
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(tipo):
            return i
    raise AssertionError(f"el menu no ofrece {tipo!r}")


def _scores(obs):
    """Puntuaciones que el agente asigna a cada opcion del menu."""
    capturado = {}
    original = m._debug_log_decision

    def espia(context, select, scores, o, my_index, top_n=3):
        capturado.setdefault("scores", list(scores))
        return original(context, select, scores, o, my_index, top_n)

    m._debug_log_decision = espia
    try:
        m.agent(obs)
    finally:
        m._debug_log_decision = original
    assert "scores" in capturado, "el agente no puntuo el menu"
    return capturado["scores"]
