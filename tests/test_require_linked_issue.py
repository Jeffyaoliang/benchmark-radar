"""A pull request that links no existing issue is closed; an API failure closes nothing."""

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(".github/scripts/require-linked-issue.sh").resolve()


def run_gate(
    tmp_path,
    *,
    body,
    kinds=None,
    api_down=False,
    current_body=None,
    state="open",
    pr_down=False,
    activity=None,
    activity_down=False,
    activity_endpoint="comments",
):
    # A fake `gh` answers the issues API from `kinds`, returns 404 for any other
    # number (or 502 when the API is down), and records every close.
    kinds = kinds or {}
    log = tmp_path / "calls.log"
    fake = tmp_path / "gh"
    cases = "".join(f'  *"issues/{n}"*) echo {kind};;\n' for n, kind in kinds.items())
    missing = (
        'echo "gh: Bad Gateway (HTTP 502)" >&2; exit 1'
        if api_down
        else 'echo "gh: Not Found (HTTP 404)" >&2; exit 1'
    )
    fake.write_text(
        "#!/usr/bin/env bash\n"
        'echo "$*" >> "$CALLS"\n'
        'if [[ "$1" == api ]]; then\n'
        '  case "$*" in\n'
        '  *"/comments"*|*"/reviews"*)\n'
        '    if [[ "$ACTIVITY_DOWN" == 1 ]]; then exit 1; fi\n'
        '    if [[ "$*" == *"/$ACTIVITY_ENDPOINT"* ]]; then echo "$ACTIVITY"; else echo "[[]]"; fi;;\n'
        '  *"pulls/900"*)\n'
        '    if [[ "$PR_DOWN" == 1 ]]; then exit 1; fi\n'
        '    echo "$CURRENT_PR";;\n'
        f"{cases if not api_down else ''}"
        f"  *) {missing};;\n"
        "  esac\n"
        "fi\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CALLS": str(log),
        "REPO": "ktwu01/benchmark-radar",
        "NUMBER": "900",
        "BODY": body,
        "PR_DOWN": str(int(pr_down)),
        "ACTIVITY": json.dumps(activity or [[]]),
        "ACTIVITY_DOWN": str(int(activity_down)),
        "ACTIVITY_ENDPOINT": activity_endpoint,
        "CURRENT_PR": json.dumps(
            {
                "state": state,
                "body": body if current_body is None else current_body,
                "user": {"login": "someone"},
            }
        ),
    }
    result = subprocess.run([str(SCRIPT)], env=env, capture_output=True, text=True)
    calls = log.read_text().splitlines() if log.exists() else []
    return result, [line for line in calls if line.startswith("pr close")]


@pytest.mark.parametrize(
    "body",
    [
        "Closes #411",
        "fixes #411 and more",
        "Related to #411",
        "Relates to: #411",
        "(closes #411)",
        "Part of ktwu01/benchmark-radar#411",
        "See https://github.com/ktwu01/benchmark-radar/issues/411",
        "Why\n\nCloses #411\n\n## Before and after",
    ],
)
def test_a_link_to_an_existing_issue_is_accepted(tmp_path, body):
    result, closes = run_gate(tmp_path, body=body, kinds={411: "issue"})
    assert result.returncode == 0
    assert closes == []


@pytest.mark.parametrize(
    "body",
    [
        "",
        "Condense leaderboard headings",
        "see #411",  # a bare mention is not a link
        "disclosed #411",  # a keyword inside a longer word is not a link
        "Closes #<issue number>",  # the unfilled template
        "Closes #999",  # the issue does not exist
        "Closes someone/else#411",  # another repository
    ],
)
def test_a_pr_without_an_existing_issue_is_closed(tmp_path, body):
    result, closes = run_gate(tmp_path, body=body, kinds={411: "issue"})
    assert result.returncode == 0
    assert len(closes) == 1


def test_a_link_to_a_pull_request_is_not_an_issue(tmp_path):
    result, closes = run_gate(tmp_path, body="Closes #411", kinds={411: "pr"})
    assert result.returncode == 0
    assert len(closes) == 1


def test_an_api_failure_leaves_the_pr_open(tmp_path):
    # Only a confirmed 404 means "no issue"; an outage must not close valid work.
    result, closes = run_gate(tmp_path, body="Closes #411", api_down=True)
    assert result.returncode != 0
    assert closes == []


def test_a_stale_event_uses_the_restored_current_link(tmp_path):
    result, closes = run_gate(tmp_path, body="", current_body="Closes #411", kinds={411: "issue"})
    assert result.returncode == 0
    assert closes == []


def test_a_stale_valid_link_does_not_hide_current_missing_link(tmp_path):
    result, closes = run_gate(tmp_path, body="Closes #411", current_body="", kinds={411: "issue"})
    assert result.returncode == 0
    assert len(closes) == 1


def test_a_currently_closed_pr_is_left_alone(tmp_path):
    result, closes = run_gate(tmp_path, body="", state="closed")
    assert result.returncode == 0
    assert closes == []


def test_a_failed_current_pr_lookup_leaves_the_pr_open(tmp_path):
    result, closes = run_gate(tmp_path, body="", pr_down=True)
    assert result.returncode != 0
    assert closes == []
