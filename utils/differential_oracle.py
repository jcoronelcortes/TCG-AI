"""What the agent BELIEVED against what the engine RESOLVED.

T2.2 of docs/night-plan-2026-08-09.md, and the only detector this repository
has for one whole class of defect.

THE DEFECT CLASS. Every example-based test in tests/ asserts that on a given
board the agent picks option X. That is a fine guard against a rule being
deleted, and no guard at all against the rule being right for the wrong reason:
if the agent believes our attack does 30 and the simulator resolves it at 210,
the test asserts the SAME WRONG BELIEF THE CODE HAS and stays green forever.
The play that comes out is legal, plausible, and loses the game. It has already
happened here -- commit 682ef74, "The promotion believed a 30 that the engine
resolves at 210".

No unit test can find that, because a unit test has no independent source of
truth about damage. The simulator IS one, it is free, and until now nothing
used it as an oracle.

WHAT IT DOES NOT DO, and this is the important part: it does not RECOMPUTE what
the agent should have believed. Reimplementing `_our_effective_damage` here
would create a second copy of the damage model, which is the exact failure this
file exists to catch (class B of the night plan: the same quantity computed in
N places, one copy drifting). Instead it READS the belief the agent actually
used -- `AGENT_STATE.plan.remain_hp`, the scratchpad the decision itself wrote
-- and compares it against the board the simulator produced one step later.

The belief is the agent's. The truth is libcg's. Nothing in between is ours.

HOW A DECISION IS JUDGED. Around every `battle_select`:

  1. snapshot the opponent's bodies by `serial` (their unique id) and their hp;
  2. snapshot `AGENT_STATE.plan` -- the attacker, the target and `remain_hp`,
     which is the agent's prediction of the target's hp AFTER our attack;
  3. let the choice resolve;
  4. if exactly one opposing body lost hp or left the field, an attack landed
     on it. Compare.

"Exactly one" is deliberate. Without a reliable map from `plan.target` to a
board serial, attributing a prediction to one of several damaged bodies would
invent findings. A spread attack is counted in `skipped_multi` and reported, so
the blind spot is a number in the output rather than a silence.

THE THREE FINDINGS, in descending order of how much a game costs:

  * `PHANTOM_KO`   -- predicted the target would fall, it did not. The agent
                      spent its turn on an attack that does not close, and the
                      whole plan behind it (the gust, the retreat, the promote)
                      was paid for nothing.
  * `MISSED_KO`    -- did not predict a knockout, got one. Cheap when it lands,
                      but it means the agent is undervaluing that line and will
                      pass it up on the board where it matters.
  * `DAMAGE_DRIFT` -- no knockout either way, but the predicted remaining hp and
                      the real one differ by more than --tolerance. The early
                      warning: the drift is the bug before it grows big enough
                      to flip a knockout.

Every finding is dumped whole -- the observation before the decision included --
so it can be replayed and pinned with the same StateBuilder the suite uses.

VALIDATE IT BEFORE YOU TRUST ITS ZERO. `--self-test` injects a deliberate lie
into the plan and asserts the oracle catches it. A monitor that reports no
violations and has never been shown to fail is indistinguishable from a monitor
that is broken, and this project has the rule written down already
(docs/testing.md: "a green test proves nothing until you have seen it fail").
The self-test runs FIRST by default and aborts the run if it does not fire.

Usage:
    python utils/differential_oracle.py --games 200
    python utils/differential_oracle.py --games 500 --opponent deck/opponents/marnie_grimmsnarl.csv
    python utils/differential_oracle.py --games 50 --dump log/night_2026-08-09/violations
    python utils/differential_oracle.py --self-test-only
"""

import argparse
import copy
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402
from cg.api import OptionType, SelectContext  # noqa: E402

# `remain_hp` starts here: AttackPlan's class default. Anything else means a
# decision in this turn wrote a prediction.
NO_PREDICTION = -1

ATTACK_OPTION = int(OptionType.ATTACK)
ATTACK_CONTEXT = int(SelectContext.ATTACK)


def bodies(obs, player_index):
    """{serial: hp} for every body a player has on the field."""
    try:
        p = obs["current"]["players"][player_index]
    except (KeyError, IndexError, TypeError):
        return {}
    out = {}
    for zone in ("active", "bench"):
        for card in (p.get(zone) or []):
            if card and card.get("serial") is not None:
                out[card["serial"]] = card.get("hp")
    return out


def is_attack_decision(obs, choice):
    """Did THIS decision launch an attack?

    The first version of this file judged any decision after which an opposing
    body's hp had changed, and that was wrong: hp changes for many reasons that
    are not our attack -- a Munkidori moving damage counters, poison between
    turns, the opponent's own effects. Against Comfey, where counters move every
    turn, it invented thousands of findings by comparing a plan formed earlier
    in the turn against a change that plan did not cause.

    So the attack has to be identified from the CHOICE, not inferred from the
    board moving. Two shapes count: picking ATTACK off the MAIN menu, and the
    follow-up context where the engine asks WHICH attack.
    """
    select = obs.get("select") or {}
    if select.get("context") == ATTACK_CONTEXT:
        return True
    options = select.get("option") or []
    for i in (choice or []):
        try:
            if options[i].get("type") == ATTACK_OPTION:
                return True
        except (IndexError, TypeError, AttributeError):
            continue
    return False


def plan_snapshot(mod):
    """The prediction the agent's own decision wrote, or None."""
    try:
        plan = mod.AGENT_STATE.plan
    except AttributeError:
        return None
    remain = getattr(plan, "remain_hp", NO_PREDICTION)
    if remain == NO_PREDICTION:
        return None
    return {"attacker": getattr(plan, "attacker", -1),
            "target": getattr(plan, "target", -1),
            "attack_index": getattr(plan, "attack_index", -1),
            "remain_hp": remain}


def judge(before, after, plan, tolerance):
    """(finding or None, skip reason: False | True (spread) | "sentinel").

    `before`/`after` are {serial: hp} of the OPPONENT's bodies.
    """
    hit = []
    for serial, hp_before in before.items():
        hp_after = after.get(serial)
        if hp_after is None:                      # left the field: knocked out
            hit.append((serial, hp_before, None))
        elif hp_after != hp_before:
            hit.append((serial, hp_before, hp_after))
    if not hit:
        return None, False                        # no attack landed this step
    if len(hit) > 1:
        return None, True                         # spread: cannot attribute
    serial, hp_before, hp_after = hit[0]

    # Healing is not our attack landing; the projector does not predict it.
    if hp_after is not None and hp_after > hp_before:
        return None, False

    # `remain_hp` left EQUAL to the target's current hp is not a prediction of
    # zero damage, it is the absence of a prediction. Several paths in main.py
    # (the Dipplin and Tapu Bulu "who attacks" blocks, ~7113 and ~7134) set
    # attacker/target/attack_index and fill remain_hp with `op_active.hp` as a
    # placeholder, because no damage projection was computed there. Read as a
    # prediction it says "this attack does nothing", so every one of them came
    # back as MISSED_KO -- 84 % of that finding class before this guard.
    #
    # A genuine prediction of zero damage (an immune wall) is indistinguishable
    # from the sentinel without changing the agent, which tonight's standing
    # orders forbid. So it is skipped and COUNTED, never silently dropped.
    if plan["remain_hp"] == hp_before:
        return None, "sentinel"

    predicted_ko = plan["remain_hp"] <= 0
    # A body at 0 hp IS knocked out; the engine simply has not removed it from
    # the field yet in the observation that follows the attack. Requiring it to
    # have disappeared reported every lethal attack as a phantom.
    actual_ko = hp_after is None or hp_after <= 0
    common = {"serial": serial, "hp_before": hp_before, "hp_after": hp_after,
              "predicted_remain_hp": plan["remain_hp"], "plan": plan}

    if predicted_ko and not actual_ko:
        return {"kind": "PHANTOM_KO",
                "detail": f"predicted the body would fall; it is at {hp_after}",
                **common}, False
    if actual_ko and not predicted_ko:
        return {"kind": "MISSED_KO",
                "detail": f"predicted {plan['remain_hp']} hp left; it was knocked out",
                **common}, False
    if not actual_ko:
        drift = abs(hp_after - plan["remain_hp"])
        if drift > tolerance:
            return {"kind": "DAMAGE_DRIFT", "drift": drift,
                    "detail": f"predicted {plan['remain_hp']} hp left, engine resolved {hp_after}",
                    **common}, False
    return None, False


def over_games(games, opponent=None, tolerance=0, liar=None, progress=None):
    """Drive complete games and judge every decision. Returns (stats, findings)."""
    from cg import game

    agents = [sp.load_agent(str(_ROOT / "main.py"), "oracle_p0"),
              sp.load_agent(str(_ROOT / "main.py"), "oracle_p1")]
    deck = sp.read_deck()
    op_deck = sp.read_deck(opponent) if opponent else list(deck)

    stats = {"games": 0, "decisions": 0, "attack_decisions": 0,
             "attacks_judged": 0, "skipped_multi": 0,
             "skipped_sentinel": 0, "skipped_repeat_attack": 0, "forfeits": 0}
    findings = []

    for game_no in range(games):
        for m in agents:
            sp._reset_si_aplica(m)
        obs, _sd = game.battle_start(list(deck), list(op_deck))
        if obs is None:
            continue
        stats["games"] += 1
        judged_turns = set()
        steps = 0
        try:
            while obs and obs["current"]["result"] == -1 and steps < 3000:
                yi = obs["current"]["yourIndex"]
                opp = 1 - yi
                mod = agents[yi]
                before = bodies(obs, opp)
                snapshot = copy.deepcopy(obs)
                try:
                    choice = mod.agent(obs)
                except Exception as exc:          # a forfeit, not an oracle finding
                    stats["forfeits"] += 1
                    findings.append({"kind": "AGENT_RAISED", "game": game_no,
                                     "step": steps, "detail": repr(exc),
                                     "observation": snapshot})
                    break
                if liar is not None:
                    liar(mod)
                plan = plan_snapshot(mod)
                attacking = is_attack_decision(snapshot, choice)
                obs = game.battle_select(choice)
                stats["decisions"] += 1
                steps += 1
                if attacking:
                    stats["attack_decisions"] += 1
                if plan is None or obs is None or not attacking:
                    continue

                # ONE JUDGEMENT PER TURN, per seat. The plan is written once per
                # turn -- main.py ~3522 rebuilds AttackPlan() only when
                # `AGENT_STATE.pre_turn != state.turn` -- while an attack can
                # land more than once in a turn (Festival Grounds' double
                # attack) and the MAIN choice plus its follow-up ATTACK context
                # are two decisions for the same attack. Judging every one of
                # them compares a single prediction against several different
                # boards: on festival_lead the findings arrive at consecutive
                # steps carrying an identical prediction (step 116 "predicted
                # 230, resolved 200", step 117 "predicted 230, resolved 70").
                #
                # The prediction belongs to the FIRST attack of the turn. The
                # rest cannot be attributed without a per-attack plan, which
                # would mean changing the agent, so they are skipped and counted.
                turn_key = (yi, (snapshot.get("current") or {}).get("turn"))
                if turn_key in judged_turns:
                    stats["skipped_repeat_attack"] += 1
                    continue
                after = bodies(obs, opp)
                finding, skip = judge(before, after, plan, tolerance)
                if skip == "sentinel":
                    stats["skipped_sentinel"] += 1
                    continue
                if skip:
                    stats["skipped_multi"] += 1
                    continue
                judged_turns.add(turn_key)
                if finding:
                    stats["attacks_judged"] += 1
                    findings.append({**finding, "game": game_no, "step": steps,
                                     "seat": yi, "choice": list(choice or []),
                                     "select_context": (snapshot.get("select") or {}).get("context"),
                                     "observation": snapshot})
                elif before != after:
                    stats["attacks_judged"] += 1
        finally:
            game.battle_finish()
        if progress and stats["games"] % progress == 0:
            print(f"  ... {stats['games']}/{games} partidas, "
                  f"{len(findings)} hallazgos", flush=True)
    return stats, findings


def _lie_always_ko(mod):
    """Make every plan claim the target falls. Must produce PHANTOM_KO."""
    try:
        mod.AGENT_STATE.plan.remain_hp = 0
    except AttributeError:
        pass


def self_test(games=6, opponent=None):
    """Show the oracle failing, AND show it staying quiet, before trusting it.

    Two halves, because the first version of this file only had the first one
    and that was not enough. Sensitivity says the detector can catch a lie.
    SPECIFICITY says it does not invent one -- and it was specificity that broke:
    judging every decision after which the board moved produced ~16 700 findings
    over 38 000 games, of which the overwhelming majority were damage counters
    being shuffled around by a Munkidori, not our attack missing.

    A detector that fires on everything is as useless as one that never fires,
    and only the second failure looks like a result.
    """
    print("Auto-test 1/2 (sensibilidad): se inyecta un plan que miente ...", flush=True)
    _stats, findings = over_games(games, opponent=opponent, liar=_lie_always_ko)
    phantoms = [f for f in findings if f["kind"] == "PHANTOM_KO"]
    if not phantoms:
        print("AUTO-TEST FALLIDO: la mentira no se detecto. El oraculo no es fiable.",
              file=sys.stderr)
        return False
    print(f"  OK: {len(phantoms)} PHANTOM_KO sobre la mentira.", flush=True)

    print("Auto-test 2/2 (especificidad): solo se juzgan decisiones de ATAQUE ...",
          flush=True)
    stats, honest = over_games(games, opponent=opponent)
    judged = stats["attacks_judged"]
    if judged > stats["attack_decisions"]:
        print(f"AUTO-TEST FALLIDO: {judged} ataques juzgados sobre solo "
              f"{stats['attack_decisions']} decisiones de ataque. El oraculo "
              f"esta atribuyendo cambios que no causo un ataque.", file=sys.stderr)
        return False
    print(f"  OK: {judged} juzgados sobre {stats['attack_decisions']} decisiones "
          f"de ataque, {len(honest)} hallazgos.\n", flush=True)
    return True


def dump(findings, where):
    out = Path(where)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for n, f in enumerate(findings):
        name = f"{f['kind'].lower()}_g{f.get('game', 0)}_s{f.get('step', 0)}_{n}.json"
        path = out / name
        path.write_text(json.dumps({"observation": f.pop("observation", None),
                                    "finding": f}, indent=1), encoding="utf-8")
        written.append(str(path))
    return written


def report(stats, findings):
    print("\nOraculo diferencial: la creencia del agente contra lo que resolvio el motor")
    print(f"Partidas: {stats['games']}   decisiones: {stats['decisions']}   "
          f"decisiones de ataque: {stats['attack_decisions']}   "
          f"ataques juzgados: {stats['attacks_judged']}")
    print(f"Sin atribuir (dano repartido en varios cuerpos): {stats['skipped_multi']}")
    print(f"Sin prediccion (remain_hp centinela = vida actual): {stats['skipped_sentinel']}")
    print(f"Ataque repetido en el mismo turno (plan es por turno): {stats['skipped_repeat_attack']}")
    if stats["forfeits"]:
        print(f"El agente lanzo excepcion en {stats['forfeits']} partidas")
    by_kind = {}
    for f in findings:
        by_kind.setdefault(f["kind"], []).append(f)
    if not findings:
        print("\nHallazgos: NINGUNO. (El auto-test confirma que el oraculo sabe fallar.)")
        return
    print("\nHallazgos:")
    for kind in ("AGENT_RAISED", "PHANTOM_KO", "MISSED_KO", "DAMAGE_DRIFT"):
        items = by_kind.get(kind) or []
        if items:
            print(f"  {kind}: {len(items)}")
            for f in items[:5]:
                print(f"    partida {f.get('game')} paso {f.get('step')}: {f['detail']}")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--opponent", default=None,
                        help="csv del mazo rival (sin el: espejo)")
    parser.add_argument("--tolerance", type=int, default=0,
                        help="diferencia de hp que no se reporta como DAMAGE_DRIFT")
    parser.add_argument("--dump", default=None, help="directorio para las observaciones")
    parser.add_argument("--progress", type=int, default=None)
    parser.add_argument("--no-self-test", action="store_true",
                        help="no validar el oraculo antes de fiarse de su cero")
    parser.add_argument("--self-test-only", action="store_true")
    args = parser.parse_args(argv)

    if not args.no_self_test:
        if not self_test():
            return 2
        if args.self_test_only:
            return 0

    stats, findings = over_games(args.games, opponent=args.opponent,
                                 tolerance=args.tolerance, progress=args.progress)
    report(stats, findings)
    if args.dump and findings:
        written = dump(findings, args.dump)
        print(f"\n{len(written)} observaciones escritas en {args.dump}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
