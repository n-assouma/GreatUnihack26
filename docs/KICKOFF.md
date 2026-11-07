# Kickoff (for humans)

## Before starting the agents (5 minutes, team lead)
1. Create the repo from the `hackathon-agent-board` template, open and pin the **Message Board** issue.
2. Copy this `docs/` folder into the repo root. Paste the owner table from `docs/PLAN.md` §6 into `AGENTS.md` §4
   and fill in the GitHub logins. Commit to `main`.
3. Everyone: `gh auth login`, then `tools/board whoami`.
4. Download the floor plan PDF (link in PLAN §10) and give it to Agent 3's human.
5. Nael: send the timetable screenshot to Agent 2's human.
6. Do **not** give `context.md` to the agents (event background only, too long).

## What each agent reads (exactly these 4 files, nothing else)
| Agent | Files |
|---|---|
| A1 Frontend | `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACTS.md`, `docs/agent-1-frontend.md` |
| A2 AI agents backend | `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACTS.md`, `docs/agent-2-agents.md` |
| A3 Indoor engine + data | `AGENTS.md`, `docs/PLAN.md`, `docs/CONTRACTS.md`, `docs/agent-3-indoor.md` |

## Prompts to paste (one per Claude Code session, at the repo root)

**Agent 1**
```
You are Agent 1 (Frontend) of a 3-agent hackathon team. Read only these files: AGENTS.md, docs/PLAN.md,
docs/CONTRACTS.md, docs/agent-1-frontend.md. Do not read other agents' files or context.md.
Start the board loop as AGENTS.md says, then start M0 immediately. Work through your file in order without
stopping; post on the board after each milestone. Ask me only for keys or decisions you cannot make.
Deadline: P0 by 14:30, everything by 15:30.
```

**Agent 2**
```
You are Agent 2 (AI agents backend) of a 3-agent hackathon team. Read only these files: AGENTS.md, docs/PLAN.md,
docs/CONTRACTS.md, docs/agent-2-agents.md. Do not read other agents' files or context.md.
Start the board loop as AGENTS.md says, then start M0 immediately. Work through your file in order without
stopping; post on the board after each milestone. Ask me only for keys, the timetable screenshot, or decisions
you cannot make. Deadline: P0 by 14:30, everything by 15:30.
```

**Agent 3**
```
You are Agent 3 (Indoor engine and building data) of a 3-agent hackathon team. Read only these files: AGENTS.md,
docs/PLAN.md, docs/CONTRACTS.md, docs/agent-3-indoor.md. Do not read other agents' files or context.md.
Start the board loop as AGENTS.md says, then start M0 immediately (others depend on your stub). Work through your
file in order without stopping; post on the board after each milestone. Ask me for the floor plan PDF and to check
your overlay images. Deadline: P0 by 14:30, everything by 15:30.
```
