"""FIRING FREQUENCY and FLIPS of the winning-recovery route (`ROUTE_RECOVER`).

The change lives entirely in `ptcg/`, so `selfplay.py --base REF` measures 50%
by construction: that flag only swaps main.py and the `import ptcg...` of the
loaded module resolves through `sys.path`, which points at the CURRENT repo. So
each agent is loaded with `sys.path` pointing at ITS OWN complete tree, and the
`__file__` of `build_turn_plan` is checked before trusting a single number.

The shadow half (base drives, candidate answers the SAME observation) gives the
two things worth knowing before any winrate:

  * how often the route FIRES -- a rule that never fires cannot be measured by
    a gate, and one that fires everywhere is not the narrow route it claims to be;
  * WHICH decisions it flips, which is the only evidence when the frequency is
    low.

Usage:
    python utils/measure_route_recover.py --base TREE [--mirror N] [--bot N]
                                          [--opponent deck/opponents/x.csv]

The opposing deck matters more than the number of games. The route was found vs
Archaludon ex, whose 300 HP is exactly what two recovered Grass reach and one
does not; against a wall immune to our ex (Crustle) `after >= hp` is false by
construction and the route cannot fire at all.
"""

import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for p in (ROOT, ROOT / "utils", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import selfplay as sp  # noqa: E402


def load_from_tree(tree, name):
    """`sp.load_agent` with `sys.path` pointing at `tree`, so the main.py it
    executes imports THAT tree's `ptcg` and not the ambient one."""
    saved = list(sys.path)
    sys.path.insert(0, str(tree))
    try:
        return sp.load_agent(tree / "main.py", name)
    finally:
        sys.path[:] = saved


def tree_of(mod):
    """The tree an agent really executes. The mandatory check: without it a
    head-to-head can be two copies of the same code."""
    return mod.build_turn_plan.__globals__["__file__"]


_OPTION_KIND = {3: "CARD", 7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
                11: "DISCARD", 12: "RETREAT", 13: "ATTACK", 14: "END"}


def _describe(obs, sel, choice, seat):
    """A flip is only auditable if it says WHICH play changed. Without the card
    behind the index, the audit is a list of integers."""
    out = []
    player = obs["current"]["players"][seat]
    for i in choice:
        try:
            opt = sel["option"][i]
        except (KeyError, IndexError, TypeError):
            out.append(f"?{i}")
            continue
        kind = _OPTION_KIND.get(opt.get("type"), str(opt.get("type")))
        zone = ("hand" if kind == "PLAY" else
                "discard" if kind == "CARD" else None)
        cid = None
        if zone == "hand":
            cid = (player["hand"][opt["index"]]["id"]
                   if opt.get("index") is not None
                   and opt["index"] < len(player["hand"]) else None)
        elif zone == "discard":
            cid = (player["discard"][opt["index"]]["id"]
                   if opt.get("index") is not None
                   and opt["index"] < len(player["discard"]) else None)
        out.append(f"{kind}:{cid}" if cid is not None else kind)
    return out


def shadow_game(drv, shd, deck0, deck1, counters, max_steps=3000):
    """`play_with_shadow` plus the route counter, read straight off the
    candidate's own `AGENT_STATE` -- the loaded instance's, not the ambient
    copy, which is the trap that reports zero firings."""
    from cg import game

    for m_ in list(drv.values()) + list(shd.values()):
        if m_ is not None:
            sp._reset_si_aplica(m_)
    obs, sd = game.battle_start(list(deck0), list(deck1))
    if obs is None:
        raise RuntimeError(f"battle_start failed: {sd.errorType}")
    flips, steps = [], 0
    while obs["current"]["result"] == -1 and steps < max_steps:
        yi = obs["current"]["yourIndex"]
        choice = drv[yi].agent(obs)
        shadow = shd.get(yi)
        if shadow is not None:
            other = shadow.agent(copy.deepcopy(obs))
            plan = shadow.AGENT_STATE.turn_plan
            route = getattr(plan, "win_route", "") if plan else ""
            counters["decisions"] += 1
            if route == "RECOVER":
                counters["recover"] += 1
                counters["recover_flip"] += (list(other) != list(choice))
            if list(other) != list(choice):
                sel = obs.get("select") or {}
                open_plan = shadow.AGENT_STATE.turn_plan_open
                if counters.get("dump") is not None and route == "RECOVER":
                    # The board itself, not a summary of it. A flip at 0.05% is
                    # audited by replaying the position, and a guessed board
                    # proves nothing about the one the harness really found.
                    import json
                    n = len(counters["dump"])
                    path = ROOT / "log" / f"rr_flip_{n:02d}.json"
                    path.write_text(json.dumps(
                        {"observation": obs, "base": list(choice),
                         "cand": list(other)}, default=str))
                    counters["dump"].append(str(path))
                flips.append({
                    "step": steps, "turn": obs["current"]["turn"],
                    "seat": yi, "context": sel.get("context"),
                    "route": route,
                    "route_open": getattr(open_plan, "win_route", "")
                                  if open_plan else "",
                    "mode": getattr(plan, "mode", "") if plan else "",
                    "prizes": (len(obs["current"]["players"][yi]["prize"]),
                               len(obs["current"]["players"][1 - yi]["prize"])),
                    "base": _describe(obs, sel, choice, yi),
                    "cand": _describe(obs, sel, other, yi),
                })
        obs = game.battle_select(choice)
        steps += 1
    return flips, steps


def main(base_tree, n_mirror=60, n_bot=60, opponent=None):
    deck = sp.read_deck()
    BASE = Path(base_tree)
    base0 = load_from_tree(BASE, "base0")
    base1 = load_from_tree(BASE, "base1")
    cand0 = load_from_tree(ROOT, "cand0")

    print("tree check (they MUST be different):")
    print("  base:", tree_of(base0))
    print("  cand:", tree_of(cand0))
    assert tree_of(base0) != tree_of(cand0), (
        "both agents are running the same tree: the measurement is worthless")
    assert "ROUTE_RECOVER" in Path(tree_of(cand0)).read_text()
    assert "ROUTE_RECOVER" not in Path(tree_of(base0)).read_text()

    counters = {"decisions": 0, "recover": 0, "recover_flip": 0, "dump": []}
    all_flips = []

    for i in range(n_mirror):
        flips, _ = shadow_game({0: base0, 1: base1}, {0: cand0, 1: None},
                               deck, deck, counters)
        all_flips += flips
        if flips:
            print(f"  mirror #{i}: {len(flips)} flips")

    print(f"mirror: {n_mirror} games")

    bot_path = (Path(opponent) if opponent
                else ROOT / "deck" / "opponents" / "crustle_kangaskhan.csv")
    if n_bot and bot_path.exists():
        print(f"opposing deck: {bot_path.name}")
        from opponent_bot import OpponentBot
        bot = OpponentBot()
        deck_r = sp.read_deck(bot_path)
        for i in range(n_bot):
            seat = i % 2
            decks = (deck, deck_r) if seat == 0 else (deck_r, deck)
            flips, _ = shadow_game(
                {seat: base0, 1 - seat: bot}, {seat: cand0, 1 - seat: None},
                decks[0], decks[1], counters)
            all_flips += flips
            if flips:
                print(f"  bot #{i}: {len(flips)} flips")
        print(f"bot: {n_bot} games")

    d = counters["decisions"]
    print(f"\ndecisions observed : {d}")
    print(f"ROUTE_RECOVER fires: {counters['recover']} "
          f"({100.0 * counters['recover'] / max(1, d):.3f}%)")
    print(f"  ... and changes the choice: {counters['recover_flip']}")
    print(f"TOTAL FLIPS        : {len(all_flips)}")
    for f in all_flips[:25]:
        print("  ", f)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True,
                    help="full tree WITHOUT the change (see the module docstring)")
    ap.add_argument("--mirror", type=int, default=60)
    ap.add_argument("--bot", type=int, default=60)
    ap.add_argument("--opponent", default=None)
    a = ap.parse_args()
    raise SystemExit(main(a.base, a.mirror, a.bot, a.opponent))
