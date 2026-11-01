# AI usage declaration

## AI tools used to BUILD this project
> Team to confirm before submission: the sections below record what the assistant that wrote this code can know. If anyone on the team also used ChatGPT or any other AI tool (for code, copy, design or prompts), add it here with the areas it helped; undeclared AI use costs marks.
- **Claude (Anthropic) in the claude.ai chat interface with a code-execution sandbox** wrote and tested essentially all code
  (backend, scheduler, engines, API, authentication, database migrations, React frontend, tests, documentation). The master prompt named Claude Code; the work was
  actually done in this sandbox. A human directs the work and reviews the output.
- No other AI development tools were used.

## AI APIs called BY THE PRODUCT at runtime
| API | Used for | Where |
|---|---|---|
| **Google Gemini** (`generativelanguage.googleapis.com`, model from `GEMINI_MODEL`, default `gemini-2.0-flash`), called from the FastAPI backend only | (1) Extracting structured booking fields from English/Hinglish requests and suggesting follow-up questions; (2) rephrasing Campus Buddy answers in the user's language | `backend/app/services/ai/` |
Gemini is **optional**: with no key, or on any failure/quota exhaustion, the built-in rule-based parser and deterministic Campus Buddy lookup are used and the UI says so ("Answered by rules"). The Gemini path has only been exercised with mocked responses (no key or outbound access was available while building); it has not been run against the live API.

## Prompts
System prompts live in code (no separate prompt files): `backend/app/services/ai/booking_parser.py` (`SYSTEM`) and `backend/app/services/ai/buddy.py` (inline rewrite instruction).

## What AI is NOT allowed to decide
Whether any schedule, booking, exam allocation, disruption repair or permission is valid or approved. Those are decided by deterministic code
(`services/scheduling|bookings|exams|disruptions`) and re-checked by the official `validator.py`. Specifically, AI cannot approve/reject bookings, override category caps
or priorities, bypass conflicts, change hard constraints or apply schedule changes. Parsed output is validated field by field (invalid days/periods/room types/needs are
discarded; invalid structures are rejected and the rule-based parser is used), shown to the user for editing, and then passes through the same schema and engine as the manual form.
Campus Buddy sends Gemini only the facts the backend already scoped to the signed-in user (student -> own group; faculty -> own classes).

## Notes
- The faculty schedule assistant and decision explanations are **rule-based/deterministic**; they do not call a model. Only the booking parser and Campus Buddy's phrasing can use Gemini.
- The Gemini path was exercised only with mocked responses; it was not run against the live API.
- Parsing the briefs' English and Hinglish examples ("2 baje se 4 baje tak", "computer lab 2") is done by the rule-based parser and is covered by tests.

- **Logo**: supplied by the team. If it was created with an AI image tool, declare that tool here (the assistant that built the code does not know how it was made).
