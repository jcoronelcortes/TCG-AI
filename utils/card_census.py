"""What each of our sixty cards actually DOES in a game.

Every other instrument here measures a DECISION. This one measures the LIST: for
each of the 60 cards, how often it is drawn at all, how often it is played once
drawn, how often it dies in hand, how often it is spent as fodder, and how often
we look straight at it in a search and put it back.

WHY IT EXISTS. The night of 13 August found that the hard matchups (Crustle Wall
80.0 %, Ogerpon Verde 85.4 %) are lost to board and resource STARVATION, not to
misplay: "stuck with an escape available and not taken" is flat across archetypes
while "stuck with no escape" separates by +8.6 to +29.2. Starvation is what a LIST
change addresses and a scoring rule does not, so the instrument that acts on that
finding is a census of the list. See `docs/card-census-plan-2026-08-13.md`.

THE ENGINE DOES THE HARD PART. `observation.logs` is a per-step event stream with
semantic types (`cg/api.py::LogType`), and every copy of every card carries a
unique global `serial`. So a census is per COPY, not per id, and nothing has to be
inferred from action indices. The one worry a card census usually has -- that a
Supporter PLAYED and a card DISCARDED as Ultra Ball fodder both look like
HAND -> DISCARD -- does not apply: see FODDER below.

WHAT WAS MEASURED ON THE REAL EPISODE before this file was written
(`log_analisys/92413910.json`, 173 steps, our seat 0, serials 3-62):

* **A played card emits `PLAY` and NO `MOVE_CARD` at all.** 22 PLAY events, 0 of
  them paired with a MOVE_CARD for the same serial, in the same batch or any
  other. Conversely all 14 `MOVE_CARD(HAND->DISCARD)` events belong to serials
  that were never played. So FODDER needs no same-step correlation: a
  HAND -> DISCARD *is* a discard-as-cost. This is stronger than the plan's rule
  and it removes its stated risk.
* **The opponent's events arrive in OUR stream.** Every batch carries both seats'
  events, tagged by `playerIndex`. Filtering by it is not optional: it is what
  turned the plan's impossible "8 PRIZE->HAND events for 6 prizes" into the true
  5 (five prizes taken, one still unrevealed at the end -- it adds up).
* **The opening hand is visible.** Seven `DRAW` events with serials, plus the
  mulligan, before the first decision.
* **The starting Basic is `MOVE_CARD(HAND->ACTIVE)`, not `PLAY`.** Setup
  placement has its own fate (`PUESTA_EN_JUEGO`) for that reason.
* **Our own face-down residue is exactly the 6 prizes being dealt.** All 6
  `MOVE_CARD_REVERSE` events for our seat are DECK -> PRIZE at setup, so the
  blindness the plan budgeted for (§6.2) is a known constant on our side, not an
  open hole.

WHAT 10 635 SIMULATED GAMES THEN ADDED, found by the `OTRO` alarm going off 48
times -- which is what the alarm is for:

* **A mill opponent hides the hand it empties.** All 20 attributable transitions
  were censused; two were unhandled. `LOOKING -> DISCARD` is the visible half of
  the opponent rifling our hand: the departure itself is a FACE-DOWN
  `HAND -> LOOKING` with no cardId, so the copy vanishes and reappears on its way
  to the discard. It gets its own fate, `DESCARTADA_EN_REVELADO`, because we did
  not choose to spend it and calling that fodder would be a lie. It concentrates
  exactly where it should: 19 of 36 games against Comfey mill, against 21 of
  1 096 versus Crustle Wall.
* **A card can enter play straight from the deck.** So entering play is read by
  DESTINATION and not by source -- while excluding sources already IN play, or a
  promotion would relabel a ten-turn attacker as freshly placed.

WHERE IT STILL CANNOT SEE, and every table says so:

* `NO_VISTA` is "deck OR unrevealed prize", never "we never drew it". Six of 60
  cards are systematically invisible, so the report prints the unrevealed-prize
  count next to it.
* Events after our seat's LAST observation are lost -- typically the final
  knock-out. Nothing that decides a list depends on them.
* **A low conversion is not a bad card.** A counter-stadium that sat in hand all
  game because the opponent never played a stadium did its job by being
  available. This census RANKS CANDIDATES FOR A HUMAN; it does not cut cards.

Usage:
    # the pure core, on a recorded game -- no engine, no network
    python utils/card_census.py --episodes log_analisys/92413910.json

    # Track S: simulated games against one opponent
    python utils/card_census.py --games 400 --opponent deck/real_opponents_500/crustle_wall_1.csv

    # Track S: the whole corpus, budget by meta share (V1 + V2)
    python utils/card_census.py --games 40 --opponents deck/real_opponents_500 --allocation peso

    # Track R: our own real ladder games
    python utils/download_player_games.py --player "Jose Coronel"
    python utils/card_census.py --episodes "Jose Coronel"
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cg.api import AreaType, LogType, all_card_data  # noqa: E402

# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------

DECK_SIZE = 60
PRIZES = 6

# A fate per copy, in RESOLUTION ORDER: the first rule that matches wins.
JUGADA = "JUGADA"
ADJUNTADA = "ADJUNTADA"
EVOLUCIONO = "EVOLUCIONO"
PUESTA_EN_JUEGO = "PUESTA_EN_JUEGO"
FORRAJE = "FORRAJE"
DESCARTADA_EN_REVELADO = "DESCARTADA_EN_REVELADO"
DEVUELTA_AL_MAZO = "DEVUELTA_AL_MAZO"
MUERTA_EN_MANO = "MUERTA_EN_MANO"
MIRADA_Y_RECHAZADA = "MIRADA_Y_RECHAZADA"
PREMIO_TOMADO = "PREMIO_TOMADO"
NO_VISTA = "NO_VISTA"
OTRO = "OTRO"

FATES = (JUGADA, ADJUNTADA, EVOLUCIONO, PUESTA_EN_JUEGO, FORRAJE,
         DESCARTADA_EN_REVELADO, DEVUELTA_AL_MAZO, MUERTA_EN_MANO,
         MIRADA_Y_RECHAZADA, PREMIO_TOMADO, NO_VISTA, OTRO)

# Where a card is once it is on the board. A move OUT of one of these is a
# promotion or a knock-out, never a card entering play, and telling them apart is
# what stops a promoted attacker being relabelled as freshly placed.
_IN_PLAY = frozenset({int(AreaType.ACTIVE), int(AreaType.BENCH),
                      int(AreaType.PRE_EVOLUTION)})

# The card did its job. Attaching an energy and evolving a line are not "playing
# a card from hand" to the engine, but they are the card being spent on purpose,
# which is what the list wants to know.
CONVERTIDA = frozenset({JUGADA, ADJUNTADA, EVOLUCIONO, PUESTA_EN_JUEGO})

# `OTRO` must stay empty. It is not a fate, it is the resolver's own alarm: with
# it the fates always sum to 60, so a bug shows up as a labelled residue in the
# table instead of as a silently wrong denominator.

_NAMES: dict[int, str] | None = None


def card_names() -> dict[int, str]:
    global _NAMES
    if _NAMES is None:
        _NAMES = {c.cardId: c.name for c in all_card_data()}
    return _NAMES


def read_deck(path=None) -> list[int]:
    """Our 60 card ids. `deck.csv` is 60 bare integers, one per line."""
    text = Path(path or _ROOT / "deck.csv").read_text(encoding="utf-8-sig")
    ids = [int(x) for x in text.split() if x.strip()]
    if len(ids) != DECK_SIZE:
        raise ValueError(f"{path or 'deck.csv'} has {len(ids)} cards, not {DECK_SIZE}")
    return ids


# ---------------------------------------------------------------------------
# B1: the pure core. No engine, no network, no games -- an event stream in,
# sixty rows out.
# ---------------------------------------------------------------------------

def zones_of(obs, seat) -> dict[int, int]:
    """{serial: AreaType} for every card of `seat` VISIBLE in one observation.

    The terminal zone is read from the observation rather than replayed from the
    stream on purpose: a played Trainer reaches the discard with no movement
    event at all, so the stream alone cannot say where a card ended.
    """
    out: dict[int, int] = {}
    me = ((obs.get("current") or {}).get("players") or [None, None])[seat]
    if not me:
        return out

    def put(card, area):
        if card and card.get("serial") is not None:
            out[card["serial"]] = area

    for card in (me.get("hand") or []):
        put(card, AreaType.HAND)
    for card in (me.get("discard") or []):
        put(card, AreaType.DISCARD)
    for card in (me.get("prize") or []):
        put(card, AreaType.PRIZE)  # only the ones already revealed are not None
    for area, key in ((AreaType.ACTIVE, "active"), (AreaType.BENCH, "bench")):
        for body in (me.get(key) or []):
            if not body:
                continue
            put(body, area)
            for card in ((body.get("energyCards") or []) + (body.get("tools") or [])
                         + (body.get("preEvolution") or [])):
                put(card, area)
    stadium = (obs.get("current") or {}).get("stadium")
    if isinstance(stadium, dict) and stadium.get("playerIndex") == seat:
        put(stadium, AreaType.STADIUM)
    return out


def unrevealed_prizes(obs, seat) -> int:
    """How many of our prizes were still face-down. §6.1's honest denominator."""
    me = ((obs.get("current") or {}).get("players") or [None, None])[seat]
    if not me:
        return 0
    return sum(1 for p in (me.get("prize") or []) if p is None)


def events_received(observations, seat):
    """[(turn, event)] for `seat`, from the observations that seat was HANDED.

    Deduplication is the whole difficulty of reading a replay: an INACTIVE seat's
    observation is a stale copy of its previous one, so counting every step's
    `logs` triple-counts. Taking the logs of the observations the seat actually
    acts on solves it, and it is also exactly what an in-process game hands us --
    which is what makes Track S and Track R comparable at all (B7).

    Verified on `log_analisys/92413910.json`: this rule and an independent
    "skip a batch identical to the previous accepted one" rule return the SAME
    455 events. Two rules agreeing is why the count is trusted.

    The events of BOTH seats come through; filtering by `playerIndex` is left to
    the caller so the opponent's stream stays available for other instruments.
    """
    out = []
    for obs in observations:
        turn = (obs.get("current") or {}).get("turn", 0)
        for event in (obs.get("logs") or []):
            out.append((turn, event))
    return out


def _hand_arrival(event) -> bool:
    """Did this event put the card into our hand?"""
    return (event["type"] == LogType.DRAW
            or (event["type"] == LogType.MOVE_CARD
                and event.get("toArea") == AreaType.HAND))


def resolve_game(events, seat, terminal, deck_ids, *, last_turn=0,
                 prizes_hidden=0):
    """The fate of all sixty copies in ONE game. Pure: this is B1.

    `events` is [(turn, event)] as `events_received` returns it, `terminal` the
    zones from the last observation of our seat, `deck_ids` our 60 ids.

    It always returns exactly 60 rows, one per copy. Serials that appear in no
    event are not enumerable (their ids are hidden in deck and prizes), so the
    unseen remainder is recovered as a MULTISET SUBTRACTION against `deck_ids`
    and emitted as `NO_VISTA` rows with `serial=None`. That is what makes the
    specificity test -- 60 rows, one fate each -- checkable rather than aspirational.
    """
    mine = [(t, e) for t, e in events if e.get("playerIndex") == seat]

    per_serial: dict[int, list[tuple[int, int, dict]]] = defaultdict(list)
    card_of: dict[int, int] = {}
    for order, (turn, event) in enumerate(mine):
        serial = event.get("serial")
        if serial is None:
            continue
        # The ORDER matters and the turn is not enough: a copy can be drawn,
        # shuffled back and drawn again inside one turn (serial 43 of episode
        # 92484395 does exactly that), and only the sequence says which came last.
        per_serial[serial].append((order, turn, event))
        if event.get("cardId") is not None:
            card_of.setdefault(serial, event["cardId"])

    # A card can also be visible in a zone without ever having produced an event
    # we can attribute (a prize revealed by the opponent, say).
    for serial in terminal:
        per_serial.setdefault(serial, [])

    rows = []
    for serial, evs in sorted(per_serial.items()):
        card_id = card_of.get(serial)
        if card_id is None:
            continue  # not ours to name; the multiset subtraction will catch it
        rows.append(_row_of_serial(serial, card_id, evs, terminal.get(serial),
                                   last_turn))

    seen = Counter(r["card_id"] for r in rows)
    missing = Counter(deck_ids) - seen
    surplus = seen - Counter(deck_ids)
    for card_id, count in sorted(missing.items()):
        for _ in range(count):
            rows.append(_blank_row(card_id))

    # Face-down movement carries no cardId, so it is blindness by construction and
    # is reported BY TRANSITION: the six DECK -> PRIZE of the deal are a known
    # constant, while HAND -> LOOKING is the opponent rifling our hand and is the
    # only one that can strand a copy with no attributable departure.
    facedown = Counter()
    for _t, event in mine:
        if event["type"] == LogType.MOVE_CARD_REVERSE:
            facedown[(event.get("fromArea"), event.get("toArea"))] += 1
    diag = {
        "filas": len(rows),
        "sobrantes": sum(surplus.values()),  # seen more copies than the deck has
        "premios_ocultos": prizes_hidden,
        "cara_abajo": sum(facedown.values()),
        "reparto_premios": facedown.get((int(AreaType.DECK), int(AreaType.PRIZE)), 0),
        "mano_revelada": facedown.get((int(AreaType.HAND), int(AreaType.LOOKING)), 0),
        "turnos": last_turn,
        "otro": sum(1 for r in rows if r["fate"] == OTRO),
    }
    return rows, diag


def _blank_row(card_id):
    return {
        "serial": None, "card_id": card_id, "fate": NO_VISTA, "robada": 0,
        "veces_jugada": 0, "veces_mirada": 0, "veces_rechazada": 0,
        "veces_recuperada": 0, "de_premio": 0, "turno_primer_juego": None,
        "turno_primera_vista": None, "turnos_en_mano": 0, "zona_final": None,
    }


def _row_of_serial(serial, card_id, evs, terminal, last_turn):
    """One copy's row.

    THE FATE IS HOW THE COPY LAST LEFT OUR HAND, and the plan's §2 order had to
    be corrected to say so. Written as a first-match-wins list of rules it
    assumed each rule could fire only once; a copy that is drawn, shuffled back
    by a Marnie and drawn AGAIN fires two of them, and the list answered
    "shuffled back" for a card sitting in our hand at the end.

    So: the observation is the authority on where a copy ENDED (`zones_of`), the
    stream decides only HOW it left, and among several departures the LAST one
    wins. The counters keep the history the single fate cannot carry.
    """
    played = [(o, t) for o, t, e in evs if e["type"] == LogType.PLAY]
    attached = [(o, t) for o, t, e in evs if e["type"] == LogType.ATTACH]
    evolved = [(o, t) for o, t, e in evs if e["type"] == LogType.EVOLVE]
    moves = [(o, t, e) for o, t, e in evs if e["type"] == LogType.MOVE_CARD]

    def movement(src, dst):
        return [(o, t) for o, t, e in moves
                if e.get("fromArea") == src and e.get("toArea") == dst]

    # Entering play is read by DESTINATION, not by source: a card can be put on
    # the bench straight from the deck. Moves that START in play are promotions
    # and knock-outs, and folding them in here would relabel an attacker that has
    # been fighting for ten turns as one just placed.
    into_play = [(o, t) for o, t, e in moves
                 if e.get("toArea") in (int(AreaType.ACTIVE), int(AreaType.BENCH))
                 and e.get("fromArea") not in _IN_PLAY]
    fodder = movement(AreaType.HAND, AreaType.DISCARD)
    # The opponent's mill reveals our hand as a face-down HAND -> LOOKING, so the
    # card's own departure is only visible as LOOKING -> DISCARD. See the
    # module docstring: this is the engine hiding the step, not a card we chose
    # to spend, and it gets its own fate rather than being called fodder.
    revealed_away = movement(AreaType.LOOKING, AreaType.DISCARD)
    to_deck = movement(AreaType.HAND, AreaType.DECK)
    looked = movement(AreaType.DECK, AreaType.LOOKING)
    declined = movement(AreaType.LOOKING, AreaType.DECK)
    recovered = movement(AreaType.DISCARD, AreaType.HAND)
    from_prize = movement(AreaType.PRIZE, AreaType.HAND)

    arrivals = sorted((o, t) for o, t, e in evs if _hand_arrival(e))
    # Every way a copy can leave our hand, tagged with the fate it earns.
    exits = sorted([(o, t, JUGADA) for o, t in played]
                   + [(o, t, ADJUNTADA) for o, t in attached]
                   + [(o, t, EVOLUCIONO) for o, t in evolved]
                   + [(o, t, PUESTA_EN_JUEGO) for o, t in into_play]
                   + [(o, t, FORRAJE) for o, t in fodder]
                   + [(o, t, DESCARTADA_EN_REVELADO) for o, t in revealed_away]
                   + [(o, t, DEVUELTA_AL_MAZO) for o, t in to_deck])
    spent = sorted(played + attached + evolved + into_play)

    if terminal == AreaType.HAND:
        fate = MUERTA_EN_MANO       # it is in our hand: nothing earlier overrides that
    elif exits:
        fate = exits[-1][2]         # the LAST way it left, not the first
    elif looked and declined:
        fate = MIRADA_Y_RECHAZADA
    elif from_prize:
        fate = PREMIO_TOMADO
    else:
        fate = OTRO

    # Turns spent sitting in hand, summed over every stay: a copy can arrive,
    # leave and arrive again, and the total wait is what the tempo column reads.
    held = 0
    for order, turn in arrivals:
        away = [t for o, t, _ in exits if o > order]
        held += max(0, (min(away) if away else last_turn) - turn)

    return {
        "serial": serial, "card_id": card_id, "fate": fate,
        "robada": 1 if arrivals else 0,
        "veces_jugada": len(played),
        "veces_mirada": len(looked),
        "veces_rechazada": len(declined),
        "veces_recuperada": len(recovered),
        "de_premio": 1 if from_prize else 0,
        "turno_primer_juego": spent[0][1] if spent else None,
        "turno_primera_vista": arrivals[0][1] if arrivals else None,
        "turnos_en_mano": held,
        "zona_final": int(terminal) if terminal is not None else None,
    }


# ---------------------------------------------------------------------------
# Adapter: a recorded replay (Track R, and B1's validation set)
# ---------------------------------------------------------------------------

def our_seat_of(data) -> int:
    """The seat WE played, by vote against deck.csv. Reuses the golden corpus's
    rule, because getting this wrong censuses the OPPONENT's deck in silence."""
    from golden_corpus import our_index
    return our_index(data)


def observations_of_episode(data, seat):
    """The observations our seat was handed, in order, plus the last one seen.

    An observation counts as handed to us when the seat is ACTIVE and has a menu
    (`select`) -- one decision, one observation -- or when the game is already
    resolved in it. Anything else is the stale copy an INACTIVE seat carries.
    """
    handed, last = [], None
    for step in data.get("steps", []):
        for item in step:
            obs = item.get("observation") or {}
            current = obs.get("current") or {}
            if current.get("yourIndex") != seat:
                continue
            resolved = current.get("result", -1) != -1
            if (item.get("status") == "ACTIVE" and obs.get("select")) or resolved:
                handed.append(obs)
            if current:
                last = obs
    return handed, last


def census_of_episode(path, deck_ids, *, label=None, won=None):
    """One recorded game -> its 60 rows. This is the whole of Track R's reader."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    seat = our_seat_of(data)
    handed, last = observations_of_episode(data, seat)
    if last is None:
        raise ValueError(f"{path}: no observation of seat {seat}")
    if won is None:
        rewards = data.get("rewards") or []
        if len(rewards) == 2 and rewards[seat] is not None and rewards[1 - seat] is not None:
            won = rewards[seat] > rewards[1 - seat]
    rows, diag = resolve_game(
        events_received(handed, seat), seat, zones_of(last, seat), deck_ids,
        last_turn=(last.get("current") or {}).get("turn", 0),
        prizes_hidden=unrevealed_prizes(last, seat))
    return {"rows": rows, "diag": diag, "won": won,
            "opponent": label or _opponent_name(data, seat),
            "episode": Path(path).stem, "seat": seat}


def opponent_cards(data, seat):
    """{serial: card_id} of every OPPOSING card this episode ever revealed.

    Their deck is hidden, so this is a PARTIAL list by construction -- which is
    also why the census covers our 60 only. It is read from two places at once:
    the events of their seat that carry a `cardId`, and their visible zones in
    every observation. Either alone misses cards the other sees.
    """
    them = 1 - seat
    cards: dict[int, int] = {}

    def note(card):
        if card and card.get("serial") is not None and card.get("id") is not None:
            if card.get("playerIndex") in (None, them):
                cards.setdefault(card["serial"], card["id"])

    for step in data.get("steps", []):
        for item in step:
            obs = item.get("observation") or {}
            current = obs.get("current") or {}
            if current.get("yourIndex") != seat:
                continue
            for event in (obs.get("logs") or []):
                if (event.get("playerIndex") == them
                        and event.get("serial") is not None
                        and event.get("cardId") is not None):
                    cards.setdefault(event["serial"], event["cardId"])
            player = (current.get("players") or [None, None])[them]
            if not player:
                continue
            for card in ((player.get("discard") or []) + (player.get("hand") or [])):
                note(card)
            for body in ((player.get("active") or []) + (player.get("bench") or [])):
                if not body:
                    continue
                note(body)
                for card in ((body.get("energyCards") or []) + (body.get("tools") or [])
                             + (body.get("preEvolution") or [])):
                    note(card)
            stadium = current.get("stadium")
            if isinstance(stadium, dict) and stadium.get("playerIndex") == them:
                note(stadium)
    return cards


def load_corpus(directory):
    """[(archetype, stem, [60 ids])] for every real list in the corpus folder."""
    import matchup_matrix as mm
    labels = load_archetypes(directory)
    out = []
    for path in sorted(Path(directory).glob("*.csv")):
        if not mm.is_deck(path):
            continue
        ids = [int(x) for x in path.read_text(encoding="utf-8-sig").split() if x.strip()]
        out.append((labels.get(path.stem, path.stem), path.stem, ids))
    return out


def label_opponent(cards, corpus, *, floor=0.80):
    """Which archetype the opponent was playing, or `desconocido`.

    The plan asked for `real_opponents.overlap_with`, which counts the cards two
    lists share WITH COPIES -- the right measure for two complete 60-card lists.
    Here one side is partial: we see only what they played, typically 25 to 45
    cards, so a raw overlap of 40/60 says more about how long the game ran than
    about which list it was. What discriminates is the other direction, the share
    of what we DID see that the candidate list can account for.

    Below `floor` the answer is `desconocido`, never the nearest archetype: a
    forced label would put a stranger's cards inside an archetype's column and
    the V2 table would report it as fact.
    """
    seen = Counter(cards.values())
    total = sum(seen.values())
    if not total:
        return "desconocido", 0.0
    best, score = "desconocido", 0.0
    for archetype, _stem, ids in corpus:
        ref = Counter(ids)
        covered = sum(min(n, ref[cid]) for cid, n in seen.items()) / total
        if covered > score:
            best, score = archetype, covered
    return (best if score >= floor else "desconocido"), score


def verify_our_list(games, deck_ids):
    """Do these games really play OUR sixty cards? {finding: detail}.

    Two submissions are two agents and possibly two decks, and pooling them
    silently averages different lists. A copy count above what `deck.csv` holds
    proves a different list; cards never seen across many games are only a hint,
    so they are reported apart and never as proof.
    """
    seen = Counter()
    for game in games:
        per_game = Counter()
        for row in game.get("rows", []):
            if row["serial"] is not None:
                per_game[row["card_id"]] += 1
        for cid, n in per_game.items():
            seen[cid] = max(seen[cid], n)
    deck = Counter(deck_ids)
    return {
        "de_mas": {cid: n - deck[cid] for cid, n in seen.items() if n > deck[cid]},
        "nunca_vistas": {cid: deck[cid] for cid in deck if cid not in seen},
    }


def _opponent_name(data, seat):
    """The opposing team's name, or `desconocido`.

    Kaggle sometimes stores the name unrendered -- episode 92484395 carries the
    literal `{{ team_name }}` -- and a template is not a label. It is reported as
    unknown rather than folded into a group, because §4.3's rule is that an
    unmatched opponent is never forced into the nearest archetype.
    """
    names = ((data.get("info") or {}).get("TeamNames") or [])
    if len(names) == 2:
        name = str(names[1 - seat]).strip()
        if name and "{{" not in name:
            return name
    return "desconocido"


# ---------------------------------------------------------------------------
# Adapter: Track S, a simulated game. Drives the battle itself, because
# `selfplay.play_game` returns a summary and the stream is in the observations.
# ---------------------------------------------------------------------------

MAX_STEPS = 3000


def play_and_census(agent_us, agent_them, deck_us, deck_them, *, seat=0,
                    seed=None, lib=None, deck_ids=None, label=None):
    """One simulated game, censused. Same rule for `logs` as the replay reader.

    We collect an observation whenever it is OURS: in process that is exactly
    once per decision we are asked to make, which is the same set the replay
    reader reconstructs.
    """
    from cg.battle import Battle

    if seed is not None and lib is None:
        import local_engine  # a measuring instrument; R11 keeps it out of the agent
        lib = local_engine.load()

    decks = (deck_us, deck_them) if seat == 0 else (deck_them, deck_us)
    agents = {seat: agent_us, 1 - seat: agent_them}
    for mod in (agent_us, agent_them):
        if hasattr(mod, "_init_cards_tracking"):
            import selfplay
            selfplay.reset_agent(mod)

    battle = Battle(list(decks[0]), list(decks[1]), seed=seed, lib=lib)
    obs = battle.obs
    handed, last, steps = [], None, 0
    try:
        while obs and obs["current"]["result"] == -1 and steps < MAX_STEPS:
            if obs["current"]["yourIndex"] == seat:
                handed.append(obs)
                last = obs
            try:
                choice = agents[obs["current"]["yourIndex"]].agent(obs)
                obs = battle.select(choice)
            except Exception as exc:  # one bad game must not void the run
                import traceback
                where = traceback.extract_tb(exc.__traceback__)[-1]
                return {"rows": [],
                        "diag": {"error": f"{type(exc).__name__}: {exc}"[:120]
                                          + f"  [{Path(where.filename).name}:{where.lineno}"
                                            f" {where.name}]"},
                        "won": False, "opponent": label, "seat": seat}
            steps += 1
        if obs and obs["current"]["yourIndex"] == seat:
            handed.append(obs)
            last = obs
        result = obs["current"]["result"] if obs else -1
    finally:
        battle.finish()

    if last is None:
        return {"rows": [], "diag": {"error": "sin observacion propia"},
                "won": False, "opponent": label, "seat": seat}
    rows, diag = resolve_game(
        events_received(handed, seat), seat, zones_of(last, seat),
        deck_ids or read_deck(),
        last_turn=(last.get("current") or {}).get("turn", 0),
        prizes_hidden=unrevealed_prizes(last, seat))
    return {"rows": rows, "diag": diag, "won": result == seat,
            "opponent": label, "seat": seat, "pasos": steps}


# ---------------------------------------------------------------------------
# Aggregation, and the three views
# ---------------------------------------------------------------------------

def aggregate(games):
    """[game census] -> {card_id: metrics}. The denominator is COPY-GAMES.

    Every card holds `copies` slots in the deck and every game fills all sixty,
    so a card with four copies over 100 games has 400 slots. Rates are per slot;
    `conversion` alone is CONDITIONAL on having been drawn, which is the headline
    the plan asked for ("jugada | robada").
    """
    per_card = defaultdict(lambda: {"slots": 0, "robada": 0, "convertida": 0,
                                    "jugada": 0, "muerta": 0, "forraje": 0,
                                    "devuelta": 0, "rechazada": 0, "no_vista": 0,
                                    "otro": 0, "mirada": 0, "de_premio": 0,
                                    "turnos_mano": 0, "primer_juego": []})
    n = 0
    for game in games:
        if not game.get("rows"):
            continue
        n += 1
        for row in game["rows"]:
            acc = per_card[row["card_id"]]
            acc["slots"] += 1
            acc["robada"] += row["robada"]
            acc["mirada"] += row["veces_mirada"]
            acc["rechazada"] += 1 if row["veces_rechazada"] else 0
            acc["de_premio"] += row["de_premio"]
            acc["turnos_mano"] += row["turnos_en_mano"]
            if row["fate"] in CONVERTIDA:
                acc["convertida"] += 1
            if row["fate"] == JUGADA:
                acc["jugada"] += 1
            if row["fate"] == MUERTA_EN_MANO:
                acc["muerta"] += 1
            if row["fate"] == FORRAJE:
                acc["forraje"] += 1
            if row["fate"] == DEVUELTA_AL_MAZO:
                acc["devuelta"] += 1
            if row["fate"] == NO_VISTA:
                acc["no_vista"] += 1
            if row["fate"] == OTRO:
                acc["otro"] += 1
            if row["turno_primer_juego"] is not None:
                acc["primer_juego"].append(row["turno_primer_juego"])
    for acc in per_card.values():
        slots = acc["slots"] or 1
        drawn = acc["robada"] or 1
        acc["copias"] = acc["slots"] / n if n else 0
        acc["tasa_robo"] = acc["robada"] / slots
        acc["tasa_juego"] = acc["convertida"] / slots
        acc["conversion"] = acc["convertida"] / drawn
        acc["tasa_muerte"] = acc["muerta"] / slots
        acc["tasa_forraje"] = acc["forraje"] / slots
        acc["tasa_rechazo"] = acc["rechazada"] / slots
        acc["tasa_no_vista"] = acc["no_vista"] / slots
        acc["turno_medio"] = (sum(acc["primer_juego"]) / len(acc["primer_juego"])
                              if acc["primer_juego"] else None)
        acc["espera_en_mano"] = acc["turnos_mano"] / drawn
    return dict(per_card), n


_COLS = (("copias", "cop", 4, 1, False), ("tasa_robo", "robo", 6, 1, True),
         ("conversion", "conv", 6, 1, True), ("tasa_muerte", "muerta", 7, 1, True),
         ("tasa_forraje", "forraje", 8, 1, True),
         ("tasa_rechazo", "rechazo", 8, 1, True),
         ("tasa_no_vista", "no vista", 9, 1, True))


def print_table(per_card, games, title, *, order="conversion", limit=None):
    names = card_names()
    print(f"\n{title}   ({games} partidas)")
    head = f"  {'carta':28s} {'cop':>4s}"
    head += "".join(f" {label:>{width}s}" for _, label, width, _, _ in _COLS[1:])
    head += f" {'turno':>6s} {'espera':>7s}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    rows = sorted(per_card.items(), key=lambda kv: (kv[1].get(order) or 0.0))
    if limit:
        rows = rows[:limit]
    for card_id, acc in rows:
        line = f"  {names.get(card_id, str(card_id))[:28]:28s} {acc['copias']:4.1f}"
        for key, _, width, dec, pct in _COLS[1:]:
            value = acc.get(key)
            line += f" {100 * value:>{width}.{dec}f}" if pct else f" {value:>{width}.{dec}f}"
        turn = acc.get("turno_medio")
        line += f" {turn:6.1f}" if turn is not None else f" {'-':>6s}"
        line += f" {acc['espera_en_mano']:7.2f}"
        print(line)


def turns_of(game):
    """How long the game ran, as our seat last saw it."""
    return (game.get("diag") or {}).get("turnos") or 0


def length_matched(won, lost):
    """One winning game per loss, OF THE SAME LENGTH. The honest control group.

    WITHOUT THIS, V3 MEASURES THE CLOCK. Measured on 900 games against
    crustle_wall_1: dead-in-hand came out LOWER in losses for 13 of the 14 cards
    reported, and conversion HIGHER for 11 of them. That is not fourteen findings
    about fourteen cards, it is one fact about the sample -- a lost game runs
    longer, so every card gets more chances to be played and fewer are left
    stranded in hand when it ends.

    Pairing each loss with a win of the same turn count removes the gradient, and
    what survives it is a claim about the CARD. It also costs coverage, so the
    number of losses left unmatched is reported rather than hidden: at the tail of
    the length distribution there is often no win to pair with a very long loss.
    """
    pool = defaultdict(list)
    for game in won:
        pool[turns_of(game)].append(game)
    control, matched, unmatched = [], [], 0
    for game in lost:
        same = pool.get(turns_of(game))
        if same:
            control.append(same.pop())
            matched.append(game)
        else:
            unmatched += 1
    return control, matched, unmatched


def print_diff(won, lost, n_won, n_lost, title, *, key="conversion", limit=14,
               turns=None):
    """V3: `win % · loss % · DIFF`, the format `autopsy.py --census` established.

    A trait frequent in losses cannot be told from a trait simply frequent
    without the control group, so the winning games ARE the control group.
    """
    names = card_names()
    print(f"\n{title}   (ganadas {n_won} · perdidas {n_lost})")
    if turns:
        print(f"  duracion media: {turns[0]:.1f} turnos ganando · {turns[1]:.1f} "
              f"perdiendo   (el sesgo que obliga a emparejar por duracion)")
    if not n_won or not n_lost:
        print("  sin una de las dos mitades no hay grupo de control: no se informa.")
        return
    print(f"  {'carta':28s} {'gana':>6s} {'pierde':>7s} {'DIFF':>7s}   {'metrica: ' + key}")
    print("  " + "-" * 58)
    diffs = []
    for card_id in set(won) | set(lost):
        a = (won.get(card_id) or {}).get(key)
        b = (lost.get(card_id) or {}).get(key)
        if a is None or b is None:
            continue
        diffs.append((b - a, card_id, a, b))
    diffs.sort()
    edge = diffs[:limit // 2] + diffs[-(limit // 2):] if len(diffs) > limit else diffs
    for delta, card_id, a, b in edge:
        print(f"  {names.get(card_id, str(card_id))[:28]:28s} {100*a:6.1f} {100*b:7.1f} "
              f"{100*delta:+7.1f}")


def print_diagnostics(games):
    """The honesty block. Every table above is only as good as these numbers."""
    played = [g for g in games if g.get("rows")]
    errors = [g for g in games if not g.get("rows")]
    otro = sum(g["diag"].get("otro", 0) for g in played)
    surplus = sum(g["diag"].get("sobrantes", 0) for g in played)
    bad_size = [g for g in played if g["diag"]["filas"] != DECK_SIZE]
    hidden = sum(g["diag"].get("premios_ocultos", 0) for g in played)
    deal = sum(g["diag"].get("reparto_premios", 0) for g in played)
    rifled = sum(g["diag"].get("mano_revelada", 0) for g in played)
    other_fd = sum(g["diag"].get("cara_abajo", 0) for g in played) - deal - rifled
    n = max(1, len(played))
    revealed_away = sum(1 for g in played for r in g["rows"]
                        if r["fate"] == DESCARTADA_EN_REVELADO)
    print(f"\nDIAGNOSTICO ({len(played)} partidas censadas"
          + (f", {len(errors)} sin censar" if errors else "") + ")")
    print(f"  filas != 60 (especificidad)      {len(bad_size)}")
    print(f"  fate OTRO (alarma del resolutor) {otro}")
    print(f"  copias de mas que el mazo        {surplus}")
    print(f"  premios sin revelar al final     {hidden}"
          f"   ({hidden / n:.2f} por partida de {PRIZES};"
          f" el NO_VISTA los incluye)")
    print("  ciego, por transicion cara abajo (sin cardId):")
    print(f"    reparto de premios DECK->PRIZE {deal}   ({deal / n:.2f} por partida,"
          f" constante conocida)")
    print(f"    mano revelada HAND->LOOKING    {rifled}   ({rifled / n:.2f} por"
          f" partida; es el rival hurgandonos la mano)")
    if other_fd:
        print(f"    OTRAS transiciones ciegas      {other_fd}   <-- sin explicar")
    print(f"  descartadas en revelado          {revealed_away}"
          f"   ({100 * revealed_away / (n * DECK_SIZE):.3f}% de las copias:"
          " se fueron sin que se vea quien las tiro)")
    if bad_size or otro or surplus or other_fd:
        print("  ATENCION: el resolutor tiene un fallo; las tablas de arriba no valen.")
    if errors:
        # An agent that raises loses the game, and `selfplay.play_game` turns the
        # exception into `error_pX` -- a loss like any other. Counting them here
        # by cause and by matchup is how a crash stops hiding inside a winrate.
        print(f"  PARTIDAS QUE REVENTARON AL AGENTE: {len(errors)}"
              f" ({100 * len(errors) / max(1, len(errors) + len(played)):.2f}%)")
        for cause, n in Counter(g["diag"].get("error") for g in errors).most_common(5):
            rivals = Counter(g.get("opponent") for g in errors
                             if g["diag"].get("error") == cause)
            top = ", ".join(f"{r} x{c}" for r, c in rivals.most_common(4))
            print(f"    {n:4d}  {cause}")
            print(f"          rivales: {top}")


def write_rows(path, games):
    """The raw rows, so a view can be recomputed without replaying anything."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["partida", "rival", "ganada", "serial", "card_id", "carta", "fate",
              "robada", "veces_jugada", "veces_mirada", "veces_rechazada",
              "veces_recuperada", "de_premio", "turno_primer_juego",
              "turno_primera_vista", "turnos_en_mano", "zona_final"]
    names = card_names()
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for i, game in enumerate(games):
            for row in game.get("rows", []):
                writer.writerow({"partida": game.get("episode", i),
                                 "rival": game.get("opponent"),
                                 "ganada": int(bool(game.get("won"))),
                                 "carta": names.get(row["card_id"], ""), **row})
    return path


# ---------------------------------------------------------------------------
# Track S driver
# ---------------------------------------------------------------------------

def _census_job(job):
    """One simulated game in a worker. Mirrors `parallel._play_job`'s contract."""
    import parallel as par
    i, label, seat, deck_them, seed = job
    try:
        game = play_and_census(par._W["cand"], par._W["base"], read_deck(),
                               deck_them, seat=seat, seed=seed, label=label)
    except Exception as exc:
        game = {"rows": [], "diag": {"error": f"{type(exc).__name__}: {exc}"[:160]},
                "won": False, "opponent": label, "seat": seat}
    return i, game


def run_track_s(matchups, jobs_n=None, seeds=None, progress=500, first_choice="first"):
    """Simulated games over `matchups` = [(label, deck_path, games)].

    Reuses `utils/parallel.py`'s worker setup (its specs, its `fork` pool, its
    one-worker-drains-many-jobs shape) and only swaps the job body, because what
    a census needs from a game is the observation stream, not the summary.
    """
    import parallel as par
    import selfplay as sp

    jobs = []
    for label, path, games in matchups:
        deck_them = sp.read_deck(path) if path else read_deck()
        for i in range(games):
            seed = None if seeds is None else seeds[i % len(seeds)]
            # Seat alternates by index WITHIN the matchup, as the matrix does.
            jobs.append((len(jobs), label, i % 2, deck_them, seed))

    cand = par.spec_file(_ROOT / "main.py")
    base = par.spec_bot(first_choice)
    jobs_n = jobs_n or par.default_jobs()
    out = []
    if jobs_n <= 1:
        par._init_worker(cand, base)
        for job in jobs:
            out.append(_census_job(job))
            if progress and len(out) % progress == 0:
                print(f"  ... {len(out)}/{len(jobs)}", flush=True)
    else:
        import multiprocessing as mp
        ctx = mp.get_context("fork")
        chunk = max(1, len(jobs) // (jobs_n * 4))
        with ctx.Pool(jobs_n, initializer=par._init_worker,
                      initargs=(cand, base)) as pool:
            for r in pool.imap_unordered(_census_job, jobs, chunksize=chunk):
                out.append(r)
                if progress and len(out) % progress == 0:
                    print(f"  ... {len(out)}/{len(jobs)}", flush=True)
    out.sort(key=lambda t: t[0])
    return [game for _, game in out]


def load_archetypes(directory):
    """{deck stem: archetype label} from the corpus's own pesos.csv."""
    path = Path(directory) / "pesos.csv"
    if not path.is_file():
        return {}
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = str(row.get("archivo", ""))
            if name.endswith(".csv"):
                name = name[:-4]
            out[name] = str(row.get("arquetipo") or name)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _v3(games, label):
    """V3 for one slice: the raw split first, then the length-matched one.

    Both are printed on purpose. The raw split is what the plan asked for and it
    is the one that looks impressive; the matched split is the one that is true.
    Printing only the second would hide how big the clock's contribution was, and
    printing only the first is how a census of this shape fools itself.
    """
    won = [g for g in games if g.get("rows") and g.get("won")]
    lost = [g for g in games if g.get("rows") and not g.get("won")]
    if not won or not lost:
        print(f"\nV3 · {label}: ganadas {len(won)} · perdidas {len(lost)} — "
              "sin las dos mitades no hay grupo de control: no se informa.")
        return
    turns = (sum(map(turns_of, won)) / len(won), sum(map(turns_of, lost)) / len(lost))
    a, na = aggregate(won)
    b, nb = aggregate(lost)
    print_diff(a, b, na, nb, f"V3 · {label} — conversion, SIN emparejar (sesgada "
               "por la duracion)", turns=turns)

    control, matched, unmatched = length_matched(won, lost)
    if not control:
        print("  no hay ninguna victoria de la misma duracion: sin control "
              "emparejado no se informa.")
        return
    ca, nca = aggregate(control)
    cb, ncb = aggregate(matched)
    tag = (f"V3 · {label} — EMPAREJADA por duracion"
           + (f" ({unmatched} derrotas sin pareja)" if unmatched else ""))
    print_diff(ca, cb, nca, ncb, f"{tag} — conversion",
               turns=(sum(map(turns_of, control)) / len(control),
                      sum(map(turns_of, matched)) / len(matched)))
    print_diff(ca, cb, nca, ncb, f"{tag} — muerta en mano", key="tasa_muerte")
    print_diff(ca, cb, nca, ncb, f"{tag} — forraje", key="tasa_forraje")


def _views(games, by_archetype, *, min_losses=60, top=None):
    per_card, n = aggregate(games)
    print_table(per_card, n, "V1 · AGRUPADO — las que menos convierten primero",
                limit=top)

    if by_archetype:
        groups = defaultdict(list)
        for game in games:
            groups[game.get("opponent") or "desconocido"].append(game)
        for label in sorted(groups, key=lambda k: -len(groups[k])):
            sub, m = aggregate(groups[label])
            if m:
                print_table(sub, m, f"V2 · vs {label}", limit=top or 12)

    _v3(games, "AGRUPADO")

    if by_archetype:
        groups = defaultdict(list)
        for game in games:
            groups[game.get("opponent") or "desconocido"].append(game)
        for label in sorted(groups, key=lambda k: -len(groups[k])):
            sub_lost = [g for g in groups[label] if g.get("rows") and not g.get("won")]
            if len(sub_lost) < min_losses:
                print(f"\nV3 · vs {label}: {len(sub_lost)} derrotas, por debajo de "
                      f"{min_losses}. Una columna de derrota sobre esa muestra es "
                      f"decoracion: no se informa.")
                continue
            _v3(groups[label], f"vs {label}")

    print_diagnostics(games)
    return per_card


def read_rows(path):
    """A raw-rows CSV back into games, so a view costs no games to recompute."""
    games = defaultdict(lambda: {"rows": [], "diag": {}, "won": False,
                                 "opponent": None})
    with Path(path).open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row["partida"], row["rival"])
            game = games[key]
            game["won"] = row["ganada"] == "1"
            game["opponent"] = row["rival"]
            game["episode"] = row["partida"]
            game["rows"].append({
                "serial": int(row["serial"]) if row["serial"] else None,
                "card_id": int(row["card_id"]), "fate": row["fate"],
                "robada": int(row["robada"]),
                "veces_jugada": int(row["veces_jugada"]),
                "veces_mirada": int(row["veces_mirada"]),
                "veces_rechazada": int(row["veces_rechazada"]),
                "veces_recuperada": int(row["veces_recuperada"]),
                "de_premio": int(row["de_premio"]),
                "turno_primer_juego": (int(row["turno_primer_juego"])
                                       if row["turno_primer_juego"] else None),
                "turno_primera_vista": (int(row["turno_primera_vista"])
                                        if row["turno_primera_vista"] else None),
                "turnos_en_mano": int(row["turnos_en_mano"]),
                "zona_final": int(row["zona_final"]) if row["zona_final"] else None,
            })
    return list(games.values())


def print_cross_check(sim, real, *, key="conversion", limit=None):
    """B7: do the simulated games and the real ones agree on which cards are dead?

    THE BLOCK THAT MAKES THIS MORE THAN BOOKKEEPING. Every simulated number in
    this repository is measured against the generic bot, and the winrate against
    it is saturated. If the two censuses disagree about which cards never get
    played, then the bot has been shaping the list and no simulated table
    describes how the sixty cards really behave.

    Agreement is read as the RANKING, not the level: real games are shorter,
    harder and fewer, so every rate moves. What has to survive is the order --
    the cards that convert worst in one must be the cards that convert worst in
    the other.
    """
    names = card_names()
    a, na = aggregate(sim)
    b, nb = aggregate(real)
    shared = sorted(set(a) & set(b), key=lambda c: a[c][key])
    if limit:
        shared = shared[:limit]
    print(f"\nB7 · CRUCE simulado ({na} partidas) vs real ({nb} partidas) — {key}")
    print(f"  {'carta':28s} {'simul':>6s} {'real':>6s} {'DIFF':>7s} {'puesto':>8s}")
    print("  " + "-" * 60)
    rank_a = {c: i for i, c in enumerate(sorted(a, key=lambda c: a[c][key]))}
    rank_b = {c: i for i, c in enumerate(sorted(b, key=lambda c: b[c][key]))}
    for card_id in shared:
        move = rank_b[card_id] - rank_a[card_id]
        print(f"  {names.get(card_id, str(card_id))[:28]:28s} "
              f"{100 * a[card_id][key]:6.1f} {100 * b[card_id][key]:6.1f} "
              f"{100 * (b[card_id][key] - a[card_id][key]):+7.1f} {move:+8d}")
    # Spearman on the shared cards: one number for "is it the same ranking".
    n = len(rank_a)
    common = set(a) & set(b)
    if len(common) > 2:
        d2 = sum((rank_a[c] - rank_b[c]) ** 2 for c in common)
        m = len(common)
        rho = 1 - 6 * d2 / (m * (m * m - 1))
        print(f"\n  correlacion de rangos (Spearman) sobre {m} cartas: {rho:+.3f}")
        print("  " + ("los dos censos ordenan la lista igual: el bot generico NO "
                      "esta deformando que cartas mueren." if rho >= 0.7 else
                      "ORDENAN DISTINTO: ninguna tabla simulada describe la lista "
                      "real, y ese hallazgo pesa mas que cualquier carta suelta."))
    return rho if len(common) > 2 else None


def _episode_paths(targets):
    paths = []
    for target in targets:
        p = Path(target)
        if p.is_dir():
            paths += sorted(p.glob("*.json")) + sorted(p.glob("episode-*-replay.json"))
        elif p.is_file():
            paths.append(p)
        else:
            print(f"AVISO: no existe {target}", file=sys.stderr)
    return sorted(set(paths))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episodes", nargs="+", default=None,
                    help="Recorded replays (Track R): files or folders.")
    ap.add_argument("--only-submission", default=None,
                    help="Census ONE submission's games (two submissions can be "
                         "two different 60-card lists).")
    ap.add_argument("--our-deck", default=None, metavar="CSV",
                    help="The list the games were played with (default deck.csv). "
                         "A REPLAY is a game of the list of its day: censusing an "
                         "August 13th episode against today's sixty invents rows "
                         "for copies that list never held, and the fates stop "
                         "closing on 60. Simulated games always play deck.csv.")
    ap.add_argument("--games", type=int, default=0, help="Simulated games (Track S).")
    ap.add_argument("--opponent", default=None, help="One opposing deck CSV.")
    ap.add_argument("--opponents", default=None, help="A corpus folder of deck CSVs.")
    ap.add_argument("--allocation", choices=("uniforme", "peso"), default="uniforme",
                    help="'peso' keeps the same TOTAL and splits it by meta share.")
    ap.add_argument("--only", default=None, help="Comma-separated deck stems.")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--seeds", default=None, help="'500' or '3,7,11'.")
    ap.add_argument("--out", default=None, help="CSV of the raw rows.")
    ap.add_argument("--top", type=int, default=None, help="Rows per table.")
    ap.add_argument("--min-losses", type=int, default=60,
                    help="Below this, V3 per archetype is not reported.")
    ap.add_argument("--no-archetypes", action="store_true", help="V1 and pooled V3 only.")
    ap.add_argument("--compare", nargs=2, metavar=("SIMULADO", "REAL"),
                    help="B7: cross-check two raw-rows CSVs against each other.")
    args = ap.parse_args(argv)

    if args.compare:
        sim, real = (read_rows(p) for p in args.compare)
        print(f"Simulado: {args.compare[0]}   Real: {args.compare[1]}")
        for key in ("conversion", "tasa_muerte", "tasa_robo"):
            print_cross_check(sim, real, key=key)
        return 0

    deck_ids = read_deck(args.our_deck)
    games = []

    if args.episodes:
        import re
        paths = _episode_paths(args.episodes)
        if not paths:
            print("No hay ninguna repeticion que leer.", file=sys.stderr)
            return 1
        # The downloader's index.csv already labels result and opponent.
        index = {}
        for folder in {p.parent for p in paths}:
            idx = folder / "index.csv"
            if idx.is_file():
                with idx.open(encoding="utf-8-sig", newline="") as fh:
                    for row in csv.DictReader(fh):
                        index[str(row.get("episode_id"))] = row
        corpus = load_corpus(args.opponents) if args.opponents else []
        if args.opponents:
            print(f"Etiquetando rivales contra {len(corpus)} listas reales de "
                  f"{args.opponents}")
        print(f"Leyendo {len(paths)} repeticiones...")
        scores, submissions = [], defaultdict(list)
        for path in paths:
            eid = (m.group(1) if (m := re.search(r"(\d+)", path.stem)) else path.stem)
            meta = index.get(eid) or {}
            outcome = str(meta.get("resultado") or "")
            won = {"victoria": True, "derrota": False}.get(outcome)
            if outcome == "empate":
                continue  # a draw belongs to neither half of V3
            try:
                census = census_of_episode(path, deck_ids, won=won)
            except Exception as exc:
                print(f"  {path.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            if corpus:
                data = json.loads(path.read_text(encoding="utf-8"))
                label, score = label_opponent(
                    opponent_cards(data, census["seat"]), corpus)
                census["opponent"] = label
                scores.append((score, label, path.stem))
            census["submission"] = str(meta.get("submission_id") or "?")
            if args.only_submission and census["submission"] != args.only_submission:
                continue
            submissions[census["submission"]].append(census)
            games.append(census)

        if index:
            print(f"  {len(index)} filas de index.csv con el resultado etiquetado "
                  "en origen")
        if scores:
            unknown = sum(1 for s, label, _ in scores if label == "desconocido")
            print(f"  rivales etiquetados: {len(scores) - unknown}/{len(scores)} "
                  f"(cobertura media {100 * sum(s for s, _, _ in scores) / len(scores):.0f}%,"
                  f" {unknown} desconocidos)")

        # §4.2: two submissions are two agents and possibly two decks.
        names = card_names()
        for sub in sorted(submissions):
            found = verify_our_list(submissions[sub], deck_ids)
            note = ""
            if found["de_mas"]:
                note = ("  LISTA DISTINTA: " + ", ".join(
                    f"{names.get(c, c)} +{n}" for c, n in found["de_mas"].items()))
            elif found["nunca_vistas"]:
                note = ("  nunca vistas: " + ", ".join(
                    names.get(c, str(c)) for c in found["nunca_vistas"]))
            print(f"  submission {sub}: {len(submissions[sub])} partidas{note}")
        if len(submissions) > 1 and any(
                verify_our_list(v, deck_ids)["de_mas"] for v in submissions.values()):
            print("  ATENCION: alguna submission NO juega deck.csv. No se agrupan "
                  "dos mazos en un censo: usa --only-submission.")

    if args.games:
        import matchup_matrix as mm
        import selfplay as sp
        seeds = sp.parse_seeds(args.seeds)
        if args.opponents:
            folder = Path(args.opponents)
            paths = [p for p in sorted(folder.glob("*.csv")) if mm.is_deck(p)]
            if args.only:
                keep = {s.strip() for s in args.only.split(",") if s.strip()}
                paths = [p for p in paths if p.stem in keep]
            weights = mm.load_weights(folder)
            if args.allocation == "peso" and not weights:
                print(f"ERROR: no hay pesos.csv en {folder}", file=sys.stderr)
                return 2
            share = mm.allocate(paths, args.games, weights, args.allocation)
            labels = load_archetypes(folder)
            matchups = [(labels.get(p.stem, p.stem), p, share[p.stem])
                        for p in paths if share.get(p.stem)]
        elif args.opponent:
            path = Path(args.opponent)
            matchups = [(path.stem, path, args.games)]
        else:
            matchups = [("espejo", None, args.games)]
        total = sum(g for _, _, g in matchups)
        print(f"Track S: {total} partidas sobre {len(matchups)} rivales "
              f"(reparto {args.allocation}, jobs {args.jobs or 'auto'}"
              + (f", semillas {args.seeds}" if seeds else "") + ")")
        games += run_track_s(matchups, jobs_n=args.jobs, seeds=seeds)

    if not games:
        print("Nada que censar: usa --episodes o --games.", file=sys.stderr)
        return 1

    _views(games, not args.no_archetypes, min_losses=args.min_losses, top=args.top)
    if args.out:
        print(f"\nFilas crudas en {write_rows(args.out, games)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
