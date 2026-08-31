#!/usr/bin/env python3
"""Run the existing architecture review chain behind Microsoft Entra sign-in."""

from __future__ import annotations

import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

from auth import EntraAuth

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_DIRECTORY = REPOSITORY_ROOT / "data" / "synthetic" / "submissions"
REVIEW_ENTRY_POINT = REPOSITORY_ROOT / "05-review-eval" / "run.py"
DEFAULT_RUN_LOG = Path(__file__).resolve().parent / "output" / "auth-runs.jsonl"


def available_submissions() -> dict[str, Path]:
    return {path.name: path for path in sorted(SUBMISSIONS_DIRECTORY.glob("SUB-*.md"))}


def create_auth_client() -> EntraAuth:
    client_id = os.getenv("ENTRA_CLIENT_ID")
    tenant_id = os.getenv("ENTRA_TENANT_ID")
    if not client_id or not tenant_id:
        raise RuntimeError("Set ENTRA_CLIENT_ID and ENTRA_TENANT_ID before signing in")
    redirect_uri = os.getenv(
        "AUTH_REDIRECT_URI", "http://localhost:5000/auth/callback"
    )
    return EntraAuth(client_id, tenant_id, redirect_uri)


def run_agent_chain(
    submission_path: Path,
    skip_research: bool,
    update_stage: Callable[[str], None],
) -> dict[str, Any]:
    command = [sys.executable, str(REVIEW_ENTRY_POINT), str(submission_path)]
    if skip_research:
        command.append("--skip-research")

    update_stage("standards")
    process = subprocess.Popen(
        command,
        cwd=REPOSITORY_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    stderr_lines: list[str] = []

    def read_stderr() -> None:
        for line in process.stderr:
            stderr_lines.append(line)
            if "Standards agent:" in line:
                update_stage("adr_author" if skip_research else "research")
            elif "Research agent:" in line:
                update_stage("adr_author")
            elif "ADR author agent:" in line:
                update_stage("reviewer")

    stderr_reader = threading.Thread(target=read_stderr, daemon=True)
    stderr_reader.start()
    stdout = process.stdout.read()
    return_code = process.wait()
    stderr_reader.join()

    if return_code != 0:
        detail = "".join(stderr_lines).strip() or "The architecture review chain failed"
        raise RuntimeError(detail)
    try:
        result = json.loads(stdout)
        return result["review"]["reviewed_adr"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError("The architecture review chain returned invalid output") from error


def append_run_record(log_path: Path, record: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as run_log:
        run_log.write(json.dumps(record, sort_keys=True) + "\n")


def execute_run(
    run_id: str,
    submission_name: str,
    submission_path: Path,
    skip_research: bool,
    user: dict[str, str],
    runs: dict[str, dict[str, Any]],
    runs_lock: threading.Lock,
    run_log_path: Path,
) -> None:
    def update_stage(stage: str) -> None:
        with runs_lock:
            runs[run_id]["status"] = stage

    try:
        reviewed_adr = run_agent_chain(submission_path, skip_research, update_stage)
        record = {
            "run_id": run_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "user": {
                "object_id": user["object_id"],
                "display_name": user["display_name"],
            },
            "submission": submission_name,
            "reviewed_adr": reviewed_adr,
        }
        append_run_record(run_log_path, record)
        with runs_lock:
            runs[run_id].update(status="complete", record=record)
    except Exception as error:
        with runs_lock:
            runs[run_id].update(status="failed", error=str(error))


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_bytes(32)
    app.config["RUN_LOG_PATH"] = DEFAULT_RUN_LOG
    # In-memory state is intentional for this single-presenter teaching harness.
    runs: dict[str, dict[str, Any]] = {}
    runs_lock = threading.Lock()
    app.config["RUNS"] = runs
    app.config["RUNS_LOCK"] = runs_lock

    @app.get("/")
    def index() -> str:
        if "user" in session and "form_token" not in session:
            session["form_token"] = secrets.token_urlsafe(32)
        return render_template(
            "index.html",
            user=session.get("user"),
            form_token=session.get("form_token"),
            submissions=available_submissions(),
        )

    @app.get("/auth/sign-in")
    def sign_in() -> Any:
        try:
            flow = create_auth_client().begin_sign_in()
        except RuntimeError as error:
            flash(str(error), "error")
            return redirect(url_for("index"))
        session["auth_flow"] = flow
        return redirect(flow["auth_uri"])

    @app.get("/auth/callback")
    def auth_callback() -> Any:
        flow = session.get("auth_flow")
        if not isinstance(flow, dict):
            abort(400, "Sign-in session not found")
        try:
            user = create_auth_client().complete_sign_in(
                flow, request.args.to_dict(flat=True)
            )
        except (RuntimeError, ValueError) as error:
            session.clear()
            flash(str(error), "error")
            return redirect(url_for("index"))
        session.clear()
        session["user"] = user
        return redirect(url_for("index"))

    @app.post("/auth/sign-out")
    def sign_out() -> Any:
        session.clear()
        return redirect(url_for("index"))

    @app.post("/review")
    def review() -> Any:
        user = session.get("user")
        if not isinstance(user, dict):
            return redirect(url_for("sign_in"))
        form_token = session.get("form_token", "")
        if not hmac.compare_digest(str(form_token), request.form.get("form_token", "")):
            abort(400, "Invalid form token")

        submission_name = request.form.get("submission", "")
        submission_path = available_submissions().get(submission_name)
        if submission_path is None:
            abort(400, "Select a valid synthetic submission")

        run_id = str(uuid4())
        run_user = {
            "object_id": str(user["object_id"]),
            "display_name": str(user["display_name"]),
        }
        with runs_lock:
            runs[run_id] = {
                "run_id": run_id,
                "status": "queued",
                "submission": submission_name,
                "user": run_user,
            }
        threading.Thread(
            target=execute_run,
            args=(
                run_id,
                submission_name,
                submission_path,
                request.form.get("skip_research") == "on",
                run_user,
                runs,
                runs_lock,
                Path(app.config["RUN_LOG_PATH"]),
            ),
            daemon=True,
        ).start()
        return redirect(url_for("run_status", run_id=run_id))

    @app.get("/runs/<run_id>")
    def run_status(run_id: str) -> Any:
        user = session.get("user")
        if not isinstance(user, dict):
            return redirect(url_for("sign_in"))
        with runs_lock:
            run = dict(runs.get(run_id, {}))
        if not run or run["user"]["object_id"] != user.get("object_id"):
            abort(404)
        return render_template("result.html", run=run)

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.getenv("AUTH_HOST", "127.0.0.1"),
        port=int(os.getenv("AUTH_PORT", "5000")),
        debug=False,
    )