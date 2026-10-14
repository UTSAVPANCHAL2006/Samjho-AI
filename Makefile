# Common commands. Run from the project root.

.PHONY: backend frontend test lint eval eval-live

backend:   ## API on http://localhost:8000/docs (creates tables + loads the question bank on start)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:  ## App on http://localhost:3000
	cd frontend && npm run dev

test:
	cd backend && uv run pytest
	cd frontend && npm test && npx tsc --noEmit

lint:
	cd backend && uv run ruff check app tests && uv run mypy app
	cd frontend && npm run lint

eval:      ## Grading accuracy on labelled attempts (no AI calls)
	cd backend && uv run python ../evals/run_eval.py

eval-live: ## Real models (slow on free tiers): curriculum, images + voice, tutor conversations
	cd backend && uv run python ../evals/run_curriculum_eval.py && uv run python ../evals/run_media_eval.py && uv run python ../evals/run_tutor_eval.py
