"""Disposable E1 stack. Credentials stay in ignored .venv/e1/session.json."""

import argparse
import json
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / ".venv/e1"
STATE = PRIVATE / "session.json"
LABEL = "org.student-warning.acceptance"


def docker(*args, capture=False):
    result = subprocess.run(
        ["docker", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else None


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def wait_http(url):
    for _ in range(90):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(1)
    raise RuntimeError("HTTP readiness timeout: " + url)


def save(state):
    PRIVATE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    STATE.chmod(0o600)


def owned(kind, name, state):
    item = json.loads(docker(kind, "inspect", name, capture=True))[0]
    labels = (
        item["Config"].get("Labels") if kind != "network" else item.get("Labels")
    ) or {}
    if labels.get(LABEL) != state["project"]:
        raise RuntimeError("Refusing action on resource without matching E1 ownership")
    return item


def up():
    if STATE.exists():
        raise SystemExit("E1 session already exists; use down before creating another")
    subprocess.run(
        [sys.executable, "scripts/ci/provision_models.py", "--verify-only"],
        cwd=ROOT,
        check=True,
    )
    backend_port, frontend_port = free_port(), free_port()
    while frontend_port == backend_port:
        frontend_port = free_port()
    state = {
        "project": "e1-acceptance-" + secrets.token_hex(5),
        "api": f"http://127.0.0.1:{backend_port}/api/v1",
        "baseURL": f"http://127.0.0.1:{frontend_port}",
        "database_password": secrets.token_hex(24),
        "jwt_secret": secrets.token_hex(32),
        "users": {
            name: {
                "username": "e1_" + name,
                "initial": secrets.token_hex(20),
                "password": secrets.token_hex(20),
            }
            for name in ("system", "academic", "advisor", "other_advisor", "disposable")
        },
    }
    save(state)
    project = state["project"]
    env = PRIVATE / "stack.env"
    env.write_text(
        "\n".join(
            [
                "POSTGRES_USER=release",
                "POSTGRES_PASSWORD=" + state["database_password"],
                "POSTGRES_DB=release_gate",
                "APP_ENV=production",
                f"DATABASE_URL=postgresql+psycopg://release:{state['database_password']}@database:5432/e1_demo",
                "JWT_SECRET_KEY=" + state["jwt_secret"],
                "CORS_ORIGINS=" + state["baseURL"],
                "BOOTSTRAP_ADMIN_USERNAME=e1_system",
                "BOOTSTRAP_ADMIN_EMAIL=e1_system@example.edu",
                "BOOTSTRAP_ADMIN_FULL_NAME=E1 Synthetic System Admin",
                "BOOTSTRAP_ADMIN_PASSWORD=" + state["users"]["system"]["initial"],
            ]
        )
        + "\n"
    )
    env.chmod(0o600)
    docker("network", "create", "--label", LABEL + "=" + project, project)
    docker(
        "build",
        "--label",
        LABEL + "=" + project,
        "-t",
        project + ":backend",
        str(ROOT / "backend"),
    )
    docker(
        "run",
        "-d",
        "--name",
        project + "-database",
        "--label",
        LABEL + "=" + project,
        "--network",
        project,
        "--network-alias",
        "database",
        "--env-file",
        str(env),
        "--tmpfs",
        "/var/lib/postgresql/data",
        "postgres:16-alpine",
    )
    for _ in range(60):
        result = subprocess.run(
            ["docker", "exec", project + "-database", "pg_isready", "-U", "release"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("PostgreSQL did not become ready")
    docker(
        "exec",
        project + "-database",
        "psql",
        "-U",
        "release",
        "-d",
        "release_gate",
        "-c",
        "CREATE DATABASE e1_demo",
    )
    docker(
        "run",
        "-d",
        "--name",
        project + "-backend",
        "--label",
        LABEL + "=" + project,
        "--network",
        project,
        "--env-file",
        str(env),
        "-p",
        f"127.0.0.1:{backend_port}:8000",
        project + ":backend",
    )
    wait_http(state["api"] + "/health/ready")
    rebuild_frontend(state)
    print(
        json.dumps(
            {"project": project, "frontend": state["baseURL"], "api": state["api"]}
        )
    )


def rebuild_frontend(state):
    project = state["project"]
    docker(
        "build",
        "--label",
        LABEL + "=" + project,
        "--build-arg",
        "NEXT_PUBLIC_API_URL=" + state["api"],
        "-t",
        project + ":frontend",
        str(ROOT / "frontend"),
    )
    existing = docker(
        "ps", "-aq", "--filter", "name=^" + project + "-frontend$", capture=True
    )
    if existing:
        owned("container", project + "-frontend", state)
        docker("rm", "-f", project + "-frontend")
    port = state["baseURL"].rsplit(":", 1)[1]
    docker(
        "run",
        "-d",
        "--name",
        project + "-frontend",
        "--label",
        LABEL + "=" + project,
        "--network",
        project,
        "-p",
        f"127.0.0.1:{port}:3000",
        project + ":frontend",
    )
    wait_http(state["baseURL"] + "/login")


def regress(state):
    project = state["project"]
    context = PRIVATE / "regression-context"
    context.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ROOT / "backend/tests",
        context / "tests",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(
        ROOT / "scripts/ci",
        context / "scripts/ci",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for name in ("requirements-dev.txt", "pyproject.toml"):
        shutil.copyfile(ROOT / "backend" / name, context / name)
    (context / "Dockerfile").write_text(f"""FROM {project}:backend
USER root
RUN mkdir /repo && cp -a /app /repo/backend
COPY requirements-dev.txt /repo/backend/
RUN python -m pip install --index-url https://pypi.org/simple -r /repo/backend/requirements-dev.txt
COPY tests /repo/backend/tests
COPY pyproject.toml /repo/backend/
COPY scripts /repo/scripts
WORKDIR /repo/backend
USER app
""")
    docker(
        "build",
        "--label",
        LABEL + "=" + project,
        "-t",
        project + ":regression",
        str(context),
    )
    env = PRIVATE / "regression.env"
    url = f"postgresql+psycopg://release:{state['database_password']}@database:5432/release_gate"
    settings = {
        name: url
        for name in (
            "MODEL_TEST_DATABASE_URL",
            "DUAL_STAGE_TEST_DATABASE_URL",
            "STAGED_IMPORT_TEST_DATABASE_URL",
            "USER_MANAGEMENT_TEST_DATABASE_URL",
            "FRESHNESS_TEST_DATABASE_URL",
            "C1_CASEWORK_TEST_DATABASE_URL",
            "D1_AUDIT_TEST_DATABASE_URL",
        )
    }
    settings.update(
        APP_ENV="test",
        ML_MODEL_REQUIRED="false",
        RUN_MODEL_INTEGRATION="1",
        RELEASE_DISPOSABLE_POSTGRES="1",
        JWT_SECRET_KEY=state["jwt_secret"],
        RELEASE_EVIDENCE_DIR="/tmp/evidence",
    )
    env.write_text("".join(f"{key}={value}\n" for key, value in settings.items()))
    env.chmod(0o600)
    result = subprocess.run(
        [
            "docker",
            "run",
            "--name",
            project + "-regression",
            "--label",
            LABEL + "=" + project,
            "--network",
            project,
            "--env-file",
            str(env),
            project + ":regression",
            "python",
            "../scripts/ci/release_backend.py",
        ]
    )
    for name in ("backend.xml", "backend-summary.json"):
        docker("cp", project + "-regression:/tmp/evidence/" + name, str(PRIVATE / name))
    raise SystemExit(result.returncode)


def down(state):
    project = state["project"]
    for name in docker(
        "ps", "-aq", "--filter", "label=" + LABEL + "=" + project, capture=True
    ).splitlines():
        owned("container", name, state)
        docker("rm", "-f", name)
    network = owned("network", project, state)
    if network["Containers"]:
        raise RuntimeError("Refusing cleanup of network with remaining endpoints")
    docker("network", "rm", project)
    for tag in ("regression", "frontend", "backend"):
        reference = project + ":" + tag
        if docker("image", "ls", "-q", reference, capture=True):
            owned("image", reference, state)
            docker("image", "rm", reference)
    # A rebuild may leave an older, untagged image. Select only this invocation's
    # labelled images; never prune caches or remove a tagged/referenced image.
    for image_id in docker(
        "image",
        "ls",
        "-q",
        "--filter",
        "label=" + LABEL + "=" + project,
        "--filter",
        "dangling=true",
        capture=True,
    ).splitlines():
        item = owned("image", image_id, state)
        references = docker(
            "ps", "-aq", "--filter", "ancestor=" + image_id, capture=True
        )
        if item.get("RepoTags") or references:
            raise RuntimeError("Refusing cleanup of referenced E1 image")
        docker("image", "rm", image_id)
    STATE.rename(PRIVATE / (project + "-closed-session.json"))
    print("Removed only resources labelled " + LABEL + "=" + project)


def reset_demo(state):
    project = state["project"]
    owned("container", project + "-database", state)
    owned("container", project + "-backend", state)
    docker("rm", "-f", project + "-backend")
    docker(
        "exec",
        project + "-database",
        "psql",
        "-U",
        "release",
        "-d",
        "release_gate",
        "-c",
        "DROP DATABASE e1_demo WITH (FORCE)",
    )
    docker(
        "exec",
        project + "-database",
        "psql",
        "-U",
        "release",
        "-d",
        "release_gate",
        "-c",
        "CREATE DATABASE e1_demo",
    )
    port = state["api"].split(":")[2].split("/")[0]
    docker(
        "run",
        "-d",
        "--name",
        project + "-backend",
        "--label",
        LABEL + "=" + project,
        "--network",
        project,
        "--env-file",
        str(PRIVATE / "stack.env"),
        "-p",
        f"127.0.0.1:{port}:8000",
        project + ":backend",
    )
    wait_http(state["api"] + "/health/ready")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("up", "frontend", "regress", "reset-demo", "down")
    )
    args = parser.parse_args()
    if args.action == "up":
        up()
    else:
        session = json.loads(STATE.read_text())
        {
            "frontend": rebuild_frontend,
            "regress": regress,
            "reset-demo": reset_demo,
            "down": down,
        }[args.action](session)
