"""Sweep a board along several axes at once and read the decision boundaries.

WHY THIS EXISTS. Every rule in this project was measured on ONE board -- the one
that lost the game it came from -- and pinned with one test on that board. That
is the right way to find a rule and a poor way to know its shape. The questions
a single board cannot answer are the ones that keep costing time:

  * WHERE does the rule change its mind? A threshold fitted on a board with
    three prizes on the table says nothing about two, and the boundary is
    usually not where the comment says it is.
  * Does it stay decided? A rule that retreats at four prizes, attacks at three
    and retreats again at two is not encoding a strategy, it is encoding the
    interaction of two rules that were never measured together.
  * Do two rules that share a menu cancel each other? Three of the changes of
    the last week live in the retreat menu and each was measured alone.

`sweep` walks the cartesian product of the axes, calls the agent on each cell and
returns a table. `boundaries` reports every pair of neighbouring cells whose
decision differs along ONE axis, which is the list of thresholds the code
actually has -- as opposed to the ones its comments claim. `monotone_along`
asserts the property that catches the third question above: along an axis
ordered from "less urgent" to "more urgent", a defensive decision may switch ON
once, and must never switch back off.

It is deliberately built on `state_builder.Scenario` and not on recorded games:
the cells that matter are usually the ones no game produced.

    rows = sweep(build, {"op_prizes": [1, 2, 3, 4], "wounded": [False, True]})
    print(table(rows, "op_prizes", "wounded"))
    assert monotone_along(rows, "op_prizes", lambda r: r["label"] == "RETREAT",
                          reverse=True)
"""

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from cg.api import OptionType  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402

_OPTION_NAME = {int(o): o.name for o in OptionType}


def label(obs, choice):
    """The chosen option as a readable string: `RETREAT`, `PLAY Ultra Ball`, ...

    The observation's options carry a type and an index and nothing else, so the
    name of the card has to be resolved against the zone the option indexes
    into. Without that a grid of decisions is a grid of integers.
    """
    options = (obs.get("select") or {}).get("option") or []
    if not choice:
        return "(no choice)"
    picked = options[choice[0]] if choice[0] < len(options) else None
    if picked is None:
        return f"(out of range {choice})"
    kind = _OPTION_NAME.get(picked.get("type"), str(picked.get("type")))
    index = picked.get("index")
    if index is None:
        return kind
    state = obs["current"]["players"][obs["current"]["yourIndex"]]
    zone = {OptionType.PLAY: "hand", OptionType.EVOLVE: "hand",
            OptionType.ATTACH: "hand", OptionType.CARD: "hand"}.get(
                OptionType(picked["type"]) if picked["type"] in _OPTION_NAME
                else None)
    if zone and index < len(state.get(zone) or []):
        card_id = (state[zone][index] or {}).get("id")
        data = m.card_table.get(card_id)
        return f"{kind} {getattr(data, 'name', card_id)}"
    return f"{kind}[{index}]"


def sweep(factory, axes, reset=True):
    """One row per cell of the cartesian product of `axes`.

    `factory(**cell)` returns the observation for that cell. Each row carries the
    cell's coordinates plus `choice` (what the agent returned) and `label` (what
    that means). A cell whose factory raises is kept with `error` set: an
    impossible board is information, not a crash.
    """
    names = list(axes)
    rows = []
    for values in itertools.product(*(axes[n] for n in names)):
        cell = dict(zip(names, values))
        if reset:
            reset_agent(m)
        try:
            obs = factory(**cell)
        except Exception as exc:                      # noqa: BLE001
            rows.append({**cell, "choice": None, "label": None,
                         "error": f"{type(exc).__name__}: {exc}"})
            continue
        choice = m.agent(obs)
        rows.append({**cell, "choice": tuple(choice),
                     "label": label(obs, choice), "error": None})
    return rows


def boundaries(rows, axes):
    """Every neighbouring pair that differs in ONE axis and decides differently.

    The list of thresholds the code really has. `axes` is the same mapping given
    to `sweep`, and its VALUE ORDER defines what "neighbouring" means.
    """
    names = list(axes)
    index = {tuple(r[n] for n in names): r for r in rows}
    found = []
    for row in rows:
        if row["error"]:
            continue
        key = tuple(row[n] for n in names)
        for i, name in enumerate(names):
            values = axes[name]
            pos = values.index(row[name])
            if pos + 1 >= len(values):
                continue
            nxt = list(key)
            nxt[i] = values[pos + 1]
            other = index.get(tuple(nxt))
            if other is None or other["error"]:
                continue
            if other["label"] != row["label"]:
                found.append({
                    "axis": name,
                    "from": row[name], "to": other[name],
                    "at": {n: row[n] for n in names if n != name},
                    "decision": f"{row['label']} -> {other['label']}",
                })
    return found


def monotone_along(rows, axis, predicate, values, reverse=False):
    """Does `predicate` switch on at most once along `axis`?

    The property a defensive rule has to satisfy: as the board gets MORE
    dangerous the decision may become defensive and must not go back. A rule
    that flips on, off and on again along one axis is two rules interfering, and
    that is exactly the failure a per-board test cannot see.

    Returns the list of violations, each naming the cell where the decision came
    back. `values` is the axis ordered from least to most urgent (or the reverse,
    with `reverse=True`).
    """
    order = list(reversed(values)) if reverse else list(values)
    others = [n for n in rows[0] if n not in (axis, "choice", "label", "error")]
    violations = []
    groups = {}
    for row in rows:
        groups.setdefault(tuple(row[n] for n in others), []).append(row)
    for key, group in groups.items():
        by_value = {r[axis]: r for r in group}
        seen_true = False
        seen_false_after = False
        for value in order:
            row = by_value.get(value)
            if row is None or row["error"]:
                continue
            hit = predicate(row)
            if hit and seen_false_after:
                violations.append({
                    "axis": axis, "at": dict(zip(others, key)),
                    "value": value,
                    "sequence": [(v, predicate(by_value[v]))
                                 for v in order if v in by_value
                                 and not by_value[v]["error"]],
                })
                break
            if hit:
                seen_true = True
            elif seen_true:
                seen_false_after = True
    return violations


def table(rows, row_axis, col_axis, cell="label"):
    """The grid as text, for reading a sweep in a terminal or a report."""
    row_values, col_values = [], []
    for r in rows:
        if r[row_axis] not in row_values:
            row_values.append(r[row_axis])
        if r[col_axis] not in col_values:
            col_values.append(r[col_axis])
    index = {(r[row_axis], r[col_axis]): r for r in rows}
    width = max(
        [len(str(c)) for c in col_values]
        + [len(str(r.get(cell) or r.get("error") or "")) for r in rows]) + 2
    out = [f"{row_axis:>12} | " + "".join(f"{str(c):<{width}}" for c in col_values)]
    out.append("-" * len(out[0]))
    for rv in row_values:
        line = f"{str(rv):>12} | "
        for cv in col_values:
            r = index.get((rv, cv))
            line += f"{str((r.get(cell) if r else None) or (r or {}).get('error') or '-'):<{width}}"
        out.append(line)
    return "\n".join(out)


__all__ = ["sweep", "boundaries", "monotone_along", "table", "label"]
