"""Trusted registry verification and explicit offline artifact installation.

The manifest is reviewed source control, never supplied alongside an untrusted
download. Verify bytes before pickle deserialization and load those same bytes.
"""

import argparse
import hashlib
import importlib.metadata
import io
import json
import platform
import tempfile
import warnings
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning

from app.core.exceptions import ApplicationError
from app.ml.training.artifact import ModelBundle
from app.ml.training.metadata import (
    validate_artifact_consistency,
    validate_registry_consistency,
    write_json,
)

ML_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_REGISTRY = ML_DIRECTORY / "model_registry" / "dropout-risk-v1"
DEFAULT_MODEL = ML_DIRECTORY / "artifacts" / "dropout-risk-v1" / "model.joblib"
RUNTIME_PACKAGES = ("joblib", "numpy", "pandas", "scipy", "scikit-learn", "xgboost")


def runtime_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for package in RUNTIME_PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            # Linux uses the CPU-only distribution with the same import namespace.
            if package != "xgboost":
                raise
            versions[package] = importlib.metadata.version("xgboost-cpu")
    return versions


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def registry_sha256(payload: bytes) -> str:
    """Canonical JSON avoids Git's platform-dependent newline conversions."""
    return sha256(
        json.dumps(json.loads(payload), sort_keys=True, separators=(",", ":")).encode()
    )


def write_manifest(model: Path, registry: Path) -> None:
    """Called only by controlled training after its registry has been validated."""
    metadata = json.loads((registry / "metadata.json").read_bytes())
    write_json(
        registry / "artifact_manifest.json",
        {
            "format_version": 1,
            "model_version": metadata["model_version"],
            "artifact_sha256": sha256(model.read_bytes()),
            "registry_sha256": {
                name: registry_sha256((registry / name).read_bytes())
                for name in ("metadata.json", "evaluation.json", "split_manifest.json")
            },
            "runtime_versions": runtime_versions(),
        },
    )


def _error(code: str, message: str) -> ApplicationError:
    return ApplicationError(503, code, message)


def load_verified_model(
    model: Path, metadata_path: Path, evaluation_path: Path, manifest_path: Path
) -> tuple[ModelBundle, dict[str, Any], dict[str, Any]]:
    paths = (
        model,
        metadata_path,
        evaluation_path,
        manifest_path,
        metadata_path.parent / "split_manifest.json",
    )
    try:
        payload, metadata_bytes, evaluation_bytes, manifest_bytes, split_bytes = (
            path.read_bytes() for path in paths
        )
    except OSError as exc:
        raise _error(
            "MODEL_ARTIFACT_UNAVAILABLE",
            "The prediction model or its registry is unavailable.",
        ) from exc
    try:
        manifest = json.loads(manifest_bytes)
        metadata = json.loads(metadata_bytes)
        evaluation = json.loads(evaluation_bytes)
        split = json.loads(split_bytes)
        if manifest["format_version"] != 1:
            raise ValueError("Unsupported manifest format")
        expected = manifest["artifact_sha256"]
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or any(char not in "0123456789abcdef" for char in expected)
        ):
            raise ValueError("Invalid expected checksum")
        for name, content in (
            ("metadata.json", metadata_bytes),
            ("evaluation.json", evaluation_bytes),
            ("split_manifest.json", split_bytes),
        ):
            if registry_sha256(content) != manifest["registry_sha256"][name]:
                raise ValueError("Registry checksum mismatch")
        validate_registry_consistency(metadata, evaluation, split)
        if manifest["model_version"] != metadata["model_version"]:
            raise ValueError("Manifest model version mismatch")
        versions = manifest["runtime_versions"]
        for name, version in metadata["library_versions"].items():
            if name in versions and versions[name] != version:
                raise ValueError("Training versions disagree with manifest")
    except Exception as exc:
        raise _error(
            "MODEL_REGISTRY_MISMATCH", "The prediction model registry is inconsistent."
        ) from exc
    if not payload:
        raise _error(
            "MODEL_ARTIFACT_CORRUPTED",
            "The prediction model artifact is empty or corrupted.",
        )
    if sha256(payload) != expected:
        raise _error(
            "MODEL_CHECKSUM_MISMATCH",
            "The prediction model checksum does not match its trusted registry.",
        )
    try:
        if versions != runtime_versions():
            raise ValueError("Runtime dependency versions differ from training")
    except Exception as exc:
        raise _error(
            "MODEL_RUNTIME_INCOMPATIBLE",
            "The prediction model requires compatible runtime dependencies.",
        ) from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            bundle = joblib.load(io.BytesIO(payload))
    except Exception as exc:
        raise _error(
            "MODEL_ARTIFACT_CORRUPTED",
            "The prediction model artifact is empty or corrupted.",
        ) from exc
    try:
        if not isinstance(bundle, ModelBundle):
            raise TypeError("Unexpected bundle type")
        validate_artifact_consistency(bundle, metadata)
        # An actual inference probe ensures readiness means usable, not just loaded.
        reference = pd.DataFrame(
            [bundle.explanation_reference], columns=bundle.feature_names
        )
        bundle.predict_proba(reference)
        bundle.explain_local(reference, top_k=1)
    except Exception as exc:
        raise _error(
            "MODEL_REGISTRY_MISMATCH",
            "The prediction artifact does not match its registry record.",
        ) from exc
    return bundle, metadata, evaluation


def verify(model: Path = DEFAULT_MODEL, registry: Path = DEFAULT_REGISTRY):
    return load_verified_model(
        model,
        registry / "metadata.json",
        registry / "evaluation.json",
        registry / "artifact_manifest.json",
    )


def install(source: Path, destination: Path, registry: Path) -> None:
    # Freeze the source before verification so replacement cannot race the copy.
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staged = Path(temporary) / "model.joblib"
        try:
            staged.write_bytes(source.read_bytes())
        except OSError as exc:
            raise _error(
                "MODEL_ARTIFACT_UNAVAILABLE",
                "The source prediction model is unavailable.",
            ) from exc
        verify(staged, registry)
        staged.replace(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "install", "reproduce"))
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "reproduce":
            # Explicit, offline full training. Never called by startup or HTTP.
            from app.ml.training.train import run_training

            trusted = json.loads((args.registry / "metadata.json").read_bytes())
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                result = run_training(
                    root / "artifact",
                    root / "registry",
                    model_version=trusted["model_version"],
                )
                regenerated = result["metadata"]
                for document in (trusted, regenerated):
                    document.pop("trained_at")
                if (
                    trusted != regenerated
                    or result["evaluation"]
                    != json.loads((args.registry / "evaluation.json").read_bytes())
                    or registry_sha256(
                        (root / "registry" / "split_manifest.json").read_bytes()
                    )
                    != registry_sha256(
                        (args.registry / "split_manifest.json").read_bytes()
                    )
                ):
                    raise _error(
                        "MODEL_REGISTRY_MISMATCH",
                        "Reproduced training records differ; approve a new version and complete registry together.",
                    )
                install(root / "artifact" / "model.joblib", args.model, args.registry)
        elif args.action == "install":
            if args.source is None:
                parser.error("install requires --source")
            install(args.source, args.model, args.registry)
        bundle, _, _ = verify(args.model, args.registry)
    except ApplicationError as exc:
        parser.exit(1, f"{exc.code}: {exc.message}\n")
    print(f"Verified model: {bundle.model_version}")


if __name__ == "__main__":
    main()
