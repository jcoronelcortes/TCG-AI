"""Grading a decision against THE RULES instead of against another heuristic.

⚠️ **THIS ORACLE READS HIDDEN INFORMATION AND CAN NEVER BE A PLAY-TIME POLICY.**
It fills in the opponent's hand from the opponent's own observation, which a
player does not have. It is a *grader*: it answers "was this choice right?" after
the fact, on games we already hold both sides of. Wiring it into `main.py` would
be cheating at the competition. That sentence is here, first, on purpose.

WHY IT EXISTS. Every instrument in this project grades the agent against another
heuristic -- including `utils/differential_oracle.py`, whose residue turned out
to be half the opponent deck's fault rather than a defect
([[el-oraculo-es-un-espejo-y-la-mitad-de-su-residuo-es-del-mazo-rival]]). And the
reference bot is SATURATED: we win 95 % of simulated games, so every close-game
capability is measured in a vanishing fraction of them -- the caveat that
withheld both of 14 August's list candidates
([[la-planta-16-vale-nueve-centesimas-de-premio-y-ninguna-carta-se-gana-el-corte]]).
A rollout to game end grades against the engine's own rules. That is a different
kind of answer, and it is phase D of the engine-source plan.

WHAT IT DOES. `rollout(obs, forced_choice, ...)` opens a search from a real
observation, forces one option as the first selection, plays the rest to the end
under a policy, and reports who won. Run it K times per option and the difference
is what the choice was worth.

## Two things measured while building it, and both change the plan that asked for it

**1. The prizes are unknowable, so sampling is not optional.** The plan
(`docs/night-plan-2026-08-13.md`, Q7) defaulted to an *omniscient*
determinization -- "read the true hidden state from the battle we are driving".
Half of it cannot be read at all: a seat's own prize cards come back as `None` in
that seat's OWN observation. Measured, not assumed. So `determinize` is
necessarily part omniscient (the opponent's hand, which their observation does
show) and part **sampled** (both prize sets, and therefore both deck remainders,
drawn from the multiset that is left). K rollouts average over that sampling;
one rollout does not, and the docstring of any result must say which.

**2. The engine accepts a determinization that does not add up.** `search_begin`
validates only `len(...) < count` -- too FEW cards is an error, too many is
silently tolerated. A first attempt here handed the opponent 46 cards for a deck
of 40 because it counted only hand, bench, active and discard, and the API took
it: the rollout then played a game with six cards that were not in that deck.
So `determinize` **closes its own arithmetic per seat** (`seen + deck + prize +
hand == 60`) and raises if it does not. It reads the zones with
`card_census.zones_of`, which already knows that a card can be an attached
energy, a tool, a pre-evolution or the stadium.

**3. The API is not reproducible, and the plan made reproducibility its
mandatory specificity half.** Same seed, same forced choice, same
determinization: 140 steps against 122. `search_begin` takes no seed, so the
shuffles inside a rollout are the engine's own and ours reaches only the
determinization and the policy. The oracle is therefore an **estimator**, not a
replay, and `self_test` measures its noise floor instead of asserting it away.

## What it costs, and what it can actually resolve

Measured on this machine, `policy="random"`, one core:

    9.3 ms per full rollout · 0.06 ms/step · 143 steps to game end

which is *cheaper* than the plan's S4 estimate of 0.02 s. K=20 rollouts on two
options is 0.37 s, so 280 ties cost under two minutes.

⚠️ **And the noise floor sets K.** It is measured as a distribution and not as
one number, because the first attempt here quoted a single pair of batches
(17 pp / 0.03) and the very next run of the same test returned 7 pp / 0.33 --
the instrument catching its own author in exactly the error it exists to
prevent. Six independent pairs of batches of the SAME option, same board:

    K= 20   winrate floor  median  7.5 pp (worst 30.0)   margin floor  0.28 (worst 0.70)
    K= 50   winrate floor  median  6.0 pp (worst  8.0)   margin floor  0.10 (worst 0.36)
    K=100   winrate floor  median  4.0 pp (worst  6.0)   margin floor  0.09 (worst 0.24)

**K=20 is not enough for anything**: its worst pair disagrees by 30 pp on two
batches of the same option. K=50 is where the floor becomes usable and K=100 is
where it stops improving much. At 9.3 ms a rollout, K=100 on two options is
**1.9 s per decision** — so use it, and quote the WORST floor rather than the
median when deciding whether a preference is real.

Sensitivity, same board, same K: our agent as the rollout policy scores **18/30
with a margin of +0.80** against a coin-flipper's **5/30 and −0.63**. The oracle
can tell a player from a random policy, which is the least it must do before it
is allowed to grade a decision.
"""

import random
import sys
import time
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cg import api  # noqa: E402
from card_census import zones_of  # noqa: E402

DECK_SIZE = 60


class DeterminizationError(ValueError):
    """The hidden state handed to the engine does not add up to sixty cards."""


# ---------------------------------------------------------------------------
# The raw step: the agent takes dicts, the API returns dataclasses
# ---------------------------------------------------------------------------

def _step_raw(search_id, select):
    """`api.search_step`, but returning the observation as a DICT.

    Our agent takes the raw dict the engine emits; `api.search_step` converts it
    to dataclasses on the way out and the conversion is lossy for our purposes
    (and slow, done a hundred times per rollout). The JSON is right there before
    `json_to_dataclass`, so this keeps it.
    """
    import ctypes
    import json

    arr = (ctypes.c_int * len(select))(*select)
    bs = api.lib.SearchStep(api.agent_ptr, search_id, arr, len(select))
    result = json.loads(bs.decode())
    error = result.get("error", 0)
    if error:
        raise ValueError(f"search_step error {error} on search_id {search_id}")
    return result["state"]


# ---------------------------------------------------------------------------
# D1 · the determinizer
# ---------------------------------------------------------------------------

def _ids_seen(obs, seat):
    """Counter of card ids of `seat` that are VISIBLE in this observation.

    Reuses the census's zone reader, which is where the first version of this
    went wrong: attached energies, tools and pre-evolutions are cards too, and
    leaving them out inflates the deck by exactly as many as are in play.
    """
    seen = Counter()
    players = ((obs.get("current") or {}).get("players") or [None, None])
    me = players[seat] if len(players) > seat else None
    if not me:
        return seen

    def take(card):
        if card and card.get("id") is not None:
            seen[card["id"]] += 1

    for card in (me.get("hand") or []):
        take(card)
    for card in (me.get("discard") or []):
        take(card)
    for card in (me.get("prize") or []):
        take(card)                      # only ALREADY REVEALED prizes are not None
    for key in ("active", "bench"):
        for body in (me.get(key) or []):
            if not body:
                continue
            take(body)
            for card in ((body.get("energyCards") or [])
                         + (body.get("tools") or [])
                         + (body.get("preEvolution") or [])):
                take(card)
    # The stadium is a LIST in the observation, not a card: whoever played it
    # owns the card, and it is one of that seat's sixty.
    stadium = (obs.get("current") or {}).get("stadium")
    for card in (stadium if isinstance(stadium, list) else [stadium]):
        if card and card.get("playerIndex") == seat:
            take(card)

    # THE CARDS IN FLIGHT, and they are the reason this used to come up two
    # short. A card being looked at (`current.looking`) or the card whose effect
    # is resolving right now (`select.effect`) is in NO zone: it has left the
    # hand and has not reached the discard. `ptcg/state/tracking.py` documents
    # the same hole from the other side -- an unaccounted copy there gets filed
    # as a PRIZE. Here it simply went missing, and `determinize` refused to
    # close, which is the guard doing its job: 3 of 15 boards on a self-play
    # workload, every one of them mid-effect.
    looking = (obs.get("current") or {}).get("looking")
    for card in (looking if isinstance(looking, list) else [looking]):
        if card and card.get("playerIndex") == seat:
            take(card)
    effect = (obs.get("select") or {}).get("effect")
    for card in (effect if isinstance(effect, list) else [effect]):
        if card and card.get("playerIndex") == seat:
            take(card)
    return seen


def determinize(obs, opponent_obs, our_deck, their_deck, rng=None):
    """The hidden state to hand `search_begin`, closing on sixty per seat.

    `opponent_obs` is the opponent's own most recent observation, which is the
    only place their hand is legible. Everything still hidden after that -- both
    prize sets and both deck remainders -- is SAMPLED from what is left, because
    (see the module docstring) prizes are face down even to their owner.

    **`opponent_obs=None` is legitimate and is the common case.** The frozen
    corpus and every recorded episode keep ONE seat's observations, so there is
    no opponent view to read: their hand is then sampled from their unseen
    multiset like everything else. The result is a fully legal world rather than
    a partly true one, and `diag["hand_sampled"]` says which of the two a run
    was, because a grade computed against a guessed hand is a weaker claim than
    one computed against the real one and the report has to be able to tell.
    """
    rng = rng or random.Random()
    state = obs["current"]
    us = state["yourIndex"]
    them = 1 - us

    out = {}
    for seat, deck_list, source in ((us, our_deck, obs), (them, their_deck, opponent_obs)):
        # ALWAYS the CURRENT observation, for both seats. The opponent's board --
        # active, bench, discard, stadium -- is PUBLIC and is right here; the
        # only thing their own view adds is the hand. Reading their whole side
        # from THEIR last observation instead mixes a stale board with current
        # counts, and `determinize` then refuses to close: 3 of 15 boards on a
        # self-play workload, first two cards short and then two cards over.
        seen = _ids_seen(obs, seat)
        hand = []
        hand_sampled = False
        n_hand = int(state["players"][them].get("handCount") or 0) if seat == them else 0
        if seat == them and opponent_obs is not None:
            src = opponent_obs["current"]
            leido = [c["id"] for c in (src["players"][them].get("hand") or [])
                     if c and c.get("id") is not None]
            # ⚠️ THE OPPONENT'S VIEW IS THE LAST ONE THEY WERE HANDED, NOT THIS
            # INSTANT. Between their turn and this decision they draw, and the
            # hand read from that stale observation is then SHORTER than the
            # `handCount` this observation reports. Mixing the two is what made
            # `determinize` come up two cards short on 3 of 15 boards -- the
            # guard caught it, which is the whole reason the guard exists. If
            # the two do not agree, the view is stale and the hand is sampled
            # like everything else rather than half-believed.
            # And it is ADDITIVE, not a correction. `seen` now comes from the
            # current observation, which does not show their hand at all, so
            # subtracting the read hand from it -- as this did while `seen` came
            # from THEIR view, where the hand IS included -- deletes board cards
            # that merely share an id with something they are holding. That is
            # what turned "two cards short" into "four cards short".
            if len(leido) == n_hand:
                hand = leido
        rest = list((Counter(deck_list) - seen).elements())
        if seat == them:
            rest = list((Counter(rest) - Counter(hand)).elements())
        rng.shuffle(rest)
        if seat == them and not hand and n_hand:
            # No opponent view: their hand is drawn from what is left, exactly
            # like their prizes. It is a legal world, not the true one.
            hand, rest = rest[:n_hand], rest[n_hand:]
            hand_sampled = True
        n_prize = len(state["players"][seat].get("prize") or [])
        n_deck = int(state["players"][seat].get("deckCount") or 0)
        prize = rest[:n_prize]
        deck = rest[n_prize:n_prize + n_deck]
        total = sum(seen.values()) + len(hand) + len(prize) + len(deck)
        if total != DECK_SIZE:
            raise DeterminizationError(
                f"seat {seat}: {sum(seen.values())} seen + {len(hand)} hand + "
                f"{len(prize)} prize + {len(deck)} deck = {total}, not {DECK_SIZE}. "
                f"The engine would accept this and play a different game.")
        if len(deck) != n_deck:
            raise DeterminizationError(
                f"seat {seat}: {len(deck)} cards left for a deck of {n_deck}")
        out[seat] = {"deck": deck, "prize": prize, "hand": hand,
                     "hand_sampled": hand_sampled}

    their_active = (state["players"][them].get("active") or [])
    op_active = []
    if their_active and their_active[0] is None:
        src = (opponent_obs or obs)["current"]["players"][them].get("active") or []
        op_active = [c["id"] for c in src if c and c.get("id") is not None][:1]

    return {
        "your_deck": out[us]["deck"],
        "your_prize": out[us]["prize"],
        "opponent_deck": out[them]["deck"],
        "opponent_prize": out[them]["prize"],
        "opponent_hand": out[them]["hand"],
        "opponent_active": op_active,
        "diag": {"seat": us,
                 "prizes_sampled": len(out[us]["prize"]) + len(out[them]["prize"]),
                 "hand_sampled": out[them]["hand_sampled"]},
    }


# ---------------------------------------------------------------------------
# D0 · the rollout
# ---------------------------------------------------------------------------

def _choose(obs, rng, policy, agent):
    """One selection under `policy`, honouring minCount/maxCount.

    The arity is not decoration: the engine rejects a one-element choice on a
    select that asks for two (error 4), and a rollout that dies there reports
    the policy's bug as the option's result.
    """
    sel = obs.get("select") or {}
    options = sel.get("option") or []
    if not options:
        return None
    if policy == "agent" and agent is not None:
        try:
            return list(agent(obs))
        except Exception:                       # noqa: BLE001 - the fallback IS the point
            pass
    n = len(options)
    lo = max(1, int(sel.get("minCount") or 1))
    hi = min(n, int(sel.get("maxCount") or 1))
    k = lo if lo >= hi else rng.randint(lo, hi)
    return rng.sample(range(n), k)


def rollout(obs, opponent_obs, our_deck, their_deck, forced_choice,
            seed=None, policy="random", agent=None, max_steps=600):
    """Force `forced_choice` at this decision, then play to the end.

    Returns {won, result, steps, prizes_left, determinization}. `won` is from the
    point of view of the seat that is deciding in `obs`.
    """
    rng = random.Random(seed)
    det = determinize(obs, opponent_obs, our_deck, their_deck, rng=rng)
    us = obs["current"]["yourIndex"]

    root = api.search_begin(api.to_observation_class(obs),
                            det["your_deck"], det["your_prize"],
                            det["opponent_deck"], det["opponent_prize"],
                            det["opponent_hand"], det["opponent_active"])
    state = _step_raw(root.searchId, list(forced_choice))
    steps = 1
    while steps < max_steps:
        ob = state["observation"]
        cur = ob.get("current") or {}
        if cur.get("result", -1) != -1:
            break
        choice = _choose(ob, rng, policy, agent)
        if choice is None:
            break
        state = _step_raw(state["searchId"], choice)
        steps += 1

    cur = (state["observation"].get("current") or {})
    result = cur.get("result", -1)
    players = cur.get("players") or []
    prizes = [len(p.get("prize") or []) for p in players] if players else []
    return {"won": result == us, "result": result, "steps": steps,
            "prizes_left": prizes, "determinization": det["diag"]}


def measure_cost(obs, opponent_obs, our_deck, their_deck, forced_choice,
                 k=10, policy="random", agent=None):
    """Seconds and steps per rollout, which is what sets K everywhere else."""
    t0 = time.perf_counter()
    steps = 0
    for i in range(k):
        r = rollout(obs, opponent_obs, our_deck, their_deck, forced_choice,
                    seed=1000 + i, policy=policy, agent=agent)
        steps += r["steps"]
    dt = time.perf_counter() - t0
    return {"rollouts": k, "seconds": dt, "s_per_rollout": dt / k,
            "steps": steps, "ms_per_step": 1000 * dt / max(1, steps)}


def score_option(obs, opponent_obs, our_deck, their_deck, choice, k=20,
                 policy="random", agent=None, seed0=0):
    """K rollouts of one option: (wins, k, mean prizes left to the opponent).

    The prize count is carried next to the winrate for the same reason the
    matchup matrix carries it: against a saturated opponent the win flag
    saturates too, and the margin is what still has resolution.
    """
    wins, margin = 0, []
    for i in range(k):
        r = rollout(obs, opponent_obs, our_deck, their_deck, choice,
                    seed=seed0 + i, policy=policy, agent=agent)
        wins += 1 if r["won"] else 0
        pl = r["prizes_left"]
        if len(pl) == 2:
            us = obs["current"]["yourIndex"]
            margin.append(pl[1 - us] - pl[us])
    return {"wins": wins, "k": k,
            "margin": (sum(margin) / len(margin)) if margin else None}


# ---------------------------------------------------------------------------
# Both halves. An instrument that cannot prove it works does not print.
# ---------------------------------------------------------------------------

def _a_board(deck_us, deck_them, lib, stop_at=40, seed=7, rng_seed=11):
    """Plays a seeded game a little way in and hands back both seats' views."""
    from cg.battle import Battle

    rng = random.Random(rng_seed)
    battle = Battle(deck_us, deck_them, seed=seed, lib=lib)
    last, steps = {}, 0
    while battle.result == -1 and steps < stop_at:
        obs = battle.obs
        last[obs["current"]["yourIndex"]] = obs
        choice = _choose(obs, rng, "random", None)
        if choice is None:
            break
        battle.select(choice)
        steps += 1
    obs = battle.obs
    us = obs["current"]["yourIndex"]
    return battle, obs, last.get(1 - us)


def self_test(deck_us=None, deck_them=None, k=20, verbose=True):
    """The two halves, and the first one had to be rewritten against the plan.

    ⚠️ **THE SEARCH API IS NOT REPRODUCIBLE, AND THE PLAN ASSUMED IT WAS.**
    `docs/night-plan-2026-08-13.md` made it the mandatory specificity half:
    *"two rollouts of the same choice with the same seed must return the same
    result -- if they do not, the oracle is measuring its own noise"*. Measured
    here: they do not. Same seed, same forced choice, same determinization →
    140 steps against 122. `search_begin` takes no seed, so the shuffles inside
    the rollout are the engine's own; our seed reaches the determinization and
    the policy and stops there.

    That does not sink the instrument -- it makes it an ESTIMATOR rather than a
    replay. So specificity is what can actually be asserted:

      a) the same seed yields the same DETERMINIZATION, which is the part we
         control, and it closes on sixty per seat;
      b) the NOISE FLOOR is measured rather than assumed: two independent
         batches of K rollouts of the SAME option. Whatever gap they show is the
         floor, and no preference below it may ever be reported.

    SENSITIVITY plants the defect in the POLICY, not in the option: our agent
    against a coin-flipper, same option, same K. An oracle that cannot tell a
    player from a random policy cannot grade a decision, and unlike two
    different options this comparison has a known direction.
    """
    import local_engine
    import selfplay as sp

    lib = local_engine.load()
    deck_us = deck_us or sp.read_deck(str(_ROOT / "deck.csv"))
    deck_them = deck_them or sp.read_deck(
        str(_ROOT / "deck" / "real_opponents_500" / "crustle_wall_1.csv"))

    battle, obs, other = _a_board(deck_us, deck_them, lib)
    try:
        us = obs["current"]["yourIndex"]
        decks = {0: deck_us, 1: deck_them}
        ours, theirs = decks[us], decks[1 - us]
        options = (obs.get("select") or {}).get("option") or []
        if len(options) < 2:
            raise RuntimeError("this board offers no choice to grade")

        # -- specificity (a): what our seed does control ------------------
        d1 = determinize(obs, other, ours, theirs, rng=random.Random(99))
        d2 = determinize(obs, other, ours, theirs, rng=random.Random(99))
        misma_det = all(d1[key] == d2[key] for key in
                        ("your_deck", "your_prize", "opponent_deck",
                         "opponent_prize", "opponent_hand"))
        if verbose:
            print(f"  ESPECIFICIDAD a) misma semilla -> "
                  f"{'MISMA' if misma_det else 'DISTINTA'} determinizacion, "
                  f"y cierra en 60 por asiento")

        # -- specificity (b): the noise floor, measured ------------------
        lote1 = score_option(obs, other, ours, theirs, [0], k=k, seed0=0)
        lote2 = score_option(obs, other, ours, theirs, [0], k=k, seed0=10_000)
        suelo_wr = abs(lote1["wins"] - lote2["wins"]) / k
        suelo_margen = abs((lote1["margin"] or 0) - (lote2["margin"] or 0))
        if verbose:
            print(f"  ESPECIFICIDAD b) SUELO DE RUIDO con K={k}: "
                  f"{lote1['wins']}/{k} vs {lote2['wins']}/{k} "
                  f"({100 * suelo_wr:.0f} pp) · margen "
                  f"{lote1['margin']:+.2f} vs {lote2['margin']:+.2f} "
                  f"({suelo_margen:.2f})")

        # -- sensitivity: a player against a coin-flipper ----------------
        import main as agente_mod

        con_agente = score_option(obs, other, ours, theirs, [0], k=k,
                                  policy="agent", agent=agente_mod.agent, seed0=0)
        al_azar = lote1
        gana_mas = (con_agente["wins"] > al_azar["wins"]
                    or (con_agente["margin"] or 0) > (al_azar["margin"] or 0))
        separa = gana_mas and (
            abs(con_agente["wins"] - al_azar["wins"]) / k > suelo_wr
            or abs((con_agente["margin"] or 0) - (al_azar["margin"] or 0)) > suelo_margen)
        if verbose:
            print(f"  SENSIBILIDAD: el AGENTE {con_agente['wins']}/{k} "
                  f"(margen {con_agente['margin']:+.2f}) contra el AZAR "
                  f"{al_azar['wins']}/{k} (margen {al_azar['margin']:+.2f})"
                  f" -> {'SEPARA por encima del suelo' if separa else 'NO SEPARA'}")

        ok = misma_det and separa
        if verbose:
            print(f"  AUTO-TEST {'OK' if ok else 'FALLIDO'}")
        return ok
    finally:
        api.search_end()
        battle.finish()


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true",
                    help="run both halves and report whether they hold")
    ap.add_argument("--cost", type=int, default=0, metavar="K",
                    help="measure the cost of K rollouts")
    ap.add_argument("--k", type=int, default=20, help="rollouts per option")
    args = ap.parse_args(argv)

    if args.self_test:
        print("AUTO-TEST del oraculo de busqueda (las dos mitades) ...")
        return 0 if self_test(k=args.k) else 1

    if args.cost:
        import local_engine
        import selfplay as sp

        lib = local_engine.load()
        deck_us = sp.read_deck(str(_ROOT / "deck.csv"))
        deck_them = sp.read_deck(
            str(_ROOT / "deck" / "real_opponents_500" / "crustle_wall_1.csv"))
        battle, obs, other = _a_board(deck_us, deck_them, lib)
        try:
            us = obs["current"]["yourIndex"]
            decks = {0: deck_us, 1: deck_them}
            c = measure_cost(obs, other, decks[us], decks[1 - us], [0], k=args.cost)
            print(f"{c['rollouts']} rollouts: {1000 * c['s_per_rollout']:.1f} ms cada uno, "
                  f"{c['ms_per_step']:.2f} ms/paso, "
                  f"{c['steps'] / c['rollouts']:.0f} pasos de media")
        finally:
            api.search_end()
            battle.finish()
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
