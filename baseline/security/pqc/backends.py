"""
Pluggable PQC signature backends.

Default backend is a lightweight PQC-style interface (toy) intended for
benchmarking and integration validation. A real PQC backend can be enabled
via liboqs (python-oqs) when available.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Tuple


class PQCBackendError(RuntimeError):
    pass


@dataclass
class PQCBackend:
    name: str
    algorithm: str

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        raise NotImplementedError

    def sign(self, payload: bytes, private_key: bytes) -> bytes:
        raise NotImplementedError

    def verify(self, payload: bytes, public_key: bytes, signature: bytes) -> bool:
        raise NotImplementedError


class ToyBackend(PQCBackend):
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        priv = os.urandom(48)
        pub = hashlib.shake_256(priv + b"pub").digest(48)
        return priv, pub

    def sign(self, payload: bytes, private_key: bytes) -> bytes:
        pub = hashlib.shake_256(private_key + b"pub").digest(48)
        return hashlib.shake_256(pub + payload).digest(64)

    def verify(self, payload: bytes, public_key: bytes, signature: bytes) -> bool:
        expected = hashlib.shake_256(public_key + payload).digest(64)
        return expected == signature


class OQSBackend(PQCBackend):
    def __init__(self, algorithm: str) -> None:
        super().__init__(name="oqs", algorithm=algorithm)

        try:
            import oqs  # noqa: F401
        except Exception as exc:
            raise PQCBackendError(
                "python-oqs is not available; install it to use the oqs backend."
            ) from exc

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        import oqs

        with oqs.Signature(self.algorithm) as signer:
            public_key = signer.generate_keypair()
            private_key = signer.export_secret_key()
        return private_key, public_key

    def sign(self, payload: bytes, private_key: bytes) -> bytes:
        import oqs

        with oqs.Signature(self.algorithm) as signer:
            signer.import_secret_key(private_key)
            signature = signer.sign(payload)
        return signature

    def verify(self, payload: bytes, public_key: bytes, signature: bytes) -> bool:
        import oqs

        with oqs.Signature(self.algorithm) as verifier:
            return verifier.verify(payload, signature, public_key)


def get_backend(name: str, algorithm: str) -> PQCBackend:
    normalized = (name or "auto").strip().lower()
    algorithm = algorithm or "Dilithium2"

    if normalized in ("auto", "oqs"):
        try:
            return OQSBackend(algorithm)
        except PQCBackendError:
            if normalized == "oqs":
                raise
            return ToyBackend(name="toy", algorithm="toy-shake256")

    if normalized == "toy":
        return ToyBackend(name="toy", algorithm="toy-shake256")

    raise PQCBackendError(f"Unknown PQC backend: {name}")
