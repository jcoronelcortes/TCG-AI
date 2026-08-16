"""The arbiter: rollouts break the ties the scorer has no honest opinion about.

Phase S2 (docs/plan-la-busqueda-en-juego-2026-08-15.md §5). The contract:

    arbitrate(n_options, rollout_one, ...) -> (index | None, diagnostics)

`None` means "no opinion", and it is the most common honest answer: the
verdict must clear THE BOARD'S OWN noise floor, measured in the same call by
a second batch of the same best option -- not a tabulated global floor. A
preference that does not clear its floor is not a preference.

The module is PURE CONTROL FLOW. The rollout machinery (determinization,
opponent-deck sampling from the posterior, the mixed policy, the search API
and its `search_end` hygiene) is injected as `rollout_one(option, i)` by the
caller -- `utils/shadow_arbiter.py` in shadow, one day `main.py` behind
`S0.1`. That keeps rule R12 satisfied by construction and makes every branch
of the verdict testable without an engine.

Safety (S5, live from the first shadow run, not after it):
  * a blanket try/except returns None -- a search that raises is invisible;
  * a wall-clock deadline is checked BEFORE every rollout, so a pathological
    board cannot overrun even with budget left;
  * K has a floor of 50: the measured noise floor says K=20 is unusable
    (worst 30 pp / 0.70 margin against 8 pp / 0.36 at K=50).

The verdict reads the PRIZE MARGIN first and the win flag second, for the
reason the matrix reports both: against a saturated opponent the win flag
stops moving while the margin still has resolution.
"""

import time

K_FLOOR = 50


def arbitrate(n_options, rollout_one, *, k=K_FLOOR, wall_s=5.0,
              clock=time.monotonic):
    """Score every option with K rollouts; answer only above the floor.

    `rollout_one(option_index, rollout_index)` returns
    `{"won": bool, "margin": float}` for one rolled-out world, or `None` for
    a world that refused to build (a determinization that would not close is
    an abstention, never an error).

    Returns `(index, diag)` or `(None, diag)`; `diag["reason"]` says which
    exit was taken.
    """
    k = max(k, K_FLOOR)
    diag = {"k": k, "scores": [], "reason": None}
    try:
        deadline = clock() + wall_s
        scores = []
        for option in range(n_options):
            wins, margins = 0, []
            for i in range(k):
                if clock() >= deadline:
                    diag["reason"] = "deadline"
                    return None, diag
                world = rollout_one(option, i)
                if world is None:
                    continue
                wins += world["won"]
                margins.append(world["margin"])
            if not margins:
                diag["reason"] = "no_worlds"
                return None, diag
            scores.append({"option": option,
                           "margin": sum(margins) / len(margins),
                           "winrate": wins / len(margins),
                           "worlds": len(margins)})
        diag["scores"] = scores
        if len(scores) < 2:
            diag["reason"] = "one_option"
            return None, diag

        ranked = sorted(scores, key=lambda s: (s["margin"], s["winrate"]),
                        reverse=True)
        best, second = ranked[0], ranked[1]

        # The board's own floor: a second batch of the SAME best option.
        wins2, margins2 = 0, []
        for i in range(k):
            if clock() >= deadline:
                diag["reason"] = "deadline"
                return None, diag
            world = rollout_one(best["option"], k + i)
            if world is None:
                continue
            wins2 += world["won"]
            margins2.append(world["margin"])
        if not margins2:
            diag["reason"] = "no_worlds"
            return None, diag
        floor_margin = abs(best["margin"] - sum(margins2) / len(margins2))
        floor_win = abs(best["winrate"] - wins2 / len(margins2))
        diag["floor_margin"] = floor_margin
        diag["floor_win"] = floor_win

        separates = ((best["margin"] - second["margin"]) > floor_margin
                     or (abs(best["margin"] - second["margin"]) <= floor_margin
                         and (best["winrate"] - second["winrate"]) > floor_win))
        if separates:
            diag["reason"] = "verdict"
            return best["option"], diag
        diag["reason"] = "floor"
        return None, diag
    except Exception as exc:  # invisible by contract (S5.1)
        diag["reason"] = f"exception: {type(exc).__name__}"
        return None, diag
