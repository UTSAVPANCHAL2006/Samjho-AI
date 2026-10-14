// Students type maths the way they say it: "x square", "sqrt(49)", "3/4", "pi r^2", "12 x 8", "5% of 200".
// This turns it into LaTeX for the live preview. The backend parser applies the same rules when checking,
// so what the student sees is what gets checked. No maths keyboard needed.

const RULES: [RegExp, string][] = [
  [/(?<![\\a-zA-Z])(?:sqrt|root|√)\s*\(([^()]*)\)/gi, "\\sqrt{$1}"],
  [/(?<![\\a-zA-Z])(?:sqrt|root|√)\s*(\d+(?:\.\d+)?|[a-zA-Z])/gi, "\\sqrt{$1}"],
  [/\s*\b(?:square|squared)\b/gi, "^{2}"],
  [/\s*\b(?:cube|cubed)\b/gi, "^{3}"],
  [/(?<![\\a-zA-Z])pi(?![a-zA-Z])/gi, "\\pi "],
  [/(\d)\s+[xX]\s+(?=\d)/g, "$1 \\times "],
  [/\*/g, " \\times "],
  [/(\d+(?:\.\d+)?)\s*\\?%\s*of\b/gi, "$1\\% \\text{ of } "],
  [/(\d+(?:\.\d+)?)\s*(?<!\\)%/g, "$1\\%"],
  [/\^\s*\(([^()]*)\)/g, "^{$1}"],
  [/\^\s*(\d{2,})/g, "^{$1}"],
  [/(?<![\\\w{])(\d+|[a-zA-Z])\s*\/\s*(\d+|[a-zA-Z])(?![\w}])/g, "\\frac{$1}{$2}"],
];

export function toPreviewLatex(typed: string): string {
  return RULES.reduce((latex, [pattern, replacement]) => latex.replace(pattern, replacement), typed.trim());
}

// Shown next to the typing box: how to write maths without a special keyboard.
export const TYPING_EXAMPLES: { typed: string; meaning: string }[] = [
  { typed: "x^2  or  x square", meaning: "x^{2}" },
  { typed: "3/4", meaning: "\\frac{3}{4}" },
  { typed: "sqrt(49)  or  root 49", meaning: "\\sqrt{49}" },
  { typed: "12 x 8  or  12*8", meaning: "12 \\times 8" },
  { typed: "pi r^2", meaning: "\\pi r^{2}" },
  { typed: "5% of 200", meaning: "5\\% \\text{ of } 200" },
];
