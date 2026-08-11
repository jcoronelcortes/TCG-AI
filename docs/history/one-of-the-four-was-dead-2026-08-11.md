# Four named rules accused of being dead. One of them was.

[← Documentation index](../README.md) · Queue item 6 of
[the night of 11 Aug 2026](night-2026-08-11.md)

**Outcome: one rule deleted with a proof, three kept with the reason written into
the code.** The queue's own caveat was the right one — those four were
"verified by evaluation, not by reading" — and reading them shows that a zero
from the census is a statement about the workload at least as often as about the
rule.

---

## The census, re-run on the current tree

`python utils/rule_census.py --corpus --games 400` — 3 580 corpus decisions plus
2 400 self-play games against six decks, both auto-test halves green:

    ultra_ball._RULES_UB_MEOWTH[22] another_supporter_in_deck  chain=3416    eval=0       fired=0
    card._RULES_MEOWTH_FETCH[10] xerosic_alakazam              chain=593322  eval=351197  fired=0
    main._RULES_LILLIE_PLAY[4] supporter_already_played        chain=80566   eval=79924   fired=0
    main._RULES_BOSS_PLAY[0] supporter_already_played          chain=72616   eval=72616   fired=0
    disruption._RULES_XEROSIC_PLAY[0] supporter_already_played chain=69977   eval=69977   fired=0
    main._ESC_NS_RECUPERACION[20] tapu_vs_crustle              chain=11706   eval=11706   fired=0

Six zeros. One deletion.

## The one that was dead — and provably, not by counting

`_ESC_NS_RECUPERACION[20] tapu_vs_crustle`:

```python
_E("tapu_vs_crustle",
   lambda w: (Tapu_Bulu in w.basics
              and w.field_counts.get(Tapu_Bulu, 0) == 0
              and w.op_is_crustle_deck and w.bench_count < 5), 850),
```

and the chain it lives in is chosen like this:

```python
if ctx.op_is_crustle_deck or ctx.op_is_cornerstone_deck:
    best, _ = _resolve_max(_ESC_NS_CRUSTLE, w)
else:
    best, _ = _resolve_max(_ESC_NS_RECUPERACION, w)     # <- this one
```

The list is only ever walked when the opponent is **not** a Crustle deck, and the
rule asks whether the opponent **is** one. `_CtxNSPlay.__getattr__` delegates
straight through to the same `ctx`, so the two readings are the same object:
the contradiction is airtight and needs no workload to establish. Not rare —
**impossible**.

And the loop closes on the other side. Its intent — *recover a Tapu Bulu against
the wall* — was already being served, and better, by the chain that actually runs
there: `_ESC_NS_CRUSTLE[0] basico_whitelist` opens its whitelist with
`Tapu_Bulu` and scores it **900**, above the 850 the dead rule would have given.

Deleted. Suite 2 264 green, corpus unchanged, no flip. *That it changes nothing
is the argument for removing it.*

The census re-run on the same workload closes the proof from the other side:

    before:  392 reglas con nombre, 341 decidieron algo
    after:   391 reglas con nombre, 341 decidieron algo

One rule fewer, **the same 341 still carrying decisions** — the removed one was
not among them, and nothing moved up to take its place.

## The three that are not dead, and why each survives

### `xerosic_alakazam` — 351 197 evaluations, zero fires, and load-bearing

It reads exactly like a rule the one above swallowed, and the arithmetic
encourages that: its predicate is `xerosic_priority_over_boss`'s **minus** that
rule's `not c.win_via_boss`. A chain breaks at the first rule that fires, so this
one is reachable **exactly when `win_via_boss` holds** — the corner the rule
above deliberately steps aside from. The corner is empty in the workload, not in
the game, and its play-side twin says so from the other direction:
`_RULES_XEROSIC_PLAY[4] alakazam_yields_to_winning_gust` is evaluated 38 963
times and fires zero as well.

In that corner it carries weight. `winning_boss` (1300) answers only the Boss's
**candidate**; if the winning Boss's is already in hand it is not a fetch
candidate at all, and this rule is what prices the Xerosic — 1260 against the
development Lillie's at 1250. Delete it and that board falls through to
`xerosic_generico` (1100) and loses to the refill.

### `another_supporter_in_deck` — never even evaluated

Dead by **ordering**: it is the tail of its chain and the rule above it,
`lillie_in_deck > 0`, always fired. With four Lillie's in a sixty-card deck that
is nearly always true. The corner this rule answers is the late game where the
deck has run out of Lillie's and still holds another Supporter. The workload did
not reach it; the game can.

### The three `supporter_already_played` vetoes — redundant with a rule of the game

~222 000 evaluations between them, zero fires. The reason is **not** a wrong
premise — that is the `_protect_last_supporter` failure mode, a guard gated on a
flag that on a forced discard belongs to the opponent. Here the premise is
correct and the **engine** enforces it: one Supporter per turn, and a second one
is never offered to play. The guard is redundant with a rule of the game rather
than with a rule of ours, and it costs one comparison to keep saying so.

## What actually changed

One rule gone; four comments added that turn a recurring "should we delete this?"
into a settled, written answer at the place where the question gets asked. The
next reader of `xerosic_alakazam` does not have to redo the chain arithmetic to
find out it is not dominated.

Suite 2 264 green, linter clean across eight rules, frozen corpus untouched.
