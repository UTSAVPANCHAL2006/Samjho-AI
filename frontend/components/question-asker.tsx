"use client";

// Step 1: the QUESTION (not the working), from a photo of the book or worksheet.
// The backend refuses anything that is not Class 6–10 maths, and anything it cannot solve reliably.

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError, type Question, type Understood } from "@/lib/api";
import { ArrowRightIcon, RetakeIcon } from "@/components/icons";
import { MathText, MixedMath } from "@/components/math";
import { Notice, PhotoPicker, PhotoReading } from "@/components/ui";

type State =
  | { kind: "idle" }
  | { kind: "busy"; photo: File }
  | { kind: "confirmPhoto"; questionId: string; readText: string }
  | { kind: "message"; title: string; text: string; readText: string | null; understood: string[] }
  | { kind: "parts"; parts: Question[] };

// A specific title per outcome: "needs one detail" is very different from "not maths".
const TITLES: Partial<Record<Understood["status"], string>> = {
  needs_clarification: "One thing to check",
  unsupported: "Not something I can check yet",
  verification_failed: "I won't guess on this one",
  parse_failed: "I couldn't read that",
  not_maths: "Only maths, please",
  ai_unavailable: "Busy right now",
};

export function QuestionAsker() {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "idle" });

  async function understand(photo: File) {
    setState({ kind: "busy", photo });
    try {
      const result = await api.understandPhoto(photo);
      if (result.question && result.other_parts.length) {
        setState({ kind: "parts", parts: [result.question, ...result.other_parts] });
      } else if (result.question) {
        setState({
          kind: "confirmPhoto",
          questionId: result.question.id,
          readText: result.read_text ?? result.question.text,
        });
      } else {
        setState({
          kind: "message",
          title: TITLES[result.status] ?? "We can't check this one yet",
          text: result.message ?? "Please take the photo again, a little closer.",
          readText: result.read_text,
          understood: result.understood,
        });
      }
    } catch (error) {
      setState({
        kind: "message",
        title: "Something went wrong",
        text: error instanceof ApiError ? error.message : "Could not read your question.",
        readText: null,
        understood: [],
      });
    }
  }

  const retake = () => setState({ kind: "idle" });

  if (state.kind === "busy") {
    return (
      <PhotoReading
        photo={state.photo}
        title="Reading the question…"
        hint="The question is read, then solved and checked by maths before you start. Usually 5–15 seconds."
      />
    );
  }

  return (
    <section aria-label="Step 1: your question" className="surface space-y-5 p-4 sm:p-6">
      {state.kind === "confirmPhoto" ? (
        <div className="fade-up space-y-4">
          <p className="eyebrow text-green-tick">Is this your question?</p>
          <div className="rounded-2xl bg-paper px-5 py-4 text-lg leading-relaxed ring-1 ring-rule">
            <MixedMath text={state.readText} />
          </div>
          <div className="flex flex-wrap gap-2.5">
            <button onClick={() => router.push(`/solve/${state.questionId}`)} className="btn-primary">
              Yes, continue <ArrowRightIcon size={18} />
            </button>
            <button onClick={retake} className="btn-secondary">
              <RetakeIcon size={18} /> Retake photo
            </button>
          </div>
        </div>
      ) : state.kind === "parts" ? (
        <div className="fade-up space-y-3">
          <p className="font-display text-lg font-bold">
            This question has {state.parts.length} parts. Which one did you solve?
          </p>
          {state.parts.map((part) => (
            <button
              key={part.id}
              onClick={() => router.push(`/solve/${part.id}`)}
              className="block w-full rounded-2xl bg-paper px-4 py-3 text-left ring-1 ring-rule transition hover:ring-ink-soft"
            >
              <MixedMath text={part.text} />
            </button>
          ))}
        </div>
      ) : (
        <PhotoPicker
          title="Photo of the question"
          hint="Snap just the question from your book, worksheet or test paper. Your own working comes next."
          onPhoto={(photo) => void understand(photo)}
        />
      )}

      {state.kind === "message" ? (
        <Notice tone="warning" title={state.title}>
          {state.readText ? (
            <span className="mb-1 block">
              We read: <MixedMath text={state.readText} />
            </span>
          ) : null}
          {state.understood.length ? (
            <span className="mb-1 block">
              I understood:{" "}
              {state.understood.map((item) => (
                <span key={item} className="mr-3 inline-block">
                  <MathText latex={item} />
                </span>
              ))}
            </span>
          ) : null}
          <MixedMath text={state.text} />
        </Notice>
      ) : null}
      <p className="text-center text-xs text-muted">
        CBSE Class 6–10 maths with a single answer. Proofs and other subjects are politely refused.
      </p>
    </section>
  );
}
