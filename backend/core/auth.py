"""
core/auth.py — Authentication, Password Hashing, JWT Tokens, and Multi-Tenant Context.

Provides:
  - Cryptographically secure PBKDF2-HMAC-SHA256 password hashing with unique per-user salts.
  - Standard HS256 JWT creation, signature verification, and expiration decoding.
  - Merchant API Key generation (e.g., `rec_live_...`).
  - FastAPI dependency for resolving the current authenticated merchant tenant
    with seamless fallback to default demo workspace (ensuring zero breakage for tests/daemons).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv

from logging_config import get_logger

load_dotenv()
logger = get_logger(__name__)

# Secret key for JWT signing (read from env or fallback to a deterministic local secret)
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "recoverai_dev_only_change-me")
if os.getenv("RECOVERAI_ENVIRONMENT", "development").lower() == "production":
    if JWT_SECRET_KEY == "recoverai_dev_only_change-me" or len(JWT_SECRET_KEY) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be set to a random 32+ character value in production.")
JWT_ALGORITHM: str = "HS256"
DEFAULT_TOKEN_EXPIRE_SECONDS: int = 86400 * 30  # 30 days

# Default demo user tenant fallback ID. Used by non-HTTP pipeline scripts only.
DEFAULT_USER_ID: str = "usr_default"

# Process-local revocation is sufficient for the current single-process API.
# Production deployments should use a shared session store.
_REVOKED_TOKENS: set[str] = set()

http_bearer_scheme = HTTPBearer(auto_error=False)


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a plaintext password using PBKDF2-HMAC-SHA256 with 100,000 rounds.
    Returns (hex_hash, hex_salt).
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    salt_bytes = bytes.fromhex(salt)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt_bytes,
        100_000,
        dklen=32
    )
    return key.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """
    Verify a password against stored PBKDF2 hash and salt using constant-time comparison.
    """
    try:
        expected_hash, _ = hash_password(password, salt)
        return hmac.compare_digest(expected_hash, password_hash)
    except Exception as e:
        logger.warning(f"Password verification failed with exception: {e}")
        return False


# ── JWT Token Implementation (Pure Standard Library) ──────────────────────────

def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')


def _b64_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4)) if len(data) % 4 != 0 else ''
    return base64.urlsafe_b64decode((data + padding).encode('utf-8'))


def create_access_token(
    payload: Dict[str, Any],
    expires_in_seconds: int = DEFAULT_TOKEN_EXPIRE_SECONDS
) -> str:
    """
    Create a signed HS256 JWT token string.
    """
    now = int(time.time())
    full_payload = {
        **payload,
        "iat": now,
        "exp": now + expires_in_seconds,
    }

    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    
    header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
    payload_json = json.dumps(full_payload, separators=(',', ':')).encode('utf-8')
    
    encoded_header = _b64_encode(header_json)
    encoded_payload = _b64_encode(payload_json)
    
    signing_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')
    signature = hmac.new(
        JWT_SECRET_KEY.encode('utf-8'),
        signing_input,
        hashlib.sha256
    ).digest()
    encoded_signature = _b64_encode(signature)
    
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a signed HS256 JWT token string.
    Returns the payload dictionary if valid, or None if expired/tampered.
    """
    try:
        if token in _REVOKED_TOKENS:
            return None
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        encoded_header, encoded_payload, encoded_signature = parts
        signing_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')
        
        expected_sig = hmac.new(
            JWT_SECRET_KEY.encode('utf-8'),
            signing_input,
            hashlib.sha256
        ).digest()
        actual_sig = _b64_decode(encoded_signature)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        
        payload_bytes = _b64_decode(encoded_payload)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        # Check expiration
        exp = payload.get("exp")
        if exp and int(time.time()) > exp:
            return None
        
        return payload
    except Exception as e:
        logger.debug(f"JWT decode error: {e}")
        return None


# ── API Key Generator ─────────────────────────────────────────────────────────

def generate_api_key(prefix: str = "rec_live_") -> str:
    """Generate a high-entropy merchant API key for live webhooks/APIs."""
    random_part = secrets.token_urlsafe(24).replace('-', '').replace('_', '')[:24]
    return f"{prefix}{random_part}"


# ── Current User Resolution & FastAPI Dependency ──────────────────────────────

def get_current_user_context(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = None
) -> Dict[str, Any]:
    """
    Resolve the current authenticated tenant user and merchant organization.
    
    Order of resolution:
    1. `Authorization: Bearer <jwt_token>` header
    2. `X-API-Key: <api_key>` header
    3. `api_key` or `token` query parameters
    Missing or invalid HTTP credentials are rejected. Non-HTTP pipeline code
    should use its explicit development defaults instead of this dependency.
    
    Returns a unified dict containing:
    - `user_id`
    - `email`
    - `full_name`
    - `role` (OWNER, ADMIN, MEMBER)
    - `merchant_id` (e.g. mer_default, mer_abc)
    - `merchant_name`
    - `business_name`
    - `api_key`
    """
    from db import fetch_user_by_id, fetch_user_by_api_key, fetch_user_by_email, fetch_merchant_by_id

    token: Optional[str] = None
    user_row = None

    # 1. Bearer Header
    if bearer and bearer.credentials:
        token = bearer.credentials
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    
    # Check token if present
    if token:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            user_row = fetch_user_by_id(payload["sub"])
    
    # 2. X-API-Key header
    if not user_row:
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if api_key:
            user_row = fetch_user_by_api_key(api_key)
    
    # 3. Query param token
    if not user_row:
        query_token = request.query_params.get("token")
        if query_token:
            payload = decode_access_token(query_token)
            if payload and "sub" in payload:
                user_row = fetch_user_by_id(payload["sub"])

    if not user_row:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_row["is_active"]:
        raise HTTPException(status_code=401, detail="User account is inactive.")
    
    if user_row:
        u_dict = dict(user_row)
        # Fetch associated merchant organization
        m_id = u_dict.get("merchant_id") or "mer_default"
        merchant_row = fetch_merchant_by_id(m_id)
        if merchant_row:
            m_dict = dict(merchant_row)
            u_dict["merchant_id"] = m_dict["merchant_id"]
            u_dict["merchant_name"] = m_dict["name"]
            u_dict["business_name"] = m_dict["business_name"]
            u_dict["company_name"] = m_dict["business_name"]
        else:
            u_dict["merchant_id"] = m_id
            u_dict["merchant_name"] = u_dict.get("company_name", "RecoverAI Retail")
            u_dict["business_name"] = u_dict.get("company_name", "RecoverAI Retail")
        return u_dict
    
def revoke_access_token(token: str) -> None:
    """Revoke a bearer token until process restart or token expiration."""
    _REVOKED_TOKENS.add(token)
