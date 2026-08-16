"""EVOLUTION LINES: stage, root, chains, and whether a link can be used.

Reasoning about lines -- Applin to Dipplin to Hydrapple ex -- is behind a large
share of the agent's decisions: what to search for, what to recover, what to
discard, what to bench. These are the functions that answer those questions
about any card.

DECK-AGNOSTIC BY CONSTRUCTION. Almost everything here reads the CARD DATABASE
(`evolvesFrom`, the stage flags), not our own `EVO_LINES` table. `_line_root`
walks up the chain link by link; `_evolution_stage` reads the printed stage. So
the same functions describe the OPPONENT's lines as well as ours, which is what
lets the gust and threat rules ask "is this the pre-evolution of something
dangerous" without a hard-coded list per matchup. `_build_deck_chains` is the
exception, and takes the deck as an argument rather than assuming one.

THE USEFUL DISTINCTION: a card being IN HAND is not the same as being PLAYABLE.
An evolution needs a body in play to go on top of; a Basic needs a free bench
seat. The `_evo_copies_usable`, `_line_base_benchable`, `_pokemon_injugable`
and `_evo_link_state` family answers the second question, and it is what stops
searches from buying cards that arrive dead -- the recurring cost of confusing
the two.

`_evo_top_unlocked_by_the_search` is the forward-looking one: what a line could
REACH if the search brought this link, which is how the searchers tell a
missing middle from a dead end.

`_validate_id_constants` is a startup self-check, not logic: it warns on stderr
when a hard-coded id in `ptcg/cards/ids.py` no longer names the card it was
written for -- the failure a card database update would otherwise cause
silently, in the worst possible way.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from cg.api import CardType
from collections import defaultdict
from ptcg.cards.groups import EVO_LINES
from ptcg.cards.ids import DUNSPARCE_IDS, _ID_NAME_EXPECTATIONS
from ptcg.cards.tables import _CARD_BY_NAME, _EVOLUTIONS_BY_NAME, card_table


def _validate_id_constants():
    """Check every hard-coded id still names the card it was written for.

    The agent is full of constants like `Teal_Mask_Ogerpon_ex = 1234`, and if
    the card database ever renumbers, those keep resolving -- to the WRONG
    card. Every rule then silently applies to something else.

    Compares each id against the name it is expected to carry
    (`_ID_NAME_EXPECTATIONS`) and WARNS on stderr rather than raising: a
    mismatch must be visible, but refusing to start would forfeit a live game
    over a cosmetic rename. Returns the mismatches so a test can assert there
    are none.
    """
    mismatches = []
    for _cid, _expected in _ID_NAME_EXPECTATIONS.items():
        if _cid < 0:
            continue
        _cd = card_table.get(_cid)
        _name = getattr(_cd, 'name', None) if _cd is not None else None
        if _name is None or _expected.lower() not in _name.lower():
            mismatches.append((_cid, _expected, _name))
    if mismatches:
        import sys as _sys
        for _cid, _expected, _name in mismatches:
            print(f"[WARN][ID-AUDIT] id={_cid} expected '{_expected}' "
                  f"but card_table says '{_name}'", file=_sys.stderr)
    return mismatches


def _evolution_stage(card_id):
    """Stage of `card_id`: 0 Basic, 1 Stage 1, 2 Stage 2. None if not a Pokemon.

    It comes from the card data (`basic`/`stage1`/`stage2`), not from
    `EVO_LINES`, which describes OUR deck only.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return None
    if getattr(data, 'stage2', False):
        return 2
    if getattr(data, 'stage1', False):
        return 1
    return 0 if getattr(data, 'basic', False) else None


def _line_root(card_id):
    """Name of the BASIC of `card_id`'s evolution chain (None if unknown).

    It walks up `evolvesFrom` until there is no pre-evolution. If an
    intermediate link is not in `card_table`, the last known name is returned:
    enough to compare two cards of the SAME chain.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return None
    name = data.name or None
    vistos = set()
    while data is not None and getattr(data, 'evolvesFrom', None):
        pre = data.evolvesFrom
        if pre in vistos:                # corrupt chain: break the loop
            break
        vistos.add(pre)
        name = pre
        data = _CARD_BY_NAME.get(pre)
    return name


def _same_evolution_line(a_id, b_id):
    """True if the two ids are links of the SAME Basic->S1->S2 chain."""
    if a_id == b_id:
        return True
    raiz = _line_root(a_id)
    return raiz is not None and raiz == _line_root(b_id)


def _is_more_evolved_than(pkmn, otro):
    """True if `pkmn` is a MORE EVOLVED link of the SAME line as `otro`.

    User's rule (registro_008 step 93 vs Cynthia's Garchomp ex, WON with a
    mistake): inside a Basic -> Stage 1 -> Stage 2 line, ALWAYS knock out the
    HIGHEST stage available. It takes the same prizes but destroys more
    development: the opponent has to rebuild both steps before having their
    Stage 2 attacker again. See [[boss-gust-mayor-evolucion-fase2]].
    """
    if pkmn is None or otro is None:
        return False
    e_pkmn = _evolution_stage(getattr(pkmn, 'id', 0))
    e_otro = _evolution_stage(getattr(otro, 'id', 0))
    if e_pkmn is None or e_otro is None or e_pkmn <= e_otro:
        return False
    return _same_evolution_line(getattr(pkmn, 'id', 0), getattr(otro, 'id', 0))


def _line_ends_in_ex(card_id):
    """True if ABOVE `card_id` its chain reaches an ex/megaEx Pokemon.

    Deck-agnostic: it walks down `evolvesFrom` (names, not ids) from the card,
    so it works for ANY Basic -> Stage 1 -> Stage 2 line in the environment
    without hand-listing it in `EX_PREEVO_IDS`. It is the criterion that
    justifies spending a Boss's to cut the line: the final stage is worth 2+
    prizes and is the opposing deck's real attacker.

    It leaves out only the Abra -> Kadabra -> Alakazam line (its final form is
    worth 1 prize in this environment), which is exactly what
    [[boss-no-gustear-preevo-linea-no-ex]] asks for.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return False
    pendientes = [data.name or ""]
    vistos = set()
    while pendientes:
        name = pendientes.pop()
        if not name or name in vistos:
            continue
        vistos.add(name)
        for evo in _EVOLUTIONS_BY_NAME.get(name, ()):
            if getattr(evo, 'ex', False) or getattr(evo, 'megaEx', False):
                return True
            pendientes.append(evo.name or "")
    return False


def _preevo_of_ex_line(card_id):
    """Is `card_id` a link worth GUSTING in order to cut an ex line?

    It replaces the curated list `EX_PREEVO_IDS` (minus
    `NONEX_FINAL_PREEVO_IDS`) wherever the criterion is "the line ends in a
    2-prize attacker": it derives it from the card data, so it covers lines
    nobody listed by hand (e.g. Frillish -> Jellicent ex).

    Guard `DUNSPARCE_IDS`: their line culminates in Dudunsparce ex, but the
    selection handler ALWAYS vetoes them as a gust target. A reason that points
    at a forbidden target makes the agent play (or search for) the Boss's only
    to end up bringing something else up -- the same failure as the Dwebble of
    log 86339758.
    """
    if card_id in DUNSPARCE_IDS:
        return False
    return _line_ends_in_ex(card_id)


def _build_deck_chains(deck_ids):
    """Derives the complete evolution chains from the deck.

    Returns `(evo_by_name, cadenas)`:
      evo_by_name: name of the pre-evolution -> tuple of DECK ids that evolve
                      from it.
      cadenas:        tuple of `(basic_id, stage1_id, stage2_id_or_0)`. The same
                      pre-evolution can have several evolutions (copies from
                      different sets), so one chain is emitted per combination;
                      the consumer chooses.

    Grand Tree searches OUR deck, hence only ids present in `deck_ids` are
    considered.
    """
    ids = set(deck_ids)
    by_name = defaultdict(set)
    for cid in ids:
        data = card_table.get(cid)
        if data is None or data.cardType != CardType.POKEMON:
            continue
        pre = getattr(data, 'evolvesFrom', None)
        if pre:
            by_name[pre].add(cid)
    evo_by_name = {name: tuple(sorted(v)) for name, v in by_name.items()}

    strings = []
    for cid in sorted(ids):
        data = card_table.get(cid)
        if data is None or data.cardType != CardType.POKEMON or not data.basic:
            continue
        for s1 in evo_by_name.get(data.name, ()):
            s1_data = card_table.get(s1)
            if s1_data is None:
                continue
            s2s = evo_by_name.get(s1_data.name, ())
            if s2s:
                for s2 in s2s:
                    strings.append((cid, s1, s2))
            else:
                strings.append((cid, s1, 0))
    return evo_by_name, tuple(strings)


def _evo_link_state(hand_counts, field_counts):
    """Classifies each EVOLUTION of our lines for the Ultra Ball fetch.
    Returns `(necesarios, huerfanos)`:

      orphan   = its PRE-EVOLUTION is neither in play nor in hand: bringing it
                 is a DEAD card, it cannot be played (user, registro_006 step
                 79 vs Marnie, LOST: with an Applin on the bench and NO Dipplin
                 in play or in hand, the Ultra Ball searched for Hydrapple ex --
                 which cannot evolve anything -- instead of the missing Dipplin).
      needed   = a missing INTERMEDIATE link (its pre-evolution is in play, and
                 we have it neither in hand nor in play) that ALSO UNLOCKS the
                 stage 2, which right now is orphaned. It is "the next evolution
                 needed on the bench".

    The stage 2 never enters `necesarios`: when it IS the missing link its own
    branches already score it (Hydrapple ex 980 / Meganium 1000), and those also
    apply the matchup clamps (a dead ex vs Crustle, yielding to the Meowth ex
    refill engine). Raising it here would step on those clamps.

    The CURRENT field is what is looked at (not the start-of-turn snapshot):
    having the link in hand is already progress even if the evolution cannot be
    completed this turn.
    """
    necesarios, huerfanos = set(), set()
    for line in EVO_LINES:
        full_line = field_counts.get(line[-1], 0) >= 1
        faltan = []
        for pre, evo in zip(line, line[1:]):
            if (field_counts.get(pre, 0) == 0
                    and hand_counts.get(pre, 0) == 0):
                huerfanos.add(evo)
            elif (not full_line
                    and field_counts.get(pre, 0) >= 1
                    and field_counts.get(evo, 0) == 0
                    and hand_counts.get(evo, 0) == 0):
                faltan.append(evo)
        # Only the intermediate link whose stage 2 was left orphaned.
        for evo in faltan:
            if evo != line[-1] and line[-1] in huerfanos:
                necesarios.add(evo)
    return necesarios, huerfanos


def _evo_top_unlocked_by_the_search(card_id, hand_counts, field_counts,
                                    deck_counts):
    """Is `card_id` an ORPHANED top of one of our lines whose ONLY missing link
    a Pokemon search can still pull out of the DECK?

    The question a discard cost cannot answer with `field_counts` alone. An
    evolution whose pre-evolution is neither in play nor in hand is an orphan
    (`_evo_link_state`), and every branch that prices such a piece prices it as
    cardboard -- correctly, because nothing on the board can wear it. But when
    the card being PAID FOR is a Pokemon tutor, the board the piece will meet is
    not the board the scorer is looking at: the very card the search brings is
    the link that un-orphans it.

    Both halves are required and both are read off the same board:

      * `card_id` is the TOP of the line and it is an orphan -- with the link
        already in hand or in play there is nothing for the search to supply and
        the ordinary branches already say so;
      * the missing link is `necesario` (its own pre-evolution IS in play, so it
        can be worn the moment it arrives) AND there is still a copy in the
        DECK, which is the only zone a search reaches. THE DISCARD IS NOT A
        SEAT, the same way `_line_base_benchable` refuses to count the deck.

    Deck-agnostic: the stages come from `EVO_LINES` and the classification from
    `_evo_link_state`. `deck_counts` is a plain `{card_id: copies in the deck}`
    so the function stays pure.
    """
    necesarios, huerfanos = _evo_link_state(hand_counts, field_counts)
    if card_id not in huerfanos:
        return False
    for line in EVO_LINES:
        if card_id != line[-1]:
            continue
        for link in line[1:-1]:
            if link in necesarios and deck_counts.get(link, 0) >= 1:
                return True
    return False


# The reading of `_evo_bridge_last_copies` below: the last middle link of a line
# we can still assemble is not fodder for a cost and not the card a forced
# discard lets go. A NAMED SWITCH, like `NZ_MUTE_ROUTING` in `ptcg/calc/damage.py`
# and the `PROMOTE_*` family in main.py -- it is the only difference the census,
# the gate and the rules oracle are allowed to put between their two arms, and
# both of this rule's call sites read it through this one name.
LAST_BRIDGE_IS_NOT_FODDER = True


def _evo_bridge_last_copies(card_id, hand_counts, field_counts,
                            reachable_counts):
    """Are the copies of `card_id` in HAND the last BRIDGE a line we can still
    assemble has left?

    A BRIDGE is a middle link: not the Basic the bench seats, not the top the
    line is played for, but the link the top can only be reached THROUGH. In
    this deck it is the Bayleef between the Chikorita and the Meganium, and the
    Dipplin between the Applin and the Hydrapple ex; the stages come from
    `EVO_LINES`, so a deck whose engine sits on another line gets the same
    answer without editing this file.

    A SEAT CAN BE SEARCHED FOR, A DISCARDED CARD CANNOT. That asymmetry is the
    whole rule. Every other reader of an evolution piece in hand prices it
    against the BOARD -- `_evo_copies_usable` calls a link with no body under it
    zero usable copies, `_line_base_benchable` refuses to count a Basic that is
    only in the deck ("THE DECK IS NOT A SEAT") -- and both are right, because
    the missing seat is a card the deck still holds and a search buys it back.
    The bridge is the other case: once it is in the discard no search reaches
    it, and the top of the line becomes cardboard in every zone at once. So the
    reading "nothing on the board can wear it, therefore it is cheap" is
    correct about the copies the deck can replace and false about the LAST
    ones.

    Four questions, all of them read off the same counts:

      * `card_id` is a middle link of one of our lines (a Basic and a top are
        somebody else's question);
      * it is not already IN PLAY -- with the bridge worn the line is under way
        and the copy in hand is a spare;
      * the copies in HAND are all that is left anywhere a draw or a search
        still reaches, so paying with them is paying with the line;
      * and the line is still worth having: something ABOVE the bridge and
        something BELOW it are still reachable too. A bridge to a top that is
        already in the discard leads nowhere, and one with no Basic left has
        nothing to stand on.

    `reachable_counts` is a plain `{card_id: copies}` of every zone a draw or a
    search still reaches -- deck, hand, play and prizes, i.e. ALL OF THEM
    EXCEPT THE DISCARD -- so the function stays pure and the caller owns the
    belief. A recovery card (Night Stretcher, Lana's Aid) can undo a discard and
    is deliberately NOT modelled here: it costs a whole card and, unlike the
    bridge itself, it is one the search can still buy.

    It answers a question about the CARD, not about a menu: it says the copy is
    load-bearing, and each caller decides what that is worth -- the Ultra Ball's
    cost count refuses to treat it as fodder, the forced-discard scorer keeps
    one copy and lets the surplus fall.
    """
    if not LAST_BRIDGE_IS_NOT_FODDER:
        return False
    for line in EVO_LINES:
        if card_id not in line:
            continue
        idx = line.index(card_id)
        if idx == 0 or idx == len(line) - 1:
            continue                     # a Basic and a top are not bridges
        if (field_counts or {}).get(card_id, 0) >= 1:
            continue                     # already worn: the line is under way
        _in_hand = (hand_counts or {}).get(card_id, 0)
        if _in_hand < 1:
            continue
        if (reachable_counts or {}).get(card_id, 0) > _in_hand:
            continue                     # the deck can still replace them
        if not any((reachable_counts or {}).get(_top, 0) >= 1
                   for _top in line[idx + 1:]):
            continue                     # the bridge leads nowhere
        if not any((reachable_counts or {}).get(_base, 0) >= 1
                   or (field_counts or {}).get(_base, 0) >= 1
                   for _base in line[:idx]):
            continue                     # nothing left to stand on
        return True
    return False


def _pokemon_injugable(card_id, field_counts, bench_count, bench_max):
    """True if bringing `card_id` to hand brings a DEAD card: a Pokemon that
    cannot be put into play today or on the next turn.

    It all comes down to the BENCH slot. With `bench_count < bench_max` nothing
    is dead: any Basic fits, and an orphaned evolution can be completed by
    benching its pre-evolution (the recovery itself brings up to 3 cards). With
    a FULL bench:
      * a BASIC does not fit in any way -> dead;
      * an EVOLUTION only lives if its pre-evolution is IN PLAY (it evolves on
        top of it without taking a bench slot). Having it in HAND is not enough:
        putting it down would need the slot that is not there.

    Deck-agnostic: the stages come from `EVO_LINES` and the type from
    `card_table`. It is not a veto -- whoever uses it must leave the option
    eligible as a LAST resort, because recoveries have `minCount >= 1` and
    sometimes the whole discard is dead cards.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return False
    if bench_count < bench_max:
        return False
    for line in EVO_LINES:
        for pre, evo in zip(line, line[1:]):
            if evo == card_id:
                return field_counts.get(pre, 0) == 0
    return True                          # a Basic with the bench full


def _direct_evolution_ids(card_id):
    """Ids of the cards `card_id` evolves into in ONE step (an empty tuple for a
    final stage or an unknown card).

    One step, not the whole chain: what it answers is "what can this body BE
    NEXT TURN", which is the only thing a defensive projection is entitled to
    assume. The chain-wide question already has its own reader
    (`_line_ends_in_ex`).

    Deck-agnostic and environment-wide: it reads the reverse index of
    `evolvesFrom`, so an opposing Riolu answers Mega Lucario ex without anybody
    having listed that line by hand.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return ()
    name = getattr(data, 'name', None)
    if not name:
        return ()
    return tuple(getattr(evo, 'cardId', 0)
                 for evo in _EVOLUTIONS_BY_NAME.get(name, ())
                 if getattr(evo, 'cardId', 0))


def _line_base_benchable(card_id, hand_counts, free_bench=0):
    """Is the BASIC of `card_id`'s line in HAND, with a bench slot that fits it?

    The companion question to `_evo_copies_usable`, asked by the cost vetoes of
    the Ultra Ball and by the forced-discard scorer: an evolution piece in hand
    is only worth protecting while some body can WEAR it. That body is either
    already on the board (the caller reads `field_counts` for that) or it is the
    line's Basic still in hand waiting for a bench slot.

    THE DECK IS NOT A SEAT. A Basic that only exists in the deck cannot dress
    anything: it has to be drawn or searched for first, and the only searcher in
    hand is usually the very Ultra Ball whose cost we are refusing to pay --
    which makes the protection circular and turns the whole hand into cardboard
    (user, registro_004 step 26 vs Archaludon ex, LOST). Same doctrine as
    `_evo_copies_usable` ("a line protects the seats, not the copies") and as
    `_evo_link_state`, which already calls a piece ORPHANED when its
    pre-evolution is "neither in play nor in hand".

    Deck-agnostic: the stages come from `EVO_LINES`.
    """
    for line in EVO_LINES:
        if card_id == line[0] or card_id not in line:
            continue
        return hand_counts.get(line[0], 0) >= 1 and free_bench >= 1
    return False


def _evo_copies_usable(card_id, hand_counts, field_counts, free_bench=0):
    """How many copies of `card_id` this board could still PUT INTO PLAY.

    An evolution goes ON TOP of a body, so what bounds it is the number of
    distinct LINE INSTANCES underneath it -- not how many pieces the hand holds.
    A Dipplin in hand with one Applin on the bench is ONE future Hydrapple ex,
    not two: that Dipplin will sit on that very Applin. Hence the count is

        bodies in play at a stage BELOW `card_id`
      + basics of the line still in hand that a free bench slot would fit

    Copies beyond that number can never reach the field: they are the cheapest
    thing the hand owns, whatever the line-protection branches say about the
    FIRST copy. Deck-agnostic -- the stages come from `EVO_LINES`.

    Returns None when `card_id` is not an evolution of one of our lines (the
    caller then has nothing to cap).
    """
    for line in EVO_LINES:
        if card_id == line[0] or card_id not in line:
            continue
        idx = line.index(card_id)
        seats = sum(field_counts.get(pre, 0) for pre in line[:idx])
        seats += min(hand_counts.get(line[0], 0), max(0, free_bench))
        return seats
    return None


def _evo_body_in_play(card_id, field_counts):
    """Is there a body in `field_counts` that `card_id` evolves DIRECTLY from?

    The door an evolution enters play by. A Basic needs a free bench SEAT
    (`_ub_target_has_no_seat` asks that half); an evolution needs the body of
    its immediately lower stage already on the board, and it is placed on top
    of it. This answers the second half, and it answers it about ONE step: a
    Meganium does not sit on a Chikorita, it sits on a Bayleef.

    Whatever `field_counts` the caller passes is the definition of "on the
    board" this function uses. That is deliberate: pass the CURRENT field and
    the answer is "could it ever be worn"; pass the start-of-turn snapshot
    (`_ub_evolvable`) and the answer becomes "could it be worn THIS TURN",
    because a body that came down this turn cannot be evolved.

    Deck-agnostic: the pre-evolution is read off the card data (`evolvesFrom`,
    which stores a NAME) and every id in `field_counts` is resolved back to its
    name, so two printings of the same Pokemon -- different ids, same name --
    both count as a seat. Returns False for a Basic and for anything that is
    not a Pokemon: neither has a body to sit on.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return False
    pre = getattr(data, 'evolvesFrom', None)
    if not pre:
        return False
    for cid, n in (field_counts or {}).items():
        if not n:
            continue
        cd = card_table.get(cid)
        if cd is not None and getattr(cd, 'name', None) == pre:
            return True
    return False


def _line_in_play_from(card_id, field_counts):
    """Is any body of `card_id`'s chain, from `card_id` UP, already on the board?

    The guard every "line from scratch" rung needs and each one used to spell
    out by hand (`field.get(Applin) + field.get(Dipplin) + field.get(Hydrapple_ex)
    == 0`). Written once, and read off the card data instead of a per-deck sum,
    so a deck with a line nobody enumerated gets the same guard.

    WHY FROM `card_id` UP AND NOT THE WHOLE CHAIN: what it answers is "would
    buying this Basic be starting the line, or doubling it". A body already
    standing anywhere at or above the candidate means the evolution pieces in
    hand have a seat WITHOUT the search, so the search would be buying a second
    copy -- development, not the turn.

    Matching is by NAME, like `_evo_body_in_play`: two printings of the same
    Pokemon carry different ids and are the same body on the board.
    """
    names, seen = set(), set()
    stack = [card_id]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        data = card_table.get(cur)
        name = getattr(data, 'name', None) if data is not None else None
        if name:
            names.add(name)
        stack.extend(_direct_evolution_ids(cur))
    for cid, n in (field_counts or {}).items():
        if not n:
            continue
        cd = card_table.get(cid)
        if cd is not None and getattr(cd, 'name', None) in names:
            return True
    return False


def _line_climb_from_hand(card_id, hand_counts):
    """How far up its own chain the HAND alone could carry `card_id` the moment
    it reaches the board: `(steps, top_id)`, `(0, card_id)` when it carries it
    nowhere.

    THE MIRROR IMAGE OF `_evo_body_in_play`. That one asks what a card in hand
    can be worn BY; this one asks what a body can be dressed IN. Both are needed
    to price a search, and until August 2026 only the first one was: every
    "rush" rung in the package tests `field.get(<the Basic>) >= 1` -- the seat
    must already be on the board -- and none of them asks the same question of a
    seat the search itself is about to buy out of the DECK.

    It matters only where a card lifts the "a body played this turn cannot
    evolve" veto (Forest of Vitality here), and there it is the whole play: the
    hand holding the Stage 1 and the Stage 2 of a line whose Basic is still in
    the deck is one search away from that Stage 2 TODAY, and a `steps == 2`
    answer is exactly that sentence. THE CALLER OWNS THE STADIUM QUESTION --
    this function knows nothing about turns or vetoes, it only reads the chain.

    Deck-agnostic and environment-wide: the links come from `_direct_evolution_ids`
    (the reverse index of `evolvesFrom`), never from `EVO_LINES`, so a deck built
    on another line -- or an opposing one -- is read by the same code. A branching
    chain (two printings of the same Stage 1) takes the branch that climbs
    HIGHEST, ties broken by id so the answer never depends on dict order, and
    every step consumes its copy from the hand, so a chain that loops or a hand
    that holds one card twice cannot spin.
    """
    best = (0, card_id)
    for evo in sorted(_direct_evolution_ids(card_id)):
        if hand_counts.get(evo, 0) < 1:
            continue
        rest = dict(hand_counts)
        rest[evo] -= 1
        steps, top = _line_climb_from_hand(evo, rest)
        if steps + 1 > best[0]:
            best = (steps + 1, top)
    return best


__all__ = [
    'LAST_BRIDGE_IS_NOT_FODDER',
    '_direct_evolution_ids',
    '_evo_body_in_play',
    '_line_climb_from_hand',
    '_line_in_play_from',
    '_evo_bridge_last_copies',
    '_evo_copies_usable',
    '_evo_top_unlocked_by_the_search',
    '_line_base_benchable',
    '_evolution_stage',
    '_line_root',
    '_same_evolution_line',
    '_is_more_evolved_than',
    '_line_ends_in_ex',
    '_preevo_of_ex_line',
    '_build_deck_chains',
    '_evo_link_state',
    '_pokemon_injugable',
    '_validate_id_constants',
]
