"""The finisher that kills itself does not WIN: it draws. You have to retreat and finish with another.

Scenario (user, episode 88696693 registro_016 step 184 vs Marnie's Grimmsnarl,
DRAW):

    US                                RIVAL
    active  Tapu Bulu   20/140  6e    active  Impidimp   70/70   0e
    bench   Meganium    80/160  0e    bench   5 bodies (full)
            Ogerpon ex 100/210  6e
            Hydrapple  290/330  0e
    prizes left: 1                    prizes left: 1

The agent attacked with Wood Hammer (220 >= 70): it knocked out the Impidimp... and Wood Hammer
"also does 30 damage to itself", so Tapu Bulu's 20 HP did not
survive either. The two KOs are SIMULTANEOUS: each player took their LAST prize and
the game ended 0-0, a DRAW (`result=2` in the simulator).

The winning play was on the bench: retreat Tapu Bulu (cost 3) and promote the
Teal Mask Ogerpon ex, already with 6 energies, for Myriad Leaf Shower = 30 + 30x6 =
210 >= 70. Verified by driving the real simulator from step 184 with
`cg.api.search_begin/search_step`: the agent's line gives `result=2` (a draw) and
the retreat one gives `result=0` (OUR VICTORY).

The agent was missing THREE pieces, which are the ones these tests pin down:

 1. the attack's SELF-DAMAGE. It is not a field of `Attack`, it lives in its TEXT; now
    `_attack_self_damage` parses it (out of the ~49 attacks in the database with self-damage,
    telling apart mandatory / optional "You may" / coin flip / by counters).
 2. that the KO of OUR body ALSO PAYS PRIZES: `_active_attack_wins_now`
    declared victory looking only at the prizes we took.
 3. that when retreating you have to promote the FINISHER, not the tankiest body: the
    promotion brought up the 290 HP Hydrapple ex (no energy, it does not finish) ahead
    of the charged Ogerpon ex that closed out the game.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from patching import parcheado
from state_builder import G, Scenario, pk

TAPU = m.Tapu_Bulu             # 920: Wood Hammer 220, -30 to itself
OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRAPPLE = m.Hydrapple_ex
MEGANIUM = m.Meganium
LANAS = m.Lanas_Aid
BAYLEEF = m.Bayleef
GRASS = m.Basic_Grass_Energy

WOOD_HAMMER = 1326
MYRIAD_LEAF_SHOWER = 120

IMPIDIMP = 646                 # 70 HP, 1 prize (Grimmsnarl line)
ARCHALUDON_EX = 190           # 300 HP, Grass resistance (-30): it survives 220
SPIKEMUTH_GYM = 1259           # the rival's stadium in the record


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


# ---------------------------------------------------------------------------
# 1. The missing datum: the self-damage comes out of the attack's TEXT
# ---------------------------------------------------------------------------

def test_wood_hammer_does_30_to_itself():
    assert m._attack_self_damage(WOOD_HAMMER) == 30


def test_myriad_leaf_shower_has_no_self_damage():
    assert m._attack_self_damage(MYRIAD_LEAF_SHOWER) == 0


def test_optional_self_damage_is_not_assumed():
    """"You may do 30 more damage. If you do, this Pokemon also does 30 damage
    to itself" (Superpower 144): the decision is OURS, so the certain damage
    is 0. Same with the form without -s ("...also DO 60 damage to itself", 1171)."""
    assert m._attack_self_damage(144) == 0
    assert m._attack_self_damage(1171) == 0


def test_coin_flip_self_damage_only_counts_in_the_worst_case():
    """Reckless Abandon (662): "Flip 2 coins. If both of them are tails, this
    Pokemon also does 90 damage to itself"."""
    assert m._attack_self_damage(662) == 0
    assert m._attack_self_damage(662, incierto=True) == 90


def test_counter_based_self_damage_uses_the_damage_taken():
    """Vanguard Punch (51): 10 for EACH damage counter on the attacker."""
    herido = _pkmn(51, hp=80, max_hp=130)
    assert m._attack_self_damage(51, herido) == 50   # 5 counters


def test_a_later_coin_flip_does_not_make_the_self_damage_random():
    """Thump-Thump Boom (364): "This Pokemon does 100 damage to itself. Flip a
    coin..." -- the coin belongs to ANOTHER sentence and does not touch the self-damage."""
    assert m._attack_self_damage(364) == 100


def test_a_tapu_bulu_at_20_hp_knocks_itself_out_with_its_own_attack():
    assert m._self_ko_by_own_attack(_pkmn(TAPU, hp=20, energies=6))
    assert not m._self_ko_by_own_attack(_pkmn(TAPU, hp=140, energies=6))


def test_with_no_energy_to_pay_the_attack_there_is_no_self_damage():
    """The self-damage only counts if the attack can be USED: Wood Hammer costs
    4 units, and with 2 energies there is no attack (nor suicide) to fear."""
    tapu = _pkmn(TAPU, hp=20, energies=2)
    assert m._self_damage_of_pokemon(tapu) == 0
    assert not m._self_ko_by_own_attack(tapu)


# ---------------------------------------------------------------------------
# 2. Step 184: retreat instead of signing off on the draw
# ---------------------------------------------------------------------------

def _step_184(op_prizes=1, my_prizes=1, tapu_hp=20, ogerpon_energies=6):
    """The exact board of step 184. Meganium on the bench => each physical Grass
    counts DOUBLE, so 3 energy cards give 6 effective units."""
    return (Scenario(turn=16, step=184, tac=1,
                      own_prizes=my_prizes)
            .my_active(pk(TAPU, hp=tapu_hp, energies=[G] * 6, fisicas=3))
            .my_bench(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]),
                      pk(OGERPON, hp=100, energies=[G] * ogerpon_energies,
                         fisicas=ogerpon_energies // 2),
                      pk(HYDRAPPLE, hp=290, pre_evo=[m.Applin, m.Dipplin]))
            .my_hand(BAYLEEF, GRASS, LANAS)
            .stadium(SPIKEMUTH_GYM, of_the_opponent=True)
            .op_active(pk(IMPIDIMP))
            .op_bench(pk(IMPIDIMP), pk(IMPIDIMP), pk(IMPIDIMP),
                      pk(IMPIDIMP), pk(IMPIDIMP))
            .op_zones(hand=4, deck=25, prizes=op_prizes))


def _tipo_elegido(obs, choice):
    return obs["select"]["option"][choice[0]]["type"]


def test_with_one_prize_each_it_retreats_instead_of_finishing_suicidally():
    """THE FAILURE IN THE RECORD. Before: ATTACK (Wood Hammer) -> a 0-0 draw.
    Now: RETREAT, to promote the Ogerpon ex and win cleanly."""
    obs = _step_184().menu_hand(with_retreat=True, with_attack=True).build()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.RETREAT)


def test_the_suicidal_finisher_stays_vetoed_while_the_relief_exists():
    obs = _step_184().menu_hand(with_retreat=True, with_attack=True).build()
    scores = _scores(obs)
    i_atk = _index(obs, m.OptionType.ATTACK)
    i_ret = _index(obs, m.OptionType.RETREAT)
    assert scores[i_atk] <= 0
    assert scores[i_ret] > 0


def test_with_no_relief_on_the_bench_the_draw_is_the_best_outcome_and_is_not_vetoed():
    """With nobody on the bench to finish, the draw is the best available: the
    attack is NOT vetoed (passing also ends in a draw, but gives away the turn).
    The veto is measured rather than the choice because, with energy in hand, attaching it
    scores higher than attacking through rules PRIOR to this change."""
    obs = (Scenario(turn=16, step=184, tac=1, own_prizes=1)
           .my_active(pk(TAPU, hp=20, energies=[G] * 6, fisicas=3))
           .my_bench(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]))
           .my_hand(GRASS)
           .op_active(pk(IMPIDIMP))
           .op_bench(pk(IMPIDIMP))
           .op_zones(hand=4, deck=25, prizes=1)
           .menu_hand(with_retreat=True, with_attack=True).build())
    assert _scores(obs)[_index(obs, m.OptionType.ATTACK)] > 0


def test_with_the_opponent_far_from_the_end_the_suicidal_finisher_still_wins():
    """The brake looks at the RIVAL'S prizes, not at self-damage in the abstract: with 3
    rival prizes our corpse (1 prize) does not close out their count, so
    Wood Hammer is still the top-priority winning finisher."""
    obs = _step_184(op_prizes=3).menu_hand(
        with_retreat=True, with_attack=True).build()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ATTACK)


def test_a_healthy_tapu_bulu_does_not_kill_itself_and_finishes_head_on():
    """The same board with Tapu Bulu at 140/140: the 30 self-damage does not kill it,
    so there is no draw to avoid and ATTACKING is the first thing again."""
    obs = _step_184(tapu_hp=140).menu_hand(
        with_retreat=True, with_attack=True).build()
    assert _tipo_elegido(obs, m.agent(obs)) == int(m.OptionType.ATTACK)


def test_a_suicidal_finisher_that_loses_is_vetoed_even_with_no_relief():
    """A worse case than the draw: our attack does NOT knock out (a 380 HP Duraludon
    survives the 220), so the self-damage only HANDS the rival their last
    prize. There, attacking is losing: it is vetoed with no need for a relief body."""
    obs = (Scenario(turn=16, step=184, tac=1, own_prizes=3)
           .my_active(pk(TAPU, hp=20, energies=[G] * 6, fisicas=3))
           .my_bench(pk(MEGANIUM, hp=80, pre_evo=[m.Chikorita, BAYLEEF]))
           .my_hand(GRASS)
           .op_active(pk(ARCHALUDON_EX, hp=300, max_hp=300))
           .op_bench(pk(IMPIDIMP))
           .op_zones(hand=4, deck=25, prizes=1)
           .menu_hand(with_retreat=True, with_attack=True).build())
    scores = _scores(obs)
    assert scores[_index(obs, m.OptionType.ATTACK)] <= 0


# ---------------------------------------------------------------------------
# 3. When retreating, the FINISHER comes up (not the tankiest body)
# ---------------------------------------------------------------------------

def test_the_promotion_after_retreating_brings_up_the_one_that_wins():
    """The other half of the chain: without this we retreated well and then brought up the
    290 HP Hydrapple ex (no energy, it does not finish) instead of the charged
    Ogerpon ex, and the turn closed without taking the prize."""
    obs = _step_184().promote_after_retreat().build()
    choice = m.agent(obs)
    idx = obs["select"]["option"][choice[0]]["index"]
    bench = obs["current"]["players"][0]["bench"]
    assert bench[idx]["id"] == OGERPON


def test_the_forced_promotion_after_a_ko_keeps_its_criterion():
    """The "bring up the finisher" bonus belongs only to the VOLUNTARY retreat
    (the SWITCH context, always on our turn and before attacking). The forced
    promotion after a KO (TO_ACTIVE) may fall on the rival's turn, where nobody
    attacks and the usual criterion is still the right one."""
    obs = _step_184().promote_from_bench().build()
    choice = m.agent(obs)
    idx = obs["select"]["option"][choice[0]]["index"]
    bench = obs["current"]["players"][0]["bench"]
    assert bench[idx]["id"] == HYDRAPPLE


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _pkmn(card_id, hp, max_hp=None, energies=0):
    """A loose Pokemon for the self-damage helpers (without a full observation)."""
    return m.Pokemon(id=card_id, serial=0, hp=hp,
                     maxHp=max_hp if max_hp is not None else hp,
                     appearThisTurn=False, energies=[G] * energies,
                     energyCards=[], tools=[], preEvolution=[])


def _index(obs, tipo):
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(tipo):
            return i
    raise AssertionError(f"el menu no ofrece {tipo!r}")


def _scores(obs):
    """The scores the agent assigns to each menu option."""
    capturado = {}
    original = m._debug_log_decision

    def spy(context, select, scores, o, my_index, top_n=3):
        capturado.setdefault("scores", list(scores))
        return original(context, select, scores, o, my_index, top_n)

    # The spy is installed in ALL the modules that bind the name: the caller
    # now lives in ptcg/turno/finalize.py, not in main.
    with parcheado("_debug_log_decision", spy):
        m.agent(obs)
    assert "scores" in capturado, "el agente no puntuo el menu"
    return capturado["scores"]
