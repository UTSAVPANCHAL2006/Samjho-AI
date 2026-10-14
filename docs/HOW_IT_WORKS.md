# How Samjho works

## The problem

Answer apps show a perfect solution, but students learn from their own mistakes, not from reading someone else's working. A teacher's red pen shows *where* the working broke but rarely *why*, and there is no time to talk it through. My earlier project gave 4/6 marks to a skipped answer and gave no feedback a student could act on. Samjho is built so that cannot happen.

**One sentence:** check the student's own working line by line with maths, then talk them through the first mistake like a teacher would.

## The design rule

> AI reads and talks. Maths decides.

| Job | Who does it | Why |
|---|---|---|
| Read a handwritten photo | Vision model (Gemini → OpenRouter) | Only AI can read handwriting |
| Is this line right? How many marks? | **SymPy** | Must be exact and repeatable — same work, same marks, every time |
| What exactly is wrong in the line | **SymPy** ("line before gives 3x = 15, this line gives 3x = 29") | An AI rewording once invented a wrong reason, so the red-pen explanation is the fact itself |
| Is the student's fix right? | **SymPy** | The tutor must never praise a wrong answer |
| Talk like a teacher, ask a guiding question | LLM (Groq → Gemini) | Natural language, Hinglish |
| Speech in / out | Sarvam (Indian accent) | Hinglish STT and TTS |

## Understanding any question (`backend/app/agents/understand.py`)

```
normalize ──> fast path: only "solve these equations"? ──yes──> equation solver (no AI)
                 │ no
                 ▼
            AI plans: family + numbers (never calculates)
                 ▼
            solver computes + verifies (maths/solvers.py)  ── solver says "doesn't fit" ──> re-plan once with the reason
                 ▼
            trust check: numbers all from the question?  AI turned words into maths?
                 └── then a 2nd reading by a DIFFERENT model must agree; if not, a 3rd decides (2 of 3), else refuse
```

**Problem families** (each a small, tested solver that returns answer + school-level steps + the checks it passed):
equations (one equation, pairs by elimination incl. no/infinite solutions, quadratics by splitting the middle term or the formula, extraneous roots, positive-only unknowns, "what the question asks for"),
progressions (both sum formulas), statistics (raw and grouped mean/median/mode), HCF/LCM, mensuration (NCERT formulas incl. Heron, sectors, solids),
interest (simple/compound), coordinates (distance, section, area), identities (algebraic/trig, proved symbolically), properties (prime, divisible,
perfect square/cube, rational, terminating decimal, compare, quadrant), and expressions (calculate / simplify / factorise / expand, surds in school form).

**Outcomes** — never a generic failure: `solved` · `needs_clarification` (says exactly what is missing or ambiguous, and shows the maths it understood) ·
`unsupported` (understood, but e.g. a geometric proof) · `parse_failed` · `verification_failed` (readings disagree — no guess) · `not_maths` ·
`ai_unavailable` (the free-tier models are rate-limited — nothing wrong with the question).

**Trust label** on every answer key: `verified` (computed by code; any AI reading confirmed by a second model) ·
`ai_agreement` (the AI stated the answer, e.g. "a hexagon has 6 lines of symmetry"; two models agreed but nothing was computed — shown to the student) ·
`single_reading` (backup model unavailable — shown to the student).

**Misconceptions** — solvers record common wrong answers for the question's own numbers (AP sum with *a* instead of *2a*, nth term with *n·d*,
πr² vs 2πr, forgetting /100 in interest...). A matching wrong answer is explained precisely; a wrong value in an equation is explained by substituting it.

## The two agents (LangGraph)

Both are fixed workflows, not free agents: the order of steps is decided by code, so the behaviour is predictable and testable.

**GradingGraph** (`backend/app/agents/grading.py`), one attempt → red pen:

```
readPhoto ──> guardZero ──> checkSteps ──> explainMistake
   │              │             │
   ├ bad photo / not maths → stop (retake)          typed work starts at guardZero
   ├ unsure reading → stop, student confirms lines
   │              ├ blank / skipped / copied / off-question → 0 marks, stop
   │                            └ no mistake → stop
```

**TutorGraph** (`backend/app/agents/tutor.py`), one student message → one reply:

```
understandMessage ──> decideNext ──> makeQuickCheck ──> writeReply
 (SymPy checks what     (teaching      (new numbers,        (LLM words it;
  the student said)      rules, code)   same rule)           templates if AI is down)
```

Teaching rules (`decideTurn`, a pure function):
probe the wrong line → hint → stronger hint → **walk through the verified steps together**
(explain one step, the student works out the next, SymPy checks it; confused twice on a step → show it and move on, never loop).
"Samjhao / I don't understand" starts the walkthrough at once; "full solution" shows all verified steps; a correct fix → praise → quick check → practice.
The tutor sees the student's actual words, the maths found in them ("Maine x = 8 likha" → `x = 8`), what SymPy said about it
(e.g. "with x = 8, equation (1) gives y = −5/3, which breaks equation (2)") and the verified steps — and may only use those numbers.

## Data (4 tables)

`students` (name, class) · `questions` (bank + typed ones; the answer is computed by SymPy) · `checks` (lines, a verdict per line, marks, the first mistake) · `tutor_chats` (stage, hints, messages). Small lists are stored as JSON columns, so there are no join tables.

## API

| Endpoint | Does |
|---|---|
| `GET /api/questions?class_level=` · `GET /api/questions/{id}` | Practice bank |
| `POST /api/questions` · `POST /api/questions/photo` | Understand any typed / photographed question |
| `POST /api/checks` (photo) · `POST /api/checks/typed` · `POST /api/checks/{id}/confirm` | Check an attempt → red pen |
| `GET /api/checks/{id}/solution` | Full solution, only after a graded attempt, only if SymPy-verified |
| `POST /api/tutor` · `POST /api/tutor/{chat_id}` | Start the tutor / one message |
| `POST /api/students` · `GET /api/students/{id}/progress` · `GET /api/practice` | Profile, streak, chapters, next question |
| `GET /api/voice` · `POST /api/voice/listen` · `POST /api/voice/speak` | Sarvam STT / TTS |

## Reliability details

- **Model fallback.** `ai/models.py` is one small client. OpenAI (optional), Groq, Gemini and OpenRouter all speak the OpenAI chat API, so a call is: try model 1 → wait and retry once if rate-limited → model 2 → `None`. A provider without a key is skipped. Every caller has a safe fallback for `None`: the student is asked to retake or fix the reading, a template reply is used, or the question is refused.
- **Cache.** Identical deterministic AI calls and every spoken sentence are cached on disk, so the free tiers and Sarvam credits last.
- **Voice.** The browser records one answer, stops on silence, and converts it to 16 kHz WAV, so speech-to-text never depends on the browser's audio codec. For the tutor's voice, code turns maths into words and Sarvam only transliterates Hinglish to Devanagari: no language model reads maths aloud (one once said "three sexy" for 360), and it takes ~2 s instead of ~12 s. Every voice failure is shown to the student, and typing to the tutor always works.
- **Fixing a misread line.** The app is photo-first; when a line was read wrong, the student retypes just that line as `x square`, `sqrt(49)`, `pi r^2`, `12 x 8` or `5% of 200`. The parser and the live preview use the same rules, so what they see is what gets checked.
- **Safety limits.** A line too heavy to compute (`2^{2^{2^{100}}}`, `(x+1)^{500}`) is not checked rather than freezing the server; paid requests (photos, tutor, voice) are rate-limited per person.

## Decisions and trade-offs

| Decision | Trade-off |
|---|---|
| Geometric proofs and constructions are refused honestly (identity proofs are supported) | We grade only what maths can verify; AI judges can falsely accuse. |
| Mistake explanation = SymPy fact, not AI wording | Less "natural", never wrong. The tutor adds the natural explanation in conversation. |
| Intent detection by code (maths? asks for the answer?), not an LLM | One AI call per turn instead of two, so voice replies are faster. |
| Streak, not points or leaderboards | Rewards the habit (one sum a day), not volume or copying. |
| No login (a profile per device, "Switch" for siblings) | Zero-friction first use. A real account system comes later. |
| Tables created on start (no migration tool yet) | Simpler while the schema is young. Add Alembic once it stabilises. |

## Evals and tests (all reproducible; reports are written next to the runners in `evals/`)

| Eval | What it measures | Report |
|---|---|---|
| `make eval` | Grading (no AI): false accusations, zero-mark leaks, verdicts, marks — 46 labelled attempts | `evals/report.md` |
| `run_curriculum_eval.py` | 121 hand-written Class 6–10 questions through the real pipeline and models; pass / false success / unnecessary refusal by class, chapter, family | `evals/curriculum_report.md`, `evals/coverage.md` |
| `run_media_eval.py` | Question photos and a working photo through real vision; spoken answers through real Sarvam STT | `evals/media_report.md` |
| `run_tutor_eval.py` | Multi-turn conversations with real models: no answer leak, uses the student's value, language, one question, no repeats, context kept | `evals/tutor_report.md` |

`make test`: backend unit/integration tests with a fake AI (tests never call a real AI or Sarvam), plus frontend tests.

## What's next

1. A real handwriting eval: 50+ student photos with labels.
2. Measure the funnel: check → tutor started → fix → practice solved, and day-2 / day-7 return rate.
3. Proofs with a verified reference, and more practice questions per chapter.
4. Streaming voice (lower latency) and WhatsApp reminders for the streak.
