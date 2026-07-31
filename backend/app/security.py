import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    algorithm, rounds, salt_value, digest_value = encoded.split("$", 3)
    if algorithm != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_value)
    expected = base64.b64decode(digest_value)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
    return hmac.compare_digest(actual, expected)


def validate_password_policy(password: str) -> None:
    checks = (
        (len(password) >= 12, "密码至少需要 12 位"),
        (any(char.islower() for char in password), "密码必须包含小写字母"),
        (any(char.isupper() for char in password), "密码必须包含大写字母"),
        (any(char.isdigit() for char in password), "密码必须包含数字"),
        (
            any(not char.isalnum() for char in password),
            "密码必须包含特殊字符",
        ),
    )
    errors = [message for passed, message in checks if not passed]
    if errors:
        raise ValueError("；".join(errors))


def create_access_token(username: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def _fernet() -> Fernet:
    settings = get_settings()
    if settings.ai_config_encryption_key:
        key = settings.ai_config_encryption_key.encode()
    else:
        # 本地开发回退；生产环境应配置独立的 AI_CONFIG_ENCRYPTION_KEY。
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("AI 配置密钥无法解密，请检查 AI_CONFIG_ENCRYPTION_KEY") from exc


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:3]}••••••{value[-4:]}"
