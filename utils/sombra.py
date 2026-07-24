"""Harness SOMBRA: verifica que un refactor de main.py NO cambia decisiones.

Complemento del corpus dorado para cuando `registros/` esta vacio (los
registros son datos locales transitorios): en vez de replays grabados, genera
las observaciones JUGANDO partidas de self-play.

Juega partidas de self-play conducidas por la version PRE-refactor y, en cada
decision, consulta tambien a la version POST-refactor con la MISMA observacion
(deepcopy). Cualquier discrepancia de eleccion es un flip del refactor.

Ambas instancias por asiento reciben el mismo flujo de observaciones, asi que
su tracking global evoluciona igual (misma semantica que el corpus dorado).

Uso: python utils/sombra.py <pre.py> <post.py> [espejo N] [rival N]
     (pre.py = copia congelada ANTES del refactor; exit 1 si hay flips)
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import selfplay as sp  # noqa: E402


def jugar_con_sombra(drv, shd, deck0, deck1, max_pasos=3000):
    """drv/shd: dicts {asiento: modulo o None}. Devuelve (flips, pasos)."""
    from cg import game

    for m_ in list(drv.values()) + list(shd.values()):
        if m_ is not None:
            sp._reset_si_aplica(m_)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start fallo: {sd.errorType}")
    flips, pasos = [], 0
    while obs["current"]["result"] == -1 and pasos < max_pasos:
        yi = obs["current"]["yourIndex"]
        eleccion = drv[yi].agent(obs)
        if shd[yi] is not None:
            e2 = shd[yi].agent(copy.deepcopy(obs))
            if list(e2) != list(eleccion):
                sel = obs.get("select") or {}
                flips.append({
                    "paso": pasos, "turno": obs["current"]["turn"],
                    "asiento": yi, "contexto": sel.get("context"),
                    "pre": list(eleccion), "post": list(e2),
                    "opciones": sel.get("option"),
                })
        obs = game.battle_select(eleccion)
        pasos += 1
    return flips, pasos


def main(ruta_pre, ruta_post, n_espejo=40, n_rival=40):
    deck = sp.leer_deck()
    total_flips, total_dec, total_pasos = [], 0, 0

    # Espejo: pre conduce ambos asientos; sombra post en ambos.
    pre0 = sp.cargar_agente(ruta_pre, "pre0")
    pre1 = sp.cargar_agente(ruta_pre, "pre1")
    post0 = sp.cargar_agente(ruta_post, "post0")
    post1 = sp.cargar_agente(ruta_post, "post1")
    for i in range(n_espejo):
        flips, pasos = jugar_con_sombra(
            {0: pre0, 1: pre1}, {0: post0, 1: post1}, deck, deck)
        total_flips += flips
        total_dec += pasos
        total_pasos += pasos
        if flips:
            print(f"  espejo #{i}: {len(flips)} flips")
    print(f"espejo: {n_espejo} partidas, {total_pasos} decisiones")

    # vs bot rival (matchup Crustle/Kangaskhan): solo nuestro asiento.
    ruta_rival = ROOT / "deck" / "rivales" / "crustle_kangaskhan.csv"
    if n_rival and ruta_rival.exists():
        from bot_rival import BotRival
        bot_rival = BotRival()
        deck_r = sp.leer_deck(ruta_rival)
        pasos_r = 0
        for i in range(n_rival):
            asiento = i % 2
            drv = {asiento: pre0, 1 - asiento: bot_rival}
            shd = {asiento: post0, 1 - asiento: None}
            decks = (deck, deck_r) if asiento == 0 else (deck_r, deck)
            flips, pasos = jugar_con_sombra(drv, shd, decks[0], decks[1])
            total_flips += flips
            pasos_r += pasos
            if flips:
                print(f"  rival #{i}: {len(flips)} flips")
        print(f"rival: {n_rival} partidas, {pasos_r} decisiones")

    print(f"\nTOTAL FLIPS: {len(total_flips)}")
    for f in total_flips[:10]:
        print(" ", f)
    return 1 if total_flips else 0


if __name__ == "__main__":
    pre = sys.argv[1]
    post = sys.argv[2]
    ne = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    nr = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    raise SystemExit(main(pre, post, ne, nr))
