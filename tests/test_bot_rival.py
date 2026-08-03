"""El rival de referencia (`utils/bot_rival.py`) juega el motor de habilidades.

Hasta 2026-08-02 el bot decía en su docstring *"Nunca RETREAT ni ABILITY"*.
Consecuencia no obvia: **el harness era CIEGO a los mazos cuyo motor ES una
habilidad**. Contra Marnie's Grimmsnarl ex nunca activaba *Adrena-Brain* de
Munkidori — la habilidad que en `registros/marnie` cobró 5 de los 7 premios que
el rival ganó SIN ATACAR — así que cualquier regla nuestra contra ese motor
medía NEUTRO por construcción.

Estos tests fijan las cuatro piezas sin las cuales el motor no llega a existir:

1. activa habilidades (con guardas anti-bucle: una por Pokémon y turno);
2. al mover contadores coge la cantidad **MÁXIMA** (el fallback genérico cogía
   `minCount`: 1 contador = 10 de daño, la habilidad casi no hacía nada);
3. los pone donde **matan**, y a igualdad donde más premios dan;
4. carga la energía en el cuerpo cuya habilidad la EXIGE (sin eso Munkidori
   nunca se enciende), y se **retira** cuando el activo no puede atacar (sin
   eso un cuerpo gusteado se queda clavado delante para siempre).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(ROOT / "utils"))

from bot_rival import BotRival
from cg.api import AreaType, OptionType, SelectContext

MUNKIDORI = 112
FROSLASS = 104
GRIMMSNARL = 648
MORGREM = 647
OGERPON = 96          # ex, 2 premios
MEGANIUM = 710        # no-ex, 1 premio
TAPU = 920
HYDRAPPLE = 150       # ex, 2 premios, 330 PV


def pk(cid, hp, max_hp, energias=0):
    return {"id": cid, "hp": hp, "maxHp": max_hp,
            "energies": [7] * energias, "energyCards": [], "tools": [],
            "preEvolution": [], "serial": cid * 10 + hp}


def obs(select, yo_activo, yo_banca, op_activo, op_banca, yidx=1, turn=6):
    jugadores = [None, None]
    jugadores[yidx] = {"active": [yo_activo] if yo_activo else [],
                       "bench": list(yo_banca), "prize": [None] * 4,
                       "hand": [], "handCount": 0, "deckCount": 30,
                       "discard": []}
    jugadores[1 - yidx] = {"active": [op_activo] if op_activo else [],
                           "bench": list(op_banca), "prize": [None] * 4,
                           "hand": [], "handCount": 0, "deckCount": 30,
                           "discard": []}
    return {"current": {"players": jugadores, "yourIndex": yidx, "turn": turn,
                        "result": -1, "stadium": [], "retreated": False,
                        "energyAttached": False, "supporterPlayed": False},
            "select": select, "logs": []}


def sel(context, option, minCount=1, maxCount=1):
    return {"context": int(context), "option": option,
            "minCount": minCount, "maxCount": maxCount, "type": 1}


@pytest.fixture
def bot():
    return BotRival()


# --- 1. activa habilidades, con guarda anti-bucle -------------------------

def test_activa_la_habilidad_en_el_menu(bot):
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.ABILITY),
                  "area": int(AreaType.BENCH), "index": 0},
                 {"type": int(OptionType.END)}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 100, 110, 1)],
            pk(OGERPON, 80, 210), [])
    assert bot.agent(o) == [0], "el bot vuelve a ignorar las habilidades"


def test_no_repite_la_misma_habilidad_en_el_turno(bot):
    def menu():
        return obs(sel(SelectContext.MAIN,
                       [{"type": int(OptionType.ABILITY),
                         "area": int(AreaType.BENCH), "index": 0},
                        {"type": int(OptionType.END)}]),
                   pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 100, 110, 1)],
                   pk(OGERPON, 80, 210), [])
    assert bot.agent(menu()) == [0]
    assert bot.agent(menu()) == [1], "segunda activación: bucle infinito"


def test_el_turno_nuevo_rehabilita_la_habilidad(bot):
    def menu(turn):
        o = obs(sel(SelectContext.MAIN,
                    [{"type": int(OptionType.ABILITY),
                      "area": int(AreaType.BENCH), "index": 0},
                     {"type": int(OptionType.END)}]),
                pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 100, 110, 1)],
                pk(OGERPON, 80, 210), [])
        o["current"]["turn"] = turn
        return o
    assert bot.agent(menu(6)) == [0]
    assert bot.agent(menu(6)) == [1]
    assert bot.agent(menu(8)) == [0]


# --- 2 y 3. Adrena-Brain: cantidad máxima y destino que MATA ---------------

def test_mueve_el_maximo_de_contadores(bot):
    o = obs(sel(SelectContext.REMOVE_DAMAGE_COUNTER_COUNT,
                [{"type": 0, "number": 1}, {"type": 0, "number": 2},
                 {"type": 0, "number": 3}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 80, 110, 1)],
            pk(OGERPON, 80, 210), [])
    assert bot.agent(o) == [2], "coge el mínimo: la habilidad casi no hace daño"
    assert bot._contadores == 3


def _fijar_tres_contadores(bot):
    """Encadena el select de CANTIDAD, como en una partida real: es el que deja
    `_contadores` listo para el select de DESTINO del mismo turno."""
    bot.agent(obs(sel(SelectContext.REMOVE_DAMAGE_COUNTER_COUNT,
                      [{"type": 0, "number": 1}, {"type": 0, "number": 2},
                       {"type": 0, "number": 3}]),
                  pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 80, 110, 1)],
                  pk(OGERPON, 80, 210), []))
    assert bot._contadores == 3


def test_los_contadores_van_al_cuerpo_que_matan(bot):
    """Ogerpon ex a 80 no muere con 30; el Meganium a 20 sí."""
    _fijar_tres_contadores(bot)
    o = obs(sel(SelectContext.DAMAGE_COUNTER,
                [{"type": 3, "area": int(AreaType.ACTIVE), "index": 0,
                  "playerIndex": 0},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 80, 110, 1)],
            pk(OGERPON, 80, 210), [pk(MEGANIUM, 20, 160)])
    assert bot.agent(o) == [1]


def test_a_igualdad_de_KO_manda_el_de_mas_premios(bot):
    """Los dos mueren con 30: gana el ex (2 premios) sobre el Meganium (1)."""
    _fijar_tres_contadores(bot)
    o = obs(sel(SelectContext.DAMAGE_COUNTER,
                [{"type": 3, "area": int(AreaType.ACTIVE), "index": 0,
                  "playerIndex": 0},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 80, 110, 1)],
            pk(OGERPON, 20, 210), [pk(MEGANIUM, 20, 160)])
    assert bot.agent(o) == [0], "el ex de 2 premios va primero"


def test_los_contadores_salen_del_cuerpo_mas_danado(bot):
    o = obs(sel(SelectContext.REMOVE_DAMAGE_COUNTER,
                [{"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 1},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 1,
                  "playerIndex": 1}]),
            pk(GRIMMSNARL, 320, 320, 2),
            [pk(MUNKIDORI, 100, 110, 1), pk(MUNKIDORI, 60, 110, 1)],
            pk(OGERPON, 80, 210), [])
    assert bot.agent(o) == [1], "el de 50 de daño da más munición que el de 10"


# --- 4. la energía que enciende el motor, y la retirada -------------------

def test_carga_el_cuerpo_cuya_habilidad_exige_energia(bot):
    """Con el activo ya energizado, la Oscura va al Munkidori seco."""
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.ATTACH), "area": int(AreaType.HAND),
                  "index": 0, "inPlayArea": int(AreaType.ACTIVE),
                  "inPlayIndex": 0},
                 {"type": int(OptionType.ATTACH), "area": int(AreaType.HAND),
                  "index": 0, "inPlayArea": int(AreaType.BENCH),
                  "inPlayIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 110, 110, 0)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [1], "sin esta energía Adrena-Brain no existe"


def test_con_el_activo_seco_la_energia_va_al_activo(bot):
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.ATTACH), "area": int(AreaType.HAND),
                  "index": 0, "inPlayArea": int(AreaType.ACTIVE),
                  "inPlayIndex": 0},
                 {"type": int(OptionType.ATTACH), "area": int(AreaType.HAND),
                  "index": 0, "inPlayArea": int(AreaType.BENCH),
                  "inPlayIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 0), [pk(MUNKIDORI, 110, 110, 0)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [0]


def test_se_retira_si_el_activo_no_puede_atacar(bot):
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.RETREAT)},
                 {"type": int(OptionType.END)}]),
            pk(FROSLASS, 90, 90, 0), [pk(GRIMMSNARL, 320, 320, 2)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [0], (
        "el cuerpo gusteado se queda clavado delante y el gusteo gana solo")


def test_con_ataque_disponible_no_se_retira(bot):
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.RETREAT)},
                 {"type": int(OptionType.ATTACK), "attackId": 937},
                 {"type": int(OptionType.END)}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MORGREM, 100, 100, 2)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [1]


def test_promueve_al_atacante_y_no_al_que_lleva_energia(bot):
    """Grimmsnarl ex (180 de ataque) por delante de Froslass, que no pega.

    Este caso pasaba ya con la regla vieja ("el que mas energia lleva"), asi
    que no distingue las dos politicas: el que si lo hace es el de abajo.
    """
    o = obs(sel(SelectContext.TO_ACTIVE,
                [{"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 1},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 1,
                  "playerIndex": 1}]),
            None, [pk(FROSLASS, 90, 90, 0), pk(GRIMMSNARL, 320, 320, 2)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [1]


def test_el_motor_de_apoyo_no_sube_de_activo_por_llevar_energia(bot):
    """El caso que motivo el cambio de politica (ago 2026).

    Munkidori lleva la energia Oscura porque su Adrena-Brain la EXIGE, pero es
    una habilidad de BANCA: subirlo de activo regala el motor. Con la regla
    vieja ("el que mas energia lleva") ganaba Munkidori y el bot pasaba el
    51.5% de sus pasos con el delante mientras Grimmsnarl ex, su unico
    atacante, esperaba detras -- cobrando 0 premios en 30 de 40 partidas.

    Grimmsnarl ex entra SECO a proposito: el dano que decide es el POTENCIAL,
    porque la politica de ATTACH de este bot carga al activo y el atacante
    recien promovido se carga solo en los turnos siguientes.
    """
    o = obs(sel(SelectContext.TO_ACTIVE,
                [{"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 1},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 1,
                  "playerIndex": 1}]),
            None, [pk(MUNKIDORI, 110, 110, 2), pk(GRIMMSNARL, 320, 320, 0)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [1], (
        "sube el ATACANTE aunque este seco, no la pieza de apoyo cargada")


def test_gustea_al_cuerpo_que_puede_noquear(bot):
    """SWITCH sobre la banca RIVAL: Shadow Bullet (180) mata al Meganium (160)
    pero no al Hydrapple ex (330), que además vale 2 premios: manda el KO."""
    o = obs(sel(SelectContext.SWITCH,
                [{"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 0},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 1,
                  "playerIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 2), [],
            pk(OGERPON, 210, 210),
            [pk(HYDRAPPLE, 330, 330), pk(MEGANIUM, 160, 160)])
    assert bot.agent(o) == [1], (
        "gustea el ex de 2 premios que NO puede matar en vez del KO seguro")
