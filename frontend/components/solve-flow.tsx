"use client";

// Solving one question, steps 2 and 3:
//   photo of your working -> [fix a line we misread] -> red pen -> tutor -> practice / solution
// One small state machine keeps every screen predictable.

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import { api, ApiError, type Check, type Question } from "@/lib/api";
import { ensureStudentId } from "@/lib/student";
import { LinesEditor } from "@/components/lines-editor";
import { MixedMath, QuestionText, formatDifficulty } from "@/components/math";
import { RedPen } from "@/components/red-pen";
import { Lesson } from "@/components/lesson";
import { JourneySteps, Notice, PhotoPicker, PhotoReading } from "@/components/ui";

type Stage =
  | { kind: "working"; error: string | null }
  | { kind: "reading"; photo: File }
  | { kind: "confirm"; check: Check; error: string | null; isBusy: boolean }
  | { kind: "result"; check: Check };

const errorText = (error: unknown) =>
  error instanceof ApiError ? error.message : "Something went wrong. Please try again.";

/** The question id is read from the address bar in the browser, so the page is one plain static page. A page that
 * waited for the id on the server (a streamed part) stayed blank on Vercel when opened directly: a refresh, a shared link. */
export function SolveFromUrl() {
  const questionId = useSyncExternalStore(neverChanges, readQuestionIdFromUrl, () => null);
  if (questionId === null) return <div className="surface h-40 animate-pulse bg-paper-deep" aria-label="Loading question" />;
  return <SolveFlow key={questionId} questionId={questionId} />;
}

const neverChanges = () => () => {}; // the id only changes with a new page, which mounts this again
const readQuestionIdFromUrl = () => decodeURIComponent(window.location.pathname.split("/").filter(Boolean)[1] ?? "");

export function SolveFlow({ questionId }: { questionId: string }) {
  const [question, setQuestion] = useState<Question | "loading" | "missing" | "unreachable">("loading");
  const [attempt, setAttempt] = useState(0);
  const [stage, setStage] = useState<Stage>({ kind: "working", error: null });
  const [focusLine, setFocusLine] = useState<number | null>(null);

  useEffect(() => {
    api
      .getQuestion(questionId)
      .then(setQuestion)
      // 404: the question is gone. No status: the server could not be reached, which is not the same thing.
      .catch((error: unknown) => setQuestion(error instanceof ApiError && error.status === null ? "unreachable" : "missing"));
  }, [questionId, attempt]);

  if (question === "loading")
    return <div className="surface h-40 animate-pulse bg-paper-deep" aria-label="Loading question" />;
  if (question === "unreachable") {
    return (
      <Notice
        tone="error"
        title="We can't reach Samjho right now"
        action={
          <button
            onClick={() => {
              setQuestion("loading");
              setAttempt(attempt + 1);
            }}
            className="rounded-full bg-ink px-4 py-1.5 text-sm font-semibold text-white"
          >
            Try again
          </button>
        }
      >
        Check your internet connection. Your question is saved.
      </Notice>
    );
  }
  if (question === "missing") {
    return (
      <Notice
        tone="error"
        title="Question not found"
        action={
          <Link href="/check" className="rounded-full bg-ink px-4 py-1.5 text-sm font-semibold text-white">
            Check another sum
          </Link>
        }
      >
        It may have been removed. Take a photo of the question again.
      </Notice>
    );
  }

  function showResult(check: Check) {
    setFocusLine(null);
    if (check.status === "needs_confirmation" || check.status === "ai_unavailable")
      setStage({ kind: "confirm", check, error: null, isBusy: false });
    else setStage({ kind: "result", check });
  }

  async function checkPhoto(photo: File) {
    setStage({ kind: "reading", photo });
    try {
      const studentId = await ensureStudentId((question as Question).class_level);
      showResult(await api.checkPhoto(questionId, photo, studentId));
    } catch (error) {
      setStage({ kind: "working", error: errorText(error) });
    }
  }

  async function confirm(check: Check, lines: string[]) {
    setStage({ kind: "confirm", check, error: null, isBusy: true });
    try {
      showResult(await api.confirmLines(check.id, lines));
    } catch (error) {
      setStage({ kind: "confirm", check, error: errorText(error), isBusy: false });
    }
  }

  const startAgain = () => setStage({ kind: "working", error: null });

  return (
    <div className="space-y-6">
      <JourneySteps activeStep={stage.kind === "result" ? 3 : 2} />

      <section aria-label="Your question" className="surface p-5 sm:p-7">
        <div className="mb-4 flex items-center justify-between gap-3">
          <span className="eyebrow text-green-tick">✓ Your question</span>
          <Link href="/check" className="text-sm font-semibold text-muted hover:text-ink">
            Change question
          </Link>
        </div>
        <div className="text-lg leading-relaxed sm:text-xl">
          <QuestionText text={question.text} expressions={question.expressions} />
        </div>
        <ul className="mt-5 flex flex-wrap gap-2 text-xs font-medium text-ink-soft">
          {[`Class ${question.class_level}`, question.chapter, formatDifficulty(question.difficulty), `${question.marks} marks`].map(
            (item) => (
              <li key={item} className="rounded-full bg-paper px-3 py-1 ring-1 ring-rule">
                {item}
              </li>
            ),
          )}
        </ul>
        {question.trust !== "verified" ? (
          <p className="mt-2 text-xs text-amber">
            {question.trust === "ai_agreement"
              ? "Answer key: two AI models agreed — it was not computed. Check with your teacher if unsure."
              : "Answer key: read once (backup AI unavailable). Check with your teacher if unsure."}
          </p>
        ) : null}
      </section>

      {stage.kind === "working" ? (
        <section aria-label="Step 2: your working" className="surface space-y-5 p-4 sm:p-7">
          <div className="space-y-1.5 px-1">
            <p className="eyebrow">Step 2 of 3</p>
            <h2 className="text-2xl font-extrabold sm:text-3xl">Now show your working</h2>
            <p className="text-sm leading-relaxed text-muted">
              Solve it in your notebook the way you always do, then take one photo of the page.
            </p>
          </div>
          {stage.error ? (
            <Notice tone="error" title="Could not check">
              {stage.error}
            </Notice>
          ) : null}
          <PhotoPicker
            title="Photo of your notebook"
            hint="The page where you solved it — every line of your working in the photo."
            onPhoto={(photo) => void checkPhoto(photo)}
          />
        </section>
      ) : null}

      {stage.kind === "reading" ? (
        <PhotoReading
          photo={stage.photo}
          title="Checking every line…"
          hint="Your handwriting is read, then every step is checked by maths against the answer key. Usually 10–20 seconds."
        />
      ) : null}

      {stage.kind === "confirm" ? (
        <div className="space-y-3">
          {stage.check.status === "ai_unavailable" ? (
            <Notice
              tone="warning"
              title="We could not read your photo right now"
              action={
                <button onClick={startAgain} className="btn-secondary">
                  Try the photo again
                </button>
              }
            >
              The reader is busy for a moment. Try again in a few seconds, or fix the lines below yourself.
            </Notice>
          ) : null}
          {stage.error ? (
            <Notice tone="error" title="Could not check">
              {stage.error}
            </Notice>
          ) : null}
          <LinesEditor
            key={stage.check.id}
            lines={stage.check.lines}
            photoUrl={stage.check.has_photo ? api.photoUrl(stage.check.id) : null}
            isBusy={stage.isBusy}
            title="Did we read it right?"
            intro="Fix any line we misread before we check it. You never lose marks for OUR reading mistake."
            onSubmit={(lines) => void confirm(stage.check, lines)}
          />
        </div>
      ) : null}

      {stage.kind === "result" && stage.check.status === "graded" ? (
        <div className="space-y-6">
          <RedPen
            check={stage.check}
            focusLine={focusLine}
            onEditLines={
              stage.check.has_photo
                ? () => setStage({ kind: "confirm", check: stage.check, error: null, isBusy: false })
                : null
            }
          />
          <Lesson key={stage.check.id} check={stage.check} onFocusLine={setFocusLine} />
          <div className="flex flex-wrap gap-2">
            <button onClick={startAgain} className="btn-primary">
              Check again
            </button>
            <Link href="/check" className="btn-secondary">
              Check another sum
            </Link>
          </div>
        </div>
      ) : null}

      {stage.kind === "result" && stage.check.status !== "graded" ? (
        <Notice
          tone={stage.check.status === "needs_retake" ? "warning" : "error"}
          title={
            stage.check.status === "needs_retake" ? "Please retake the photo" : `Score: 0/${stage.check.max_score}`
          }
          action={
            <button onClick={startAgain} className="btn-primary">
              Try again
            </button>
          }
        >
          <MixedMath text={stage.check.explanation ?? stage.check.message ?? "We could not check this answer."} />
        </Notice>
      ) : null}
    </div>
  );
}
