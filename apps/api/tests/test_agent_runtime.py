from app.agent.runtime import decide_next_action


def test_decide_next_action_prefers_probe_when_target_user_missing():
    state = {
        "idea": "做一个 AI Co-founder",
        "target_user": None,
        "problem": None,
        "solution": None,
    }
    action = decide_next_action(state, "我想做一个帮助创业者梳理想法的产品")
    assert action.action == "probe_deeper"
    assert action.target == "target_user"
