"""The TURN PLAN: what the prize count says the turn is FOR.

Why this module exists (user, registro_013 steps 126-145 vs the mirror, WON
suboptimally). Board at the start of our turn 13: ONE prize left on each side --
match point for both players. Our active Teal Mask Ogerpon ex carried 4 energies,
Boss's Orders and a Grass were in hand, and on the opponent's bench sat an
Ogerpon ex with 4 energies (Myriad 30+30*(4+4) = 270 >= 210) and a Tapu Bulu with
2 (210 >= 140). Boss's Orders + attack CLOSED THE GAME on the second action.

The agent instead spent NINETEEN actions -- Bug Catching Set, two benched
Ogerpon, two Teal Dances, an Ultra Ball, an Unfair Stamp that handed the opponent
a fresh hand, a Fezandipiti -- and only won at the end because it managed to pile
8 energies onto the active and reach exactly the 330 of the opposing Hydrapple
ex. One missing energy and the opponent, also at one prize, wins on the reply.

The winning gust WAS detected (`_win_via_boss_gust` was True). What killed it was
an ORDERING veto that never asked what the turn was for: `yields_to_unfair_stamp`
sits above `winning_gust` in `_RULES_BOSS_PLAY`, so Boss's scored -1. The Stamp
"goes first" is a sound rule when the turn is about resources; it is nonsense
when the turn is about ending the game.

That is the gap this module fills. Every "does this win?" flag already existed --
`_active_attack_wins_now`, `_win_via_boss_gust`, `_win_ko_active_via_promote` --
but each lived alone, consulted by whichever rule remembered it. Nothing put the
prize count in front of the turn and answered, ONCE and BEFORE the first decision:

  * can we CLOSE the game this turn, and along which route?
  * if not, how many prizes can we take?
  * and how many do they take on the reply -- do they close it themselves?

`TurnPlan` is that answer, and `mode` is the sentence the rest of the turn reads.

DESIGN DECISION: this module does NOT recompute the lethal routes. The flags it
consumes carry years of measured corrections (guaranteed KO vs Tenacious Body,
the suicidal finisher that draws, prize denial from Pecharunt/Mega Gengar) and a
second implementation would drift away from them silently. What is genuinely new
here is the DEFENSIVE half -- the prizes the opponent takes on their next turn --
and the single sentence that combines both halves.
"""

from dataclasses import dataclass

from ptcg.calc.card import prize_count, prize_count_op
from ptcg.calc.damage import (_attacker_base_damage, _ko_not_guaranteed,
                              _op_active_attack_damage_to,
                              _our_effective_damage)
from ptcg.calc.energy import (_grass_attach_unit, _grass_mult,
                              _reachable_grass_for, _retreat_grass_to_discard)
from ptcg.cards.ids import Basic_Grass_Energy, Boss_Orders

# The four sentences a turn can be under. They are ordered by urgency: the first
# one that applies wins, because a turn that ENDS the game does not care what the
# opponent would have done, and a turn where they close it does not care about
# development.
MODE_WIN_NOW = 'WIN_NOW'    # a lethal route exists: execute it, everything else is noise
MODE_DENY = 'DENY'          # no lethal route and THEY close it on the reply
MODE_RACE = 'RACE'          # no lethal route, but we take prizes and survive
MODE_DEVELOP = 'DEVELOP'    # nothing decisive today: build the board

# The routes that close the game, cheapest first. "Cheapest" = fewest resources
# committed, which is also the most robust: a route that spends neither the
# Supporter nor the turn's attachment cannot be broken by a bad draw.
ROUTE_ACTIVE = 'ACTIVE'              # attack the opposing active as it stands
ROUTE_PROMOTE = 'PROMOTE'            # retreat -> promote the bench finisher -> attack
ROUTE_GUST = 'GUST'                  # Boss's Orders on a bench target -> attack


@dataclass(frozen=True)
class TurnPlan:
    """What the prize count says about THIS turn. Read-only for every consumer."""

    my_prize: int
    op_prize: int

    # --- offence ---------------------------------------------------------
    # '' when no route closes the game; otherwise one of the ROUTE_* constants.
    win_route: str
    # The route spends the turn's Supporter slot (Boss's Orders in hand).
    win_needs_supporter: bool
    # The route is NOT lethal with the energy already on the attacker: it needs a
    # charge this turn (the manual attachment, a Teal Dance, a Ripening Charge)
    # before the finisher exists. It is what tells the two shapes of a winning
    # gust apart, and the order of the turn depends on which one it is: with the
    # KO already there, gusting FIRST is the play; with the KO one energy away,
    # charging first is (registro_012 step 227, the Myriad combo: Teal Dance
    # leaves the Ogerpon at 5 and only then does the Bellibolt ex die).
    win_needs_charge: bool
    # Prizes we can take TODAY without necessarily winning (0 = a sterile turn on
    # the offence side). It is what tells a RACE apart from a DEVELOP.
    prizes_today: int

    # --- defence ---------------------------------------------------------
    # Prizes the opposing ACTIVE takes from our ACTIVE on their next turn (0 = our
    # active survives the projection).
    op_prizes_next: int
    # ... and that closes THEIR count: we lose on the reply unless this turn
    # changes the picture.
    op_wins_next: bool

    mode: str

    @property
    def wins_this_turn(self) -> bool:
        """Is there a route that ENDS the game this turn?

        The single question the ordering vetoes have to ask before stepping
        aside for a resource card.
        """
        return bool(self.win_route)

    @property
    def lethal_gust(self) -> bool:
        """The winning route goes through Boss's Orders: the Supporter slot of
        this turn is SPOKEN FOR and no other Supporter may take it."""
        return self.win_route == ROUTE_GUST

    @property
    def gust_closes_it_now(self) -> bool:
        """Boss's Orders IS the finisher: the target dies to the energy already
        on the attacker, so nothing has to happen before the gust.

        The condition for giving the gust the priority of an attack. When the KO
        is still one charge away the gust must WAIT for that charge -- the play
        order is Teal Dance, then Boss's, then attack -- which is why the
        distinction is a field and not an afterthought.
        """
        return self.lethal_gust and not self.win_needs_charge

    def denial_saves_the_game(self, body_prizes: int) -> bool:
        """Would putting a `body_prizes`-prize body in front instead of the
        current active take the win away from the opponent's reply?

        MEASURED AND REVERTED as a rule, TWICE, KEPT as a primitive (ago 2026).
        Its one consumer was an exception to the `my_prize >= 3` gate of the
        sacrifice pivot in `ptcg/turn/options/retreat.py`: at 1-2 prizes, with no
        route and no prize to take, retreat the doomed 2-prize ex and put a
        1-prize body in front so their reply does not close the game. Self-play
        against HEAD, 4000 games per arm:

            plan only (offence)              51.1% / 49.2% / 50.4%   premios +0.08 / -0.03 / +0.00
            + this pivot, BLIND projection   48.9%                   premios -0.07
            + this pivot, SCALED projection  48.9% / 49.1%           premios -0.06 / -0.06

        The second round is the one that settles it. The first measurement could
        be dismissed -- the pivot was firing off `op_wins_next`, and with the
        printed-damage projector that flag was true in 1.0% of decisions and
        often for the wrong reason. Once the projection was corrected
        (`ptcg/cards/op_scaling.py`, lethal reply seen in 37.4% of decisions
        instead of 5.2%) the rule fired on READINGS THAT WERE RIGHT and still
        lost the same ground. Conceding tempo to hand over a smaller corpse is
        not a good trade for this deck; the `my_prize >= 3` gate was right for a
        reason its own comment only half stated.

        The mode and this method stay as DATA the plan publishes, not a rule --
        the same treatment `_op_attack_deficit` got when its graded version
        measured inert.

        The arithmetic of MODE_DENY. It is only true when all four things hold:
        this turn takes no prize and closes nothing, their attack knocks our
        active out, that KO CLOSES their count -- and the cheaper body's prizes
        do NOT. That last clause is the one that matters: at `op_prize` 1 every
        corpse ends the game and conceding a smaller one buys nothing, so the
        pivot has to stay switched off there and let the turn be spent on
        anything with a chance instead.
        """
        return (not self.wins_this_turn
                and self.prizes_today == 0
                and self.op_wins_next
                and self.op_prize > body_prizes)


# A plan with nothing decided: what a consumer sees when there is no plan yet
# (a unit test that builds its context by hand, an observation outside our turn).
# Every flag is off, so every rule keeps the behaviour it had before this module.
NO_PLAN = TurnPlan(
    my_prize=6, op_prize=6, win_route='', win_needs_supporter=False,
    win_needs_charge=False, prizes_today=0, op_prizes_next=0,
    op_wins_next=False, mode=MODE_DEVELOP,
)


def _our_damage_to(attacker, target, extra_attach, total_grass, bench_count,
                   meganium_in_play, neutralization_zone):
    """EFFECTIVE damage our `attacker` does to `target` counting `extra_attach`
    Grass still to be attached this turn.

    Same two-step shape as everywhere else in the file: the base table
    (`_attacker_base_damage`) and then the central evaluator
    (`_our_effective_damage`), which is the one that knows about immunities,
    weakness, the Sturdy cap and the Neutralization Zone. Never reimplement the
    second step: `can_ko` flags that skipped it used to declare KOs that the
    simulator refused.
    """
    if attacker is None or target is None:
        return 0
    effective = (len(attacker.energies) * _grass_mult()
                 + extra_attach * _grass_attach_unit())
    base = _attacker_base_damage(
        attacker.id, target, effective, grass_scale=total_grass,
        teal_self_energy=effective, bench_count=bench_count)
    if base <= 0:
        return 0
    return _our_effective_damage(attacker, target, base, meganium_in_play,
                                 neutralization_zone)


def _charge_this_turn(pokemon, state, my_state, hand_counts, field_counts,
                      extra_discard_grass=0, abilities_off=False):
    """PHYSICAL Grass this turn can still put on `pokemon`, capped at ONE.

    The SOURCE is the whole answer of `_reachable_grass_for` (hand, discard
    through Night Stretcher, and the card a retreat is about to pay); the CAP is
    deliberate and keeps the previous semantics of this file. A second
    attachment in the same turn is often legal, but where it lands is decided by
    the energy scorer and its physical caps (`_ogerpon_base_phys_cap`), and
    Myriad Leaf Shower scales with every energy: projecting two would let the
    plan claim damage the turn will never do.
    """
    return min(1, _reachable_grass_for(pokemon, state, my_state, hand_counts,
                                       field_counts, extra_discard_grass,
                                       abilities_off))


def _prizes_we_can_take(my_state, op_state, state, hand_counts, field_counts,
                        total_grass, bench_count, meganium_in_play,
                        neutralization_zone, boss_in_hand, can_switch,
                        abilities_off):
    """Best number of prizes this turn's ATTACK can take (0 = none).

    Two routes, because a turn has two ways of putting an attacker in front of
    the opponent: our ACTIVE as it stands, and the body we PROMOTE by retreating
    it. The second one used to be left out ("the routes that matter arrive as
    measured flags") and that hole is what registro_004 step 45 walked into: an
    active one energy short of Myriad, a fresh Ogerpon ex on the bench and a
    Night Stretcher in hand: `prizes_today` said 0, the turn read DEVELOP, the
    Supporter was spent on a gust with no attack behind it and the turn ended
    with a free prize on the board. See `_prizes_via_promote`.
    """
    best = _prizes_via_active(my_state, op_state, state, hand_counts,
                              field_counts, total_grass, bench_count,
                              meganium_in_play, neutralization_zone,
                              boss_in_hand, abilities_off)
    if can_switch:
        best = max(best, _prizes_via_promote(
            my_state, op_state, state, hand_counts, field_counts, total_grass,
            bench_count, meganium_in_play, neutralization_zone, boss_in_hand,
            abilities_off))
    return best


def _best_prize_against(attacker, targets, extra, total_grass, bench_count,
                        meganium_in_play, neutralization_zone):
    """Prizes of the best target `attacker` knocks out, 0 if it knocks out none."""
    best = 0
    for target in targets:
        if target is None or _ko_not_guaranteed(target):
            continue
        damage = _our_damage_to(attacker, target, extra, total_grass,
                                bench_count, meganium_in_play,
                                neutralization_zone)
        if damage > 0 and damage >= (target.hp or 0):
            best = max(best, prize_count_op(target))
    return best


def _targets(op_state, boss_in_hand):
    """The bodies this turn's attack can reach: their active always, their bench
    only when Boss's Orders is really playable."""
    targets = list(op_state.active or [])
    if boss_in_hand:
        targets += [p for p in (op_state.bench or []) if p is not None]
    return targets


def _prizes_via_active(my_state, op_state, state, hand_counts, field_counts,
                       total_grass, bench_count, meganium_in_play,
                       neutralization_zone, boss_in_hand, abilities_off):
    attacker = my_state.active[0] if my_state.active else None
    if attacker is None:
        return 0
    extra = _charge_this_turn(attacker, state, my_state, hand_counts,
                              field_counts, abilities_off=abilities_off)
    return _best_prize_against(attacker, _targets(op_state, boss_in_hand),
                               extra, total_grass, bench_count,
                               meganium_in_play, neutralization_zone)


def _prizes_via_promote(my_state, op_state, state, hand_counts, field_counts,
                        total_grass, bench_count, meganium_in_play,
                        neutralization_zone, boss_in_hand, abilities_off):
    """Prizes from the PROMOTE route: retreat, promote a benched body, attack.

    The retreat is not only a cost here, it is a SOURCE: paying it discards the
    Grass off the retreating body, and with a Night Stretcher in hand that card
    comes back and charges the body we promote (`_retreat_grass_to_discard`).
    That is the whole line of registro_004 step 45.

    Conservative on purpose: the retreat has to be payable with the energy the
    active carries, and the energy it pays LEAVES the field, so `total_grass` is
    lowered before scaling anything with it -- the same correction
    `_retreat_grass_units` documents.
    """
    active = my_state.active[0] if my_state.active else None
    if active is None or getattr(state, 'retreated', False):
        return 0
    if getattr(my_state, 'asleep', False) or getattr(my_state, 'paralyzed', False):
        return 0
    discarded = _retreat_grass_to_discard(active)
    if discarded * _grass_attach_unit() > len(active.energies):
        return 0            # the retreat cannot be paid: there is no route

    targets = _targets(op_state, boss_in_hand)
    grass_after = max(0, total_grass - discarded * _grass_attach_unit())
    best = 0
    for body in (my_state.bench or []):
        if body is None:
            continue
        extra = _charge_this_turn(body, state, my_state, hand_counts,
                                  field_counts,
                                  extra_discard_grass=discarded,
                                  abilities_off=abilities_off)
        best = max(best, _best_prize_against(
            body, targets, extra, grass_after, bench_count, meganium_in_play,
            neutralization_zone))
    return best


def _gust_is_lethal_without_charging(my_state, op_state, my_prize, total_grass,
                                     bench_count, meganium_in_play,
                                     neutralization_zone):
    """Does some body on the opposing bench die to the energy the attacker
    ALREADY carries, for at least the prizes we are missing?

    Same walk as the winning-gust detector, with the pending charges deliberately
    set to zero. That single difference is what separates "gust now and win" from
    "charge, then gust, then win", and the play order of the turn hangs on it.
    """
    attacker = my_state.active[0] if my_state.active else None
    if attacker is None:
        return False
    for target in (op_state.bench or []):
        if target is None or _ko_not_guaranteed(target):
            continue
        if prize_count_op(target) < my_prize:
            continue
        damage = _our_damage_to(attacker, target, 0, total_grass, bench_count,
                                meganium_in_play, neutralization_zone)
        if damage > 0 and damage >= (target.hp or 0):
            return True
    return False


def _we_knock_out_their_active(my_state, op_state, state, hand_counts,
                               field_counts, total_grass, bench_count,
                               meganium_in_play, neutralization_zone,
                               abilities_off):
    """Does our attack this turn knock out the opposing ACTIVE?

    The projection of their reply is built on the body standing in front of us,
    and that body is not there tomorrow if we knock it out today. Without this
    check `op_wins_next` was answering with a Pokemon on its way to the discard:
    measured over 200 self-play games, 379 of the energy decisions flagged as
    "no tomorrow" were turns where our active already secured the KO, which is
    the case `_tapu_future_charge` is built for -- charging the bench body for a
    turn that does exist.

    Gusted bench targets do NOT count: knocking one of those out leaves their
    active exactly where it is, and its attack with it.
    """
    attacker = my_state.active[0] if my_state.active else None
    target = op_state.active[0] if op_state.active else None
    if attacker is None or target is None or _ko_not_guaranteed(target):
        return False
    extra = _charge_this_turn(attacker, state, my_state, hand_counts,
                              field_counts, abilities_off=abilities_off)
    damage = _our_damage_to(attacker, target, extra, total_grass, bench_count,
                            meganium_in_play, neutralization_zone)
    return damage > 0 and damage >= (target.hp or 0)


def _opponent_reply(my_state, op_state, op_hand_count):
    """(prizes they take from our ACTIVE next turn, does that close their count).

    It projects ONLY the opposing active hitting our active, which is the same
    scope as `active_doomed_real` elsewhere in the file: their bench swaps and
    their gusts need a hand we cannot see, and inventing them would make every
    turn look lost.

    `scaled=True` is what makes this half worth anything. Without it the
    projector returns the number PRINTED on the card, and for the attacks that
    scale with the board that number is a placeholder: in registro_013 the
    opposing Hydrapple ex hit for 270 and the projection said 30. Measured over
    200 self-play games, the blind reading found a lethal reply in 5.2% of
    decisions and the scaled one in 37.4% -- the difference between a defensive
    half that never fires and one that sees the board. This is the ONLY consumer
    of the flag on purpose; the reason is in `_op_active_attack_damage_to`.
    """
    my_active = my_state.active[0] if my_state.active else None
    op_active = op_state.active[0] if op_state.active else None
    if my_active is None or op_active is None:
        return 0, False
    damage = _op_active_attack_damage_to(op_active, my_active, op_hand_count,
                                         scaled=True)
    if damage < (my_active.hp or 0):
        return 0, False
    return prize_count(my_active), True


def build_turn_plan(*, my_prize, op_prize, my_state, op_state, state,
                    hand_counts, total_grass, bench_count, meganium_in_play,
                    neutralization_zone, op_hand_count,
                    active_attack_wins_now, win_via_boss_gust,
                    win_ko_active_via_promote,
                    field_counts=None, can_switch=True, abilities_off=False):
    """Builds the plan for the CURRENT observation of our turn.

    It is rebuilt on every call to `agent()` and not frozen at the first one: the
    board changes inside the turn (a Teal Dance adds energy, an evolution adds a
    body) and a plan that answered "no lethal route" at action 1 would still be
    saying it at action 9, which is exactly the blindness this module exists to
    remove.

    The three `*_wins_now` inputs are the flags `agent()` has already computed
    for this observation; see the module docstring for why they are consumed and
    not recomputed.
    """
    boss_playable = (hand_counts.get(Boss_Orders, 0) >= 1
                     and not state.supporterPlayed)

    # Route order = cost order. Attacking with the active as it stands commits
    # nothing; the promotion pays a retreat; the gust burns the turn's Supporter.
    # When two routes win, the cheapest is the one the rest of the turn commits
    # to, so that the Supporter stays available for whatever else the turn needs.
    if active_attack_wins_now:
        win_route = ROUTE_ACTIVE
    elif win_ko_active_via_promote:
        win_route = ROUTE_PROMOTE
    elif win_via_boss_gust and boss_playable:
        win_route = ROUTE_GUST
    else:
        win_route = ''

    win_needs_charge = (
        win_route == ROUTE_GUST
        and not _gust_is_lethal_without_charging(
            my_state, op_state, my_prize, total_grass, bench_count,
            meganium_in_play, neutralization_zone))

    prizes_today = _prizes_we_can_take(
        my_state, op_state, state, hand_counts, field_counts, total_grass,
        bench_count, meganium_in_play, neutralization_zone, boss_playable,
        can_switch, abilities_off)

    # Their reply is only THEIRS if the body that would make it survives our
    # turn. See `_we_knock_out_their_active`.
    if _we_knock_out_their_active(my_state, op_state, state, hand_counts,
                                  field_counts, total_grass, bench_count,
                                  meganium_in_play, neutralization_zone,
                                  abilities_off):
        op_prizes_next, op_kos_our_active = 0, False
    else:
        op_prizes_next, op_kos_our_active = _opponent_reply(
            my_state, op_state, op_hand_count)
    op_wins_next = op_kos_our_active and op_prize <= op_prizes_next

    if win_route:
        mode = MODE_WIN_NOW
    elif op_wins_next:
        mode = MODE_DENY
    elif prizes_today >= 1:
        mode = MODE_RACE
    else:
        mode = MODE_DEVELOP

    return TurnPlan(
        my_prize=my_prize, op_prize=op_prize,
        win_route=win_route,
        win_needs_supporter=(win_route == ROUTE_GUST),
        win_needs_charge=win_needs_charge,
        prizes_today=prizes_today,
        op_prizes_next=op_prizes_next,
        op_wins_next=op_wins_next,
        mode=mode,
    )


def plan_of(ctx):
    """The plan carried by a decision context, or `NO_PLAN`.

    Contexts are built by hand in dozens of unit tests and some of them wrap the
    real one (`_CtxLillie`). Reading the field through here means a context
    without a plan behaves exactly as it did before the plan existed.
    """
    return getattr(ctx, 'turn_plan', None) or NO_PLAN


__all__ = [
    'MODE_WIN_NOW', 'MODE_DENY', 'MODE_RACE', 'MODE_DEVELOP',
    'ROUTE_ACTIVE', 'ROUTE_PROMOTE', 'ROUTE_GUST',
    'TurnPlan', 'NO_PLAN', 'build_turn_plan', 'plan_of',
]
