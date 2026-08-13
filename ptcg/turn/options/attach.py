"""Scoring the ATTACH options: WHERE this turn's one energy goes.

The manual attachment happens ONCE per turn, so this branch is not really
choosing between energies -- it is choosing the body, and every option in the
menu is the same card pointed at a different target.

THE SCORE COMES FROM ELSEWHERE. The ranking of bodies is `energy_score` (see
`ptcg/turn/energy.py`), which knows the caps, the matchups and who is worth
feeding. What this branch adds is the situational corrections that only make
sense at the moment of attaching:

  * DOES THIS ATTACHMENT BUY SOMETHING TODAY -- it finishes the game, it
    unlocks an attack, it pays a retreat that promotes a finisher. Those beat
    any development charge.
  * DOES A FREE ROUTE ALREADY COVER IT -- Teal Dance and Ripening Charge attach
    energy without spending the turn's attachment. Where an ability can charge
    this body, the manual attachment should go somewhere the abilities cannot
    reach (`_attach_yields_to_teal_dance`).
  * THE OPENING VETO -- on our first turn, energy poured into the starting
    attacker is usually wasted. Note the exceptions written into it: a charge
    that WINS today, one that pays the retreat fee to hide an ex behind a
    one-prize wall, and Tapu Bulu against Crustle, where it is the only body
    that can damage the wall at all.

The recurring shape of all three: a general "do not spend it here" rule with
NAMED exceptions, each carrying the game that produced it. When adding one,
extend the exception list rather than weakening the rule.

Extracted VERBATIM from the `agent()` chain: it unpacks from the context only
the fields it reads and returns only the ones it reassigns.
"""

from cg.api import AreaType
from ptcg.calc.card import get_card
from ptcg.calc.energy import _can_attack_eff, _grass_ability_slots, _grass_attach_unit
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Chikorita, Dipplin, Fezandipiti_ex, Hydrapple_ex, Lillie_Determination, Meowth_ex, Pinsir, RETREAT_COST, SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK, SCORE_CHARGE_FUTURE_OGERPON, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball
from ptcg.cards.scoring import MAIN_ATTACKERS
from ptcg.state.agent_state import AGENT_STATE


def _ogerpon_still_short(my_state):
    """Is there a Teal Mask Ogerpon ex in play still short of Myriad Leaf Shower?

    The question behind it is "is there a body on our field that this Grass is
    really FOR, today or tomorrow". An Ogerpon ex that already covers its cost is
    not one: charging it further is the overcharge that half the per-matchup caps
    exist to stop, and reserving a Grass for a Teal Dance that would only
    overcharge it buys nothing but the draw.
    """
    for _p in list(my_state.active or []) + list(my_state.bench or []):
        if (_p is not None and _p.id == Teal_Mask_Ogerpon_ex
                and not _can_attack_eff(_p.id, len(_p.energies))):
            return True
    return False


def _is_our_first_turn(state):
    """Our first turn of the game, whichever seat we play from."""
    return ((state.turn == 1 and AGENT_STATE.we_go_first)
            or (state.turn == 2 and not AGENT_STATE.we_go_first))


def _lillie_route_next_turn(hand_counts):
    """Can the hand still put a Lillie's Determination on the table TOMORROW?

    The three routes, exactly as the user spelled them out: the Supporter itself
    in hand, a Meowth ex in hand (Last-Ditch Catch fetches it when the body is
    benched) or an Ultra Ball in hand (which digs the Meowth ex out). A Meowth ex
    ALREADY on the bench is deliberately NOT a route: Last-Ditch Catch triggers
    on playing the body from hand, so a Meowth that is already sitting there
    fetches nothing tomorrow.
    """
    return (hand_counts.get(Lillie_Determination, 0) >= 1
            or hand_counts.get(Meowth_ex, 0) >= 1
            or hand_counts.get(Ultra_Ball, 0) >= 1)


def score_play(tc, o, score):
    """Returns the score of `o`. It may return `_SALTAR`."""
    _attach_yields_to_teal_dance = tc._attach_yields_to_teal_dance
    _attach_enable_retreat_attack = tc._attach_enable_retreat_attack
    _attach_enable_retreat_ko = tc._attach_enable_retreat_ko
    _attach_reaches_no_cost = tc._attach_reaches_no_cost
    _bcs_playable_in_hand = tc._bcs_playable_in_hand
    _charge_active_enables_attack = tc._charge_active_enables_attack
    _charge_active_finishes = tc._charge_active_finishes
    _ft_wall_charge_active = tc._ft_wall_charge_active
    _opening_sac_charge_active = tc._opening_sac_charge_active
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _lucario_sac_pivot = tc._lucario_sac_pivot
    _tapu_future_charge = tc._tapu_future_charge
    _tapu_sac_enable_retreat = tc._tapu_sac_enable_retreat
    _teal_dance_ko_pivot = tc._teal_dance_ko_pivot
    _teal_dance_slots = tc._teal_dance_slots
    _win_via_boss_gust = tc._win_via_boss_gust
    card = tc.card
    energy_score = tc.energy_score
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_ogerpon = tc.has_ogerpon
    itchy_pollen_active = tc.itchy_pollen_active
    my_index = tc.my_index
    my_state = tc.my_state
    obs = tc.obs
    pokemon = tc.pokemon
    scores = tc.scores
    state = tc.state

    try:
        card = get_card(obs, AreaType.HAND, o.index, my_index)
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        if card is not None and pokemon is not None:
            score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE)
            if o.inPlayArea == AreaType.ACTIVE:
        
                # vs Crustle, an ACTIVE Tapu Bulu is our MAIN attacker
                # (non-ex; the only one that damages the ex-immune wall): it
                # ALWAYS has the first charging priority, from the first turn.
                # The generic veto of "do not charge the starting active"
                # (Ogerpon/Tapu on our first turn, meant to avoid wasting energy
                # overcharging the opening attacker) must NOT degrade it:
                # without a charge, Tapu never reaches its 4 energies for Wood
                # Hammer (user, registro_002 step 17 vs Crustle, LOST: the agent
                # charged a benched Applin instead of the active Tapu Bulu). Only
                # Tapu Bulu is exempted; Ogerpon ex stays vetoed (it does not
                # damage the wall).
                _ft_veto_ids = ((Teal_Mask_Ogerpon_ex,) if AGENT_STATE.op_is_crustle_deck
                                else (Teal_Mask_Ogerpon_ex, Tapu_Bulu))
                if (((state.turn == 1 and AGENT_STATE.we_go_first) or
                        (state.turn == 2 and not AGENT_STATE.we_go_first))
                        and my_state.active and my_state.active[0] is not None
                        and my_state.active[0].id in _ft_veto_ids
                        # ...unless that charge FINISHES the game today (anti-DONK):
                        # the first-turn veto exists to avoid wasting energy, not to
                        # give up a KO.
                        and not _charge_active_finishes
                        # ...nor to block the RETREAT FEE towards the one-prize
                        # wall (`_ft_wall_charge_active`, main.py). That energy
                        # is not overcharging the opening attacker: it is what
                        # buys the swap that hides this 2-prize body behind a
                        # body that costs one.
                        and not _ft_wall_charge_active
                        # ...nor the same fee paid by the ex itself
                        # (`_opening_sac_charge_active`). This veto exists to
                        # stop the turn's energy being wasted on the opening
                        # attacker; an energy that buys the retreat is spent on
                        # the swap, not on the body.
                        and not _opening_sac_charge_active):
                    if _lucario_sac_pivot:
                        # Charging the active Ogerpon ex: when it retreats later, it
                        # keeps energy on the bench (it pays the retreat cost and
                        # leaves a charged attacker out of harm's way).
                        score = 8500
                    else:
                        score = SCORE_VETO
                elif _attach_enable_retreat_ko:
                    # An attachment that enables retreat + a bench KO (user,
                    # registro_034 step 141 vs Terrakion): it is a LETHAL line
                    # for this turn, so it scores in the band of the lethal
                    # charges (41000): above Teal Dance (31500-31600) and the
                    # bench charges (~30000), below the active's direct
                    # finisher (42000). The rest of the chain (RETREAT via the
                    # plan with can_switch, promotion, attack) is already
                    # resolved by the existing machinery once the retreat is
                    # legal.
                    #
                    # IT GOES BEFORE `_tapu_sac_enable_retreat`, AND THAT ORDER IS
                    # THE RULE. The Tapu branch below is the SPECIAL CASE this one
                    # generalises -- Tapu Bulu with four Grass, which is the whole
                    # plan of the Crustle matchup -- and it was being tested first,
                    # so on precisely the boards it covers the lethal line scored
                    # 24000 instead of 41000 and lost to a routine bench charge at
                    # 31000. Found by dumping the dry turns of
                    # `utils/wall_probe.py` against crustle_wall_6: seco_019, turn
                    # 14, active Meowth ex at 0 energy with retreat cost 1, one
                    # Grass in hand, a Tapu Bulu with four on the bench and a
                    # Crustle 170/170 in front. Grass -> active, retreat, promote,
                    # Wood Hammer 220: a prize. The agent attached to a benched
                    # Dipplin at 0 energy and ended the turn.
                    score = 41000
                elif _tapu_sac_enable_retreat:
                    # THE SPECIAL CASE OF THE BRANCH ABOVE, kept for the boards
                    # where the general detector stays quiet. Attaching to the
                    # active ex (2 prizes) to reach its retreat cost and pivot to an
                    # already charged Tapu Bulu that knocks the opposing active out
                    # (user, log 86029588 turn 16 step 148, vs Alakazam/Dunsparce).
                    # Fezandipiti ex's retreat cost is 1, so ONE Grass enables the
                    # retreat this very turn -> bring up Tapu and finish. It used to
                    # score 8000, but a BENCHED Dipplin at 0 energy scores 8150 and
                    # won the tie-break, wasting the energy on a non-attacker.
                    # Raised above any bench DEVELOPMENT -- which is not the same as
                    # above any bench CHARGE, and that gap is what made the ordering
                    # above matter.
                    score = 24000
                elif _attach_enable_retreat_attack:
                    # The same line without a KO (user, log 88162794 turns 11/13 vs
                    # Archaludon ex): the active can neither attack nor retreat and
                    # the benched attacker only does CHIP damage. The Grass goes to
                    # the ACTIVE to pay the retreat: 80-140 damage is worth more
                    # than closing the turn without attacking. Band 31200 (the one
                    # the Teal Dance branches cite as "the manual attachment"):
                    # above any bench charge (<=31150, including Ripening's on the
                    # best attacker) and below everything that enables a KO this
                    # turn (31300+, 31500, 41000).
                    score = 31200
                elif (AGENT_STATE.plan.attacker == 0 and AGENT_STATE.plan.energy
                        # The band of `_charge_active_enables_attack` (31300) is
                        # calibrated against the UB engine (31450) and Teal Dance
                        # (31500): the tie-break bonus would cross it.
                        and not _charge_active_enables_attack):
                    score += 200
        
                elif (AGENT_STATE.plan.attacker >= 1 and has_ogerpon and score > 31000
                        and not AGENT_STATE.op_is_crustle_deck and not AGENT_STATE.op_is_cornerstone_deck
                        and not (_win_via_boss_gust or _gust_2prize_via_boss)
                        # ...nor when this charge is the one that makes the active
                        # attack TODAY (a finisher or the turn's only attack).
                        and not _charge_active_finishes
                        and not _charge_active_enables_attack):
                    # Do NOT degrade the attachment to the active if there is a
                    # WINNING / 2-prize play via Boss's that leans on charging the
                    # active (user, registro_012 step 227 vs Iono): Ogerpon's Myriad
                    # Leaf Shower counts the energy on BOTH actives, so charging the
                    # active + gusting a charged Bellibolt ex knocks it out (2
                    # prizes). The winning finisher (energy_score=42000) must
                    # prevail over this downgrade (designed to avoid overcharging
                    # the active when a benched body attacks), which would otherwise
                    # erase the KO line.
        
                    _attach_active_pkmn = my_state.active[0] if my_state.active else None
                    _attach_needs_for_retreat = False
                    if _attach_active_pkmn is not None:
                        _attach_rc = RETREAT_COST.get(_attach_active_pkmn.id, 1)
                        _attach_curr_e = len(_attach_active_pkmn.energies)
                        if _attach_curr_e < _attach_rc:
                            _attach_needs_for_retreat = True
                    if not _attach_needs_for_retreat:
                        score = 7500
            else:
                if AGENT_STATE.plan.attacker == 1 + o.inPlayIndex and AGENT_STATE.plan.energy:
                    score += 200
        
                _our_first_turn_attach = ((state.turn == 1 and AGENT_STATE.we_go_first) or
                                          (state.turn == 2 and not AGENT_STATE.we_go_first))
                _active_blocked_ft = (
                    my_state.active and my_state.active[0] is not None
                    and my_state.active[0].id in (Teal_Mask_Ogerpon_ex, Tapu_Bulu))
                if _our_first_turn_attach and _active_blocked_ft and len(pokemon.energies) < 1:
                    _BENCH_ATTACKER_PRIORITY = {
                        Hydrapple_ex: 900,
                        Dipplin: 850,
                        Teal_Mask_Ogerpon_ex: 800,
                        Tapu_Bulu: 750,
                        Pinsir: 650,
                        # We prioritise the Hydrapple ex line (Applin ->
                        # Dipplin -> Hydrapple ex), which accelerates energy and
                        # charges Tapu Bulu in one turn, over the Meganium line
                        # (Chikorita).
                        Applin: 500,
                        Chikorita: 400,
                        Fezandipiti_ex: 200,
                    }
                    _bench_prio = _BENCH_ATTACKER_PRIORITY.get(pokemon.id)
                    if _bench_prio is not None:
                        score = max(score, 8000 + _bench_prio)
        
                # Never manually attach energy to a BENCHED Meowth ex: it is a
                # non-attacker and the energy is wasted. The only valid use of
                # Meowth ex for the manual attachment is on the ACTIVE, to pay its
                # retreat when needed (handled by the AreaType.ACTIVE branch via
                # energy_score). It is ALWAYS vetoed, no matter the turn or whether
                # it is the only bench target available.
                if pokemon.id == Meowth_ex:
                    score = SCORE_VETO
        
            if _bcs_playable_in_hand and not itchy_pollen_active and score > 9000 \
                    and not (_tapu_future_charge
                             and o.inPlayArea != AreaType.ACTIVE
                             and pokemon is not None
                             and pokemon.id == Tapu_Bulu) \
                    and not (_charge_active_finishes
                             and o.inPlayArea == AreaType.ACTIVE):
                # Bug Catching Set first... unless the charge to the ACTIVE
                # finishes the game this turn: the KO does not wait for a search.
                score = 9000
        
            if _teal_dance_ko_pivot and hand_counts.get(Basic_Grass_Energy, 0) <= 1:
                # Teal Dance pivot (log 85802744 turn 16): with a single Grass
                # Energy in hand, RESERVE IT for Teal Dance on the active (it
                # attaches + DRAWS and enables the cost-1 retreat to bring up the
                # non-ex attacker that knocks out the Crustle wall). Any manual
                # attachment is vetoed so it neither steals the Grass nor beats
                # Teal Dance through the ENERGY tier of the play order.
                score = SCORE_VETO
        
            # Teal Dance PRECEDES the manual attachment (user, registro_004
            # step 28, vs Mega Starmie): if we are about to charge energy
            # MANUALLY onto a Teal Mask Ogerpon ex that can STILL use Teal
            # Dance this turn (its ABILITY option is still available in this
            # very slot), the manual attachment is vetoed. Teal Dance attaches
            # the Grass AND DRAWS a card, so it is played FIRST; after using it
            # the ability disappears and, if a 2nd energy is still wanted, the
            # manual attachment scores normally on the next step. This corrects
            # the order imposed by the ENERGY tier (which made the manual
            # attachment win even though Teal Dance scores higher).
            if (score > 0
                    and pokemon is not None
                    and pokemon.id == Teal_Mask_Ogerpon_ex
                    and (o.inPlayArea, o.inPlayIndex) in _teal_dance_slots):
                score = SCORE_VETO
        
            # GENERALISATION of the previous precedence (user, registro_002
            # step 20, vs Marnie): Teal Dance does not only precede the
            # attachment on the Ogerpon ITSELF. While a Teal Dance remains
            # unused this turn, a manual attachment that is mere DEVELOPMENT
            # (the target does NOT become ready to attack with that energy)
            # yields to it. Teal Dance spends the same Grass from hand, but it
            # also DRAWS a card and does NOT consume the turn's manual
            # attachment: it is strictly better than spending the attachment
            # on a body that is not going to attack.
            #
            # In that record, the ACTIVE Ogerpon ex had already used its Teal
            # Dance that turn, so the attachment to the active was vetoed by
            # the first-turn rule and the Teal Dance of the BENCHED Ogerpon ex
            # fell into the degraded band (7500); the only target left, a
            # benched Chikorita, won with 8400 (base 8000 from energy_score +
            # development boost) and wasted the only Grass on a body that with
            # 1 energy is not an attacker.
            #
            # It is CAPPED (not vetoed) below Teal Dance's degraded band (7500)
            # instead of cancelling the play: if the ability were vetoed by
            # another route, the attachment is still playable and the turn does
            # not hang. "Ready to attack" requires a REAL ATTACKER
            # (MAIN_ATTACKERS): Chikorita/Applin/Bayleef appear in
            # ATTACK_ENERGY_REQ because of their chip attack, but they are not
            # attackers.
            #
            # Capping the score is not enough: the PLAY ORDER rules by tier and
            # the manual attachment lives in _TIER_ENERGY, while a degraded
            # Teal Dance (7500) stays in tier 0 (its promotion requires
            # >= 29000, a guard that is NOT touched: it stops a degraded Teal
            # Dance from crushing Ripening Charge by tier). That is why the
            # index is marked here and further down the attachment is left in
            # tier 0, so that within the same tier the score decides (Teal
            # Dance 7500 > capped attachment 7000).
            # Only the DEVELOPMENT BAND (< 9000: energy_score's base 8000 and
            # the first-turn bench boost, max 8900). Attachments with a
            # strategic override score far above (8500 Lucario sacrifice,
            # 24000 Tapu pivot, 31000+ charges, 41000 the one that enables a
            # retreat towards a bench KO) and are NOT development: yielding
            # there would break lethal lines for this turn.
            if (pokemon is not None and _teal_dance_slots
                    and 0 < score < 9000
                    and not (pokemon.id in MAIN_ATTACKERS
                             and _can_attack_eff(
                                 pokemon.id,
                                 len(pokemon.energies)
                                 + _grass_attach_unit()))):
                score = min(score, 7000)
                _attach_yields_to_teal_dance.add(len(scores))

            # AND THE SAME YIELD ABOVE THE DEVELOPMENT BAND, WHEN THE
            # ATTACHMENT REACHES NO COST AT ALL (user, registro_006 step 55 vs
            # a Dragapult ex deck, LOST -- the board is drawn out in
            # `_attach_reaches_no_cost`, main.py).
            #
            # The block above only looks at `0 < score < 9000` because that is
            # where DEVELOPMENT lives, and its comment says why: above it sit
            # the strategic overrides -- a charge that pays a retreat, unlocks
            # an attack, takes a prize -- and yielding there would break lethal
            # lines. What the record found is a third kind of number in
            # between: the per-body "future attacker" bands of
            # `_energy_score_base` (15000 for a Tapu Bulu under four energies,
            # 23200 with Meganium in play, and their siblings), which are
            # neither development nor a play for today. On that board one of
            # them priced at 23010 an energy going onto an active Tapu Bulu at
            # 0 of 4 -- three attachments from its attack, three from its own
            # retreat -- and it beat everything else in the menu.
            #
            # `_attach_reaches_no_cost` is the honest test for those bands, and
            # it is the same arithmetic asked of the WHOLE field: if not one
            # body of ours reaches an attack or a retreat with this energy,
            # then no attachment in this menu is buying anything today, so the
            # promise the band is priced on ("it will attack later") is not
            # this turn's business and a Teal Dance -- same Grass, plus a card
            # -- is strictly better. The ceiling is the same 7000 as above, so
            # the ability (7500) decides inside tier 0.
            #
            # It stops BELOW `SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK` (31150),
            # the floor of every band that buys something today. By
            # construction the flag cannot be true while one of those is
            # justified -- they all require a cost to be reached -- and the
            # guard is kept anyway: a flag is cheaper to trust when it cannot
            # reach the lethal lines even if it is wrong.
            #
            # AND IT ONLY OPENS WHERE THE DANCE WOULD OTHERWISE BE VETOED,
            # which is what keeps it from being a second, wider copy of the
            # block above. The board it was written for is the one where the
            # Ogerpon ALREADY covers its cost: there the ability branch answers
            # "do not overcharge" and the two of them left the Grass to a body
            # that could not cash it. Where the Ogerpon is still short the
            # dance is a normal live play, the block above already parks the
            # attachment next to it, and this clause has nothing to add --
            # measured, it fired 26 times in 174 games against the meta decks
            # and moved the weighted matrix by +0.00. Narrowed to its own
            # board it stops paying for decisions it was not written from.
            _anc_dance_is_full = False
            for _anc_area, _anc_index in _teal_dance_slots:
                _anc_card = get_card(obs, _anc_area, _anc_index, my_index)
                if (_anc_card is not None
                        and _can_attack_eff(_anc_card.id,
                                            len(_anc_card.energies))):
                    _anc_dance_is_full = True
                    break
            if (_attach_reaches_no_cost and _anc_dance_is_full
                    and 0 < score < SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK):
                score = min(score, 7000)
                _attach_yields_to_teal_dance.add(len(scores))

            # ==============================================================
            # ONCE THE CHARGING ABILITIES OF THE TURN ARE SPENT: WHOSE GRASS?
            # ==============================================================
            # The two blocks above ask "is there still a Teal Dance TODAY". This
            # one answers the question that opens the moment the answer is no,
            # and that the agent was resolving by the bench table alone (user,
            # registro_002 step 21, episode 90591443 vs Marnie, LOST): active
            # Teal Mask Ogerpon ex with the one energy its own Teal Dance had
            # just attached, a Chikorita on the bench and a single Grass left in
            # hand. The attachment to the active was vetoed by the first-turn
            # rule ("do not overcharge the opening attacker") and the Chikorita
            # -- the only target left -- took the Grass at 8400. A Chikorita with
            # one energy is not an attacker: the Grass went to a body that was
            # never going to use it while the body that WAS going to attack sat
            # in front at 1 of 3.
            #
            # THE MATCHUP DECIDES WHO THE ATTACKER IS, and that is why the rule
            # steps aside for the two wall decks. Against Crustle and against
            # Cornerstone our ex does not damage the wall: there the Chikorita is
            # the first rung of the Meganium line and Tapu Bulu is the plan, so
            # charging the bench line IS the right play and the behaviour is left
            # exactly as it was. Against every other deck we know -- Marnie,
            # Cynthia's Garchomp, Hop's, Alakazam, Dragapult, Archaludon, Mega
            # Starmie -- the Teal Mask Ogerpon ex is our first real attacker, and
            # against the two Grass-weak ones (Marnie's Grimmsnarl line,
            # Cynthia's Garchomp) Myriad Leaf Shower is the fastest prize on the
            # board. The per-matchup energy CAPS are not touched: this only ever
            # moves an Ogerpon ex that is still SHORT of its cost.
            #
            # And the Grass that is not spent today is not free either. Teal
            # Dance is once per turn per body and it is paid FROM HAND: the last
            # Grass in hand is what makes tomorrow's Teal Dance -- an attachment
            # AND A CARD -- payable at all. So:
            #
            #   * last Grass and no route to a Lillie's Determination tomorrow
            #     -> HOLD IT. Spending it on development today buys one energy on
            #     a body; holding it buys the same energy tomorrow PLUS the draw.
            #   * a Lillie's route, or a second Grass in hand
            #     -> SPEND IT ON THE OGERPON. With a Lillie's coming, holding is
            #     not even holding: the refill SHUFFLES THE HAND INTO THE DECK,
            #     Grass included, so a Grass kept back for tomorrow is a Grass
            #     given away. That is precisely what happened in the record two
            #     steps later.
            #
            # Both halves live in the DEVELOPMENT band and gate on it (the same
            # `0 < score < 9000` and "does not become an attacker with this
            # energy" guard as the block above): a charge that enables a retreat,
            # an attack or a KO today scores 31000+ and neither half can see it.
            #
            # "THE ABILITIES ARE SPENT" IS ASKED TWICE, AND ON PURPOSE. The menu
            # (`_teal_dance_slots`) is the honest test of "can it be used from
            # HERE"; `_grass_ability_slots` is the one that knows a Teal Dance or
            # a Ripening Charge is still alive on a body the menu is not offering
            # right now. A live charging ability spends this same Grass for free,
            # so while either says yes the question below is not open yet and
            # neither half of the rule may answer it.
            if (not _teal_dance_slots
                    and _grass_ability_slots(state, field_counts) < 1
                    and pokemon is not None
                    and not AGENT_STATE.op_is_crustle_deck
                    and not AGENT_STATE.op_is_cornerstone_deck
                    and _ogerpon_still_short(my_state)):
                if (hand_counts.get(Basic_Grass_Energy, 0) <= 1
                        and not _lillie_route_next_turn(hand_counts)):
                    if (0 < score < 9000
                            and not (pokemon.id in MAIN_ATTACKERS
                                     and _can_attack_eff(
                                         pokemon.id,
                                         len(pokemon.energies)
                                         + _grass_attach_unit()))):
                        score = SCORE_VETO
                elif (pokemon.id == Teal_Mask_Ogerpon_ex
                        and not _can_attack_eff(pokemon.id, len(pokemon.energies))
                        and (0 < score < SCORE_CHARGE_FUTURE_OGERPON
                             # THE ONLY VETO IT LIFTS IS THE ONE IT ARGUES WITH.
                             # A veto is a veto: the per-matchup energy caps, the
                             # Hydrapple redirections and the anti-waste rules all
                             # speak through one, and a rule about which body gets
                             # a DEVELOPMENT energy has no business overruling
                             # them. The exception is the first-turn veto on our
                             # own opening Ogerpon ex -- "do not overcharge the
                             # opening attacker" -- which is precisely the
                             # judgement the record disputes: at 1 of 3 this is
                             # not overcharging it, it is building it.
                             or (score <= 0
                                 and o.inPlayArea == AreaType.ACTIVE
                                 and _is_our_first_turn(state)))):
                    # It RAISES, it never lowers: an Ogerpon ex the matchup
                    # already scores above this band (the Hydrapple/Meganium
                    # redirections of `_energy_score_base`, any charge with a
                    # prize behind it) keeps its own number.
                    score = SCORE_CHARGE_FUTURE_OGERPON
        return score
    finally:
        tc.card = card
        tc.pokemon = pokemon


__all__ = ['score_play']
