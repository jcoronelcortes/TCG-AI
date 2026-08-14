# Tools

[← Documentation index](README.md)

Everything in `utils/` is a command-line tool. None of them are needed to *run*
the agent — they exist to measure it, feed it opponents, debug it and ship it.
Flags and identifiers are in English; a few stored data fields are still Spanish, and the last section says which and why.

Run them from the repository root. This page is the catalogue, one entry per
script. For *which* of them to reach for and in what order —  and for the rule
that decides whether a number they print may be believed — read
[The instruments](instruments.md) first.

```bash
python utils/nightly.py --quick    # every gate and every detector, a few minutes
```

---

## Run everything

### `nightly.py` — the whole pipeline as one script

Every gate and every detector, in the order the dependencies want, with a report
written to `log/nightly_<timestamp>/REPORT.md` and one log per stage.

```bash
python utils/nightly.py --quick                       # a few minutes: is the pipeline still working
python utils/nightly.py --since HEAD~5                # ~1 hour, the default
python utils/nightly.py --full --since origin/main    # hours, matchup matrix included
```

It exists because the pipeline used to be a sequence of commands in one person's
terminal, and **a night nobody else can relaunch is not infrastructure.** A stage
whose self-test fails is marked INVALID and its output is quarantined in the
report rather than summarised. The mutation stage is the only one that writes to
the tree (it restores on exit, on exception and on a kill), which is why nothing
else may read the tree while it runs.

`informe_noche.py` renders the report; the `noche-*.sh` scripts are the
per-session run-books of individual measurement nights, kept for reproducibility
rather than for reuse — each one names the tree it measured.

---

## Play games and measure

### `selfplay.py` — the winrate gate

Plays full games with the local simulator. This is the gate that answers the one
question no unit test can: **does this change win more games?**

```bash
python utils/selfplay.py --games 100                      # mirror: sanity check, expect ~50%
python utils/selfplay.py --games 200 --base HEAD~1        # candidate vs. a previous version
python utils/selfplay.py --games 200 --opponent deck/real_opponents/crustle_wall_2.csv
python utils/selfplay.py --games 200 --opponent ... --base HEAD~1   # matchup delta
python utils/selfplay.py --games 1000 --jobs 6             # every core (default: perf cores)
python utils/selfplay.py --games 200 --base HEAD~1 --seeds 200   # paired: both arms, same games
```

It loads two independent copies of the agent so their internal tracking never
mixes, and alternates seats between games. Output: score, winrate with a 95%
confidence interval, and the split by seat.

**`--jobs` spreads the games over processes.** The engine runs concurrent
battles happily — the old one-at-a-time limit was a Python global, not the
engine — and the agent is ~85 % of wall time and pure Python, so processes are
what help and threads are not. Measured on the 1000-game mirror: 76.2 s at
`--jobs 1`, 15.1 s at 6 (**5.06×**), 11.3 s at 10 (**6.76×**), with the three
winrates agreeing (49.1 / 49.8 / 50.2 %). `--jobs 1` runs in-process and is the
control when a parallel result looks wrong.

**`--seeds` makes the games themselves reproducible**, which is what the
shipped engine cannot do. It needs the local build (`cg/build_local_engine.sh`);
asking for a seed without it is an error rather than an unseeded game reported
as seeded. Both arms replay the *same* games, so a candidate that decides
identically scores identically — see the matrix below for why that matters.

**`--base` compares whole trees, not just `main.py`.** The baseline is exported
with `git archive` and its `ptcg/` package is what that copy of the agent
imports. This matters because most of the agent now lives in the package: while
the baseline was a lone `main.py`, its imports resolved to the working tree and
a change under `ptcg/` came out of both arms identically — the gate reported
neutral no matter what the change did. Two things stay deliberately shared: the
simulator (`cg`, which aborts the interpreter if initialised twice) and
`deck.csv`, so both sides pilot the same sixty cards.

### `parallel.py` and `local_engine.py` — what makes the two above fast and repeatable

Neither is run directly; both are the machinery `selfplay.py` and
`matchup_matrix.py` sit on, and knowing they exist explains most of the flags
above.

| Module | What it provides |
| --- | --- |
| `parallel.py` | The process pool behind `--jobs`. Processes rather than threads because the agent is ~85% of wall time and pure Python, so the GIL binds and threads buy nothing; the engine itself is happy to run concurrent battles once the pointer stops being a Python global (`cg/battle.py`). One pool serves a whole matrix, not one per deck. |
| `local_engine.py` | Loads the **locally built** engine, the one that honours a seed. The shipped `cg/libcg.*` sets `deviceRand = true`, so every shuffle and both coin paths draw from a fresh `std::random_device` and the seed is ignored — which is why `--seeds` needs the local build and errors without it. |

`local_engine.py` is **for tools only**, and that boundary is enforced rather
than trusted: rule **R11** of the architecture lint fails the build if anything
under `main.py` or `ptcg/` reaches for it. What we submit runs on the official
binaries, and the local one is git-ignored and simply absent on Kaggle. It also
carries a **drift guard** — it compares the card-data hash on every load, so a
local build that quietly diverged from the official engine cannot silently
invalidate every measurement taken with it.

### `matchup_matrix.py` — the matchup matrix

Plays N games against **every** opponent deck in a folder and prints the table
from weakest matchup to strongest, with confidence intervals and forfeits.

```bash
python utils/matchup_matrix.py --games 400 --weights
python utils/matchup_matrix.py --games 200 --base <git-ref>   # per-matchup delta
python utils/matchup_matrix.py --games 400 --weights --allocation peso   # spend by meta share
python utils/matchup_matrix.py --games 200 --base <ref> --seeds 200      # paired, noise floor 0
```

**`--seeds` is what makes a small delta readable.** Without it the per-matchup
noise reaches ±6.5 points at 200 games, which is why `--games` had to rise to
400 and why `--control-card` exists. With it, both arms replay the same games,
so a matchup the change cannot affect reports a delta of *exactly* zero.
Verified 12 August 2026 over the whole corpus: candidate against `HEAD` with a
clean `main.py` and `ptcg/`, **87 of 87 matchups at delta 0.0000**, in winrate
and in prize differential alike. The limit is honest and worth knowing: once the
two arms genuinely decide differently the RNG streams diverge and variance
returns *for that matchup* — what becomes free is every matchup the change does
not touch, which is most of them.

**`--allocation peso` fixes where the budget goes.** The corpus has 88 lists
but they are not equally common: 66 appear once each (0.33 % of the meta) while
the top three are 53.7 % between them, so the uniform default spends 75 % of
the compute on 22 % of the meta. `peso` keeps the same total and redistributes
it by meta share, with a floor (`--games // 4`) so the tail keeps enough games
to catch a change that breaks it outright. The summary now prints a 95 %
interval on the weighted winrate, which is the number the schedule is
optimising and the only way to judge one split against another.

By default it measures against the real leaderboard lists in
`deck/real_opponents/`. `--weights` weights each list by how often it actually
appears, which turns the average into an expected ladder winrate. The synthetic
decks in `deck/opponents/` are still there but are no longer the default: many of
them are archetypes that do not exist in the current meta, and measuring against
them spent half the budget on imaginary opponents. They remain useful for
exercising **mechanics** the real meta does not offer (item lock, mill).

**⚠️ It cannot A/B two LISTS, and the obvious way to make it do so is wrong.**
`main.py:165` reads `deck.csv` from the process's working directory at import,
and the agent derives its whole deck belief from there. Handing the engine a
different list through `selfplay.torneo(deck_candidate=…)` changes what is
*dealt* and not what the agent *believes*, so the arm plays one deck while
thinking it holds another — the same mismatch that made seven tests go red on
14 August, where the belief placed eight cards in six prizes. `checkout_tree`
says so in its own docstring: it deliberately does not take the deck from the
ref, which is what makes `--base` a code comparison. **A `--our-deck` flag on
this tool is mis-specified and is not built.**

The harness that does work needs no new code — one exported tree per list, each
with its own `deck.csv` on disk, and the matrix run from inside it:

```bash
D=log/noche-XXXX
git archive HEAD | (mkdir -p $D/tree_a && tar -x -C $D/tree_a)   # the old list
git archive HEAD | (mkdir -p $D/tree_b && tar -x -C $D/tree_b)
cp deck.csv $D/tree_b/deck.csv                                   # the new one
ln -sfn "$PWD/cg/build" $D/tree_a/cg/build                       # gitignored, and --seeds needs it
cd $D/tree_a && python utils/matchup_matrix.py --opponents /ABS/deck/real_opponents_500 ...
```

`deck/real_opponents_500/` is gitignored, so `--opponents` takes an **absolute**
path; `cg/build/` and `ptcg_engine/` are too, and a seeded run loads the engine
from the tree it lives in, so both need a symlink.

### `compare_runs.py` — the paired delta between two saved runs

```bash
python utils/compare_runs.py BASE.txt CAND.txt --weights deck/real_opponents_500/pesos.csv
```

Two arms measured with the same `--seeds` played the same games, so the honest
comparison is **paired**: the per-matchup difference and its weighted mean, not
the overlap of the two headline intervals. It prints prizes first (18 of 22
archetypes are above 92 % winrate and the winrate cannot rank them), how many
matchups moved at all — a delta carried by three decks is a different object
from one carried by all — and the delta **aggregated by archetype**, which is
the view that ranks: twenty Crustle lists moving +1 each is a finding, twenty
rows of +1 at 0.2 % weight is not visibly anything.

### `holdout_classify.py` — what the 370 unlabelled extras are

```bash
python utils/holdout_classify.py --out log/.../holdout.csv
```

Labels `competitor_decks_500/adicionales/` by nearest neighbour against the
admitted corpus, counting copies, and reports anything under 40/60 as
`desconocido` rather than forcing it into the closest bucket. Run 14 August
2026: the holdout is the same meta as the 500 (Marnie 32.7 % against 37.4 %,
Alakazam 20.3 % against 17.8 %) and only **5.9 % falls outside the corpus**, so
a recommendation fitted to the 500 is not fitted to 500 particular lists.

### `opponent_bot.py` — the reference opponent

The generic bot that pilots any deck legally and consistently. It is not a good
player and does not try to be: because its policy is fixed and deterministic,
the **difference** between two versions of our agent against it is signal, even
though the bot's absolute level is not.

**It answers YES to the `IS_FIRST` select like any other yes/no, and until
August 2026 that bounded every matchup number this project has.** Our agent used
to veto going first on purpose, so in matchup mode the bot went first in 60 of 60
games while the mirror ran 30/30: the matchup matrix, the Crustle axis and nearly
every gate on record describe only the going-**second** half of the game. Our
agent now answers YES too (`ptcg/turn/options/minor.py`), and since the engine
always offers that select to **seat 0** while `torneo` alternates seats, a
matchup run now splits the first turn ~50/50 rather than holding it fixed.

```python
OpponentBot()                        # unchanged: the historical measuring stick
OpponentBot(first_choice="second")   # it declines, and the coin flip decides
```

The default is deliberately untouched — moving the stick silently would break
comparison with every figure on record. A first reading of the other half, 400
games vs `crustle_kangaskhan` with the split decided by the flip inside one run:
**78.0% going first against 68.5% going second**.

---

## Understand losses

### `autopsy.py` — automatic autopsy of losses

Plays N games, records the decision stream of the ones we lost, and runs
detectors over them: a lethal attack that was available and never taken, and
sterile turns (ended with a full hand and no damage). Each loss is classified by
how we lost — prizes, bench-out, deck-out.

```bash
python utils/autopsy.py --opponent deck/real_opponents/<deck>.csv --games 40
python utils/autopsy.py --census ...        # census with a control group
```

**40 games collects records; it does not compare matchups.** At that size the
winrate swings enormously: two 60-game runs on a matched pair of Crustle lists
reported 83.3% and 81.7% — the same, to the eye — where the truth was 69.5% and
85.0%, and both errors happened to point the wrong way at once. Raised to 200
games both landed on the matrix's figure. Use the default to gather losses to
read; if the number itself is the finding, it needs 200+ or the matchup matrix.

### `collision_radar.py` — collisions between matchup rules

Finds the failure class nothing else finds: a veto written for one matchup that
kills a play another matchup requires. It defines deck-agnostic situations and
measures how often we resolve each one per opponent. A resolution rate that
collapses for a single deck points at the flag to inspect.

### `turn_explorer.py` — exhaustive turn explorer

Enumerates every legal sequence of **our** actions for one turn, evaluates the
resulting board, and reports the dominant line. If the agent's line is
dominated, you have a new scenario with the correct play already computed. It
models our turn only (no draws, no opponent branching) — that limit is
deliberate and documented in the script.

### `turn_waste_census.py` — is there anything to write a rule about?

Counts, per turn and per plan mode, the resources that were **legally playable
in the menu** and were declined: the turn's energy attachment, the Supporter
slot, an evolution, a body for the bench, an ability. It runs one step earlier
than every other tool here — before asking whether a rule would change a
decision, it asks whether the behaviour the rule would fix happens at all.

The first run (250 games) came back negative, and that answer is the point: the
agent is not leaving resources unspent, so the remaining ground is in *which*
legal play it picks, not in what it fails to spend. The script's docstring
carries the numbers.

```bash
python utils/turn_waste_census.py --games 250 --detail
```

### `wall_probe.py` — the immune-wall probe

Answers one specific question per turn: when our ex is blocked by an immune wall
and a non-ex answer is already charged on the bench, how does the turn end? Dry
turns are dumped as replayable observations.

**Read the dumps.** They are the point of the tool, not a side effect. Twenty-two
dry turns against `crustle_wall_6` shared one shape -- our active at zero energy
with no retreat in the menu while a charged Tapu Bulu sat on the bench -- and one
of them (`seco_019`) turned out to be a lethal line the agent could see and was
outbid on. That is the band-ordering bug of `_attach_enable_retreat_ko`.

### `healing_census.py` — how much of our damage gets healed away

Follows every opposing body by serial and separates the hit points we take off it
from the ones a card puts back. The number that matters is the ratio: damage that
never became a prize.

```bash
python utils/healing_census.py --opponent deck/real_opponents/crustle_wall_6.csv
```

Fifty-five of the ninety-seven real lists carry healing and the agent reads none
of it. Against `crustle_wall_6` -- the worst matchup in the matrix --
**83% of the damage we deal is healed back**; against `crustle_wall_2`, 44%;
against Marnie, 26%; in the mirror, 0%, which is the method's noise floor.

### `promoted_reply_census.py` — is a rule worth writing?

The shape every candidate rule should be put through before it is written: count
the nested populations, from "the situation happens" down to "and we had a choice
about it". It was built for one question (when our attack knocks their active
out, does the body they promote reply?) and its answer was to NOT write the rule:
the actionable population is 0.08% of decisions.

### `card_census.py` — what each of our sixty cards actually does

Every other instrument here measures a decision; this one measures the **list**.
It follows each of the sixty copies by its unique serial and records how it left
our hand: played, attached, evolved, spent as fodder, shuffled back, left to die
in hand, or looked at in a search and declined.

```bash
python utils/card_census.py --episodes log_analisys/                    # a recorded game
python utils/card_census.py --games 900 --opponent deck/real_opponents_500/crustle_wall_1.csv
python utils/card_census.py --games 80 --opponents deck/real_opponents_500 --allocation peso
python utils/card_census.py --episodes log/real_games --opponents deck/real_opponents_500
```

Two things it does that are easy to get wrong. **It matches the control group on
game length**: a lost game runs 31 turns against a won game's 13, so the raw
wins-vs-losses split reports the clock as if it were fourteen findings about
fourteen cards. And **it filters the event stream by `playerIndex`**, because both
seats' events arrive in our own observation — without that the census prices our
list using the opponent's plays.

The full write-up, including the cross-check between simulated and real games, is
in [the card census results](card-census-2026-08-13.md).

### `rule_census.py` — which named rules never fire

Every scoring rule here carries a NAME and every chain resolves through one choke
point in `ptcg/engine/rules.py`, and until August 2026 nobody counted. This does:
chain walked / evaluated / fired / decided, per rule, over the frozen corpus and
over self-play, sorted into four bands — the chain never ran, the rule was never
evaluated (dead by **ordering**), it was evaluated and never fired (dead by
**condition**), it fired and never decided.

```bash
python utils/rule_census.py --self-test
python utils/rule_census.py --corpus --games 400 --dump log/censo.json
python utils/rule_census.py --games 800 --opponent deck/opponents/alakazam.csv
```

It touches nothing: the rule OBJECTS are found by walking the loaded agent and
their `when`/`value` are wrapped in place, so the engine runs the code it always
runs. It refuses to print if its self-test fails.

**The output is a worklist, not a verdict**, and a zero says as much about the
workload as about the rule — run it at more than one load. What survives 2 400
games is what deserves reading. It found `xerosic_alakazam` (dominated by the
rule above it: 350 267 evaluations, zero fires) and `tapu_vs_crustle` (needs
`op_is_crustle_deck` and lives in the chain chosen when the opponent is *not*
Crustle).

### `blind_window_census.py` — how much of the turn a guard cannot see

A rule that opens with `not state.supporterPlayed` is not asking a question, it
is asking a question **with an expiry date**: before the Supporter slot is spent
it arbitrates, and afterwards it is a branch that can never be taken. The
decisions of the turn that happen after the resource is gone are that rule's
**blind window**, and this measures it per guard.

It exists for two real and expensive bugs. `_protect_last_supporter` was gated
on `not state.supporterPlayed` — and Xerosic's Machinations *is* a Supporter, so
on every forced discard that card can produce the flag was already True. The
rule was not misfiring, it was **unreachable**, blind window 100%, and had been
since it was written. That is the shape this census finds: a guard whose window
is near 100% is dead code that reads exactly like a live rule.

### `duplicate_protection_audit.py` — who protects the second copy too

A discard menu prices cards one at a time, so a protection meaning "this is our
only out" is handed to every copy in the hand — and only one copy can be the out.
The audit replays the frozen corpus with `score_option` wrapped and reports every
menu where two copies of a card came out with the SAME score in the keep band.

The fix shape is a latch (`_lillie_protected_once`, `_evo_spare_seen`). Its
self-test is historical rather than planted: `Meowth ex` is the standing corpus
flip (if the audit cannot see it, it is not looking) and `Forest of Vitality` was
latched in `ab1945a` (if the audit reports it, it is reading wrong).

### `promoted_relay_census.py` — the same shape, for the body that outlasts

Counts how often "the prize is cashed by the body that outlasts" actually fires
and what it flips. Its argument for existing is the one above: over 2 485 mirror
decisions the full population of the rule was **two boards**, and a rule that
fires in a fraction of a per cent has a ceiling of effect far below the noise
floor of the self-play gate. Asking the gate for a verdict there repeats an
error this project has already made.

### `relay_saves_the_game_census.py` — the retreat that saves the last prize

Third of the family, for the narrowest board any of them names: our attack takes
the knockout, the body they promote knocks our active out in reply, and those
prizes **close their count**. Same argument for existing as the two above — the
population is a subset of a fraction of a per cent — with one instrument the
others lack. It counts **firings** directly, by spying for the score only this
rule produces, instead of differencing two runs; and it carries a `--control`
arm in which the neutralisation does nothing, because asking the agent twice
about the same board perturbs what it answers about the next one and that noise
has to be measured before any flip column can be read.

```bash
python utils/relay_saves_the_game_census.py --games 300
python utils/relay_saves_the_game_census.py --games 300 --control   # the floor
```

### `match_point_reply_census.py` — and does the projection come true?

Fourth of the family, and the only one that asks a question about the READING
rather than about a rule. It takes the shelf `op_wins_after_ko` sits on — their
promoted reply closes their count, with an attack and a retreat both on the menu
— splits it three ways (a relay takes the same knockout / no knockout but a body
outlasts the reply / everything dies to the same reply) and then, for every board
where we attacked anyway, records whether the game **actually ended on their
reply**.

That second half is what stops a population from being mistaken for a licence.
Measured at 300 mirror games (19 018 decisions) and 300 games over the 87 real
opponent decks (20 660):

| | mirror | real opponents |
| --- | --- | --- |
| the shelf | 248 (1.30%) | 5 (0.02%) |
| ... a relay takes the same KO | 5 | 0 |
| ... a body merely outlasts the reply | 9 | 0 |
| ... everything dies to the same reply | 234 (94.4% of the shelf) | 5 |
| we attacked and the game closed on the reply | 32 of 59 (54.2%) | 1 of 1 |

Two conclusions, and both are load-bearing. The shelf is almost entirely boards
that were already lost — 94% of it — so the room for a rule is the 3.6% left.
And the flag is a **coin flip** as a prediction: it says the reply ends the game
and the reply ends the game a little over half the time. That is fine for a rule
whose downside is the retreat's energy and which cashes the prize either way; it
is not enough to pay a *prize* for, which is why the wider pivot was dropped
before it was written rather than after 400 games.

### `op_buff_census.py` — the bench body that raises their damage

Sibling of `op_scaling_census.py`, auditing the other family: not the attack
whose printed number is a placeholder, but the **flat bonus that is not on the
attacker at all** — a body on their bench whose ability boosts the whole team.

The failure it guards against is a Gabite whose Dragonslice prints 40 and took
70 off a Tapu Bulu that had 70 left. The extra 30 was a Roserade on their bench.
Nothing in the agent read it, so every defensive rule answered "it survives" and
the turn's energy went onto a body that was knocked out with the Grass still on
it.

### `op_immunity_census.py` — the tables that cancel our damage, against the cards

Third sibling of the two censuses above, and it exists for the same reason: a
table of ids rots silently. It diffs `EX_IMMUNE_IDS`, `ABILITY_IMMUNE_IDS` and
`FULL_HP_SURVIVE_IDS` against the printed ability text, in both directions — an
id in a table whose card does not say that thing, and a card that says it and is
in no table.

```bash
python utils/op_immunity_census.py            # the buckets
python utils/op_immunity_census.py --check    # exit 1 if a table is WRONG
```

It found `EX_IMMUNE_IDS` carrying Crustle **533**, whose ability is Sturdy — the
ex-immune wall is **345**, and the two share a name and nothing else. Every
attack from our ex read as zero against a 150 HP body that falls in one hit.
Exposure was 0 of 87 real lists, so nothing was bleeding; a wall that is not
there is still walked around for free. An exclusion (`Acerola's Mischief`: their
hand, their choice, one turn) has to carry its argument in `_EXCLUDED`, and a
test enforces that.

### `tier_inversion_census.py` — every menu where an ORDER beat a NUMBER

`max(range(len(scores)), key=lambda i: (_play_order_tier[i], scores[i]))`, at the
bottom of `ptcg/turn/finalize.py`, is the only place in this project where a
category decides before a value. On 12 August 2026 it produced two separate
defects in one day (`74f85f1`, `fcfb17d`), and neither could have gone red: in
both, the agent did exactly what its tiers say.

```bash
python utils/tier_inversion_census.py --corpus
python utils/tier_inversion_census.py --corpus --games 200 --dump out.json
```

It plants a sink in the loaded agent's own `finalize` namespace
(`TIER_CENSUS_SINK`, None in production) and, on every MAIN menu, compares the
option the tiers play against the one the score alone would pick. Over the
frozen corpus: **280 inversions in 2 097 MAIN menus (13.35 %)**, across 18 tier
pairs, each row naming the record of its widest gap.

**An inversion is not a defect** — it is the shape of every correct execution of
a winning attack, and most rows are the tier doing its job. What is read is the
GAP. The top row is `_TIER_DEVELOP` (40) over `_TIER_ENERGY` (10), **124 times,
median gap 10 000**, worst case a Pokémon drop over a Teal Dance worth 33 000
more — and there is a rule in this agent that says Teal Dance comes first.

### `card_text_census.py` — the card texts the code has never heard of

Fourth sibling, and the one that looks the other way round. The three above start
from a table **we wrote** and check it against the printed text, so a card nobody
ever thought about is in no table and therefore in no census. This one starts
from the **card pool** — every id in `deck/opponents/`, `deck/real_opponents/`
and `competitor_decks/` — and ends at the code, which is the only direction that
finds a *hole* rather than a *mistake*.

```bash
python utils/card_text_census.py               # ranked by decks that play it
python utils/card_text_census.py --band 1      # only what nothing mentions
python utils/card_text_census.py --self-test   # the two halves
```

Three bands: **NUNCA REFERENCIADA** (no id, no attack id, no constant of
`ids.py` appears anywhere under `main.py` or `ptcg/`), **SOLO NOMBRADA**
(`ids.py` binds a name and no module reads it) and **MODELADA**. A bare integer
in the source never promotes a card — `93` in a scorer is a score far more often
than it is Dipplin — it is printed as `? 93` and ignored, because the only thing
this instrument can do wrong is hide a hole.

It exists for **Deluxe Bomb (1167)**, 120 damage to our own attacker, which
`grep` found nowhere in the tree. On its first run over 408 lists it reported
227 cards with printable text and **94 in band 1**, and the sharpest finding was
not the card but its family: the same sentence is printed by **Spiky Energy (14,
17 measurable lists)**, **Handheld Fan (1161, 8)** and **Punk Helmet (1176, 2)**
— a cost on *who attacks* that the board does not show until after we commit.
Deluxe Bomb itself is in **0** measurable lists, so the class is testable and the
card that found it is not.

### `fodder_ladder_audit.py` — the cost paying with the fuel it is buying

Counts, over the same capture, how often a Basic Grass is scored ABOVE an
evolution the agent itself calls orphaned (`_evo_link_state`: pre-evolution
neither in play nor in hand) — the energy leaves and the dead card stays. On the
frozen corpus: **12 of 118 discard menus**, five of them dropping the last energy
in hand.

### `permutation_probe.py` — does the menu's order decide?

Plays games with two agent instances: the driver sees the real menu, the shadow
sees the same board with the options shuffled, and their choices are compared as
PLAYS rather than as indexes. Any difference is a decision the rules did not
make. Currently **0.6-0.7%** of decisions, most of them ties over which card a
search brings back.

`--dump DIR` writes each diverging board out whole, observation included, so it
can be replayed and turned into a fixture; `--kinds ABILITY,ATTACH` narrows the
dump to one class of tie. The percentage alone is not a finding — a board nobody
can reopen cannot be arbitrated.

### `search_oracle.py` — grading a decision against THE RULES

```bash
python utils/search_oracle.py --self-test --k 50    # both halves, ~5 s
python utils/search_oracle.py --cost 20             # ms per rollout on this machine
```

Phase D of [the engine-source plan](engine-source-plan-2026-08-12.md). Opens a
search from a real observation, forces one option as the first selection, plays
to the end under a policy, and reports who won and by how many prizes. Every
other instrument here grades the agent against another heuristic; this one rolls
the engine's own rules forward.

**It reads the opponent's hand and can never be a play-time policy.** It is a
grader for games we already hold both sides of; wiring it into `main.py` would be
cheating.

Three things it measured about itself, each of which edits the plan that asked
for it:

* **the prizes are unknowable**, even to their owner — a seat's own prize cards
  come back `None` in that seat's observation — so the determinization is part
  omniscient (their hand) and part **sampled**, and K averages over the sampling;
* **`search_begin` accepts a determinization that does not add up**: it validates
  only `len(...) < count`, so too many cards is silently tolerated. `determinize`
  closes its own arithmetic per seat and raises;
* **the API is not seeded**, so the oracle is an estimator, not a replay. Its
  noise floor is measured rather than assumed: at **K=20 the worst pair of
  batches of the same option disagrees by 30 pp**, at K=50 by 8, at K=100 by 6.
  Use K≥50, quote the worst floor, and read the prize margin before the win flag.

Cost: **9.3 ms per full rollout**, 143 steps to game end — cheaper than the plan's
own estimate, so two options at K=100 cost 1.9 s per decision.

### `differential_oracle.py` — what the plan predicted vs. what the engine resolved

The agent's attack plan states, before the attack, what it expects to happen. The
engine then resolves it. This replays games with both recorded and reports where
they disagree — a predicted knockout that did not happen is a `PHANTOM_KO`.

```bash
python utils/differential_oracle.py --games 40 --opponent deck/real_opponents/alakazam_1.csv
```

**Two readings that took three rounds to get right, both now built in.** It
judges the body *the plan was about*, not the one that took the hit: 89% of its
first findings were gusts the turn never played. And it is a **mirror** — it
watches whichever agent it is attached to, so pointed at self-play, half of its
residue is our agent failing to pilot the opponent's deck.

Its self-test has both halves (plant a lying plan, see the findings; remove it,
see the silence) and it refuses to print without them. That discipline is the
subject of [The instruments](instruments.md).

### `invariant_monitor.py` — things that must never be true

Checks, on every decision of every game, the properties that need no human to
know the right play: an index outside the option list, a turn ended with an
empty bench, and a **promise standing while its premise is dead**
(`STALE_FLAG` / `STALE_READ`).

The last of those needs a premise written next to the flag. Sixteen boolean
flags currently have none, and the monitor prints their names — a flag with no
premise is a flag nothing watches, which is how "our agent never goes first"
stayed invisible.

```bash
python utils/invariant_monitor.py --games 200 --dump log/ --dump-kinds STALE_READ
```

`--dump` without `--dump-kinds` counts findings and writes none. The tool says
so; read what it says.

### `mutation_probe.py` — which safety nets can actually fail?

Rewrites one expression at a time (comparisons, small integer boundaries, boolean
operators, `not`) and runs the suite against each mutant. A SURVIVOR is a line no
test is watching.

```bash
python utils/mutation_probe.py ptcg/calc/damage.py --lines 560-600
python utils/mutation_probe.py --changed HEAD~3     # only the lines a diff added
```

It edits the file in place -- the suite imports the agent from the tree -- and
restores it on exit, on exception and on a kill. `--changed` is the mode worth
using: it asks whether the test you just wrote watches the code you just wrote.

---

## Opponent decks

| Tool | Purpose |
| --- | --- |
| `download_competitor_decks.py` | Downloads the exact 60-card lists of the top leaderboard competitors from their public replays. Resumable. `--top 100` |
| `real_opponents.py` | Turns those lists into *measurable* opponents: deduplicates them (300 decks are ~93 unique lists), keeps each one's meta weight, and screens out lists the generic bot cannot pilot — an unpilotable list measures the bot getting stuck, not the matchup, and returns a falsely high winrate. It also marks the lists that are near-copies of our own 60 (`solape_propio` in `pesos.csv`): the bot pilots those legally but pilots *our* engine, badly, so they read as a matchup we dominate. They are kept, because people play them, and flagged so the aggregation can report the field with and without. |
| `build_meta_decks.py` | Hand-built synthetic archetype decks, for mechanics the real meta does not currently offer. |
| `harvest_opponent_deck.py` | Rebuilds a plausible 60-card opponent list from what was visible in local game records. |
| `op_scaling_census.py` | Audits `ptcg/cards/op_scaling.py` against every opposing deck in the repo: which attacks scale with the board rather than doing their printed damage, which of them the agent reads, and which are missing. The suite runs it as a gate — a new deck that brings an unread one is invisible in a game, because the agent does not crash, it just walks into the hit. `--unmodelled` |
| `meta_representation_report.py` | Reads the harvested leaderboard index and answers two questions that are **not** the same one: how much of the top an archetype occupies, and how that presence is distributed across bands of thirty positions. An archetype can be 10% of the field and own the first band, or be everywhere and never reach the top 30. |
| `corpus_bridge.py` | Carries a finding across a rebuild of the corpus, matching by content instead of by name. See above. |

---

## Reproduce and debug

| Tool | Purpose |
| --- | --- |
| `log_replay.py` | Replays a recorded game through the agent and compares its choices with what was actually played. `--verbose`, `--interactive`, `--max-items N` |
| `split_turns.py` | Splits a game log into one record per turn, into `records/`. Takes no arguments. |
| `record_corpus.py` | Records fresh games against the real leaderboard decks, in the same format, so the golden corpus can be regenerated without depending on downloaded replays. |

See [Debugging a decision](debugging.md) for how these fit together.

---

## The corpus, frozen

### `freeze_corpus.py` — make the flip-diff run on a clean checkout

The flip-diff — *which historical decisions did your change flip, exactly* — is
the most useful review artefact this project produces, and for a long time it
did not exist for anyone who had just cloned the repository: `records/` is
git-ignored transient data, so the local corpus test skips.

The corpus only ever replays **our own decisions**, so keeping just those and
gzipping takes 50 whole games from 41 MB to **0.85 MB**, which is small enough
to commit. No sampling and no "representative subset": all of them.

```bash
python utils/record_corpus.py --games 50       # play the games
python utils/freeze_corpus.py                  # freeze them + the snapshot
python utils/freeze_corpus.py --snapshot-only  # accept reviewed flips
```

**`--snapshot-only` is the flag for accepting a flip**, and getting this wrong
is the trap the script's header is mostly about. The bare command *rebuilds the
bundle* from whatever is in your `records/` — usually a handful of games against
the fifty in the committed bundle — and the bundle is a gzip, so the commit diff
does not show what was thrown away. Shrinking now needs `--force`.

Both corpora are kept, because they behave differently on purpose: the local one
self-heals when a record is replaced, the frozen one cannot, and that is what
makes it usable as a gate.

### `corpus_bridge.py` — carry a finding across a rebuild of the opponent corpus

`crustle_wall_6` is not a deck, it is a **rank**: the lists are numbered by
descending meta weight within their archetype, so after the leaderboard is
re-harvested the same name lands on different sixty cards. A finding recorded by
name then either gets re-measured against the wrong deck and called
irreproducible, or measured against the right deck under a name nobody wrote
down.

The bridge matches by **content**, never by name, and sorts every list into
IDENTICAL, DRIFTED (with the card distance printed, not assumed), GONE — the
deck left the top 300, which is a result and not a failure — or NEW.

```bash
python utils/corpus_bridge.py --old deck/real_opponents_2026-08-07 \
                              --new deck/real_opponents
```

---

## The CI gates

These are the two jobs in [.github/workflows/gates.yml](../.github/workflows/gates.yml)
that are not simply "run the suite".

| Tool | Purpose |
| --- | --- |
| `gate_coverage.py` | A **ratchet**, not a target. `coverage-floors.json` records what the unit suite covers of each module today, and the gate fails when one of them drops by more than half a point. It exists because a module reached 6% covered while that week's diffs were being written into it and nothing said so. `--update` raises the floors; lowering one belongs in a commit message. |
| `gate_mutation.py` | Mutates **only the lines a pull request adds** and asks whether any test goes red. A survivor is not proof the line is wrong — it is proof that if it ever becomes wrong, nothing will say so. It runs `--self-test-only` first and aborts rather than reporting, because two earlier versions of it reported their own bugs as findings. Non-blocking for now, on purpose. |

### The per-rule gates: `gate_*.py`

The rest of the `gate_*.py` family is written **per candidate rule**, not per
project: `gate_the_engine_waits.py`, `gate_the_cap_reads_their_hand.py`,
`gate_promoted_relay.py`, `gate_what_the_search_bought.py`,
`gate_the_search_buys.py` and so on. Each one exports two trees, loads an agent
from each, and plays the same matchups with both, so the change under test is
the only difference between the arms.

`gate_the_search_buys.py` is worth reading as the model of the *other* way to
build an arm: instead of exporting two trees, it loads the same tree twice and
switches the predicate off on one of the loaded module objects. Nothing on disk
is rewritten, so it is safe to leave running while you edit other files — unlike
the mutation and A/B-by-swap harnesses, which **are** the working tree while
they run.

Three things a new one must do, all three learned from a gate that reported a
false neutral:

1. **export both trees**, package included. A change under `ptcg/` that both
   arms import from the working tree comes out of both arms identically, and the
   gate reports exactly zero;
2. **define and call `provenance()`**, which prints what each arm actually is.
   Rule R7 of `lint_architecture.py` checks this statically;
3. **state its own control** — an opponent the rule cannot fire against, run in
   the same session. A delta that does not clear the control's noise floor is
   not a delta.

---

## Ship it

### `package_project.py`

Builds `submission.tar.gz` with `main.py`, `deck.csv` and the local packages
that `main.py` imports. The package list is **derived from the imports**, so a
new package is included the moment the agent imports it — nobody has to remember
to update the script. Forgetting one is the most expensive possible mistake: the
submission starts broken in the competition with every local test green.

---

## Architecture and refactoring

These exist because of the large refactor described in
[Project history](project-history.md). They are still useful when moving code.

| Tool | Purpose |
| --- | --- |
| `lint_architecture.py` | **Eight** architecture rules, checked by the test suite. They cover failures that do **not** show up as a red test. R1–R5 watch the agent: importing a mutable by name (freezes a stale copy), data modules touching state, anything bound after the agent entry point (breaks the competition loader), lazy imports that break the container, one name defined twice. R6–R8 watch the INSTRUMENTS, and each comes from a bug that shipped on 10 August 2026: a test may not read a `records/` file without a skip guard (that directory is re-harvested), a two-arm `gate_*.py` must define **and call** `provenance()` (a gate that cannot see its own change reports neutral, and neutral orders a revert here), and inside the DISCARD block the turn-scoped flags may only be read through the horizon (on a forced discard they are the opponent's). |
| `purity.py` | Proves which definitions can be moved out of `main.py` without touching mutable state. |
| `extract_pure.py` / `extract_definitions.py` | Move constants and definitions into package modules, carrying their comments with them. |
| `migrate_state.py` | Rewrites module-level state into fields of the state object, editing text in place so comments survive. |
| `shadow.py` | The equivalence gate: plays self-play with the old version and asks the new one for the same observation. Any different choice is a flip. |
| `measure_route_recover.py` | The shadow pattern applied to one rule that lives entirely under `ptcg/`, where `selfplay.py --base` measures 50% by construction. It loads each agent with `sys.path` pointing at its own complete tree and checks the `__file__` of the function under test before trusting a single number — the same lesson that later became lint rule R7. |

---

## Assets

| Tool | Purpose |
| --- | --- |
| `deck/render_deck_image.py` | Renders `deck/deck_en.jpg` from `deck.csv` and the official card data. Needs the optional render dependencies. |

---

Next: [Testing](testing.md) · [Debugging a decision](debugging.md)

## Flag names: what changed

The command line used to be in Spanish. It is not any more, and there are no
aliases: an old invocation fails with argparse's own error. The mapping, for
commands you may have written down:

| Old | New |
|---|---|
| `--partidas` | `--games` |
| `--rival` | `--opponent` |
| `--rivales` | `--opponents` |
| `--pesos` | `--weights` |
| `--espejo` | `--mirror` |
| `--censo` | `--census` |
| `--todos` | `--all` |
| `--candidato` | `--candidate` |
| `--control-carta` | `--control-card` |
| `--sin-criba` | `--no-filter` |
| `--salida` | `--output` |
| `--destino` | `--target` |
| `--origen` | `--source` |
| `--actualizar` | `--update` |
| `--aplicar` | `--apply` |
| `--volcar` | `--dump` |
| `--desde` / `--hasta` | `--from-line` / `--to-line` |

`tests/test_cli.py` keeps it that way: it fails if a script offers a Spanish
flag again, and if any `args.X` a script reads is not a `dest` its parser
declares.

## What is still Spanish, and why

The identifiers are done: four batches renamed them with
`utils/rename_code.py`, which proves against git that **only** the mapped names
moved. What is left is **stored data**, and it is left on purpose:

- the finding fields the tools write and read — `turno`, `hallazgos`,
  `detector`, `detalle`, `modo_derrota` — carried by the 900+ files under
  `records/` and by the golden decisions;
- the `pesos.csv` columns — `archivo`, `arquetipo`, `peso_meta`,
  `solape_propio`, `motivo`.

Renaming a stored field is not a rename, it is a migration: every file already
written keeps the old spelling, and the reader that stops accepting it breaks
silently. That is not hypothetical — it is what left `turn_explorer.py`
crashing on every real finding until it was fixed. When these do move, they
move with a converter for the existing records and a reader that accepts both
spellings, with the golden corpus as the witness.

Two rules that come out of doing the batches:

- **Run `rename_code.py` on Python 3.12 or newer.** Below that a whole
  f-string is one token, so `f"{old_name}"` survives the rename while the
  assignment above it does not. The tool now refuses to start.
- **Screen the map for collisions first.** The AST proof shows that nothing but
  names changed; it cannot show that two different symbols were not merged into
  one. Check every target against the names already present in the files the
  source appears in.
