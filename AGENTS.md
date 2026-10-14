# Rules for anyone (human or AI) changing this code

1. **Maths decides, AI talks.** Marks, ✓/✗ and "is this fix right" come only from `backend/app/maths/checker.py`. Never let an AI give or change marks.
2. **Never accuse without proof.** A line is wrong only if SymPy proves it. Unclear = "?" and costs nothing.
3. **Zero means zero.** Blank, skipped, copied or off-question work scores 0 before any checking.
4. **Every AI call can fail.** `AiModels` returns `None`; always have a safe fallback (typing, a template, or an honest "we can't check this").
5. **Names:** functions and variables in camelCase, no underscores (`checkSteps`, `isFullMarks`). Files start with a 1–3 line comment saying what they are for. Plain loops over clever one-liners.
6. **Tests:** `make test` and `make eval` must pass. Never skip or loosen a test to make it pass. Tests never call a real AI or Sarvam.
7. **Secrets** live only in `backend/.env` (git-ignored). Never log or print them.
8. **New maths capability = a solver family** in `maths/solvers.py` (answer + steps + checks + traps) with tests, never a special case for one question. Add eval cases to `evals/data/curriculum_v1.json` (hand-written expected answers) and re-run the evals; report what failed.
9. **Never return a guessed answer.** Readings must be confirmed (numbers from the question, or a second model agrees); otherwise return a specific status.
10. **Keep it small.** Extend an existing file before adding a new one. No new dependency without a reason.
