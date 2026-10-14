"use client";

// The voice tutor for the first mistake. Tap the mic once and talk (it stops when you pause), or type.
// It never hands over the answer: it asks about YOUR line, gives hints, then a quick check, then practice.

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type BoardScene, type Language, type TutorReply } from "@/lib/api";
import { useVoice, type VoiceStatus } from "@/lib/voice";
import { PracticeCard } from "@/components/after-check";
import { MixedMath } from "@/components/math";
import { SmartBoard } from "@/components/smart-board";
import { Notice } from "@/components/ui";

interface Message {
  role: "tutor" | "student";
  text: string;
  speech: string;
  badge: { good: boolean; text: string } | null;
  scenes: BoardScene[];
  boardLine: TutorReply["board_line"];
}

/** The reply as board scenes. Replies without scenes become one caption-only scene. */
function scenesOf(reply: TutorReply): BoardScene[] {
  return reply.scenes?.length ? reply.scenes : [{ text: reply.reply, speech: reply.speech, maths: [] }];
}

const STAGES: Record<TutorReply["stage"], string> = {
  hints: "Finding the mistake",
  walkthrough: "Step by step together",
  quick_check: "Quick check",
  practice: "Practice time",
};
const VOICE_STATUS: Record<VoiceStatus, string> = {
  idle: "Tap the mic and say your answer",
  listening: "Listening… I'll stop when you pause",
  transcribing: "Got it, writing it down…",
  speaking: "Tutor is speaking — tap the mic to interrupt",
};

function badgeFor(reply: TutorReply): Message["badge"] {
  if (reply.quick_check_correct !== null)
    return {
      good: reply.quick_check_correct,
      text: reply.quick_check_correct ? "✓ Quick check correct" : "✗ Quick check — see why",
    };
  if (reply.step_correct !== null)
    return { good: reply.step_correct, text: reply.step_correct ? "✓ That step is right" : "✗ Let's see this step" };
  if (reply.fix_correct !== null)
    return { good: reply.fix_correct, text: reply.fix_correct ? "✓ Your fix is correct" : "✗ Not quite yet" };
  return null;
}

export function Tutor({
  checkId,
  language,
  onFocusLine,
}: {
  checkId: string;
  language: Language;
  onFocusLine: (line: number) => void;
}) {
  const voice = useVoice();
  const [isVoiceOn, setIsVoiceOn] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [latest, setLatest] = useState<TutorReply | null>(null);
  const [draft, setDraft] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [board, setBoard] = useState<{ index: number; run: number } | null>(null); // which reply is on the board
  const messageCountRef = useRef(0); // how many messages exist, readable inside async code
  const chatIdRef = useRef<string | null>(null); // a spoken answer arrives seconds later; the ref is always current
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isWaiting]);

  async function talk(studentText: string | null) {
    setIsWaiting(true);
    setError(null);
    if (studentText) {
      messageCountRef.current += 1;
      setMessages((current) => [
        ...current,
        { role: "student", text: studentText, speech: studentText, badge: null, scenes: [], boardLine: null },
      ]);
    }
    try {
      const reply =
        chatIdRef.current && studentText
          ? await api.sendToTutor(chatIdRef.current, studentText)
          : await api.startTutor(checkId, language);
      chatIdRef.current = reply.chat_id;
      setLatest(reply);
      const tutorMessage: Message = {
        role: "tutor",
        text: reply.reply,
        speech: reply.speech,
        badge: badgeFor(reply),
        scenes: scenesOf(reply),
        boardLine: reply.board_line,
      };
      const index = messageCountRef.current;
      messageCountRef.current += 1;
      setMessages((current) => [...current, tutorMessage]);
      setBoard((previous) => ({ index, run: (previous?.run ?? 0) + 1 })); // the board plays the new reply
      onFocusLine(reply.focus_line);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The tutor could not answer. Please try again.");
    } finally {
      setIsWaiting(false);
    }
  }

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.trim() && !isWaiting) {
      void talk(draft.trim());
      setDraft("");
    }
  }

  function toggleVoice() {
    if (isVoiceOn) voice.stopSpeaking();
    setIsVoiceOn(!isVoiceOn);
  }

  function toggleMic() {
    if (voice.status === "listening") voice.stopListening();
    else void voice.listen(language, (spoken) => void talk(spoken));
  }

  if (!latest) {
    return (
      <section aria-label="Tutor" className="space-y-5">
        <div className="max-w-xl space-y-2">
          <h3 className="font-display text-2xl text-ink">Now fix it yourself</h3>
          <p className="leading-relaxed text-ink-soft">
            The tutor will not just give you the answer. They will ask short questions about your line — speak or
            type — until you find and fix the mistake yourself.
          </p>
        </div>
        <button
          onClick={() => void talk(null)}
          disabled={isWaiting}
          className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white shadow-[0_10px_24px_-12px_rgba(30,34,48,0.8)] transition hover:-translate-y-0.5 disabled:opacity-60"
        >
          {isWaiting ? "Starting…" : "Start talking with the tutor"}
          <span aria-hidden>→</span>
        </button>
        {error ? (
          <Notice tone="error" title="Tutor unavailable">
            {error}
          </Notice>
        ) : null}
      </section>
    );
  }

  return (
    <section aria-label="Voice tutor" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-xl text-ink">With the tutor</h3>
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded-full bg-blue-soft px-3 py-1 font-semibold text-blue-ink">
            {STAGES[latest.stage]}
          </span>
          {voice.canTalk ? (
            <button
              onClick={toggleVoice}
              aria-pressed={isVoiceOn}
              className="rounded-full px-2.5 py-1 ring-1 ring-rule"
            >
              {isVoiceOn ? "🔊 Voice on" : "🔇 Voice off"}
            </button>
          ) : null}
        </div>
      </div>

      {board && messages[board.index] ? (
        <SmartBoard
          key={board.run}
          scenes={messages[board.index].scenes}
          voice={voice}
          language={language}
          withVoice={isVoiceOn}
          pinnedLine={messages[board.index].boardLine}
          pinnedLabel="Your line"
        />
      ) : null}

      <p className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">Conversation</p>
      <div ref={listRef} aria-live="polite" className="max-h-72 space-y-2 overflow-y-auto rounded-2xl bg-paper p-3">
        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === "tutor" ? "justify-start" : "justify-end"}`}>
            <div
              className={`max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-2 text-sm leading-relaxed ${message.role === "tutor" ? "rounded-bl-sm bg-card ring-1 ring-rule" : "rounded-br-sm bg-ink text-white"}`}
            >
              {message.badge ? (
                <p className={`mb-1 text-xs font-bold ${message.badge.good ? "text-green-tick" : "text-red-pen"}`}>
                  {message.badge.text}
                </p>
              ) : null}
              <MixedMath text={message.text} />
              {message.role === "tutor" ? (
                <button
                  onClick={() => setBoard((previous) => ({ index, run: (previous?.run ?? 0) + 1 }))}
                  aria-label="Play this on the board again"
                  className="ml-2 align-middle text-xs text-muted hover:text-ink"
                >
                  ▶ board
                </button>
              ) : null}
            </div>
          </div>
        ))}
        {isWaiting ? (
          <p className="px-2 text-sm text-muted" role="status">
            Tutor is thinking…
          </p>
        ) : null}
      </div>

      {error ? (
        <Notice tone="error" title="Something went wrong">
          {error}
        </Notice>
      ) : null}
      {voice.error ? (
        <Notice
          tone="warning"
          title="Voice"
          action={
            <button
              onClick={voice.clearError}
              className="rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-rule"
            >
              OK
            </button>
          }
        >
          {voice.error}
        </Notice>
      ) : null}

      {latest.show_practice ? (
        <PracticeCard checkId={checkId} title="Your practice question" />
      ) : (
        <div className="space-y-2">
          {voice.canTalk ? (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={toggleMic}
                disabled={isWaiting || voice.status === "transcribing"}
                aria-label={voice.status === "listening" ? "Stop listening" : "Speak your answer"}
                className={`relative grid h-14 w-14 shrink-0 place-items-center rounded-full text-2xl text-white shadow-md transition disabled:opacity-50 ${voice.status === "listening" ? "bg-red-pen" : "bg-ink hover:bg-ink-soft"}`}
              >
                {voice.status === "listening" ? (
                  <span className="absolute inset-0 animate-ping rounded-full bg-red-pen/40" />
                ) : null}
                <span className="relative">{voice.status === "listening" ? "■" : "🎤"}</span>
              </button>
              <p className="text-sm text-muted" role="status">
                {VOICE_STATUS[voice.status]}
              </p>
            </div>
          ) : null}
          <form onSubmit={send} className="flex items-center gap-2">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              aria-label="Your answer to the tutor"
              placeholder="…or type your answer or your reason"
              className="min-w-0 flex-1 rounded-full border border-rule bg-paper px-4 py-2.5 text-sm focus:border-ink-soft focus:outline-none"
            />
            <button
              type="submit"
              disabled={isWaiting || !draft.trim()}
              className="rounded-full bg-red-pen px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </div>
      )}
    </section>
  );
}
