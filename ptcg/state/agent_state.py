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
        self.we_go_first = False

        # --- reading OUR board (recomputed every turn) -----------------------
        self.meganium_in_play = False
        self.forest_in_play = False
        self._field_at_turn_start = {}
        # Grass energies attached to OUR Pokemon during the current turn (accumulated
        # from the ATTACH logs on every call to agent() and reset when the turn
        # changes). It tells how many charging ABILITIES (Teal Dance / Ripening Charge)
        # are still alive once the MANUAL attachment has been spent.
        self._grass_attaches_this_turn = 0

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
