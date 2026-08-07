"""The prize is the same from either body: the front spot goes to the one that pays less.

Scenario (`records/registro_008_pasos_114_hasta_128.json`, step 126, turn 8,
WON vs Alakazam -- episode 90336164). Their Alakazam had just hit our active for
140:

    US (5 prizes)                             RIVAL (4 prizes)
    active  Teal Mask Ogerpon ex **70**/210   active  Alakazam 140/140, 1 energy
            6 energies                                (Powerful Hand: 20 x hand)
    bench   Meganium 160/160,       2 en.     bench   Alakazam 140/140, 1 en.
            Fezandipiti ex 210,     0 en.             Alakazam 140/140
            Teal Mask Ogerpon ex **210**/210, 4 en.   Dunsparce 60, Dunsparce 70
            Teal Mask Ogerpon ex 210/210, 2 en.
            Meowth ex 170/170

Both Ogerpon finish the Alakazam -- *Myriad Leaf Shower* counts the energy of
BOTH actives, so 30 + 30·(6+1) = 240 from the front and 30 + 30·(4+1) = 180 from
the bench, over 140 either way -- and both hand over the same 2 prizes. The
agent attacked from the front, and the body it left standing there was the one
at 70: their next Powerful Hand, projected at 100 over the hand of three our
Xerosic had just left them, knocks it out and takes two of their four prizes.
The body it could have left there instead eats the same 100 and stays up at 110
of 210.

Cause: the retreat scorer vetoes every retreat under `_active_can_ko_now`
("taking the prize from the front costs nothing") and the one pivot that argues
back, `_relay_finisher_pivot`, only fires when their reply CLOSES THE GAME. Here
it did not -- two of their four prizes survive our corpse -- so nothing looked
at the board and the wounded twin took the prize.

Fix: `_bench_finisher_upgrade` / `_front_spot_upgrade`. When the active already
finishes the target, the knockout is not what is being chosen -- the body left
standing in the active spot is, and once their reply is going to remove that
body, the choice has a bill in two currencies:

    1. PRIZES: a benched finisher handing over FEWER prizes takes the same
       prize and gives back half as much when it is collected.
    2. HP: with the prizes tied, the one that OUTLASTS the blow the active does
       not -- the same removal then costs the opponent another turn.

Both strict: the swap pays the retreat's energy. And both scoped by the same
projected reply, which is what stops the rule from talking over the plays that
are about the prize itself -- with our active out of reach there is no trade to
improve, and a Boss's Orders onto a 2-prize bench body goes on deciding those
boards (`test_main_regressions_3`, Iono step 161).

The blow itself is the one only their HAND reveals (`_hand_revealed_lethal_reply`,
the seam where Powerful Hand prints damage 0 and every defensive rule reads
their Alakazam as harmless). Reading it with the ordinary projector generalises
the rule and costs four already-measured decisions -- Marnie step 107 and the
three of `test_ns_no_evolution_without_its_preevo` step 84 -- so that widening is
a separate change with its own measurement. Measured as it stands: ONE flip in
the whole record corpus (this step), 8 firings in 300 games against the Alakazam
bot, none in 400 mirror games.

Surviving a blow the active does not is CURRENT HP above it, which makes this
the exact mirror of `_pdx_act_margin` (registro_012 step 174), where a HEALTHY
210 active must not step aside for its twin at 50: same two bodies, same
knockout, opposite answer, one rule.

Coverage:
  * the record's board and its arithmetic: both twins finish, same prizes,
    their reply kills one and not the other;
  * why the existing pivot stayed silent (their reply does not close the game);
  * the record's step: RETREAT, not ATTACK;
  * the rest of the chain -- the promotion brings up the healthy twin and the
    promoted twin attacks;
  * the ladder on the helper: prizes before HP, and the HP comparison read on
    the blow itself (100 dies, 101 survives);
  * the boundaries -- no trade, no choice; a wounded twin on the bench does not
    pull the healthy active out (registro_012 step 174 does not regress); a
    relay that does not finish is no relay; and a knockout that WINS the game
    now never retreats.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m
from cg.api import OptionType
from state_builder import Scenario, pk

OGERPON = m.Teal_Mask_Ogerpon_ex
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
DIPPLIN = m.Dipplin
APPLIN = m.Applin
FEZANDIPITI = m.Fezandipiti_ex
MEOWTH = m.Meowth_ex

OP_ALAKAZAM = m.Alakazam_ex          # id 743, "Alakazam": Stage 2, 140 HP, 1 prize
OP_KADABRA = m.Kadabra
OP_ABRA = m.Abra

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_step126_the_front_spot_goes_to_the_healthy_twin.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._prev_op_prize = 6
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs_step126():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _index_of(obs, kind):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(kind))


# ---------------------------------------------------------------------------
# 1. The record: without this board the test measures nothing
# ---------------------------------------------------------------------------

def test_step126_the_board_is_the_records_one():
    obs = _obs_step126()
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    active = mine["active"][0]
    twin = next(p for p in mine["bench"]
                if p["id"] == OGERPON and p["hp"] == 210
                and len(p["energies"]) >= 3)

    # Same card, same 2 prizes: the only difference is how much is left of it.
    assert active["id"] == twin["id"] == OGERPON
    assert active["hp"] == 70 and active["maxHp"] == 210
    assert twin["hp"] == twin["maxHp"] == 210

    # Both finish their Alakazam: Myriad counts the energy of BOTH actives.
    opa = theirs["active"][0]
    assert opa["id"] == OP_ALAKAZAM and opa["hp"] == 140
    op_energy = len(opa["energies"])
    assert 30 + 30 * (len(active["energies"]) + op_energy) == 240 >= 140
    assert 30 + 30 * (len(twin["energies"]) + op_energy) == 180 >= 140

    # Their reply kills ONE of the two. That is the whole difference.
    # (Their hand is down to 3: our Xerosic's Machinations discarded four of
    # them one step earlier. The projector scales Powerful Hand to the hand they
    # will really attack with.)
    assert theirs["handCount"] == 3
    cur_cls = m.to_observation_class(obs).current
    reply = m._op_active_attack_damage_to(
        cur_cls.players[1 - cur["yourIndex"]].active[0],
        cur_cls.players[cur["yourIndex"]].active[0], theirs["handCount"])
    assert reply == 100
    assert reply >= active["hp"] and reply < twin["hp"]

    # And the retreat is on the table, paid by a body with three Grass cards.
    assert m.RETREAT_COST[OGERPON] == 1
    assert len(active["energyCards"]) == 3
    assert any(o.get("type") == int(OptionType.RETREAT)
               for o in obs["select"]["option"])


def test_step126_the_existing_relay_pivot_could_not_see_it():
    """`_relay_finisher_pivot` asks the same question and answers only when
    their reply CLOSES THE GAME. Two of their four prizes survive our corpse,
    so it stayed silent -- which is why the rule had to be widened rather than
    tightened."""
    obs = _obs_step126()
    cur = m.to_observation_class(obs).current
    mine = cur.players[cur.yourIndex]
    theirs = cur.players[1 - cur.yourIndex]
    active, opa = mine.active[0], theirs.active[0]

    assert m._hand_revealed_lethal_reply(opa, active, theirs.handCount) == 100
    assert m.prize_count(active) == 2
    assert len(theirs.prize) == 4
    assert m._reply_closes_the_game(active, theirs, opa) is False


def test_step126_the_wounded_twin_steps_aside():
    obs = _obs_step126()
    retreat = _index_of(obs, OptionType.RETREAT)
    assert m.agent(obs) == [retreat], (
        "the same knockout is available from a body at 210: taking it from the "
        "one at 70 leaves their Powerful Hand a free 2-prize corpse"
    )


# ---------------------------------------------------------------------------
# 2. The rest of the chain: a retreat whose promotion brings up the wrong body,
#    or whose promoted body does not attack, is worse than no retreat at all
# ---------------------------------------------------------------------------

def _board(active_hp=70, bench=None, op_active=None, own_prizes=5,
           op_prizes=4, op_hand=3, **menu):
    """The record's two bodies, parameterised. Six energies on the active and
    four on the benched twin, and the hand of three our Xerosic left them --
    which is what puts their projected Powerful Hand at 100."""
    sc = (Scenario(turn=8, step=126, tac=13, first_player=1,
                   energy_played=True, supporter_played=True,
                   own_prizes=own_prizes)
          .my_active(pk(OGERPON, hp=active_hp, max_hp=210,
                        energies=6, fisicas=3))
          .my_bench(*(bench if bench is not None
                      else [pk(OGERPON, energies=4, fisicas=2)]))
          .op_active(op_active if op_active is not None
                     else pk(OP_ALAKAZAM, hp=140, max_hp=140, energies=1,
                             pre_evo=[OP_ABRA, OP_KADABRA]))
          .op_zones(hand=op_hand, deck=9, prizes=op_prizes))
    return sc.menu_hand(**menu) if menu else sc


def _main_menu(**kwargs):
    """The record's board as a MAIN menu with the two options in dispute."""
    return _board(with_attack=True, with_retreat=True, **kwargs).build()


def test_the_promotion_brings_up_the_healthy_twin():
    """The bench of the record: the twin at 210 with four energies is the only
    body that finishes; the other Ogerpon (two energies) does not reach Myriad's
    number and Meowth ex has no attack at all."""
    obs = (_board(bench=[pk(OGERPON, energies=4, fisicas=2),
                         pk(OGERPON, energies=2, fisicas=1),
                         pk(MEOWTH)])
           .promote_after_retreat().build())
    choice = m.agent(obs)
    promoted = obs["current"]["players"][0]["bench"][
        obs["select"]["option"][choice[0]]["index"]]
    assert promoted["id"] == OGERPON and len(promoted["energies"]) == 4, (
        f"expected the twin that finishes, got {promoted}")


def test_the_promoted_twin_takes_the_prize():
    """The end of the chain. The retreat has been paid (one Grass card off the
    wounded body, which is now on the bench) and the healthy twin is in front:
    it must attack, or the swap threw the prize away."""
    obs = (_board(active_hp=210, bench=[pk(OGERPON, hp=70, max_hp=210,
                                           energies=4, fisicas=2)])
           .my_active(pk(OGERPON, energies=4, fisicas=2))
           .menu_hand(with_attack=True, with_retreat=True).build())
    attacks = [i for i, o in enumerate(obs["select"]["option"])
               if o["type"] == int(OptionType.ATTACK)]
    assert attacks, "four energies pay Myriad Leaf Shower"
    assert m.agent(obs)[0] in attacks, (
        "180 over their 140: the prize the retreat was made for")


# ---------------------------------------------------------------------------
# 3. The ladder itself, read on the helper
# ---------------------------------------------------------------------------

def _upgrade(obs):
    """What `_bench_finisher_upgrade` answers over a built board, fed with the
    same projected reply the scorer feeds it."""
    cur = m.to_observation_class(obs).current
    mine, theirs = cur.players[0], cur.players[1]
    total_grass = sum(len(p.energies)
                      for p in ([mine.active[0]] if mine.active else [])
                      + list(mine.bench) if p is not None)
    return m._bench_finisher_upgrade(
        mine, mine.active[0], theirs.active[0], m.AGENT_STATE.meganium_in_play,
        len(mine.bench), total_grass, False,
        m._hand_revealed_lethal_reply(theirs.active[0], mine.active[0],
                                      theirs.handCount))


def test_the_healthier_twin_is_a_body_upgrade():
    assert _upgrade(_main_menu()) == m.UPGRADE_BODY


def test_a_cheaper_finisher_is_a_prize_upgrade_and_wins_the_ladder():
    """A Dipplin (1 prize) that finishes beats the 210 HP twin (2 prizes): the
    cheaper corpse is read before the tougher body."""
    obs = _main_menu(bench=[pk(OGERPON, energies=4, fisicas=2),
                            pk(DIPPLIN, pre_evo=[APPLIN], energies=1, fisicas=1),
                            pk(MEOWTH), pk(FEZANDIPITI), pk(MEOWTH)])
    mine = m.to_observation_class(obs).current.players[0]
    dipplin = next(p for p in mine.bench if p.id == DIPPLIN)
    # Do the Wave: 20 x our bench (5) = 100... it does NOT reach 140.
    assert 20 * len(mine.bench) == 100 < 140
    assert _upgrade(obs) == m.UPGRADE_BODY, "a relay that does not finish is no relay"

    # With their Alakazam already down to 100 the same Dipplin does finish, and
    # then it is the one the ladder picks.
    obs = _main_menu(bench=[pk(OGERPON, energies=4, fisicas=2),
                            pk(DIPPLIN, pre_evo=[APPLIN], energies=1, fisicas=1),
                            pk(MEOWTH), pk(FEZANDIPITI), pk(MEOWTH)],
                     op_active=pk(OP_ALAKAZAM, hp=100, max_hp=140, energies=1,
                                  pre_evo=[OP_ABRA, OP_KADABRA]))
    assert m.prize_count(dipplin) == 1 < 2
    assert _upgrade(obs) == m.UPGRADE_PRIZE


def test_the_relay_must_outlast_the_blow_the_active_does_not():
    """The HP comparison, measured where it is really made: against their
    projected reply of 100. A relay standing at exactly 100 dies to the same
    blow and buys nothing but the retreat's energy; one point above it, it is
    the body that survives."""
    assert _upgrade(_main_menu(bench=[pk(OGERPON, hp=100, max_hp=210,
                                         energies=4, fisicas=2)])) == ''
    assert _upgrade(_main_menu(bench=[pk(OGERPON, hp=101, max_hp=210,
                                         energies=4, fisicas=2)])) == m.UPGRADE_BODY


# ---------------------------------------------------------------------------
# 4. Boundaries: what was widened and what was not
# ---------------------------------------------------------------------------

def test_nothing_is_chosen_where_nothing_is_being_traded():
    """The gate that keeps the rule from talking over the plays that are about
    the prize itself (a Boss's Orders onto a 2-prize bench body, for one). Their
    reply has to knock the ACTIVE out: with the active out of reach there is no
    trade to improve, whatever the bench holds."""
    assert _upgrade(_main_menu(active_hp=210)) == ''
    assert _upgrade(_main_menu(op_hand=0)) == ''


def test_the_healthy_active_does_not_step_aside_for_the_wounded_twin():
    """The mirror case, `registro_012` step 174: the SAME two bodies with the HP
    the other way round. Whichever of them is standing in front, what decides is
    which one outlasts their reply -- so the answer flips with the board and
    that retreat stays vetoed. The wounded active with an even more wounded twin
    (second board) is the same reading: nobody is safer, nothing to swap."""
    obs = (_board(active_hp=210, bench=[pk(OGERPON, hp=50, max_hp=210,
                                           energies=4, fisicas=2)])
           .menu_hand(with_attack=True, with_retreat=True).build())
    assert _upgrade(obs) == ''
    retreat = _index_of(obs, OptionType.RETREAT)
    assert m.agent(obs) != [retreat], (
        "the body at 210 already takes the prize: swapping it for the one at 50 "
        "costs an energy and leaves the corpse in front")

    assert _upgrade(_main_menu(bench=[pk(OGERPON, hp=50, max_hp=210,
                                         energies=4, fisicas=2)])) == ''


def test_a_winning_knockout_never_steps_aside():
    """With their last prizes on the line the attack ENDS the game: there is no
    next turn to be standing in, and no reason to pay a retreat first."""
    obs = _board(own_prizes=1, op_prizes=1).menu_hand(
        with_attack=True, with_retreat=True).build()
    attacks = [i for i, o in enumerate(obs["select"]["option"])
               if o["type"] == int(OptionType.ATTACK)]
    assert m.agent(obs)[0] in attacks


def test_a_bench_that_cannot_finish_is_not_an_upgrade():
    """Healthier and cheaper, but it does not attack today: nothing to relay."""
    obs = _main_menu(bench=[pk(MEGANIUM, energies=2, fisicas=1,
                               pre_evo=[CHIKORITA, BAYLEEF])])
    mine = m.to_observation_class(obs).current.players[0]
    meg = mine.bench[0]
    assert m.prize_count(meg) == 1 and (meg.hp or 0) > 70
    assert len(meg.energies) < m.AGENT_STATE.ATTACK_ENERGY_REQ[MEGANIUM]
    assert _upgrade(obs) == ''
