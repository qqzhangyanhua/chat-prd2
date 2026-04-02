from app.db.models import ProjectSession, User


def test_models_have_expected_tablenames() -> None:
    assert User.__tablename__ == "users"
    assert ProjectSession.__tablename__ == "project_sessions"
