"""
Simple authentication helper for EchoConnect.
Provides a deterministic SHA‑256 based password hash used by the seed script
(and any other part of the code that needs to store passwords).
In a production setting you would replace this with bcrypt/argon2.
"""
import hashlib
import base64

def hash_password(plain: str) -> str:
    """Return a salted SHA‑256 hash.

    The format is ``salt$hash`` where ``salt`` is a static 16‑byte base64 string
    (suitable for demo/testing).  This keeps the seed script deterministic.
    """
    if not isinstance(plain, str):
        raise TypeError("Password must be a string")
    # Static salt for reproducibility in tests
    salt_bytes = b"static_salt_1234"
    salt = base64.urlsafe_b64encode(salt_bytes)[:16].decode()
    digest = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"
