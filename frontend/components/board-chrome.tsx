"use client";

// The chalkboard both lessons are taught on: a framed board, the teacher (speaking indicator), and a
// video-player style control bar. SmartBoard and ConceptVisual only decide what is written on it.

import type { ReactNode } from "react";

function TeacherBadge({ isSpeaking, label }: { isSpeaking: boolean; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="relative grid h-9 w-9 place-items-center">
        {isSpeaking ? <span className="teacher-ring absolute inset-0 rounded-full" aria-hidden /> : null}
        <span className="relative grid h-9 w-9 place-items-center rounded-full bg-chalk font-display text-lg font-semibold text-board">
          S
        </span>
      </span>
      <div className="leading-tight">
        <p className="text-[13px] font-semibold text-chalk">Samjho teacher</p>
        <p className="text-[11px] text-chalk/55">{isSpeaking ? "speaking…" : label}</p>
      </div>
    </div>
  );
}

export function BoardShell({
  kicker,
  title,
  isSpeaking,
  statusLabel,
  children,
  footer,
}: {
  kicker: string;
  title?: string;
  isSpeaking: boolean;
  statusLabel: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <section aria-label={title ?? kicker} className="chalk-frame">
      <div className="chalkboard text-chalk">
        <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5 sm:px-7">
          <TeacherBadge isSpeaking={isSpeaking} label={statusLabel} />
          <div className="text-right">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-chalk-yellow/80">{kicker}</p>
            {title ? <p className="font-display text-base text-chalk/90 sm:text-lg">{title}</p> : null}
          </div>
        </header>
        <div className="px-4 pt-4 sm:px-6">{children}</div>
        <footer className="px-5 pb-5 pt-4 sm:px-7">{footer}</footer>
        <div className="chalk-tray" aria-hidden />
      </div>
    </section>
  );
}

// ---------- the player bar ----------

function Icon({ name }: { name: "play" | "pause" | "prev" | "next" }) {
  const paths = {
    play: <path d="M8 5.5v13l11-6.5z" fill="currentColor" />,
    pause: (
      <g fill="currentColor">
        <rect x="7" y="5.5" width="3.6" height="13" rx="1.2" />
        <rect x="13.4" y="5.5" width="3.6" height="13" rx="1.2" />
      </g>
    ),
    prev: <path d="M17 6v12l-8.5-6zM7 6h2v12H7z" fill="currentColor" />,
    next: <path d="M7 6v12l8.5-6zM15 6h2v12h-2z" fill="currentColor" />,
  };
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      {paths[name]}
    </svg>
  );
}

export function PlayerBar({
  caption,
  index,
  count,
  share,
  isPlaying,
  captionsOnly,
  onPlay,
  onPause,
  onSeek,
}: {
  caption: ReactNode;
  index: number;
  count: number;
  share: number; // 0..1 through the whole lesson
  isPlaying: boolean;
  captionsOnly: boolean;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (index: number) => void;
}) {
  return (
    <div className="space-y-4">
      <p key={index} className="chalk-caption fade-up min-h-[3.25rem] text-[19px] leading-relaxed text-chalk sm:text-xl">
        {caption}
      </p>
      <div className="flex items-center gap-3 sm:gap-4">
        <button
          type="button"
          aria-label="Previous step"
          onClick={() => onSeek(index - 1)}
          disabled={index === 0}
          className="grid h-9 w-9 place-items-center rounded-full text-chalk/70 transition hover:bg-chalk/10 hover:text-chalk disabled:opacity-25"
        >
          <Icon name="prev" />
        </button>
        <button
          type="button"
          aria-label={isPlaying ? "Pause" : "Play"}
          onClick={isPlaying ? onPause : onPlay}
          className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-chalk text-board shadow-[0_6px_20px_-6px_rgba(0,0,0,0.6)] transition hover:scale-105"
        >
          <Icon name={isPlaying ? "pause" : "play"} />
        </button>
        <button
          type="button"
          aria-label="Next step"
          onClick={() => onSeek(index + 1)}
          disabled={index >= count - 1}
          className="grid h-9 w-9 place-items-center rounded-full text-chalk/70 transition hover:bg-chalk/10 hover:text-chalk disabled:opacity-25"
        >
          <Icon name="next" />
        </button>

        <div className="relative flex-1" role="tablist" aria-label="Lesson steps">
          <div className="h-[3px] rounded-full bg-chalk/15" />
          <div
            className="absolute left-0 top-0 h-[3px] rounded-full bg-chalk-yellow transition-[width] duration-150 ease-linear"
            style={{ width: `${Math.round(share * 100)}%` }}
          />
          <div className="absolute inset-x-0 -top-[7px] flex justify-between">
            {Array.from({ length: count }, (_, step) => (
              <button
                key={step}
                role="tab"
                aria-selected={step === index}
                aria-label={`Step ${step + 1}`}
                onClick={() => onSeek(step)}
                className={`h-[17px] w-[17px] rounded-full border-2 transition ${
                  step < index
                    ? "border-chalk-yellow bg-chalk-yellow"
                    : step === index
                      ? "scale-110 border-chalk-yellow bg-board"
                      : "border-chalk/25 bg-board hover:border-chalk/50"
                }`}
              />
            ))}
          </div>
        </div>

        <p className="w-14 shrink-0 text-right text-xs tabular-nums text-chalk/55">
          {index + 1} / {count}
          {captionsOnly ? <span className="block text-[10px]">captions</span> : null}
        </p>
      </div>
    </div>
  );
}
