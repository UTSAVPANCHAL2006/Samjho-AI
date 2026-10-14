// Tests for turning plain typed maths ('x square', 'sqrt(49)') into LaTeX previews.

import { describe, expect, it } from "vitest";
import { toPreviewLatex } from "@/lib/plain-maths";

describe("toPreviewLatex", () => {
  it.each([
    ["sqrt(49)", "\\sqrt{49}"],
    ["root 49", "\\sqrt{49}"],
    ["x square + 2x", "x^{2} + 2x"],
    ["pi r^2", "\\pi  r^2"],
    ["12 x 8 = 96", "12 \\times 8 = 96"],
    ["3/4", "\\frac{3}{4}"],
    ["x = 29/3", "x = \\frac{29}{3}"],
    ["5% of 200", "5\\% \\text{ of }  200"],
    ["2^(n+1)", "2^{n+1}"],
  ])("turns %s into LaTeX", (typed, latex) => {
    expect(toPreviewLatex(typed)).toBe(latex);
  });

  it("keeps a variable glued to a number", () => {
    expect(toPreviewLatex("3x = 22 + 7")).toBe("3x = 22 + 7");
  });

  it("leaves real LaTeX alone", () => {
    expect(toPreviewLatex("\\frac{22}{7} \\times 7^2")).toBe("\\frac{22}{7} \\times 7^2");
    expect(toPreviewLatex("\\sqrt{16}")).toBe("\\sqrt{16}");
  });
});
