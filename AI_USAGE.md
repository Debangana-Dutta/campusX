# AI usage declaration

## AI tools used to BUILD this project
- **Claude (Anthropic), via the claude.ai chat interface with a code-execution sandbox** wrote and tested the backend:
  dataset loader, CP-SAT scheduler, exam scheduler, booking engine, disruption repair, API, and tests. (The master
  prompt called for Claude Code; this part was actually produced in the claude.ai sandbox.) A human reviews the output.
- No other AI development tools have been used so far.

## AI models called BY THE PRODUCT (runtime)
- **None in the current build.** Part 2 plans Gemini (via the backend only) for: reading plain-English/Hinglish
  booking requests into the structured booking form, asking follow-up questions, and explaining decisions.
  This file must be updated when that ships.

## Prompts
- No runtime prompts exist yet. Part 2 prompts will live in `backend/app/prompts/`.

## What AI is NOT allowed to decide
Whether a schedule, booking, exam allocation or disruption repair is valid or approved. Those decisions are made by
deterministic code (`services/scheduling`, `services/bookings`, `services/exams`, `services/disruptions`) and are
re-checked by the official `validator.py` before anything is exported or applied. Every AI-produced structure will pass
the same Pydantic schemas and hard-constraint checks as a manual form. If the AI API fails, the manual booking form works.
