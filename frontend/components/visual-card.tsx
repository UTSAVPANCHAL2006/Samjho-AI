"use client";

// "See it visually": loads the concept visual for an attempt (or a question) on demand and plays it.

import { useEffect, useRef, useState } from "react";
import { api, ApiError, type ConceptVisualData } from "@/lib/api";
import { readLanguage } from "@/lib/student";
import { useVoice } from "@/lib/voice";
import { ConceptVisual } from "@/components/concept-visual";

type State =
  | { kind: "closed" }
  | { kind: "loading" }
  | { kind: "none"; message: string }
  | { kind: "ready"; visual: ConceptVisualData };

export function VisualCard({
  checkId = null,
  questionId = null,
  autoOpen = false,
}: {
  checkId?: string | null;
  questionId?: string | null;
  autoOpen?: boolean;
}) {
  const [state, setState] = useState<State>(autoOpen ? { kind: "loading" } : { kind: "closed" });
  const voice = useVoice();
  const language = readLanguage();
  const prefetchRef = useRef<Promise<{ visual: ConceptVisualData | null }> | null>(null);

  function fetchVisual() {
    return checkId ? api.getCheckVisual(checkId, language) : api.getQuestionVisual(questionId ?? "", language);
  }

  function toState(visual: ConceptVisualData | null): State {
    return visual
      ? { kind: "ready", visual }
      : { kind: "none", message: "We could not draw a checked visual for this one. The board lesson still works." };
  }

  function toError(error: unknown): State {
    return { kind: "none", message: error instanceof ApiError ? error.message : "Could not load the visual." };
  }

  function open() {
    setState({ kind: "loading" });
    (prefetchRef.current ?? fetchVisual())
      .then((result) => setState(toState(result.visual)))
      .catch((error: unknown) => setState(toError(error)));
  }

  // Start drawing in the background as soon as the result is shown, so "Show me" is usually instant.
  useEffect(() => {
    if (autoOpen) return;
    const request = fetchVisual();
    request.catch(() => undefined);
    prefetchRef.current = request;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per card
  }, []);

  useEffect(() => {
    if (!autoOpen) return;
    let isCurrent = true;
    fetchVisual()
      .then((result) => isCurrent && setState(toState(result.visual)))
      .catch((error: unknown) => isCurrent && setState(toError(error)));
    return () => {
      isCurrent = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when opened
  }, []);

  if (state.kind === "ready") return <ConceptVisual visual={state.visual} voice={voice} language={language} autoPlay />;
  if (state.kind === "none") return <p className="rounded-2xl bg-paper-deep p-4 text-sm text-muted">{state.message}</p>;
  return (
    <section className="flex flex-col justify-between gap-3 rounded-2xl border border-rule bg-gradient-to-br from-card to-amber-soft/40 p-4 sm:flex-row sm:items-center">
      <div>
        <p className="font-semibold">🎨 See it visually</p>
        <p className="mt-1 text-sm text-muted">A picture of the idea — drawn step by step while the tutor explains.</p>
      </div>
      <button
        onClick={open}
        disabled={state.kind === "loading"}
        className="shrink-0 rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 disabled:opacity-60"
      >
        {state.kind === "loading" ? "Drawing it…" : "▶ Show me"}
      </button>
    </section>
  );
}
