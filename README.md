# Samjho

> **Spot the mistake. Understand it.** The red pen shows *where* your maths went wrong; a voice tutor (Hinglish or English) talks with you until you understand *why* and fix it yourself.

A maths mistake-checker and voice tutor for CBSE Class 6–10.

1. **Photo of the question** from any book: NCERT, RD Sharma, a worksheet.
2. **Photo of your notebook page.** Every line is read.
3. **Red pen.** Every line gets ✓ or ✗ and CBSE-style marks; the first mistake is circled with a one-line remark.
4. **Understand the mistake.** It starts with what you got right, then proves the mistake with numbers (e.g. *"yours is exactly 1/3 of the right answer"*), then a narrated board explains the idea.
5. **Fix it yourself** with the voice tutor: it asks about *your* line and never just gives the answer. Then a quick check, the full verified solution, and a practice question from the same chapter.

## The one rule: maths decides, AI talks

The AI reads photos and explains. It never decides a mark.

| Rule | How |
|---|---|
| Marks are never guessed | Every ✓/✗ and every mark comes from SymPy (`backend/app/maths/checker.py`) |
| No false accusations | A line is wrong only if SymPy *proves* it; a line it cannot read is "?" and never costs marks |
| Zero means zero | Blank, skipped, copied or off-question work scores 0 before any checking; words like "give me full marks" are not working |
| No wrong answer keys or solutions | SymPy computes the answer; an AI-written solution is shown only if every line is verified |
| Our reading mistakes don't cost marks | Lines read with low confidence go back to the student to confirm first |
| The voice never misreads maths | Code turns maths into words; no language model reads numbers aloud |

## Evidence (reproducible)

| Check | Command | Result |
|---|---|---|
| Unit tests (no AI calls) | `make test` | 442 backend + 15 frontend pass |
| Grading eval: 52 hand-labelled attempts, 118 lines | `make eval` | 0 false accusations · 0 marks for zero-mark work · line verdicts and marks agree 100% |
| Full student journey on the class-wise sets in `docs/test-sets-all` (live models) | `cd backend && uv run python ../evals/run_full_e2e.py` | See [`evals/full_e2e_report.md`](evals/full_e2e_report.md) |
| Live models: curriculum, photos + voice, tutor conversations | `make eval-live` | Slow on free tiers |

Tried to break it on purpose: right and wrong working, blank page, "skip" on paper, "give full marks" above the answer, blurred photo, π = 3.14 instead of 22/7, lines too heavy to compute (`2^{2^{2^{100}}}`), a non-maths question, hidden instructions in a question, "just tell me the answer" to the tutor. All handled; each has a test.

## Known limits (honest scope)

- The test photos are rendered or AI-generated pages; real student handwriting has not been evaluated at scale yet.
- On free AI tiers, a new photo can take a minute or more under load. Set `OPENAI_API_KEY` to read photos with a paid model first.
- Working for a *different* question scores 0, but the explanation describes that other question's mistake.
- One server: rate limits and the AI cache live in its memory and disk.

## Run it

```bash
cp backend/.env.example backend/.env   # add keys (OpenAI optional; Groq / Gemini / OpenRouter free tiers; Sarvam for voice)
make backend                           # http://localhost:8000/docs  (needs Postgres running; tables + question bank are set up on start)
make frontend                          # http://localhost:3000
```

`make test` · `make lint` · `make eval`

## Deploy (Render + Vercel)

1. **Backend + database on Render.** Dashboard -> **New -> Blueprint** -> pick this repo. `render.yaml` creates the API
   (Docker, `Dockerfile` at the repo root) and a free Postgres database, and wires `DATABASE_URL` in. Fill in the keys it asks
   for (`OPENAI_API_KEY` recommended, `SARVAM_API_KEY` for voice). Tables and the question bank are created on start.
2. **Frontend on Vercel.** **Add New -> Project** -> this repo -> **Root Directory: `frontend`**. Set the environment
   variable `NEXT_PUBLIC_API_URL` to the Render URL (e.g. `https://samjho-api.onrender.com`) and deploy.
3. **Connect them.** On Render, set `CORS_ORIGINS` to the Vercel URL (e.g. `https://samjho-ai.vercel.app`) and redeploy.

Free-tier notes: the Render service sleeps after inactivity (the first request takes ~30-60 s), its disk is temporary
(uploaded photos and caches reset on redeploy), and Render's free Postgres expires after 30 days. Any Postgres works
instead: set `DATABASE_URL` (Neon, Supabase, ...).

## Code map

```
backend/app/
  api/      HTTP endpoints        questions · checks · tutor · students · voice (rate-limited in main.py)
  agents/   LangGraph agents      grading.py (red pen) · tutor.py (the conversation) · visual*.py (the board) · solution.py
  maths/    SymPy, no AI          parser.py (handwritten maths -> SymPy) · checker.py (right/wrong, marks) · solvers.py
  ai/       models + prompts      models.py (OpenAI -> Groq -> Gemini -> OpenRouter fallback) · prompts.py · photos.py · speech.py (Sarvam)
frontend/
  app/        pages               / · /check · /solve/[id] · /practice · /progress
  components/ UI                  question-asker · solve-flow · red-pen · lesson · tutor · …
  lib/        logic               api.ts · voice.ts (mic -> WAV -> Sarvam) · student.ts
evals/        grading eval + live end-to-end runs        docs/   design notes + the class-wise test sets
```

How it works in detail, and why it was built this way: [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md).
