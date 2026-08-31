"""Symmetric encryption for secrets that must never be stored as plain text
(Epic 10: Social Media Account Management - "Never store social access
tokens as plain text.").

The Fernet key is derived deterministically from SECRET_KEY so no new
required env var is needed in development, while production deployments can
still set SOCIAL_TOKEN_ENCRYPTION_KEY explicitly to use a key independent of
SECRET_KEY (recommended, since rotating SECRET_KEY would otherwise also
silently break decryption of every stored token).
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    raw_key = getattr(settings, 'SOCIAL_TOKEN_ENCRYPTION_KEY', '') or settings.SECRET_KEY
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode('utf-8')).digest())
    return Fernet(derived_key)


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ''
    return _fernet().encrypt(plaintext.encode('utf-8')).decode('ascii')


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ''
    try:
        return _fernet().decrypt(ciphertext.encode('ascii')).decode('utf-8')
    except InvalidToken:
        return ''
