"""
Pluggable PQC signature backends.

This project requires a real PQC backend via liboqs (python-oqs).
"""

from __future__ import annotations

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


class OQSBackend(PQCBackend):
    def __init__(self, algorithm: str) -> None:
        super().__init__(name="oqs", algorithm=algorithm)

        try:
            import oqs  # noqa: F401
        except Exception as exc:
            raise PQCBackendError(
                "python-oqs is not available; install it to use the oqs backend."
            ) from exc
        if not hasattr(oqs, "Signature"):
            raise PQCBackendError(
                "python-oqs is required (package name: python-oqs); "
                "the installed 'oqs' module lacks Signature."
            )

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
    normalized = (name or "oqs").strip().lower()
    algorithm = algorithm or "Dilithium2"

    if normalized == "oqs":
        return OQSBackend(algorithm)

    raise PQCBackendError(f"Unknown PQC backend: {name}")
