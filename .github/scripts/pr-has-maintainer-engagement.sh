#!/usr/bin/env bash
# Human review must not be undone by an automated intake gate.
# Exit 0 protects the PR, 1 allows intake checks, and 2 fails safely on API errors.
set -euo pipefail
: "${REPO:?}" "${NUMBER:?}"
if ! pr="$(gh api "repos/$REPO/pulls/$NUMBER")"; then
  exit 2
fi
if [[ "$(jq -er '.state' <<<"$pr")" != open ]]; then
  exit 0
fi
author="$(jq -er '.user.login' <<<"$pr")"
for endpoint in "issues/$NUMBER/comments" "pulls/$NUMBER/reviews" "pulls/$NUMBER/comments"; do
  if ! pages="$(gh api --paginate --slurp "repos/$REPO/$endpoint")"; then
    exit 2
  fi
  if ! engaged="$(jq -er --arg author "$author" '
    [ .[][] | select(
        .user.type == "User" and
        (.user.login | ascii_downcase) != ($author | ascii_downcase) and
        (.author_association == "OWNER" or .author_association == "MEMBER" or
         .author_association == "COLLABORATOR")
    ) ] | length > 0' <<<"$pages")"; then
    # jq -e returns 1 for the valid boolean false.
    [[ "$engaged" == false ]] || exit 2
  fi
  if [[ "$engaged" == true ]]; then
    echo "Maintainer engagement found; leaving closure to maintainers"
    exit 0
  fi
done
exit 1
