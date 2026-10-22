"""Provision only the approved retained artifact; never download or train a model."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKSUMS = {
    "dropout-risk-v1": "0cdc1e57f145626bba9f46c729685d4ae0968fc39b96564c09c548f7577f1bd8",
    "enrollment-outcome-v1": "bc3690bb930b3320e029673282e3e6c5bedccbfd332cdd28953677dbfc1c8602",
    "first-semester-outcome-v1": "2d6f7f80d6d6dcc2c844d9c3b714b1f5d7d92fa42d0a2db21fb3a3b139b5da81",
}


def verify_bytes(version, payload):
    manifest = (
        ROOT / "backend/app/ml/model_registry" / version / "artifact_manifest.json"
    )
    expected = CHECKSUMS[version]
    if json.loads(manifest.read_bytes())["artifact_sha256"] != expected:
        raise SystemExit("Approved manifest checksum changed: " + version)
    if hashlib.sha256(payload).hexdigest() != expected:
        raise SystemExit("Artifact checksum mismatch: " + version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    artifacts = ROOT / "backend/app/ml/artifacts"
    if not args.verify_only:
        if args.source:
            payload = args.source.read_bytes()
        else:
            encoded = os.environ.pop("LEGACY_MODEL_BASE64", "")
            if not encoded:
                raise SystemExit("Required LEGACY_MODEL_BASE64 secret is unavailable")
            try:
                payload = base64.b64decode(encoded, validate=True)
            except ValueError:
                raise SystemExit("Invalid legacy artifact encoding") from None
        verify_bytes("dropout-risk-v1", payload)
        target = artifacts / "dropout-risk-v1/model.joblib"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        target.chmod(0o600)
    for version in CHECKSUMS:
        verify_bytes(version, (artifacts / version / "model.joblib").read_bytes())
        print(version + ": approved SHA-256 verified")


if __name__ == "__main__":
    main()
