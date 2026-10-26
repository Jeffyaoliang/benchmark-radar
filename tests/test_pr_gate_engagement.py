"""Maintainer engagement protects reviewed PRs in both automatic intake gates."""

import pytest
from test_open_item_cap import run_cap
from test_require_linked_issue import run_gate


@pytest.fixture(params=["linked", "cap"])
def gate(request, tmp_path):
    def run(**kwargs):
        if request.param == "linked":
            return run_gate(tmp_path, body="", **kwargs)
        return run_cap(tmp_path, author="someone", issues=5, prs=6, **kwargs)

    return run


@pytest.mark.parametrize(
    "endpoint", ["issues/900/comments", "pulls/900/reviews", "pulls/900/comments"]
)
@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_maintainer_activity_on_later_page_prevents_closure(gate, association, endpoint):
    result, closes = gate(
        activity_endpoint=endpoint,
        activity=[
            [],
            [
                {
                    "user": {"login": "maintainer", "type": "User"},
                    "author_association": association,
                }
            ],
        ],
    )
    assert result.returncode == 0
    assert closes == []


@pytest.mark.parametrize(
    "login,kind,association",
    [
        ("someone", "User", "OWNER"),
        ("SOMEONE", "User", "COLLABORATOR"),
        ("review-bot", "Bot", "MEMBER"),
        ("visitor", "User", "CONTRIBUTOR"),
    ],
)
def test_author_bot_and_visitor_activity_does_not_bypass_gate(gate, login, kind, association):
    result, closes = gate(
        activity=[
            [
                {
                    "user": {"login": login, "type": kind},
                    "author_association": association,
                }
            ]
        ]
    )
    assert result.returncode == 0
    assert len(closes) == 1


def test_discussion_api_failure_does_not_close_pr(gate):
    result, closes = gate(activity_down=True)
    assert result.returncode != 0
    assert closes == []
