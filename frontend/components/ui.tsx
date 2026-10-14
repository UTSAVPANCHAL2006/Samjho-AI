"use client";

// Small shared building blocks: a message box, the 3-step journey bar, the photo picker (a scanner-style card,
// camera or gallery), and the photo shown with a scan line while the teacher reads it.

import { useMemo, useState, type DragEvent, type ReactNode } from "react";
import { CameraIcon, FlatIcon, FrameIcon, SunIcon } from "@/components/icons";

// ---------- message box ----------

const TONES = {
  error: "border-red-pen/30 bg-red-soft text-red-pen",
  warning: "border-amber/30 bg-amber-soft text-amber",
  info: "border-blue-ink/20 bg-blue-soft text-blue-ink",
  success: "border-green-tick/30 bg-green-soft text-green-tick",
};

export function Notice({
  tone,
  title,
  children,
  action,
}: {
  tone: keyof typeof TONES;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-2xl border px-5 py-4 ${TONES[tone]}`}>
      <p className="font-semibold">{title}</p>
      {children ? <div className="mt-1 text-sm text-ink-soft">{children}</div> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

// ---------- ① question → ② working → ③ red pen ----------

const JOURNEY = [
  { title: "Question", hint: "Photo of the book" },
  { title: "Your working", hint: "Photo of your notebook" },
  { title: "Red-pen check", hint: "See the mistake, fix it" },
];

export function JourneySteps({ activeStep }: { activeStep: 1 | 2 | 3 }) {
  return (
    <nav aria-label="Your progress" className="surface p-1.5">
      <ol className="grid grid-cols-[auto_auto_auto] justify-between gap-1 sm:grid-cols-3">
        {JOURNEY.map((step, index) => {
          const number = index + 1;
          const isActive = number === activeStep;
          const isDone = number < activeStep;
          return (
            <li
              key={step.title}
              aria-current={isActive ? "step" : undefined}
              className={`flex items-center gap-2.5 rounded-[1.25rem] px-2.5 py-2.5 transition ${isActive ? "bg-ink text-white shadow-lg shadow-ink/20" : ""}`}
            >
              <span
                className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold ${isActive ? "bg-white text-ink" : isDone ? "bg-green-tick text-white" : "bg-paper-deep text-muted"}`}
                aria-hidden
              >
                {isDone ? "✓" : number}
              </span>
              {/* On a phone only the current step is named; the others are just their number. */}
              <span className={`min-w-0 ${isActive ? "" : "hidden sm:block"}`}>
                <span className={`block truncate text-sm font-semibold ${isActive || isDone ? "" : "text-muted"}`}>
                  {step.title}
                </span>
                <span className={`hidden truncate text-xs sm:block ${isActive ? "text-white/70" : "text-muted"}`}>
                  {step.hint}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// ---------- photo picker: a scanner card; camera or gallery on a phone, drag & drop on a laptop ----------

const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
const TIPS = [
  { icon: FlatIcon, text: "Page flat" },
  { icon: SunIcon, text: "Good light" },
  { icon: FrameIcon, text: "Whole page in" },
];

export function PhotoPicker({
  title,
  hint,
  onPhoto,
}: {
  title: string;
  hint: string;
  onPhoto: (photo: File) => void;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function accept(photo: File | undefined) {
    if (!photo) return;
    const issue = !PHOTO_TYPES.includes(photo.type)
      ? "Please choose a JPEG, PNG or WEBP photo."
      : photo.size > 10 * 1024 * 1024
        ? "The photo must be under 10 MB."
        : null;
    setProblem(issue);
    if (!issue) onPhoto(photo);
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event: DragEvent<HTMLDivElement>) => {
          event.preventDefault();
          setIsDragging(false);
          accept(event.dataTransfer.files[0]);
        }}
        className={`scan-frame flex flex-col items-center gap-4 rounded-[1.75rem] px-6 py-12 text-center transition sm:py-14 ${isDragging ? "bg-red-soft" : "bg-paper"}`}
      >
        <span className="grid h-16 w-16 place-items-center rounded-[1.25rem] bg-ink text-white shadow-lg shadow-ink/25">
          <CameraIcon size={30} />
        </span>
        <span className="space-y-1">
          <span className="block font-display text-xl font-bold tracking-tight">{title}</span>
          <span className="mx-auto block max-w-sm text-sm leading-relaxed text-muted">{hint}</span>
        </span>
        <span className="flex flex-wrap justify-center gap-2.5">
          <label className="btn-primary cursor-pointer">
            <CameraIcon size={18} /> Open camera
            <input
              type="file"
              accept={PHOTO_TYPES.join(",")}
              capture="environment"
              className="sr-only"
              aria-label={`${title}: take a photo`}
              onChange={(event) => accept(event.target.files?.[0])}
            />
          </label>
          <label className="btn-secondary cursor-pointer">
            Choose from gallery
            <input
              type="file"
              accept={PHOTO_TYPES.join(",")}
              className="sr-only"
              aria-label={`${title}: choose a photo`}
              onChange={(event) => accept(event.target.files?.[0])}
            />
          </label>
        </span>
        <span className="hidden text-xs text-muted sm:block">or drag &amp; drop · JPG, PNG, WEBP · up to 10 MB</span>
      </div>
      <ul className="flex flex-wrap justify-center gap-2" aria-label="Photo tips">
        {TIPS.map((tip) => (
          <li key={tip.text} className="flex items-center gap-1.5 rounded-full bg-card px-3 py-1.5 text-xs font-medium text-ink-soft ring-1 ring-rule">
            <tip.icon size={15} /> {tip.text}
          </li>
        ))}
      </ul>
      {problem ? (
        <p role="alert" className="text-center text-sm font-medium text-red-pen">
          {problem}
        </p>
      ) : null}
    </div>
  );
}

/** The student's photo with a scan line moving over it, while the teacher reads it. */
export function PhotoReading({ photo, title, hint }: { photo: File | null; title: string; hint?: string }) {
  // One small object URL per photo, kept for the page's life: revoking it in an effect cleanup breaks the image
  // when React runs effects twice (development) and the screen is only shown while that photo is being read.
  const url = useMemo(() => (photo ? URL.createObjectURL(photo) : null), [photo]);
  return (
    <div className="fade-up surface flex flex-col items-center gap-5 px-5 py-8 text-center sm:flex-row sm:text-left" role="status">
      <div className="relative h-56 w-44 shrink-0 overflow-hidden rounded-2xl bg-paper-deep shadow-lg ring-1 ring-rule">
        {url ? (
          // eslint-disable-next-line @next/next/no-img-element -- a local object URL of the student's own photo
          <img src={url} alt="Your photo" className="h-full w-full object-cover" />
        ) : null}
        <span className="scan-line" aria-hidden />
      </div>
      <div className="space-y-2">
        <p className="eyebrow">The teacher is reading</p>
        <p className="font-display text-2xl font-bold tracking-tight">{title}</p>
        {hint ? <p className="max-w-sm text-sm leading-relaxed text-muted">{hint}</p> : null}
      </div>
    </div>
  );
}

