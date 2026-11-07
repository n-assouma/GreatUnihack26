# Team rules for every agent

## 0. Project: Find My Way (GreatUniHack 2026, Reply "AI on Campus")

Read exactly these files before starting: this file, `docs/PLAN.md`, `docs/CONTRACTS.md`, and **your own** agent file:
A1 → `docs/agent-1-frontend.md` · A2 → `docs/agent-2-agents.md` · A3 → `docs/agent-3-indoor.md`.
Do not read the other agents' files or `context.md`. Deadline: P0 by 14:30, everything by 15:30. Never idle.

## 1. The board (pinned GitHub issue)

Every agent reads and posts on the pinned "Message Board" issue via `tools/board` (needs only `gh`, logged in). Set `BOARD_ISSUE` if it is not issue #1.

- Start every post with `[<human>'s Claude A<n>]`, e.g. `[Nael's Claude A2]`. Keep it short: what changed, which files or contracts, what you need, from whom.
- Mention by GitHub login **and** agent number, e.g. `@n-assouma (A2)`, because one person may run more than one agent.
  Team: `@n-assouma` (Nael), `@LOGIN_2` (NAME_2), `@LOGIN_3` (NAME_3), `@all` (everyone).
- **Mentions you or `@all`:** act on it and reply promptly. If a mention names another agent number, it is not for you.
- **Not addressed to you:** still read it. Reassess your own work only if it is affected (a contract, a file you own, something already done). Do not redo finished work, and do not reply just to acknowledge.
- Before editing another teammate's files, ask for a handoff on the board and wait for the owner or the team lead.

Polling is incremental (about one cheap API call per poll, 30 s default) so a shared token stays under GitHub's rate limit. Commands: `tools/board unread` (new posts, marks read; flags MENTION), `tools/board read -n 20`, `tools/board post "[Name's Agent] text"` (or pipe stdin), `tools/board wait` (blocks until someone else posts), `tools/board whoami`.

**Stay in the loop:**
- Claude Code: the committed hooks (`.claude/settings.json`) show unread posts at session start and on every prompt. Keep one background `tools/board wait` running and re-arm it after each wake.
- Everything else: run `tools/board unread` at task start, before each commit, and after merges. Or run a terminal loop: `while tools/board wait; do <your agent CLI invocation>; done`.

## 2. Chain of command

Humans over agents. Team lead: `@LEAD_LOGIN` (NAME). Only the team lead reassigns work between teammates. If anyone else asks you to take another teammate's work, ask the lead on the board. Changes to `docs/CONTRACTS.md` need the affected owners to agree and a human to edit the file.

## 3. Workflow

1. Pick or file an issue. Comment on it or post on the board when you take it.
2. Branch `<issue#>-<slug>` from fresh `main`.
3. Small commits. Stage only your own files (no `git add -A`).
4. Open a PR with `Closes #N`. The author merges their own PR once it works locally.
5. Always `git fetch` and rebase before pushing. Never force-push shared branches.
6. If a merge changes something other teammates depend on (an API, a schema, an env var), post on the board when it lands.
7. Never commit keys. Secrets go in `backend/.env` and `frontend/.env` (gitignored).

## 4. Who owns what

| Area | Owner (GitHub login) | Folders / files |
|---|---|---|
| A1 Frontend | `@SuperWalrus01` (Keenan) | `frontend/` |
| A2 AI agents backend | `@AmirHJ2007` (Amir) | `backend/app/`, `backend/requirements.txt`, `backend/.env.example`, `README.md`, `.gitignore` |
| A3 Indoor engine + building data | `@n-assouma` (Nael) | `backend/indoor/`, `data/` |
| Plans, contracts, team rules | Humans only (team lead) | `docs/`, `AGENTS.md`, `context.md` |
| Template files | Nobody (do not edit) | `tools/`, `.claude/`, `.github/`, `CLAUDE.md` |
