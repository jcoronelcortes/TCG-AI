"""THE PRIZE IS CASHED BY THE BODY THAT OUTLASTS WHAT COMES UP NEXT.

Scenario (user, registro_006 step 54 vs Mega Starmie ex, LOST -- episode
91693960):

    US (seat 0)                                RIVAL
    active  Teal Mask Ogerpon ex 210/210 (4G)  active  Cinderace 160/160 (1W)
            Myriad Leaf Shower -> 180                  Turbo Flare -> 50
    bench   Hydrapple ex 330/330 (1G)          bench   Mega Starmie ex 330 (3W)
            Bayleef 110 (0)                            Mega Starmie ex 330 (3W)
    hand    Night Stretcher, Xerosic's,        prizes  6 - 5
            Chikorita, Bayleef
    discard 2 Basic Grass

The agent attacked from the front. 180 over 160: the Cinderace fell and we
cashed one prize. Then they promoted a Mega Starmie ex, Nebula Beam read 210
against exactly 210 HP, and the reply took two prizes and sent four Grass to the
discard with the body. One prize for two, and the attacker of the deck gone.

THE LINE THAT WAS ON THE MENU, and it takes the SAME prize:

    RETREAT -> PROMOTE Hydrapple ex -> NIGHT STRETCHER -> ATTACH -> ATTACK

The retreat costs one Grass off the Ogerpon; the Stretcher brings a Grass back
out of the discard and the turn's attachment puts it on the Hydrapple. Syrup
Storm scales with the Grass on the WHOLE field: 3 left on the Ogerpon plus 2 on
the Hydrapple is 30 + 30x5 = 180, over the same 160 HP Cinderace. Same knockout,
same prize -- and the 210 lands on a 330 HP body that survives at 120, with the
Ogerpon ex safe on the bench, where its own Tera prevents all damage from
attacks. Driven through the real simulator from this state
(`cg.api.search_begin/search_step`) the fixed agent plays exactly those six
selections and the attack log reads -180 on the Cinderace.

WHY NEITHER PIVOT COULD SEE IT: TWO READINGS OFF THE WRONG BOARD
----------------------------------------------------------------
`_relay_finisher_pivot` and `_front_spot_upgrade` (ptcg/turn/options/retreat.py)
ask this exact question -- "two of our bodies take the same knockout; which one
do I want standing there afterwards?" -- and both answered no.

  1. THE REPLY CAME OFF A CORPSE. Both are scoped by the blow their ACTIVE
     lands, and both only ever run when our attack is about to knock that active
     out. On this board that is 50 from a Cinderace already on its way to the
     discard, where the board's real answer was 210 from the bench. The
     projection of the body they PROMOTE existed -- `_reply_after_promotion`,
     published by the turn plan as `op_prizes_after_ko` -- and was DATA that
     nothing read. `_promoted_lethal_reply` (ptcg/calc/damage.py) is that
     reading, and these are its first consumers.

  2. THE RELAY WAS READ MUTE. Both measured the benched body at
     `len(bp.energies)` and stopped: a Hydrapple ex one energy short of Syrup
     Storm does not attack today, so it is no relay. The Night Stretcher in hand
     and the attachment nobody had spent were not part of the question -- while
     `_ogerpon_lethal_promote`, three blocks further down the same file, has
     counted exactly that route since it was written. `_relay_reading` now gives
     both predicates the same eyes, through `_reachable_grass_for`.

WHAT KEEPS IT NARROW, and it is measured, not argued
-----------------------------------------------------
The defensive machinery of this agent has been measured negative three separate
times when it was made to fire more often, and the promoted reading opens a seam
that was closed. Three clauses hold it shut, each one a decision the project had
already paid for and each one re-measured here:

  * `not active_ko_likely` -- the promoted reading speaks only where EVERY
    reading the agent already has says the body in front is safe. Without it,
    `iono_step161` and `mewtwo_step119` flip: a Hydrapple ex at 30 of its 330,
    a body that anything on their board removes, and the rules written on a
    doomed active own that turn.
  * `not (_win_via_boss_gust or _gust_2prize_via_boss)` -- a bigger prize on the
    table silences it. The swap is about WHO takes a knockout that happens
    anyway; a gust onto a 2-prize bench body is a different and bigger one. It
    is also the coherent reading: the blow being projected comes off their
    bench and the gust deletes a body from that bench.
  * IT MAY ONLY TURN THE PIVOTS ON, NEVER OFF. Both predicates FILTER by the
    reply -- a relay whose HP does not clear it is dropped -- so substituting a
    bigger number silences pivots the old reading granted. The promoted number
    is therefore asked as a SECOND question, only where the first answered
    nothing. This is the clause with the largest measured effect, and it is
    pinned by `test_it_never_takes_away_a_pivot_the_old_reading_granted`.

MEASURED (utils/promoted_relay_census.py, utils/gate_promoted_relay.py; both
build their baseline from THIS tree with the change's two seams switched off, so
no other work in progress contaminates the comparison):

    head to head vs that same baseline, n=1500 each, the comparable pair
        substituting the reading   47.8% [45.3-50.3]   prizes -0.09
        asking it additively       50.5% [47.9-53.0]   prizes -0.01
    census of the flips it causes
        substituting the reading     3 /    579 decisions  (0.52%,   8 games)
        asking it additively        12 / 19 886 decisions  (0.06%, 300 games
                                    over 87 real opponent decks)

The two census rows are not the same sample -- the substituting form was only
run as far as it took to see what it was doing, and the h2h pair above is the
measurement that decided the shape.

Golden corpus: zero flips. The 50.5% is the point: a rule that fires in 0.06% of
decisions cannot be shown to WIN by a gate whose noise floor is a full point --
the project has paid twice for reading such a number as a verdict -- so what the
gate is asked for here is collateral damage, and it reports none. The evidence
that the rule is right is the record above and the boundaries below.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from ptcg.calc.damage import (_promoted_lethal_reply,  # noqa: E402
                              _promoted_reply_damage)

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRA = m.Hydrapple_ex
CINDERACE = 666
MEGA_STARMIE = 1031

_FIX = ROOT / "tests" / "fixtures" / \
    "starmie_t6_the_prize_is_cashed_by_the_body_that_outlasts_step54.json"


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


# ---------------------------------------------------------------------------
# The board: the premise is that BOTH bodies take the same knockout
# ---------------------------------------------------------------------------

def test_the_active_does_knock_their_active_out_from_the_front():
    """Without this the scenario is an ordinary defensive retreat and measures
    nothing: the whole point is that the prize is there either way."""
    obs = _obs()
    m.agent(obs)
    _, mine, opp = _sides(obs)
    active, target = mine.active[0], opp.active[0]

    base = m._attacker_base_damage(
        OGERPON, target, len(active.energies),
        grass_scale=0, teal_self_energy=len(active.energies),
        bench_count=len(mine.bench))
    dmg = m._our_effective_damage(active, target, base,
                                  m.AGENT_STATE.meganium_in_play, False)

    assert target.id == CINDERACE and (target.hp or 0) == 160
    assert dmg >= (target.hp or 0), (
        f"Myriad Leaf Shower deberia noquear al Cinderace desde delante "
        f"({dmg} vs {target.hp})")


def test_their_active_is_harmless_and_their_bench_is_not():
    """The seam itself: read off the body in front, nothing is in danger."""
    obs = _obs()
    m.agent(obs)
    _, mine, opp = _sides(obs)
    active = mine.active[0]

    from_active = m._op_active_attack_damage_to(
        opp.active[0], active, getattr(opp, "handCount", None))
    assert from_active < (active.hp or 0), (
        f"su ACTIVO no mata al nuestro ({from_active} vs {active.hp}): esa es "
        f"la lectura que dejaba dormidos a todos los pivotes")

    promoted = _promoted_reply_damage(mine, opp, getattr(opp, "handCount", None))
    assert promoted >= (active.hp or 0), (
        f"el cuerpo que SUBE de su banca si lo mata ({promoted} vs "
        f"{active.hp}): Nebula Beam del Mega Starmie ex")
    assert any(b is not None and b.id == MEGA_STARMIE for b in opp.bench)


def test_the_promoted_reading_speaks_here_and_only_here():
    """`_promoted_lethal_reply` is the hand-revealed reading's twin: it answers
    only when the second blow is lethal and the first is not."""
    obs = _obs()
    m.agent(obs)
    _, mine, opp = _sides(obs)

    assert _promoted_lethal_reply(mine, opp, getattr(opp, "handCount", None)) \
        >= (mine.active[0].hp or 0)

    # Boundary: with their bench emptied there is nothing to promote, the
    # knockout wins by bench-out and the reading falls silent.
    opp.bench = []
    assert _promoted_lethal_reply(mine, opp, getattr(opp, "handCount", None)) == 0


# ---------------------------------------------------------------------------
# The relay: mute at face value, lethal with the Grass the turn can still reach
# ---------------------------------------------------------------------------

def test_the_hydrapple_cannot_attack_with_what_it_already_carries():
    obs = _obs()
    m.agent(obs)
    _, mine, _ = _sides(obs)
    hydra = next(b for b in mine.bench if b is not None and b.id == HYDRA)

    assert len(hydra.energies) < m.AGENT_STATE.ATTACK_ENERGY_REQ[HYDRA], (
        "la premisa: a una energia de Syrup Storm, y por eso se leia MUDO")


def test_the_stretcher_and_the_attachment_make_the_same_knockout():
    """3 Grass left on the Ogerpon + 2 on the Hydrapple = 30 + 30x5 = 180."""
    obs = _obs()
    m.agent(obs)
    state, mine, opp = _sides(obs)
    active = mine.active[0]
    hydra = next(b for b in mine.bench if b is not None and b.id == HYDRA)
    target = opp.active[0]

    hand_counts = {}
    for c in mine.hand or []:
        hand_counts[c.id] = hand_counts.get(c.id, 0) + 1
    field_counts = {}
    for p in (mine.active + mine.bench):
        if p is not None:
            field_counts[p.id] = field_counts.get(p.id, 0) + 1

    reach = m._reachable_grass_for(
        hydra, state, mine, hand_counts, field_counts,
        extra_discard_grass=m._retreat_grass_to_discard(active))
    assert reach == 1, (
        "una Planta alcanzable: la Night Stretcher la saca del descarte y "
        "queda una ruta de adjunte libre")

    unit = m._grass_attach_unit()
    grass_after = (m.count_total_grass_energy(mine)
                   - m._retreat_grass_units(m.RETREAT_COST[OGERPON]))
    base = m._attacker_base_damage(
        HYDRA, target, len(hydra.energies) + reach * unit,
        grass_scale=grass_after + reach * unit,
        teal_self_energy=len(hydra.energies) + reach * unit,
        bench_count=len(mine.bench))
    dmg = m._our_effective_damage(hydra, target, base,
                                  m.AGENT_STATE.meganium_in_play, False)

    assert dmg >= (target.hp or 0), (
        f"Syrup Storm tras retirar, recuperar y pegar deberia noquear igual "
        f"({dmg} vs {target.hp})")


def test_the_relay_outlasts_the_blow_the_active_does_not():
    obs = _obs()
    m.agent(obs)
    _, mine, opp = _sides(obs)
    active = mine.active[0]
    hydra = next(b for b in mine.bench if b is not None and b.id == HYDRA)
    reply = _promoted_reply_damage(mine, opp, getattr(opp, "handCount", None))

    assert (active.hp or 0) <= reply, "el ex de delante cae por exactamente 210"
    assert (hydra.hp or 0) > reply, "el de 330 se queda en pie"
    assert m.prize_count(hydra) == m.prize_count(active), (
        "mismos premios en juego: lo que se compra es el CUERPO, no el precio")


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

    choice = m.agent(obs)

    assert choice == [i_retreat], (
        f"esperaba RETREAT (idx {i_retreat}) para cobrar el mismo premio con el "
        f"Hydrapple ex de 330; eligio {choice} (ATTACK era {i_attack})")


def test_with_their_bench_empty_the_prize_is_taken_from_the_front():
    """Boundary: no body to promote means no reply to outlast -- and knocking
    their last body out wins by bench-out. The rule must stay silent."""
    obs = _obs()
    op = obs["current"]["players"][1]
    op["bench"] = []
    i_attack = _index_of(obs, m.OptionType.ATTACK)

    assert m.agent(obs) == [i_attack], (
        "sin banca rival no hay relevo que comprar: se ataca")


def test_the_reading_is_confined_to_the_board_it_was_written_for():
    """Over the whole record corpus, switching the promoted reading OFF must
    change exactly ONE decision: the founding board.

    This is the property the additive shape buys, measured where it can be seen.
    Both pivots FILTER by the reply -- a relay whose HP does not clear it is
    dropped -- so SUBSTITUTING the bigger number silences pivots the
    hand-revealed reading had granted, and the ones it silenced were on the
    Alakazam boards the front-spot rule was measured on. Head to head against
    the same baseline, n=1500 each: 47.8% substituting, 50.5% additive.

    A decision-level assertion is what a rule this rare can honestly be held to:
    the self-play gate cannot resolve 0.06%, so the guard against the addition
    spreading has to live here.
    """
    from ptcg.turn.options import retreat as R

    records = sorted((ROOT / "records").glob("registro_*.json"))
    if not records:
        pytest.skip("records/ is transient local data")

    def _decide(obs, reading):
        R._promoted_lethal_reply = reading
        m.AGENT_STATE.reset()
        m._init_cards_tracking()
        return list(m.agent(json.loads(json.dumps(obs))))

    original = R._promoted_lethal_reply
    off = lambda *a, **k: 0          # noqa: E731 -- the reply comes off their active
    seen, changed = 0, []
    try:
        for path in records:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            episode = (data.get("info") or {}).get("EpisodeId")
            for step in data.get("steps", []):
                for item in step:
                    obs = item.get("observation") or {}
                    if item.get("status") != "ACTIVE" or not obs.get("select"):
                        continue
                    if (obs.get("current") or {}).get("yourIndex") is None:
                        continue
                    seen += 1
                    if _decide(obs, original) != _decide(obs, off):
                        changed.append((episode, obs.get("step")))
    finally:
        R._promoted_lethal_reply = original

    assert seen > 0, "el corpus de registros no aporto ninguna decision nuestra"
    # THE NAME OF A RECORD IS TRANSIENT DATA, THE PROPERTY IS NOT -- AND SO IS
    # THE SPLIT. `records/` is re-harvested (the guard at the top of this test
    # says so out loud) and `utils/split_turns.py` re-cuts the same episode into
    # different files with every run, so a filename is twice a bet: on which
    # game is on disk and on where the knife fell. What identifies a board is
    # the EPISODE and the STEP, and neither moves.
    #
    # What is asserted is the property: the reading may change only boards that
    # have been READ, and every one of them is written down here with what it
    # decided. A board that is not on this list failing the test is the point of
    # the test -- it means the reading reached somewhere nobody looked.
    #
    #   91693960 / 54  the foundational board (the docstring above). Their Mega
    #                  Starmie ex answers a 210 HP active from the bench, so the
    #                  prize is cashed by the 330 HP body instead.
    #   93173834 / 98  vs Marnie, turn 7, read 15 August 2026. Same shape, and
    #                  the reading is right for the same reason: our active is a
    #                  Teal Mask Ogerpon ex at 20 of 210 carrying three Grass,
    #                  and Myriad Leaf Shower (30 + 30 per Energy on both
    #                  Actives) reads 120 over their 70 HP Marnie's Impidimp --
    #                  the prize is there for the taking from the front. The
    #                  RETREAT takes the same prize with the twin: one Grass off
    #                  the front, the 200 HP Ogerpon with four Grass comes up
    #                  and its own 150 knocks the same body out, while the 20 HP
    #                  ex ends the turn on the bench where its Tera prevents all
    #                  damage from attacks. Leaving it in front hands over TWO
    #                  prizes to anything at all -- their Froslass alone drips a
    #                  counter on it at every checkup. It is the line the game
    #                  actually played (steps 99-102).
    _read = {(91693960, 54), (93173834, 98)}
    assert set(changed) <= _read, (
        f"la lectura del cuerpo que sube toco un tablero que nadie ha leido; "
        f"cambio {len(changed)} de {seen} decisiones: "
        f"{sorted(set(changed) - _read)}")


def test_a_bench_that_cannot_answer_leaves_the_prize_in_front():
    """Boundary: the SAME board with their Mega Starmie ex swapped for the
    pre-evolution it comes from. Staryu replies for 20, our 210 HP ex is in no
    danger, and the retreat buys nothing it should pay a Grass for."""
    obs = _obs()
    for b in obs["current"]["players"][1]["bench"]:
        b["id"] = 1030          # Staryu
        b["maxHp"] = b["hp"] = 70
        b["energies"] = [3]
        b["energyCards"] = b["energyCards"][:1]
    # El hueco de Supporter del turno esta libre y la mano rival esta en seis:
    # la red de `finalizar` cobra el Xerosic antes del ataque que cierra el
    # turno (`OP_HAND_PRICED_PLAY_IDS`). Eso reordena, no sustituye -- la
    # afirmacion de este test es sobre la RETIRADA, asi que se comprueba en el
    # menu con el hueco ya gastado, donde el premio se cobra desde delante.
    from main_support import spend_the_supporter_slot
    despues = spend_the_supporter_slot(obs, m.Xerosic_Machinations)
    i_attack = _index_of(despues, m.OptionType.ATTACK)

    assert m.agent(despues) == [i_attack], (
        "si el cuerpo que sube no mata al nuestro, el premio se cobra desde "
        "delante y no se paga la retirada")


# ---------------------------------------------------------------------------
# THE SECOND BOARD THE READING REACHED, and it is not a regression
#
# Found 15 August 2026 by the spread guard above, on a corpus that had just
# rotated to episode 93173834 (vs Marnie, LOST). Verified at `2442f27` as well,
# so nothing that day's merges shipped put it there: the board simply arrived.
#
# Turn 7, step 98, and the shape is the foundational one with different cards:
#
#     US (seat 0)                                RIVAL
#     active  Teal Mask Ogerpon ex  20/210 (3G)  active  Marnie's Impidimp 70/70
#     bench   Teal Mask Ogerpon ex 200/210 (4G)  bench   Munkidori 100/110 (1D)
#             Dipplin 70/80 (1G)                         Froslass 90/90
#             Bayleef 80/110 (1G)                        Munkidori 100/110 (1D)
#             Applin 40/40                               Marnie's Morgrem 100
#     hand    Bayleef, Xerosic's                         Marnie's Impidimp 70
#     prizes  3 - 6            stadium  Forest of Vitality (ours)
#
# Myriad Leaf Shower is 30 + 30 per Energy on BOTH Actives: 120 from the front
# over 70 HP, so the prize is there without moving. The retreat takes the SAME
# prize -- one Grass off the front, the twin comes up with four Grass and its
# own 150 knocks the same Impidimp out -- and ends the turn with 200 HP in front
# instead of 20, with the wounded ex on the bench where its Tera prevents all
# damage from attacks. It is the line the game played (steps 99-102).
#
# These three tests are the durable half: `records/` is transient, the fixture
# is not.
# ---------------------------------------------------------------------------

_FIX_MARNIE = ROOT / "tests" / "fixtures" / \
    "marnie_step098_the_body_that_outlasts_the_reply.json"


def _obs_marnie():
    with open(_FIX_MARNIE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def test_marnie_step98_the_prize_is_there_from_the_front():
    """Without this the swap measures nothing: attacking already wins a prize."""
    obs = _obs_marnie()
    _st, mine, theirs = _sides(obs)

    assert mine.active[0].id == OGERPON and mine.active[0].hp == 20
    assert len(mine.active[0].energies) == 3
    assert theirs.active[0].hp == 70
    # 30 + 30 x (3 on ours + 0 on theirs) = 120, over 70. The front takes it,
    # and it is the agent's own calculator that says so.
    base = m._attacker_base_damage(
        OGERPON, theirs.active[0], len(mine.active[0].energies),
        grass_scale=0, teal_self_energy=len(mine.active[0].energies),
        bench_count=len(mine.bench))
    assert m._our_effective_damage(mine.active[0], theirs.active[0], base) >= 70
    assert _index_of(obs, m.OptionType.ATTACK) == 0


def test_marnie_step98_the_twin_takes_the_same_prize_and_outlasts_the_reply():
    obs = _obs_marnie()
    assert m.agent(obs) == [_index_of(obs, m.OptionType.RETREAT)], (
        "el premio lo cobra el gemelo de 200 que sigue en pie, no el cuerpo de "
        "20 que entrega dos premios a cualquier cosa")


def test_marnie_step98_it_is_the_promoted_reading_that_decides_it():
    """The attribution, pinned: with the reading off, the board attacks."""
    from ptcg.turn.options import retreat as R

    original = R._promoted_lethal_reply
    R._promoted_lethal_reply = lambda *a, **k: 0
    try:
        m.AGENT_STATE.reset()
        m._init_cards_tracking()
        sin = m.agent(_obs_marnie())
    finally:
        R._promoted_lethal_reply = original
    assert sin == [_index_of(_obs_marnie(), m.OptionType.ATTACK)]
