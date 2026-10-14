// Tests for small helpers: maths text splitting and readable fallbacks, question labels, WAV encoding, red-pen lines.

import { describe, expect, it } from "vitest";
import { asWritten, getQuestionLabel, readableLatex, splitMath } from "@/components/math";
import { encodeWav } from "@/lib/voice";
import { isWordLine } from "@/components/red-pen";

describe("showing maths", () => {
  it("shows a word line or garbled LaTeX as plain text, never backslashes and braces", () => {
    expect(readableLatex("Find the difference: \\frac{-3}{5} - \\frac{7}{10}")).toBe("Find the difference: (-3)/5 - 7/10");
    expect(readableLatex("\\text{Ans: Third angle is } 70^\\circ")).toBe("Ans: Third angle is 70°");
    expect(readableLatex("\\text{Area = } 44/7 \\text{ cm}^2")).toBe("Area = 44/7 cm²");
    expect(isWordLine("Sol:") && isWordLine("\\text{Given:}") && !isWordLine("x = 2")).toBe(true);
    expect(readableLatex("\\text{Cost of } 1 \\text{ pen = \\text{Rs } 12")).toBe("Cost of 1 pen = Rs 12");
  });

  it("splits tutor replies into words and maths", () => {
    expect(splitMath("Line 2 dekho: $(x-3)^2$ kya hai?")).toEqual([
      { isMath: false, value: "Line 2 dekho: " },
      { isMath: true, value: "(x-3)^2" },
      { isMath: false, value: " kya hai?" },
    ]);
  });

  it("labels a question only when its maths is shown separately", () => {
    expect(getQuestionLabel("Solve: 2x + 3 = 11", ["2x+3=11"])).toBe("Solve");
    expect(getQuestionLabel("Solve 3x + 7 = 22", ["3x+7=22"])).toBe("Solve");
    expect(getQuestionLabel("Find the area of a circle of radius 7 cm", [])).toBeNull();
  });
});

describe("voice recording", () => {
  it("makes a 16 kHz mono 16-bit WAV that speech APIs accept", async () => {
    const wav = encodeWav(new Float32Array(16000));
    const view = new DataView(await wav.arrayBuffer());
    const text = (start: number) => String.fromCharCode(...new Uint8Array(view.buffer, start, 4));
    expect([text(0), text(8), text(36)]).toEqual(["RIFF", "WAVE", "data"]);
    expect([view.getUint16(22, true), view.getUint32(24, true), view.getUint16(34, true)]).toEqual([1, 16000, 16]);
    expect(wav.size).toBe(44 + 16000 * 2);
  });
});

describe("asWritten", () => {
  it("shows a student's multiplication as ×, never a raw asterisk", () => {
    expect(asWritten("(60/360)*2*(22/7)*6")).toBe("(60/360) \\times 2 \\times (22/7) \\times 6");
    expect(asWritten("\\frac{1}{2} \\times 6")).toBe("\\frac{1}{2} \\times 6"); // already right: unchanged
  });
});
