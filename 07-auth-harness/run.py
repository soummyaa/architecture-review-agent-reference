#!/usr/bin/env python3
"""Run the existing architecture review chain behind Microsoft Entra sign-in."""

from __future__ import annotations

import hmac
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

from auth import EntraAuth

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SUBMISSIONS_DIRECTORY = REPOSITORY_ROOT / "data" / "synthetic" / "submissions"
REVIEW_ENTRY_POINT = REPOSITORY_ROOT / "06-review-eval" / "run.py"
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


def run_agent_chain(submission_path: Path, skip_research: bool) -> dict[str, Any]:
    command = [sys.executable, str(REVIEW_ENTRY_POINT), str(submission_path)]
    if skip_research:
        command.append("--skip-research")

    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "The architecture review chain failed"
        raise RuntimeError(detail)
    try:
        result = json.loads(completed.stdout)
        return result["review"]["reviewed_adr"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError("The architecture review chain returned invalid output") from error


def append_run_record(log_path: Path, record: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as run_log:
        run_log.write(json.dumps(record, sort_keys=True) + "\n")


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_bytes(32)
    app.config["RUN_LOG_PATH"] = DEFAULT_RUN_LOG

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

        try:
            reviewed_adr = run_agent_chain(
                submission_path,
                skip_research=request.form.get("skip_research") == "on",
            )
        except RuntimeError as error:
            flash(str(error), "error")
            return redirect(url_for("index"))

        record = {
            "run_id": str(uuid4()),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "user": {
                "object_id": str(user["object_id"]),
                "display_name": str(user["display_name"]),
            },
            "submission": submission_name,
            "reviewed_adr": reviewed_adr,
        }
        append_run_record(Path(app.config["RUN_LOG_PATH"]), record)
        return render_template("result.html", record=record)

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.getenv("AUTH_HOST", "127.0.0.1"),
        port=int(os.getenv("AUTH_PORT", "5000")),
        debug=False,
    )