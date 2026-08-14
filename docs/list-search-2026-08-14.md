# Searching the list — results, 14 August 2026

[← Documentation index](README.md) · [the plan this executes](day-plan-2026-08-14.md) · [the night that built the harness](history/night-2026-08-14.md)

**Status: finished. Eleven variants, zero recommended swaps, one finding.** Every variant is measured paired against the current sixty
(`log/noche-2026-08-14/L-A2.txt`) over the same 133 lists with the same 400
seeds, 53 181 games per arm. Raw runs in `log/dia-2026-08-14/`.

**The criterion, fixed before anything ran:** recommend only if the weighted
**prize delta is positive** *and* the **winrate delta's 95 % interval excludes
zero**. Nothing is merged into `deck.csv`.

---

## The table

| # | swap | prizes | winrate | verdict |
|---|---|---:|---|---|
| V1 | −1 Xerosic → +1 Grass (15) | **+0.025** | −0.08 pp [−0.33, +0.17] | not recommended — interval includes zero |
| V2 | −1 Boss's → +1 Grass (15) | **+0.067** | +0.05 pp [−0.20, +0.29] | not recommended — interval includes zero |
| V3 | −1 Dawn → +1 Poké Pad (3) | +0.037 | **−0.37 pp [−0.62, −0.11]** | not recommended — worse, and significantly |
| V4 | −1 Dawn → +1 Tapu Bulu (2) | **−0.079** | **−0.69 pp [−0.95, −0.44]** | not recommended — worse on both axes |

**Nothing in wave 1 passes.** That is the headline and it is worth saying
plainly: four swaps chosen from the strongest evidence available — the card
census's worst converters and a recorded finding about how the hard matchups
lose — and none of them beats the sixty cards already on the ladder.

---

## What the failures say, which is more than the pass/fail

### The second Tapu Bulu is a matchup card, not a list card (V4)

This is the direct test S1 asked for, and the aggregate verdict (−0.69 pp)
hides the interesting half:

| archetype | weight | winrate | prizes |
|---|---:|---|---|
| **Crustle Wall** | 8.2 % | **+1.92 pp** | −0.024 |
| Ogerpon Verde | 6.2 % | +1.29 pp | +0.157 |
| Marnie Grimmsnarl | **37.4 %** | −1.48 pp | −0.118 |
| Alakazam | **17.8 %** | −1.29 pp | −0.179 |

The second copy **does** buy the wall matchup, exactly as the Night Stretcher
whitelist assumes when it reaches for a Tapu Bulu against Cornerstone. It pays
for it in Marnie and Alakazam, which are **55 % of the field between them**. So
the right sentence is not "it does not earn its slot" but *it earns it against
8 % of the meta and is taxed by 55 %* — and the list that dropped to one copy
was reading the field correctly.

### Cutting Dawn helps against Ogerpon Verde and hurts everywhere else

V3 and V4 differ in what they add and agree in what they cut, and both move
**Ogerpon Verde up** (+1.61 and +1.29) while both move Alakazam down (−0.91,
−1.29). The card that converts at 31.4 % is load-bearing in the matchups that
are 55 % of the meta — which is the card census's own warning, in numbers: **a
low conversion is not a bad card**, and the census says so in its own §5.

### The two Grass variants agree in direction and disagree with the winrate

V1 and V2 both trade a piece of tech for fuel, and both come out **prize-positive
with a flat winrate** (+0.025 and +0.067 against −0.08 and +0.05 pp). V2's
+0.067 prizes is nearly the whole four-card swap's +0.077 — on one card.

That split is a real object and not noise in one direction: the prize
differential is the axis with resolution (18 of 22 archetypes sit above 92 %
winrate), so a change that moves prizes without moving games won is a change
that wins *harder* without winning *more often*. Wave 2 asks whether the axis
continues and whether it is the cut or the addition doing the work.

---

## Wave 2 — one variant passes the gate, and then fails a check the gate does not make

Chosen by wave 1: **V5** (−1 Xerosic −1 Boss's → +2 Grass) asks whether the fuel
axis continues; **V6** (−1 Grass → +1 Dawn) asks whether the load-bearing Dawn
wants a second copy; **V7** (−1 Boss's → +1 Poké Pad) separates *cutting Boss's is
good* from *adding Grass is good*.

| # | swap | prizes | winrate | verdict |
|---|---|---:|---|---|
| **V5** | −1 Xerosic −1 Boss's → +2 Grass (16) | **+0.086** | **+0.52 pp [+0.28, +0.76]** | **passes the criterion** — and see below |
| V6 | −1 Grass → +1 Dawn (2) | −0.029 | −0.36 pp [−0.61, −0.11] | not recommended — worse, significantly |
| V7 | −1 Boss's → +1 Poké Pad (3) | +0.064 | −0.02 pp [−0.26, +0.23] | not recommended — interval includes zero |

**V5 is superadditive and that is the clue.** Its two halves measured alone are
V1 (−0.08 pp) and V2 (+0.05 pp); together they are **+0.52 pp**, far more than
their sum. Two cuts that each do nothing cannot add up to the largest delta of
the day — so what is doing the work is most likely **the sixteenth Grass**, not
the cards that left to make room for it. Wave 3 tests exactly that.

**V6 settles Dawn.** Cutting it hurts (V3, V4) and adding a second copy also
hurts (−0.36 pp). One copy is right, and the card that converts at 31.4 % is not
a candidate for anything.

**V7 isolates V2.** Cutting a Boss's Orders for a Poké Pad gives +0.064 prizes
and −0.02 pp; cutting it for a Grass gave +0.067 and +0.05. The two are the same
number, so **the gain belongs to the cut, not to the replacement** — Boss's
Orders is the card carrying it either way.

### ⚠️ Why V5 is NOT recommended despite passing

The criterion is a gate on the *simulation*, and the project has a recorded rule
about which cards the simulation may not judge
([[el-bot-generico-tasa-como-muertas-las-cartas-de-remontada]]). So V5's two cuts
were checked against the real ladder, like for like (the same 22 cards, the old
list, `card_census --compare`):

| card | simulated | real ladder | |
|---|---:|---:|---|
| **Xerosic's Machinations** | 19.6 % | **36.9 %** | **+17.3** — the third-largest gap in the list |
| **Boss's Orders** | 31.1 % | 24.8 % | −6.3 — the simulation *over*rates it |

**The two halves of V5 are not the same kind of decision.** Xerosic converts
nearly twice as well against real opponents as against the bot, which puts it in
the same family as Unfair Stamp (+48.6) and Fezandipiti ex (+34.7) — the cards
that only work from behind, and against a bot we beat 95 % of the time there is
no behind. Its measured gain is precisely the artefact the recorded rule exists
to stop. Cutting Boss's Orders, by contrast, rests on solid ground: the real
ladder converts it *lower* than the simulation does.

**So V5 is measured, reported, and not recommended.** What survives it is a
hypothesis rather than a swap: *the sixteenth Grass, bought with cards the
instrument prices honestly.*

---

## Wave 3 — it is the fuel, and the axis has a top

Each variant reaches 16 or 17 Grass **while keeping both Xerosic**, so nothing in
them is priced by an instrument known to misprice it. Named in advance: cutting
Boss's Orders entirely removes a capability and not just a card, and wave 4
counts what that costs.

| # | swap | Grass | prizes | winrate | verdict |
|---|---|---:|---:|---|---|
| **V8** | −2 Boss's → +2 Grass | 16 | **+0.086** | **+0.30 pp [+0.05, +0.54]** | **passes**, and touches nothing mispriced |
| V9 | −1 Boss's −1 Poké Pad → +2 Grass | 16 | +0.055 | −0.10 pp [−0.35, +0.15] | not recommended — the Poké Pad pays for itself |
| V10 | −2 Boss's −1 Poké Pad → +3 Grass | 17 | +0.088 | +0.05 pp [−0.19, +0.30] | not recommended — **the axis turns here** |

**The question wave 3 was built to answer is answered: it is the fuel.** V8
keeps both Xerosic and still delivers **the same +0.086 prizes as V5**, so the
prize gain never belonged to the Xerosic cut at all.

**And the difference between them is exactly the mispriced part.** V5 = +0.52 pp,
V8 = +0.30 pp; the extra 0.22 pp is what cutting Xerosic adds *against a bot we
are never behind against*. The honest half of V5 is V8.

**Sixteen is the top, and seventeen is past it.** V10 reaches the same prize
differential (+0.088) with the winrate gain gone (+0.05 pp, interval spanning
zero). More fuel stops converting into games won somewhere between the sixteenth
and seventeenth Grass. V9 says the same thing from the other side: reach sixteen
by spending a Poké Pad instead of a Boss's and the gain disappears — the second
Poké Pad is load-bearing, exactly as the census said when it converted at 68.3 %,
identically to the first.

### Where V8's gain lands

| archetype | weight | winrate | prizes |
|---|---:|---|---|
| **Ogerpon Verde** | 6.2 % | **+3.03 pp** | +0.258 |
| **Crustle Wall** | 8.2 % | +1.09 pp | +0.186 |
| Mega Lopunny / Mega Froslass | 7.2 % | +0.88 pp | +0.098 |
| Alakazam | 17.8 % | −0.42 pp | **+0.152** |

It goes where the recorded diagnosis said it would: **the two hard matchups lose
by starvation, not by misplay** — and the two hardest are the two that gain most
from fuel. It also repairs the one regression the night left open, Mega Lopunny /
Mega Froslass, and even Alakazam — the only archetype whose winrate dips — takes
**more prizes**, which is the axis with resolution.

### ⚠️ The risk V8 carries, named before it was measured and still unpriced

**V8 removes Boss's Orders from the list entirely.** That is a capability, not a
card: several rule families are written around gusting a benched body to close a
game, and with no copies they become unreachable. Two things make this hard to
price here and both belong in the report rather than in a footnote:

* the reference bot is **saturated** — we win 95 % — so cards that decide *close*
  games are systematically under-rewarded, and reach is the definition of a
  close-game card;
* the one real-ladder measurement available says the opposite of the Xerosic
  case (Boss's converts **lower** in real games, 24.8 % against 31.1 %), which is
  evidence *for* the cut, but conversion measures whether a card was played and
  not whether it decided the game.

So V8 is reported as **the strongest candidate the day found, with one named risk
the instrument cannot price.** V11 below asks whether the same fuel is reachable
while keeping a gust.

---

## Wave 4 — the capability, counted

**V11** (−1 Boss's −1 Bug Catching Set → +2 Grass; sixteen Grass, one Boss's
kept): **+0.090 prizes**, the best of the day, and **+0.19 pp [−0.06, +0.43]** —
the interval spans zero, so by the written criterion it is **not recommended**.

### What V8 actually costs: 52 named rules

`rule_census.py` on each tree, self-play only over three of the heaviest lists
(Marnie, Crustle Wall, Alakazam), both halves of the self-test passing. The
first attempt at this included `--corpus`, which replays records under **their
own** list — identical in both arms — so its diff was contaminated; this one
varies the whole workload.

| band | current list | V8 | new |
|---|---:|---:|---|
| **chain never resolved** | 11 | **56** | **45, every one of them Boss's / gust** |
| evaluated, never fires | 69 | 67 | 17 new, 7 of them Boss's-dependent |

**Zero rules revive** in the chain band, so this is signal and not sample noise.
Removing Boss's Orders makes **52 of the project's 393 named rules unreachable** —
one in eight — and the names are the closing tools themselves:
`gust_wins_the_game`, `winning_gust`, `win_via_bench`, `gust_for_2_prizes`,
`finish_the_immune_wall_before_gusting`, the whole of `_ADJUST_GUST_OFFENSIVE`
and `_RULES_GUST_NUISANCE`, and seven more in other modules that ask about a
Boss's they will never have.

---

## The day's verdict

### One finding, and it is not a swap

**The sixteenth Grass is worth about +0.09 prizes per game, and the result is
robust across four independent routes to it.** Every variant that added Grass
came out prize-positive, and the amount tracks the count:

| Grass | routes measured | prize delta |
|---:|---|---|
| 15 | V1, V2 | +0.025, +0.067 |
| **16** | V5, V8, V9, V11 | +0.086, +0.086, +0.055, **+0.090** |
| 17 | V10 | +0.088 — and the winrate gain is gone |

**Which card pays for it is not resolved by this instrument.** The winrate
significance is the fragile half: two of seven routes clear it, and V8 (+0.30)
and V11 (+0.19) differ by less than their own error. That choice belongs to the
deck's owner, and the evidence for each payment is in the table above.

### Zero recommended swaps, and why the one that passed is not among them

**V8 passes the criterion and is still not recommended.** The criterion is a gate
on simulated games, and this project's discipline is that a gate is necessary and
not sufficient — the same reason V5 was withheld. Two independent measurements
say V8 is priced by an instrument that cannot see what it costs:

* it deletes **52 named rules**, one in eight, and they are the game-closing
  ones;
* the reference bot is **saturated** — we win 95 % — so reach and closing tools
  are exercised in a vanishing fraction of games. A change that deletes them and
  measures +0.30 pp is telling us about the bot's bench discipline at least as
  much as about our list.

**V11 is the honest candidate**: the best prize delta of the day, sixteen Grass,
and not one rule lost. It fails the winrate half of the criterion, so it is
reported as *measured, not recommended*, and it is the one a human should look at
first.

### What the day says about the method

Two of the four things that would have been adopted on a naive reading — V5 and
V8 — were stopped by checks the winrate gate does not make: the real-ladder
conversion cross, and the rule census. **The gate found candidates; the recorded
disciplines decided.** That is the day's most reusable result.

---

## What is still open

| # | what | why |
|---|---|---|
| 1 | **Which card pays for the sixteenth Grass** | The prize gain is robust, the winrate significance is not. Needs either real-ladder games or an instrument that is not saturated |
| 2 | **Nothing here is measured against a non-saturated opponent** | Every caveat above has the same root, and it is the argument the night already made for **phase D — a grader against the rules** |
| 3 | The mirror-class and top-100 weightings | Every number here is field-weighted; the top-100 reorders the leak ranking and was not recomputed for these variants |

---

Next: [the day's plan](day-plan-2026-08-14.md) · [the night](history/night-2026-08-14.md) · [the card census](card-census-2026-08-13.md) · [the playbook](playbook-vs-meta-2026-08-13.md)
