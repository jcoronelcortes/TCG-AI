"""A sterile turn is a dead turn that can still swing.

registro_004 step 53, episode 90589108 vs Marnie (WON suboptimally). The active
Dipplin chips a full-health 320 HP Marnie's Grimmsnarl ex that knocks it out
next turn, no benched body is charged, and the Dipplin cannot even pay its own
retreat. The agent ATTACKED as the last action of the turn and threw away the
free Supporter slot AND the free bench development, because every arm of the
Meowth ladder that says "a ready active does not veto free development" is gated
on `field_counts == 0` -- and here ONE Meowth ex was already on the bench, whose
only door asked `_active_cant_attack_this_turn`, a binary "can it attack at all".

Four boundary counterfactuals, one per guard of the new arm: with a healthy
active, with a retreat it can pay, with relief already charged on the bench, or
at the opponent's match point, the veto stands and the agent attacks.
"""

import copy
import json

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step53_the_sterile_turn_benches_the_meowth.json")


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def _replay(observation_key=None):
    """Cold replay of the whole turn; the decision under test is the last one."""
    data = _load()
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = (copy.deepcopy(data[observation_key]) if observation_key
           else seq[-1]["observation"])
    return m.agent(obs), obs, data


def _meowth_option(obs):
    mi = obs["current"]["yourIndex"]
    hand = obs["current"]["players"][mi]["hand"]
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(OptionType.PLAY)
                and hand[o["index"]]["id"] == m.Meowth_ex)


def _attack_option(obs):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(OptionType.ATTACK))


def test_step53_benches_the_second_meowth_instead_of_chipping():
    result, obs, _ = _replay()
    assert result == [_meowth_option(obs)], (
        f"turno esteril (el chip no noquea, el activo muere el proximo turno, "
        f"la banca no tiene nada cargado y el Dipplin no puede pagar su "
        f"retirada): BAJAR el 2o Meowth ex (opt {_meowth_option(obs)}) para "
        f"encadenar Last-Ditch Catch -> Lillie's, no atacar "
        f"(opt {_attack_option(obs)}); obtuvo {result}")


def test_step53_the_play_does_not_close_the_turn():
    # The whole argument is one of SEQUENCE: benching a Basic does not consume
    # the attack. The play must therefore live in `_TIER_DEVELOP`, ABOVE the
    # attack by order and not by score -- if it ever won on score alone inside
    # tier 0, the attack would be the one being replaced, not merely deferred.
    result, obs, _ = _replay()
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"el desarrollo tiene que ganar como PLAY (tier de orden), no como un "
        f"sustituto del ataque; obtuvo {result} -> {opt}")
    assert _attack_option(obs) is not None, (
        "el ataque sigue en el menu: se juega DESPUES, en la misma decision "
        "siguiente del turno")


def test_step53_a_healthy_active_keeps_the_veto():
    # Guard `_active_doomed_real`: with nothing on their side that finishes our
    # Dipplin, the turn is not sterile and a 2-prize body is not worth a fetch.
    result, obs, _ = _replay("synthetic_activo_no_condenado")
    assert result != [_meowth_option(obs)], (
        f"con el activo NO condenado vuelve el veto: no se expone un 2o Meowth "
        f"ex (2 premios) solo por refrescar; obtuvo {result}")


def test_step53_an_active_that_can_retreat_keeps_the_veto():
    # Guard `_mw_active_stuck`: with the second Grass the Dipplin pays its
    # retreat (cost 2), the turn has another move and the ladder keeps its
    # measured preference for the clean retreat-sacrifice of the mismatch.
    result, obs, _ = _replay("synthetic_activo_puede_retirarse")
    assert result != [_meowth_option(obs)], (
        f"si el activo PUEDE retirarse el turno no es esteril: la retirada-"
        f"sacrificio manda sobre exponer un cuerpo de 2 premios; obtuvo {result}")


def test_step53_charged_relief_on_the_bench_keeps_the_veto():
    # Guard `_ready_attacker_count <= 1`: with the benched Teal Mask Ogerpon ex
    # already charged there IS an answer when the active falls, so the turn
    # throws nothing away and the dig buys nothing.
    result, obs, _ = _replay("synthetic_relevo_cargado_en_banca")
    assert result != [_meowth_option(obs)], (
        f"con relevo YA cargado en banca no hay nada que cavar; obtuvo {result}")


def test_step53_at_their_match_point_keeps_the_veto():
    # Guard `op_prize > 2`: plain arithmetic. At their match point the 2-prize
    # body we bench IS the game, and no hand refill buys that back.
    result, obs, _ = _replay("synthetic_rival_a_match_point")
    assert result != [_meowth_option(obs)], (
        f"a match point del rival el cuerpo que bajamos ES la partida; "
        f"obtuvo {result}")
