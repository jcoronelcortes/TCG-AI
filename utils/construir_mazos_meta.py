"""Biblioteca de mazos META sinteticos para el modo --rival del self-play.

Fase 8 de la arquitectura de mejora de estrategia. `utils/cosechar_deck_rival.py`
reconstruye mazos desde registros locales, pero los registros son transitorios:
esta pieza NO depende de logs. Cada arquetipo del meta que enfrentamos (memoria
del proyecto: Dragapult, Hop's, Alakazam, Mega Lucario, Comfey, Cornerstone/
Cubchoo) se define AQUI a mano, con ids del pool y una composicion pilotable
por el bot generico (utils/bot_rival.py): lineas evolutivas completas, energia
del tipo que pagan sus ataques y trainers de select simple.

No pretenden ser las listas exactas del meta: son RIVALES DE REFERENCIA
deterministas y legales para medir matchups (utils/selfplay.py --rival) y para
la matriz de matchups (utils/matriz_matchups.py).

Uso:
    python utils/construir_mazos_meta.py            # escribe deck/rivales/*.csv
    python utils/construir_mazos_meta.py --verificar  # ademas battle_start + 4 pasos
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cg.api import CardType, all_card_data

_CARTAS = {c.cardId: c for c in all_card_data()}
_ENERGIAS_BASICAS = set(range(1, 9))  # Basic {G/R/W/L/P/F/D/M} Energy

# --------------------------------------------------------------------------
# Listas por arquetipo: {card_id: copias}. Comentario = nombre de la carta.
# --------------------------------------------------------------------------

MAZOS = {
    # Dragapult ex (dragon: Phantom Dive paga {R}{P}). Linea 4-4-3 + Budew
    # (traba items) y Latias ex (Skyliner). Crispin busca 2 energias basicas
    # de tipos DISTINTOS: clave en un mazo bicolor.
    "dragapult": {
        119: 4,   # Dreepy
        120: 4,   # Drakloak
        121: 3,   # Dragapult ex
        235: 2,   # Budew
        184: 2,   # Latias ex
        1121: 4,  # Ultra Ball
        1198: 4,  # Crispin
        1210: 4,  # Brock's Scouting
        1182: 3,  # Boss's Orders
        1227: 4,  # Lillie's Determination
        1120: 4,  # Crushing Hammer
        1256: 2,  # Team Rocket's Watchtower
        2: 10,    # Basic {R} Energy
        5: 10,    # Basic {P} Energy
    },
    # Hop's (Trevenant pega con {P}{C}{C}; Zacian ex {M}{M}{M}{C}; Snorlax
    # {C}{C}{C}). Hop's Bag busca Pokemon "Hop's"; Choice Band sube el dano.
    "hops": {
        878: 4,   # Hop's Phantump
        879: 4,   # Hop's Trevenant
        299: 2,   # Hop's Zacian ex
        304: 2,   # Hop's Snorlax
        311: 2,   # Hop's Cramorant
        1115: 4,  # Hop's Bag
        1171: 3,  # Hop's Choice Band
        1121: 4,  # Ultra Ball
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        5: 14,    # Basic {P} Energy
        8: 14,    # Basic {M} Energy
    },
    # Alakazam (Powerful Hand = 20 x carta en mano, paga {P}). Dunsparce de
    # muro. Brock's Scouting/Lillie's engordan la mano (su win condition).
    "alakazam": {
        741: 4,   # Abra
        742: 4,   # Kadabra
        743: 3,   # Alakazam
        305: 3,   # Dunsparce (Trading Places)
        1121: 4,  # Ultra Ball
        1210: 4,  # Brock's Scouting
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        1120: 3,  # Crushing Hammer
        5: 28,    # Basic {P} Energy
    },
    # Mega Lucario ex (Aura Jab {F}, Mega Brave {F}{F}): agresivo y barato de
    # cargar. Maximum Belt (ACE SPEC, x1) espejo del matchup real.
    "mega_lucario": {
        677: 4,   # Riolu (80 PV; el limite de 4 copias es por NOMBRE:
                  #        no mezclar con el Riolu 333)
        678: 3,   # Mega Lucario ex
        305: 4,   # Dunsparce
        1121: 4,  # Ultra Ball
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        1120: 4,  # Crushing Hammer
        1158: 1,  # Maximum Belt (ACE SPEC)
        6: 33,    # Basic {F} Energy
    },
    # Comfey mill (Flower Shower nos hace robar 3 -> deckeo) + Brambleghast
    # (confusion). Disrupcion: Hammer, Xerosic, Handheld Fan.
    "comfey": {
        164: 4,   # Comfey
        817: 4,   # Bramblin
        818: 3,   # Brambleghast
        1120: 4,  # Crushing Hammer
        1197: 4,  # Xerosic's Machinations
        1161: 4,  # Handheld Fan
        1227: 4,  # Lillie's Determination
        1121: 3,  # Ultra Ball
        5: 30,    # Basic {P} Energy
    },
    # Raging Bolt ex (registro_002, jul 2026): TODO ex de 2 premios. Su
    # Bellowing Thunder descarta energias basicas y pega 70 por cada una:
    # one-shot a cualquiera de nuestros ex. Los Teal Mask Ogerpon ex rivales
    # aceleran la energia. OJO: el bot generico solo descarta 1 energia en el
    # select del ataque (~70 de dano), asi que el NIVEL absoluto del matchup
    # no es senal; sirve para ejercitar la deteccion y el descuadre.
    "raging_bolt": {
        63: 3,    # Raging Bolt ex
        96: 4,    # Teal Mask Ogerpon ex
        1121: 4,  # Ultra Ball
        1124: 3,  # Pokemon Catcher
        1122: 2,  # Pokegear 3.0
        1127: 2,  # Tera Orb
        1094: 2,  # Bug Catching Set
        1: 16,    # Basic {G} Energy (para los Ogerpon / forraje del Bolt)
        4: 12,    # Basic {L} Energy
        6: 12,    # Basic {F} Energy
    },
    # Cornerstone Mask Ogerpon ex (anula el dano de Pokemon CON habilidad;
    # Demolish {F}{C}{C}) + linea Cubchoo/Beartic (Sheer Cold {W}{W}{W}{C}).
    # El matchup de la colision de whitelists (memoria del proyecto).
    "cornerstone_cubchoo": {
        117: 3,   # Cornerstone Mask Ogerpon ex
        386: 2,   # Cornerstone Mask Ogerpon (no-ex)
        506: 4,   # Cubchoo
        507: 3,   # Beartic
        1121: 4,  # Ultra Ball
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        1147: 3,  # Jumbo Ice Cream
        6: 17,    # Basic {F} Energy
        3: 17,    # Basic {W} Energy
    },
}


def validar(nombre, mazo):
    total = sum(mazo.values())
    assert total == 60, f"{nombre}: {total} cartas (deben ser 60)"
    tiene_basico = False
    for cid, n in mazo.items():
        carta = _CARTAS.get(cid)
        assert carta is not None, f"{nombre}: id {cid} no existe en el pool"
        if cid not in _ENERGIAS_BASICAS:
            assert n <= 4, f"{nombre}: {n}x {carta.name} (max 4)"
        if getattr(carta, "aceSpec", False):
            assert n == 1, f"{nombre}: ACE SPEC {carta.name} debe ser x1"
        if (carta.cardType == CardType.POKEMON and carta.basic):
            tiene_basico = True
    assert tiene_basico, f"{nombre}: sin Pokemon Basico"


def como_lista(mazo):
    lista = []
    for cid, n in mazo.items():
        lista += [cid] * n
    return lista


def escribir(destino):
    destino.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, mazo in MAZOS.items():
        validar(nombre, mazo)
        ruta = destino / f"{nombre}.csv"
        ruta.write_text("\n".join(str(c) for c in como_lista(mazo)) + "\n")
        rutas.append(ruta)
        resumen = ", ".join(
            f"{n}x{_CARTAS[cid].name}" for cid, n in
            Counter({c: v for c, v in mazo.items()
                     if _CARTAS[c].cardType == CardType.POKEMON}).most_common())
        print(f"{ruta.name}: 60 cartas | {resumen}")
    return rutas


def verificar(rutas):
    """battle_start acepta cada mazo y el bot juega 4 pasos sin reventar."""
    sys.path.insert(0, str(_ROOT / "utils"))
    from cg import game
    from bot_rival import BotRival
    deck_nuestro = [int(x) for x in
                    (_ROOT / "deck.csv").read_text().split("\n")[:60]]
    bot = BotRival()
    for ruta in rutas:
        deck_rival = [int(x) for x in ruta.read_text().split()]
        obs, sd = game.battle_start(list(deck_rival), list(deck_nuestro))
        assert obs is not None, (
            f"{ruta.name}: battle_start lo rechazo "
            f"(errorPlayer={sd.errorPlayer}, errorType={sd.errorType})")
        for _ in range(4):
            if obs["current"]["result"] != -1:
                break
            yi = obs["current"]["yourIndex"]
            eleccion = (bot.agent(obs) if yi == 0 else [0])
            obs = game.battle_select(eleccion)
        print(f"{ruta.name}: battle_start OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default=str(_ROOT / "deck" / "rivales"))
    ap.add_argument("--verificar", action="store_true")
    args = ap.parse_args()
    rutas = escribir(Path(args.destino))
    if args.verificar:
        verificar(rutas)
