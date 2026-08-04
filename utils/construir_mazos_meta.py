"""Library of synthetic META decks for the --rival mode of self-play.

Phase 8 of the strategy improvement architecture. `utils/cosechar_deck_rival.py`
rebuilds decks from local records, but the records are transient:
this piece does NOT depend on logs. Each meta archetype we face (project
memory: Dragapult, Hop's, Alakazam, Mega Lucario, Comfey, Cornerstone/
Cubchoo) is defined HERE by hand, with ids from the pool and a composition the
generic bot (utils/bot_rival.py) can pilot: complete evolution lines, energy
of the type their attacks pay and trainers with a simple select.

They do not claim to be the exact lists of the meta: they are deterministic and legal
REFERENCE OPPONENTS for measuring matchups (utils/selfplay.py --rival) and for
the matchup matrix (utils/matriz_matchups.py).

Usage:
    python utils/construir_mazos_meta.py            # writes deck/rivales/*.csv
    python utils/construir_mazos_meta.py --verificar  # plus battle_start + 4 steps
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
# Lists per archetype: {card_id: copies}. The comment = the card's name.
# --------------------------------------------------------------------------

MAZOS = {
    # Dragapult ex (a dragon: Phantom Dive pays {R}{P}). A 4-4-3 line + Budew
    # (which jams items) and Latias ex (Skyliner). Crispin searches for 2 basic energies
    # of DIFFERENT types: key in a two-colour deck.
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
    # Hop's (Trevenant hits with {P}{C}{C}; Zacian ex {M}{M}{M}{C}; Snorlax
    # {C}{C}{C}). Hop's Bag searches for "Hop's" Pokemon; Choice Band raises the damage.
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
    # Alakazam (Powerful Hand = 20 x card in hand, pays {P}). A Dunsparce as a
    # wall. Brock's Scouting/Lillie's fatten the hand (their win condition).
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
    # Mega Lucario ex (Aura Jab {F}, Mega Brave {F}{F}): aggressive and cheap to
    # charge. A Maximum Belt (ACE SPEC, x1) mirroring the real matchup.
    "mega_lucario": {
        677: 4,   # Riolu (80 HP; the limit of 4 copies is by NAME:
                  #        do not mix with the Riolu 333)
        678: 3,   # Mega Lucario ex
        305: 4,   # Dunsparce
        1121: 4,  # Ultra Ball
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        1120: 4,  # Crushing Hammer
        1158: 1,  # Maximum Belt (ACE SPEC)
        6: 33,    # Basic {F} Energy
    },
    # Comfey mill (Flower Shower makes us draw 3 -> decking out) + Brambleghast
    # (confusion). Disruption: Hammer, Xerosic, Handheld Fan.
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
    # Raging Bolt ex (registro_002, jul 2026): EVERYTHING is a 2-prize ex. Its
    # Bellowing Thunder discards basic energies and hits for 70 per one:
    # a one-shot on any of our ex. The opposing Teal Mask Ogerpon ex
    # accelerate the energy. CAREFUL: the generic bot only discards 1 energy in the
    # attack's select (~70 damage), so the absolute LEVEL of the matchup
    # is not signal; it serves to exercise the detection and the mismatch.
    "raging_bolt": {
        63: 3,    # Raging Bolt ex
        96: 4,    # Teal Mask Ogerpon ex
        1121: 4,  # Ultra Ball
        1124: 3,  # Pokemon Catcher
        1122: 2,  # Pokegear 3.0
        1127: 2,  # Tera Orb
        1094: 2,  # Bug Catching Set
        1: 16,    # Basic {G} Energy (for the Ogerpon / fodder for the Bolt)
        4: 12,    # Basic {L} Energy
        6: 12,    # Basic {F} Energy
    },
    # Cornerstone Mask Ogerpon ex (it cancels the damage of Pokemon WITH an ability;
    # Demolish {F}{C}{C}) + the Cubchoo/Beartic line (Sheer Cold {W}{W}{W}{C}).
    # The matchup of the whitelist collision (project memory).
    "cornerstone_cubchoo": {
        117: 3,   # Cornerstone Mask Ogerpon ex
        386: 2,   # Cornerstone Mask Ogerpon (non-ex)
        506: 4,   # Cubchoo
        507: 3,   # Beartic
        1121: 4,  # Ultra Ball
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        1147: 3,  # Jumbo Ice Cream
        6: 17,    # Basic {F} Energy
        3: 17,    # Basic {W} Energy
    },
    # Iron Thorns ex (jul 2026 plan, P1.4): "Initialization" in the active spot cancels
    # the Rule Box abilities of BOTH sides -> it switches off Teal Dance, Ripening
    # Charge, Last-Ditch Catch and Flip the Script at once. It exercises the
    # `meowth_ability_lock` and plan B through the line with no Rule Box (Meganium /
    # Tapu Bulu). Zapdos as a simple second {L} attacker for the bot.
    "iron_thorns": {
        37: 4,    # Iron Thorns ex (Volt Cyclone {L}{C}{C} 140)
        953: 3,   # Zapdos TWM (Thunderbolt {L}{L}{C} 190)
        1121: 4,  # Ultra Ball
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        1120: 4,  # Crushing Hammer
        1124: 3,  # Pokemon Catcher
        1122: 2,  # Pokegear 3.0
        4: 33,    # Basic {L} Energy
    },
    # Fire aggro (jul 2026 plan, P1.7): our WHOLE deck except Meowth and
    # Fezandipiti is weak to {R} (x2). Gouging Fire ex (a basic ex): Heat Blast
    # {R}{C} 60 -> 120 with weakness already knocks out Ogerpon/Applin; Blaze Blitz
    # {R}{R}{C} 260 one-shots everything. A non-ex Hearthflame Ogerpon comes along
    # (Searing Flame {R}{R}{C} 80 -> 160) for the prize mismatch.
    "fuego_gouging": {
        46: 4,    # Gouging Fire ex
        358: 3,   # Hearthflame Mask Ogerpon (non-ex)
        1121: 4,  # Ultra Ball
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        1120: 4,  # Crushing Hammer
        1124: 2,  # Pokemon Catcher
        1122: 2,  # Pokegear 3.0
        2: 34,    # Basic {R} Energy
    },
    # Item-lock (jul 2026 plan, P1.5): Jellicent ex's "Oceanic Curse" blocks
    # our Items WHILE it is in the active spot; Budew (Itchy Pollen) covers the
    # turns when the Jellicent is not in front. With 10+ items in our deck
    # (UBx4/BCSx4/NSx2/Stamp/PokePad) it exercises the re-prioritisation of
    # Supporters/abilities of the generalised `itchy_pollen_active` flag.
    "jellicent_lock": {
        597: 4,   # Frillish (Oceanic Gloom: it also jams items)
        598: 3,   # Jellicent ex (Power Press {P}{C} 80)
        235: 3,   # Budew
        1121: 4,  # Ultra Ball
        1227: 4,  # Lillie's Determination
        1182: 3,  # Boss's Orders
        1120: 4,  # Crushing Hammer
        5: 35,    # Basic {P} Energy
    },
}


def validar(name, mazo):
    total = sum(mazo.values())
    assert total == 60, f"{name}: {total} cartas (deben ser 60)"
    tiene_basico = False
    for cid, n in mazo.items():
        carta = _CARTAS.get(cid)
        assert carta is not None, f"{name}: id {cid} no existe en el pool"
        if cid not in _ENERGIAS_BASICAS:
            assert n <= 4, f"{name}: {n}x {carta.name} (max 4)"
        if getattr(carta, "aceSpec", False):
            assert n == 1, f"{name}: ACE SPEC {carta.name} debe ser x1"
        if (carta.cardType == CardType.POKEMON and carta.basic):
            tiene_basico = True
    assert tiene_basico, f"{name}: sin Pokemon Basico"


def como_lista(mazo):
    lista = []
    for cid, n in mazo.items():
        lista += [cid] * n
    return lista


def escribir(destino):
    destino.mkdir(parents=True, exist_ok=True)
    rutas = []
    for name, mazo in MAZOS.items():
        validar(name, mazo)
        ruta = destino / f"{name}.csv"
        ruta.write_text("\n".join(str(c) for c in como_lista(mazo)) + "\n")
        rutas.append(ruta)
        resumen = ", ".join(
            f"{n}x{_CARTAS[cid].name}" for cid, n in
            Counter({c: v for c, v in mazo.items()
                     if _CARTAS[c].cardType == CardType.POKEMON}).most_common())
        print(f"{ruta.name}: 60 cartas | {resumen}")
    return rutas


def verificar(rutas):
    """battle_start accepts each deck and the bot plays 4 steps without blowing up."""
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
