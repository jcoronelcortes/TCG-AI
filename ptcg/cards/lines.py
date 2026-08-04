"""Evolution lines: stage, root, deck chains and missing links.

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
            print(f"[WARN][ID-AUDIT] id={_cid} esperaba '{_expected}' "
                  f"pero card_table dice '{_name}'", file=_sys.stderr)
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

    cadenas = []
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
                    cadenas.append((cid, s1, s2))
            else:
                cadenas.append((cid, s1, 0))
    return evo_by_name, tuple(cadenas)


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


def _validate_id_constants():
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
            print(f"[WARN][ID-AUDIT] id={_cid} esperaba '{_expected}' "
                  f"pero card_table dice '{_name}'", file=_sys.stderr)
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

    cadenas = []
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
                    cadenas.append((cid, s1, s2))
            else:
                cadenas.append((cid, s1, 0))
    return evo_by_name, tuple(cadenas)


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

__all__ = [
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
