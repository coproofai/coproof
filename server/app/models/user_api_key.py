import os
import uuid
from base64 import urlsafe_b64encode, urlsafe_b64decode

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.extensions import db


def _get_kek() -> bytes:
    """Derive a 32-byte key-encryption key from SECRET_KEY."""
    raw = os.environ.get('SECRET_KEY', 'dev_key_change_in_production')
    # Pad/truncate to 32 bytes (AES-256 requires exactly 32)
    encoded = raw.encode('utf-8')
    return (encoded * ((32 // len(encoded)) + 1))[:32]


class UserApiKey(db.Model):
    """
    Stores per-user, per-model LLM API keys.

    The raw key is NEVER persisted in plaintext.
    - api_key_enc: AES-256-GCM ciphertext (nonce prepended), base64url-encoded.

    Usage:
        record = UserApiKey.create(user_id=uid, model_id="openai/gpt-4o", raw_key="sk-...")
        db.session.add(record)
        db.session.commit()

        raw = record.decrypt_key()
    """
    __tablename__ = 'user_api_keys'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    model_id = db.Column(db.Text, nullable=False)
    # AES-256-GCM(nonce || ciphertext), base64url-encoded
    api_key_enc = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        db.UniqueConstraint('user_id', 'model_id', name='uq_user_api_keys_user_model'),
    )

    # --- Relationships ---
    user = db.relationship('User', backref=db.backref('api_keys', lazy='dynamic'))

    # --- Encryption helpers ---

    @classmethod
    def _encrypt(cls, plaintext: str) -> str:
        kek = _get_kek()
        aesgcm = AESGCM(kek)
        nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        return urlsafe_b64encode(nonce + ciphertext).decode('utf-8')

    @classmethod
    def _decrypt(cls, encoded: str) -> str:
        kek = _get_kek()
        aesgcm = AESGCM(kek)
        raw = urlsafe_b64decode(encoded.encode('utf-8'))
        nonce, ciphertext = raw[:12], raw[12:]
        return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')

    # --- Factory ---

    @classmethod
    def create(cls, user_id: uuid.UUID, model_id: str, raw_key: str) -> 'UserApiKey':
        """Build a new record; does NOT add it to the session."""
        return cls(
            user_id=user_id,
            model_id=model_id,
            api_key_enc=cls._encrypt(raw_key),
        )

    # --- Instance methods ---

    def decrypt_key(self) -> str:
        """Return the raw API key in plaintext (for in-memory use only)."""
        return self._decrypt(self.api_key_enc)

    def masked_key(self) -> str:
        """Return a display-safe masked form, e.g. sk-***...abc"""
        try:
            raw = self.decrypt_key()
        except Exception:
            return '***'
        if len(raw) <= 8:
            return '***'
        return raw[:4] + '***...' + raw[-4:]

    def update_key(self, raw_key: str) -> None:
        """Re-encrypt and store a new key value."""
        self.api_key_enc = self._encrypt(raw_key)

    def __repr__(self) -> str:
        return f'<UserApiKey user={self.user_id} model={self.model_id}>'
