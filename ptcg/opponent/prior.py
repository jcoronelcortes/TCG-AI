"""The opponent is not a flag, it is a posterior over the 133 real lists.

Phase S1 of docs/plan-la-busqueda-en-juego-2026-08-15.md. The archetype flags
(`op_is_*_deck`) have caused four documented defects because a boolean cannot
say "how sure are we". This module answers that question: given one
observation, a normalised distribution over the admitted leaderboard lists,
with the meta share as the prior.

Three design decisions, each forced by a measured fact:

1. **Hosting is binary and coverage among hosts is always total.** A list
   HOSTS a board when every visible opponent card fits inside its sixty
   (multiset subset). Among hosting lists the coverage score of the
   `oracle_*` twins (`_their_deck_for`) is therefore always 100 %, so the
   discrimination between hosts comes from the meta prior and from the board
   growing until it evicts the wrong lists -- not from coverage. Coverage
   only ranks the FALLBACK, when no list hosts (an off-meta opponent).

2. **A list that cannot host the board gets probability zero, not a low
   score.** Same semantics as `DeterminizationError` in
   `utils/search_oracle.py`: an early draft of the twins graded a Dragapult
   board under an Alakazam list because the arithmetic closed by accident.

3. **No engine, no state.** `ids_seen` is a faithful port of
   `utils/search_oracle._ids_seen` (attached energies, tools, pre-evolutions,
   the stadium's owner, and the cards IN FLIGHT -- `current.looking` and
   `select.effect` -- are all cards of that seat's sixty). The census tool
   cross-checks the two implementations board by board; if they ever diverge,
   the census fails, not the game.

The lists live in `deck/real_opponents_500/` which is GITIGNORED: this module
is a shadow instrument. Shipping it inside the submission would require
embedding the lists in a generated module -- a daytime decision, out of scope
here (rule of the night: main.py is not touched).
"""

from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
OPPONENTS_DIR = _ROOT / "deck" / "real_opponents_500"
PESOS_CSV = OPPONENTS_DIR / "pesos.csv"

# Sharpening for the no-host fallback: coverage differences between wrong
# lists are small (a foreign board shares trainers with everyone), so the
# ranking is raised to a power to keep the fallback from looking confident.
FALLBACK_SHARPNESS = 8

# A list whose meta weight is zero still exists on the ladder: the floor keeps
# it samplable instead of silently unreachable.
WEIGHT_FLOOR = 1e-6


def ids_seen(obs, seat):
    """Counter of card ids of `seat` VISIBLE in this observation.

    Port of `utils/search_oracle._ids_seen` with no engine import. Attached
    energies, tools and pre-evolutions are cards; the stadium belongs to the
    seat that played it; a card being looked at or mid-effect is in no zone
    but is still one of the sixty.
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
        take(card)  # only ALREADY REVEALED prizes are not None
    for key in ("active", "bench"):
        for body in (me.get(key) or []):
            if not body:
                continue
            take(body)
            for card in ((body.get("energyCards") or [])
                         + (body.get("tools") or [])
                         + (body.get("preEvolution") or [])):
                take(card)
    stadium = (obs.get("current") or {}).get("stadium")
    for card in (stadium if isinstance(stadium, list) else [stadium]):
        if card and card.get("playerIndex") == seat:
            take(card)
    looking = (obs.get("current") or {}).get("looking")
    for card in (looking if isinstance(looking, list) else [looking]):
        if card and card.get("playerIndex") == seat:
            take(card)
    effect = (obs.get("select") or {}).get("effect")
    for card in (effect if isinstance(effect, list) else [effect]):
        if card and card.get("playerIndex") == seat:
            take(card)
    return seen


def _read_deck_file(path):
    """Sixty ids, one per line -- the format of `utils/selfplay.read_deck`."""
    lines = Path(path).read_text().split("\n")
    return [int(lines[i]) for i in range(60)]


class OpponentPrior:
    """A posterior over lists, computed fresh from each observation.

    Stateless on purpose: the visible board only grows during a game, so the
    observation alone carries all the evidence, and a stateless object cannot
    accumulate a belief that the real board no longer supports.
    """

    def __init__(self, entries):
        # entries: iterable of (name, archetype, weight, deck_ids[60])
        self.entries = []
        for name, archetype, weight, deck in entries:
            self.entries.append((name, archetype,
                                 max(float(weight), WEIGHT_FLOOR),
                                 Counter(deck), list(deck)))
        if not self.entries:
            raise ValueError("OpponentPrior needs at least one list")

    # ------------------------------------------------------------- loading

    @classmethod
    def load(cls, opponents_dir=None, pesos_csv=None, flat=False):
        """The admitted lists of `pesos.csv` with their meta weight.

        `flat=True` is the pre-registered fallback of the plan's §4: same
        lists, uniform weight, for when the census says the meta prior does
        not earn its keep.
        """
        import csv

        opp = Path(opponents_dir or OPPONENTS_DIR)
        pesos = Path(pesos_csv or (opp / "pesos.csv"))
        entries = []
        with open(pesos, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if row.get("estado") != "admitido":
                    continue
                path = opp / row["archivo"]
                try:
                    deck = _read_deck_file(path)
                except (OSError, ValueError, IndexError):
                    continue
                weight = 1.0 if flat else float(row.get("peso_meta") or 0.0)
                entries.append((path.stem, row.get("arquetipo") or path.stem,
                                weight, deck))
        return cls(entries)

    @classmethod
    def flat(cls, opponents_dir=None, pesos_csv=None):
        return cls.load(opponents_dir, pesos_csv, flat=True)

    # ----------------------------------------------------------- inference

    def _opponent_seat(self, obs):
        return 1 - ((obs.get("current") or {}).get("yourIndex") or 0)

    def evaluate(self, obs, seat=None):
        """The full reading: `(posterior, hosted)`.

        `posterior` is `[(name, prob), ...]` sorted by prob, normalised.
        `hosted` says which arm produced it: True = at least one list hosts
        the whole visible board (probability mass only on hosts); False = the
        coverage fallback, which should be read as "closest, not confirmed".
        """
        seat = self._opponent_seat(obs) if seat is None else seat
        seen = ids_seen(obs, seat)
        hosts, fallback = [], []
        total_seen = sum(seen.values()) or 1
        for name, _arch, weight, deck_counter, _deck in self.entries:
            foreign = seen - deck_counter
            if not foreign:
                hosts.append((name, weight))
            else:
                hit = total_seen - sum(foreign.values())
                fallback.append(
                    (name, weight * (hit / total_seen) ** FALLBACK_SHARPNESS))
        chosen, hosted = (hosts, True) if hosts else (fallback, False)
        mass = sum(w for _n, w in chosen)
        if mass <= 0:  # degenerate fallback: nothing overlaps at all
            chosen = [(name, 1.0) for name, _w in chosen]
            mass = float(len(chosen))
        posterior = sorted(((n, w / mass) for n, w in chosen),
                           key=lambda kv: -kv[1])
        return posterior, hosted

    def posterior(self, obs, seat=None):
        return self.evaluate(obs, seat)[0]

    def top1(self, obs, seat=None):
        return self.posterior(obs, seat)[0]

    def archetype_of(self, name):
        for entry_name, archetype, _w, _c, _d in self.entries:
            if entry_name == name:
                return archetype
        return None

    def archetype_posterior(self, obs, seat=None):
        by_arch = {}
        for name, prob in self.posterior(obs, seat):
            arch = self.archetype_of(name)
            by_arch[arch] = by_arch.get(arch, 0.0) + prob
        return sorted(by_arch.items(), key=lambda kv: -kv[1])

    def top1_archetype(self, obs, seat=None):
        return self.archetype_posterior(obs, seat)[0]

    def sample_deck(self, obs, rng, seat=None):
        """One list drawn from the posterior -- the sampler of phase S2.

        K rollouts calling this average over WHICH deck they brought as well
        as over the shuffle. Zero-probability lists are unreachable.
        """
        posterior, _hosted = self.evaluate(obs, seat)
        roll = rng.random()
        acc = 0.0
        for name, prob in posterior:
            acc += prob
            if roll <= acc:
                break
        for entry_name, _arch, _w, _c, deck in self.entries:
            if entry_name == name:
                return name, list(deck)
        raise RuntimeError("posterior returned a name outside the entries")
