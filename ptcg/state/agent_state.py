"""`AgentState`: the mutable state that persists BETWEEN turns.

Wave 3 of the refactor (docs/project-history.md). Up to here everything was a
verbatim move; this is the first thing that REWRITES code, because every
`ko_last_turn` becomes `AGENT_STATE.ko_last_turn`.

WHY AN OBJECT AND NOT LOOSE NAMES
  `from ptcg.estado.agente import ko_last_turn` COPIES the value at import time:
  when main.py reassigns it, the module that imported it that way keeps seeing
  the old value. It raises no exception, it breaks no test that sets the global
  on its own -- the agent simply decides badly in a real game. With an object
  there is nothing to copy: `AGENT_STATE` is never reassigned, only its fields, and
  every module looks at the same one. utils/lint_architecture.py (R1) watches it.

  It has already happened twice with names that were NOT state and still behaved
  like it: `card_table` (wave 2) and `_score_xerosic_play` (wave 4). Both cases
  are the same trap seen from another angle.

THERE IS ONLY ONE RESET
  There used to be two hand-written copies of the reset -- the `reset_main_state`
  fixture of tests/test_main.py and `golden_corpus.reset_agente` -- which had to
  be remembered every time a global was born. Now `reset()` is the only source.
"""

from ptcg.cards.costs import ATTACK_ENERGY_REQ_BASE
from ptcg.cards.op_scaling import EMPTY_SCALE
from ptcg.engine.plan import AttackPlan

# Sentinel value of `_log_current_turn`: we do not know yet which turn the
# logs we are reading belong to.
_TURN_LOG_UNKNOWN = -1


class AgentState:
    """Agent state that survives between calls to `agent()`.

    The fields are documented where they are used; only their initial values
    live here, which are the ones main.py had at module level.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Leaves the state as it is at the start of a new game."""
        # --- Ultra Ball: intentions that cross from one turn to the next -----
        self._ub_meowth_pending = False
        # Sibling of the previous one for the chain UB -> Fezandipiti ex -> Flip the
        # Script (user, registro_006 step 90, episode 88710543 vs Mega Lucario): if the
        # Ultra Ball CHOSE to search for Fezandipiti ex (target `fez_tras_ko`, 1050:
        # only chosen with the ability ALIVE), the play has to be COMPLETED and the body
        # benched. It is paid for with two cards in the discard, so leaving it dead in
        # hand -- or worse, shuffling it back into the deck with the turn's own Unfair
        # Stamp -- throws away the whole Ultra Ball and with it the 3-card draw of Flip
        # the Script, which is ONCE PER TURN and only lives on the turn after the KO.
        # Reset every turn.
        self._ub_fez_pending = False
        # UB->Meowth->Lillie's engine on the energy tier (user, registro_008 step 58 vs
        # Archaludon ex): it is armed when `_ub_engine_refresh_pivot` scores the Ultra
        # Ball at 31450; the FETCH of that UB (a later decision, when the energies have
        # already been discarded and the pivot conditions can no longer be recomputed)
        # consumes it to choose Meowth ex. Reset every turn.
        self._ub_engine_pivot_turn = False

        # --- Poke Pad / Last-Ditch: commitments of the turn ------------------
        self._poke_pad_target_id = 0
        # THE SUPPORTER THE LAST-DITCH BROUGHT GETS PLAYED (user, registro_002 step 22
        # vs Alakazam, WON with a mistake). Benching a Meowth ex from hand costs a
        # 2-prize body on the bench and its ONLY payment is the Supporter that Last-Ditch
        # Catch brings: if that Supporter stays dead in hand, the whole play was a gift.
        # Here we note WHICH Supporter the fetch of a Meowth ex benched THIS turn
        # brought; while the Supporter slot is still free, that id keeps the turn (the
        # other Supporters in hand yield). Reset every turn.
        #
        # It is the OTHER HALF of `_meowth_fetch_loses_the_turn`: that one predicts,
        # BEFORE benching the Meowth, that the fetch is going to win the slot; this one
        # COLLECTS on the prediction afterwards. It is only armed with a PAID body
        # (`appearThisTurn`): the Last-Ditch of a Meowth from previous turns is free and
        # can keep the Supporter for the next turn without having given anything away
        # (same criterion as `_meowth_skip_fetch`).
        self._ld_supp_comprometido = 0

        # --- per-turn caches -------------------------------------------------
        # Serial of the ACTIVE Pokemon whose ABILITY was offered by the last MAIN MENU of
        # the turn (None if none). See the block that updates it inside agent().
        self._td_ability_serial = None
        self._dodge_immune_serial = None
        self._dodge_immune_turn = -1

        # --- the attack plan and the turn in progress ------------------------
        self.plan = AttackPlan()
        self.pre_turn = 0
        # OUR prize pile the first time we were asked to decide this turn. The
        # observation carries the pile as it stands NOW, so the only way to know
        # how many prizes THIS TURN has cashed is to remember where it started.
        # Settle the Score (Okidogi) scales with exactly that number; see
        # ptcg/cards/op_scaling.py. None until the first turn transition.
        self._prize_pile_at_turn_start = None
        self.we_go_first = False

        # --- reading OUR board (recomputed every turn) -----------------------
        self.meganium_in_play = False
        self.forest_in_play = False
        # Full Metal Lab on the field: -30 onto {M} bodies, after weakness and
        # resistance. It lives here rather than as a local of agent() because the
        # arithmetic it corrects is duplicated across ptcg/turn/, and those
        # modules have no other way to see the stadium. ptcg/calc/ is pure and
        # takes it as a parameter instead.
        self.full_metal_lab_in_play = False
        self._field_at_turn_start = {}
        # Grass energies attached to OUR Pokemon during the current turn (accumulated
        # from the ATTACH logs on every call to agent() and reset when the turn
        # changes). It tells how many charging ABILITIES (Teal Dance / Ripening Charge)
        # are still alive once the MANUAL attachment has been spent.
        self._grass_attaches_this_turn = 0
        # ...and WHICH of our bodies received them: the serial of every Pokemon
        # that took a Grass this turn. The bare counter above says how many
        # charges are gone but not WHICH ability spent them, and the two
        # charging abilities do not reach the same places: Teal Dance attaches
        # ONLY to the Ogerpon that used it, Ripening Charge to anybody. A Grass
        # sitting on a benched Ogerpon is therefore explained by that Ogerpon's
        # own dance -- a route that never could have charged the ACTIVE -- and
        # `_grass_ability_slots_active` uses these serials so it does not bill
        # it to the Ripening Charge that is still live.
        self._grass_attach_targets_this_turn = set()
        # OUR OWN Xerosic's Machinations has already been played THIS TURN, so the
        # opposing hand is already capped at `XEROSIC_HAND_CAP` and those cards are
        # in the discard FOREVER. Read by `_stamp_worth_playing`: after our own cap
        # the Unfair Stamp has no half left to pay with, and it is kept for a later
        # turn (`_our_cap_already_spent`). Accumulated from the PLAY logs on every
        # call to agent() -- they arrive in incremental batches, so the fact has to
        # survive from the menu that played Xerosic to the menus that follow it --
        # and reset when the turn changes.
        self._xerosic_played_this_turn = False
        # Serials that OUR OWN searches have moved into this hand DURING THE
        # CURRENT TURN (deck -> hand, discard -> hand). A draw is not a purchase
        # and does not enter here: this is the set of cards a card we PLAYED
        # went and got, which is what makes them the reason a cost was paid.
        # Accumulated from the MOVE_CARD logs on every call to agent() -- they
        # arrive in incremental batches, so the fact has to survive from the
        # menu that resolved the search to the menus that follow it -- and reset
        # when the turn changes. Read by the DISCARD scorer (see
        # `DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT`).
        self._bought_this_turn = set()
        # How many ATTACKS each OPPOSING body has already declared during the
        # current turn, keyed by serial. Only Festival Lead makes a second one
        # possible ("this Pokemon may use an attack it has twice"), and only
        # `op_double_attack_pending` reads it: a wave already spent is not a
        # wave still owed to us. Accumulated from the ATTACK logs on every call
        # to agent() -- during the OPPONENT'S turn we are only called for forced
        # selections, so the count has to survive from one of those menus to the
        # next -- and reset when the turn changes.
        self._op_attack_waves_this_turn = {}
        # Serials of OUR bodies that REACHED PLAY WITHOUT BEING PLAYED: the
        # opening SETUP (hand -> active spot before the first turn) and anything
        # an effect puts down straight from the deck or the discard. The engine
        # logs those as MOVE_CARD; a card played from hand is a PLAY log, and
        # the two are disjoint. It is a fact about the GAME, not the turn, so it
        # is never reset in between: a serial that got its seat for free never
        # stops having got it for free.
        #
        # WHY IT HAS TO BE STATE. `appearThisTurn` says the body arrived this
        # turn and nothing else -- it cannot tell a Meowth ex we PLAYED (its
        # come-into-play ability spent) from the one the setup dealt into the
        # active spot (no ability ever fired). The only evidence of the
        # difference is a log line that goes past ONCE, in the first batch of
        # the game, so it has to be written down when it does. Read by
        # `_meowth_ld_free`; see [[el-cuerpo-que-el-setup-sienta-no-gasto-su-habilidad]].
        self._in_play_without_a_play = set()

        # --- THE WALL THAT IS NOT ON THE BOARD --------------------------------
        # Acerola's Mischief (`OP_EX_SHIELD_IDS`): "during your opponent's next
        # turn, prevent all damage from and effects of attacks done to that
        # Pokemon by your opponent's Pokemon ex". Every other wall this agent
        # knows is READABLE -- a card in the active spot, a stadium on the
        # field. This one leaves nothing behind: the body it protects looks
        # exactly like the body it was, and the only evidence that our ex are
        # mute against it is the PLAY log of the turn it went down. Hence the
        # three fields, and hence they live here: a fact that has to survive
        # from the log batch that carries it to every menu of the turn it
        # governs is state, not a reading of the board.
        #
        # THE SERIAL, NOT THE SPOT. The shield is pinned to a body and travels
        # with it: gust that body to the bench and it is still shielded, while
        # whatever comes up in its place is not. A reading that said "their
        # active" would follow the SPOT and would mute the wrong body one action
        # after our own Boss's Orders -- which is precisely the answer to the
        # card.
        self._op_ex_shield_serial = None
        # The `state.turn` the shield applies to. Their Supporter buys ONE of
        # our turns, so this is a single turn number and not a window: read
        # during their turn it is the next one, read from the batch that already
        # carries their TURN_END it is the current one.
        self._op_ex_shield_turn = -99
        # ...and the resolved answer for the observation being answered: the
        # serial the shield covers RIGHT NOW, or None. Refreshed on every call
        # to agent() once the logs have been read, because `ptcg/calc/damage.py`
        # cannot see `state.turn` from where it stands -- the same arrangement
        # `full_metal_lab_in_play` and `_op_bench_count` already use.
        self.op_ex_shield_serial = None
        # ...and that this opponent HOLDS the card at all. STICKY for the rest
        # of the game, exactly like `op_is_crustle_deck` and for the same
        # reason: a shield we forget the turn it expires is a shield we re-learn
        # one wasted turn later, and the decisions that depend on it are taken
        # BEFORE it comes down -- which cards survive their hand cap, which body
        # the turn charges. Lists that play it play three or four copies (the
        # episode above shows serials 120, 121 and 122), so one sighting really
        # is a property of the deck and not of the turn.
        self.op_has_ex_shield = False

        # --- KOs and the prize window ----------------------------------------
        self.ko_last_turn = False
        self._ko_detected_this_turn = False
        self._prev_op_prize = 6
        # Turn in progress according to the logs: player index, None = BETWEEN TURNS,
        # -1 = we have not seen any TURN_START/TURN_END yet.
        self._log_current_turn = _TURN_LOG_UNKNOWN
        # The `state.turn` in which we saw the last KO OF OUR OWN inside the opponent's
        # turn (which enables Flip the Script / Unfair Stamp) and outside it (which does
        # not).
        self._own_ko_inside_op_turn = -99
        self._own_ko_outside_op_turn = -99

        # --- the turn plan ----------------------------------------------------
        # `ptcg.turn.game_plan.TurnPlan` for the observation being answered: what
        # the prize count says the turn is for (a lethal route and which one, the
        # prizes we take today, the prizes they take on the reply). It is rebuilt
        # on EVERY call to agent() -- the board changes inside the turn -- and
        # cleared at the top of each call so that a stale plan can never reach a
        # rule. `turn_plan_open` keeps the one from the FIRST menu of the turn:
        # the opening sentence, for the PTCG_DEBUG trace and for rules that need
        # to know what the turn was for before we started spending it.
        self.turn_plan = None
        self.turn_plan_open = None

        # --- setup -------------------------------------------------------------
        # Card id we sent to the ACTIVE spot in the setup. It is placed face
        # down, so no later observation reveals it: the bench selection of that
        # same setup reads it here to count how many bodies of a kind are really
        # IN PLAY (the "a maximum of 2 Teal Mask Ogerpon ex" cap).
        self.setup_active_id = None

        # --- detected opposing matchup ----------------------------------------
        self.op_is_crustle_deck = False
        self.op_is_cornerstone_deck = False
        self.op_has_mega_kangaskhan = False
        # The Mega Starmie ex line (Staryu -> Mega Starmie ex). STICKY, like
        # the two above: the deck announces itself with a 70 HP Staryu that
        # threatens nothing, and the whole point of the rule that reads this
        # flag is to have acted BEFORE the 330 HP body shows up. A matchup
        # forgotten the turn the Staryu retreats to the bench is a matchup we
        # would re-learn one KO too late.
        self.op_is_starmie_deck = False
        # Per-turn flags (P0.2): prize denial active on the OPPONENT's field.
        # They are refreshed at the start of agent() together with meganium_in_play.
        self._op_prize_denial_pecharunt = False   # Pecharunt ex (141) on the opposing field
        self._op_prize_denial_gengar = False      # Mega Gengar ex (772) on the opposing field
        self._festival_grounds_in_play = False  # Festival Grounds (1245) on the field, whoever's

        # --- EFFECTIVE attack cost for this turn ------------------------------
        # Copy of the base table onto which `_aplicar_impuesto_tera` applies the
        # +1 of Nighttime Mine to our Tera. It is ALWAYS recomputed from the base,
        # so the tax does not accumulate between turns or between games.
        self.ATTACK_ENERGY_REQ = dict(ATTACK_ENERGY_REQ_BASE)

        # --- belief about the deck --------------------------------------------
        # `ACTIVE_CARDS_IN_DECK[card_id][ZONE]` = how many copies are in each
        # zone. `_init_cards_tracking()` fills it from deck.csv and
        # `_move_card_state` and `_update_cards_tracking` move it around.
        self.ACTIVE_CARDS_IN_DECK = {}
        self._cards_first_scan_done = False
        self._cards_prizes_identified = False
        self._cards_last_turn = -1

        # --- projected opposing damage ---------------------------------------
        # Projected damage of the opposing snipe to ONE Pokemon on our bench (recomputed
        # on every call to agent() from OP_BENCH_SNIPE_DAMAGE and the opposing field).
        self._op_bench_snipe_dmg = 0
        # RECURRING drip that each of OUR bodies with an ability takes between two of
        # our turns: FREEZING_SHROUD_COUNTER x Froslass in play x the TWO checks of the
        # round. 0 without Froslass. (See "THE GIFT WINDOW".)
        self._op_chip_per_round = 0
        # The same drip in the unit ONE CHECKUP, which is the unit the mirror of
        # the window is measured in: Freezing Shroud says "each Pokemon in play
        # that has an Ability", and THEIR board is in play too. A hit that falls
        # short of their active by no more than this cashes the prize anyway, at
        # the checkup, before they get to answer. 0 without Froslass.
        # (See `_shroud_damage_to` / `_op_hp_for_our_ko` in ptcg/calc/damage.py.)
        self._op_chip_per_checkup = 0
        # Damage Adrena-Brain can AIM at any of our Pokemon this turn.
        self._op_movable_dmg = 0
        # The two halves of the line above, published apart because our OWN
        # attack moves one of them: the ceiling is what the charged Munkidori
        # can carry (30 each) and the ammunition is the counters already on
        # their board -- which is 0 until we hit them. See
        # `_movable_dmg_after_our_hit`.
        self._op_movable_cap = 0
        self._op_movable_ammo = 0
        # OPPOSING board per turn: data the damage projections need and that does NOT
        # travel in the signature of `_op_active_attack_damage_to`. Refreshed at the
        # start of agent(), in the same block as the prize denial flags.
        self._op_bench_count = 0              # scales Do the Wave (20 x opposing bench)
        # Flat damage their ACTIVE's attacks get from an ability on their FIELD
        # (Cynthia's Roserade, Hop's Snorlax). It travels here and not in the
        # signature for the same reason as the bench count: the buff body sits on
        # their BENCH and the projector only ever receives the attacker. See
        # `_op_team_damage_buff` and OP_TEAM_DAMAGE_BUFF.
        self._op_team_dmg_buff = 0
        # The BoardScale of this turn: everything the opposing attacks that do
        # NOT do their printed damage count (the opposing bench and Grass, our
        # hand, our ex in play, the prizes we have taken...). Refreshed in the
        # same block as `_op_bench_count` and published here for the same reason:
        # it does not travel in the signature of `_op_active_attack_damage_to`,
        # and a caller that forgot to pass it would silently go back to reading
        # the placeholder printed on the card. See ptcg/cards/op_scaling.py.
        self.op_scale = EMPTY_SCALE


# Single instance. It is NEVER reassigned: modules keep a reference to this
# object, so reassigning it here would leave them looking at the old one.
AGENT_STATE = AgentState()


__all__ = [
    'AgentState',
    'AGENT_STATE',
]
