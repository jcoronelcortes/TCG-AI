"""Tests del StateBuilder (`Escenario`) y primer barrido parametrico de frontera.

Fase 1 de la arquitectura de mejora de estrategia: validar que el builder
produce observaciones que `main.agent()` procesa igual que las reales.

Validacion "contra la realidad": la replica sintetica del paso 69 de
registro_008 (vs Crustle/Kangaskhan) debe producir la MISMA decision que la
observacion real (Ultra Ball busca Hydrapple ex para evolucionar al Dipplin
activo condenado). A partir de ahi, el barrido parametrico fabrica variantes
que NUNCA ocurrieron en partidas (activo rival inmune, Dipplin sin energia)
y verifica las fronteras de la regla `_ub_evo_doomed_hittable`.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import C, G, Escenario, EstadoInconsistente, pk

# IDs que no estan en nuestro deck.csv (cartas del rival).
KANGASKHAN = 756
CRUSTLE = 345
DWEBBLE = 344
HEROS_CAPE = 1159


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


def _escenario_paso69(op_activo="kangaskhan", energia_dipplin=2):
    """Replica sintetica del paso 69 de registro_008 con variantes.

    op_activo: "kangaskhan" (golpeable por ex) o "crustle" (inmune a ex,
        con el Kangaskhan relegado a la banca).
    energia_dipplin: 2 = como el real (1 fisica x Meganium = [G, G], ataca
        tras evolucionar); 0 = sin energia (no ataca tras evolucionar).
    """
    kang = pk(KANGASKHAN, hp=160, max_hp=400, energias=[C, G, C, C],
              fisicas=4, tools=[HEROS_CAPE])
    crustle = pk(CRUSTLE, pre_evo=[DWEBBLE])
    if op_activo == "kangaskhan":
        activo_rival, banca_rival = kang, crustle
    else:
        activo_rival, banca_rival = crustle, kang

    if energia_dipplin == 2:
        dipplin = pk(m.Dipplin, energias=[G, G], fisicas=1,
                     pre_evo=[m.Applin])
    else:
        dipplin = pk(m.Dipplin, energias=[], fisicas=0, pre_evo=[m.Applin])

    esc = (Escenario(turno=8, paso=69, tac=3, primer_jugador=1)
           .mi_activo(dipplin)
           .mi_banca(pk(m.Meganium, pre_evo=[m.Chikorita, m.Bayleef]),
                     pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=1),
                     m.Meowth_ex)
           .mi_mano()
           .estadio(m.Forest_of_Vitality)
           .op_activo(activo_rival)
           .op_banca(banca_rival)
           .op_zonas(mano=9, mazo=37, premios=2)
           .op_descarte(m.Xerosic_Machinations, m.Lillie_Determination,
                        m.Lillie_Determination, 1264)
           # Mazo visible: composicion real del select.deck del paso 69.
           .mazo(m.Hydrapple_ex, m.Tapu_Bulu, m.Lillie_Determination,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                 m.Teal_Mask_Ogerpon_ex, m.Hydrapple_ex, m.Chikorita,
                 m.Bug_Catching_Set, m.Night_Stretcher, m.Night_Stretcher,
                 m.Ultra_Ball, m.Boss_Orders, m.Xerosic_Machinations,
                 m.Lillie_Determination, m.Lillie_Determination,
                 m.Forest_of_Vitality, m.Forest_of_Vitality)
           # OJO: fetch_ultra_ball() ANTES de resto_al_descarte(), para que
           # la Ultra Ball "en efecto" se reserve del pool y no acabe en el
           # descarte (la contabilidad estricta lo detecta si se invierte).
           .fetch_ultra_ball()
           .resto_al_descarte())
    return esc.construir()


def _carta_elegida(obs, eleccion):
    assert eleccion, f"el agente cancelo el fetch: {eleccion}"
    opt = obs["select"]["option"][eleccion[0]]
    return obs["select"]["deck"][opt["index"]]["id"]


# ---------------------------------------------------------------------
# Validacion del builder contra la decision real (paso 69)
# ---------------------------------------------------------------------

def test_replica_sintetica_paso69_coincide_con_decision_real():
    obs = _escenario_paso69()
    eleccion = m.agent(obs)
    assert _carta_elegida(obs, eleccion) == m.Hydrapple_ex, (
        "la replica sintetica del paso 69 debe reproducir la decision del "
        "escenario real: buscar Hydrapple ex para evolucionar al Dipplin "
        "activo condenado")


# ---------------------------------------------------------------------
# Barrido de frontera de `_ub_evo_doomed_hittable` (estados que NUNCA
# ocurrieron en partidas reales)
# ---------------------------------------------------------------------

@pytest.mark.parametrize("op_activo,energia_dipplin,espera_hydrapple", [
    # activo rival golpeable + Dipplin ataca tras evolucionar -> excepcion
    ("kangaskhan", 2, True),
    # activo rival INMUNE a ex -> la excepcion no aplica, vuelve el clamp
    ("crustle", 2, False),
    # Dipplin sin energia: evoluciona pero NO ataca -> sin excepcion
    ("kangaskhan", 0, False),
])
def test_frontera_ub_evo_doomed(op_activo, energia_dipplin, espera_hydrapple):
    obs = _escenario_paso69(op_activo=op_activo,
                            energia_dipplin=energia_dipplin)
    eleccion = m.agent(obs)
    elegida = _carta_elegida(obs, eleccion)
    if espera_hydrapple:
        assert elegida == m.Hydrapple_ex, (
            f"con activo rival golpeable y Dipplin que ataca tras "
            f"evolucionar, el fetch debe ser Hydrapple ex; fue {elegida}")
    else:
        assert elegida != m.Hydrapple_ex, (
            f"({op_activo}, e={energia_dipplin}): la excepcion no aplica y "
            f"el clamp vs Crustle debe impedir el fetch de Hydrapple ex; "
            f"fue {elegida}")


# ---------------------------------------------------------------------
# La contabilidad del builder rechaza estados imposibles
# ---------------------------------------------------------------------

def test_builder_rechaza_mas_copias_que_el_mazo():
    esc = Escenario().mi_activo(pk(m.Dipplin, pre_evo=[m.Applin]))
    with pytest.raises(EstadoInconsistente):
        # deck.csv tiene 2 Hydrapple ex: la 3a copia debe fallar.
        esc.mazo(m.Hydrapple_ex, m.Hydrapple_ex, m.Hydrapple_ex)


def test_builder_rechaza_sobrante_distinto_de_premios():
    esc = (Escenario()
           .mi_activo(pk(m.Dipplin, pre_evo=[m.Applin]))
           .op_activo(pk(KANGASKHAN, hp=160, max_hp=400))
           # mazo declarado de 2 cartas: sobran ~50 sin colocar (mucho mas
           # que los 6 premios) -> la construccion debe fallar.
           .mazo(m.Hydrapple_ex, m.Tapu_Bulu)
           .fetch_ultra_ball())
    with pytest.raises(EstadoInconsistente):
        esc.construir()


# ---------------------------------------------------------------------
# Linea Meganium prioritaria vs Cornerstone Mask Ogerpon ex (user,
# registro_004 turno 4): su Cornerstone Stance anula el dano de TODOS
# nuestros Pokemon CON habilidad (Teal Mask Ogerpon ex, Hydrapple ex,
# Dipplin...), asi que el unico atacante real es Tapu Bulu. Meganium tampoco
# le hace dano -- tambien tiene habilidad -- pero su Wild Growth DUPLICA cada
# Planta, de modo que con el en juego Tapu ataca con 2 Plantas FISICAS en vez
# de 4. Montar la linea es por tanto prioritario en este matchup.
#
# Escenario SINTETICO (no existe en los registros vigentes: ninguno llega a
# jugar Ultra Ball frente a Cornerstone), justo el caso para el StateBuilder.
# ---------------------------------------------------------------------
CORNERSTONE = 117
CUBCHOO = 506


def _fetch_ub_vs(op_id):
    """Fetch de Ultra Ball con Chikorita en banca y la linea en el mazo."""
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Chikorita))
           .mi_mano()
           .op_activo(pk(op_id, hp=210, max_hp=210))
           .op_zonas(mano=4, mazo=40, premios=6)
           .mazo(m.Meganium, m.Bayleef, m.Tapu_Bulu, m.Teal_Mask_Ogerpon_ex,
                 m.Hydrapple_ex, m.Applin, m.Chikorita, m.Meowth_ex)
           .fetch_ultra_ball()
           .resto_al_descarte()
           .construir())
    eleccion = m.agent(obs)
    sel = obs["select"]
    return sel["deck"][sel["option"][eleccion[0]]["index"]]["id"]


def test_cornerstone_prioriza_linea_meganium():
    elegida = _fetch_ub_vs(CORNERSTONE)
    assert elegida in (m.Meganium, m.Bayleef), (
        f"vs Cornerstone, Wild Growth deja a Tapu Bulu atacando con 2 Plantas "
        f"fisicas en vez de 4: completar la linea Meganium es la busqueda "
        f"prioritaria; obtuvo {m.card_table[elegida].name}")


def test_sin_cornerstone_la_busqueda_no_cambia():
    # Frontera: sin Cornerstone la prioridad de matchup no aplica y el fetch
    # conserva su comportamiento normal (Bayleef, evolucion inmediata).
    elegida = _fetch_ub_vs(CUBCHOO)
    assert elegida == m.Bayleef, (
        f"sin Cornerstone el fetch no debe cambiar; obtuvo "
        f"{m.card_table[elegida].name}")


# ---------------------------------------------------------------------
# Tapu Bulu es el UNICO atacante real vs Cornerstone (user, registro_004
# turno 4): la whitelist anti-Cubchoo (`_CUB_ALLOWED_PLAY`) permitia Teal Mask
# Ogerpon ex e Hydrapple ex -- que por su habilidad hacen dano CERO a
# Cornerstone -- pero excluia a Tapu Bulu, el unico que si le pega. El agente
# bajaba un 2o Ogerpon ex y dejaba a Tapu muerto en la mano.
# ---------------------------------------------------------------------

def _menu_con_tapu_en_mano(op_id):
    """Menu principal vs un rival Cubchoo con Cornerstone (o no) de activo."""
    return (Escenario(turno=6, paso=1, tac=1)
            .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
            .mi_banca(pk(m.Bayleef, pre_evo=[m.Chikorita]))
            .mi_mano(m.Basic_Grass_Energy, m.Tapu_Bulu)
            .op_activo(pk(op_id, hp=210, max_hp=210))
            .op_banca(pk(CUBCHOO))
            .op_zonas(mano=4, mazo=40, premios=6)
            .menu_attach_energia()
            .construir())


def _energia_va_a(obs, eleccion):
    opt = obs["select"]["option"][eleccion[0]]
    if opt.get("type") != 8:
        return None
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    destino = (me["active"][0] if opt.get("inPlayArea") == 4
               else me["bench"][opt["inPlayIndex"]])
    return destino["id"]


def test_cornerstone_energia_va_a_tapu_bulu():
    # Con Tapu Bulu YA en banca, la energia debe cargarlo a el (unico atacante
    # que dana a Cornerstone), no al Ogerpon ex de habilidad anulada.
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Tapu_Bulu), pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(CORNERSTONE, hp=210, max_hp=210))
           .op_zonas(mano=4, mazo=40, premios=6)
           .menu_attach_energia()
           .construir())
    assert _energia_va_a(obs, m.agent(obs)) == m.Tapu_Bulu, (
        "vs Cornerstone la energia debe ir a Tapu Bulu: el Ogerpon ex tiene "
        "habilidad y su dano queda anulado")


def test_cornerstone_sin_el_la_energia_no_cambia():
    # Frontera: sin Cornerstone el reparto de energia conserva su criterio.
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Tapu_Bulu), pk(m.Bayleef, pre_evo=[m.Chikorita]))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(CUBCHOO, hp=70, max_hp=70))
           .op_zonas(mano=4, mazo=40, premios=6)
           .menu_attach_energia()
           .construir())
    assert _energia_va_a(obs, m.agent(obs)) == m.Teal_Mask_Ogerpon_ex, (
        "sin Cornerstone la energia sigue yendo al atacante habitual")


# ---------------------------------------------------------------------
# Tope de energia del Teal Mask Ogerpon ex vs el mazo de Hop's (user):
# maximo 3 energias FISICAS sin Meganium en juego / 2 con Meganium. La UNICA
# razon para pasarse (adjunte manual, Ripening Charge o Teal Dance) es que el
# Ogerpon este en el ACTIVO y le falte esa energia para NOQUEAR al activo
# rival. Escenarios SINTETICOS (los registros vs Hop's no llegan a 3 cargas).
# ---------------------------------------------------------------------
TREVENANT = 879     # Hop's Trevenant (140 PV): activa op_is_hop_deck


def _jugada_elegida(obs, eleccion):
    """('ABILITY', None) para Teal Dance; ('ATTACH', id destino) para adjunte."""
    opt = obs["select"]["option"][eleccion[0]]
    if opt.get("type") == int(m.OptionType.ABILITY):
        return ("ABILITY", None)
    if opt.get("type") != int(m.OptionType.ATTACH):
        return ("OTRA", opt.get("type"))
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    destino = (me["active"][0] if opt.get("inPlayArea") == int(m.AreaType.ACTIVE)
               else me["bench"][opt["inPlayIndex"]])
    return ("ATTACH", destino["id"])


def _esc_hop(activo, banca, op_energias=(), menu="attach"):
    esc = (Escenario(turno=8, paso=1, tac=1)
           .mi_activo(activo)
           .mi_banca(*banca)
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(TREVENANT, hp=140, max_hp=140, energias=list(op_energias)))
           .op_zonas(mano=4, mazo=40, premios=4))
    esc = esc.menu_teal_dance() if menu == "teal" else esc.menu_attach_energia()
    return esc.construir()


def test_hop_tope_3_energias_ogerpon_banca():
    # 3 fisicas en el Ogerpon de BANCA = tope alcanzado: la energia va a otro
    # cuerpo (antes el tope era 4 y se sobrecargaba al Ogerpon).
    obs = _esc_hop(pk(m.Dipplin, pre_evo=[m.Applin], energias=[G], fisicas=1),
                   [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3)])
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert (tipo, destino) != ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "vs Hop's un Ogerpon de banca con 3 energias fisicas esta en su tope: "
        "no se le adjunta una 4a")


def test_hop_dos_energias_ogerpon_banca_sigue_permitido():
    # Frontera: con 2 fisicas el tope no aplica y la carga sigue siendo valida.
    obs = _esc_hop(pk(m.Dipplin, pre_evo=[m.Applin], energias=[G], fisicas=1),
                   [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2)])
    assert _jugada_elegida(obs, m.agent(obs)) == ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "con 2 energias fisicas el Ogerpon aun no llega al tope de Hop's")


def test_hop_cuarta_energia_solo_si_habilita_el_ko():
    # EXCEPCION: Ogerpon ACTIVO con 3 fisicas; Myriad hace 30+30*(3+0)=120 y no
    # noquea al Trevenant de 140, pero con la 4a llega a 150 => se permite.
    obs = _esc_hop(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3),
                   [pk(m.Tapu_Bulu, energias=[G, G, G], fisicas=3)])
    assert _jugada_elegida(obs, m.agent(obs)) == ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "la 4a energia se permite cuando es la que HABILITA el KO del activo "
        "rival desde el Ogerpon activo")


def test_hop_cuarta_energia_vetada_si_el_ogerpon_ya_noquea():
    # Sin la excepcion: el Ogerpon activo YA noquea (30+30*(3+2 energias del
    # rival) = 180 >= 140), asi que la 4a energia sobra y va a otro atacante.
    obs = _esc_hop(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3),
                   [pk(m.Tapu_Bulu, energias=[G, G, G], fisicas=3)],
                   op_energias=[G, G])
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert (tipo, destino) != ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "si el Ogerpon activo ya noquea, la energia extra no habilita nada: "
        "el tope de Hop's la reserva para otro cuerpo")


def test_hop_teal_dance_respeta_el_tope():
    # Teal Dance tambien adjunta: con 3 fisicas en el Ogerpon de banca queda
    # vetada (antes se usaba y lo dejaba en 4).
    obs = _esc_hop(pk(m.Dipplin, pre_evo=[m.Applin], energias=[G], fisicas=1),
                   [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3)],
                   menu="teal")
    assert _jugada_elegida(obs, m.agent(obs))[0] != "ABILITY", (
        "Teal Dance sobre un Ogerpon de banca en su tope (3 fisicas vs Hop's) "
        "sobrecargaria: debe quedar vetada")


def test_hop_teal_dance_permitida_si_habilita_el_ko():
    # La excepcion del ACTIVO tambien vale para Teal Dance (adjunta + ROBA).
    obs = _esc_hop(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3),
                   [pk(m.Tapu_Bulu, energias=[G, G, G], fisicas=3)],
                   menu="teal")
    assert _jugada_elegida(obs, m.agent(obs))[0] == "ABILITY", (
        "con el Ogerpon activo a una energia del KO, Teal Dance es la jugada "
        "(adjunta la Planta y ademas roba)")


def test_hop_tope_2_energias_con_meganium():
    # Con Meganium en juego (Wild Growth duplica) el tope baja a 2 fisicas.
    obs = (Escenario(turno=8, paso=1, tac=1)
           .mi_activo(pk(m.Meganium, pre_evo=[m.Chikorita, m.Bayleef]))
           .mi_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G, G], fisicas=2),
                     pk(m.Tapu_Bulu))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(TREVENANT, hp=140, max_hp=140))
           .op_zonas(mano=4, mazo=40, premios=4)
           .menu_attach_energia()
           .construir())
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert (tipo, destino) != ("ATTACH", m.Teal_Mask_Ogerpon_ex), (
        "con Meganium en juego 2 Plantas fisicas ya son 4 efectivas: el "
        "Ogerpon de banca esta en su tope")


def test_tope_base_por_matchup():
    # Frontera de matchup: el tope de 3 fisicas es SOLO de Hop's; vs Alakazam
    # (el otro matchup con tope) la base sigue siendo 4 sin Meganium.
    assert m._ogerpon_base_phys_cap(False, True) == 3
    assert m._ogerpon_base_phys_cap(True, True) == 2
    assert m._ogerpon_base_phys_cap(False, False) == 4
    assert m._ogerpon_base_phys_cap(True, False) == 2


# ---------------------------------------------------------------------
# Combo Myriad ganador: Teal Dance -> Boss's Orders -> gusteo -> ataque
# (user, registro_012 paso 227 vs Iono, PERDIDA; escenario SINTETICO porque
# los registros son datos locales transitorios). A 2 premios, con Teal Mask
# Ogerpon ex activo (4 energias), 1 Planta + Boss's en mano y un Iono's
# Bellibolt ex (280 PV, 4 energias) en la banca rival, la linea GANA:
# Teal Dance deja al Ogerpon en 5 -> Boss's sube al Bellibolt ->
# Myriad = 30 + 30*(5+4) = 300 >= 280 -> KO de 2 premios.
# El bloqueo era doble: Teal Dance vetada ("ya tiene >=3 energias y ya noquea
# al activo rival") y el adjunte manual al activo vetado por la PRECEDENCIA de
# Teal Dance, asi que la energia acababa en un cuerpo de banca.
# ---------------------------------------------------------------------
BELLIBOLT_EX = 269      # Iono's Bellibolt ex, 280 PV, 2 premios
KILOWATTREL = 271       # Iono's Kilowattrel, 120 PV
MYRIAD_ATK = 120


def _esc_combo_myriad(energias=4, plantas=1, energia_jugada=False,
                      premios_propios=2):
    # `menu_teal_dance()` exige una Planta en la mano (la habilidad la adjunta
    # DE la mano); para los pasos posteriores de la cadena (`plantas=0`) se
    # construye con ella y luego se mueve al descarte, que es justo donde acaba
    # tras usarse.
    obs = (Escenario(turno=12, paso=227, tac=1,
                     premios_propios=premios_propios,
                     energia_jugada=energia_jugada)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G] * energias,
                         fisicas=energias))
           .mi_banca(pk(m.Applin))
           .mi_mano(m.Basic_Grass_Energy, m.Boss_Orders)
           .op_activo(pk(KILOWATTREL, hp=120, max_hp=120))
           .op_banca(pk(BELLIBOLT_EX, hp=280, max_hp=280,
                        energias=[G, G, G, G]))
           .op_zonas(mano=5, mazo=30, premios=3)
           .menu_teal_dance()
           .construir())
    if plantas == 0:
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        sobra = [c for c in me["hand"] if c["id"] == m.Basic_Grass_Energy]
        me["hand"] = [c for c in me["hand"] if c["id"] != m.Basic_Grass_Energy]
        me["handCount"] = len(me["hand"])
        me["discard"] = list(me["discard"]) + sobra
    return obs


def _menu_combo(obs, con_ability=True, con_attach=True):
    """Menu MAIN realista: Teal Dance + PLAY Boss's + adjuntes + ataque."""
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    i_boss = next(i for i, c in enumerate(me["hand"]) if c["id"] == m.Boss_Orders)
    i_e = next((i for i, c in enumerate(me["hand"])
                if c["id"] == m.Basic_Grass_Energy), None)
    ops = []
    if con_ability:
        ops.append({"type": int(m.OptionType.ABILITY),
                    "area": int(m.AreaType.ACTIVE), "index": 0})
    ops.append({"type": int(m.OptionType.PLAY), "index": i_boss})
    if con_attach and i_e is not None:
        for area, idx in ((int(m.AreaType.ACTIVE), 0), (int(m.AreaType.BENCH), 0)):
            ops.append({"type": int(m.OptionType.ATTACH), "area": 2, "index": i_e,
                        "inPlayArea": area, "inPlayIndex": idx})
    ops += [{"type": int(m.OptionType.ATTACK), "attackId": MYRIAD_ATK},
            {"type": int(m.OptionType.RETREAT)}, {"type": int(m.OptionType.END)}]
    obs["select"]["option"] = ops
    return obs


def _tipo_elegido(obs, eleccion):
    return int(obs["select"]["option"][eleccion[0]]["type"])


def test_combo_myriad_usa_teal_dance_para_el_remate():
    obs = _menu_combo(_esc_combo_myriad())
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ABILITY), (
        "con un remate ganador via Boss's, la energia del turno va al Ogerpon "
        "ACTIVO por Teal Dance (adjunta y roba), no a un cuerpo de banca")


def test_combo_myriad_teal_dance_con_el_adjunte_ya_gastado():
    # La habilidad es INDEPENDIENTE del adjunte manual: aunque la energia del
    # turno ya se haya jugado, Teal Dance sigue sumando la 5a energia y el
    # remate debe detectarse igual (antes `_mbw_dmg_to` solo modelaba el +1 del
    # adjunte y el remate se perdia).
    obs = _menu_combo(_esc_combo_myriad(energia_jugada=True), con_attach=False)
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ABILITY), (
        "con el adjunte manual gastado, Teal Dance sigue siendo la carga que "
        "habilita el remate ganador")


def test_combo_myriad_juega_boss_tras_teal_dance():
    # Segundo paso de la cadena: Ogerpon ya en 5 energias, sin Planta en mano.
    obs = _menu_combo(_esc_combo_myriad(energias=5, plantas=0),
                      con_ability=False, con_attach=False)
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.PLAY), (
        "con el Ogerpon ya cargado, la jugada es Boss's Orders para subir al "
        "objetivo de 2 premios, no atacar al activo rival")


def test_combo_myriad_gustea_el_bellibolt():
    # Tercer paso: eleccion del objetivo del gusteo.
    obs = _esc_combo_myriad(energias=5, plantas=0)
    yo = obs["current"]["yourIndex"]
    obs["select"] = {
        "context": int(m.SelectContext.TO_ACTIVE), "type": 1,
        "minCount": 1, "maxCount": 1, "contextCard": None, "deck": None,
        "effect": None, "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"area": 5, "index": 0, "playerIndex": 1 - yo, "type": 3}],
    }
    eleccion = m.agent(obs)
    rival = obs["current"]["players"][1 - yo]
    objetivo = rival["bench"][obs["select"]["option"][eleccion[0]]["index"]]["id"]
    assert objetivo == BELLIBOLT_EX, (
        f"el gusteo debe subir al Bellibolt ex (2 premios, letal con Myriad); "
        f"obtuvo {m.card_table[objetivo].name}")


def test_combo_myriad_sin_remate_no_gasta_la_planta():
    # Frontera: sin objetivo de premios en la banca rival (solo un Kilowattrel
    # de 1 premio que ya noqueamos), vuelve el veto de no sobrecargar: la
    # energia NO va al Ogerpon activo via Teal Dance.
    obs = (Escenario(turno=12, paso=227, tac=1, premios_propios=2)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G] * 4, fisicas=4))
           .mi_banca(pk(m.Applin))
           .mi_mano(m.Basic_Grass_Energy, m.Boss_Orders)
           .op_activo(pk(KILOWATTREL, hp=120, max_hp=120))
           .op_banca(pk(KILOWATTREL, hp=120, max_hp=120))
           .op_zonas(mano=5, mazo=30, premios=3)
           .menu_teal_dance()
           .construir())
    obs = _menu_combo(obs)
    assert _tipo_elegido(obs, m.agent(obs)) != int(m.OptionType.ABILITY), (
        "sin remate de premios via Boss's, el Ogerpon con 4 energias que ya "
        "noquea no gasta otra Planta en Teal Dance")


# ---------------------------------------------------------------------
# Pivote Ogerpon retirar->KO, validacion END-TO-END (user, log 86583929
# turno 4 vs Alakazam; memoria ogerpon-retreat-ko-pivot). La regla abarca
# VARIAS decisiones encadenadas y solo se habia verificado el RETIRO aislado.
# Aqui se camina la cadena completa con transiciones simuladas: activo
# Fezandipiti ex estancado (1 energia, su ataque pide 3) + Ogerpon ex de
# banca a 2 energias que con la Planta de Teal Dance llega a 3 y NOQUEA al
# Abra activo rival (Myriad 30+30*3=120 >= 50).
#   Caso A (Planta en MANO):    TD banca -> RETREAT -> promueve Ogerpon -> ATTACK
#   Caso B (Planta en DESCARTE): NS -> recupera -> TD banca -> RETREAT ->
#                                promueve Ogerpon -> ATTACK
#   Caso C (sin Planta alcanzable): no malgasta el retiro (END).
# ---------------------------------------------------------------------
import copy

ABRA_ALAKAZAM = 741     # Abra de la linea Alakazam (50 PV)
KADABRA_ALK = 742


def _pivote_obs(caso):
    esc = (Escenario(turno=6, paso=40, tac=1)
           .mi_activo(pk(m.Fezandipiti_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2),
                     pk(m.Applin)))
    if caso == "A":
        esc = esc.mi_mano(m.Basic_Grass_Energy)
    else:
        esc = esc.mi_mano(m.Night_Stretcher, m.Basic_Grass_Energy)
    obs = (esc
           .op_activo(pk(ABRA_ALAKAZAM, hp=50, max_hp=50))
           .op_banca(pk(KADABRA_ALK, hp=80, max_hp=80))
           .op_zonas(mano=5, mazo=34, premios=6)
           .menu_teal_dance()  # el walker regenera el menu en cada paso
           .construir())
    yo = obs["current"]["players"][0]
    if caso in ("B", "C"):
        # la Planta se construyo en mano (exigencia del builder); en el
        # escenario real esta en el DESCARTE (caso B) o no existe (caso C)
        planta = next(c for c in yo["hand"] if c["id"] == m.Basic_Grass_Energy)
        yo["hand"] = [c for c in yo["hand"] if c is not planta]
        yo["discard"] = list(yo["discard"]) + [planta]
    if caso == "C":
        yo["hand"] = [c for c in yo["hand"] if c["id"] != m.Night_Stretcher]
        yo["discard"] = [c for c in yo["discard"]
                         if c["id"] != m.Basic_Grass_Energy]
    yo["handCount"] = len(yo["hand"])
    return obs


def _pivote_menu_main(obs):
    """Menu MAIN realista para el estado actual (regenerado en cada paso)."""
    yo = obs["current"]["players"][0]
    ops = []
    if any(c["id"] == m.Basic_Grass_Energy for c in yo["hand"]):
        if yo["active"][0]["id"] == m.Teal_Mask_Ogerpon_ex:
            ops.append({"type": 10, "area": 4, "index": 0})
        for k, bp in enumerate(yo["bench"]):
            if bp["id"] == m.Teal_Mask_Ogerpon_ex:
                ops.append({"type": 10, "area": 5, "index": k})
        if not obs["current"]["energyAttached"]:
            i_e = next(i for i, c in enumerate(yo["hand"])
                       if c["id"] == m.Basic_Grass_Energy)
            ops.append({"type": 8, "area": 2, "index": i_e,
                        "inPlayArea": 4, "inPlayIndex": 0})
            for k in range(len(yo["bench"])):
                ops.append({"type": 8, "area": 2, "index": i_e,
                            "inPlayArea": 5, "inPlayIndex": k})
    for i, c in enumerate(yo["hand"]):
        if c["id"] == m.Night_Stretcher:
            ops.append({"type": 7, "index": i})
    act = yo["active"][0]
    if act["id"] == m.Teal_Mask_Ogerpon_ex and len(act["energies"]) >= 3:
        ops.append({"type": 13, "attackId": 120})
    if len(act["energies"]) >= 1 and not obs["current"]["retreated"]:
        ops.append({"type": 12})
    ops.append({"type": 14})
    obs["select"] = {"context": 0, "type": 0, "minCount": 1, "maxCount": 1,
                     "contextCard": None, "deck": None, "effect": None,
                     "remainDamageCounter": 0, "remainEnergyCost": 0,
                     "option": ops}
    return obs


def _pivote_caminar(obs, max_pasos=10):
    """Ejecuta la cadena; devuelve la lista de etiquetas de las decisiones."""
    obs = _pivote_menu_main(copy.deepcopy(obs))
    pasos = []
    for _ in range(max_pasos):
        r = m.agent(obs)
        o = obs["select"]["option"][r[0]]
        t = int(o["type"])
        cur = obs["current"]
        yo = cur["players"][0]
        regen = True
        if t == 12:                                   # RETREAT + promocion
            act = yo["active"][0]
            yo["discard"] = list(yo["discard"]) + [act["energyCards"].pop()]
            act["energies"] = act["energies"][:-1]
            cur["retreated"] = True
            pasos.append("RETREAT")
            obs["select"] = {"context": int(m.SelectContext.SWITCH), "type": 1,
                             "minCount": 1, "maxCount": 1, "contextCard": None,
                             "deck": None, "effect": None,
                             "remainDamageCounter": 0, "remainEnergyCost": 0,
                             "option": [{"area": 5, "index": k,
                                         "playerIndex": 0, "type": 3}
                                        for k in range(len(yo["bench"]))]}
            regen = False
        elif t == 3 and obs["select"]["context"] == int(m.SelectContext.SWITCH):
            k = o["index"]
            nuevo, anterior = yo["bench"][k], yo["active"][0]
            yo["active"] = [nuevo]
            yo["bench"] = ([bp for i, bp in enumerate(yo["bench"]) if i != k]
                           + [anterior])
            pasos.append(f"PROMUEVE {m.card_table[nuevo['id']].name}")
        elif t == 7:                                  # PLAY Night Stretcher
            carta = yo["hand"][o["index"]]
            yo["hand"] = [c for i, c in enumerate(yo["hand"])
                          if i != o["index"]]
            yo["discard"] = list(yo["discard"]) + [carta]
            yo["handCount"] = len(yo["hand"])
            pasos.append("PLAY NS")
            cands = [i for i, c in enumerate(yo["discard"])
                     if c["id"] == m.Basic_Grass_Energy]
            obs["select"] = {"context": int(m.SelectContext.TO_HAND), "type": 1,
                             "minCount": 1, "maxCount": 1, "contextCard": None,
                             "deck": None,
                             "effect": {"id": m.Night_Stretcher,
                                        "playerIndex": 0, "serial": 999},
                             "remainDamageCounter": 0, "remainEnergyCost": 0,
                             "option": [{"area": 3, "index": i,
                                         "playerIndex": 0, "type": 3}
                                        for i in cands]}
            regen = False
        elif t == 3 and obs["select"]["context"] == int(m.SelectContext.TO_HAND):
            carta = yo["discard"][o["index"]]
            yo["discard"] = [c for j, c in enumerate(yo["discard"])
                             if j != o["index"]]
            yo["hand"] = list(yo["hand"]) + [carta]
            yo["handCount"] = len(yo["hand"])
            pasos.append(f"RECUPERA {m.card_table[carta['id']].name}")
        elif t == 10:                                 # Teal Dance
            i_e = next(i for i, c in enumerate(yo["hand"])
                       if c["id"] == m.Basic_Grass_Energy)
            e_card = yo["hand"][i_e]
            yo["hand"] = [c for i, c in enumerate(yo["hand"]) if i != i_e]
            yo["handCount"] = len(yo["hand"])
            tgt = (yo["active"][0] if o["area"] == 4
                   else yo["bench"][o["index"]])
            tgt["energies"] = list(tgt["energies"]) + [int(G)]
            tgt["energyCards"] = list(tgt["energyCards"]) + [e_card]
            pasos.append("TEAL DANCE")
        elif t == 8:                                  # adjunte manual
            e_card = yo["hand"][o["index"]]
            yo["hand"] = [c for i, c in enumerate(yo["hand"])
                          if i != o["index"]]
            yo["handCount"] = len(yo["hand"])
            tgt = (yo["active"][0] if o["inPlayArea"] == 4
                   else yo["bench"][o["inPlayIndex"]])
            tgt["energies"] = list(tgt["energies"]) + [int(G)]
            tgt["energyCards"] = list(tgt["energyCards"]) + [e_card]
            cur["energyAttached"] = True
            pasos.append("ATTACH")
        elif t == 13:
            pasos.append("ATTACK")
            return pasos, obs
        else:
            pasos.append("END")
            return pasos, obs
        if regen:
            obs = _pivote_menu_main(obs)
    raise AssertionError(f"cadena sin cierre: {pasos}")


def _pivote_asserts_ko(pasos, obs):
    assert pasos[-1] == "ATTACK", pasos
    act = obs["current"]["players"][0]["active"][0]
    opa = obs["current"]["players"][1]["active"][0]
    assert act["id"] == m.Teal_Mask_Ogerpon_ex and len(act["energies"]) >= 3
    dmg = 30 + 30 * (len(act["energies"]) + len(opa["energies"]))
    assert dmg >= opa["hp"], (dmg, opa["hp"])


def test_pivote_ogerpon_retreat_ko_planta_en_mano():
    pasos, obs = _pivote_caminar(_pivote_obs("A"))
    assert pasos == ["TEAL DANCE", "RETREAT",
                     "PROMUEVE Teal Mask Ogerpon ex", "ATTACK"], pasos
    _pivote_asserts_ko(pasos, obs)


def test_pivote_ogerpon_retreat_ko_planta_via_night_stretcher():
    pasos, obs = _pivote_caminar(_pivote_obs("B"))
    assert pasos == ["PLAY NS", "RECUPERA Basic {G} Energy", "TEAL DANCE",
                     "RETREAT", "PROMUEVE Teal Mask Ogerpon ex",
                     "ATTACK"], pasos
    _pivote_asserts_ko(pasos, obs)


def test_pivote_ogerpon_sin_planta_no_malgasta_el_retiro():
    pasos, _ = _pivote_caminar(_pivote_obs("C"))
    assert pasos == ["END"], (
        f"sin Planta alcanzable el pivote no dispara: retirar solo pagaria "
        f"una energia para subir un Ogerpon que no ataca; obtuvo {pasos}")


# ---------------------------------------------------------------------
# Deteccion del arquetipo Cornerstone por el NO-ex (386) y por el DESCARTE
# (fase 8: la autopsia vs el mazo sintetico cornerstone_cubchoo mostro 112
# turnos esteriles en 35 derrotas; con solo Cubchoo/Beartic a la vista el
# flag `op_is_cornerstone_deck` no disparaba y la whitelist anti-Cubchoo
# vetaba PLAY Tapu Bulu -- la win condition del matchup -- 38 veces).
# ---------------------------------------------------------------------
CORNERSTONE_NOEX = 386


def _menu_con_tapu(op_activo, op_banca=(), op_descarte=()):
    esc = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Chikorita))
           .mi_mano(m.Tapu_Bulu, m.Basic_Grass_Energy)
           .op_activo(pk(op_activo, hp=70, max_hp=70)))
    if op_banca:
        esc = esc.op_banca(*[pk(b) for b in op_banca])
    if op_descarte:
        esc = esc.op_descarte(*op_descarte)
    # menu_attach_energia() da el select minimo del builder; se reemplaza
    # abajo por el menu PLAY que ejercita la whitelist.
    obs = (esc.op_zonas(mano=4, mazo=38, premios=6)
           .menu_attach_energia().construir())
    yo = obs["current"]["players"][0]
    i_tapu = next(i for i, c in enumerate(yo["hand"])
                  if c["id"] == m.Tapu_Bulu)
    obs["select"] = {"context": int(m.SelectContext.MAIN), "type": 0,
                     "minCount": 1, "maxCount": 1, "contextCard": None,
                     "deck": None, "effect": None, "remainDamageCounter": 0,
                     "remainEnergyCost": 0,
                     "option": [{"type": int(m.OptionType.PLAY),
                                 "index": i_tapu},
                                {"type": int(m.OptionType.END)}]}
    return obs


def test_cornerstone_noex_en_banca_permite_tapu():
    # El no-ex 386 no inmuniza (sin habilidad) pero delata el arquetipo: la
    # whitelist anti-Cubchoo debe ampliarse con Tapu Bulu.
    obs = _menu_con_tapu(CUBCHOO, op_banca=(CORNERSTONE_NOEX,))
    r = m.agent(obs)
    assert obs["select"]["option"][r[0]]["type"] == int(m.OptionType.PLAY), (
        "con un Cornerstone no-ex en la banca rival, Tapu Bulu (la win "
        "condition del matchup) debe poder bajarse")


def test_cornerstone_en_descarte_permite_tapu():
    # Verlo en el DESCARTE tambien identifica el mazo (flag de PLAN; el
    # posicional op_has_ability_immune_active sigue atado al tablero).
    obs = _menu_con_tapu(CUBCHOO, op_descarte=(CORNERSTONE_NOEX,))
    r = m.agent(obs)
    assert obs["select"]["option"][r[0]]["type"] == int(m.OptionType.PLAY), (
        "con un Cornerstone en el descarte rival, el plan del matchup "
        "cambia y Tapu Bulu debe poder bajarse")


def test_cubchoo_puro_sigue_vetando_tapu():
    # Frontera: sin rastro de Cornerstone, el plan anti-Cubchoo del usuario
    # queda INTACTO (Tapu Bulu no se juega vs el mazo Cubchoo puro).
    obs = _menu_con_tapu(CUBCHOO, op_banca=(CUBCHOO,))
    r = m.agent(obs)
    assert obs["select"]["option"][r[0]]["type"] == int(m.OptionType.END), (
        "vs Cubchoo puro la whitelist del usuario excluye a Tapu Bulu")


# ---------------------------------------------------------------------
# Estrategia vs Raging Bolt ex: DESCUADRE DE PREMIOS (user, registro_002
# paso 27 vs Raging Bolt/Ogerpon, PERDIDA). Todo su mazo son ex de 2 premios
# y Bellowing Thunder noquea de un golpe a cualquiera de nuestros ex: si
# nuestro activo ex NO puede noquear, se baja un cuerpo de 1 premio (Tapu
# Bulu), se retira el ex y se pone el 1-premio delante — el KO rival paga 1
# premio y no 2. Cadena real del paso 27, caminada con transiciones.
# ---------------------------------------------------------------------

def _raging_obs(tapu_en_banca=False, ogerpon_cargado=False, bolt_hp=240):
    act = pk(m.Teal_Mask_Ogerpon_ex,
             energias=[G] * (4 if ogerpon_cargado else 1),
             fisicas=(4 if ogerpon_cargado else 1))
    banca = [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2),
             pk(m.Meowth_ex)]
    mano = [m.Forest_of_Vitality, m.Dawn, m.Xerosic_Machinations,
            m.Meganium, m.Basic_Grass_Energy, m.Forest_of_Vitality]
    if tapu_en_banca:
        banca.append(pk(m.Tapu_Bulu, aparecio=True))
    else:
        mano.insert(4, m.Tapu_Bulu)
    return (Escenario(turno=2, paso=27, tac=14, primer_jugador=0,
                      energia_jugada=True, partidario_jugado=True)
            .mi_activo(act)
            .mi_banca(*banca)
            .mi_mano(*mano)
            .mi_descarte(m.Night_Stretcher, m.Forest_of_Vitality,
                         m.Ultra_Ball, m.Lillie_Determination)
            .op_activo(pk(m.Raging_Bolt_ex, hp=bolt_hp, max_hp=240))
            .op_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1),
                      pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1),
                      pk(m.Teal_Mask_Ogerpon_ex))
            .op_zonas(mano=2, mazo=44, premios=6)
            .menu_teal_dance()   # el walker regenera el menu en cada paso
            .construir())


def _raging_menu(obs):
    yo = obs["current"]["players"][0]
    act = yo["active"][0]
    ops = []
    for i, c in enumerate(yo["hand"]):
        if c["id"] in (m.Forest_of_Vitality, m.Tapu_Bulu):
            if (c["id"] == m.Forest_of_Vitality
                    and (obs["current"]["stadiumPlayed"]
                         or obs["current"]["stadium"])):
                continue
            ops.append({"type": int(m.OptionType.PLAY), "index": i})
    if (act["id"] == m.Teal_Mask_Ogerpon_ex
            and len(act["energies"]) >= 3):
        ops.append({"type": int(m.OptionType.ATTACK), "attackId": 120})
    if len(act["energies"]) >= 1 and not obs["current"]["retreated"]:
        ops.append({"type": int(m.OptionType.RETREAT)})
    ops.append({"type": int(m.OptionType.END)})
    obs["select"] = {"context": int(m.SelectContext.MAIN), "type": 0,
                     "minCount": 1, "maxCount": 1, "contextCard": None,
                     "deck": None, "effect": None, "remainDamageCounter": 0,
                     "remainEnergyCost": 0, "option": ops}
    return obs


def _raging_caminar(obs, max_pasos=10):
    pasos = []
    obs = _raging_menu(copy.deepcopy(obs))
    for _ in range(max_pasos):
        r = m.agent(obs)
        o = obs["select"]["option"][r[0]]
        t = int(o["type"])
        yo = obs["current"]["players"][0]
        if t == int(m.OptionType.PLAY):
            carta = yo["hand"][o["index"]]
            yo["hand"] = [c for i, c in enumerate(yo["hand"])
                          if i != o["index"]]
            yo["handCount"] = len(yo["hand"])
            if carta["id"] == m.Forest_of_Vitality:
                obs["current"]["stadium"] = [carta]
                obs["current"]["stadiumPlayed"] = True
                pasos.append("FOREST")
            else:
                d = m.card_table[carta["id"]]
                yo["bench"] = list(yo["bench"]) + [
                    {"id": carta["id"], "serial": carta["serial"],
                     "playerIndex": 0, "hp": d.hp, "maxHp": d.hp,
                     "appearThisTurn": True, "energies": [],
                     "energyCards": [], "tools": [], "preEvolution": []}]
                pasos.append(f"BAJA {d.name}")
        elif t == int(m.OptionType.RETREAT):
            act = yo["active"][0]
            yo["discard"] = list(yo["discard"]) + [act["energyCards"].pop()]
            act["energies"] = act["energies"][:-1]
            obs["current"]["retreated"] = True
            pasos.append("RETREAT")
            obs["select"] = {"context": int(m.SelectContext.SWITCH),
                             "type": 1, "minCount": 1, "maxCount": 1,
                             "contextCard": None, "deck": None,
                             "effect": None, "remainDamageCounter": 0,
                             "remainEnergyCost": 0,
                             "option": [{"area": 5, "index": k,
                                         "playerIndex": 0, "type": 3}
                                        for k in range(len(yo["bench"]))]}
            r2 = m.agent(obs)
            k = obs["select"]["option"][r2[0]]["index"]
            nuevo = yo["bench"][k]
            yo["bench"] = [b for i, b in enumerate(yo["bench"])
                           if i != k] + [act]
            yo["active"] = [nuevo]
            pasos.append(f"PROMUEVE {m.card_table[nuevo['id']].name}")
        else:
            pasos.append("ATTACK" if t == int(m.OptionType.ATTACK) else "END")
            break
        obs = _raging_menu(obs)
    return pasos, obs["current"]["players"][0]["active"][0]


def test_raging_bolt_descuadre_cadena_completa():
    pasos, activo_final = _raging_caminar(_raging_obs())
    assert "BAJA Tapu Bulu" in pasos and "RETREAT" in pasos, pasos
    assert "PROMUEVE Tapu Bulu" in pasos, pasos
    assert activo_final["id"] == m.Tapu_Bulu, (
        f"vs Raging Bolt (todo ex de 2 premios), el turno debe terminar con "
        f"un cuerpo de 1 premio delante; termino {activo_final['id']}: {pasos}")


def test_raging_bolt_con_1premio_en_banca_no_baja_otro_y_retira():
    # Con el Tapu YA en banca no hace falta bajar otro cuerpo: la cadena va
    # directa a retirar y promoverlo.
    pasos, activo_final = _raging_caminar(_raging_obs(tapu_en_banca=True))
    assert "RETREAT" in pasos and "PROMUEVE Tapu Bulu" in pasos, pasos
    assert not any(p.startswith("BAJA") for p in pasos), pasos
    assert activo_final["id"] == m.Tapu_Bulu, pasos


def test_raging_bolt_con_ko_disponible_no_sacrifica():
    # Frontera: el Ogerpon activo cargado NOQUEA al Bolt danado (Myriad
    # 30+30*4=150 >= 120): se ataca, no se regala el tempo del descuadre.
    pasos, activo_final = _raging_caminar(
        _raging_obs(ogerpon_cargado=True, bolt_hp=120))
    assert "RETREAT" not in pasos, pasos
    assert pasos[-1] == "ATTACK", pasos
    assert activo_final["id"] == m.Teal_Mask_Ogerpon_ex, pasos


# ---------------------------------------------------------------------
# Estrategia vs Mega Abomasnow ex: DESCUADRE DE PREMIOS (user, registro_002
# paso 14 y registro_004 paso 17, vs Snover -> Mega Abomasnow ex). Su linea
# one-shotea a cualquiera de nuestros ex; con dos Ogerpon ex en juego y sin
# poder noquear al activo (Ogerpon con 1 energia, Myriad cuesta 3), la linea
# correcta es bajar un cuerpo de 1 premio (Tapu Bulu) y ponerlo delante.
# EXCEPCION (user): la regla NO aplica en nuestro primer turno partiendo
# PRIMEROS -- el rival aun no puede noquearnos su siguiente turno.
# ---------------------------------------------------------------------

def _abomasnow_obs(primer_jugador=1, turno=2, tapu_en_banca=False):
    # Ogerpon ex activo con 1 sola energia: NO puede usar Myriad Leaf Shower
    # (cuesta 3) => no noquea al Snover => se dispara el descuadre.
    act = pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1)
    banca = [pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2),
             pk(m.Meowth_ex)]
    mano = [m.Forest_of_Vitality, m.Dawn, m.Xerosic_Machinations,
            m.Meganium, m.Basic_Grass_Energy, m.Forest_of_Vitality]
    if tapu_en_banca:
        banca.append(pk(m.Tapu_Bulu, aparecio=True))
    else:
        mano.insert(4, m.Tapu_Bulu)
    return (Escenario(turno=turno, paso=14, tac=7, primer_jugador=primer_jugador,
                      energia_jugada=True, partidario_jugado=True)
            .mi_activo(act)
            .mi_banca(*banca)
            .mi_mano(*mano)
            .op_activo(pk(m.Snover))
            .op_banca(pk(m.Snover))
            .op_zonas(mano=5, mazo=41, premios=6)
            .menu_teal_dance()   # el walker regenera el menu en cada paso
            .construir())


def test_abomasnow_descuadre_cadena_completa():
    # Yendo SEGUNDOS (nuestro primer turno es el turno 2), la regla aplica:
    # bajar Tapu Bulu, retirar el Ogerpon ex y ponerlo delante.
    pasos, activo_final = _raging_caminar(_abomasnow_obs())
    assert "BAJA Tapu Bulu" in pasos and "RETREAT" in pasos, pasos
    assert "PROMUEVE Tapu Bulu" in pasos, pasos
    assert activo_final["id"] == m.Tapu_Bulu, (
        f"vs Mega Abomasnow ex, sin poder noquear, el turno debe terminar con "
        f"un cuerpo de 1 premio delante; termino {activo_final['id']}: {pasos}")


def test_abomasnow_primer_turno_primeros_no_sacrifica():
    # EXCEPCION (user): en NUESTRO primer turno partiendo PRIMEROS la regla NO
    # aplica -- el rival aun no puede noquearnos su siguiente turno, no se
    # sacrifica el desarrollo temprano. No se retira el ex.
    pasos, activo_final = _raging_caminar(
        _abomasnow_obs(primer_jugador=0, turno=1))
    assert "RETREAT" not in pasos, pasos
    assert activo_final["id"] == m.Teal_Mask_Ogerpon_ex, (
        f"primer turno partiendo primeros: el descuadre no aplica; "
        f"termino {activo_final['id']}: {pasos}")


def test_abomasnow_primeros_pero_turno_posterior_si_sacrifica():
    # Frontera de la excepcion: la excepcion es SOLO el turno 1. Partiendo
    # primeros pero en un turno posterior (turno 3) la regla vuelve a aplicar.
    pasos, activo_final = _raging_caminar(
        _abomasnow_obs(primer_jugador=0, turno=3))
    assert "RETREAT" in pasos and activo_final["id"] == m.Tapu_Bulu, pasos


# ---------------------------------------------------------------------
# Activo rival INMUNE -> motor Boss's para gustear la banca (user).
# Escenario: Hydrapple ex activo (puede 330) vs Cornerstone Mask Ogerpon ex
# activo (anula a nuestros Pokemon CON habilidad -> atacarlo = 0 dano) con un
# Mega Lucario ex en la banca rival, y Meowth ex en la mano. La jugada correcta
# NO es atacar al Cornerstone (0), sino bajar Meowth ex para que Last-Ditch
# Catch busque un Boss's Orders (en el mazo), gustear el Mega Lucario y atacarlo.
# ---------------------------------------------------------------------
MEGA_LUCARIO = 678


def _menu_inmune_activo(op_activo_id, op_banca_id):
    esc = (Escenario(turno=8, paso=100, tac=0,
                     partidario_jugado=False, estadio_jugado=True,
                     premios_propios=4)
           .mi_activo(pk(m.Hydrapple_ex, energias=[G, G, G, G], fisicas=4))
           .mi_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G, G], fisicas=4),
                     pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G, G], fisicas=3))
           .mi_mano(m.Meowth_ex)
           .op_activo(pk(op_activo_id, energias=[C], fisicas=1))
           .op_banca(pk(op_banca_id, energias=[], fisicas=0))
           .op_zonas(mano=5, mazo=28, premios=4))
    esc._select = {
        "context": int(m.SelectContext.MAIN), "contextCard": None, "deck": None,
        "effect": None, "maxCount": 1, "minCount": 1,
        "option": [
            {"index": 0, "type": 7},          # PLAY Meowth ex
            {"attackId": 195, "type": 13},    # ATTACK Hydrapple Syrup Storm
            {"type": 14},                     # END
        ],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 0,
    }
    return esc.construir()


def test_activo_inmune_juega_meowth_para_gustear_banca():
    obs = _menu_inmune_activo(CORNERSTONE, MEGA_LUCARIO)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    dec = m.agent(obs)
    tipo = obs["select"]["option"][dec[0]]["type"]
    assert tipo == int(m.OptionType.PLAY), (
        f"con el activo rival INMUNE (Cornerstone) y un Mega Lucario gusteable "
        f"en banca, debe JUGAR Meowth ex (motor Boss's), no atacar al muro por "
        f"0; eligio tipo {tipo}")


def test_activo_atacable_no_desvia_a_meowth():
    # Frontera: si el activo rival NO es inmune (Mega Lucario ex de activo, sin
    # la habilidad Cornerstone), `_meowth_immune_boss_engine` NO aplica -- el
    # Hydrapple ex SI le pega (330), asi que el agente ATACA en vez de desviarse
    # a jugar Meowth ex por la via del motor de inmunidad.
    obs = _menu_inmune_activo(MEGA_LUCARIO, CORNERSTONE)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    dec = m.agent(obs)
    tipo = obs["select"]["option"][dec[0]]["type"]
    assert tipo == int(m.OptionType.ATTACK), (
        f"con el activo rival ATACABLE (Mega Lucario), Hydrapple ex debe ATACAR "
        f"(330), no desviarse al motor Meowth-inmune; eligio tipo {tipo}")


# ---------------------------------------------------------------------
# Iron Thorns ex ("Initialization") en el ACTIVO rival apaga las habilidades
# de los Pokemon con Rule Box de AMBOS lados (plan jul 2026, P1.4). El agente
# no debe planear alrededor de Last-Ditch Catch: con Iron Thorns delante,
# buscar Meowth ex "para el fetch de Supporter" es una carta muerta -- mismo
# tratamiento que Team Rocket's Watchtower (`meowth_ability_lock`).
# ---------------------------------------------------------------------

def _fetch_ub_motor_meowth_vs(op_id):
    """UB con mano vacia y motor de refresco disponible en el mazo."""
    obs = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(m.Teal_Mask_Ogerpon_ex, energias=[G], fisicas=1))
           .mi_banca(pk(m.Chikorita))
           .mi_mano()
           .op_activo(pk(op_id, hp=230, max_hp=230))
           .op_zonas(mano=4, mazo=40, premios=6)
           .mazo(m.Meowth_ex, m.Lillie_Determination, m.Tapu_Bulu,
                 m.Hydrapple_ex, m.Applin, m.Chikorita)
           .fetch_ultra_ball()
           .resto_al_descarte()
           .construir())
    eleccion = m.agent(obs)
    sel = obs["select"]
    return sel["deck"][sel["option"][eleccion[0]]["index"]]["id"]


def test_iron_thorns_activo_veta_fetch_de_meowth():
    elegida = _fetch_ub_motor_meowth_vs(m.Iron_Thorns_ex)
    assert elegida != m.Meowth_ex, (
        "con Iron Thorns ex de activo rival (Initialization anula Last-Ditch "
        "Catch), Ultra Ball no debe buscar Meowth ex para el motor de "
        f"Supporter; obtuvo {m.card_table[elegida].name}")


def test_sin_iron_thorns_el_motor_meowth_sigue_vivo():
    # Frontera: con un activo rival neutro (Snorunt) el mismo escenario SI
    # busca Meowth ex (motor de refresco Last-Ditch -> Lillie's).
    elegida = _fetch_ub_motor_meowth_vs(103)  # Snorunt
    assert elegida == m.Meowth_ex, (
        f"sin lock de habilidades el fetch del motor no debe cambiar; obtuvo "
        f"{m.card_table[elegida].name}")


# =====================================================================
# Motor UB de PRIMER turno saliendo SEGUNDOS (user, jul 2026): la UNICA
# razon de jugar Ultra Ball en nuestro primer turno de accion saliendo
# segundos (fuera de banca vacia / Budew activo rival) es BUSCAR MEOWTH EX
# cuando NO tenemos Lillie's Determination y necesitamos jugar una
# (Last-Ditch Catch la trae del mazo). Gate `_ub_ft_case2`. Estos tests
# pinnan el contrato completo tras los gates de la red anti-turno-esteril
# (a7df1ce / 57db985), que usan otra via (score 200) y no deben afectarlo.
# =====================================================================

def _escenario_t2_saliendo_segundo(mano):
    return (Escenario(turno=2, tac=1, primer_jugador=1)
            .mi_activo(pk(m.Tapu_Bulu))
            .mi_banca(pk(m.Chikorita))
            .mi_mano(*mano)
            .op_activo(pk(103, hp=60, max_hp=60))
            .op_zonas(mano=6, mazo=40, premios=6)
            .mazo(m.Meowth_ex, m.Lillie_Determination, m.Tapu_Bulu,
                  m.Hydrapple_ex, m.Applin, m.Teal_Mask_Ogerpon_ex)
            .fetch_ultra_ball()
            .resto_al_descarte()
            .construir())


def _menu_main(obs, opciones):
    obs["select"] = {"context": 0, "contextCard": None, "deck": None,
                     "effect": None, "maxCount": 1, "minCount": 1, "type": 0,
                     "remainDamageCounter": 0, "remainEnergyCost": 0,
                     "option": opciones}
    return obs


def test_ub_t1_segundos_sin_lillie_busca_el_motor_meowth():
    # Sin Lillie's NI Meowth en mano, con ambos en el MAZO: la UB de primer
    # turno saliendo segundos SI se juega (motor Last-Ditch -> Lillie's).
    obs = _menu_main(
        _escenario_t2_saliendo_segundo([m.Ultra_Ball, m.Basic_Grass_Energy,
                                        m.Chikorita]),
        [{"index": 0, "type": 7}, {"index": 2, "type": 7}, {"type": 14}])
    eleccion = m.agent(obs)
    opt = obs["select"]["option"][eleccion[0]]
    assert opt.get("type") == 7 and opt.get("index") == 0, (
        f"la UB del motor Meowth->Lillie's debe jugarse en t2 saliendo "
        f"segundos sin Lillie's en mano; obtuvo {opt}")


def test_ub_t1_segundos_fetch_elige_meowth():
    obs = _escenario_t2_saliendo_segundo([m.Basic_Grass_Energy, m.Chikorita])
    eleccion = m.agent(obs)
    sel = obs["select"]
    elegida = sel["deck"][sel["option"][eleccion[0]]["index"]]["id"]
    assert elegida == m.Meowth_ex, (
        f"el fetch de la UB de primer turno debe traer Meowth ex (motor de "
        f"Lillie's); obtuvo {m.card_table[elegida].name}")


def test_ub_t1_segundos_con_lillie_en_mano_se_veta():
    # Control: con la Lillie's YA en mano el motor no hace falta y la UB de
    # primer turno vuelve a estar vetada (se juega la Lillie's).
    obs = _menu_main(
        _escenario_t2_saliendo_segundo([m.Ultra_Ball, m.Lillie_Determination,
                                        m.Basic_Grass_Energy]),
        [{"index": 0, "type": 7}, {"index": 1, "type": 7}, {"type": 14}])
    eleccion = m.agent(obs)
    opt = obs["select"]["option"][eleccion[0]]
    assert opt.get("type") == 7 and opt.get("index") == 1, (
        f"con Lillie's en mano se juega la Lillie's y la UB queda vetada; "
        f"obtuvo {opt}")


# ---------------------------------------------------------------------------
# Tope de Teal Dance en Ogerpon EXTENDIDO a Cornerstone (autopsia v2.1 p025
# t20, ciclo jul 2026). Cornerstone Stance anula el dano de nuestros Pokemon
# CON habilidad: el Ogerpon no ataca en ese matchup y sobrecargarlo via Teal
# Dance mata de hambre a Tapu Bulu (EL atacante). Mismo patron de extension
# que d801d57 (whitelist anti-Cubchoo ampliada con el muro inmune en juego).

def _esc_corner_td(ogerpon_fisicas):
    return (Escenario(turno=8, paso=1, tac=1)
            .mi_activo(pk(m.Tapu_Bulu, energias=[G], fisicas=1))
            .mi_banca(pk(m.Teal_Mask_Ogerpon_ex,
                         energias=[G] * ogerpon_fisicas,
                         fisicas=ogerpon_fisicas))
            .mi_mano(m.Basic_Grass_Energy)
            .op_activo(pk(117, hp=210, max_hp=210))   # Cornerstone Mask O. ex
            .op_zonas(mano=4, mazo=40, premios=4)
            .menu_teal_dance()
            .construir())


def test_cornerstone_td_tope_2_fisicas_redirige_a_tapu():
    # Ogerpon de banca YA con 2 fisicas: Teal Dance vetada; la Planta de la
    # mano va al Tapu Bulu (la regla cornerstone->Tapu +22000 de energy_score
    # por fin recibe la energia).
    obs = _esc_corner_td(ogerpon_fisicas=2)
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert (tipo, destino) == ("ATTACH", m.Tapu_Bulu), (
        f"vs Cornerstone un Ogerpon con 2 fisicas esta en su tope: la energia "
        f"va a Tapu Bulu; obtuvo {(tipo, destino)}")


def test_cornerstone_td_una_fisica_sigue_permitida():
    # Frontera del tope: con 1 fisica el Ogerpon aun no llega al tope. La
    # Teal Dance no esta VETADA (puede perder contra otras cargas por score,
    # pero el tope no la mata): comprobamos que el veto no dispara mirando
    # que la eleccion NO es END y que si gana una carga, es legitima.
    obs = _esc_corner_td(ogerpon_fisicas=1)
    tipo, destino = _jugada_elegida(obs, m.agent(obs))
    assert tipo in ("ABILITY", "ATTACH"), (
        f"con 1 fisica el turno sigue produciendo (TD o adjunte); "
        f"obtuvo {(tipo, destino)}")


def test_generico_td_dos_fisicas_sin_muro_no_capa():
    # Control inverso: sin Cornerstone/Crustle/muro delante (rival neutro,
    # Kilowattrel 271) el tope no aplica y la Teal Dance del Ogerpon con 2
    # fisicas sigue viva.
    obs = (Escenario(turno=8, paso=1, tac=1)
           .mi_activo(pk(m.Tapu_Bulu, energias=[G], fisicas=1))
           .mi_banca(pk(m.Teal_Mask_Ogerpon_ex, energias=[G, G], fisicas=2))
           .mi_mano(m.Basic_Grass_Energy)
           .op_activo(pk(271, hp=120, max_hp=120))    # Kilowattrel
           .op_zonas(mano=4, mazo=40, premios=4)
           .menu_teal_dance()
           .construir())
    tipo, _ = _jugada_elegida(obs, m.agent(obs))
    assert tipo == "ABILITY", (
        f"sin muro anti-habilidad el tope no aplica: Teal Dance sigue siendo "
        f"la jugada (adjunta + ROBA); obtuvo {tipo}")
