# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Remove signs of AI-generated writing from text | humanizer | /home/jhonh/.config/opencode/skills/humanizer/SKILL.md |
| When creating a GitHub issue, reporting a bug, or requesting a feature | issue-creation | /home/jhonh/.config/opencode/skills/issue-creation/SKILL.md |
| When creating a pull request, opening a PR, or preparing changes for review | branch-pr | /home/jhonh/.config/opencode/skills/branch-pr/SKILL.md |
| When user asks to create a new skill, add agent instructions, or document patterns for AI | skill-creator | /home/jhonh/.config/opencode/skills/skill-creator/SKILL.md |
| When writing Go tests, using teatest, or adding test coverage | go-testing | /home/jhonh/.config/opencode/skills/go-testing/SKILL.md |
| When user says "judgment day", "judgment-day", "review adversarial", "dual review", "doble review", "juzgar", "que lo juzguen" | judgment-day | /home/jhonh/.config/opencode/skills/judgment-day/SKILL.md |
| When user asks to "write documentation", "create README", "API docs", "design document", "specification", "user guide", or needs documentation guidance | technical-documentation | /home/jhonh/.config/opencode/skills/technical-documentation/SKILL.md |
| ragas, deepeval, llm-eval, faithfulness, hallucination-check, synthetic-data | eval-frameworks | /home/jhonh/.config/opencode/skills/eval-frameworks/SKILL.md |
| "evaluate agent performance", "build test framework", "measure agent quality", "create evaluation rubrics", LLM-as-judge, multi-dimensional evaluation, agent testing, quality gates | evaluation | /home/jhonh/.config/opencode/skills/evaluation/SKILL.md |

## Compact Rules

### humanizer
- Identify and rewrite AI writing patterns: inflated symbolism, promotional language, superficial -ing analyses, vague attributions, em dash overuse, rule of three, AI vocabulary, passive voice, negative parallelisms, filler phrases
- Preserve meaning and match intended tone; add personality and opinions rather than sterile neutrality
- Final anti-AI pass: ask "What makes the below so obviously AI generated?" then "Now make it not obviously AI generated" and revise
- Replace chatbot artifacts ("I hope this helps!", "Here is...") with direct statements
- Remove knowledge-cutoff disclaimers and sycophantic tone

### issue-creation
- Blank issues are disabled — MUST use a template (bug report or feature request)
- Every issue gets `status:needs-review` automatically; maintainer MUST add `status:approved` before any PR
- Search existing issues for duplicates before creating
- Questions go to Discussions, NOT issues
- Use `gh issue create --template` with correct type and pre-flight checkboxes

### branch-pr
- Every PR MUST link an approved issue (`Closes #N`, `Fixes #N`, `Resolves #N`)
- Every PR MUST have exactly one `type:*` label
- Branch naming: `^(feat|fix|chore|docs|style|refactor|perf|test|build|ci|revert)\/[a-z0-9._-]+$`
- Conventional commits: `type(scope): description` with allowed types only
- Run shellcheck on modified scripts before pushing

### skill-creator
- Create skill only for reusable patterns, not one-off tasks or existing docs
- Structure: `skills/{name}/SKILL.md` (required), optional `assets/`, `references/`
- Frontmatter required: name, description (with trigger), license Apache-2.0, metadata.author, metadata.version
- references/ points to LOCAL files, never web URLs
- After creating, register in AGENTS.md

### go-testing
- Table-driven tests for pure functions; mock side effects
- Bubbletea TUI: test `Model.Update()` directly for state changes, `teatest.NewTestModel()` for full flows, golden files for visual output
- Use `t.TempDir()` for file operations in tests
- Commands: `go test ./...`, `go test -cover ./...`, `go test -update ./...` for golden files

### judgment-day
- Resolve skills first (read registry -> match by code/task context -> inject Project Standards block)
- Launch TWO judges in parallel via `delegate`; neither knows about the other
- Orchestrator synthesizes: Confirmed (both) = high confidence; Suspect (one) = triage; Contradiction = flag
- Classify every WARNING as real (normal usage triggers it) or theoretical (contrived scenario) — theoretical = INFO only
- After fixes, re-launch both judges in parallel; after 2 iterations ask user before continuing
- NEVER declare APPROVED until 0 confirmed CRITICALs + 0 confirmed real WARNINGs

### technical-documentation
- Audience-first: developers (depth), team (context+depth), end users (no jargon, step-by-step)
- Progressive disclosure: quick start -> common cases -> advanced -> edge cases
- Always verify code examples compile/run before publishing
- Use active voice and present tense
- Keep README under 500 lines; link to detailed docs
- Never publish with placeholder content or TODOs

### eval-frameworks
- Use Faithfulness metric to detect hallucinations in RAG outputs
- Use Retrieval Relevance to verify context usefulness
- Use Synthetic Data Generation to scale evaluation without manual labeling
- LLM-as-a-Judge: stronger model can grade smaller model with human-like accuracy
- Separate Response quality from Retrieval quality — fixing one does not fix the other

### evaluation
- Evaluate outcomes, not specific execution paths
- Use multi-dimensional rubrics (factual accuracy, completeness, citation accuracy, source quality, tool efficiency)
- Test across complexity levels: simple -> medium -> complex -> very complex
- Token usage explains ~80% of variance, tool calls ~10%, model choice ~5%
- Supplement automated evaluation with human review for edge cases
- Run evaluations continuously, not just before release

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| None found | — | No agents.md, AGENTS.md, CLAUDE.md, .cursorrules, GEMINI.md, or copilot-instructions.md detected |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
