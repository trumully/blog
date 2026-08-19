---
title: My Agentic Development Workflow
date: 2026-08-19T09:12:41Z
tags: ["ai", "tools"]
---

Agentic development, for me, means delegating repository work to an AI agent while retaining responsibility for validating and understanding the result. I currently run this workflow through [Oh My Pi](https://github.com/can1357/oh-my-pi) (OMP), an agent harness for coding tasks, from VS Code in WSL.

I like to use a user-level `AGENTS.md` file at `~/.omp/agent/` to define agent's communication style:

```md
## How to communicate

- Follow Microsoft Writing Style Guide
- Follow Zinsser's core principles of writing: clarity, simplicity, brevity, humanity.
```

This has improved results from models such as Opus 5 which tend to be riddles littered with buzzwords.

In OMP, `modelRoles` assigns models to different kinds of work. I like to use [prewalk](https://stencil.so/blog/prewalk):

```yaml
modelRoles:
  default: openai-codex/gpt-5.6-luna:max
  slow: openai-codex/gpt-5.6-terra:high

prewalk:
  enabled: true
```

I use `default` for routine turns and `slow` for more demanding repository-level reasoning. `prewalk` starts the session with the stronger model, which reads the repository, establishes the constraints, and makes the first substantive change before OMP continues with the smaller model. This gives me frontier-level intelligence at a fraction of the cost.

For slightly more complex tasks I also use `advisor` to steer the active model when needed without having to provide every correction myself.

This produces fairly consistent output that I can validate, understand, and modify myself. Being able to own the output by understanding it myself is important; I do not want to be a [meat proxy](https://gruhn.me/blog/2026-08-03/).
