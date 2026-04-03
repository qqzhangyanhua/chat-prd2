from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories import prd as prd_repository
from app.repositories import sessions as sessions_repository


def build_markdown_export(snapshot: dict) -> str:
    sections = snapshot.get("sections", {})
    return "\n".join(
        [
          "# PRD",
          "",
          "## 目标用户",
          sections.get("target_user", {}).get("content", ""),
          "",
          "## 核心问题",
          sections.get("problem", {}).get("content", ""),
          "",
          "## 解决方案",
          sections.get("solution", {}).get("content", ""),
          "",
          "## MVP 范围",
          sections.get("mvp_scope", {}).get("content", ""),
        ]
    )


def export_markdown(db: Session, session_id: str, user_id: str) -> dict[str, str]:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)
    content = build_markdown_export({"sections": snapshot.sections if snapshot else {}})
    return {"file_name": "ai-cofounder-prd.md", "content": content}
