// The red-pen check, drawn like a teacher marking a notebook page: blue-ink lines, hand-drawn ✓ and ✗,
// a red circle round the first mistake with a remark in the margin, and the marks as a stamp.

import type { Check } from "@/lib/api";
import { mistakeRemark } from "@/lib/mistakes";
import { MathText, formatMarks, readableLatex } from "@/components/math";

type Verdict = Check["steps"][number]["verdict"];

/** "Adding the fractions on LHS:" is the student talking, not a maths step — no mark for it. */
export function isWordLine(latex: string): boolean {
  const words = latex.replace(/\\[a-zA-Z]+/g, " ").match(/[A-Za-z]{3,}/g) ?? [];
  const isLabelOnly = /^\s*(\\text\s*\{)?\s*[A-Za-z][A-Za-z .]*:\s*\}?\s*$/.test(latex); // 'Sol:', 'Given:'
  return !latex.includes("=") && (words.length >= 2 || isLabelOnly);
}

function Tick() {
  return (
    <svg viewBox="0 0 40 32" className="h-7 w-9 text-green-tick" aria-hidden>
      <path d="M4 17 C 9 21, 12 25, 15 28 C 21 17, 29 8, 37 3" className="pen-stroke" />
    </svg>
  );
}

function Cross() {
  return (
    <svg viewBox="0 0 36 36" className="h-8 w-8 text-red-pen" aria-hidden>
      <path d="M7 6 C 15 14, 22 22, 30 31" className="pen-stroke" />
      <path d="M30 5 C 22 13, 14 22, 6 30" className="pen-stroke pen-stroke-late" />
    </svg>
  );
}

/** After the first mistake: the line follows from it. Never a green tick (the student would trust it), never a cross. */
function Carried() {
  return (
    <span className="flex items-center gap-1 whitespace-nowrap font-hand text-lg leading-none text-muted">
      <span aria-hidden>→</span>
      <span className="hidden sm:inline">follows the mistake</span>
    </span>
  );
}

function Unsure() {
  return <span className="font-hand text-3xl leading-none text-amber">?</span>;
}

const LABELS: Record<Verdict, string> = {
  correct: "Correct step",
  incorrect: "Mistake here",
  carried: "Follows from your first mistake — this line earns no marks",
  unverifiable: "Could not check this step (never costs marks)",
  unreadable: "Could not read this line",
  note: "A given value — no mark needed",
};

function MarkFor({ verdict }: { verdict: Verdict }) {
  if (verdict === "correct") return <Tick />;
  if (verdict === "incorrect") return <Cross />;
  if (verdict === "carried") return <Carried />;
  return <Unsure />;
}

export function RedPen({
  check,
  focusLine,
  onEditLines,
}: {
  check: Check;
  focusLine: number | null;
  onEditLines: (() => void) | null;
}) {
  const isFullMarks = check.score >= check.max_score;
  const footnote =
    check.wrong_line !== null
      ? null
      : isFullMarks
        ? "Well done! Every step is correct."
        : "No step is wrong — just write the final answer in full, like x = 5.";

  return (
    <section aria-label="Red-pen check" className="fade-up">
      <div className="flex items-end justify-between gap-4 pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Your notebook</p>
          <h2 className="font-display text-[1.75rem] leading-tight text-ink">Red-pen check</h2>
          <p className="mt-0.5 text-sm text-muted">Every ✓ and ✗ is proven with maths, never guessed by AI.</p>
        </div>
        <div
          aria-label={`Score ${formatMarks(check.score)} out of ${check.max_score}`}
          className={`marks-stamp ${isFullMarks ? "text-green-tick" : "text-red-pen"}`}
        >
          <span className="font-hand text-[2.4rem] leading-none">
            {formatMarks(check.score)}
            <span className="text-2xl">/{check.max_score}</span>
          </span>
        </div>
      </div>

      <div className="notebook-page">
        <ol>
          {check.lines.map((line, index) => {
            const lineNo = index + 1;
            const step = check.steps.find((item) => item.line_no === lineNo);
            const verdict: Verdict = step?.verdict ?? "unverifiable";
            const isMistake = lineNo === check.wrong_line;
            const isNote = isWordLine(line.latex) || verdict === "note";
            return (
              <li
                key={lineNo}
                className={`relative flex min-h-[3.5rem] items-center gap-3 py-2 pl-16 pr-4 transition ${
                  lineNo === focusLine ? "bg-blue-soft/50" : ""
                }`}
              >
                <span className="absolute left-0 w-12 text-center font-hand text-lg text-muted/70">{lineNo}</span>
                <div className={`relative min-w-0 flex-1 ${isMistake ? "py-1" : ""}`}>
                  <span className="relative inline-block max-w-full align-middle">
                    {/* the circle sits outside the scroll box, so it is never cut off */}
                    {isMistake ? (
                      <svg className="red-circle" viewBox="0 0 200 60" preserveAspectRatio="none" aria-hidden>
                        <path d="M10 33 C 12 8, 186 4, 192 28 C 198 54, 18 60, 8 36 C 4 24, 40 10, 70 8" className="pen-stroke" />
                      </svg>
                    ) : null}
                    <span
                      className={`block max-w-full overflow-x-auto overflow-y-hidden px-1 text-[1.2rem] ${
                        isNote ? "italic text-ink-soft" : "text-blue-ink"
                      }`}
                    >
                      {isNote ? readableLatex(line.latex) : <MathText latex={line.latex} />}
                    </span>
                  </span>
                  {isMistake ? (
                    <span className="mt-1 block font-hand text-xl leading-none text-red-pen sm:absolute sm:-bottom-1 sm:right-0 sm:mt-0">
                      {mistakeRemark(check.mistake)}
                    </span>
                  ) : null}
                </div>
                {step?.is_question_copy ? (
                  <span className="rounded-full bg-paper-deep px-2 py-0.5 text-xs text-muted" title="Copying the question earns no marks">
                    question
                  </span>
                ) : null}
                <span className={`grid shrink-0 place-items-center ${verdict === "carried" ? "min-w-9" : "w-9"}`} title={LABELS[verdict]} aria-label={isNote ? "Note" : LABELS[verdict]}>
                  {isNote ? null : <MarkFor verdict={verdict} />}
                </span>
              </li>
            );
          })}
        </ol>
        {footnote ? (
          <p className={`py-3 pl-16 pr-4 font-hand text-2xl ${isFullMarks ? "text-green-tick" : "text-red-pen"}`}>{footnote}</p>
        ) : null}
      </div>

      {onEditLines ? (
        <button onClick={onEditLines} className="mt-3 text-sm font-semibold text-blue-ink underline-offset-4 hover:underline">
          Did we misread a line? Fix it →
        </button>
      ) : null}
    </section>
  );
}
