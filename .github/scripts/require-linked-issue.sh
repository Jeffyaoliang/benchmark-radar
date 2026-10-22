#!/usr/bin/env bash
# Close a pull request that does not link an existing issue.
#
# A PR with no issue is a change nobody asked for: it has no stated requirement
# to review against. Only a confirmed "not found" counts as a missing issue; any
# other API failure exits nonzero and leaves the PR open, so a GitHub outage
# never closes valid work. Read the current PR so a delayed edited event cannot
# close a PR whose issue link has already been restored.
set -euo pipefail

: "${REPO:?}" "${NUMBER:?}"
# Event snapshots may be stale by the time this run starts.
if ! current_pr="$(gh api "repos/$REPO/pulls/$NUMBER")"; then
  echo "could not read the current PR; leaving the pull request open" >&2
  exit 1
fi
state="$(jq -er '.state' <<<"$current_pr")"
[[ "$state" == "open" ]] || exit 0
BODY="$(jq -r '.body // ""' <<<"$current_pr")"
err="$(mktemp)"

# `Closes #N`, `Related to #N`, `owner/repo#N`, or an issue URL. The keyword must
# start a word, so "disclosed #5" is not a link.
keywords='(close[sd]?|fix(e[sd])?|resolve[sd]?|relate[sd]? to|refs?|part of)'
refs="$(
  {
    grep -oiE "(^|[^A-Za-z0-9_])${keywords}:? +([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)?#[0-9]+" <<<"$BODY" || true
    grep -oiE "github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/issues/[0-9]+" <<<"$BODY" || true
  } | sed -E 's|^[^A-Za-z]+||; s|^.*github\.com/([^/]+/[^/]+)/issues/([0-9]+)$|\1#\2|; s|^[A-Za-z ]+:? +||'
)"

for ref in $refs; do
  number="${ref##*#}"
  repo="${ref%#*}"
  [[ -z "$repo" ]] && repo="$REPO"
  [[ "${repo,,}" == "${REPO,,}" ]] || continue
  # The issues API also returns pull requests, so tell them apart.
  if kind="$(gh api "repos/$REPO/issues/$number" --jq 'if .pull_request then "pr" else "issue" end' 2>"$err")"; then
    if [[ "$kind" == "issue" ]]; then
      echo "linked issue #$number found"
      exit 0
    fi
  elif grep -q "HTTP 404" "$err"; then
    echo "#$number does not exist"
  else
    echo "could not look up #$number; leaving the pull request open" >&2
    cat "$err" >&2
    exit 1
  fi
done

message="Closing: this pull request does not link an existing issue. Every change starts from an issue, so reviewers have a stated requirement to check it against.

Open or pick an issue first. Then reopen this PR with \`Closes #N\` (or \`Related to #N\` if it is one step of a larger issue) in the description, and fill in the pull request template.

已关闭：此 PR 没有关联任何已有 issue。每个改动都应从 issue 出发，评审才有明确的要求可以对照。

请先创建或认领一个 issue，然后在 PR 描述里写 \`Closes #N\`（只完成一部分则写 \`Related to #N\`），按模板补全后再 reopen。"

gh pr close "$NUMBER" --repo "$REPO" --comment "$message"
