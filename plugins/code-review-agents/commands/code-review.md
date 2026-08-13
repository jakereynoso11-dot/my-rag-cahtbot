---
description: Runs five parallel specialized review agents against a pull request and posts high-confidence findings as inline GitHub review comments.
argument-hint: "[pr-number-or-url] [--threshold 0-100] [--focus security,performance,accessibility]"
allowed-tools: Bash, Read, Grep, Glob, Agent, mcp__github__pull_request_read, mcp__github__pull_request_review_write, mcp__github__add_comment_to_pending_review, mcp__github__list_pull_requests, mcp__github__search_pull_requests, mcp__github__get_commit, mcp__github__list_commits, mcp__github__get_me
---

# Automated multi-agent PR code review

You are orchestrating an automated code review. Follow the steps below in order. Do not skip the skip-filters in Step 2 — they exist to keep this command from spamming PRs that don't need review.

## Configuration

Edit these values to change default behavior. Command-line overrides in `$ARGUMENTS` (see Step 1) take precedence over these defaults for a single run.

```yaml
# Minimum confidence (0-100) a finding needs to be posted as a review comment.
CONFIDENCE_THRESHOLD: 80

# Optional focus areas passed to the bug-detector agent to bias attention.
# Leave empty ([]) to weight all categories evenly.
# Example: ["security", "performance", "accessibility"]
FOCUS_AREAS: []

# Logins (without the trailing "[bot]") treated as automated PR authors to skip.
AUTOMATED_AUTHORS: ["dependabot", "renovate", "github-actions", "copilot-pull-request-reviewer"]

# Marker prefix used to detect "already reviewed this exact commit" and to
# recognize this tool's own prior comments. Do not change unless you also
# want to lose history-matching against past runs.
MARKER_PREFIX: "<!-- code-review-agents:reviewed"
```

## Step 1 — Resolve arguments

Parse `$ARGUMENTS` for:
- An optional PR number or PR URL (first bare token). If omitted, determine the current branch with `git rev-parse --abbrev-ref HEAD` and find the open PR whose head branch matches it (`mcp__github__list_pull_requests` with `head: "<owner>:<branch>"`, or `mcp__github__search_pull_requests` with `query: "is:pr head:<branch>"`).
- An optional `--threshold N` overriding `CONFIDENCE_THRESHOLD` for this run.
- An optional `--focus a,b,c` overriding `FOCUS_AREAS` for this run.

Determine `owner` and `repo` from the git remote (`git remote get-url origin`) if not otherwise obvious from context.

If no PR can be resolved at all, stop and tell the user you couldn't find a PR to review (don't guess).

## Step 2 — Skip filters

Fetch the PR with `mcp__github__pull_request_read` (`method: "get"`). Stop immediately, without posting anything, and report which filter matched, if any of the following is true:

1. **Closed or merged**: `state != "open"` or the PR is merged.
2. **Draft**: `draft == true`.
3. **Automated author**: the PR author's login (stripped of a trailing `[bot]`) is in `AUTOMATED_AUTHORS`, or the login ends in `[bot]` and isn't explicitly the user asking for this review.
4. **Already reviewed at this SHA**: fetch top-level comments (`mcp__github__pull_request_read`, `method: "get_comments"`) and check for a comment body containing `MARKER_PREFIX` followed by `sha=<current head SHA>`. The head SHA comes from the PR's `head.sha` field. If found, this exact commit was already reviewed — stop and report that.

Only proceed past this step for an open, non-draft PR from a non-automated author, at a commit that hasn't been reviewed yet.

## Step 3 — Gather shared context

Collect once, to hand to every agent (avoids each agent re-fetching the same data):

1. The PR's full diff: `mcp__github__pull_request_read` with `method: "get_diff"`.
2. The changed file list: `method: "get_files"`.
3. Base ref/SHA and head ref/SHA from the PR's `base` and `head` fields.
4. Make sure the repo is checked out at (or you can diff against) both refs locally: `git fetch origin <base> <head>` then you can run `git diff <base>...<head>` and `git log`/`git blame` against those refs directly with Bash for the agents that need it.

## Step 4 — Dispatch the five review agents in parallel

Launch all five agents from this plugin in a **single message with five parallel Agent tool calls** (`subagent_type` set to the plugin-scoped agent name below, `run_in_background: false` so you block on all five results before continuing), so they run concurrently rather than one at a time — the whole point is parallel independent review. Give each agent:
- The PR diff (or enough of it — for large diffs, at minimum the changed-file list plus the base/head SHAs so the agent can pull the diff itself via `git diff`)
- Base and head SHAs
- Repository root path
- `owner`, `repo`, `pullNumber` (for `pr-comment-history`)
- The effective `FOCUS_AREAS` for this run (for `bug-detector`)

Agents to dispatch:
1. `code-review-agents:claude-md-compliance`
2. `code-review-agents:bug-detector`
3. `code-review-agents:git-history-context`
4. `code-review-agents:pr-comment-history`
5. `code-review-agents:comment-verification`

Each agent returns a JSON array of findings (see each agent's own output contract). Wait for all five to complete before continuing — do not post anything based on partial results.

## Step 5 — Aggregate and filter

1. Parse each agent's JSON output. If an agent's output isn't valid JSON, treat it as `[]` for that agent and note the parse failure in your own summary rather than failing the whole run.
2. Concatenate all findings into one list.
3. Drop any finding with `confidence` below the effective threshold (`--threshold` override, else `CONFIDENCE_THRESHOLD`).
4. Deduplicate: when two findings target the same `file` and overlapping `startLine`-`endLine` ranges and describe substantially the same issue, keep only the higher-confidence one.
5. Cross-check each surviving finding's `file`/line range against the PR's actual diff hunks (`get_files`/`get_diff` from Step 3) — only findings that land on lines the diff actually touches (added/modified lines, i.e. the `RIGHT` side) can be posted as inline PR comments. If a finding is valid but lands outside the diff (e.g. a `git-history-context` finding about a nearby line the PR didn't literally touch), fall back to posting it in the summary comment body instead of as an inline comment, and say so.
6. Sort the remaining findings by confidence, descending.

## Step 6 — Post the review

1. Create a pending review: `mcp__github__pull_request_review_write`, `method: "create"`, `commitID` set to the head SHA.
2. For each surviving inline-eligible finding, call `mcp__github__add_comment_to_pending_review` with:
   - `path`: the finding's `file`
   - `side: "RIGHT"`
   - `line`: the finding's `endLine`; add `startLine`/`startSide: "RIGHT"` when `startLine != endLine` for a multi-line comment
   - `subjectType: "LINE"`
   - `body`: formatted as below
3. Comment body format for each finding:

   ```
   **[<category>] <summary>** (confidence: <confidence>/100)

   <detail>

   Suggested fix: <suggestion>

   <link to the exact head SHA + line range, e.g. https://github.com/<owner>/<repo>/blob/<head-sha>/<file>#L<startLine>-L<endLine>>

   ---
   _Generated by [Claude Code](https://claude.ai/code) — code-review-agents plugin_
   ```

4. Submit the pending review: `mcp__github__pull_request_review_write`, `method: "submit_pending"`, `event: "COMMENT"` (never auto-approve or auto-request-changes — this tool surfaces findings, it doesn't gate merges), with a top-level `body` that is a short summary:

   ```
   ## Automated code review

   <N> high-confidence finding(s) posted (threshold: <threshold>/100). <M> lower-confidence item(s) suppressed.

   | Agent | Findings posted |
   |---|---|
   | CLAUDE.md compliance | <n> |
   | Bug detection | <n> |
   | Git history context | <n> |
   | PR comment history | <n> |
   | Comment verification | <n> |

   <If any findings were valid but outside the diff, list them here as bullet points with file/line/summary instead of inline comments.>
   <If any agent's output failed to parse, note it here.>

   <!-- code-review-agents:reviewed sha=<head-sha> -->

   ---
   _Generated by [Claude Code](https://claude.ai/code) — code-review-agents plugin_
   ```

   The HTML comment marker is required even when there are zero findings — it's what makes Step 2's "already reviewed" filter work on the next run, so re-running this command on an unchanged PR doesn't repost.

5. If there are zero findings at or above threshold, still submit the review with `event: "COMMENT"` so the marker is posted, but keep the body to a one-line "No high-confidence issues found" plus the marker — don't pad it out.

## Step 7 — Report to the user

Tell the user, in your final chat response (not a GitHub comment): how many findings were posted, how many were suppressed as below-threshold, and a link to the PR. Keep it to a few sentences.
