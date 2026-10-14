// Showing maths: LaTeX with KaTeX, sentences with $maths$ inside, and a question with its expressions.

import katex from "katex";

const SYMBOLS: [RegExp, string][] = [
  [/\\(?:times|cdot)/g, "×"],
  [/\s*\*\s*/g, " × "],
  [/\\div/g, "÷"],
  [/\\pm/g, "±"],
  [/\\(?:approx|sim)/g, "≈"],
  [/\\neq?/g, "≠"],
  [/\\(?:leq?|leqslant)/g, "≤"],
  [/\\(?:geq?|geqslant)/g, "≥"],
  [/\\(?:rightarrow|to|Rightarrow|implies)/g, "→"],
  [/\\parallel/g, "∥"],
  [/\\perp/g, "⊥"],
  [/\\angle/g, "∠"],
  [/\\triangle/g, "△"],
  [/\\(?:theta|vartheta)/g, "θ"],
  [/\\pi/g, "π"],
  [/\\alpha/g, "α"],
  [/\\beta/g, "β"],
  [/\\infty/g, "∞"],
  [/\^\s*\{?\\circ\}?/g, "°"],
  [/\\circ/g, "°"],
];
const SUPERSCRIPTS: Record<string, string> = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻" };

/** LaTeX as a person would write it in plain text: '\\frac{-3}{5} \\times x^2' -> '(-3)/5 × x²'. For words with maths in them
 * and for LaTeX the reader garbled, so a line never shows backslashes and braces. */
export function readableLatex(latex: string): string {
  let text = latex.replace(/\\(?:text|textbf|mathrm|operatorname|mbox)\s*\{([^{}]*)\}/g, "$1");
  for (let pass = 0; pass < 3; pass++) {
    text = text
      .replace(/\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, (_, top: string, bottom: string) => `${wrap(top)}/${wrap(bottom)}`)
      .replace(/\\sqrt\s*\[\s*3\s*\]\s*\{([^{}]*)\}/g, "∛($1)")
      .replace(/\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}/g, "$1th root of ($2)")
      .replace(/\\sqrt\s*\{([^{}]*)\}/g, (_, inside: string) => `√${wrap(inside)}`)
      .replace(/\\(?:text|textbf|mathrm|operatorname|mbox|overline|bar)\s*\{([^{}]*)\}/g, "$1");
  }
  for (const [pattern, symbol] of SYMBOLS) text = text.replace(pattern, symbol);
  text = text
    .replace(/\^\s*\{?(-?\d+)\}?/g, (_, power: string) => [...power].map((digit) => SUPERSCRIPTS[digit]).join(""))
    .replace(/\\(?:left|right|displaystyle|quad|qquad|,|;|:|!)/g, " ")
    .replace(/\\([%&$#_{}])/g, "$1")
    .replace(/\\\\/g, " ")
    .replace(/\\(?:text|textbf|mathrm|operatorname|mbox)\s*\{/g, "") // a group the reader never closed
    .replace(/\\[a-zA-Z]+/g, (command) => command.slice(1))
    .replace(/[{}]/g, "")
    .replace(/\\/g, "");
  return text.replace(/\s+/g, " ").trim();
}

const wrap = (part: string) => (/^[\w.]+$/.test(part.trim()) ? part.trim() : `(${part.trim()})`);

/** A reader often writes the student's '×' as '*', and KaTeX shows a raw asterisk: show the × they wrote. */
export function asWritten(latex: string): string {
  return latex.replace(/\s*\*\s*/g, " \\times ");
}

export function MathText({ latex, display = false }: { latex: string; display?: boolean }) {
  let html: string | null = null;
  try {
    html = katex.renderToString(asWritten(latex), { displayMode: display, throwOnError: true, strict: "ignore" });
  } catch {
    return <span className="italic">{readableLatex(latex)}</span>; // broken LaTeX never breaks the page, nor shows raw
  }
  // KaTeX builds this HTML itself and escapes the input.
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

export function splitMath(text: string): { isMath: boolean; value: string }[] {
  return text
    .split(/\$([^$]+)\$/)
    .map((value, index) => ({ isMath: index % 2 === 1, value }))
    .filter((part) => part.value !== "");
}

/** "Look at line 2: what is $(x-3)^2$?" -> words and rendered maths. */
export function MixedMath({ text }: { text: string }) {
  return (
    <>
      {splitMath(text).map((part, index) =>
        part.isMath ? <MathText key={index} latex={part.value} /> : <span key={index}>{part.value}</span>,
      )}
    </>
  );
}

const squash = (text: string) =>
  text
    .replace(/\$/g, "")
    .replace(/\\(cdot|times)|[×·]/g, "*")
    .replace(/−/g, "-")
    .replace(/[\s{}.]/g, "")
    .toLowerCase();

/** "Solve: x^2 = 4" or "Solve 3x + 7 = 22" (when the rest is the shown maths) -> "Solve". Word problems -> null. */
export function getQuestionLabel(text: string, expressions: string[]): string | null {
  const colon = text.indexOf(":");
  if (colon > 0 && colon <= 40) return text.slice(0, colon);
  if (expressions.length !== 1) return null;
  for (let space = text.indexOf(" "); space > 0 && space <= 40; space = text.indexOf(" ", space + 1)) {
    if (squash(text.slice(space + 1)) === squash(expressions[0])) return text.slice(0, space).trim();
  }
  return null;
}

export function QuestionText({
  text,
  expressions,
  size = "large",
}: {
  text: string;
  expressions: string[];
  size?: "large" | "small";
}) {
  const label = getQuestionLabel(text, expressions);
  if (expressions.length === 0 || !label) {
    return (
      <p className={size === "large" ? "text-lg leading-relaxed" : "text-sm leading-relaxed"}>
        <MixedMath text={text} />
      </p>
    );
  }
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <div className={`overflow-x-auto ${size === "large" ? "text-2xl" : "text-lg"}`}>
        {expressions.map((expression) => (
          <div key={expression}>
            <MathText latex={expression} display={size === "large"} />
          </div>
        ))}
      </div>
    </div>
  );
}

export const formatMarks = (score: number) => (Number.isInteger(score) ? String(score) : score.toFixed(1));
export const formatDifficulty = (difficulty: number) =>
  difficulty <= 1 ? "Easy" : difficulty === 2 ? "Medium" : "Hard";
