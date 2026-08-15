# The refill buys the wave the evolution would delete (step 61)

[← Documentation index](README.md)

One board of a game we **lost** (episode 93378353, vs Festival Lead). The turn
evolved a Dipplin into Hydrapple ex on the bench — a body that could not attack,
could not use its ability and did nothing at all that turn — and in doing so
deleted the one card whose value the *opponent's own stadium* changes.

---

## The board

**Step 61, turn 6** — `records/registro_006_pasos_061_hasta_085.json`

```
US (6 prizes)                            THEM (5 prizes)
active  Teal Mask Ogerpon ex 210, 3 {G}  active  Dipplin 80/80, 1 {G}, Brave Bangle
bench   Fezandipiti ex 210, 0            bench   Thwackey 100, Thwackey 100,
        DIPPLIN 80, 0 energy                     Applin 40 (1 {G}), Applin 40,
        Meowth ex 170, 0                         Grookey 70
hand    Hydrapple ex, LILLIE'S DETERMINATION,
        Lana's Aid, Meganium, Boss's Orders      stadium  FESTIVAL GROUNDS (theirs)
        — not one Basic {G}
```

The menu offered five things; the agent evolved.

```
[2] EVOLVE Hydrapple ex onto the benched Dipplin   33000   <-- played
[4] Fezandipiti ex — Flip the Script               31700
[0] Lana's Aid                                      3730
[1] LILLIE'S DETERMINATION                            -1   `line_pending`
```

**Festival Grounds is shared.** With it on the field our Dipplin's *Festival
Lead* lets it use *Do the Wave* twice — and *Do the Wave* is 20 × our bench,
while every body they own is 100 HP or less. Evolving that Dipplin trades the
only double attack on the table for a 330 HP body that, on the bench at zero
energy with no Grass in hand, can neither attack nor even use *Ripening Charge*
(it takes its Grass from hand). The evolution does **nothing this turn**.

---

## What the turn could have been

```
LILLIE'S DETERMINATION → at exactly SIX prizes it draws EIGHT → bench two of
them → attach a Grass to the Dipplin → retreat the Ogerpon (cost 1, it carries
3) → DO THE WAVE = 20 × 5 = 100 → their Dipplin dies → Festival Lead throws it
AGAIN at whatever they promote → TWO prizes, and a ONE-prize body left in front
```

Not a hypothetical: the recorded game played Lillie's on the *next* action and
those eight cards were four Basic {G}, a Meowth ex, two Ultra Ball and a Bug
Catching Set — and it went on to bench a second Ogerpon ex and a Chikorita. Every
piece of the line was in that draw. And the refill costs nothing the board
already had: a Supporter does not end the turn, so the Ogerpon in front still
attacks for the same prize afterwards. What it does risk is the Hydrapple ex it
shuffles back, which is the trade being made rather than an oversight.

---

## The cause

Two readings already exist to protect that Dipplin, and both ask the board **as
it stands**:

- `_festival_lead_pays_us_now` — our Dipplin can attack *today* and its wave
  knocks their Active out *today*. It needs a Grass in hand to charge the body
  (there is none) and a wave that already reaches (20 × 3 benched = 60 against
  80 HP).
- `_festival_sac_pivot` — the retreat that gives the Dipplin the front spot. It
  needs the same thing before it will commit.

Both shortages are the **hand's**, and the hand was exactly what the turn had not
spent. The Supporter slot was free, the bench had two seats, and the card in it
draws eight.

And the second half of the lock is on the other side: Lillie's Determination
scored **−1** on this very board, vetoed by `line_pending` — *"there is a Stage 2
in hand for a body in play; evolve first and refill later"*. The hand was being
kept for the evolution that deletes the attacker.

---

## The rule

`THE_REFILL_BUYS_THE_WAVE` ([ptcg/cards/ids.py](../ptcg/cards/ids.py)) — the
flag `_festival_refill_buys_the_wave` in [main.py](../main.py) lights when all
of this holds at once:

1. **their stadium is on the field** (`_festival_grounds_in_play` — we do not
   carry Festival Grounds, so on the field it is theirs);
2. **the wave does not reach yet** — where `_festival_lead_pays_us_now` is true
   the older veto is already doing the work and this one stands aside;
3. **a Dipplin of ours can take the front spot this turn** — it is active, or a
   retreat away from it;
4. **the bench has a free seat**, because a wave that cannot grow is not one the
   refill can buy;
5. **at a FULL bench the wave closes two bodies** — 20 × `benchMax` knocks their
   Active out *and* `_festival_second_wave_prizes` claims a prize behind it,
   which it refuses to do the moment one body on their side survives the same
   wave. The full bench is the honest bound: the refill can only buy seats we
   already have;
6. **the turn still holds the refill** — the Supporter slot is free and Lillie's
   Determination is in hand.

Two decisions read that one flag, and it has to be one flag so they cannot
disagree — the same reason `_festival_wave_bench` is a single function:

- [ptcg/turn/options/evolve.py](../ptcg/turn/options/evolve.py) vetoes an
  evolution onto that Dipplin **only while the new body cannot attack today**.
  A Hydrapple ex that reaches Syrup Storm this turn is cashing a prize now and
  outranks a wave that still has to be bought.
- the Lillie's ladder in [main.py](../main.py) gains `the_refill_buys_the_wave`,
  above `line_pending`: the evolution that veto was saving the hand for is the
  one the evolve branch now refuses, so keeping the hand for it keeps the hand
  for nothing.

---

## What it measures

**Golden corpus:** one flip — this step. **Frozen corpus: zero** of 3 580
decisions.

**Census** (`utils/census_the_refill_buys_the_wave.py`, 500 games against the
two Festival Lead lists, 250 against a list that cannot bring the stadium):

| | menus with a retreat | stadium on the field | wave already reaches | **the refill buys it** | …and the menu held the decision |
| --- | --- | --- | --- | --- | --- |
| festival_lead_1 + _5 | 7 669 | 962 | 198 | **9 (0.018/game)** | **9 (0.018/game)** |
| marnie_grimmsnarl (control) | 4 294 | 0 | 0 | **0** | **0** |

Every firing was on a menu that really held one of the two options the flag
moves, and the control is inert by construction rather than by luck.

**Turn yield** (`utils/turn_yield_the_refill_buys_the_wave.py`, 40 determinised
worlds per arm, the agent finishing the turn in both, same seeds; their answers
inside our turn played by the reference bot, because Festival Lead's second wave
only comes *after* they choose a new Active):

| | prizes | energy attached | hand at end | body left in front |
| --- | --- | --- | --- | --- |
| with the reading (Lillie's) | **1.50** | +1.85 | 7.62 | **Dipplin 20 / Hydrapple ex 15 / Ogerpon 5** |
| without it (the recorded evolve) | 1.00 | +2.38 | 6.92 | Hydrapple ex 37 / Ogerpon 3 |

**20 of 40 worlds take more prizes, 0 take fewer** — and half of them end the
turn with a one-prize body in the Active spot instead of a two-prize one.

**Rules oracle** (`utils/oracle_the_refill_buys_the_wave.py`, K=100, per-board
floor from a second batch at different seeds):

| board | with the rule | without | delta | its own floor |
| --- | --- | --- | --- | --- |
| `registro_006` step 61 | **99/100**, margin +3.92 | 96/100, +3.29 | **+3 pp / +0.63** | 2 pp / 0.19 → **clears** |

**1 for, 0 against** — and it is the only board in the fourteen local records
where the two arms disagree at all.

**Winrate** (`utils/gate_the_refill_buys_the_wave.py`, 1000 paired seeds vs
`festival_lead_1`, with its own `--control` row at the same N):

| | candidate | control (the noise floor at the same N) |
| --- | --- | --- |
| wins | 632/1000 = 63.20 % | 632/1000 = 63.20 % |
| delta | **+0.00 pp** (z 0.00, p 1.000) | +0.00 pp |
| prizes | **+0.000** | +0.000 |

**NEUTRAL, and expected to be.** At nine boards in five hundred games this axis
cannot resolve anything, and the wall is the one main.py already names on
`switch_off_festival_lead`: *the generic OpponentBot cannot pilot the Festival
Lead deck*, so most of these games never build the board. The control row at
exactly zero is the provenance proof that the two arms differ in nothing but the
flag.

---

## Status

Carried by the **board** and by the two instruments that do not saturate on it:
the turn yield (1.50 prizes against 1.00, 20/40 worlds better and none worse)
and the oracle (+3 pp over a 2 pp floor). The census says the population is
small and real and lives entirely on the list that brings the stadium; the
winrate is **neutral** and is stated as measured, per
[the policy for neutral changes](improving-the-agent.md).

The switch to flip is `THE_REFILL_BUYS_THE_WAVE` in
[ptcg/cards/ids.py](../ptcg/cards/ids.py); the board is pinned in
[tests/test_the_refill_buys_the_wave.py](../tests/test_the_refill_buys_the_wave.py),
whose last four tests are the half that must not move — no stadium, no refill in
hand, a Supporter slot already spent, a survivor on their bench, a full bench of
ours, and a Hydrapple ex that **can** attack the turn it lands.

---

Related: [The second wave is a reason of its own](festival-the-second-wave-is-a-reason-of-its-own-2026-08-15.md)
· [The Supporter that buys bodies cannot unblock a turn with no energy](festival-lead-the-body-search-cannot-buy-the-energy-2026-08-15.md)
