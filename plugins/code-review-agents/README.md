# Code Review Agents

Automates pull request code review using multiple specialized agents working in parallel. Five independent reviewers analyze your changes from different angles — CLAUDE.md compliance checking, bug detection, git history context analysis, previous PR comment review, and code comment verification. Each finding is scored on a 0-100 confidence scale, and only high-confidence issues (default threshold: 80) are posted as comments, dramatically reducing false positives and review noise.

The plugin intelligently filters out PRs that don't need review — closed, merged, draft, automated, or already-reviewed pull requests are automatically skipped. Comments include direct GitHub links with full SHA hashes and line number ranges for easy navigation to the exact code in question.

## How it works

```
/code-review-agents:code-review [pr-number-or-url] [--threshold 0-100] [--focus security,performance,accessibility]
        │
        ├─ Step 1-2: resolve the PR, apply skip filters (closed/merged/draft/automated/already-reviewed)
        ├─ Step 3:   gather the diff, changed files, base/head SHAs once for all agents
        ├─ Step 4:   dispatch five agents in parallel via the Agent tool
        │              claude-md-compliance   bug-detector   git-history-context
        │              pr-comment-history     comment-verification
        ├─ Step 5:   aggregate findings, drop anything below the confidence threshold, dedupe
        └─ Step 6-7: post a GitHub review (inline comments + summary), report back in chat
```

## Install

From this repository:

```bash
claude --plugin-dir ./plugins/code-review-agents
```

Then in that session, invoke it on the current branch's PR:

```
/code-review-agents:code-review
```

or target a specific PR:

```
/code-review-agents:code-review 42
/code-review-agents:code-review --threshold 70 --focus security,performance
```

To make it available in every session for this repo without the `--plugin-dir` flag, add it as a project-scoped plugin (see the [plugins guide](https://code.claude.com/docs/en/plugins)) or install it from a marketplace once one is set up.

## Configuration

Default confidence threshold and focus areas live at the top of [`commands/code-review.md`](./commands/code-review.md) in a `Configuration` section — edit the `CONFIDENCE_THRESHOLD`, `FOCUS_AREAS`, and `AUTOMATED_AUTHORS` values there for a permanent change, or pass `--threshold` / `--focus` on the command line for a one-off run.

## Agents

| Agent | What it checks |
|---|---|
| `claude-md-compliance` | Changed lines against every governing `CLAUDE.md` in the repo |
| `bug-detector` | Correctness, security, performance, and accessibility defects in the diff |
| `git-history-context` | Accidental reverts, contradicted rationale, and re-introduced bugs, via `git log`/`blame` |
| `pr-comment-history` | Whether prior review comments/threads on this PR were actually addressed |
| `comment-verification` | Whether comments/docstrings touched by the diff are still accurate |

Each agent returns a JSON array of findings with a `confidence` (0-100), `category`, `summary`, `detail`, and `suggestion`. Only the orchestrating command (`commands/code-review.md`) posts to GitHub — agents never call the GitHub write tools directly.
