"""vs Marnie (Froslass + Munkidori): no alimentar cuerpos condenados (Fase C) ni
llenar la banca de cuerpos que pagan peaje (Fase E).

Fases C y E del `docs/plan-matchup-marnie-froslass-munkidori.md`, que quedaron
sin escribir cuando se midieron A, B y D.

**Fase C — no alimentar a un cuerpo CONDENADO** (defecto D3 del plan). Partida 2
turno 10: *Teal Dance sobre el Ogerpon de banca a 80/210 con 8 energías*, que
murió ese mismo turno con 5 Plantas encima. De las 13 Plantas del mazo, 8 se
fueron al descarte dentro de cuerpos noqueados.

El plan pedía un tope de "coste de ataque + 1" mientras hubiera Munkidori en
mesa. **Ese tope no se implementa, y a propósito**: `_attacker_base_damage`
verifica -- contra el daño REAL de seis registros -- que *Myriad Leaf Shower*
escala con la energía del propio Ogerpon (30 + 30 × (propia + la del activo
rival)) y *Syrup Storm* con la Planta de TODA nuestra mesa. Un Ogerpon con 8
energías no está sobrecargado: pega 270+. La premisa "el excedente sobre 3 fue
puro regalo" es falsa; lo que convierte la energía en regalo no es el exceso
sino el **KO**, exactamente como dice el propio diagnóstico del plan ("mientras
el cuerpo VIVE la energía no se desperdicia; el desperdicio ocurre en el KO").

Así que la regla es la otra mitad: `_cuerpo_condenado` + techo
`SCORE_CARGA_CONDENADA`. Dos decisiones de diseño:

  * la ventana se mide **COMPLETA** (con el daño dirigible de Adrena-Brain), al
    revés que la curación de Ripening Charge, que usa la GARANTIZADA. Allí un
    falso positivo gasta la habilidad entera; aquí sólo desvía la Planta a otro
    cuerpo nuestro -- y para Syrup Storm da igual dónde caiga.
  * el techo va en un ENVOLTORIO de `energy_score`, no al final de su cuerpo:
    `_energy_score_base` tiene ~60 `return` repartidos (topes por matchup,
    bandas de banca a 0, pivotes de retirada) y un techo al final sólo alcanzaba
    a la cola genérica -- medido, disparaba 0 veces.

**Fase E — higiene de banca** (defecto D5). Con Froslass en mesa, cada cuerpo
nuestro CON HABILIDAD paga 20 por ronda y por Froslass sin que el rival gaste
nada. Meowth ex ya estaba protegido; **Fezandipiti ex no**: se unía a la lista
de matchups donde sólo se baja con *Flip the Script* viva o con la banca vacía
(E1). Y entre dos jugadas de DESARROLLO se prefiere el cuerpo que no paga peaje
-- pero E2 se midió INERTE (0 decisiones cambiadas) y no se implementa: ver el
comentario homónimo en `main.py`.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk, G

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
TAPU = m.Tapu_Bulu
APPLIN = m.Applin
DIPPLIN = m.Dipplin
FEZ = m.Fezandipiti_ex
MEOWTH = m.Meowth_ex
GRASS = m.Basic_Grass_Energy

FROSLASS = m.Froslass
MUNKIDORI = m.Munkidori
GRIMMSNARL = m.Grimmsnarl_ex
MORGREM = m.Marnies_Morgrem


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


def _destino_de_la_energia(obs, eleccion):
    """Id del Pokemon que recibe la Planta, o None si no se eligio un ATTACH."""
    opt = obs["select"]["option"][eleccion[0]]
    if opt.get("type") != int(m.OptionType.ATTACH):
        return None
    yo = obs["current"]["players"][obs["current"]["yourIndex"]]
    destino = (yo["active"][0] if opt.get("inPlayArea") == int(m.AreaType.ACTIVE)
               else yo["bench"][opt["inPlayIndex"]])
    return destino["id"]


def _jugada(obs, eleccion):
    """('PLAY', id) / ('ATTACH', id) / ('END',) ... de la opcion elegida."""
    opt = obs["select"]["option"][eleccion[0]]
    tipo = opt.get("type")
    yo = obs["current"]["players"][obs["current"]["yourIndex"]]
    if tipo == int(m.OptionType.PLAY):
        return ("PLAY", yo["hand"][opt["index"]]["id"])
    if tipo == int(m.OptionType.ATTACH):
        return ("ATTACH", _destino_de_la_energia(obs, eleccion))
    if tipo == int(m.OptionType.END):
        return ("END",)
    return (tipo,)


# ---------------------------------------------------------------------------
# FASE C — la Planta no va al cuerpo que el rival puede cobrar esta noche
# ---------------------------------------------------------------------------

def _mesa_con_meganium_herido(con_goteo=True):
    """Meganium de banca a 30/160 (dentro de la ventana si hay goteo) junto a un
    Ogerpon ex de banca INTACTO. Reproduce el flip real del paso 172 de
    `registros/marnie/partida_1`, donde la Planta iba al Meganium moribundo.

    `con_goteo=False` es el grupo de CONTROL: el mismo tablero con un rival sin
    Froslass ni Munkidori, donde la ventana vale 0 y la regla no existe.
    """
    banca_rival = ([pk(FROSLASS, hp=90, max_hp=90),
                    pk(MUNKIDORI, hp=110, max_hp=110, energias=[G], fisicas=1)]
                   if con_goteo else [pk(MORGREM, hp=100, max_hp=100)])
    return (Escenario(turno=12, paso=172, tac=1)
            .mi_activo(pk(HYDRAPPLE, hp=110, max_hp=330, energias=[G, G],
                          fisicas=2, pre_evo=[APPLIN, DIPPLIN]))
            .mi_banca(pk(MEGANIUM, hp=30, max_hp=160,
                         pre_evo=[CHIKORITA, BAYLEEF]),
                      pk(OGERPON, hp=210, max_hp=210, energias=[G, G],
                         fisicas=2))
            .mi_mano(GRASS)
            .op_activo(pk(GRIMMSNARL, hp=310, max_hp=320,
                          energias=[G, G], fisicas=2))
            .op_banca(*banca_rival)
            .op_zonas(mano=5, mazo=35, premios=3)
            .menu_attach_energia()
            .construir())


def test_la_planta_no_va_al_cuerpo_condenado():
    obs = _mesa_con_meganium_herido(con_goteo=True)
    destino = _destino_de_la_energia(obs, m.agent(obs))
    assert destino == OGERPON, (
        "con Froslass + Munkidori en mesa, el Meganium a 30 PV está DENTRO de "
        "la ventana de regalo (20 de goteo + 30 dirigibles): la Planta debe ir "
        f"al Ogerpon ex intacto, no al cuerpo que muere con ella encima "
        f"(fue a {m.card_table[destino].name if destino else destino})")


def test_sin_froslass_ni_munkidori_el_reparto_no_cambia():
    # CONTROL: el mismo tablero sin goteo. La ventana vale 0, ningun cuerpo
    # entra en ella y la regla no puede dispararse -- el destino lo decide el
    # criterio de siempre (el Meganium herido, que es quien mas pide energia).
    obs = _mesa_con_meganium_herido(con_goteo=False)
    destino = _destino_de_la_energia(obs, m.agent(obs))
    assert destino == MEGANIUM, (
        "sin Froslass ni Munkidori la Fase C no existe y el reparto debe ser "
        f"el de siempre; obtuvo "
        f"{m.card_table[destino].name if destino else destino}")


def test_el_activo_que_ataca_hoy_no_cuenta_como_condenado():
    # El ACTIVO en ventana pero que ATACA este turno con esa misma Planta no
    # esta condenado: la energia se cobra antes de que el rival juegue. Ogerpon
    # activo a 60 PV con 2 energias -> la 3a le paga Myriad Leaf Shower.
    obs = (Escenario(turno=12, paso=1, tac=1)
           .mi_activo(pk(OGERPON, hp=60, max_hp=210, energias=[G, G], fisicas=2))
           .mi_banca(pk(BAYLEEF, hp=100, max_hp=100, pre_evo=[CHIKORITA]))
           .mi_mano(GRASS)
           .op_activo(pk(GRIMMSNARL, hp=310, max_hp=320, energias=[G, G],
                         fisicas=2))
           .op_banca(pk(FROSLASS, hp=90, max_hp=90),
                     pk(MUNKIDORI, hp=110, max_hp=110, energias=[G], fisicas=1))
           .op_zonas(mano=5, mazo=35, premios=3)
           .menu_attach_energia()
           .construir())
    assert _destino_de_la_energia(obs, m.agent(obs)) == OGERPON, (
        "el activo que ataca HOY con esa Planta cobra antes de morir: la Fase C "
        "no debe desviarla al Bayleef de banca")


# ---------------------------------------------------------------------------
# FASE E — la banca cobra peaje con Froslass en mesa
# ---------------------------------------------------------------------------

def _mesa_para_bajar_fez(con_froslass=True, premios_rival=6):
    """Turno de DESARROLLO con Fezandipiti ex en la mano y la banca en basicos.

    La rama de desarrollo de Fezandipiti ex exige `bench_count <= 2` y que la
    banca sean todo Basicos, asi que la banca es un Tapu Bulu (con un Bayleef
    la rama no se alcanza y el control no distinguiria nada).

    `premios_rival=5` significa que el rival cobro un premio: el tracking deduce
    que nos noquearon y `ko_last_turn` enciende Flip the Script.
    """
    banca_rival = ([pk(FROSLASS, hp=90, max_hp=90)] if con_froslass
                   else [pk(MORGREM, hp=100, max_hp=100)])
    return (Escenario(turno=6, paso=1, tac=1)
            .mi_activo(pk(OGERPON, hp=210, max_hp=210, energias=[G, G, G],
                          fisicas=3))
            .mi_banca(pk(TAPU, hp=140, max_hp=140))
            .mi_mano(FEZ, GRASS)
            .op_activo(pk(GRIMMSNARL, hp=320, max_hp=320, energias=[G],
                          fisicas=1))
            .op_banca(*banca_rival)
            .op_zonas(mano=5, mazo=40, premios=premios_rival)
            .menu_mano(con_adjunte=True)
            .construir())


def test_fezandipiti_no_se_banca_con_froslass_en_mesa():
    obs = _mesa_para_bajar_fez(con_froslass=True)
    jugada = _jugada(obs, m.agent(obs))
    assert jugada != ("PLAY", FEZ), (
        "Fezandipiti ex son DOS premios con habilidad: con Froslass en mesa "
        "paga 20 por ronda sin que el rival gaste nada y Munkidori puede "
        f"rematarlo en la banca. No debe bajarse por desarrollo; jugó {jugada}")


def test_sin_froslass_fezandipiti_si_se_baja():
    # CONTROL: el MISMO tablero sin Froslass. Aqui la rama de desarrollo de
    # Fezandipiti ex sigue viva (15000) y el cuerpo se baja -- lo que prueba que
    # el veto del test anterior lo pone la Fase E1 y no otra condicion del
    # tablero.
    obs = _mesa_para_bajar_fez(con_froslass=False)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ), (
        "sin Froslass la ruta de desarrollo de Fezandipiti ex no cambia")


def _mesa_para_bajar_applin(con_munkidori=True, con_cadena=False):
    """Turno de desarrollo con un Applin en la mano.

    `con_munkidori=True` pone el snipe (30) + un Adrena-Brain (30) sobre la mesa:
    los 40 PV del Applin recién bajado caen dentro de la ventana. `con_cadena`
    añade el Dipplin en la mano y el Forest en juego, con lo que el Applin
    evoluciona el mismo turno y sale de la ventana.
    """
    banca_rival = [pk(FROSLASS, hp=90, max_hp=90)]
    if con_munkidori:
        banca_rival.append(pk(MUNKIDORI, hp=110, max_hp=110,
                              energias=[G], fisicas=1))
    mano = [APPLIN, GRASS] + ([DIPPLIN] if con_cadena else [])
    esc = (Escenario(turno=6, paso=1, tac=1)
           .mi_activo(pk(OGERPON, hp=210, max_hp=210, energias=[G, G, G],
                         fisicas=3))
           .mi_banca(pk(TAPU, hp=140, max_hp=140))
           .mi_mano(*mano)
           .op_activo(pk(GRIMMSNARL, hp=320, max_hp=320, energias=[G],
                         fisicas=1))
           .op_banca(*banca_rival)
           .op_zonas(mano=5, mazo=40, premios=6))
    if con_cadena:
        esc = esc.estadio(m.Forest_of_Vitality)
    return esc.menu_mano(con_adjunte=True).construir()


def test_no_se_baja_un_applin_pelado_dentro_de_la_ventana():
    obs = _mesa_para_bajar_applin(con_munkidori=True)
    jugada = _jugada(obs, m.agent(obs))
    assert jugada != ("PLAY", APPLIN), (
        "un Applin recién bajado tiene 40 PV: el snipe de 30 más UN contador "
        "movido por Adrena-Brain ya lo matan, y sin Dipplin en mano no "
        f"evoluciona este turno. Es un premio regalado; jugó {jugada}")


def test_sin_munkidori_el_snipe_pelado_no_alcanza():
    # CONTROL: solo Froslass. El Applin no tiene habilidad, así que no paga el
    # goteo, y el snipe pelado (30) no llega a sus 40 PV: la regla no se
    # enciende y el desarrollo sigue como siempre.
    obs = _mesa_para_bajar_applin(con_munkidori=False)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", APPLIN), (
        "sin daño dirigible el Applin sobrevive al snipe y se baja igual que "
        "siempre")


def test_con_la_cadena_lista_el_applin_si_baja():
    # EXCEPCIÓN: con Forest en juego y Dipplin en mano, el Applin evoluciona el
    # mismo turno -- la evolución sube los PV máximos sin borrar contadores, así
    # que sale de la ventana. Es justo lo que pide el plan: RESERVAR la pieza
    # hasta poder encadenarla, no renunciar a la línea.
    obs = _mesa_para_bajar_applin(con_munkidori=True, con_cadena=True)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", APPLIN), (
        "con Forest + Dipplin la cadena se monta en un turno y el Applin no "
        "queda expuesto")


def test_con_flip_the_script_viva_si_se_baja():
    # EXCEPCION: si nos noquearon el turno anterior, Flip the Script SE COBRA
    # este turno (roba 3) y el peaje deja de importar -- el mismo criterio que
    # ya usaban Lucario/Crustle/Cornerstone/Sylveon. El KO se declara por el
    # TABLERO (el rival bajo a 5 premios), no tocando el flag a mano.
    obs = _mesa_para_bajar_fez(con_froslass=True, premios_rival=5)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ), (
        "con Flip the Script viva el Fezandipiti ex se cobra ESTE turno: la "
        "Fase E1 no debe vetarlo")
