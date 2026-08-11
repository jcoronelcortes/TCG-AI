# A scorer prices an option. It does not write state.

[← Documentation index](../README.md) · Queue item 5 of
[the night of 11 Aug 2026](night-2026-08-11.md)

**Outcome: the latent defect is fixed and the class is closed with a lint rule.
The veto itself is deliberately NOT touched** — the weighted matrix already said
no, and nothing here changes that.

---

## The two halves of queue item 5, and only one of them was work

The item carried a measurement and a bug.

**The measurement, already done and already decided.** Our agent always declines
to go first, and the opponent bot has no rule for that select, so in matchup mode
the bot ends up first *every time* — which means every gate run with
`--opponent` has only ever measured the going-second half. Measured properly with
`OpponentBot(first_choice="second")`, 800 games per deck: **+11 points against
crustle_kangaskhan**, +4.75 against marnie, and roughly zero against the other
four. But asked of the meta that exists (`matchup_matrix.py --weights`, 87 real
lists), the weighted winrate does not move: Crustle is 2 % of the ladder, while
31 % is Marnie and 15 % Alakazam, where we already win 94–98 % and there is no
room. **It is a change FOR hard matchups, to be measured IN hard matchups, not a
ladder winrate play.** That verdict stands, and the veto stays as it is.

**The bug, in the same lines, and this is the deliverable.**

```python
if o.type == YES and context == IS_FIRST:   score = SCORE_VETO
                                            AGENT_STATE.we_go_first = True
if o.type == NO  and context == IS_FIRST:   score = 2
                                            AGENT_STATE.we_go_first = False
```

A scorer is called **once per option**, so the value that survived belonged to
whichever option the simulator happened to price *last*.

## What the measurement said before anything was touched

Sixty openings, driven through the engine:

| | |
| --- | --- |
| `firstPlayer` at the IS_FIRST menu | **-1 in all 60** — the coin has not resolved |
| the order the simulator lists | **(YES, NO) in all 60** |
| the option chosen | NO in all 60 |
| the flag after scoring | False in all 60 — *correct, by accident* |
| `firstPlayer` at our next decision | 1 in all 60 — the engine has decided |
| decisions of OURS in between | **zero** (0 or 1 of the opponent's) |

So it comes out right only because NO is priced last. Flip that order and every
`we_go_first` branch in the tree — `_RULES_FOREST_PLAY[0] t1_going_first`, the
opening attachments — inverts in silence, with nothing going red.

## The fix is a deletion, and the reason it can be

`we_go_first` is a **mirror of the board** — that is the law
[the invariant monitor files it under](every-flag-has-a-law-2026-08-11.md) — and
a mirror has exactly one honest writer: the code that reads the observation.
`agent()` already does it, under the same guard the engine imposes:

```python
if state.firstPlayer >= 0:
    AGENT_STATE.we_go_first = (state.firstPlayer == state.yourIndex)
```

The write in the scorer was trying to **predict** that before the board knew. It
had nothing to add and one way to be wrong, so both lines are gone. Nothing
replaces them: the window they covered contains no decision of ours, and even
inside the same call the scoring context is snapshotted before the loop, so the
write was already invisible to everything downstream.

## R9: closing the class instead of the instance

The shape generalises, so it became a rule rather than a fix. `utils/lint_
architecture.py` **R9**: no module under `ptcg/turn/options/` may assign to
`AGENT_STATE.<field>`. Those modules are called once per option over a list whose
order belongs to the simulator, so anything they write is a function of that
order. A score is not — it is returned, and the caller decides.

`ptcg/turn/finalize.py` writes state freely and is deliberately outside the rule:
it runs *after* the choice, which is exactly the difference. Swept over the whole
tree, the only two violations that ever existed were the two lines above.

## Both halves, on both mechanisms

With the two assignments put back:

* three of the nine tests go red, led by `test_the_flag_does_not_depend_on_the_
  order_either` — the one that prices the menu backwards, which is what the old
  code could not survive;
* the linter names both lines, `minor.py:68` and `minor.py:81`.

And R9 has its own pair: it catches `AGENT_STATE.x = ...` and `AGENT_STATE.x +=
1`, and says nothing about *reading* `AGENT_STATE`, which scorers do constantly
and must go on doing.

Note which test did **not** go red: `test_the_choice_survives_the_menu_being_
listed_backwards`. The choice was never order-dependent; only the belief the
agent kept about it was.

## Closing control

`utils/invariant_monitor.py --games 150` — 18 978 decisions, `FLAG_MIRROR` and
`FLAG_UNSTUCK` both absent from the violations. The instrument built for queue
item 3 signing off on queue item 5: the flag still agrees with the engine
everywhere the engine has an opinion.

Suite 2 273 green, linter clean across **nine** rules now, frozen corpus
untouched — not one of its 3 580 decisions moved.
