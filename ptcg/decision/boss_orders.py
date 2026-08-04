"""Boss's Orders: how much playing it is worth and who to gust.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.cards.ids import Dwebble_Fighting, Dwebble_Grass, EX_PREEVO_IDS, GUST_TRAP_IDS, SCORE_FORBID, THREAT_PREEVO_IDS
from ptcg.calc.opponent import _alakazam_attacker_relief, _op_active_is_harmless, _op_body_is_harmless
from ptcg.calc.energy import _can_attack_eff, _grass_attach_unit, _retreat_grass_units
from ptcg.calc.damage import _attacker_base_damage, _bench_attacker_best_damage, _bench_attacker_can_ko, _our_effective_damage
from ptcg.calc.card import prize_count_op
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.ids import Basic_Grass_Energy, Bayleef, DUNSPARCE_IDS, Dipplin, EX_PREEVO_IDS, Fezandipiti_ex, Hydrapple_ex, Meganium, OUR_EX_IDS, RETREAT_COST, THREAT_PREEVO_IDS, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calc.board import _active_of
from ptcg.calc.energy import _grass_mult
from ptcg.calc.damage import _ko_not_guaranteed
from dataclasses import dataclass
from ptcg.cards.ids import ALAKAZAM_ATTACKER_IDS, ALAKAZAM_LINE_IDS, Abra, Alakazam_ex, Boss_Orders, Budew, Cyndaquil, Dragapult_ex, Drakloak, Dreepy, Dwebble_Fighting, Dwebble_Grass, EX_PREEVO_IDS, Froslass, GUST_TRAP_IDS, Hydrapple_ex, Iron_Thorns_ex, Kadabra, Latias_ex, Lillie_Determination, Meowth_ex, Munkidori, Quilava, SCORE_FORBID, Snorunt, THREAT_PREEVO_IDS, Teal_Mask_Ogerpon_ex, Typhlosion
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
    and the walls that cancel our attacker from the front."""
    v = ctx.supp_values
    return (ctx.win_via_boss_gust or ctx.gust_2prize_via_boss
            or ctx.boss_win_via_bench or ctx.boss_deny_alakazam_line
            or ctx.boss_prize_rank >= 1 or ctx.boss_ko_threat_preevo
            or ctx.boss_dodge_redirect or ctx.boss_defensive_gust
            or ctx.op_has_ability_immune_active or ctx.op_has_ex_immune_active
            or bool(v.get('_boss_deny_evo'))
            or bool(v.get('_boss_gust_key_bench')))


def _gust_is_basic(card_id):
    data = card_table.get(card_id)
    return (data is not None
            and not getattr(data, 'stage1', False)
            and not getattr(data, 'stage2', False))


def _v_gust_net_stuck(c):
    v = 500 + c.stall_diff * 100
    # Tie-break (user): between targets that jam things up EQUALLY, avoid bringing
    # up the PRE-EVOLUTION of the opponent's main attacker (it could evolve and
    # attack from the active spot). A small penalty that only breaks ties.
    if c.card_id in THREAT_PREEVO_IDS or c.card_id in EX_PREEVO_IDS:
        v -= 50
    return v


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
            # The active FINISHES with that Grass: attacking with it comes first.
            return False, False
    # The attached energy is discarded when paying the retreat: the Grass on the
    # field after retreating is approximated with the current one (net ~0).
    grass_after = max(0, total_grass - _retreat_grass_units(rc))
    if _bench_attacker_can_ko(my_state, opa, meganium_active, total_grass,
                              bench_count, grass_after, neutral_zone):
        return True, False
    if active_can_attack:
        return False, False
    # The "do not swap an ex for a worse body" guard (mirror of the retreat
    # scorer): the body coming up must endure at least what the ex has left.
    min_hp = (act.hp or 0) if act.id in OUR_EX_IDS else 0
    chip = _bench_attacker_best_damage(
        my_state, opa, meganium_active, bench_count, grass_after,
        neutral_zone, min_body_hp=min_hp)
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


def _ctx_gust_target(card, o, my_state, op_state, state, hand_counts,
                       total_grass, bench_count, neutralization_zone_active,
                       op_is_alakazam, op_latias, op_dragapult_line,
                       op_typhlosion_line, my_prize=6):
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
        eff_after = eff_e + (_grass_attach_unit() if can_attach else 0)
        dmg = 0
        if atk.id == Hydrapple_ex and eff_after >= 2:
            dmg = 30 + 30 * total_grass
        elif atk.id == Dipplin and eff_after >= 1:
            dmg = 20 * bench_count
        elif atk.id == Teal_Mask_Ogerpon_ex and eff_after >= 3:
            o_e = energy
            m_e = len(atk.energies) + (1 if can_attach else 0)
            dmg = 30 + 30 * (o_e + m_e)
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
        body_is_harmless=_op_body_is_harmless(card))


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
    _Adjustment("ex_preevo_takes_priority",
            lambda c, s: (c.can_ko and c.energy >= 1 and not c.is_exmega
                          and c.card_id in EX_PREEVO_IDS),
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
    '_gust_evolution_line',
    '_gust_generic_tiers',
    '_gust_opponent_line',
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
