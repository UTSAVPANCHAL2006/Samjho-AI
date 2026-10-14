// The only place the frontend talks to the backend. Types mirror backend/app/schemas.py.

export type Language = "en" | "hinglish";

export interface Question {
  id: string;
  trust: "verified" | "single_reading" | "ai_agreement"; // how the answer key was confirmed
  class_level: number;
  chapter: string;
  text: string;
  expressions: string[]; // only the maths that is safe to show
  marks: number;
  difficulty: number;
}

export interface Understood {
  status:
    | "solved"
    | "needs_clarification"
    | "unsupported"
    | "parse_failed"
    | "verification_failed"
    | "not_maths"
    | "ai_unavailable";
  question: Question | null;
  other_parts: Question[]; // (b), (c)... of a multi-part question
  message: string | null; // exactly what is missing, ambiguous or not supported
  understood: string[]; // the maths we read, shown with the message
  read_text: string | null; // what we read from a photo
}

export interface Check {
  id: string;
  question_id: string;
  // graded | needs_confirmation | needs_retake | blank | skipped | unreadable | only_question_copied
  // | off_question | not_maths | ai_unavailable
  status: string;
  message: string | null;
  lines: { latex: string; needs_check: boolean }[];
  steps: {
    line_no: number;
    // note: a given value like a = 2; carried: after the first mistake, follows from it (no tick, no cross, no marks)
    verdict: "correct" | "incorrect" | "carried" | "unverifiable" | "unreadable" | "note";
    is_question_copy: boolean;
  }[];
  score: number;
  max_score: number;
  wrong_line: number | null;
  explanation: string | null;
  mistake: string | null; // kind of mistake, e.g. "adding fractions (tops and bottoms added separately)"
  has_photo: boolean;
}

/** One drawing block of a concept visual (bar, balance, axes, ...). Fields depend on the type. */
export interface VisualElement extends Record<string, unknown> {
  type: string;
  frame: number; // the frame it appears in
  color: string;
  highlight?: boolean;
}

/** An AI-designed, SymPy-checked visual: frames appear one by one while their captions are spoken. */
export interface ConceptVisualData {
  title: string;
  frames: { caption: string }[];
  elements: VisualElement[];
}

/** One sentence of the tutor, spoken while its maths is written on the smart board. */
export interface BoardScene {
  text: string; // display text, maths inside $...$
  speech: string; // what the voice says
  maths: string[]; // LaTeX lines written on the board during this sentence (arithmetic checked by the server)
  voiceText?: string; // what the server voice should say, with maths in $...$ (defaults to text)
}

export interface Solution {
  steps: { explain: string; latex: string | null; speech: string }[];
  answer_latex: string;
  verified: boolean; // SymPy checked every line
}

export interface TutorReply {
  chat_id: string;
  reply: string;
  speech: string; // reply with maths turned into words
  stage: "hints" | "walkthrough" | "quick_check" | "practice";
  fix_correct: boolean | null;
  quick_check_correct: boolean | null;
  step_correct: boolean | null; // walkthrough: their answer for the current step
  focus_line: number;
  show_practice: boolean;
  scenes: BoardScene[];
  board_line: { line_no: number; latex: string } | null; // the student's line being discussed
}

export interface Student {
  id: string;
  name: string;
  class_level: number;
}

export interface Progress {
  name: string;
  class_level: number;
  streak_days: number;
  checked_today: boolean;
  checks_done: number;
  full_marks: number;
  mistakes_fixed: number;
  chapters: { chapter: string; attempts: number; full_marks: number; needs_revision: boolean }[];
  /** Kinds of mistake decided by the maths checker (not an AI), most frequent first. */
  mistakes: { mistake: string; times: number; chapters: string[] }[];
  recent: {
    check_id: string;
    question_text: string;
    chapter: string;
    score: number;
    max_score: number;
    created_at: string;
  }[];
}

const BASE_URL = `${(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "")}/api`;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null = null, // null = the server could not be reached
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE_URL + path, init);
  } catch {
    throw new ApiError("We can't reach Samjho right now. Check your internet and try again.");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    throw new ApiError(
      typeof detail === "string" ? detail : "Something went wrong. Please try again.",
      response.status,
    );
  }
  return body as T;
}

const postJson = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function postForm(fields: Record<string, Blob | string | null>): RequestInit {
  const form = new FormData();
  for (const [name, value] of Object.entries(fields)) if (value !== null) form.append(name, value);
  return { method: "POST", body: form };
}

/** The "Understand the mistake" board. complete = false: the drawing is missing for now (busy AI), so ask again. */
/** One number check the server proved (checker.measureMistake): sizes side by side, the answer put back, a test point. */
export type NumberCheck =
  | { kind: "size"; given: string; expected: string; givenApprox?: string; expectedApprox?: string; ratio?: string }
  | { kind: "plug_in"; equation: string; variable: string; given: string; left: string; right: string }
  | { kind: "test_point"; point: string; question: string; given: string; questionValue: string; givenValue: string };

export interface CheckVisual {
  visual: ConceptVisualData | null;
  insight?: string | null;
  numbers?: NumberCheck[];
  /** Proven right before the mistake: ✓ lines, given values, and whether only one idea broke (a known trap). */
  rightSoFar?: { lines: { line: number; latex: string }[]; givens: string[]; oneIdea: boolean } | null;
  complete?: boolean;
}

export const api = {
  listQuestions: (classLevel: number) => request<Question[]>(`/questions?class_level=${classLevel}`),
  getQuestion: (id: string) => request<Question>(`/questions/${encodeURIComponent(id)}`),
  understandText: (text: string) => request<Understood>("/questions", postJson({ text })),
  understandPhoto: (photo: File) => request<Understood>("/questions/photo", postForm({ image: photo })),

  checkPhoto: (questionId: string, photo: File, studentId: string | null) =>
    request<Check>("/checks", postForm({ image: photo, question_id: questionId, student_id: studentId })),
  checkTyped: (questionId: string, lines: string[], studentId: string | null) =>
    request<Check>("/checks/typed", postJson({ question_id: questionId, lines, student_id: studentId })),
  confirmLines: (checkId: string, lines: string[]) => request<Check>(`/checks/${checkId}/confirm`, postJson({ lines })),
  photoUrl: (checkId: string) => `${BASE_URL}/checks/${checkId}/photo`,
  getQuestionVisual: (questionId: string, language: Language) =>
    request<{ visual: ConceptVisualData | null }>(`/questions/${questionId}/visual?language=${language}`),
  getCheckVisual: (checkId: string, language: Language) =>
    request<CheckVisual>(
      `/checks/${checkId}/visual?language=${language}`,
    ),

  getSolution: (checkId: string, language: Language) =>
    request<Solution>(`/checks/${checkId}/solution?language=${language}`),

  startTutor: (checkId: string, language: Language) =>
    request<TutorReply>("/tutor", postJson({ check_id: checkId, language })),
  sendToTutor: (chatId: string, text: string) => request<TutorReply>(`/tutor/${chatId}`, postJson({ text })),

  createStudent: (name: string, classLevel: number) =>
    request<Student>("/students", postJson({ name, class_level: classLevel })),
  getProgress: (studentId: string) => request<Progress>(`/students/${studentId}/progress`),
  nextPractice: (checkId: string, studentId: string | null) =>
    request<{ question: Question | null; reason: string }>(
      `/practice?check_id=${checkId}${studentId ? `&student_id=${studentId}` : ""}`,
    ),

  voiceMode: () => request<{ provider: "sarvam" | "browser" }>("/voice"),
  listen: (wav: Blob, language: Language) =>
    request<{ text: string }>("/voice/listen", postForm({ audio: wav, language })),
  speak: (text: string, language: Language) =>
    request<{ audio_base64: string }>("/voice/speak", postJson({ text, language })),
};
