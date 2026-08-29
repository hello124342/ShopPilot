from __future__ import annotations


class AppError(RuntimeError):
    def __init__(self, error_code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


VALUE_ERROR_STATUS = {
    "run_not_found": (404, "运行记录不存在"),
    "platform_payload_not_found": (409, "运行尚未生成平台内容"),
    "artifact_version_mismatch": (409, "内容版本已变化，请刷新后重新审批"),
    "asset_not_found": (404, "资产不存在"),
    "asset_not_ready": (409, "资产当前不可访问"),
    "asset_hash_mismatch": (409, "资产完整性校验失败"),
    "asset_storage_missing": (409, "资产内容不可用"),
}


def from_value_error(exc: ValueError) -> AppError:
    code = str(exc)
    status, message = VALUE_ERROR_STATUS.get(code, (409, "当前操作与运行状态冲突"))
    return AppError(code, message, status)
