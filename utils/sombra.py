"""SHADOW harness: it verifies that a refactor of main.py does NOT change decisions.

A complement to the golden corpus for when `registros/` is empty (the
records are transient local data): instead of recorded replays, it generates
the observations by PLAYING self-play games.

It plays self-play games driven by the PRE-refactor version and, on each
decision, also asks the POST-refactor version with the SAME observation
(a deepcopy). Any difference in the choice is a flip of the refactor.

Both instances per seat receive the same stream of observations, so
their global tracking evolves the same way (the same semantics as the golden corpus).

Usage: python utils/sombra.py <pre.py> <post.py> [mirror N] [rival N]
     (pre.py = a copy frozen BEFORE the refactor; exit 1 if there are flips)
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import selfplay as sp  # noqa: E402


def play_with_shadow(drv, shd, deck0, deck1, max_steps=3000):
    """drv/shd: dicts {seat: module or None}. Returns (flips, steps)."""
    from cg import game

    for m_ in list(drv.values()) + list(shd.values()):
        if m_ is not None:
            sp._reset_si_aplica(m_)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start fallo: {sd.errorType}")
    flips, steps = [], 0
    while obs["current"]["result"] == -1 and steps < max_steps:
        yi = obs["current"]["yourIndex"]
        choice = drv[yi].agent(obs)
        if shd[yi] is not None:
            e2 = shd[yi].agent(copy.deepcopy(obs))
            if list(e2) != list(choice):
                sel = obs.get("select") or {}
                flips.append({
                    "paso": steps, "turno": obs["current"]["turn"],
                    "asiento": yi, "contexto": sel.get("context"),
                    "pre": list(choice), "post": list(e2),
                    "opciones": sel.get("option"),
                })
        obs = game.battle_select(choice)
        steps += 1
    return flips, steps


def main(pre_path, post_path, n_espejo=40, n_opponent=40):
    deck = sp.read_deck()
    total_flips, total_dec, total_steps = [], 0, 0

    # Mirror: pre drives both seats; the post shadow on both.
    pre0 = sp.load_agent(pre_path, "pre0")
    pre1 = sp.load_agent(pre_path, "pre1")
    post0 = sp.load_agent(post_path, "post0")
    post1 = sp.load_agent(post_path, "post1")
    for i in range(n_espejo):
        flips, steps = play_with_shadow(
            {0: pre0, 1: pre1}, {0: post0, 1: post1}, deck, deck)
        total_flips += flips
        total_dec += steps
        total_steps += steps
        if flips:
            print(f"  espejo #{i}: {len(flips)} flips")
    print(f"espejo: {n_espejo} partidas, {total_steps} decisiones")

    # vs the opposing bot (the Crustle/Kangaskhan matchup): our seat only.
    opponent_path = ROOT / "deck" / "rivales" / "crustle_kangaskhan.csv"
    if n_opponent and opponent_path.exists():
        from bot_rival import BotRival
        bot_rival = BotRival()
        deck_r = sp.read_deck(opponent_path)
        steps_r = 0
        for i in range(n_opponent):
            asiento = i % 2
            drv = {asiento: pre0, 1 - asiento: bot_rival}
            shd = {asiento: post0, 1 - asiento: None}
            decks = (deck, deck_r) if asiento == 0 else (deck_r, deck)
            flips, steps = play_with_shadow(drv, shd, decks[0], decks[1])
            total_flips += flips
            steps_r += steps
            if flips:
                print(f"  rival #{i}: {len(flips)} flips")
        print(f"rival: {n_opponent} partidas, {steps_r} decisiones")

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
