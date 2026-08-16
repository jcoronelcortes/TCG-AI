"""BOSS'S ORDERS: drag one of their benched Pokemon into the active spot.

The most decisive Supporter in the deck and the one with the most written
rules, because "gust" is really two questions that get answered in different
places: is playing this card the best use of the turn's only Supporter slot,
and if so, WHICH body do we drag out.

THE TWO HALVES OF THE FILE

  * IS IT WORTH PLAYING -- the `_boss_*` predicates near the top, consumed by
    `_score_boss_orders_play`. Mostly reasons to DECLINE: the gust that
    achieves nothing because our active cannot attack anyway
    (`_boss_empty_gust`), the one that yields to a refill or a dig, the one
    that hands them their own evolution line back.
  * WHO TO DRAG -- `_ctx_gust_target` builds a per-candidate reading and the
    `_RULES_GUST_*` chains rank them, with `_ADJUST_GUST_*` correcting for the
    rest of the board.

WHAT A GUST IS ACTUALLY FOR. Three distinct purposes, and confusing them is the
classic error here:

  * THE PRIZE -- pull out something we can knock out. Ranked by what the
    knockout PAYS (`prize_count_op`, so their prize denial is included), not by
    how impressive the body is.
  * THE TRAP -- with no knockout available, pull up a body that cannot answer
    from the front. It costs them the turn or the energy to escape. This is
    what `_op_body_is_harmless` in `ptcg/calc/opponent.py` is for.
  * THE UNLOCK -- move their active out of the way because it is what is
    blocking us: an ex-immune wall, an ability lock, a dodge.

AND WHAT IT IS NOT FOR. A gust is also a FREE RETREAT WE GIVE THEM -- their
active goes to the bench without paying. Against a deck with one attacking
line, dragging up a pre-evolution just advances their plan; that is the
Alakazam family of rules, and the reason `_alakazam_attacker_relief` asks
whether the swap RELIEVES them instead.

THE ORDERING TRAP, which is this card's recurring defect. Boss's Orders
competes with every other Supporter, so its rules are full of "yields to X".
Each of those is sound in the situation it was written for and WRONG on a turn
that ends the game -- a resource-ordering veto has no business stopping a
winning gust. That is what `ptcg/turn/game_plan.py` exists to arbitrate, and
why rules here consult the turn plan rather than just the board.

Several vetoes are ABSOLUTE (`SCORE_FORBID`): Dunsparce, and anything in
`GUST_TRAP_IDS`. Those are not preferences to be outbid.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.cards.ids import Dwebble_Fighting, Dwebble_Grass, EX_PREEVO_IDS, GUST_TRAP_IDS, SCORE_FORBID, THREAT_PREEVO_IDS
from ptcg.calc.opponent import _alakazam_attacker_relief, _op_active_is_harmless, _op_body_is_harmless
from ptcg.calc.energy import _can_attack_eff, _grass_attach_unit, _pending_grass_extra_eff, _retreat_grass_units
from ptcg.calc.damage import _attacker_base_damage, _bench_attacker_best_damage, _bench_attacker_can_ko, _bench_finisher_that_survives, _bench_snipe_can_ko, _ex_active_is_a_wall, _hand_revealed_lethal_reply, _op_active_attack_damage_to, _our_effective_damage, _reply_reaches_match_point
from ptcg.calc.card import prize_count, prize_count_op
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.ids import Basic_Grass_Energy, Bayleef, DUNSPARCE_IDS, Dipplin, EX_PREEVO_IDS, Fezandipiti_ex, Hydrapple_ex, Meganium, OUR_EX_IDS, RETREAT_COST, THE_RELAY_INHERITS_THE_SEAT, THREAT_PREEVO_IDS, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calc.board import _active_of
from ptcg.calc.energy import _grass_mult
from ptcg.calc.damage import _ko_not_guaranteed
from dataclasses import dataclass
from ptcg.cards.ids import ALAKAZAM_ATTACKER_IDS, ALAKAZAM_LINE_IDS, Abra, Alakazam_ex, BOSS_SCORE_MARNIE_ENGINE_FIRST, Boss_Orders, Budew, Cyndaquil, DARKNESS_ENERGY_TYPE, Dragapult_ex, Drakloak, Dreepy, Dwebble_Fighting, Dwebble_Grass, EX_PREEVO_IDS, Froslass, GUST_TRAP_IDS, Grimmsnarl_ex, Hydrapple_ex, Iron_Thorns_ex, Kadabra, Latias_ex, Lillie_Determination, MARNIE_ENGINE_BEFORE_THE_LINE, MARNIE_ENGINE_GUST_RANK, MARNIE_LINE_IDS, Meowth_ex, Munkidori, Quilava, SCORE_FORBID, Snorunt, THREAT_PREEVO_IDS, Teal_Mask_Ogerpon_ex, Typhlosion
from ptcg.cards.tables import card_table
from ptcg.engine.rules import _Adjustment, _FixedRule


def _boss_val_de(ctx):
    return ctx.supp_values.get(Boss_Orders, 0)


def _boss_empty_gust(ctx):
    """An active that CANNOT attack this turn (log 85799299 step 50): the gust
    is not executable as a finisher; with Lillie's in hand, refilling pays more.
    The valuable cases are exempted."""
    return (ctx.active_cant_attack
            and not ctx.boss_win_via_bench
            and not ctx.boss_dodge_redirect
            and not ctx.boss_defensive_gust
            and not ctx.op_has_ability_immune_active
            and not ctx.op_has_ex_immune_active
            and ctx.hand_counts.get(Lillie_Determination, 0) >= 1)


def _boss_first_turn_yields(ctx):
    """On OUR first turn (log 86025936 step 11) with Lillie's in hand,
    Lillie's is ALWAYS played; Boss's yields (a gust takes no prize on the
    first turn)."""
    return (ctx.our_first_turn
            and ctx.hand_counts.get(Lillie_Determination, 0) >= 1
            and not ctx.state.supporterPlayed
            and not ctx.boss_win_via_bench)


def _boss_yields_to_dig(ctx):
    """It yields to Lillie's when we have no REAL benched attacker (user,
    registro_005 vs Dragapult): a DEVELOPMENT gust (cutting the opposing line
    by knocking out a 1-prize basic/pre-evolution) has no priority if, besides
    the active, we only have BASICS and no ready benched attacker: without a
    second attacker the gust does not chain and it is better to DIG.
    `has_ready_bench_attacker` only counts real ready attackers, never an
    Applin. ALL the valuable gusts are exempted."""
    # DOOMED ACTIVE WITH NO RELIEF (user, registro_004 t4 vs Team Rocket, LOST;
    # deck-agnostic): with the active about to die (active_ko_likely) and NO
    # ready benched attacker, a prize gust that does NOT win the game
    # (boss_ko_threat_preevo: +1 prize from the weak Spidops) leaves the board
    # with no plan -- the opponent knocks out, we promote a body with no energy
    # and the dead hand rebuilds nothing. There the KO yields to Lillie's
    # (digging for future attackers); the WINNING gust (boss_win_via_bench /
    # win_via_boss_gust) still dominates.
    # `active_doomed_real` (user, registro_004 t4 vs Mega Lucario, LOST):
    # the `active_ko_likely` heuristic returned False with our Ogerpon ex at
    # 210/210 HP because `_op_best_damage_vs` does not resolve the damage of the
    # opposing attack (always 0); the Mega Lucario ex in front already had the 2
    # energies of Mega Brave (270) and knocked it out for sure. The REAL finisher
    # read from attack_table is also consulted so the yield fires.
    _doomed_without_relief = ((ctx.active_ko_likely or ctx.active_doomed_real)
                             and not ctx.has_ready_bench_attacker)
    return (ctx.hand_counts.get(Lillie_Determination, 0) >= 1
            and not ctx.has_ready_bench_attacker
            and not ctx.boss_win_via_bench
            and not ctx.boss_dodge_redirect
            and not ctx.boss_defensive_gust
            and not (ctx.boss_ko_threat_preevo
                     and not _doomed_without_relief)
            and not ctx.boss_deny_alakazam_line
            and not ctx.op_has_ability_immune_active
            and not ctx.op_has_ex_immune_active)


def _boss_unlock_gust(ctx):
    """Gusting to UN-LOCK abilities (iron_thorns autopsy p018 t10, step 3 of the
    jul 2026 plan): with Iron Thorns ex as the opposing ACTIVE, Initialization
    cancels Teal Dance / Ripening / Last-Ditch / Flip the Script -- our whole
    engine. The lock is POSITIONAL: bringing up any NON-locker body from their
    bench with Boss's switches it off instantly (unlike Watchtower, which is a
    stadium and the gust does not touch it). In 6 dead turns of the autopsy the
    agent had Boss's in hand, an opposing bench with non-lockers... and END
    (`no_value`). It also chains with Meowth ex IN HAND: Boss's first (it
    un-locks), Meowth afterwards -> Last-Ditch works again.
    Guards: Iron Thorns ex in the opposing ACTIVE, a non-locker on their bench
    to bring up, and the un-locking being useful to us TODAY (Ogerpon ex /
    Hydrapple ex in play, or Meowth ex in hand)."""
    act = ctx.op_state.active[0] if ctx.op_state.active else None
    if act is None or act.id != Iron_Thorns_ex:
        return False
    if not any(b is not None and b.id != Iron_Thorns_ex
               for b in (ctx.op_state.bench or [])):
        return False
    return (ctx.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
            or ctx.field_counts.get(Hydrapple_ex, 0) >= 1
            or ctx.hand_counts.get(Meowth_ex, 0) >= 1)


def _boss_reason_with_prize(ctx):
    """Does the gust have a REAL reason behind it? The common denominator of the
    two vetoes below: if any of this is alive, the Boss's is played and they
    decide the target. It covers the finishers (winning the game, 2 prizes, a KO
    through `boss_prize_rank`), the line cuts with a KO (`deny_evo`,
    `deny_alakazam_line`, `gust_key_bench`, `ko_threat_preevo`), the dodge
    (`dodge_redirect`), the DEFENSIVE gust (avoiding the opponent's finisher)
    and the walls that cancel our attacker from the front.

    THE RELAY SEAT IS ON THIS LIST and belongs on it literally: it is a knockout,
    with its prizes already counted, that lands one turn later because the seat it
    is taken from does not open until then. Leaving it off would let the two
    deck-agnostic vetoes below kill it for the reason they were written to catch
    -- a gust that achieves nothing -- on the one board where the gust is the only
    thing the turn achieves. `gust_without_purpose` in particular reads THEIR
    CURRENT ACTIVE, and the body that opens our seat is the one we are about to
    put there."""
    v = ctx.supp_values
    return (ctx.win_via_boss_gust or ctx.gust_2prize_via_boss
            or ctx.boss_win_via_bench or ctx.boss_deny_alakazam_line
            or ctx.boss_prize_rank >= 1 or ctx.boss_ko_threat_preevo
            or ctx.boss_dodge_redirect or ctx.boss_defensive_gust
            or ctx.boss_relay_seat
            or ctx.op_has_ability_immune_active or ctx.op_has_ex_immune_active
            or bool(v.get('_boss_deny_evo'))
            or bool(v.get('_boss_gust_key_bench')))


def _gust_is_basic(card_id):
    data = card_table.get(card_id)
    return (data is not None
            and not getattr(data, 'stage1', False)
            and not getattr(data, 'stage2', False))


def _v_gust_net_stuck(c):
    """How badly a TRAP gust jams them, when no knockout is on offer.

    The measure is `stall_diff` -- their retreat cost minus the energy on the
    body -- which is what it will actually cost them to undo the gust. A body
    with an expensive retreat and nothing attached is the one that hurts.
    """
    v = 500 + c.stall_diff * 100
    # Tie-break (user): between targets that jam things up EQUALLY, avoid bringing
    # up the PRE-EVOLUTION of the opponent's main attacker (it could evolve and
    # attack from the active spot). A small penalty that only breaks ties.
    if c.card_id in THREAT_PREEVO_IDS or c.card_id in EX_PREEVO_IDS:
        v -= 50
    return v


def _v_gust_relay_seat(c):
    """The band of THE RELAY INHERITING THE SEAT, ordered by what it PAYS.

    20000 clears the whole nuisance ladder (`net_stuck` tops out around 2100
    with the harmless bonus, and `opponent_line_higher_evolution` reaches
    ~12000 but needs a retreat this state does not have) and the 2000 per prize
    is wider than any tie-break that runs after it, so the prize order cannot be
    inverted by an adjustment.
    """
    return 20000 + c.prizes * 2000


_RULES_GUST_NUISANCE = [
    # FREE retreat cost: the opponent sends it back to the bench without paying
    # anything; it does not get in the way at all (e.g. Budew). Discarded.
    _FixedRule("free_retreat",
               lambda c: c.rc0 <= 0,
               lambda c: SCORE_FORBID),
    # Latias ex (Skyliner) lets any Basic retreat for FREE: gusting a Basic does
    # not jam anything, and gusting the Latias itself is useless (user,
    # registro 010 step 76 vs Dragapult). The right target is a NON-basic (e.g.
    # Drakloak).
    _FixedRule("latias_frees_the_basics",
               lambda c: (c.op_latias
                          and (c.card_id == Latias_ex
                               or _gust_is_basic(c.card_id))),
               lambda c: SCORE_FORBID),
    # Bringing up an Iron Thorns ex as a NUISANCE is shooting ourselves in the
    # foot: its Initialization in the active spot LOCKS our abilities (Teal Dance /
    # Ripening / Last-Ditch) -- if one was already in front, the gust that was
    # supposed to un-lock (gust_unlocks_abilities) keeps it there; if there
    # was none, it creates one. In OFFENSIVE mode it does not apply: gusting it to
    # KNOCK IT OUT takes 2 prizes and removes it from the board.
    _FixedRule("nuisance_creates_the_iron_thorns_lock",
               lambda c: c.card_id == Iron_Thorns_ex,
               lambda c: SCORE_FORBID),
    # THE RELAY INHERITS THE SEAT (user, registro_008 step 72 vs Marnie's
    # Grimmsnarl ex, LOST -- deck-agnostic). Above the whole jam ladder, and it
    # has to be, because in this state the jam is not a currency: it is a lock we
    # put on our OWN door.
    #
    # Turn 8, six prizes each. Our active a Tapu Bulu at 20 of its 140 HP with no
    # energy: Wood Hammer costs four, its retreat costs three, there was no Grass
    # and no Switch in hand. It could not attack, it could not step aside, and the
    # three Teal Mask Ogerpon ex behind it -- two of them already at their three
    # energies -- could not reach the front while it stood there. On their bench:
    # two Munkidori, a Froslass and a Marnie's Grimmsnarl ex at 310 HP carrying
    # FIVE energies.
    #
    # The nuisance ladder priced the four candidates by what it would cost the
    # opponent to escape them, and answered the bare Munkidori: retreat cost one,
    # no energy, Mind Bend unpayable -- a body that cannot attack and cannot
    # leave, 500 + 100 for the net jam and +1500 for being harmless. The
    # Grimmsnarl ex, five energies against a retreat cost of two, jammed nothing
    # and fell to the default: -200, last of the four.
    #
    # Both halves of that reading are wrong on this board, and for the same
    # reason. A trap costs the opponent a turn, which is only worth something if
    # WE can spend the turn it buys -- and we could not: our active neither
    # attacked nor retreated, and the hand was two Meganium with no Bayleef under
    # them. What the trap really bought was that their knockout never came, and
    # THEIR KNOCKOUT WAS THE ONLY KEY TO OUR OWN SEAT. Freezing them freezes us
    # behind a body that will not move until it dies.
    #
    # Read the other way round it is a route the target scorer never had.
    # `can_ko` asks two questions -- can the ACTIVE knock this out today, can a
    # benched body knock it out after we RETREAT today -- and both need an active
    # that is usable. There is a third, and when the seat is locked it is the only
    # one alive: they knock our active out, we PROMOTE, and the body we promote
    # attacks whatever we gusted. Down that route every candidate on the board was
    # lethal, so the choice collapses to what the knockout PAYS: the Grimmsnarl ex
    # is worth two prizes and takes 540 from a benched Ogerpon that was already
    # charged -- Myriad Leaf Shower counts the energy on BOTH actives, so their
    # own five energies pay for it, and their Grass weakness doubles it.
    #
    # And that is the prize race the user names: their two-prize body spends its
    # attack on our one-prize corpse (6->5), our relay cashes two (6->4), and the
    # exchange keeps that shape. The bare Munkidori sells the same seat for one
    # prize; the Froslass and the other Munkidori do not open it at all.
    #
    # THE THREE CONDITIONS, all read per candidate in `_ctx_gust_target`: the
    # seat is LOCKED (our active neither attacks this turn nor can pay its way
    # out), THIS body opens it (its attack from the active spot knocks our active
    # out -- the bare Munkidori does not, which is exactly why trapping with it
    # keeps our door shut), and our BENCH cashes it with the energy it already
    # carries. Ordered by prizes, because once every candidate is lethal that is
    # the only thing left to choose by.
    #
    # `op_wins_next` vetoes it: handing over a knockout is only a trade while
    # there is a game left after it. The narrower half of that guard --
    # their knockout on our active taking their LAST prizes -- is inside the
    # reading itself, measured against this very body.
    _FixedRule("the_relay_inherits_the_seat",
               lambda c: (THE_RELAY_INHERITS_THE_SEAT
                          and c.relay_cashes_the_seat and not c.op_wins_next),
               _v_gust_relay_seat),
    # The nuisance is proportional to the NET retreat cost (the part the opponent
    # cannot pay with their energy): the higher the unpaid cost, the more it jams.
    _FixedRule("net_stuck",
               lambda c: c.stall_diff >= 1,
               _v_gust_net_stuck),
    # It can already pay its own retreat: a bad target (default -200).
]


_ADJUST_GUST_NUISANCE = [
    # Alakazam generalisation (user, registro_004 step 51 vs Garchomp, LOST):
    # ALWAYS favour the HIGHEST evolution of the opposing line that a benched
    # attacker can KNOCK OUT after retreating. Without this, nuisance mode
    # prefers the basic and lets the opposing line grow.
    _Adjustment("opponent_line_higher_evolution",
            # c.rc0 > 0: in the original this override lives INSIDE the else of the
            # free-retreat case; it must not rescue a FORBID caused by rc0<=0.
            lambda c, s: (c.rc0 > 0 and not c.op_alakazam
                          and c.line_rank >= 1 and c.line_can_ko),
            lambda c, s: max(s, 6000 + c.line_rank * 3000
                             + c.energy * 50
                             + (300 if c.tiene_tool else 0))),
    # Rule (user, registro 014 step 146 vs Alakazam): in nuisance mode,
    # PRIORITISE the Alakazam line over other support basics; trapping their
    # pre-evolution cuts the development. Kadabra > Abra > Alakazam.
    _Adjustment("alakazam_line_nuisance",
            lambda c, s: (c.op_alakazam
                          and c.card_id in ALAKAZAM_LINE_IDS),
            lambda c, s: s + {Kadabra: 350, Abra: 300,
                              Alakazam_ex: 250}[c.card_id]),
    # ...but WITHOUT a KO that order is inverted: bringing up a Kadabra/Alakazam
    # swaps one attacker for another (Powerful Hand costs 1 energy and the Kadabra
    # evolves the same turn). The relief only works with a bare Abra or with a body
    # outside the line (user, registro_002 step 20). It goes AFTER the adjustment
    # above so it overrides its bonus.
    _Adjustment("alakazam_line_do_not_promote_the_attacker",
            lambda c, s: (c.op_alakazam and not c.can_ko
                          and c.card_id in ALAKAZAM_ATTACKER_IDS),
            lambda c, s: SCORE_FORBID),
    # Same criterion as in OFFENSIVE mode (see there), and here it weighs more: in
    # nuisance mode our active CANNOT attack, so the body we bring up hits us with
    # no answer. `net_stuck` only looks at who cannot pay their RETREAT; this looks
    # at who cannot pay their ATTACK. `s > 0` so it does not rescue a SCORE_FORBID
    # from the rules above.
    _Adjustment("without_a_ko_prefer_the_dead_body",
            lambda c, s: (s > 0 and not c.can_ko and c.body_is_harmless
                          and c.card_id not in GUST_TRAP_IDS),
            lambda c, s: s + 1500),
    # THE GUST THAT ENDS THE GAME IS NOT A JAM (user, registro_010 step 131 vs
    # Dragapult, WON with one prize instead of two -- deck-agnostic).
    #
    # Turn 10, two prizes to five. Our active a Meganium at two of the four
    # energies Petal Dance costs -- so it did not attack -- but with a retreat
    # cost of two it could step aside, and behind it sat a Teal Mask Ogerpon ex
    # at EIGHT effective energies. On their bench: a Drakloak with one energy,
    # a Dreepy, and a **Fezandipiti ex** at 210 HP and no energy. Myriad Leaf
    # Shower counts the energy on both actives, so that Ogerpon read 270 on the
    # bare Fezandipiti: two prizes, our last two, the game.
    #
    # The agent gusted the Drakloak, cashed one prize, and played on.
    #
    # BOTH HALVES OF THE CARD HAD THE ANSWER AND NEITHER SPENT IT. The PLAY half
    # priced the Supporter at `win_via_bench` (990 -> 5600): its
    # retreat-and-promote detector walked their bench with the same
    # `_bench_attacker_can_ko`, found the body whose knockout wins, and then
    # `break`s without recording WHICH body it was. The TARGET half rebuilt the
    # reading correctly too -- `_ctx_gust_target` came out of that board with
    # `can_ko=True, prizes=2, wins_now=True` on the Fezandipiti ex -- and then
    # resolved it in the ladder that has no rung for winning.
    #
    # WHICH LADDER RUNS IS DECIDED BY OUR ACTIVE, AND THAT IS THE WHOLE DEFECT.
    # `ptcg/turn/options/card.py` sends the candidates to NUISANCE mode when the
    # active cannot attack this turn, which is a sound proxy for "no knockout is
    # on offer" only while the knockout has to come from the front. It does not:
    # `can_ko` has always had a second route -- retreat, promote, attack -- and
    # that route is at its STRONGEST precisely when the active is stuck, because
    # a stuck active is what makes retreating free of opportunity cost.
    #
    # So on this board the jam ladder priced three bodies by what it would cost
    # the opponent to escape them, and it is prize-blind by construction: its
    # only knockout-aware rung, `opponent_line_higher_evolution`, is gated on
    # `line_rank >= 1` and therefore cannot see a BASIC at all. The Drakloak --
    # a Stage 1 of their line we could also knock out -- took 6000 + 3000 + 50 =
    # 9050; the Fezandipiti ex, a Basic, fell through to `net_stuck` for 500 +
    # 100 = 600. One prize outranked the game by 8450 points.
    #
    # `wins_now` is not a preference to be outbid, and the offensive chain
    # already says so with `gust_wins_the_game`. This is the same sentence in
    # the other ladder, and it must be `max()` rather than `+`: the rules above
    # hand out SCORE_FORBID for free retreat, for Latias freeing the basics and
    # for the Iron Thorns lock, and every one of those is an argument about the
    # board we get to keep AFTER the gust. There is no such board. The prize
    # tie-break only orders WINNERS against each other.
    #
    # It names no card and no matchup: the reading is our bench's damage, their
    # body's HP, `prize_count_op` and our own prize count, so any deck whose
    # active is stuck with a charged finisher behind it gets the same answer.
    _Adjustment("gust_wins_the_game",
            lambda c, s: c.wins_now,
            lambda c, s: max(s, 100000 + c.tier_ko * 3000 + c.prizes * 100)),
]


def _gust_evolution_line(c, id_final, id_medio, id_basico):
    """Contribution for decks with a known evolution line (Dragapult,
    Ethan's Typhlosion, Alakazam): pin down / take out the most advanced piece.
    A Stage 1 WITHOUT energy is left PINNED (it pays no retreat and does not
    attack) and DELAYS the evolution: the best disruption target; a basic with
    no energy is also pinned (a strong nuisance)."""
    if c.card_id == id_final:
        return 1200 if c.can_ko else 800
    if c.card_id == id_medio:
        if c.can_ko:
            return 1000
        return 700 if c.energy < c.rc1 else 300
    if c.card_id == id_basico:
        if c.can_ko:
            return 400
        return 500 if c.energy < c.rc1 else 200
    if c.can_ko:
        if c.is_ex:
            return 900 + c.energy * 50
        if c.is_stage1:
            return 350 + c.energy * 50
        return 250 + c.energy * 50
    return 150


def _gust_generic_tiers(c):
    """A deck with no known line: tiers by stage/energy (KO / no-KO)."""
    if c.can_ko:
        if c.is_ex and c.energy >= 1:
            return 1100
        if c.is_ex:
            return 1000
        if c.is_stage2 and c.energy >= 1:
            return 900
        if c.is_stage2:
            return 850
        if c.is_stage1 and c.energy >= 1:
            return 700
        if c.is_stage1:
            return 600
        if c.card_id in THREAT_PREEVO_IDS:
            return 550
        if c.card_id == Budew:
            return 500
        if c.card_id == Munkidori:
            return 450
        if c.card_id == Snorunt:
            return 400
        if c.card_id in (Dwebble_Grass, Dwebble_Fighting):
            return 380
        if c.card_id in (Dreepy,):
            return 350
        if c.energy >= 1:
            return 300
        return 200
    if c.is_ex and c.energy >= 1:
        return 250
    if c.is_ex:
        return 200
    if c.is_stage2 and c.energy >= 1:
        return 180
    if c.is_stage2:
        return 160
    if c.is_stage1 and c.energy >= 1:
        return 150
    if c.is_stage1:
        return 130
    if c.card_id == Froslass:
        return 220
    if c.card_id == Budew:
        return 200
    if c.card_id == Munkidori:
        return 190
    if c.card_id == Snorunt:
        return 185
    if c.card_id in (Dreepy, Drakloak):
        return 180
    if c.card_id in (Dwebble_Grass, Dwebble_Fighting):
        return 178
    return 100


def _gust_opponent_line(c):
    if c.op_dragapult_line:
        return _gust_evolution_line(c, Dragapult_ex, Drakloak, Dreepy)
    if c.op_typhlosion_line:
        return _gust_evolution_line(c, Typhlosion, Quilava, Cyndaquil)
    if c.op_alakazam:
        return _gust_evolution_line(c, Alakazam_ex, Kadabra, Abra)
    return _gust_generic_tiers(c)


@dataclass(frozen=True)
class _ProjectedBody:
    """A body that is NOT on the board yet, shaped like one that is.

    The damage model in `ptcg/calc/damage.py` reads bodies through `id`, `hp`,
    `maxHp`, `energies`, `tools` and `serial`, and it is the only model in this
    project allowed to answer "does this knock out". A question about a body
    still in their deck -- the Grimmsnarl ex the line in front of us is going to
    become -- therefore has to be asked as a body and not as a second copy of the
    arithmetic. `serial=None` is deliberate: `_shield_mutes_our_ex` documents
    that a body with no serial answers False, which is the right answer about a
    card that has not been played.
    """

    id: int
    hp: int
    maxHp: int
    energies: tuple = ()
    tools: tuple = ()
    serial: object = None


def _marnie_grimmsnarl_projection(op_state):
    """The Marnie's Grimmsnarl ex we have to be able to answer.

    The one ON THE BOARD if they have already evolved -- its real HP, its real
    energy -- and otherwise the one their line is one Punk Up away from playing:
    full HP, carrying the energy the most-charged body of the line already holds.

    That energy is the CONSERVATIVE floor and not a guess. Punk Up searches up to
    five Basic {D} Energy out of the deck when the evolution lands, so the real
    body arrives with at least what its pre-evolution was holding and usually
    more -- and more energy on their active is MORE damage from our Teal Mask
    Ogerpon ex (Myriad Leaf Shower counts both actives), never less. Reading the
    floor can only make us answer "no, our bench does not cover it".

    Returns None when there is no Marnie's body in play to project from.
    """
    line = [b for b in ([_active_of(op_state)] + list(op_state.bench or []))
            if b is not None and b.id in MARNIE_LINE_IDS]
    if not line:
        return None
    for b in line:
        if b.id == Grimmsnarl_ex:
            return b
    data = card_table.get(Grimmsnarl_ex)
    if data is None:
        return None
    energy = max(len(getattr(b, 'energies', []) or []) for b in line)
    return _ProjectedBody(id=Grimmsnarl_ex, hp=data.hp, maxHp=data.hp,
                          energies=tuple([DARKNESS_ENERGY_TYPE] * energy))


def _marnie_bench_answers_the_grimmsnarl(my_state, op_state, total_grass,
                                         bench_count, neutralization_zone):
    """Does a body on OUR BENCH knock a Marnie's Grimmsnarl ex out?

    THE QUESTION THAT DECIDES WHETHER CUTTING THE LINE IS STILL WORTH IT. Boss's
    Orders hunts the highest link of an ex line (`ex_preevo_takes_priority`)
    because a 320 HP two-prize attacker we cannot answer decides the game on its
    own. Against Marnie's Grimmsnarl ex that premise is often false: the card is
    WEAK TO GRASS, so Myriad Leaf Shower doubles into it and a Teal Mask Ogerpon
    ex sitting on four Grass takes it off the board by itself.

    When that answer is already parked on our bench, spending the gust on the
    Morgrem buys a body they rebuild next turn and leaves the engine that is
    actually beating us -- Froslass's drip and Munkidori's aimed 30 -- untouched
    for another round. When it is NOT there, and our active is the only thing
    that covers the Grimmsnarl, cutting the line is still the play: our active
    can be knocked out, and then nothing covers it.

    The BENCH and not the whole board, which is the user's wording and also the
    only reading that means anything: an answer that has to stay in the active
    spot to exist is not a reserve.
    """
    target = _marnie_grimmsnarl_projection(op_state)
    if target is None:
        return False
    # No retreat is simulated and the field's Grass is not discounted: the
    # question is whether the reserve EXISTS, not what it costs to bring it
    # forward this turn -- the Grimmsnarl ex is not even on the board yet.
    return _bench_attacker_can_ko(
        my_state, target, AGENT_STATE.meganium_in_play, total_grass,
        bench_count, total_grass, neutralization_zone)


def _gust_relieves_the_attacker(op_state):
    """Deck-agnostic: does the gust swap an ATTACKER for a dead body?

    It is the generalisation of `_alakazam_attacker_relief` to the other
    evolution-line decks. A gust WITHOUT a KO only costs the opponent a turn
    when their ACTIVE can attack (or will be able to with one attachment) and
    the body that comes up canNOT: there the invested energy is left stranded on
    the bench and coming back means paying a retreat. If their active does not
    attack any more, there is nothing to relieve -- and Boss's also gives them
    the retreat for free (`_boss_gust_without_purpose`).

    Discarded as relief:
      * Dunsparce: a FORBIDDEN gust target (user's rule);
      * the known threat PRE-EVOLUTIONS (THREAT_PREEVO_IDS / EX_PREEVO_IDS):
        they evolve IN THE ACTIVE SPOT and attack with the NEW body, so their
        attack cost today says nothing. That is exactly what happened in
        registro_002 step 20 with the Abra -> Kadabra.

    NOTE: vs Alakazam `_alakazam_attacker_relief` still rules, and it DOES
    accept a bare Abra as relief (an explicit rule from the user). Here the Abra
    would be discarded for being a threat pre-evolution -- and its attack costs
    1 anyway, so it is not "harmless" by cost either.
    """
    if _op_active_is_harmless(op_state):
        return False
    for _b in (op_state.bench or []):
        if _b is None or _b.id in DUNSPARCE_IDS:
            continue
        if _b.id in THREAT_PREEVO_IDS or _b.id in EX_PREEVO_IDS:
            continue
        if _op_body_is_harmless(_b):
            return True
    return False


def _grass_unlocks_active_retreat(my_state, op_state, meganium_active,
                                  total_grass, bench_count, neutral_zone,
                                  active_can_attack, budget=1):
    """(ko, chip): do the Grass energies that can STILL land on the ACTIVE pay its
    retreat cost and enable attacking with a benched attacker?

    Common core of the line "Grass to the active -> RETREAT -> attack with the
    benched one". Two different routes consume it:
      * the MANUAL attachment (`_attach_enable_retreat_ko` /
        `_attach_enable_retreat_attack`, which also require the turn's
        attachment to still be free), and
      * the charging ABILITIES (Ripening Charge attaches to ANY of our Pokemon,
        Teal Dance to its own): those do NOT spend the manual attachment, so the
        line is still alive with `state.energyAttached` already set
        (user, registro_014 steps 137/141 vs Alakazam).

    It returns (False, False) if there is nothing to unlock: the active already
    pays its retreat, one Grass is not enough for it, or with that Grass the
    ACTIVE ITSELF attacks as well as or better than the benched body (then it
    does not retreat). `chip` is only evaluated if the active canNOT attack this
    turn.

    The comparison with the active's attack is by DAMAGE, not by "can attack"
    (user, registro_006 step 101 vs Alakazam, LOST): the active was an Applin
    (attack cost 1, retreat cost 1) with a benched Teal Mask Ogerpon ex at 6
    effective energies that KNOCKED OUT the Alakazam. Because one Grass left the
    Applin "at its attack cost", the old guard switched off the entire line --
    even though `_attacker_base_damage` does not give the Applin A SINGLE point
    of damage. The Grass went to a benched Ogerpon and the turn ended without
    attacking. A filler body that reaches its attack cost cannot veto the KO
    served up by a real attacker; a tie is resolved in favour of the active
    (attacking with the active comes first, and it also does not spend the
    retreat).

    `budget` is the charging BUDGET: how many Grass energies can still land on
    the ACTIVE this turn (an unspent manual attachment + charging abilities that
    can point at it, bounded by the available Grass). It mirrors the budget of
    `_charge_active_finishes`, which already computed the active's ATTACK cost that
    way -- here it was missing and the line was limited to ONE Grass (user,
    episode 88631738 step 77): with a retreat cost of 2 or 3 symbols and two
    live charging routes, the retreat was payable and the detector did not see
    it, so the turn closed without attacking. `budget=1` (the default)
    reproduces the previous behaviour, which is the right one for consumers with
    a single Grass at hand (e.g. the one a Night Stretcher recovers from the
    discard).
    """
    act = _active_of(my_state)
    opa = _active_of(op_state)
    if act is None or opa is None:
        return False, False
    rc = RETREAT_COST.get(act.id, 1)
    e = len(act.energies)
    unit = _grass_attach_unit()
    if e >= rc:
        return False, False
    # Grass needed to reach the cost (rounded up), and what the budget allows. The
    # chain is executed step by step: the greedy tie-break re-evaluates after each
    # charge, with `need` already decremented.
    need = -(-(rc - e) // unit) if unit > 0 else 0
    if not 1 <= need <= max(1, int(budget or 1)):
        return False, False
    gained = need * unit
    # EFFECTIVE damage the active itself would do with those same Grass (0 if it
    # does not reach its attack cost or its attack does not score in the model).
    act_dmg = 0
    if _can_attack_eff(act.id, e + gained):
        _act_base = _attacker_base_damage(
            act.id, opa, e + gained, grass_scale=total_grass + gained,
            teal_self_energy=e + gained, bench_count=bench_count)
        act_dmg = _our_effective_damage(act, opa, _act_base, meganium_active,
                                        neutral_zone)
        if act_dmg > 0 and act_dmg >= (opa.hp or 0):
            # The active FINISHES with that Grass: attacking with it comes
            # first -- UNLESS standing there afterwards is what loses the game
            # (user, registro_012 step 120 vs Alakazam, LOST -- deck-agnostic).
            #
            # Turn 12, four prizes to three. Our active was a Hydrapple ex at
            # 110 of its 330 HP with two energies, and its Syrup Storm knocked
            # out their Alakazam from the front. So the guard fired, the turn
            # went into Teal Dance and we attacked with the active. Their reply
            # -- Powerful Hand, 20 per card in a hand of six, plus the Maximum
            # Belt against our ex -- knocked out that 110 HP body, took the two
            # prizes it hands over, and closed the game.
            #
            # One energy short of its retreat cost sat the answer: a benched
            # Teal Mask Ogerpon ex with three energies that ALSO finished their
            # Alakazam, at 210 HP, out of reach of that same reply. Same prize
            # this turn, and the body left in front survives to take the next
            # one.
            #
            # So "the active finishes" only settles it while the active can
            # afford to stay. When the projected reply knocks it out AND those
            # are their last prizes, the choice is not whether to finish but
            # WHICH of the two finishers is left standing -- and the retreat
            # line wins whenever the relay survives and hands over no more
            # prizes.
            #
            # The prize gate (`_reply_reaches_match_point`) is what keeps this a
            # defensive pivot and not a preference. Without it the rule also
            # fires on boards where the trade is merely unpleasant, and there
            # the turn is worth more spent elsewhere -- healing the body that is
            # about to die, charging the bench -- as several measured records
            # already fix.
            #
            # It reads the attack of the active we are about to knock out, as a
            # proxy for the body that replaces it -- in an evolution-line deck
            # that is the same threat again, and the guard only ever loosens
            # towards a strictly tougher body of ours.
            _op_reply = _hand_revealed_lethal_reply(
                opa, act, getattr(op_state, 'handCount', None))
            _relay_survives = (
                _op_reply > 0
                and _reply_reaches_match_point(act, op_state, opa)
                and _bench_finisher_that_survives(
                    my_state, opa, meganium_active, bench_count,
                    max(0, total_grass - _retreat_grass_units(rc)),
                    neutral_zone, _op_reply, prize_count(act)))
            if not _relay_survives:
                return False, False
    # The attached energy is discarded when paying the retreat: the Grass on the
    # field after retreating is approximated with the current one (net ~0).
    grass_after = max(0, total_grass - _retreat_grass_units(rc))
    if _bench_attacker_can_ko(my_state, opa, meganium_active, total_grass,
                              bench_count, grass_after, neutral_zone):
        return True, False
    # SECOND question, never a substitute for the one above: the body we promote
    # may be a SNIPER, and then the KO does not have to be in front of us
    # (registro_014 step 129 -- the whole story is on `_bench_snipe_best`). It is
    # asked before the `active_can_attack` cut-off because that cut-off is the
    # one that swallowed the case: our Hydrapple ex COULD attack, into a
    # Cornerstone wall, for zero.
    if _bench_snipe_can_ko(my_state, op_state, meganium_active, bench_count,
                           grass_after, neutral_zone):
        return True, False
    if active_can_attack:
        return False, False
    # The "do not swap an ex for a worse body" guard (mirror of the retreat
    # scorer): the body coming up must endure at least what the ex has left.
    #
    # The HP floor only makes sense while the ex in front IS a wall (user,
    # episode 90321662 step 104 vs Crustle/Great Tusk, LOST by deck-out with
    # five prizes still on the table). Our active was a Meowth ex at 170/170 and
    # 0 energy -- retreat cost 1, no attack in any state of the game -- with two
    # charged Dipplin on the bench and a Neutralization Zone of theirs on the
    # field, which zeroes our ex against their 1-prize active. So EVERY body
    # that could hurt their Great Tusk was a non-ex smaller than 170, the floor
    # discarded all of them, `chip` came out 0 and the line died: the Grass went
    # to a benched Tapu Bulu (28000) and the turn ended without attacking. The
    # same shape had been repeating for turns, and we never took a prize.
    #
    # When the ex is not a wall the guard keeps its OTHER half -- the one the
    # Archaludon case was really about, "the opponent takes the same prizes with
    # less effort": the body coming up may not hand over more prizes than the
    # one going down. A 1-prize Dipplin that hits for the 2-prize engine that
    # cannot is a strict improvement on both counts.
    min_hp = 0
    max_prizes = None
    if act.id in OUR_EX_IDS:
        if _ex_active_is_a_wall(act):
            min_hp = act.hp or 0
        else:
            max_prizes = prize_count(act)
    chip = _bench_attacker_best_damage(
        my_state, opa, meganium_active, bench_count, grass_after,
        neutral_zone, min_body_hp=min_hp, max_prizes=max_prizes)
    return False, chip > act_dmg


def _boss_gives_away_alakazam_line(ctx):
    """VETO vs Alakazam (user, registro_002 step 20, LOST -- ep. 88906640).

    Turn 2: our Ogerpon ex at 1/3 energies (no attack), their active a
    Fezandipiti ex at 0 energies (Cruel Arrow costs 3: it CANNOT attack on their
    turn) and their bench with four Abra + a Dunsparce. The agent played Boss's
    Orders and brought up an Abra; the opponent had the Kadabra IN HAND, evolved
    and started attacking with the body we had put in front of us.

    Two mistakes in the same play: (1) the gust took nothing -- the opposing
    active was not a threat that had to be moved out of the way; (2) in THIS
    matchup Abra/Kadabra/Alakazam are the only attacking line, so bringing one
    up is doing their work for them. The valuation came from the
    `elif op_is_alakazam_deck` branch of `evaluate_supporters`, which scored 700
    for gusting "the highest evolution of the line on their bench" without
    requiring a KO.

    The only gust without a KO that is allowed is the RELIEF of their attacker
    (`_alakazam_attacker_relief`). Any reason with a prize behind it
    (`_boss_reason_with_prize`) rules over this veto."""
    if not ctx.op_is_alakazam_deck or _boss_reason_with_prize(ctx):
        return False
    return not _alakazam_attacker_relief(ctx.op_state)


def _boss_gust_without_purpose(ctx):
    """Deck-agnostic VETO: a gust without a KO against a HARMLESS opposing active.

    Boss's Orders is, for the opponent, a FREE RETREAT. Giving it away only pays
    off for one of two reasons: taking a prize we cannot take from the front, or
    moving out of the way the body that is going to hit us. If their ACTIVE
    cannot attack even on their next turn (`_op_active_is_harmless`: all its
    attacks cost more than energies+1) the second reason does not exist, and
    `_boss_reason_with_prize` already ruled out the first: the gust only moves
    bodies around, spends the turn's Supporter and leaves the opponent better
    placed.

    It generalises the failure of `registro_002 step 20` to any deck: the
    branches of `evaluate_supporters` that score "bring up the highest evolution
    of their line" (Dragapult, Ethan's Typhlosion, Gardevoir, Zoroark, Slowking,
    Alakazam) and the JAM branch (`stall_val`) do not require a KO, and all of
    them end up in the reserve rule `supporter_value`.

    EXCEPTION: if their active is a known threat pre-evolution
    (THREAT_PREEVO_IDS / EX_PREEVO_IDS) its current attack is not read -- it
    evolves and attacks with the new body -- so it is not vetoed."""
    if _boss_reason_with_prize(ctx):
        return False
    act = ctx.op_state.active[0] if ctx.op_state.active else None
    if act is not None and (act.id in THREAT_PREEVO_IDS
                            or act.id in EX_PREEVO_IDS):
        return False
    return _op_active_is_harmless(ctx.op_state)


@dataclass
class _CtxGustObjetivo:
    """ONE candidate gust target, read against the whole board.

    Built per opposing body by `_ctx_gust_target` and scored by the
    `_RULES_GUST_*` chains. The fields group into the three purposes a gust can
    serve, and reading them that way is the fastest way to understand the
    chains: `prizes`/`can_ko`/`tier_ko`/`wins_now` are THE PRIZE,
    `rc0`/`stall_diff`/`body_is_harmless` are THE TRAP, and
    `wall_blocks_active`/`op_alakazam`/the line flags are the matchup reading
    that decides whether dragging this body out helps us or helps them.

    The defaulted fields at the bottom arrive from readings made elsewhere --
    notably `op_wins_next`, which is taken from the turn plan and deliberately
    NOT recomputed here, so the offensive and defensive halves of the turn
    cannot disagree about whether we are about to lose.
    """

    card_id: int
    energy: int
    rc0: int                 # RETREAT_COST.get(id, 0) (jams)
    rc1: int                 # RETREAT_COST.get(id, 1) (evolution lines)
    stall_diff: int          # rc0 - energy
    is_ex: bool              # ex flag (without mega)
    is_exmega: bool          # ex or megaEx (KO tiers)
    is_megaex: bool          # megaEx (3 prizes): its own tier above ex
    prizes: int              # prize_count(target): prizes we take by knocking it out
    wins_now: bool           # knocking this target out WINS the game (prizes >= my_prize)
    is_stage1: bool
    is_stage2: bool
    tiene_tool: bool
    can_ko: bool             # the active (or the bench after retreating) knocks it out
    tier_ko: int             # 1..8 if can_ko, 0 otherwise
    plan_target_match: bool  # o.index == plan.target - 1
    regust_energized: bool   # charged copy of an opposing active with no energy
    line_rank: int          # 0 basic / 1 stage1 / 2 stage2
    line_can_ko: bool       # nuisance: a benched attacker knocks it out after retreating
    op_alakazam: bool
    op_latias: bool
    op_dragapult_line: bool
    op_typhlosion_line: bool
    # The opposing ACTIVE cancels our damage (a wall): attacking from the front
    # gives 0 prizes.
    wall_blocks_active: bool = False
    # The target could NOT attack from the active spot on the opponent's next turn
    # even with one energy attached (`_op_body_is_harmless`, measured by COST). It
    # is the datum that decides the target when there is NO KO: bringing up a dead
    # body costs them the turn; bringing up one that attacks does their work.
    body_is_harmless: bool = False
    # The turn plan says their reply CLOSES the game: the body in front of us
    # knocks our active out and that KO takes their last prizes. Read from the
    # plan and not recomputed; see `ptcg/turn/game_plan.py`.
    op_wins_next: bool = False
    # This target LOCKS their next turn: it survives our attack, it cannot attack
    # us from the active spot even after one attachment, and it cannot pay its own
    # retreat to get back to the bench. The three together are what makes the gust
    # a denial and not just a nuisance.
    traps_their_turn: bool = False
    # THE THIRD KO ROUTE, the only one alive when the seat is locked: our active
    # can neither attack this turn nor pay its way out of the front, THIS body
    # knocks it out from the active spot (so their turn hands us the promotion),
    # and a body already on our bench knocks THIS one out from the seat it
    # inherits. `can_ko` cannot see it -- its two routes both need a usable
    # active. It also carries the prize floor: it is only True while their
    # knockout on our active leaves them prizes to take afterwards.
    relay_cashes_the_seat: bool = False
    # THE MARNIE MATCHUP, and the one condition that switches its ladder on: the
    # opponent plays Marnie's Grimmsnarl ex AND a body on OUR BENCH already
    # answers that Grimmsnarl ex, so cutting the line is no longer the only
    # thing keeping us alive and the gust can go after the Munkidori/Froslass
    # engine instead. It is a property of the BOARD, identical for every
    # candidate of the same decision; it rides on the candidate context because
    # that is the only thing the rule chains can see.
    marnie_engine_first: bool = False


def _gust_relay_cashes_the_seat(card, my_state, op_state, state, hand_counts,
                                total_grass, bench_count,
                                neutralization_zone_active, op_prize):
    """Does gusting `card` sell a locked seat for a knockout our RELAY takes?

    THE THIRD KNOCKOUT ROUTE, and the only one alive when the seat is locked.
    `can_ko` asks whether our ACTIVE finishes the target today, and whether a
    benched body finishes it after we RETREAT today; both need an active that is
    usable. When ours neither attacks nor can leave, there is one route left --
    they knock it out, we PROMOTE, and the promoted body attacks what we gusted
    -- and this is the function that reads it.

    ONE FUNCTION FOR BOTH HALVES OF THE CARD, deliberately. The play half asks it
    as an EXISTENCE question over their bench ("is there a reason to spend the
    Supporter"), the target half asks it PER CANDIDATE ("which body"). Two models
    of the same question is exactly how this card came to justify a play with one
    reading and then aim it with another -- see `without_a_ko_prefer_the_dead_body`
    and the defensive gust it used to contradict.

    Three readings, in the order that makes the cheap one cut first, plus the
    prize floor that keeps it a trade. Nothing here names a card or a matchup: it
    is our active's attack and retreat costs, their body's attack, our bench's
    damage and the two prize counts.
    """
    atk = my_state.active[0] if (my_state.active and card is not None) else None
    if atk is None:
        return False
    # (1) THE SEAT IS LOCKED. Our active does not attack this turn even with the
    # attachment still to come, and it cannot pay its way out of the front -- no
    # Switch in hand and not enough energy for its retreat. So the only thing
    # that empties the seat is their knockout.
    _rs_e = len(atk.energies)
    _rs_attach = (_grass_attach_unit()
                  if (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                      and not state.energyAttached) else 0)
    if (_can_attack_eff(atk.id, _rs_e + _rs_attach)
            or hand_counts.get(1123, 0) >= 1
            or _rs_e >= RETREAT_COST.get(atk.id, 1)):
        return False
    # (2) THEIR KNOCKOUT STILL LEAVES A GAME. Selling the body in front is a
    # trade only while the prizes it pays are not their last ones.
    if op_prize <= prize_count(atk):
        return False
    # (3) THIS body opens the seat, and our bench cashes what sits in it. The
    # promoted body pays no retreat -- the seat comes free -- but the knockout
    # takes our active's energy off the field with it, and the bench it leaves is
    # one body smaller.
    if _op_active_attack_damage_to(
            card, atk, getattr(op_state, 'handCount', None),
            scaled=True, team_buff=True) < (atk.hp or 0):
        return False
    return _bench_attacker_can_ko(
        my_state, card, AGENT_STATE.meganium_in_play, total_grass,
        max(0, bench_count - 1), max(0, total_grass - _rs_e),
        neutralization_zone_active)


def _gust_relay_seat_on_their_bench(my_state, op_state, state, hand_counts,
                                    total_grass, bench_count,
                                    neutralization_zone_active, op_prize):
    """The EXISTENCE half: is there any body on their bench worth the trade?

    What the PLAY half of Boss's Orders needs. The exclusions are the ones every
    other bench walk in this file already makes -- a Dunsparce is a forbidden
    target, a free-retreat body goes straight back, and the walls and the ability
    locker are the last bodies we want in front however good the trade looks.
    """
    for _b in (op_state.bench or []):
        if _b is None or _b.id in DUNSPARCE_IDS or _b.id in GUST_TRAP_IDS:
            continue
        if RETREAT_COST.get(_b.id, 0) <= 0:
            continue
        if _gust_relay_cashes_the_seat(
                _b, my_state, op_state, state, hand_counts, total_grass,
                bench_count, neutralization_zone_active, op_prize):
            return True
    return False


def _ctx_gust_target(card, o, my_state, op_state, state, hand_counts,
                       total_grass, bench_count, neutralization_zone_active,
                       op_is_alakazam, op_latias, op_dragapult_line,
                       op_typhlosion_line, my_prize=6, op_prize=6):
    """Read ONE opposing body as a gust candidate -> `_CtxGustObjetivo`.

    Called once per body on their bench; the resulting contexts are what the
    `_RULES_GUST_*` chains rank against each other. Everything expensive is
    resolved here -- can we knock it out, what does that pay, what would it
    cost them to escape -- so the rules themselves stay cheap comparisons.

    Note the defensive `hasattr`/`getattr` reads: the candidate arrives from
    `get_card()` and may be a shape this function did not expect. An exception
    at this point would forfeit the game, so a missing field degrades to a
    conservative default instead.
    """
    tgt_data = card_table.get(card.id)
    energy = len(card.energies) if hasattr(card, 'energies') else 0
    hp = card.hp if hasattr(card, 'hp') else 999
    is_ex = bool(tgt_data and getattr(tgt_data, 'ex', False))
    is_megaex = bool(tgt_data and getattr(tgt_data, 'megaEx', False))
    is_exmega = bool(tgt_data is not None and
                     (getattr(tgt_data, 'ex', False) or
                      getattr(tgt_data, 'megaEx', False)))
    prizes = prize_count_op(card)
    is_stage1 = bool(tgt_data and getattr(tgt_data, 'stage1', False))
    is_stage2 = bool(tgt_data and getattr(tgt_data, 'stage2', False))

    # KO by the ACTIVE: damage table per attacker + weakness/resistance
    # (except Fezandipiti, fixed damage) + ex/ability immunities.
    can_ko = False
    atk = my_state.active[0] if my_state.active else None
    if atk is not None:
        eff_e = len(atk.energies) * _grass_mult()
        can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                      and not state.energyAttached)
        # THE SAME projection the winning-gust detector makes (`_win_via_boss_gust`
        # in agent()): the manual attachment AND the active's own Teal Dance, in
        # EFFECTIVE energy. Two models of the same attack is how the agent came to
        # promise a game and cash one prize (registro_014 step 154 vs Alakazam:
        # the detector projected Teal Dance -> Myriad 210 -> the Fezandipiti ex on
        # their bench = our last two prizes = 20000 `winning_gust`, which VETOED
        # the Xerosic; this scorer read the same Ogerpon without the ability, saw
        # 150 on a 210 HP body, found "no KO" and aimed the gust at an Abra worth
        # one prize). The projection only ever ADDS knockable targets, and it
        # cannot promise energy the ability scorer will refuse to attach: the
        # matchup caps on Teal Dance (Alakazam / Hop's / Cubchoo / Crustle) all
        # make an exception for the attachment that ENABLES the KO on the
        # opposing active, which is exactly the case that flips `can_ko` here.
        eff_after = eff_e + _pending_grass_extra_eff(
            atk, hand_counts.get(Basic_Grass_Energy, 0), state.energyAttached)
        dmg = 0
        if atk.id == Hydrapple_ex and eff_after >= 2:
            dmg = 30 + 30 * total_grass
        elif atk.id == Dipplin and eff_after >= 1:
            dmg = 20 * bench_count
        elif atk.id == Teal_Mask_Ogerpon_ex and eff_after >= 3:
            # Myriad Leaf Shower counts the energy on BOTH actives, and OURS is
            # the EFFECTIVE one (Wild Growth doubles every Grass): `eff_after` is
            # what `_attacker_base_damage` calls `teal_self_energy`. The copy that
            # lived here added the pending attachment RAW (+1), so with Meganium
            # in play it fell 30 damage short of the real number.
            o_e = energy
            dmg = 30 + 30 * (o_e + eff_after)
        elif atk.id == Tapu_Bulu and eff_after >= 4:
            dmg = 220
        elif atk.id == Fezandipiti_ex and eff_after >= 3:
            dmg = 100
        elif atk.id == Meganium and eff_after >= 4:
            dmg = 140
        elif atk.id == Bayleef and eff_after >= 2:
            dmg = 60

        # CENTRAL damage evaluator (P0.1): the inline copy applied weakness and
        # ex/ability immunities but ignored Drednaw (cancels >=200),
        # Sturdy/Resolute Heart (cap at hp-10), Farigiraf's Armor Tail and the
        # Neutralization Zone -> `can_ko`/`wins_now` could declare false KOs.
        eff_dmg = _our_effective_damage(atk, card, dmg, AGENT_STATE.meganium_in_play,
                                        neutralization_zone_active)
        if eff_dmg >= hp:
            can_ko = True

    # Alternative KO: retreat the active and knock out with a benched attacker.
    if not can_ko and atk is not None:
        switch_hand = hand_counts.get(1123, 0) >= 1
        ret_cost = RETREAT_COST.get(atk.id, 1)
        if switch_hand or len(atk.energies) >= ret_cost:
            grass_after = max(0, total_grass
                              - (0 if switch_hand else ret_cost))
            if _bench_attacker_can_ko(
                    my_state, card, AGENT_STATE.meganium_in_play, total_grass,
                    bench_count, grass_after, neutralization_zone_active):
                can_ko = True

    # PRIZE-AWARE KO tiers (user, registro_011 vs Mega Heracross ex): a megaEx
    # yields 3 PRIZES, an ex 2. Before, both fell into `is_exmega` (tier 8/7) and
    # the +1 for "charged" (with_energy) made a CHARGED 2-prize ex (tier 8) beat a
    # 3-prize megaEx WITHOUT energy (tier 7): the game gusted the Ogerpon ex (2)
    # instead of the Mega (3) that won the game. Now the megaEx has its own tier
    # ABOVE the ex (10/9 vs 8/7), so that a Mega with no energy (9 -> 27000) beats
    # a charged ex (8 -> 24000). Deck-agnostic.
    tier = 0
    if can_ko:
        with_energy = energy >= 1
        if is_megaex:
            tier = 10 if with_energy else 9
        elif is_ex:
            tier = 8 if with_energy else 7
        elif is_stage2:
            tier = 6 if with_energy else 5
        elif is_stage1:
            tier = 4 if with_energy else 3
        else:
            tier = 2 if with_energy else 1

    # Nuisance: the HIGHEST evolution of the opposing line that a benched attacker
    # can knock out after retreating the active (registro_004 step 51 vs Garchomp).
    line_rank = 2 if is_stage2 else (1 if is_stage1 else 0)
    line_can_ko = False
    if line_rank >= 1 and atk is not None:
        switch_hand = hand_counts.get(1123, 0) >= 1
        ret_cost = RETREAT_COST.get(atk.id, 1)
        if switch_hand or len(atk.energies) >= ret_cost:
            grass_after = max(0, total_grass
                              - (0 if switch_hand else ret_cost))
            if _bench_attacker_can_ko(
                    my_state, card, AGENT_STATE.meganium_in_play, total_grass,
                    bench_count, grass_after, neutralization_zone_active):
                line_can_ko = True

    op_act = op_state.active[0] if op_state.active else None
    regust = (can_ko and op_act is not None and op_act.id == card.id
              and len(op_act.energies) == 0 and energy >= 1)

    # WALL IN THE ACTIVE SPOT (deck-agnostic): if our ACTIVE does not do a SINGLE
    # point of damage to the opposing active, attacking from the front takes no
    # prizes and the turn's only prize is on the opposing BENCH. It covers any
    # cancellation that `_our_effective_damage` already models (Crustle's Mysterious
    # Rock Inn, Cornerstone Stance, Sylveon...), not a list of ids. The exemption of
    # the anti-Dwebble veto in `_ADJUST_GUST_NUISANCE` consumes it.
    wall_blocks_active = False
    if atk is not None and op_act is not None:
        _mb_raw = len(atk.energies) + (
            1 if (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                  and not state.energyAttached) else 0)
        _mb_base = _attacker_base_damage(
            atk.id, op_act, _mb_raw * _grass_mult(), grass_scale=total_grass,
            teal_self_energy=_mb_raw, bench_count=bench_count)
        wall_blocks_active = _our_effective_damage(
            atk, op_act, _mb_base, AGENT_STATE.meganium_in_play,
            neutralization_zone_active) <= 0

    # THE TRAP: a body that survives the turn, cannot answer and cannot leave.
    # `not can_ko` is not a weakness of the target, it is the point -- a corpse
    # does not stay in the active spot, and after a gust KO the opponent promotes
    # whatever they like, which is exactly the body we were trying to move.
    # `GUST_TRAP_IDS` (walls and the ability locker) is excluded for the same
    # reason as in `without_a_ko_prefer_the_dead_body`: their attacks cost 3, so
    # bare they read as harmless and they are the last bodies we want in front.
    body_harmless = _op_body_is_harmless(card)
    traps_their_turn = (not can_ko and body_harmless
                        and RETREAT_COST.get(card.id, 0) - energy >= 1
                        and card.id not in GUST_TRAP_IDS)

    relay_cashes_the_seat = _gust_relay_cashes_the_seat(
        card, my_state, op_state, state, hand_counts, total_grass, bench_count,
        neutralization_zone_active, op_prize)

    # ONE point for the whole reading, and therefore one point for the switch:
    # both consumers ask this field (the new rung and the stand-down of
    # `ex_preevo_takes_priority`), so `MARNIE_ENGINE_BEFORE_THE_LINE = False`
    # restores the previous behaviour in both at once.
    marnie_engine_first = (
        MARNIE_ENGINE_BEFORE_THE_LINE
        and AGENT_STATE.op_is_marnie_deck
        and _marnie_bench_answers_the_grimmsnarl(
            my_state, op_state, total_grass, bench_count,
            neutralization_zone_active))

    return _CtxGustObjetivo(
        card_id=card.id, energy=energy,
        rc0=RETREAT_COST.get(card.id, 0), rc1=RETREAT_COST.get(card.id, 1),
        stall_diff=RETREAT_COST.get(card.id, 0) - energy,
        is_ex=is_ex, is_exmega=is_exmega, is_megaex=is_megaex,
        # `wins_now` also requires a GUARANTEED KO (P0.1): against Tenacious Body
        # (a coin flip) or Survival Brace the finisher can fail and hand the turn back.
        prizes=prizes, wins_now=(can_ko and prizes >= my_prize
                                 and not _ko_not_guaranteed(card)),
        is_stage1=is_stage1, is_stage2=is_stage2,
        tiene_tool=bool(getattr(card, 'tools', None)),
        can_ko=can_ko, tier_ko=tier,
        plan_target_match=(o.index == AGENT_STATE.plan.target - 1),
        regust_energized=regust,
        line_rank=line_rank, line_can_ko=line_can_ko,
        op_alakazam=op_is_alakazam, op_latias=op_latias,
        op_dragapult_line=op_dragapult_line,
        op_typhlosion_line=op_typhlosion_line,
        wall_blocks_active=wall_blocks_active,
        body_is_harmless=body_harmless,
        op_wins_next=bool(getattr(AGENT_STATE.turn_plan, 'op_wins_next', False)),
        traps_their_turn=traps_their_turn,
        relay_cashes_the_seat=relay_cashes_the_seat,
        marnie_engine_first=marnie_engine_first)


_ADJUST_GUST_OFFENSIVE = [
    _Adjustment("target_of_the_plan",
            lambda c, s: c.plan_target_match,
            lambda c, s: s + 100),
    # WINNING GUST (user, registro_011 vs Mega Heracross ex, WON suboptimally):
    # if knocking THIS target out takes the prizes we need to WIN
    # (`wins_now`: prizes >= my_prize), it is the ABSOLUTE top priority over any
    # other target. When several targets win, the prize-aware tier_ko below breaks
    # the tie towards the one worth more prizes. It covers the case where the
    # finisher was available but the game gusted an ex worth fewer prizes.
    # Deck-agnostic.
    _Adjustment("gust_wins_the_game",
            lambda c, s: c.wins_now,
            lambda c, s: s + 100000),
    _Adjustment("tier_ko",
            lambda c, s: c.can_ko,
            lambda c, s: s + c.tier_ko * 3000),
    # PRIORITY (user, log 86504664 step 94, LOST vs Archaludon): when it can be
    # KNOCKED OUT, a CHARGED pre-evolution of an ex line (Duraludon ->
    # Archaludon ex) erases a future 2-prize ex attacker. Effective tier
    # 6.5 (19500): above any non-ex, below a real ex.
    # ...UNLESS the line is Marnie's and our bench already answers what it grows
    # into. See `marnie_the_engine_before_the_line` below for the record and the
    # reasoning: this rung pays 19500 for the premise "a two-prize ex attacker we
    # cannot answer", and that premise is what `marnie_engine_first` reports
    # false. The line then falls back to its plain knockout tier (a charged
    # Morgrem: 12700) instead of being suppressed outright, so it still outranks
    # the bodies that threaten nothing -- it just stops outbidding the engine.
    _Adjustment("ex_preevo_takes_priority",
            lambda c, s: (c.can_ko and c.energy >= 1 and not c.is_exmega
                          and c.card_id in EX_PREEVO_IDS
                          and not (c.marnie_engine_first
                                   and c.card_id in MARNIE_LINE_IDS)),
            lambda c, s: s + max(0, 19500 - c.tier_ko * 3000)),
    # No KO possible: gust as a nuisance (the highest NET retreat cost) with the
    # anti threat pre-evolution tie-break.
    _Adjustment("stuck_without_ko",
            lambda c, s: not c.can_ko and c.stall_diff >= 1,
            lambda c, s: s + c.stall_diff * 100
            - (50 if (c.card_id in THREAT_PREEVO_IDS
                      or c.card_id in EX_PREEVO_IDS) else 0)),
    # A CHARGED copy of an opposing active with no energy: re-gusting it collects
    # on the opponent's investment.
    _Adjustment("regust_the_energized_one",
            lambda c, s: c.regust_energized,
            lambda c, s: s + 200),
    _Adjustment("opponent_line",
            lambda c, s: True,
            lambda c, s: s + _gust_opponent_line(c)),
    # THE ENGINE BEFORE THE LINE, and only in the Marnie matchup (user,
    # `records/registro_008_pasos_108_hasta_114.json` step 110, episode 93525290,
    # turn 8 vs Marnie's Grimmsnarl ex -- LOST).
    #
    #     US (seat 1, 4 prizes)                RIVAL (5 prizes)
    #     active Hydrapple ex 270/330, 2G      active Marnie's Impidimp 70/70, 2D
    #     bench  Ogerpon ex 4G, Meowth ex,     bench  Froslass, **Morgrem 2D**,
    #            Ogerpon ex 3G, Ogerpon ex 2G,        Froslass, Impidimp 1D,
    #            Fezandipiti ex                       **Munkidori 1D**
    #
    # The agent played Boss's Orders on the MORGREM and knocked it out: one prize
    # for the highest link of the ex line, which is what `ex_preevo_takes_priority`
    # is written to do (12000 of `tier_ko` lifted to 19500, plus 700 of the line
    # band -> 20200, over 6450 for the Munkidori). They rebuilt the line and won.
    # Every recorded loss to this list ends the same way, and never to the
    # Grimmsnarl ex: it is the two abilities behind it that take the game.
    #
    # THE PREMISE OF CUTTING THE LINE DOES NOT HOLD HERE. That rule pays 19500
    # because a two-prize ex attacker we cannot answer decides the game by
    # itself; Marnie's Grimmsnarl ex is 320 HP and WEAK TO GRASS, so Myriad Leaf
    # Shower doubles into it -- the benched Teal Mask Ogerpon ex on four Grass
    # reads 300-420 against an effective 300 (their own Freezing Shroud takes 20
    # off a body that prints an Ability). The answer was already parked on our
    # bench. What was NOT answered is the pair of abilities that had been
    # grinding us down all game and that no evolution step gates:
    #
    #   * Froslass, "Freezing Shroud" -- 20 per round onto EVERY body of ours,
    #     because every body of ours prints an Ability;
    #   * Munkidori, "Adrena-Brain" -- 30 counters MOVED, once per turn per copy,
    #     onto whichever of our Pokemon it closes a knockout on, with their own
    #     Froslass reloading its ammunition every checkup.
    #
    # Munkidori is the more dangerous of the two because it AIMS: the drip is
    # arithmetic we can plan around, the move is what turns a body we had counted
    # as surviving into a corpse. Hence Munkidori, then the Froslass that feeds
    # it, then the Snorunt that becomes the next Froslass
    # (MARNIE_ENGINE_GUST_RANK).
    #
    # AND ONLY WITH THE RESERVE ON THE BENCH. `marnie_engine_first` is False
    # while our ACTIVE is the only body that covers a Grimmsnarl ex: there the
    # line rule keeps its 19500 and its reason, because the active can be knocked
    # out and then nothing covers it. `can_ko` gates each rung for the reason the
    # whole file repeats -- a gust that takes no prize is a free retreat we hand
    # them -- so a Munkidori we cannot finish yields to the Froslass we can.
    #
    # `max` and not `+`: the floor is BOSS_SCORE_MARNIE_ENGINE_FIRST, so that
    # whatever tier the three engine bodies happen to sit in, the order between
    # them is the user's and not the stage table's -- a Stage 1 Froslass outranks
    # a Basic Munkidori by 3000 on tier alone. Anything that already scored
    # ABOVE the floor keeps its score untouched, which is how `gust_wins_the_game`
    # survives this rung.
    _Adjustment("marnie_the_engine_before_the_line",
            lambda c, s: (c.marnie_engine_first and c.can_ko
                          and c.card_id in MARNIE_ENGINE_GUST_RANK),
            lambda c, s: max(s, BOSS_SCORE_MARNIE_ENGINE_FIRST
                             + MARNIE_ENGINE_GUST_RANK[c.card_id])),
    # WITHOUT a KO what rules is WHO COMES UP to the active spot, not which is the
    # biggest piece on their bench. The two bands of `_gust_opponent_line` score it
    # backwards: `_gust_evolution_line` gives 800 to the FINAL EVOLUTION (Dragapult
    # ex, Typhlosion, Alakazam) -- above the 700 of the pinned Stage 1, which its own
    # docstring calls "the best disruption target" -- and `_gust_generic_tiers`
    # gives 250 to a CHARGED ex, the ceiling of its no-KO band. Without a KO that
    # means putting in front of us, and for free (Boss's pays their retreat),
    # precisely the body they wanted to attack with.
    #
    # It also contradicted the detector that JUSTIFIES the play: the DEFENSIVE gust
    # (`_bo_defensive_gust`) is worth 940 because there EXISTS on their bench a body
    # that cannot finish us off... and then the selector brought up another one.
    #
    # +1500 beats the whole no-KO band (100-1200) and does not touch the KO tiers
    # (>= 3000), which are gated by `can_ko`. `GUST_TRAP_IDS` excludes the walls
    # and the locker: their attacks cost 3, so bare they would pass as harmless and
    # they are exactly the bodies we do NOT want in front.
    _Adjustment("without_a_ko_prefer_the_dead_body",
            lambda c, s: (not c.can_ko and c.body_is_harmless
                          and c.card_id not in GUST_TRAP_IDS),
            lambda c, s: s + 1500),
    # THE KO THAT DOES NOT SAVE THE TURN (user, registro_016 step 132 vs Crustle,
    # LOST). Their active a Crustle -- immune to our ex, so our Teal Mask Ogerpon
    # ex at 90 HP does 0 from the front -- and Superb Scissors hits for 120: their
    # reply knocks it out and their LAST prize closes the game. On their bench, two
    # Dwebble (70 HP, a real KO for 1 prize) and a Mega Kangaskhan ex: 300 HP, ONE
    # energy of the three its attack costs, and a retreat cost of three it cannot
    # pay. The agent gusted a Dwebble, took its prize, the Crustle came straight
    # back to the active spot and we lost on the reply.
    #
    # The gap is that `tier_ko` treats a gust KO as if it emptied the active spot.
    # It does not: the corpse leaves and the opponent PROMOTES whatever they like,
    # so the body that threatens us is back in front for free. A KO that neither
    # wins the game nor removes that body buys one prize and hands the same board
    # back. Gusting the trap instead spends their whole turn: it cannot attack us,
    # it cannot retreat, and it is a 3-prize body parked where we can chip it down.
    #
    # Gated on the plan saying their reply CLOSES the game (`op_wins_next`, that is
    # MODE_DENY), which is what makes "one more prize" worthless. `wins_now` still
    # rules above with its 100000: if the KO ends the game, it ends the game. The
    # 40000 clears the KO band (10 tiers x 3000 plus the line bonus) and stays
    # under it. Prizes only break ties BETWEEN traps, which is the reading of the
    # record: the Mega worth 3 is the one to park. Deck-agnostic.
    _Adjustment("under_denial_the_trap_beats_the_small_ko",
            lambda c, s: (s > 0 and c.op_wins_next and not c.wins_now
                          and c.traps_their_turn),
            lambda c, s: s + 40000 + c.prizes * 100),
    # vs Crustle, the Dwebble is NEVER gusted (wall fodder)... UNLESS the opposing
    # active is a WALL that cancels our attacker and that Dwebble is a real KO
    # (user, episode 88620891 step 78, LOST): active Hydrapple ex against a Crustle
    # immune to ex, with two knockable Dwebble on the bench. The original veto (log
    # 86339758) avoids spending Boss's chasing fodder when there is something better
    # to do; here there is NOTHING better -- attacking from the front does 0 and the
    # turn closes with no prizes. With the wall in front, the knockable Dwebble is
    # the ONLY prize of the turn and it also denies a future Crustle.
    _Adjustment("forbid_dwebble_vs_crustle",
            lambda c, s: (AGENT_STATE.op_is_crustle_deck
                          and c.card_id in (Dwebble_Grass, Dwebble_Fighting)
                          and not (c.wall_blocks_active and c.can_ko)),
            lambda c, s: SCORE_FORBID),
    # FREE retreat without a KO: the opponent sends it back to the bench at no
    # cost; it is only worth gusting when it is a real KO.
    _Adjustment("forbid_free_retreat_without_ko",
            lambda c, s: c.rc0 <= 0 and not c.can_ko,
            lambda c, s: SCORE_FORBID),
]

__all__ = [
    '_boss_val_de',
    '_boss_empty_gust',
    '_boss_first_turn_yields',
    '_boss_yields_to_dig',
    '_boss_unlock_gust',
    '_boss_reason_with_prize',
    '_gust_is_basic',
    '_v_gust_net_stuck',
    '_v_gust_relay_seat',
    '_gust_relay_cashes_the_seat',
    '_gust_relay_seat_on_their_bench',
    '_gust_evolution_line',
    '_gust_generic_tiers',
    '_gust_opponent_line',
    '_ProjectedBody',
    '_marnie_grimmsnarl_projection',
    '_marnie_bench_answers_the_grimmsnarl',
    '_RULES_GUST_NUISANCE',
    '_ADJUST_GUST_NUISANCE',
    '_gust_relieves_the_attacker',
    '_boss_gives_away_alakazam_line',
    '_boss_gust_without_purpose',
    '_CtxGustObjetivo',
    '_ctx_gust_target',
    '_grass_unlocks_active_retreat',
    '_ADJUST_GUST_OFFENSIVE',
]
