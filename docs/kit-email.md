# Email subscriptions with Kit

Readers subscribe on benchmark-radar.org. Each day, a GitHub workflow sends that day's brief to them through Kit. This guide tells you how to set up, run, and repair the send.

## What is where

| Item | Where |
| --- | --- |
| Kit account | Owned by the maintainer, `ktwu01`. Nobody else needs a login. |
| Signup form | Kit form `10097391`. Both forms on the site post to `https://app.kit.com/forms/10097391/subscriptions`. |
| Cadence | Custom field `frequency`, with the value `daily` or `weekly`. |
| Audiences | Kit segments named exactly `Daily` (`frequency` is `daily`) and `Weekly` (`frequency` is `weekly`). |
| Workflow | `.github/workflows/send-email.yml`. It runs every day at 08:00 UTC. |
| Code | `src/benchmark_radar/email_brief.py`. It renders the email from `data/snapshots/<date>.json`. |
| Send record | A git tag `email/<date>` for each day that was sent. |

Weekly subscribers get Monday's daily brief until a weekly roundup exists (#979).

## Set up

1. In Kit, create the segments `Daily` and `Weekly` from the `frequency` field.
2. Write down the ID of each segment. The ID is the number in the segment's URL.
3. In Kit, go to Settings → Developer and create an API key.
4. In GitHub, go to Settings → Secrets and variables → Actions.
5. Add the secret `KIT_API_KEY` with the API key.
6. Add the variable `KIT_DAILY_SEGMENT_ID` with the Daily segment ID.
7. Add the variable `KIT_WEEKLY_SEGMENT_ID` with the Weekly segment ID.

The workflow stops before it sends if a segment ID is missing, or if a segment does not have its expected name.

## Run it by hand

1. In GitHub, open Actions → Send email brief → Run workflow.
2. Type a date, or leave the date empty for today in UTC.
3. Select a mode:
   - `preview` renders the email and attaches it to the run as `email.html`. It does not touch Kit.
   - `draft` saves the email as a draft in Kit. Send or delete the draft in Kit.
   - `send` schedules the email to the segments 10 minutes later.
4. Open the run and read the last step.

A manual run uses `preview` by default.

## Stop all sends

1. Set the repository variable `KIT_EMAIL_MODE` to `off`.
2. To cancel an email that is already scheduled, open it in Kit within 10 minutes and unschedule it.

To start sending again, delete the variable or set it to `send`.

## When a send fails

A failed run sends a notification email to the maintainer. Read the error in the run, then do the step for that error.

- **"Brief not live":** the day's page was not published by 08:00 UTC. Check the Deploy Dashboard run. When the page is live, run the workflow by hand in `send` mode for that date.
- **"Email not sent" with a Kit error:** do these steps in this order.
  1. Open Kit → Broadcasts and look for that day's subject.
  2. If Kit has the broadcast, do nothing more. The day was sent.
  3. If Kit does not have it, delete the tag with `git push origin :refs/tags/email/<date>`.
  4. Run the workflow by hand in `send` mode for that date.
- **"this day was sent or its send is unresolved":** the tag `email/<date>` exists. Do the steps above before you delete it.

The tag goes up before the workflow calls Kit. A day can be missed, but the list never gets the same day twice. Delete a tag only after you check Kit.

## Replace the API key

1. Create a new key in Kit.
2. Replace the `KIT_API_KEY` secret in GitHub.
3. Delete the old key in Kit.
4. Run the workflow by hand in `draft` mode to confirm the new key works. Delete the draft.

## Legal basics

- Keep double opt-in on in the form settings. It records when each subscriber confirmed.
- Every email has an unsubscribe link and the postal address. The template adds both through `{{ unsubscribe_url }}` and `{{ address }}`, and Kit refuses a broadcast without the unsubscribe link.
- The privacy notice in the site footer says what Kit stores and how to ask for deletion. Update it if the provider changes.
