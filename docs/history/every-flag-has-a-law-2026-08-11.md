# Sixteen flags nobody had written a law for

[← Documentation index](../README.md) · Queue item 3 of
[the night of 11 Aug 2026](night-2026-08-11.md) · siblings:
[the second copy](the-second-copy-2026-08-11.md) ·
[the fuel and the orphan](the-fuel-and-the-orphan-2026-08-11.md)

**Outcome: the monitor's blind spot goes from 16 to 0, and both new checks come
back at zero over 600 games.** No rule of the agent was changed.

---

## The blind spot

`utils/invariant_monitor.py` watched three promises and printed, on every run,
how many boolean flags on `AGENT_STATE` it could **not** watch:

    Promesas con premisa escrita: 3   banderas booleanas SIN premisa: 16

That is the honest thing to print, and it is what made the item actionable. One
of the sixteen was **`we_go_first`** — the flag that the same night turned out
to be assigned from inside a *scorer*
(`ptcg/turn/options/minor.py`, once per option scored, so its value is the last
option's). The monitor could not see it because nobody had written down what the
flag promises.

## The part that was not mechanical

The queue called this "mechanical work with a demonstrated return", and the
writing is — but **the sixteen are not one shape**, and forcing them into one
would have built a detector that fires on correct play. This repository has paid
for that failure five times, most recently
[two hours earlier](the-fuel-and-the-orphan-2026-08-11.md). So they were triaged:

| shape | n | the law | why |
| --- | --- | --- | --- |
| `PROMISES` | 3 | a premise that must still hold | a plan whose reason can die (`_ub_meowth_pending`, …) |
| `MIRRORS` | 7 | **equality with the board** | recomputed every turn from the observation, so a disagreement is a rule reasoning about a board that is not there |
| `STICKY` | 6 | once up, never down **inside one game** | matchup memory is one-way on purpose |
| `SIN_PREMISA` | 3 | exempt, with the reason written | accumulated from the log stream; one observation has nothing to reconcile them against |

**The mirrors are the strong ones**, and for the same reason `DECK_BELIEF` is:
the truth comes from *outside* the agent. Each expectation is rebuilt here from
the raw observation and never by calling the agent's own helper — that would
restate the belief instead of reconciling it. They cover `we_go_first`,
`meganium_in_play`, `forest_in_play`, `full_metal_lab_in_play`,
`_festival_grounds_in_play` and the two prize-denial reads.

**The sticky ones needed the opposite law**, and the code already said why. From
the comment on `op_is_starmie_deck`:

> the deck announces itself with a 70 HP Staryu that threatens nothing, and the
> whole point of the rule that reads this flag is to have acted BEFORE the
> 330 HP body shows up. A matchup forgotten the turn the Staryu retreats to the
> bench is a matchup we would re-learn one KO too late.

A premise that "must still hold" would therefore have reported correct play on
every board where the Crustle went to the bench. What is checkable is the
**fall**, and it is reported once rather than on every remaining decision of the
game — which is how one defect becomes forty thousand lines.

**And three are exempt with a reason.** `_xerosic_played_this_turn`,
`_ko_detected_this_turn` and `ko_last_turn` are accumulated from the LOG stream
inside a turn; a single observation carries nothing to reconcile them against.
Writing "we cannot check this, and here is why" is worth more than leaving them
in an anonymous count: the next reader knows the question was asked.

## Both halves, before the number

The sabotage run had to be built carefully for each new law:

* the mirrors are **inverted**, not forced True — `meganium_in_play = True` on a
  board that has a Meganium is not a lie, and a saboteur that can be right by
  accident proves nothing;
* the sticky flags are **raised and then dropped, alternating by decision**.
  Forcing them False every time would prove nothing (the check only reports a
  fall, so it first has to see the flag up), and flipping would not work either:
  against a mirror deck the matchup flags never go up on their own, so an
  inversion would hold them permanently True.

Specificity matters more than usual for the mirrors, and it has its own gate: a
clean run must be **silent**, and if it is not, the mirror is reconstructed
differently from the belief and *the defect is the monitor's*.

    Auto-test 2/3: 1506 STALE_FLAG, 948 DECK_BELIEF,
                   7405 FLAG_MIRROR y 2928 FLAG_UNSTUCK sobre el sabotaje
    Auto-test 3/3: 874 decisiones limpias, 0 ilegales,
                   0 creencias contra el tablero

## The number

    Partidas: 600   decisiones: 76284
    Banderas con ley escrita: 3 promesas + 7 espejos del tablero + 6 pegajosas,
                              3 exentas con motivo escrito
    Banderas booleanas que nadie ha pensado todavia: 0

    FLAG_MIRROR:  0
    FLAG_UNSTUCK: 0
    STALE_FLAG:   4996   } both `_ub_meowth_pending`, already understood:
    STALE_READ:    753   } its single consumer re-checks both halves itself

**A negative result, and the point of it.** The seven beliefs agree with the
board on all 76 284 decisions. That is worth having on its own, and it also
**scopes the `we_go_first` defect precisely**: the mirror can only speak while
`state.firstPlayer >= 0`, which is the same guard the agent's own assignment
carries — so a wrong value can exist **only inside the IS_FIRST menu**, before
the coin resolves. Everywhere else the flag is now provably right. Queue item 5
inherits a much smaller question than it had this morning.

## What was delivered

`utils/invariant_monitor.py` (three registries, two checks, four auto-test
halves, `FLAG_MIRROR` / `FLAG_UNSTUCK` added to `DEFECT_KINDS` since a hard
finding is worth its observation) and
`tests/test_every_flag_has_a_law.py` (14 tests: the triage pinned flag by flag,
both directions of every mirror, and the four ways a sticky check can be wrong).
Suite 2264 green, linter clean across eight rules.
