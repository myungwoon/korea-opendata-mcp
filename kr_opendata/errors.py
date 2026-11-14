"""에러 계약 — 도구 실패는 "[코드] 메시지\n제안: ..." 형식으로 나간다."""

from __future__ import annotations

from fastmcp.exceptions import ToolError


class Code:
    CONFIG_ERROR = "CONFIG_ERROR"          # 해당 서비스의 API 키 없음
    AUTH_ERROR = "AUTH_ERROR"              # 키 오류, 활용신청 미승인, 호출 한도 초과
    NOT_FOUND = "NOT_FOUND"
    INVALID_PARAM = "INVALID_PARAMETER"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"      # 외부 서버 장애 — 대상이 없다는 뜻이 아님


class ApiError(ToolError):
    """코드를 가진 ToolError. 메시지는 그대로 클라이언트에 전달된다."""

    def __init__(self, code: str, message: str, *suggestions: str) -> None:
        self.code = code
        self.message = message
        text = f"[{code}] {message}"
        if suggestions:
            text += "\n제안:\n" + "\n".join(f"  {i}. {s}" for i, s in enumerate(suggestions, 1))
        super().__init__(text)
