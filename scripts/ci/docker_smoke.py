"""Build and probe isolated release images; clean only this invocation's labelled objects."""

import argparse
import json
import os
import re
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def docker(*args, capture=False):
    result = subprocess.run(
        ["docker", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else None


def request(url, *, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        body = response.read()
        return (
            response.status,
            response.headers,
            json.loads(body)
            if "application/json" in response.headers.get("Content-Type", "")
            else body.decode(),
        )


def wait_http(url, container):
    for _ in range(90):
        state = docker(
            "inspect", container, "--format", "{{.State.Running}}", capture=True
        )
        if state != "true":
            raise RuntimeError("Smoke container exited before HTTP readiness")
        try:
            return request(url)
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise RuntimeError("HTTP readiness timeout: " + url)


def require_ownership(labels, project, owner):
    if (
        labels.get("com.docker.compose.project") != project
        or labels.get("org.student-warning.release-run") != owner
    ):
        raise RuntimeError("Refusing cleanup: Docker ownership labels do not match")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--backend-image", help="Verify an already built unchanged baseline image"
    )
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,60}", args.project):
        raise SystemExit("Invalid isolated project name")
    os.chdir(ROOT)
    label = "com.docker.compose.project=" + args.project
    owner = secrets.token_hex(6)
    owner_label = "org.student-warning.release-run=" + owner
    prefix = args.project + "-" + owner
    network = prefix + "-network"
    containers, images = [], []
    evidence = {
        "project": args.project,
        "run": owner,
        "http": [],
        "images": {},
        "result": "failed",
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        env_file = Path(temporary) / "smoke.env"
        password, initial_password = secrets.token_hex(24), secrets.token_hex(24)
        env_file.write_text(
            "\n".join(
                [
                    "POSTGRES_USER=release",
                    "POSTGRES_PASSWORD=" + password,
                    "POSTGRES_DB=release_gate",
                    "APP_ENV=production",
                    "DATABASE_URL=postgresql+psycopg://release:"
                    + password
                    + "@database:5432/release_gate",
                    "JWT_SECRET_KEY=" + secrets.token_hex(32),
                    "BOOTSTRAP_ADMIN_USERNAME=release_admin",
                    "BOOTSTRAP_ADMIN_EMAIL=release@example.edu",
                    "BOOTSTRAP_ADMIN_FULL_NAME=Disposable Release Admin",
                    "BOOTSTRAP_ADMIN_PASSWORD=" + initial_password,
                ]
            )
            + "\n"
        )
        env_file.chmod(0o600)
        try:
            for kind in ("backend", "frontend"):
                if kind == "frontend" and args.backend_only:
                    continue
                if kind == "backend" and args.backend_image:
                    image = args.backend_image
                else:
                    image = prefix + ":" + kind
                    docker(
                        "build",
                        "--label",
                        label,
                        "--label",
                        owner_label,
                        "-t",
                        image,
                        kind,
                    )
                    images.append(image)
                evidence["images"][kind] = docker(
                    "image", "inspect", image, "--format", "{{.Id}}", capture=True
                )
                if kind == "backend":
                    backend_image = image
                else:
                    frontend_image = image
            docker(
                "network", "create", "--label", label, "--label", owner_label, network
            )

            def start(service, image, *extra):
                name = prefix + "-" + service
                docker(
                    "run",
                    "-d",
                    "--name",
                    name,
                    "--label",
                    label,
                    "--label",
                    owner_label,
                    "--network",
                    network,
                    "--network-alias",
                    service,
                    "--env-file",
                    str(env_file),
                    *extra,
                    image,
                )
                containers.append(name)
                return name

            database = start(
                "database", "postgres:16-alpine", "--tmpfs", "/var/lib/postgresql/data"
            )
            for _ in range(60):
                ready = subprocess.run(
                    [
                        "docker",
                        "exec",
                        database,
                        "pg_isready",
                        "-U",
                        "release",
                        "-d",
                        "release_gate",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Disposable PostgreSQL readiness timeout")
            backend = start("backend", backend_image, "-p", "127.0.0.1::8000")
            port = docker("port", backend, "8000/tcp", capture=True).split(":")[-1]
            api = "http://127.0.0.1:" + port + "/api/v1"
            assert wait_http(api + "/health/ready", backend)[2]["status"] == "ready"
            assert request(api + "/health/live")[2] == {"status": "ok"}
            evidence["http"] += ["GET /health/live 200", "GET /health/ready 200 ready"]
            for module in ("app.ml.deployment", "app.ml.outcomes.deployment"):
                docker("exec", backend, "python", "-m", module, "verify")
            docker("exec", backend, "python", "-m", "pip", "check")
            try:
                request(api + "/students")
                raise AssertionError("Unauthenticated student access succeeded")
            except urllib.error.HTTPError as exc:
                assert exc.code == 401
            login = request(
                api + "/auth/login",
                data={"username": "release_admin", "password": initial_password},
            )[2]
            assert login["must_change_password"] is True
            changed = request(
                api + "/auth/change-password",
                token=login["access_token"],
                data={
                    "current_password": initial_password,
                    "new_password": secrets.token_hex(24),
                },
            )[2]
            assert changed["must_change_password"] is False
            assert (
                request(api + "/auth/me", token=changed["access_token"])[2]["role"]
                == "SYSTEM_ADMIN"
            )
            catalog = request(api + "/models", token=changed["access_token"])[2]
            assert len(catalog["items"]) == 3
            evidence["http"] += [
                "GET /students unauthenticated 401",
                "POST /auth/login 200 forced password change",
                "POST /auth/change-password 200",
                "GET /auth/me 200 SYSTEM_ADMIN",
                "GET /models 200 three models",
            ]
            if not args.backend_only:
                frontend = start("frontend", frontend_image, "-p", "127.0.0.1::3000")
                port = docker("port", frontend, "3000/tcp", capture=True).split(":")[-1]
                status, headers, body = wait_http(
                    "http://127.0.0.1:" + port + "/login", frontend
                )
                assert status == 200 and "<html" in body
                assert headers["X-Content-Type-Options"] == "nosniff"
                assert headers["X-Frame-Options"] == "DENY"
                evidence["http"].append(
                    "GET frontend /login 200 HTML with security headers"
                )
            evidence["result"] = "passed"
        finally:
            # Check both ownership labels before each deletion; never enumerate shared resources.
            for name in reversed(containers):
                labels = json.loads(
                    docker(
                        "container",
                        "inspect",
                        name,
                        "--format",
                        "{{json .Config.Labels}}",
                        capture=True,
                    )
                )
                require_ownership(labels, args.project, owner)
                docker("rm", "-f", name)
            networks = json.loads(
                docker(
                    "network",
                    "ls",
                    "--filter",
                    "name=^" + network + "$",
                    "--format",
                    "json",
                    capture=True,
                )
                or "{}"
            )
            if networks:
                data = json.loads(docker("network", "inspect", network, capture=True))[
                    0
                ]
                require_ownership(data["Labels"], args.project, owner)
                if data["Containers"]:
                    raise RuntimeError("Refusing cleanup: Docker network has endpoints")
                docker("network", "rm", network)
            for image in images:
                labels = json.loads(
                    docker(
                        "image",
                        "inspect",
                        image,
                        "--format",
                        "{{json .Config.Labels}}",
                        capture=True,
                    )
                )
                require_ownership(labels, args.project, owner)
                docker("image", "rm", image)
            evidence["cleanup"] = {
                "owned_containers_removed": len(containers),
                "owned_network_removed": True,
                "owned_image_tags_removed": len(images),
            }
            args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
