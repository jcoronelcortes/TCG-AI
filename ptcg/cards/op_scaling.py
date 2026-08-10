"""The opposing attacks whose damage is NOT the number printed on the card.

Why this table exists. `_op_active_attack_damage_to` reads `attack.damage` and
returns it. For most cards that is the whole story; for a family of them the
printed number is a placeholder ("20x", "30+") and the real damage is a count of
something on the board. Until this table existed, exactly TWO of them were
modelled -- Powerful Hand and Do the Wave -- each as an `if` bolted onto the
projector, and every other one was silently projected as its printed value.

What that costs is not an approximation, it is a blind spot. Everything
defensive in the agent hangs off this one function: `active_ko_likely`,
`active_doomed_real`, the promotion that has to SURVIVE, the doomed-ex retreat,
the turn plan's `op_wins_next`. When the projector says 30 and the attack does
270, none of those rules fires and the agent walks into the hit without seeing
it. Measured on the mirror (registro_013, episode 89616806, the competition's own
validation game): the opposing Hydrapple ex hit for **270** on turn 12 and the
projector called it **30** -- the printed value of Syrup Storm.

CENSUS, not intuition. The table covers the scaling attacks that actually appear
in the 411 opposing decks in the repo (`deck/opponents/`, `deck/real_opponents/`,
`competitor_decks/`): 20 of them, of which 15 are deterministic and observable
from the observation. Those 15 are here, plus three that the corpus of an
earlier leaderboard brought and the current one no longer does -- an entry is
kept when its deck leaves, because the deck comes back.

WHAT IS DELIBERATELY LEFT OUT, and why
--------------------------------------
The line is "can the agent READ the number, or would it be guessing?".

  * COIN FLIPS -- Rapid-Fire Combo (Mega Kangaskhan ex, 45 decks: 200 + 50 per
    heads until tails), Continuous Headbutt (Beartic, 1) and Comet Punch (Team
    Rocket's Kangaskhan ex, 5 decks: four coins, 30 per heads). The expected
    value is computable, the damage is not. Rapid-Fire Combo's +50 was already
    tried and MEASURED AND REVERTED (see the policy note in the memory index):
    it is a better-founded estimate, not a correction of a wrong reading, which
    is a different class of change from everything in this table.
  * THE OPPONENT'S CHOICE -- Erasure Ball (TR Mewtwo ex: 160 + 60 per Energy
    they choose to discard, 6 decks) and Bellowing Thunder (Raging Bolt ex: 70
    per Basic Energy they choose to discard, 5 decks). The scale is not on the
    board, it is in their head. Projecting the maximum would make every turn
    look lost; projecting the minimum is what we already do.

The distinction matters when the next person reads this file: the entries below
fix a number the engine contradicts, the exclusions above would invent one.

HOW THE PERSPECTIVE WORKS
-------------------------
The attacker is ALWAYS the opponent, so in the card text "your ..." is THEIR
side and "your opponent's ..." is OURS. Getting this backwards is the easy
mistake and it is silent, so every entry names the side in its comment.

The lambdas are pure arithmetic over a `BoardScale` snapshot: no card lookups,
no state. Everything that needs the card database (which bodies are Basic, which
are ex, which belong to a named trainer) is resolved ONCE when the snapshot is
built, in `ptcg.calc.opponent.build_op_scale`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardScale:
    """Everything the scaling attacks count, read once per turn.

    Built by `ptcg.calc.opponent.build_op_scale` and published in
    `AGENT_STATE.op_scale`, following the precedent of `_op_bench_count`: if the
    scale travelled in the signature of `_op_active_attack_damage_to` we would be
    back to a silent 0 wherever a caller forgot to pass it.
    """

    # --- THEIR side ("your ..." in the card text) ------------------------
    op_bench: int                 # Pokemon on their bench
    op_grass_on_field: int        # {G} energies on ALL of their Pokemon
    op_psychic_on_field: int      # {P} energies on ALL of their Pokemon
    op_basics_in_play: int        # their Basic Pokemon in play (active + bench)
    op_rocket_in_play: int        # their "Team Rocket's ..." Pokemon in play
    op_cynthia_bench_counters: int  # damage counters on their benched "Cynthia's ..."
    op_ethan_adventure_in_discard: int  # "Ethan's Adventure" cards in THEIR discard

    # --- OUR side ("your opponent's ..." in the card text) ---------------
    my_bench: int                 # Pokemon on our bench
    my_hand: int                  # cards in our hand
    my_active_energy: int         # energies on OUR active
    my_energy_on_field: int       # energies of ANY type on ALL of our Pokemon
    my_ex_in_play: int            # our Pokemon ex / Mega ex in play
    my_basic_energy_in_discard: int   # Basic Energy cards in OUR discard
    prizes_we_took: int           # Prize cards WE have already taken
    # Prize cards WE have taken during the turn IN PROGRESS -- not the whole
    # game. The card text that needs it says "during their last turn", and when
    # we are the ones deciding, "their last turn" is the turn we are playing
    # right now. See the entry for Settle the Score.
    prizes_we_took_this_turn: int


# The empty snapshot: what a consumer sees before `agent()` has built one (a unit
# test that calls the projector directly, an observation outside our turn). Every
# counter at zero means every entry below returns its printed floor, which is
# exactly the behaviour the projector had before this table existed.
EMPTY_SCALE = BoardScale(
    op_bench=0, op_grass_on_field=0, op_psychic_on_field=0, op_basics_in_play=0,
    op_rocket_in_play=0, op_cynthia_bench_counters=0,
    op_ethan_adventure_in_discard=0, my_bench=0, my_hand=0, my_active_energy=0,
    my_energy_on_field=0, my_ex_in_play=0, my_basic_energy_in_discard=0,
    prizes_we_took=0, prizes_we_took_this_turn=0,
)


def _damage_counters(pokemon):
    """Damage counters on a body, from the two numbers the observation carries."""
    if pokemon is None:
        return 0
    return max(0, ((pokemon.maxHp or 0) - (pokemon.hp or 0)) // 10)


# attack id -> damage(attacker, scale). `attacker` is the opposing ACTIVE, the
# only Pokemon that can use these; `scale` is the BoardScale of this turn.
OP_SCALING_DAMAGE = {
    # Do the Wave (Dipplin, 17 decks) -- 20 x THEIR bench. It was already
    # modelled inline in the projector; it lives here now so there is one place
    # to look, and the formula is unchanged.
    115: lambda atk, s: 20 * s.op_bench,

    # Myriad Leaf Shower (Teal Mask Ogerpon ex, 26 decks -- and OUR OWN deck, so
    # this is the mirror's main attack) -- 30 + 30 per Energy on BOTH actives.
    # Ours is read from the snapshot and not from the projection's `target`: when
    # the caller is asking about a body on our BENCH, the scale is still our
    # ACTIVE.
    120: lambda atk, s: 30 + 30 * (len(atk.energies or []) + s.my_active_energy),

    # Syrup Storm (Hydrapple ex, 2 decks + the mirror) -- 30 + 30 per {G} on ALL
    # of THEIR Pokemon. The one that cost registro_013: 8 Grass on their board =
    # 270, and the engine dealt exactly 270.
    195: lambda atk, s: 30 + 30 * s.op_grass_on_field,

    # Resentful Refrain (Mega Froslass ex, 12 decks) -- 50 per card in OUR hand.
    # The only entry that grows when WE refill: a Lillie's before their turn
    # hands this attack 300 extra damage.
    1240: lambda atk, s: 50 * s.my_hand,

    # Tenacious Tail (Dudunsparce ex, 8 decks) -- 60 per Pokemon ex of OURS in
    # play. Our deck is nearly all ex, so this is routinely 240+.
    425: lambda atk, s: 60 * s.my_ex_in_play,

    # Full Moon Rondo (Lillie's Clefairy ex, 8 decks) -- 20 + 20 per benched
    # Pokemon, BOTH sides.
    371: lambda atk, s: 20 + 20 * (s.my_bench + s.op_bench),

    # Rocket Rush (Team Rocket's Spidops, 6 decks) -- 30 per "Team Rocket's"
    # Pokemon of THEIRS in play.
    560: lambda atk, s: 30 * s.op_rocket_in_play,

    # Psychic (Rabsca, 5 decks) -- 10 + 30 per Energy on OUR active. It punishes
    # exactly the body we have been charging.
    88: lambda atk, s: 10 + 30 * s.my_active_energy,

    # Coordinated Throwing (Passimian, 4 decks) -- 20 per Basic Pokemon of
    # THEIRS in play.
    1407: lambda atk, s: 20 * s.op_basics_in_play,

    # Powerful Rage (N's Reshiram, 3 decks) -- 20 per damage counter on ITSELF:
    # the more we chip it, the harder it hits back.
    420: lambda atk, s: 20 * _damage_counters(atk),

    # Raging Hammer (Duraludon, 3 decks) -- 80 + 10 per damage counter on itself.
    224: lambda atk, s: 80 + 10 * _damage_counters(atk),

    # Mind Ruler (Chandelure, 2 decks) -- 30 per card in OUR hand.
    123: lambda atk, s: 30 * s.my_hand,

    # Raging Curse (Cynthia's Spiritomb, 20 decks) -- 10 per damage counter on
    # ALL their benched "Cynthia's" Pokemon. See OP_SCALING_IGNORES_WEAKNESS.
    540: lambda atk, s: 10 * s.op_cynthia_bench_counters,

    # Irritated Outburst (Pecharunt ex, 1 deck) -- 60 per Prize WE have taken:
    # it scales with us winning, which is the worst moment to be blind to it.
    184: lambda atk, s: 60 * s.prizes_we_took,

    # Back Draft (N's Darmanitan, 1 deck) -- 30 per Basic Energy in OUR discard.
    355: lambda atk, s: 30 * s.my_basic_energy_in_discard,

    # Linked Lightning (Tapu Koko ex, 1 deck) -- 60 + 20 per Pokemon on THEIR
    # bench. The same shape as Do the Wave at entry 115, with a printed base.
    #
    # It arrived with the harvest of 9 August 2026 and turned
    # `test_no_opposing_attack_scales_without_being_read` red without a line of
    # code changing, which is exactly the job that test was written to do. The
    # deck is `mega_kangaskhan_1` of the corpus (leaderboard 278), so this is an
    # attack the agent meets in the matchups it is measured on, not a card seen
    # only in a list file.
    #
    # It is modelled rather than excluded because their bench is IN the
    # observation: the exclusions above are for scales that are not on the board
    # (coin flips, Energy the opponent chooses to discard), and a bench count is
    # not one of them.
    #
    # MEASURED, 100 games against that list: the entry is consulted 718 times
    # and returns 80 to 200 against a printed 60 --- benches here reach EIGHT,
    # not the five a paper game would cap them at, so there is no ceiling to
    # write down. And it changes **0 decisions of 12 431**. The harness that
    # says so was checked in both directions: deleting the most-consulted entry
    # instead (Myriad Leaf Shower, 120) flips 10 decisions of 5 225, so it can
    # see a difference when there is one.
    #
    # Correct and, for now, inert --- which is the expected shape for a table
    # that is opt-in and read only by the turn plan, whose thresholds were
    # fitted against the blind number. It closes the blind spot; nobody should
    # expect it to move a game.
    458: lambda atk, s: 60 + 20 * s.op_bench,

    # Settle the Score (Okidogi, 1 deck) -- 80 + 60 per Prize WE took during the
    # turn that is running. It is the twin of Irritated Outburst above, with one
    # difference that changes what can be read: Pecharunt counts the prizes of
    # the WHOLE game, which the observation carries as "six minus the pile", and
    # this one counts the prizes of ONE turn, which it does not.
    #
    # WHAT THIS ENTRY READS, AND WHAT IT DELIBERATELY DOES NOT. The counter is
    # the pile at the start of the turn minus the pile now: the prizes already
    # cashed in this turn, an observation and not a guess. The prize that the
    # attack we are SCORING is about to take is not in it, and in our deck that
    # is the common case -- a knockout ends the turn, so most of the time this
    # entry sees zero and returns the printed 80.
    #
    # That is a floor, which is the direction this table is allowed to be wrong
    # in (see the exclusions at the top: projecting a maximum makes every turn
    # look lost). Reading the prize our own pending attack would cash is a
    # projection over an action that has not happened, it belongs to the rule
    # that decides WHETHER to cash it, and it is measured there rather than
    # smuggled into a damage table.
    1284: lambda atk, s: 80 + 60 * s.prizes_we_took_this_turn,

    # Mega Symphonia (Mega Gardevoir ex, 2 decks) -- 50 per {P} on ALL of THEIR
    # Pokemon. The Psychic twin of Syrup Storm, and just as steep: four Psychic
    # spread over their board is already 200 off a card that prints 0.
    1079: lambda atk, s: 50 * s.op_psychic_on_field,

    # Verdant Storm (Leafeon ex, 2 decks) -- 60 per Energy on ALL of OUR
    # Pokemon, ANY type. Ours is the deck that charges three or four bodies, so
    # this is the entry that punishes our own setup hardest.
    324: lambda atk, s: 60 * s.my_energy_on_field,

    # Buddy Blast (Ethan's Typhlosion, 2 decks) -- 40 + 60 per "Ethan's
    # Adventure" in THEIR discard. It is the only entry counted out of a discard
    # pile of theirs, and the observation carries it.
    490: lambda atk, s: 40 + 60 * s.op_ethan_adventure_in_discard,
}

# Attacks whose own text says the damage is NOT affected by Weakness. The
# projector doubles for weakness at the end, which would inflate these.
OP_SCALING_IGNORES_WEAKNESS = frozenset({540})


def op_scaled_damage(attack_id, printed, attacker, scale):
    """Real damage of an opposing attack, or its printed value if it does not
    scale. Never returns LESS than the printed number: an entry is a floor being
    raised, never a nerf."""
    formula = OP_SCALING_DAMAGE.get(attack_id)
    if formula is None or attacker is None:
        return printed
    return max(printed, formula(attacker, scale))


__all__ = [
    'BoardScale', 'EMPTY_SCALE', 'OP_SCALING_DAMAGE',
    'OP_SCALING_IGNORES_WEAKNESS', 'op_scaled_damage',
]
