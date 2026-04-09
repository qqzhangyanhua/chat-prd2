from typing import Any, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse


RecoveryAction = dict[str, Optional[str]]


def build_api_error_payload(
    code: str,
    message: str,
    recovery_action: Optional[RecoveryAction] = None,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "detail": message,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if recovery_action is not None:
        payload["error"]["recovery_action"] = recovery_action
    if details is not None:
        payload["error"]["details"] = details
    return payload


class ApiError(HTTPException):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        recovery_action: Optional[RecoveryAction] = None,
        details: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.message = message
        self.recovery_action = recovery_action
        self.details = details

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content=build_api_error_payload(
                code=self.code,
                message=self.message,
                recovery_action=self.recovery_action,
                details=self.details,
            ),
            headers=self.headers,
        )


def raise_api_error(
    *,
    status_code: int,
    code: str,
    message: str,
    recovery_action: Optional[RecoveryAction] = None,
    details: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> None:
    raise ApiError(
        status_code=status_code,
        code=code,
        message=message,
        recovery_action=recovery_action,
        details=details,
        headers=headers,
    )
