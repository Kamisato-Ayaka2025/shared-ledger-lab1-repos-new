"""Domain values shared by the application and its tests."""

from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import uuid


class BusinessError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def require(condition: bool, message: str, status: int = 400) -> None:
    if not condition:
        raise BusinessError(message, status)


def money(value: object, *, zero: bool = False) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BusinessError("金额必须为数字") from None
    require(amount.is_finite(), "金额必须为有限数字")
    require(amount >= 0 if zero else amount > 0, "金额必须为非负数" if zero else "金额必须大于零")
    require(amount <= Decimal("999999999999.99"), "金额超过单笔上限")
    require(amount * 100 == (amount * 100).to_integral_value(), "金额最多两位小数")
    return int(amount * 100)


def uid() -> str:
    return str(uuid.uuid4())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(value: object, label: str, limit: int = 200) -> str:
    result = str(value or "").strip()
    require(bool(result), f"请填写{label}")
    require(len(result) <= limit, f"{label}不能超过 {limit} 字")
    return result
