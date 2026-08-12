"""THE LAST PRIZE IS CASHED BY A BODY THAT IS STILL THERE.

Scenario (user, registro_012 step 133 vs Archaludon, LOST -- episode 92260006):

    US (seat 0)                             RIVAL          prizes 2 - 1
    active  Hydrapple ex   10/330 (4G)      active  Duraludon 130/130 (2M)
            Syrup Storm -> lethal                   just gusted in by our Boss's
    bench   Teal Mask Ogerpon ex 210 (6G)   bench   Cinderace 160/160 (1M)
            Teal Mask Ogerpon ex 210 (4G)           Duraludon 130 (0)
            Teal Mask Ogerpon ex 210 (4G)           Relicanth 100 (0)
            Meowth ex 170 (0), Meganium 160 (2G)

We attacked from the front. The knockout was real -- our second prize of the
game, 2 to 1 -- and then the Cinderace came up, 10 HP was all it had to get
through, and the two prizes a Hydrapple ex hands over closed a count that only
needed one. The same knockout was sitting on our bench: retreat, promote the
Ogerpon ex with six Grass, Myriad Leaf Shower reads 30 + 30x(6+2) = 270 against
the same 130 HP Duraludon -- SAME knockout, SAME prize -- and what stands in the
active spot afterwards is 210 HP against a reply of 100.

Driven through the real engine (`cg.api.search_begin/search_step`) from this
exact state, the fixed agent plays retreat -> pay -> promote the six-Grass
Ogerpon ex -> attack, and the turn ends with their active spot empty, our prize
pile at 1 and a 210 HP body in front. `test_the_whole_line_runs_on_the_real_engine`
is that run.

WHY NOTHING SAW IT
------------------
The turn plan had the whole picture and said so out loud: on this very board it
publishes `op_prizes_after_ko=2` and `op_wins_after_ko=True` -- "the knockout we
are about to take is the one that loses the game". Those two fields are DATA
that no rule read; this is the first consumer.

The two pivots that ask this exact question -- `_relay_finisher_pivot` and
`_front_spot_upgrade` (ptcg/turn/options/retreat.py) -- both went silent, and
for the same reason. Each is scoped to a blow the ordinary projector CANNOT see:
`_hand_revealed_lethal_reply` for the attacks only a hand size reveals,
`_promoted_lethal_reply` for the ones only a bench promotion reveals, and that
second one answers 0 by construction wherever their ACTIVE already kills our
active. Here it did: their Duraludon reads 80 against 10 HP. So the board fell
through to "their active kills it anyway", where the machinery written on a
doomed body owns the turn -- except that machinery is gated by
`not _active_can_ko_now`, and `_active_can_ko_now` is exactly what vetoes the
retreat outright (score -1) on the grounds that taking the prize from the front
costs nothing.

It costs nothing except on this board, and here it costs the game.

WHAT KEEPS IT NARROW
--------------------
  * `op_wins_after_ko` -- the plan's own sentence for "attacking from the front
    loses the game". Not "their reply hurts", not "their reply reaches match
    point" (that is `_relay_finisher_pivot`, one tier below): their promoted
    body knocks our active out AND those prizes close their count.
  * THE RELAY TAKES THE SAME KNOCKOUT. `_bench_finisher_that_survives`, the same
    predicate the pivot above it uses, with the same charge reading and the same
    "no more prizes than the body it replaces" clause. The prize is collected
    either way; only the corpse left behind changes. A retreat that DROPS the
    prize to survive is `TurnPlan.denial_saves_the_game`, measured and reverted
    twice, and it stays reverted.
  * ATTACKING THAT ALREADY WINS NEEDS NO RELAY. `my_prize <= prize_count_op(...)`
    ends the game on the spot and there is no reply to survive into.

MEASURED (utils/relay_saves_the_game_census.py, 300 games over the 87 real
opponent decks, both arms):

    the change      19 632 decisions   1 firing (0.005%), 0 of them won the menu
                                       15 flips (0.076%)
    --control       20 410 decisions   0 firings
                                        9 flips (0.044%)

The flip columns are the same number. They have to be: the `--control` arm
neutralises NOTHING and still reports nine, because the agent carries state and
asking it twice about one board changes what it answers about the next. With one
firing that did not win its menu, no flip in the real arm can be attributed to
the rule at all -- and the listed flips confirm it, several of them in menus with
no retreat option in them.

The population, and the price of the reading it is built on
(utils/match_point_reply_census.py, 300 mirror games / 19 018 decisions):

    the shelf: their promoted reply closes their count,
    with an attack AND a retreat on the menu                  248  (1.30%)
      a relay takes the SAME knockout -- this rule              5
      no knockout, but a body outlasts the reply               9
      everything dies to the same reply: already lost        234  (94.4%)
    of the boards where we attacked anyway, the game
    actually ended on their reply                       32 of 59  (54.2%)

THE 54.2% IS WHY THE RULE HAS THE SHAPE IT HAS. `op_wins_after_ko` is a coin
flip as a prediction -- it reads the WORST body on their bench and assumes they
promote it and have the energy for it, which is the only honest assumption a
defensive projection can make and is wrong about half the time. A rule that
cashes the same prize either way can be built on a reading like that: when the
projection is wrong we still took the prize and we are simply standing behind a
healthier body, and the only bill is the retreat's energy. A rule that gives the
prize UP to survive cannot, and that is the wider pivot -- 9 boards in 19 018
decisions, of which exactly one was an attack-or-retreat decision -- which was
dropped before it was written rather than after 400 games.

Golden corpus: zero flips. Suite: green.

A rule that fires that rarely cannot be shown to WIN by a self-play gate whose
noise floor is a full point -- the project has paid twice for reading such a
number as a verdict. What the census is asked for is collateral damage, and it
reports none. The evidence that the rule is right is the record above, the
engine run below, and the boundaries.
"""

import dataclasses
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from ptcg.calc.damage import (_bench_finisher_that_survives,  # noqa: E402
                              _promoted_lethal_reply,
                              _promoted_reply_damage)

HYDRA = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
DURALUDON = 169
CINDERACE = 666

_FIX = ROOT / "tests" / "fixtures" / \
    "archaludon_the_last_prize_is_cashed_by_a_body_that_is_still_there_step133.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)


def _obs():
    return _fixture()["observation"]


def _sides(obs):
    st = m.to_observation_class(obs).current
    return st, st.players[st.yourIndex], st.players[1 - st.yourIndex]


def _index_of(obs, option_type):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(option_type))


def _best_ogerpon(mine):
    return max((b for b in mine.bench if b is not None and b.id == OGERPON),
               key=lambda b: len(b.energies))


# ---------------------------------------------------------------------------
# The board: the premise is that BOTH bodies take the same knockout
# ---------------------------------------------------------------------------

def test_the_board_is_the_records_one():
    obs = _obs()
    m.agent(obs)
    _, mine, opp = _sides(obs)

    assert mine.active[0].id == HYDRA and (mine.active[0].hp or 0) == 10
    assert opp.active[0].id == DURALUDON and (opp.active[0].hp or 0) == 130
    assert any(b is not None and b.id == CINDERACE for b in opp.bench)
    assert len(opp.prize) == 1, "estan a UN premio: cualquier KO cierra"
    assert len(_best_ogerpon(mine).energies) == 6


def test_the_active_does_knock_their_active_out_from_the_front():
    """Without this the board is an ordinary defensive retreat and measures
    nothing: the point is that the prize is there either way."""
    obs = _obs()
    m.agent(obs)
    _, mine, opp = _sides(obs)
    active, target = mine.active[0], opp.active[0]

    base = m._attacker_base_damage(
        HYDRA, target, len(active.energies),
        grass_scale=m.count_total_grass_energy(mine),
        teal_self_energy=len(active.energies), bench_count=len(mine.bench))
    dmg = m._our_effective_damage(active, target, base,
                                  m.AGENT_STATE.meganium_in_play, False)
    assert dmg >= (target.hp or 0), (
        f"Syrup Storm deberia noquear al Duraludon desde delante "
        f"({dmg} vs {target.hp})")


def test_the_plan_says_the_knockout_is_the_one_that_loses_the_game():
    """`op_wins_after_ko`: the gate of the rule, and the field that was DATA
    nobody read."""
    obs = _obs()
    m.agent(obs)
    plan = m.AGENT_STATE.turn_plan

    assert plan.prizes_today >= 1, "el premio esta ahi de todas formas"
    assert plan.op_prizes_after_ko == 2, "el Hydrapple ex entrega 2"
    assert plan.op_wins_after_ko is True, (
        "el cuerpo que sube de su banca nos noquea y esos premios CIERRAN su "
        "cuenta: atacar desde delante pierde la partida")


def test_the_reply_comes_off_their_bench_and_the_old_readings_are_blind():
    """The seam: their ACTIVE already kills our active, which is precisely what
    silences the two pivots that ask this question."""
    obs = _obs()
    m.agent(obs)
    _, mine, opp = _sides(obs)
    active = mine.active[0]
    hand = getattr(opp, "handCount", None)

    from_active = m._op_active_attack_damage_to(opp.active[0], active, hand,
                                                scaled=True)
    assert from_active >= (active.hp or 0), (
        "su activo ya mata al nuestro: por eso `_promoted_lethal_reply` calla")
    assert _promoted_lethal_reply(mine, opp, hand) == 0
    assert m._hand_revealed_lethal_reply(opp.active[0], active, hand) == 0

    promoted = _promoted_reply_damage(mine, opp, hand)
    assert promoted >= (active.hp or 0), (
        f"lo que suba de su banca tambien lo mata ({promoted} vs {active.hp})")


def test_the_relay_takes_the_same_knockout_and_outlasts_the_reply():
    obs = _obs()
    m.agent(obs)
    _, mine, opp = _sides(obs)
    active, target = mine.active[0], opp.active[0]
    ogerpon = _best_ogerpon(mine)
    reply = _promoted_reply_damage(mine, opp, getattr(opp, "handCount", None))

    assert (active.hp or 0) <= reply, "el de delante cae con cualquier cosa"
    assert (ogerpon.hp or 0) > reply, "el Ogerpon ex de 210 se queda en pie"
    assert m.prize_count(ogerpon) <= m.prize_count(active), (
        "no entrega mas premios que el cuerpo al que releva")

    grass_after = max(0, m.count_total_grass_energy(mine)
                      - m._retreat_grass_units(m.RETREAT_COST[HYDRA]))
    assert _bench_finisher_that_survives(
        mine, target, m.AGENT_STATE.meganium_in_play, len(mine.bench),
        grass_after, False, reply, m.prize_count(active)), (
        "Myriad Leaf Shower noquea al mismo Duraludon tras retirar")


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------

def test_it_retreats_instead_of_cashing_the_prize_from_the_front():
    obs = _obs()
    i_retreat = _index_of(obs, m.OptionType.RETREAT)
    i_attack = _index_of(obs, m.OptionType.ATTACK)

    assert _fixture()["accion_registrada"] == [i_attack], (
        "el escenario deja de medir lo que dice si el ataque no es la accion "
        "registrada de la partida perdida")

    assert m.agent(obs) == [i_retreat], (
        "el premio se cobra con el Ogerpon ex de 210, no con el Hydrapple ex "
        "de 10 que devuelve los dos premios que cierran su cuenta")


def test_the_rule_is_what_moves_it():
    """Neutralise the single seam and the board goes back to attacking. The
    other half of the harness: without it the test could be passing for a
    reason that has nothing to do with the change."""
    from ptcg.turn.options import retreat as R

    obs = _obs()
    original = R._promoted_reply_damage
    try:
        R._promoted_reply_damage = lambda *a, **k: 10 ** 9   # nobody survives
        choice = m.agent(obs)
    finally:
        R._promoted_reply_damage = original

    assert choice == [_index_of(obs, m.OptionType.ATTACK)], (
        "sin la lectura del cuerpo que SUBE, el veto `_active_can_ko_now` "
        "vuelve a dejar al Hydrapple de 10 delante")


# ---------------------------------------------------------------------------
# The boundaries: each clause of the gate, switched off one at a time
# ---------------------------------------------------------------------------

def test_it_stays_quiet_when_their_reply_does_not_close_their_count():
    """Three prizes instead of one: the reply is a trade, not the game, and
    this rule is not a preference about trades."""
    obs = _obs()
    st = obs["current"]
    them = st["players"][1 - st["yourIndex"]]
    them["prize"] = [None, None, None]

    m.agent(obs)
    assert m.AGENT_STATE.turn_plan.op_wins_after_ko is False
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    assert m.agent(obs) == [_index_of(obs, m.OptionType.ATTACK)]


def test_it_stays_quiet_when_no_benched_body_takes_the_same_knockout():
    """With the bench stripped of energy the swap buys nothing: the prize is
    real and giving it up is the pivot this rule refuses to be.

    The assertion is "not the retreat" and not "the attack": with no charged
    relay the turn has other business (it reaches for the Night Stretcher), and
    what this boundary owns is whether the retreat is bought, not what wins the
    menu in its absence."""
    obs = _obs()
    st = obs["current"]
    mine = st["players"][st["yourIndex"]]
    for body in mine["bench"]:
        body["energies"] = []
        body["energyCards"] = []

    assert m.agent(obs) != [_index_of(obs, m.OptionType.RETREAT)]


def test_it_stays_quiet_when_attacking_already_wins_the_game():
    """Our own match point: the knockout ends it and there is no reply to
    survive into."""
    obs = _obs()
    st = obs["current"]
    mine = st["players"][st["yourIndex"]]
    mine["prize"] = [None]

    assert m.agent(obs) == [_index_of(obs, m.OptionType.ATTACK)]


# ---------------------------------------------------------------------------
# The whole line, on the real engine
# ---------------------------------------------------------------------------

def test_the_whole_line_runs_on_the_real_engine():
    """retreat -> pay -> promote the six-Grass Ogerpon ex -> attack, and the
    turn ends with their active spot empty and 210 HP in front of us."""
    from cg import api

    def as_dict(o):
        if dataclasses.is_dataclass(o):
            return {k: as_dict(v) for k, v in dataclasses.asdict(o).items()}
        if isinstance(o, list):
            return [as_dict(v) for v in o]
        if isinstance(o, dict):
            return {k: as_dict(v) for k, v in o.items()}
        return o

    first = _obs()
    parsed = api.to_observation_class(first)
    me = parsed.current.players[0]
    them = parsed.current.players[1]

    # `tests/test_cg_api.py` fakes `AgentStart` to return the integer 77 and
    # `search_begin` caches it in the module global `api.agent_ptr`; a real
    # SearchBegin later in the same session would then dereference 77 and take
    # the interpreter down with a segfault instead of a red test.
    api.__dict__.pop("agent_ptr", None)
    search = api.search_begin(
        parsed, [m.Basic_Grass_Energy] * me.deckCount,
        [m.Basic_Grass_Energy] * len(me.prize), [6] * them.deckCount,
        [6] * len(them.prize), [6] * them.handCount, [])

    obs, played = first, []
    for _ in range(20):
        choice = m.agent(obs)
        played.append(int(obs["select"]["option"][choice[0]].get("type", -1)))
        search = api.search_step(search.searchId, choice)
        current = search.observation.current
        if current is not None and (current.result or -1) >= 0:
            break
        if search.observation.select is None:
            break
        obs = as_dict(search.observation)
        obs["search_begin_input"] = None
        if obs["current"]["yourIndex"] != 0:
            break

    assert int(m.OptionType.RETREAT) in played, f"tipos jugados: {played}"
    assert int(m.OptionType.ATTACK) in played, f"tipos jugados: {played}"

    final = obs["current"]
    ours = final["players"][0]["active"][0]
    assert ours["id"] == OGERPON and ours["hp"] == 210, (
        "delante queda el Ogerpon ex de 210, no el Hydrapple de 10")
    assert len(ours["energies"]) == 6, "sube el que ya estaba cargado"
    assert not final["players"][1]["active"], "su activo cayo igual"
    assert len(final["players"][0]["prize"]) == 1, "y el premio se cobro"
