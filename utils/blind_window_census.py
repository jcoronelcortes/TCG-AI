r"""How much of the turn each guard hung on a spent resource cannot see.

A rule that opens with `not state.supporterPlayed` is not asking a question: it
is asking a question WITH AN EXPIRY DATE. Before the Supporter slot is spent it
arbitrates; after, it is a branch that can never be taken. That window -- the
decisions of the turn that happen after the resource is gone -- is its BLIND
WINDOW, and nothing in this project measured it.

THE TWO BUGS IT EXISTS FOR, both real, both expensive:

  * `93a27eb` (10 August 2026). `_protect_last_supporter` was gated on `not
    state.supporterPlayed`, and Xerosic's Machinations IS a Supporter, so on
    every forced discard that card can produce the flag was ALREADY True. The
    rule was not misfiring, it was UNREACHABLE -- blind window 100% -- and it
    had been since it was written. Reviving it exposed two more defects that had
    been hiding behind it.
  * `f229ff1` (12 August 2026). Every cost veto protecting the Xerosic and the
    Lillie's opens with `not state.supporterPlayed`, because they were written
    to arbitrate TODAY's Supporter slot. Once it is spent they go blind, and an
    Ultra Ball paid for a Chikorita with the cap and the refill -- the two cards
    the agent's own ladder calls its engine.

WHAT IT COUNTS. Every named rule of the engine whose predicate mentions a turn
resource flag is wrapped, and each evaluation is filed under the state of that
flag AT THAT MOMENT:

    ciega       the flag was already spent -- with `not <flag>` in the guard,
                the rule was structurally incapable of firing
    viva        the flag was still available

and three bands fall out:

    CIEGA SIEMPRE          100% of its evaluations. This is
                           `_protect_last_supporter`'s band and the expensive
                           one: the rule is unreachable, whatever it says
    CIEGA LA MAYOR PARTE   over half
    resto                  reported with its number, no band

A BLIND WINDOW IS NOT A DEFECT, and this needs saying because the number is
large. Most of these rules are ABOUT the resource -- "do not spend the Supporter
slot on this" is a question that stops existing once the slot is gone, and going
quiet is the correct behaviour. What makes a row worth reading is either a 100%
(the rule never got to speak at all) or a rule whose SUBJECT is not the resource:
the Ultra Ball cost vetoes of `f229ff1` are about which cards may be discarded,
and they were gated on the Supporter slot for a reason that expired.

Usage:
    python utils/blind_window_census.py --corpus
    python utils/blind_window_census.py --corpus --games 100
    python utils/blind_window_census.py --corpus --dump out.json
    python utils/blind_window_census.py --self-test
"""

import argparse
import inspect
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(_ROOT / "utils"))

import selfplay as sp  # noqa: E402
from rule_census import espacios_del_agente  # noqa: E402

# The turn resources: one per turn, spent once, and every one of them is read as
# a guard somewhere in this agent.
FLAGS = ("supporterPlayed", "energyAttached", "retreatUsed")


def _source_of(function):
    try:
        return inspect.getsource(function)
    except (OSError, TypeError):
        return ""


def flags_of(rule):
    """{flag: negated} for every turn resource the rule's predicate mentions.

    `negated` is what decides whether the window is blind or merely different:
    `not state.supporterPlayed` cannot fire once it is spent, while
    `state.supporterPlayed` cannot fire BEFORE. Both are windows; only the first
    is the shape of the two bugs above, and the report keeps them apart.
    """
    source = _source_of(rule.when)
    out = {}
    for flag in FLAGS:
        if flag not in source:
            continue
        out[flag] = bool(re.search(r"not\s+[\w.]*\b" + flag, source))
    return out


class Counter:
    __slots__ = ("blind", "live", "fired_blind")

    def __init__(self):
        self.blind = self.live = self.fired_blind = 0


def _flag_value(ctx, flag):
    state = getattr(ctx, "state", None)
    return bool(getattr(state, flag, False)) if state is not None else None


def instrument(agent, counters):
    """Wraps every named rule that reads a turn resource. Returns the undo."""
    undo = []
    watched = 0
    # The rules are walked the same way `utils/rule_census.py` walks them --
    # same namespaces, same order, `main` last -- so that a rule carries the
    # SAME label in both censuses and the two reports can be read side by side.
    rules_ns = None
    for name, space in espacios_del_agente(agent):
        if name == "ptcg.engine.rules":
            rules_ns = space
            break
    fixed_rule = rules_ns["_FixedRule"]

    seen = set()
    spaces = sorted(espacios_del_agente(agent), key=lambda pair: pair[0] == "main")
    for module_name, space in spaces:
        for var, value in sorted(space.items(), key=lambda kv: kv[0]):
            candidates = ([(0, value)] if isinstance(value, fixed_rule)
                          else list(enumerate(value))
                          if isinstance(value, (list, tuple)) else [])
            for index, element in candidates:
                if not isinstance(element, fixed_rule) or id(element) in seen:
                    continue
                found = flags_of(element)
                if not found:
                    continue
                seen.add(id(element))
                watched += 1
                short = module_name.split(".")[-1]
                label = f"{short}.{var}[{index}] {element.name}"
                for flag, negated in found.items():
                    counters.setdefault((label, flag, negated), Counter())

                original = element.when

                def when(ctx, _rule=element, _found=found, _label=label,
                         _original=original):
                    for _flag, _negated in _found.items():
                        spent = _flag_value(ctx, _flag)
                        if spent is None:
                            continue
                        counter = counters[(_label, _flag, _negated)]
                        # Blind means "the guard's own condition is already
                        # decided against it": negated guards die once spent,
                        # positive ones before.
                        if spent == _negated:
                            counter.blind += 1
                        else:
                            counter.live += 1
                    result = _original(ctx)
                    if result:
                        for _flag, _negated in _found.items():
                            spent = _flag_value(ctx, _flag)
                            if spent is not None and spent == _negated:
                                counters[(_label, _flag, _negated)].fired_blind += 1
                    return result

                element.when = when
                undo.append(lambda r=element, o=original: setattr(r, "when", o))

    if not watched:
        raise SystemExit(
            "ninguna regla nombrada lee una bandera de recurso de turno: o la "
            "costura no ve al agente, o este arbol no es el que se cree")

    def restore():
        for action in reversed(undo):
            action()
    return restore, watched


def unwatched():
    """Functions that read a turn resource and are NOT named rules of the engine.

    THE COVERAGE OF THIS CENSUS, printed rather than assumed, and it is the
    honest half of the report. The dynamic pass can only wrap `_FixedRule`
    objects, because those are the things this project gives a NAME and resolves
    through one choke point. A plain `def` that opens with `not
    state.supporterPlayed` has the same blind window and no counter can reach
    it -- and that is precisely where `f229ff1` lived: `_ub_cancel_meowth` and
    its siblings are functions, not rules.

    So the gap is counted statically. A row here is not measured, it is
    UNMEASURED, and saying which is the whole difference between a census and a
    reassuring number.
    """
    import ast

    out = []
    files = [_ROOT / "main.py"] + sorted((_ROOT / "ptcg").rglob("*.py"))
    for path in files:
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        if not any(flag in source for flag in FLAGS):
            continue
        tree = ast.parse(source, filename=str(path))
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = "\n".join(lines[node.lineno - 1:getattr(node, "end_lineno",
                                                           node.lineno)])
            # Only the CODE: a flag named in a docstring or a comment is
            # provenance, not a guard.
            code = re.sub(r"#[^\n]*", "", body)
            code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
            for flag in FLAGS:
                if not re.search(r"\b" + flag + r"\b", code):
                    continue
                negated = bool(re.search(r"not\s+[\w.]*\b" + flag, code))
                out.append({
                    "function": node.name,
                    "file": str(path.relative_to(_ROOT)),
                    "line": node.lineno,
                    "flag": flag,
                    "negated": negated,
                })
    return out


def rows(counters):
    out = []
    for (label, flag, negated), counter in counters.items():
        total = counter.blind + counter.live
        if not total:
            continue
        out.append({
            "rule": label, "flag": flag, "negated": negated,
            "blind": counter.blind, "live": counter.live,
            "evaluated": total,
            "blind_pct": 100.0 * counter.blind / total,
            "fired_blind": counter.fired_blind,
        })
    out.sort(key=lambda r: (-r["blind_pct"], -r["evaluated"]))
    return out


# --------------------------------------------------------------------------
# workloads


def pass_corpus(agent):
    import golden_corpus as gc

    records = gc.frozen_records()
    if not records:
        raise SystemExit("no hay corpus congelado en tests/corpus/")
    decisions = 0
    for _, data in sorted(records.items()):
        decisions += len(gc.replay_data(agent, data))
    return f"corpus congelado: {decisions} decisiones en {len(records)} registros"


def pass_games(agent, games):
    from opponent_bot import OpponentBot

    decks = ("deck/opponents/alakazam.csv", "deck/opponents/marnie_grimmsnarl.csv",
             "deck/opponents/crustle_kangaskhan.csv")
    played = 0
    for relative in decks:
        path = _ROOT / relative
        if not path.exists():
            continue
        stats = sp.torneo(agent, OpponentBot(), games, deck_base=sp.read_deck(path))
        played += stats["candidate"] + stats["base"]
    return f"self-play: {played} partidas"


# --------------------------------------------------------------------------
# the two halves


class _FakeState:
    def __init__(self, supporterPlayed):
        self.supporterPlayed = supporterPlayed


class _FakeCtx:
    def __init__(self, supporterPlayed):
        self.state = _FakeState(supporterPlayed)


def self_test(verbose=True):
    """Sensitivity: a guard that cannot fire is reported blind. Specificity: a
    rule that does not read a resource is not watched at all.

    The plant is a rule object of the real class, so what is exercised is the
    wrapper that ships -- `flags_of` reading real source, `_flag_value` reading
    a real ctx shape, and the counter deciding which side of the window it is
    on.
    """
    from ptcg.engine.rules import _FixedRule

    blind_rule = _FixedRule("__canary_blind__",
                            lambda c: not c.state.supporterPlayed,
                            lambda c: 1)
    deaf_rule = _FixedRule("__canary_deaf__", lambda c: True, lambda c: 1)

    found_blind = flags_of(blind_rule)
    found_deaf = flags_of(deaf_rule)
    sensitivity = found_blind.get("supporterPlayed") is True
    specificity = found_deaf == {}

    # ... and the counting half: the same guard, once on each side of the window
    counter = Counter()
    for spent in (True, False):
        if _flag_value(_FakeCtx(spent), "supporterPlayed") == found_blind.get(
                "supporterPlayed"):
            counter.blind += 1
        else:
            counter.live += 1
    counting = (counter.blind, counter.live) == (1, 1)

    if verbose:
        print("autotest del censo de ventana ciega")
        print(f"  sensibilidad   `not state.supporterPlayed` -> negada={found_blind}"
              f"   {'OK' if sensitivity else 'FALLA'}")
        print(f"  especificidad  una regla que no lee recurso -> {found_deaf}"
              f"   {'OK' if specificity else 'FALLA'}")
        print(f"  el contador    gastado/no gastado -> ciega={counter.blind} "
              f"viva={counter.live}   {'OK' if counting else 'FALLA'}")
        if not (sensitivity and specificity and counting):
            print("  EL DETECTOR NO IMPRIME.")
        print()
    return sensitivity and specificity and counting


# --------------------------------------------------------------------------

def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", action="store_true")
    parser.add_argument("--games", type=int, default=0)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--dump", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--no-self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1
    if not args.no_self_test and not self_test():
        return 1
    if not args.corpus and not args.games:
        raise SystemExit("nada que medir: usa --corpus y/o --games N")

    agent = sp.load_agent(_ROOT / "main.py", "censo_ciego")
    counters = {}
    restore, watched = instrument(agent, counters)
    loads = []
    try:
        if args.corpus:
            loads.append(pass_corpus(agent))
        if args.games:
            loads.append(pass_games(agent, args.games))
    finally:
        restore()

    for line in loads:
        print(line)
    data = rows(counters)
    always = [r for r in data if r["blind_pct"] >= 100.0 and r["evaluated"]]
    most = [r for r in data if 50.0 <= r["blind_pct"] < 100.0]
    print(f"\n{watched} reglas nombradas leen una bandera de recurso de turno; "
          f"{len(data)} llegaron a evaluarse\n")

    for title, group in (("CIEGA SIEMPRE (la regla nunca pudo hablar)", always),
                         ("CIEGA LA MAYOR PARTE DEL TURNO", most)):
        print(f"=== {title}  ({len(group)})")
        for row in group[:args.top]:
            sign = "not " if row["negated"] else ""
            print(f"  {row['rule']:<58} {sign}{row['flag']:<16} "
                  f"ciega={row['blind']:>6} viva={row['live']:>6} "
                  f"({row['blind_pct']:.0f}%)")
        if len(group) > args.top:
            print(f"  ... y {len(group) - args.top} mas")
        print()

    outside = unwatched()
    negated_outside = [r for r in outside if r["negated"]]
    print(f"=== FUERA DEL ALCANCE DE ESTE CENSO  ({len(outside)} funciones, "
          f"{len(negated_outside)} con el guard NEGADO)")
    print("  no son reglas nombradas del motor, asi que no hay contador que "
          "las envuelva: su ventana ciega existe y NO esta medida.")
    for row in negated_outside[:args.top]:
        print(f"  {row['function']:<48} not {row['flag']:<16} "
              f"{row['file']}:{row['line']}")
    if len(negated_outside) > args.top:
        print(f"  ... y {len(negated_outside) - args.top} mas")
    print()

    print("UNA VENTANA CIEGA NO ES UN DEFECTO: la mayoria de estas reglas van "
          "SOBRE el recurso, y callar cuando ya se gasto es lo correcto. Lo que "
          "se lee es un 100% -- la regla no llego a hablar nunca -- o una regla "
          "cuyo ASUNTO no es el recurso (los vetos de coste de la Ultra Ball, "
          "f229ff1).")

    if args.dump:
        Path(args.dump).write_text(json.dumps(
            {"watched": data, "unwatched": outside}, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        print(f"\nfilas crudas -> {args.dump}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
