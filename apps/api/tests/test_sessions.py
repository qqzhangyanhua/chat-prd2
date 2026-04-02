def test_create_session_returns_initial_state(auth_client):
    response = auth_client.post(
        "/api/sessions",
        json={
            "title": "AI Co-founder",
            "initial_idea": "一个帮助独立开发者梳理产品想法并生成 PRD 的智能体系统",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session"]["title"] == "AI Co-founder"
    assert data["state"]["stage_hint"] == "问题探索"
    assert data["prd_snapshot"]["sections"] == {}
