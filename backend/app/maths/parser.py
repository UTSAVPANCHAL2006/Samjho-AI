# Turns handwritten / typed maths into SymPy objects. Pure code, no AI.

import re
from functools import lru_cache
from typing import Any

import sympy
from lark import Tree
from sympy.parsing.latex import parse_latex

# ---------- latex parser ----------
# Turns handwritten-maths LaTeX (as read by the vision model) into SymPy objects.

# Characters vision models often return that the LaTeX parser does not understand.
# Every dash that means minus, superscripts, fullwidth symbols and vulgar fractions, as typed or OCR'd.
UNICODE_REPLACEMENTS = {
    "−": "-",
    "–": "-",
    "—": "-",
    "‒": "-",
    "﹣": "-",
    "－": "-",
    "＋": "+",
    "＝": "=",
    "×": r"\cdot ",
    "✕": r"\cdot ",
    "÷": "/",
    "·": r"\cdot ",
    "√": r"\sqrt",
    "½": "(1/2)",
    "⅓": "(1/3)",
    "⅔": "(2/3)",
    "¼": "(1/4)",
    "¾": "(3/4)",
    "\u00a0": " ",
}
SUPERSCRIPT_DIGITS = str.maketrans("⁻⁰¹²³⁴⁵⁶⁷⁸⁹", "-0123456789")


def normalizeSymbols(text: str) -> str:
    """Unicode maths symbols -> plain typing. Superscript runs become powers: 'x¹²' -> 'x^{12}'."""
    text = re.sub(r"⁻?[⁰¹²³⁴⁵⁶⁷⁸⁹]+", lambda match: "^{" + match.group(0).translate(SUPERSCRIPT_DIGITS) + "}", text)
    for original, replacement in UNICODE_REPLACEMENTS.items():
        text = text.replace(original, replacement)
    return text


# Units are checked separately (UNIT_ERROR); they are removed before the maths is parsed.
UNIT_PATTERN = re.compile(
    r"\\(text|mathrm|operatorname)\{\s*(cm|mm|m|km|g|kg|mg|l|ml|s|min|h|hr|hrs|rs|Rs|years?|days?|units?|sq|cu|deg|degrees?)\.?\s*\}(\s*\^\s*\{?[23]\}?)?"
)
CURRENCY_PATTERN = re.compile(r"(₹|\\text\{\s*(?:Rs|INR)\.?\s*\}|Rs\.?)")
# Degrees become radians only when the line has trigonometry (sin 30° -> sin(π/6)): '30^\\circ' -> '\\frac{30 \\pi}{180}'.
DEGREE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\^\{?\\circ\}?|°)")
# Without trigonometry an angle stays a plain number of degrees: '180° - 65°' is 115, not 23π/36.
TRIG_PATTERN = re.compile(r"(?<![a-zA-Z])\\?(sin|cos|tan|cot|sec|cosec|csc)(?![a-zA-Z])")
# The lark parser has no \\pi; we parse \\xi (never used in Class 6-10 maths) and swap in sympy.pi afterwards.
PI_PLACEHOLDER = "xi"
PI_PATTERN = re.compile(r"\\pi(?![a-zA-Z])|π")

# Words students write before '=' to name a quantity ("Area = ...", "S.I. = ..."). Only these are removed,
# so algebra like 'xy = 6' is never touched.
LABEL_WORDS = (
    "area",
    "perimeter",
    "volume",
    "surface area",
    "tsa",
    "csa",
    "lsa",
    "ar",
    "si",
    "s.i.",
    "ci",
    "c.i.",
    "amount",
    "cp",
    "c.p.",
    "sp",
    "s.p.",
    "profit",
    "loss",
    "interest",
    "mean",
    "median",
    "mode",
    "probability",
    "distance",
    "length",
    "breadth",
    "height",
    "side",
    "radius",
    "diameter",
    "circumference",
    "sum",
    "total",
    "answer",
    "ans",
    "required",
    "speed",
    "time",
    "rate",
    "discount",
)
LABEL_PATTERN = re.compile(
    r"^\s*(\\text\{\s*)?(" + "|".join(re.escape(word) for word in LABEL_WORDS) + r")(\s*\})?\s*(?==)",
    re.IGNORECASE,
)

# 'Ans:', '\\text{Given: Radius }', '\\text{Area of sector} =': words in front of the maths are a label, not maths.
WORD_TEXT_PREFIX = re.compile(r"^\s*\\text\{\s*([A-Za-z][A-Za-z0-9 .,']*:?[A-Za-z0-9 .,']*)\}\s*")  # 'Cost of 1 pen' too
PLAIN_WORD_PREFIX = re.compile(r"^\s*[A-Za-z]{3,}[A-Za-z .']{0,30}:\s*")
NAMED_BEFORE_EQUALS = re.compile(r"^\s*(\([^()]*\)\s*|\\?[A-Za-z](_\{?\w+\}?)?\s*)?=")
# '-- (1)', '\\text{ --- (2)}', '\\quad (i)', '\\tag{1}' at the end of a line name the equation; they are not maths.
TAG_NUMBER = r"\(\s*(?:\d+|[ivx]+)\s*\)"
EQUATION_TAG = re.compile(
    r"\s*(?:\\text\{\s*[-–—.]*\s*" + TAG_NUMBER + r"\s*\}"  # '\\text{ --- (2)}'
    + r"|(?:\\text\{[\s\-–—.]*\}|[-–—.]+|\\q?quad)\s*"
    + TAG_NUMBER  # '-- (1)', '\\text{ --- } (1)', '\\quad (i)'
    + r"|\\tag\{[^{}]*\})\s*$"
)
# 'x1', 'y2', 'a1' (coordinates, AP terms) mean x₁, y₂, a₁ — never x × 1.
PLAIN_SUBSCRIPT = re.compile(r"(?<![\\A-Za-z0-9_])([xyab])([12])(?![0-9^}])")


MISSING_OPERATOR = re.compile(r"(?<![\\A-Za-z])[A-Za-z0-9)]\s*\\text\{\s*\}\s*[A-Za-z0-9(]|(?<!\d\s)(?<![\\A-Za-z])[a-zA-Z]\s+\d")  # '12 x 8' typed means times


ACRONYM = re.compile(r"(?<![\\A-Za-z_{])([A-Z]{2,5})(?![A-Za-z}])")
TEXT_BLOCK = re.compile(r"\\text\{[^{}]*\}")


def nameAcronyms(text: str) -> str:
    """'LCM = 36 \\times 657', '9 \\times LCM': a name written in capitals is ONE quantity, never L·C·M.
    At the start of a line it is a label like '\\text{LCM} ='; elsewhere it becomes one symbol. Words inside
    \\text{...} are left alone."""
    # 'P(6) = 1/6', 'P(E) = ...': one capital letter applied to brackets at the start of a line names a quantity
    # (a probability, f(x)), never P × 6. Inside a line 'A(2, 3)' stays a point.
    text = re.sub(
        r"^(\s*)([A-Z])\(([^()]{1,10})\)(?=\s*=)",
        lambda match: match.group(1) + "Q_{" + (match.group(2) + re.sub(r"[^a-z]", "", match.group(3).lower())).lower() + "}",
        text,
    )
    # '\\text{Ans: 1/6}': the answer itself was put inside the words. Keep the label, give the maths back.
    text = re.sub(r"\\text\{\s*([A-Za-z][A-Za-z .]*:)\s*([^{}]*[\d=][^{}]*)\}", r"\\text{\1} \2", text)
    # '\\text{Sum}(fx)', '\\text{HCF}(306, 657)', 'LCM(a, b)': a word applied to brackets is ONE quantity (Σfx).
    text = re.sub(
        r"(?:\\text\{\s*([A-Za-z]{2,})\s*\}|(?<![\\A-Za-z])([A-Z]{2,5}))\s*\(([^()]{1,16})\)",
        lambda match: "Q_{" + re.sub(r"[^a-z]", "", ((match.group(1) or match.group(2)) + match.group(3)).lower())[:14] + "}",
        text,
    )
    text = re.sub(r"^(\s*)([A-Z]{2,5})(?=\s*=)", r"\1\\text{\2}", text)
    pieces, last = [], 0
    for block in TEXT_BLOCK.finditer(text):
        pieces.append(ACRONYM.sub(lambda match: "Q_{" + match.group(1).lower() + "}", text[last : block.start()]))
        pieces.append(block.group(0))
        last = block.end()
    pieces.append(ACRONYM.sub(lambda match: "Q_{" + match.group(1).lower() + "}", text[last:]))
    return "".join(pieces)


MIXED_NUMBER = re.compile(r"(?<![\w}).^])(\d+)\s?(?:\(\s*\\frac\{(\d+)\}\{(\d+)\}\s*\)|\\frac\{(\d+)\}\{(\d+)\})")


def readMixedNumber(match: re.Match[str]) -> str:
    whole = match.group(1)
    top, bottom = match.group(2) or match.group(4), match.group(3) or match.group(5)
    if int(top) >= int(bottom):
        return match.group(0)  # '2\\frac{7}{3}' is not how a mixed number is written: leave it to the parser
    return f"({whole} + \\frac{{{top}}}{{{bottom}}})"


def stripEquationTag(text: str) -> str:
    return EQUATION_TAG.sub("", text) if "=" in text else text


def stripWordLabels(text: str) -> str:
    """Remove a word label in front of the maths: 'Ans: x = 9', '\\text{Given: } r = 6', '\\text{Area} = ...'.
    A label is removed only when it has a ':' or is directly followed by '=' (a named quantity, like 'Area =')."""
    text = re.sub(r"^\s*(\\text\{\s*)?(step|line)\s*(\}\s*)?\d+\s*(\\text\{\s*)?[:.)]\s*\}?\s*", "", text, flags=re.IGNORECASE)
    for _ in range(3):  # '\\text{Ans: } \\text{Area} = ...' has two labels
        match = WORD_TEXT_PREFIX.match(text)
        if match and ":" in match.group(1):
            text = text[match.end() :]
            continue
        named = NAMED_BEFORE_EQUALS.match(text[match.end() :]) if match else None
        if match and named and named.group(1):
            text = text[match.end() :]  # 'Semi-perimeter s = ...', 'Radius (r) = 6': the symbol is the name
            continue
        if match and named:
            word = match.group(1).strip().lower()
            # 'Area = ...' names the asked quantity: drop the word. 'HCF = 3x' is a side result: keep it as its own
            # name, so it is never mixed into the main chain of working.
            name = "" if word in LABEL_WORDS else "Q_{" + re.sub(r"[^a-z]", "", word)[:8] + "} "
            text = name + text[match.end() :]
            continue
        plain = PLAIN_WORD_PREFIX.match(text)
        if plain:
            text = text[plain.end() :]
            continue
        break
    # 'Radius (r) = 6' leaves '(r) = 6': the bracket only names the symbol.
    return re.sub(r"^\s*\(\s*(\\?[A-Za-z]+)\s*\)\s*(?==)", r"\1 ", text)


SKIP_WORDS = ("skip", "dont know", "don't know", "pata nahi", "idk", "n/a")


class LatexParseError(Exception):
    """Raised when a line cannot be understood as maths."""


MATHS_WORDS_IN_TEXT = {"sqrt", "cbrt", "root", "units", "unit", "sin", "cos", "tan", "cot", "sec", "cosec", "cm", "mm", "km"}


def unwrapMathsText(text: str) -> str:
    """A reader sometimes wraps the maths itself in \\text{...} and drops a brace: '\\text{PT}^2 \\text{ = 169 - 25'.
    Close missing braces, then take a \\text block out of the words when it is maths ('PT = 12 cm': an '=' or a
    number, and no English word of 4+ letters). Real sentences ('Let O be the centre') stay words."""
    text += "}" * max(0, text.count("{") - text.count("}"))

    def unwrap(match: re.Match[str]) -> str:
        content = match.group(1)
        words = [word for word in re.findall(r"[A-Za-z]{4,}", content) if word.lower() not in MATHS_WORDS_IN_TEXT]
        isMaths = bool(re.search(r"[=\d]", content)) and not words
        isLengthName = bool(re.fullmatch(r"\s*[A-Z]{1,3}\s*", content))  # 'PT', 'OP', 'AB': a side, not a word
        return f" {content} " if isMaths or isLengthName else match.group(0)

    return re.sub(r"\\text\{([^{}]*)\}", unwrap, text)


def normalizeLatex(latex: str) -> str:
    """Clean up a LaTeX string so the parser has the best chance of reading it."""
    text = re.sub(r"\\checkmark|✓|✔", " ", latex)  # a tick the student drew is not maths
    # '45^{circ}', '30^circ': a model that lost the backslash still means degrees, never the letters c·i·r·c
    text = re.sub(r"\^\s*\{\s*circ\s*\}|\^\s*circ\b", r"^{\\circ}", text)
    text = re.sub(r"\\(?:bar|overline)\{\s*x\s*\}", r"\\text{Mean}", text)  # '\\bar{x}' is the mean
    text = unwrapMathsText(text.strip().strip("$").strip())
    # An empty '\\text{ }' BETWEEN two operands ('(x \\text{ } 7)') is a symbol the reader lost — never guess it.
    text = re.sub(r"(?<=[\w)])\s*\\text\{\s*\}\s*(?=[\w(])", r" \\unreadable ", text)
    text = re.sub(r"\\text\{\s*\}", " ", text)  # elsewhere it is only spacing
    # '\\text{Area = } 54': the reader put the '=' inside the words. The '=' is maths: take it out of the text.
    text = re.sub(
        r"\\text\{([^{}]*?)\s*=\s*\}",
        lambda match: f"\\text{{{match.group(1)}}} =" if match.group(1).strip() else "=",
        text,
    )
    text = re.sub(r"\^\s*\{?\\wedge\}?|\{\\wedge\}|\\wedge", "^", text)  # '2x^{\\wedge}2', 'cm^\\wedge 2'
    text = re.sub(r"\\hspace\*?\{[^{}]*\}|\\vspace\*?\{[^{}]*\}", " ", text)  # spacing, not maths
    text = re.sub(r"\s*\\text\{\s*\([^{}]*\}.*$", "", text)  # a note in brackets at the end: '\\text{ (used 360 ...'
    text = re.sub(r"\s*\\text\{\s*\([^{}]*\)\s*\}\s*$", "", text)
    # A function name is maths, not a word label: '\\text{cbrt}(2744)', '\\text{To find: cbrt}(2744)', '\\text{sqrt}(8)'.
    text = re.sub(
        r"\\(?:text|mathrm|operatorname)\{([^{}]*?)\s*\b(sqrt|cbrt|root)\s*\}",
        lambda match: (f"\\text{{{match.group(1)}}} " if match.group(1).strip() else "") + match.group(2),
        text,
    )
    # '\\text{tan}(45^\\circ)', '\\text{sin } 30': a trig function written as a word is still the function.
    text = re.sub(r"\\(?:text|mathrm|operatorname)\{\s*(sin|cos|tan|cot|sec|cosec|csc)\s*\}", r"\\\1 ", text)
    text = nameAcronyms(text.strip())
    text = stripWordLabels(stripEquationTag(text))
    text = re.sub(r"(?<![-–—])-\s*-(?![-–—])\s*(?=[\d(\\a-zA-Z])", "+ ", text)  # '2 - -4' is 2 + 4 (after equation tags like '-- (1)' are gone)
    text = re.sub(r"\+\s*-\s*(?=[\d(\\a-zA-Z])", "- ", text)  # '5 + -3' is 5 - 3
    text = PLAIN_SUBSCRIPT.sub(r"\1_{\2}", text)
    text = normalizeSymbols(convertPlainMaths(text))
    text = text.replace(r"\left", "").replace(r"\right", "")
    # A mixed number: '1\\frac{3}{10}' or '-1(\\frac{3}{10})' is 1 3/10, never 1 × 3/10 (a proper fraction only).
    text = MIXED_NUMBER.sub(readMixedNumber, text)
    text = text.replace(r"\times", r"\cdot ")
    text = text.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    text = re.sub(r"\\(,|;|!|quad|qquad)", " ", text)
    text = LABEL_PATTERN.sub("", text)
    text = encodeNumberSubscripts(text)
    # Square brackets group like round ones (S = n/2 [2a + (n-1)d]); keep the root index in \sqrt[3]{x}.
    text = re.sub(
        r"\\sqrt\[[^\]]*\]|\[|\]",
        lambda match: match.group(0) if match.group(0).startswith("\\") else "(" if match.group(0) == "[" else ")",
        text,
    )
    text = re.sub(r"\)\s*(?=\d)", r") \\cdot ", text)  # '(n-1)5' means (n-1) × 5
    text = stripUnits(text)
    text = wrapTrigCalls(text)
    # '(1 - cos²A) sec²A', 'cos²A sec²A': a bracket or a trig term next to a trig term multiplies it
    text = re.sub(r"([)}])\s*(?=\{\\(?:sin|cos|tan|cot|sec|csc|cosec)\b)", r"\1 \\cdot ", text)
    text = makePowerProductsExplicit(text)
    # '2 \\cdot 5x' is not read by the parser; '2 \\cdot 5 \\cdot x' means the same.
    text = re.sub(r"\\cdot\s*(\d+(?:\.\d+)?)\s*(?=[a-zA-Z(])(?!cdot)", r"\\cdot \1 \\cdot ", text)
    # 'x(x-2)' would be read as a function call x(...); make the multiplication explicit.
    text = re.sub(r"(?<![\\a-zA-Z])([a-zA-Z])\s*\(", r"\1 \\cdot (", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Students often continue a chain with a leading '=', e.g. '= (x+2)(x+3)'.
    if text.startswith("="):
        text = text[1:].strip()
    return text


TRIG_FUNCTION_PATTERN = re.compile(r"\\(sin|cos|tan|cot|sec|csc|cosec)(?![a-zA-Z])")
POWER_PATTERN = re.compile(r"\s*\^\s*(\{[^{}]*\}|\d)")


def findClosingBracket(text: str, openIndex: int) -> int:
    """Index of the bracket that closes the one at openIndex, or -1."""
    pairs = {"(": ")", "{": "}", "[": "]"}
    opening = text[openIndex]
    depth = 0
    for index in range(openIndex, len(text)):
        if text[index] == opening:
            depth += 1
        elif text[index] == pairs[opening]:
            depth -= 1
            if depth == 0:
                return index
    return -1


def readTrigArgument(text: str, start: int) -> tuple[str, int] | None:
    """Read the argument after \\sin: '(...)', '{...}', '\\theta', 'x', '30' or '\\frac{..}{..}'."""
    index = start
    while index < len(text) and text[index] == " ":
        index += 1
    if index >= len(text):
        return None
    if text[index] in "({":
        closing = findClosingBracket(text, index)
        return (text[index + 1 : closing], closing + 1) if closing != -1 else None
    if text.startswith(r"\frac", index):
        numeratorEnd = findClosingBracket(text, index + 5)
        denominatorEnd = findClosingBracket(text, numeratorEnd + 1) if numeratorEnd != -1 else -1
        return (text[index : denominatorEnd + 1], denominatorEnd + 1) if denominatorEnd != -1 else None
    token = re.match(r"\\[a-zA-Z]+|[a-zA-Z]|\d+(\.\d+)?", text[index:])
    return (token.group(0), index + token.end()) if token else None


def wrapTrigCalls(text: str) -> str:
    """Rewrite '\\sin^{2} x + 1' as '{\\sin^{2}(x)} + 1' so the parser cannot read it as sin(x + 1)."""
    result = ""
    position = 0
    while True:
        match = TRIG_FUNCTION_PATTERN.search(text, position)
        if match is None:
            return result + text[position:]
        name = "csc" if match.group(1) == "cosec" else match.group(1)
        power = POWER_PATTERN.match(text, match.end())
        argumentStart = power.end() if power else match.end()
        argument = readTrigArgument(text, argumentStart)
        if argument is None:
            return result + text[position:]
        argumentText, argumentEnd = argument
        powerText = f"^{{{power.group(1).strip('{}')}}}" if power else ""
        before = text[position : match.start()]
        # '}{' is not valid input for the parser; make the multiplication explicit.
        joiner = " \\cdot " if (result + before).rstrip().endswith("}") else ""
        result += before + joiner + f"{{\\{name}{powerText}({wrapTrigCalls(argumentText)})}}"
        position = argumentEnd


POWER_BEFORE_FACTOR = re.compile(r"(\^\{[^{}]*\}|\^[0-9a-zA-Z])\s*(?=[a-zA-Z(]|\\(?!cdot|times|right|text))")
TRIG_POWER_ENDING = re.compile(r"\\(sin|cos|tan|cot|sec|csc|cosec)\s*$")


def makePowerProductsExplicit(text: str) -> str:
    """'r^2 h' is read badly by the parser, so write it as 'r^2 \\cdot h'.

    A trig power such as '\\sin^{2}(x)' is left alone: there the power belongs to the function.
    """

    def addProduct(match: re.Match[str]) -> str:
        if TRIG_POWER_ENDING.search(text[: match.start()]):
            return match.group(0)
        return match.group(1) + " \\cdot "

    return POWER_BEFORE_FACTOR.sub(addProduct, text)


# ---------- plain typing ----------
# Students type maths the way they say it: 'sqrt(49)', 'x square', 'pi r^2', '12 x 8', '5% of 200'.
# These rules turn that into LaTeX before parsing. No maths keypad needed.

PLAIN_ROOT_BRACKETS = re.compile(r"(?<![\\a-zA-Z])(sqrt|root|√|cbrt|∛)\s*[(\[]")
PLAIN_ROOT_NUMBER = re.compile(r"(?<![\\a-zA-Z])(?:sqrt|root|√)\s*(\d+(?:\.\d+)?|[a-zA-Z])")
PLAIN_POWER_WORDS = (
    (re.compile(r"\s*\b(?:square|squared)\b", re.IGNORECASE), "^{2}"),
    (re.compile(r"\s*\b(?:cube|cubed)\b", re.IGNORECASE), "^{3}"),
)
PLAIN_PI = re.compile(r"(?<![\\a-zA-Z])pi(?![a-zA-Z])", re.IGNORECASE)
# '12 x 8' with spaces on both sides means multiply; 'x' glued to a number ('3x') stays a variable.
PLAIN_TIMES_X = re.compile(r"(\d)\s+[xX]\s+(?=\d)")
PLAIN_PERCENT_OF = re.compile(r"(\d+(?:\.\d+)?)\s*\\?%\s*of\b", re.IGNORECASE)
PLAIN_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*\\?%")
PLAIN_POWER_BRACKETS = re.compile(r"\^\s*\(([^()]*)\)")
PLAIN_POWER_DIGITS = re.compile(r"\^\s*(\d{2,})")


DIGIT_GROUPS = re.compile(r"\b\d{1,3}(?:(?:,\d{3})+|(?:,\d{2})+,\d{3})\b(?!,\d)")  # 34,500,000 or 3,45,00,000 (Indian)
RECURRING_BAR = re.compile(r"(\d*)\.(\d*)\\(?:overline|bar)\{(\d+)\}")  # 0.\overline{36}, 2.1\bar{6}
RECURRING_DOTS = re.compile(r"(\d*)\.(\d+?)(?:\.\.\.|…)")  # 0.363636...


def recurringToFraction(whole: str, fixed: str, repeat: str) -> str:
    """0.1(6 repeating) -> '\\frac{1}{6}': the exact value of a recurring decimal."""
    from fractions import Fraction

    value = (
        Fraction(int(whole or 0))
        + Fraction(int(fixed or 0), 10 ** len(fixed))
        + Fraction(int(repeat), (10 ** len(repeat) - 1) * 10 ** len(fixed))
    )
    return f"\\frac{{{value.numerator}}}{{{value.denominator}}}"


def convertDotsRecurring(match: re.Match[str]) -> str:
    """'0.363636...' -> the shortest block that repeats at least twice at the end is the recurring part."""
    whole, digits = match.group(1), match.group(2)
    for size in range(1, len(digits) // 2 + 1):
        block = digits[-size:]
        if digits.endswith(block * 2):
            start = len(digits) - size
            while start - size >= 0 and digits[start - size : start] == block:
                start -= size
            return recurringToFraction(whole, digits[:start], block)
    return match.group(0)


# Units typed or read without \\text{}: '6 cm', '44/7 cm²', '(...) sq units'. Only after a number or ')', and never a
# single letter (m, g, l can be variables).
PLAIN_UNIT = re.compile(
    r"(?<=[\d)}])(?:\s|\\[,;:! ])*(?:sq\.?\s*)?(?:cm|mm|km|kg|mg|ml|units?|cu\.?\s*units?|sec|hrs?|mins?|years?|days?)\.?"
    r"(?:\s*\^\s*\{?[23]\}?|[²³])?(?![A-Za-z])"
)
PLAIN_GREEK = re.compile(r"(?<![\\A-Za-z])(theta|alpha|beta|gamma)(?![A-Za-z])")


def convertPlainMaths(text: str) -> str:
    """Turn natural typing ('sqrt(x+1)', 'x square', '5% of 200') into LaTeX the parser reads."""
    text = PLAIN_UNIT.sub(" ", text)
    text = PLAIN_GREEK.sub(r"\\\1 ", text)  # 'theta' is θ, not t·h·e·t·a
    text = DIGIT_GROUPS.sub(lambda match: match.group(0).replace(",", ""), text)
    text = RECURRING_BAR.sub(lambda match: recurringToFraction(*match.groups()), text)
    text = RECURRING_DOTS.sub(convertDotsRecurring, text)
    match = PLAIN_ROOT_BRACKETS.search(text)
    while match:
        closeIndex = findClosingBracket(text, match.end() - 1)
        if closeIndex < 0:
            break
        inside = text[match.end() : closeIndex]
        root = r"\sqrt[3]{" if match.group(1) in ("cbrt", "∛") else r"\sqrt{"  # cbrt(2744) is the cube root
        text = text[: match.start()] + root + inside + "}" + text[closeIndex + 1 :]
        match = PLAIN_ROOT_BRACKETS.search(text)
    text = PLAIN_ROOT_NUMBER.sub(r"\\sqrt{\1}", text)
    for pattern, power in PLAIN_POWER_WORDS:
        text = pattern.sub(power, text)
    text = PLAIN_PI.sub(r"\\pi ", text)
    text = PLAIN_TIMES_X.sub(r"\1 \\cdot ", text)
    text = PLAIN_PERCENT_OF.sub(r"\\frac{\1}{100} \\cdot ", text)
    text = PLAIN_PERCENT.sub(r"\\frac{\1}{100}", text)
    text = PLAIN_POWER_BRACKETS.sub(r"^{\1}", text)
    return PLAIN_POWER_DIGITS.sub(r"^{\1}", text)


def stripUnits(text: str) -> str:
    """Remove units, currency and degree signs so '12\\text{ cm}^2' parses as 12."""
    text = UNIT_PATTERN.sub(" ", text)
    text = CURRENCY_PATTERN.sub(" ", text)
    text = DEGREE_PATTERN.sub(r"\\frac{\1 \\pi}{180}" if TRIG_PATTERN.search(text) else r"\1", text)
    return PI_PATTERN.sub(r"\\xi ", text)


def isEmptyLine(latex: str) -> bool:
    """True when a line has no characters worth reading."""
    return normalizeLatex(latex) == ""


def isSkipText(latex: str) -> bool:
    """True when a line is a 'skip' / 'don't know' style answer instead of maths."""
    lowered = normalizeLatex(latex).lower().replace(r"\text", "").strip("{} ?.")
    return lowered == "" or lowered in SKIP_WORDS or set(lowered) <= {"?", " "}


MAX_LINE_CHARACTERS = 400
MAX_TERMS = 80
MAX_EXPONENT = 60
MAX_NUMBER_EXPONENT = 10000
MAX_FACTORIAL = 1000
EXPONENT = re.compile(r"\^\s*(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|(\d+))")


def baseIsNumber(before: str) -> bool:
    """The base of the power that ends just before '^': '(-1)' or '25' -> True, '(x+1)' or 'x' -> False."""
    before = before.rstrip()
    if before.endswith(")") or before.endswith("}"):
        closing, opening = before[-1], "(" if before.endswith(")") else "{"
        depth = 0
        for index in range(len(before) - 1, -1, -1):
            depth += before[index] == closing
            depth -= before[index] == opening
            if depth == 0:
                return not re.search(r"[A-Za-z]", before[index:])
        return False
    return bool(re.search(r"\d$", before))


def isTooHeavy(text: str) -> bool:
    """Lines SymPy could spend minutes on ('2^{2^{2^{100}}}', '(x+1)^{500}', a 3000-term sum). No school answer
    needs them, and one of them must never freeze the server: such a line is simply not checked."""
    if len(text) > MAX_LINE_CHARACTERS or len(re.findall(r"[+\-*/=]", text)) > MAX_TERMS:
        return True
    for match in EXPONENT.finditer(text):
        exponent = match.group(1) or match.group(2)
        if "^" in exponent:
            return True  # a power of a power
        number = re.fullmatch(r"\s*-?(\d+)\s*", exponent)
        # A number's power is cheap ('(-1)^{101}' in Class 7); a power of letters is what SymPy expands for minutes.
        limit = MAX_NUMBER_EXPONENT if baseIsNumber(text[: match.start()]) else MAX_EXPONENT
        if number and int(number.group(1)) > limit:
            return True
    return any(int(value) > MAX_FACTORIAL for value in re.findall(r"(\d+)\s*!", text))


def parseLatex(latex: str) -> sympy.Expr | sympy.Eq:
    """Parse one line of LaTeX into a SymPy expression or equation."""
    if isTooHeavy(latex):
        raise LatexParseError("This line is too large to check.")
    if MISSING_OPERATOR.search(latex):
        # '(x \\text{ } 7)' or 'x 7': the reader lost the sign between them. Guessing it could accuse a right line.
        raise LatexParseError(f"A sign seems to be missing in: {latex}")
    text = normalizeLatex(latex)
    if text == "":
        raise LatexParseError("Line is empty.")
    try:
        if text.count("=") == 1:
            return parseEquation(text)
        return parseExpression(text)
    except LatexParseError:
        raise
    except (TypeError, ValueError, AttributeError, RecursionError, ZeroDivisionError, sympy.SympifyError) as error:
        # Words read as letters can make SymPy itself fail ('Number of outcomes' -> N·u·m·b·e·r...). For every
        # caller (grading, solutions, tutor, visuals) that is simply a line we cannot read, never a crash.
        raise LatexParseError(f"Could not read: {text}") from error


def parseExpression(text: str) -> sympy.Expr | sympy.Eq:
    """Parse LaTeX that has no '=' (or a shape we let the parser handle)."""
    parsed, problem = parseOnce(text)
    if problem:
        raise LatexParseError(problem)
    return parsed


@lru_cache(maxsize=4096)
def parseOnce(text: str) -> tuple[Any, str]:
    """The slow part of reading a line, done once per text: grading reads the same line many times (the step check,
    the final answer, the mistake finder), and the LaTeX parser takes ~40 ms a line, seconds on a small server.
    SymPy expressions never change, so sharing one is safe. Returns (expression, "") or (None, the problem)."""
    try:
        return parseUncached(text), ""
    except LatexParseError as error:
        return None, str(error)
    except (TypeError, ValueError, AttributeError, RecursionError, ZeroDivisionError, sympy.SympifyError):
        return None, f"Could not read: {text}"


def parseUncached(text: str) -> sympy.Expr | sympy.Eq:
    try:
        parsed = parse_latex(text, backend="lark")
    except Exception as error:  # the parser raises many different error types
        raise LatexParseError(f"Could not parse: {text}") from error
    parsed = pickSingleReading(parsed, text)
    if not isinstance(parsed, (sympy.Expr, sympy.Eq)):
        raise LatexParseError(f"Unsupported maths in: {text}")
    parsed = substitute(parsed, {sympy.Symbol(PI_PLACEHOLDER): sympy.pi})
    return decodeNumberSubscripts(parsed)


def substitute(parsed: Any, values: dict[Any, Any]) -> Any:
    """subs() that keeps an equation an equation: Eq(2x, 4).subs(x, 2) would collapse to True, which no
    later step can compare. Raises LatexParseError when the line is not an expression or equation."""
    if not values:
        return parsed
    if isinstance(parsed, sympy.Eq):
        return sympy.Eq(parsed.lhs.subs(values), parsed.rhs.subs(values), evaluate=False)
    if not isinstance(parsed, sympy.Expr):
        raise LatexParseError(f"Not an expression: {parsed}")
    return parsed.subs(values)


# The LaTeX parser reads 'S_{20}' as S_2 × 0. Number subscripts (a₁₀, S₂₀ in progressions) are encoded as
# letters for parsing ('S_{zzca}') and renamed back afterwards, so they stay ordinary named quantities.
SUBSCRIPT_LETTERS = str.maketrans("0123456789", "abcdefghij")
SUBSCRIPT_DIGITS = str.maketrans("abcdefghij", "0123456789")


def encodeNumberSubscripts(text: str) -> str:
    return re.sub(
        r"([A-Za-z])_\{?(\d+)\}?",
        lambda match: f"{match.group(1)}_{{zz{match.group(2).translate(SUBSCRIPT_LETTERS)}}}",
        text,
    )


def decodeNumberSubscripts(parsed: Any) -> Any:
    renames = {}
    for symbol in parsed.free_symbols:
        match = re.fullmatch(r"(.+)_\{zz([a-j]+)\}", str(symbol))
        if match:
            renames[symbol] = sympy.Symbol(f"{match.group(1)}_{{{match.group(2).translate(SUBSCRIPT_DIGITS)}}}")
    return substitute(parsed, renames)


def parseEquation(text: str) -> sympy.Eq:
    """Parse 'left = right' side by side so numeric lines like '6 \\cdot 4 = 24' stay checkable."""
    leftText, rightText = (side.strip() for side in text.split("="))
    if not leftText or not rightText:
        raise LatexParseError(f"Incomplete equation: {text}")
    left = parseExpression(leftText)
    right = parseExpression(rightText)
    if not isinstance(left, sympy.Expr) or not isinstance(right, sympy.Expr):
        raise LatexParseError(f"Unsupported equation: {text}")
    return sympy.Eq(left, right, evaluate=False)


def pickSingleReading(parsed: object, text: str) -> object:
    """The parser may return several readings of one line. Accept it only if they all mean the same."""
    if not isinstance(parsed, Tree):
        return parsed
    readings = [pickSingleReading(child, text) for child in parsed.children]
    first = readings[0]
    for reading in readings[1:]:
        if not isinstance(reading, (sympy.Expr, sympy.Eq)) or not isSameReading(first, reading):
            raise LatexParseError(f"Ambiguous maths in: {text}")
    return first


def isSameReading(first: object, second: sympy.Expr | sympy.Eq) -> bool:
    if first == second:
        return True
    if isinstance(first, sympy.Eq) and isinstance(second, sympy.Eq):
        return bool(sympy.simplify((first.lhs - first.rhs) - (second.lhs - second.rhs)) == 0)
    if isinstance(first, sympy.Expr) and isinstance(second, sympy.Expr):
        return bool(sympy.simplify(first - second) == 0)
    return False


def getFreeSymbols(parsed: sympy.Expr | sympy.Eq) -> set[sympy.Symbol]:
    """Return the variables used in a parsed line."""
    return {symbol for symbol in parsed.free_symbols if isinstance(symbol, sympy.Symbol)}


MATHS_WORDS = {
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "cosec",
    "csc",
    "sqrt",
    "root",
    "pi",
    "square",
    "squared",
    "cube",
    "cubed",
    "of",
    "frac",
    "cdot",
    "times",
    "div",
    "theta",
    "alpha",
    "beta",
    "text",
    "left",
    "right",
    "circ",
}


def hasPlainWords(text: str) -> bool:
    """True when text contains an ordinary word ('Solve', 'likha'), so it is not purely maths.
    Without this, 'Solve x = 2' would be read as S·o·l·v·e·x = 2."""
    for word in re.findall(r"(?<!\\)[A-Za-z]{2,}", text):
        if word.lower() not in MATHS_WORDS:
            return True
    return False
