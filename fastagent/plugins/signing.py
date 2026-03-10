from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().lower()


def load_private_key(private_key_path: Path) -> Ed25519PrivateKey:
    if not private_key_path.exists():
        raise FileNotFoundError(f"Private key not found: {private_key_path}")
    key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Private key must be an Ed25519 private key")
    return key


def load_public_key(public_key_path: Path) -> Ed25519PublicKey:
    if not public_key_path.exists():
        raise FileNotFoundError(f"Public key not found: {public_key_path}")
    key = serialization.load_pem_public_key(public_key_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Public key must be an Ed25519 public key")
    return key


def public_key_to_base64(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def generate_keypair(private_key_path: Path, public_key_path: Path, overwrite: bool = False) -> dict:
    if (private_key_path.exists() or public_key_path.exists()) and not overwrite:
        raise ValueError("Key file already exists. Use --overwrite to replace.")

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_bytes(private_pem)
    public_key_path.write_bytes(public_pem)

    return {
        "private_key_path": str(private_key_path),
        "public_key_path": str(public_key_path),
        "public_key_base64": public_key_to_base64(public_key),
    }


def sign_payload(payload: bytes, private_key: Ed25519PrivateKey) -> str:
    signature = private_key.sign(payload)
    return base64.b64encode(signature).decode("ascii")


def verify_signature(payload: bytes, signature_b64: str, public_key_b64: str) -> None:
    try:
        signature = base64.b64decode(signature_b64)
    except Exception as exc:
        raise ValueError(f"Invalid signature base64: {exc}") from exc
    try:
        public_raw = base64.b64decode(public_key_b64)
    except Exception as exc:
        raise ValueError(f"Invalid public key base64: {exc}") from exc

    public_key = Ed25519PublicKey.from_public_bytes(public_raw)
    try:
        public_key.verify(signature, payload)
    except Exception as exc:
        raise ValueError(f"Signature verification failed: {exc}") from exc
