# Concept visuals built by CODE: every picture, number and board line is computed with SymPy, so a visual is
# correct from the first frame to the last. The AI (or a simple rule) only chooses WHICH template and with
# which numbers; it never draws or calculates.
#
# Output is the same {"title", "frames", "elements"} recipe the frontend already draws (concept-visual.tsx).

import re
from collections.abc import Callable
from typing import Any

import sympy

from app.maths.parser import LatexParseError, getFreeSymbols, parseLatex

Visual = dict[str, Any]


class TemplateError(Exception):
    """The numbers do not fit this template (the caller then shows no picture rather than a wrong one)."""


def tex(value: Any) -> str:
    return str(sympy.latex(sympy.nsimplify(value) if isinstance(value, (int, float)) else value))


def wrapped(value: Any) -> str:
    """A negative number in brackets, so '5 - (-3)' never reads as '5 - -3'."""
    text = tex(value)
    return f"({text})" if text.startswith("-") else text


class Board:
    """Collects frames (one caption each), drawings and board lines."""

    def __init__(self, title: str, language: str, englishTitle: str | None = None) -> None:
        self.title = englishTitle if language == "en" and englishTitle else title
        self.language = language
        self.frames: list[dict[str, str]] = []
        self.elements: list[dict[str, Any]] = []

    def say(self, hinglish: str, english: str) -> int:
        self.frames.append({"caption": english if self.language == "en" else hinglish})
        return len(self.frames) - 1

    def pick(self, hinglish: str, english: str) -> str:
        """A label or board line in the lesson's language."""
        return english if self.language == "en" else hinglish

    def draw(self, frame: int, element: dict[str, Any]) -> None:
        self.elements.append({"frame": frame, "color": "blue", **element})

    def write(self, frame: int, text: str, tone: str = "normal") -> None:
        self.elements.append({"frame": frame, "type": "text", "text": text, "tone": tone, "color": "white"})

    def build(self) -> Visual:
        return {"title": self.title, "frames": self.frames, "elements": self.elements}


def number(value: Any) -> sympy.Expr:
    try:
        parsed = sympy.nsimplify(value) if isinstance(value, (int, float)) else parseLatex(str(value))
    except (LatexParseError, TypeError, ValueError, sympy.SympifyError) as error:
        raise TemplateError(f"not a number: {value}") from error
    if not isinstance(parsed, sympy.Expr) or not parsed.is_number:
        raise TemplateError(f"not a number: {value}")
    return sympy.nsimplify(parsed)


# ---------- 1. division ladder: prime factors, square / cube roots ----------


def divisionLadder(params: dict[str, Any], language: str) -> Visual:
    value = int(number(params["number"]))
    purpose = str(params.get("purpose") or "prime_factors")
    if not 2 <= value <= 100000:
        raise TemplateError("number out of range")
    primes = [prime for prime, power in sorted(sympy.factorint(value).items()) for _ in range(power)]
    if len(primes) > 9:
        raise TemplateError("ladder too long")
    group = 3 if purpose == "cube_root" else 2 if purpose == "square_root" else 1
    board = Board(f"{value} ki division ladder", language, f"Division ladder for {value}")
    start = board.say(
        f"Chalo ${value}$ ke prime factors nikaalte hain — sabse chhote prime se divide karte jaate hain.",
        f"Let's find the prime factors of ${value}$ — keep dividing by the smallest prime.",
    )
    board.write(start, board.pick(f"${value}$ ke prime factors", f"Prime factors of ${value}$"))
    current = value
    perFrame = 1 if len(primes) <= 5 else 2
    frame = start
    for index, prime in enumerate(primes):
        if index % perFrame == 0:
            frame = board.say(
                f"${current}$ ko ${prime}$ se divide karo.", f"Divide ${current}$ by ${prime}$."
            )
        y = 20 + index * 46
        board.draw(frame, {"type": "rect", "x": 180, "y": y, "width": 56, "height": 40, "color": "gold", "label": str(prime)})
        board.draw(frame, {"type": "rect", "x": 240, "y": y, "width": 150, "height": 40, "color": "blue", "label": str(current)})
        board.write(frame, f"${current} \\div {prime} = {current // prime}$")
        current //= prime
    end = board.say("Ab 1 aa gaya — ladder poori hui.", "We reached 1 — the ladder is complete.")
    board.draw(end, {"type": "rect", "x": 240, "y": 20 + len(primes) * 46, "width": 150, "height": 40, "color": "green", "label": "1"})
    product = " \\times ".join(str(prime) for prime in primes)
    board.write(end, f"${value} = {product}$")
    if group == 1:
        powers = " \\times ".join(f"{p}^{{{k}}}" if k > 1 else str(p) for p, k in sorted(sympy.factorint(value).items()))
        last = board.say(f"Toh ${value} = {powers}$.", f"So ${value} = {powers}$.")
        board.write(last, f"${value} = {powers}$", "right")
        return board.build()
    counts = sympy.factorint(value)
    if any(power % group for power in counts.values()):
        name = "perfect cube" if group == 3 else "perfect square"
        last = board.say(
            f"Saare primes ke poore {'triplet' if group == 3 else 'jode'} nahi bante — ${value}$ {name} nahi hai.",
            f"The primes do not all make complete {'triplets' if group == 3 else 'pairs'} — ${value}$ is not a {name}.",
        )
        board.write(last, f"${value}$ is not a {name}", "wrong")
        return board.build()
    groups = [f"({' \\times '.join([str(p)] * group)})" for p, k in sorted(counts.items()) for _ in range(k // group)]
    pairFrame = board.say(
        f"Ab same primes ke {'teen-teen ke group' if group == 3 else 'jode'} banao.",
        f"Now group equal primes in {'threes' if group == 3 else 'pairs'}.",
    )
    for index, text in enumerate(groups):
        board.draw(pairFrame, {"type": "rect", "x": 430, "y": 20 + index * 70, "width": 170, "height": 56, "color": "purple", "label": f"${text}$"})
    board.write(pairFrame, f"${value} = {' \\times '.join(groups)}$")
    picked = [str(p) for p, k in sorted(counts.items()) for _ in range(k // group)]
    root = 1
    for item in picked:
        root *= int(item)
    symbol = "\\sqrt[3]" if group == 3 else "\\sqrt"
    last = board.say(
        f"Har group se ek number bahar aata hai: ${' \\times '.join(picked)} = {root}$.",
        f"One number comes out of each group: ${' \\times '.join(picked)} = {root}$.",
    )
    board.write(last, f"${symbol}{{{value}}} = {' \\times '.join(picked)} = {root}$", "right")
    return board.build()


# ---------- 2. fraction bars ----------


def fractionBars(params: dict[str, Any], language: str) -> Visual:
    pairs = [(int(number(p)), int(number(q))) for p, q in params["fractions"]][:2]
    if len(pairs) != 2 or any(q <= 0 or q > 12 or not 0 <= p <= q for p, q in pairs):
        raise TemplateError("fractions must be proper, denominators up to 12")
    sign = "-" if params.get("op") == "-" else "+"
    (p1, q1), (p2, q2) = pairs
    lcm = int(sympy.ilcm(q1, q2))
    if lcm > 24:
        raise TemplateError("LCM too large to draw")
    first, second = sympy.Rational(p1, q1), sympy.Rational(p2, q2)
    board = Board("Fractions ko jodna", language, "Adding fractions")
    names = (f"\\frac{{{p1}}}{{{q1}}}", f"\\frac{{{p2}}}{{{q2}}}")
    f0 = board.say(
        f"Ye hai ${names[0]}$ aur ${names[1]}$ — dekho, dono ke tukde alag size ke hain.",
        f"Here are ${names[0]}$ and ${names[1]}$ — the pieces are different sizes.",
    )
    board.draw(f0, {"type": "bar", "x": 160, "y": 30, "width": 360, "height": 42, "parts": q1, "filled": p1, "color": "blue", "label": f"${names[0]}$"})
    board.draw(f0, {"type": "bar", "x": 160, "y": 100, "width": 360, "height": 42, "parts": q2, "filled": p2, "color": "gold", "label": f"${names[1]}$"})
    board.write(f0, f"${names[0]} {sign} {names[1]}$")
    wrong = params.get("wrong")
    if wrong and sign == "+":
        wp, wq = int(number(wrong[0])), int(number(wrong[1]))
        wrongValue = sympy.Rational(wp, wq)
        smaller = wrongValue < max(first, second)
        fw = board.say(
            f"Upar-upar aur neeche-neeche jodne se $\\frac{{{wp}}}{{{wq}}}$ aata hai… "
            + ("par ye toh akele " + f"${names[0] if first > second else names[1]}$ se bhi chhota hai! Jodne par chhota kaise?" if smaller else "par ye sahi nahi ho sakta."),
            f"Adding tops and bottoms gives $\\frac{{{wp}}}{{{wq}}}$… "
            + ("but that is smaller than one part alone! Adding cannot make it smaller." if smaller else "but that cannot be right."),
        )
        board.draw(fw, {"type": "bar", "x": 160, "y": 190, "width": 360, "height": 42, "parts": wq, "filled": wp, "color": "red", "label": f"$\\frac{{{wp}}}{{{wq}}}$"})
        board.write(fw, f"${names[0]} + {names[1]} \\neq \\frac{{{wp}}}{{{wq}}}$", "wrong")
    a, b = p1 * (lcm // q1), p2 * (lcm // q2)
    fl = board.say(
        f"Pehle tukde barabar karo: ${q1}$ aur ${q2}$ ka LCM ${lcm}$ hai, toh dono ko ${lcm}$ hisson mein kaato.",
        f"First make the pieces equal: the LCM of ${q1}$ and ${q2}$ is ${lcm}$, so cut both into ${lcm}$ parts.",
    )
    board.draw(fl, {"type": "bar", "x": 160, "y": 30, "width": 360, "height": 42, "parts": lcm, "filled": a, "color": "blue", "label": f"$\\frac{{{a}}}{{{lcm}}}$"})
    board.draw(fl, {"type": "bar", "x": 160, "y": 100, "width": 360, "height": 42, "parts": lcm, "filled": b, "color": "gold", "label": f"$\\frac{{{b}}}{{{lcm}}}$"})
    board.write(fl, f"$\\text{{LCM}}({q1}, {q2}) = {lcm}$")
    board.write(fl, f"${names[0]} = \\frac{{{a}}}{{{lcm}}}, \\quad {names[1]} = \\frac{{{b}}}{{{lcm}}}$")
    top = a + b if sign == "+" else a - b
    result = first + second if sign == "+" else first - second
    fr = board.say(
        f"Ab sirf upar wale jodo: ${a} {sign} {b} = {top}$ — answer ${tex(result)}$.",
        f"Now combine only the tops: ${a} {sign} {b} = {top}$ — the answer is ${tex(result)}$.",
    )
    if 0 <= top <= lcm:
        board.draw(fr, {"type": "bar", "x": 160, "y": 190, "width": 360, "height": 42, "parts": lcm, "filled": top, "color": "green", "label": f"$\\frac{{{top}}}{{{lcm}}}$", "highlight": True})
    simplified = "" if sympy.Rational(top, lcm) == result and sympy.fraction(result)[1] == lcm else f" = {tex(result)}"
    board.write(fr, f"$\\frac{{{a}}}{{{lcm}}} {sign} \\frac{{{b}}}{{{lcm}}} = \\frac{{{top}}}{{{lcm}}}{simplified}$", "right")
    return board.build()


# ---------- 3. balance: linear equation in one variable ----------


def sides(equation: sympy.Eq, variable: sympy.Symbol) -> tuple[sympy.Expr, sympy.Expr, sympy.Expr, sympy.Expr]:
    left, right = sympy.expand(equation.lhs), sympy.expand(equation.rhs)
    try:
        lp, rp = sympy.Poly(left, variable), sympy.Poly(right, variable)
    except sympy.PolynomialError as error:
        raise TemplateError("not linear") from error
    if lp.degree() > 1 or rp.degree() > 1:
        raise TemplateError("not linear")
    return lp.coeff_monomial(variable), lp.coeff_monomial(1), rp.coeff_monomial(variable), rp.coeff_monomial(1)


def balanceEquation(params: dict[str, Any], language: str) -> Visual:
    equation = parseLatex(str(params["equation"]))
    if not isinstance(equation, sympy.Eq) or len(getFreeSymbols(equation)) != 1:
        raise TemplateError("needs one equation in one variable")
    variable = next(iter(getFreeSymbols(equation)))
    a1, b1, a2, b2 = sides(equation, variable)
    if a1 == a2:
        raise TemplateError("no unique solution")
    board = Board("Equation ek taraazu hai", language, "An equation is a balance")
    x = variable

    def show(frame: int, left: sympy.Expr, right: sympy.Expr) -> None:
        board.draw(frame, {"type": "balance", "x": 120, "y": 120, "width": 420, "left": [f"${tex(left)}$"], "right": [f"${tex(right)}$"], "color": "blue"})
        board.write(frame, f"${tex(left)} = {tex(right)}$")

    f = board.say(
        "Equation ek taraazu jaisi hai — dono taraf barabar. Jo ek taraf karoge, wahi doosri taraf bhi.",
        "An equation is like a balance — both sides equal. Whatever you do to one side, do to the other.",
    )
    show(f, equation.lhs, equation.rhs)
    multiplier = sympy.ilcm(*[sympy.fraction(c)[1] for c in (a1, b1, a2, b2)])
    if multiplier != 1:
        a1, b1, a2, b2 = (c * multiplier for c in (a1, b1, a2, b2))
        f = board.say(f"Fractions hataane ke liye dono taraf ${multiplier}$ se guna karo.", f"Multiply both sides by ${multiplier}$ to clear the fractions.")
        show(f, a1 * x + b1, a2 * x + b2)
    if a2 != 0:
        f = board.say(f"Dono taraf se ${tex(a2 * x)}$ hatao — taraazu abhi bhi barabar.", f"Take ${tex(a2 * x)}$ away from both sides — still balanced.")
        a1, a2 = a1 - a2, 0
        show(f, a1 * x + b1, b2)
    if b1 != 0:
        f = board.say(
            f"Ab dono taraf se ${tex(b1)}$ {'hatao' if b1 > 0 else 'ke liye ' + tex(-b1) + ' jodo'}.",
            f"Now {'subtract' if b1 > 0 else 'add'} ${tex(abs(b1))}$ on both sides.",
        )
        b2, b1 = b2 - b1, 0
        show(f, a1 * x, b2)
    value = sympy.nsimplify(b2 / a1)
    if a1 != 1:
        f = board.say(f"Dono taraf ko ${tex(a1)}$ se divide karo.", f"Divide both sides by ${tex(a1)}$.")
    else:
        f = board.say("Bas, x akela reh gaya.", "Done — x is alone.")
    board.draw(f, {"type": "balance", "x": 120, "y": 120, "width": 420, "left": [f"${tex(x)}$"], "right": [f"${tex(value)}$"], "color": "green", "highlight": True})
    board.write(f, f"${tex(x)} = {tex(value)}$", "right")
    return board.build()


# ---------- 4. elimination: a pair of linear equations ----------


def elimination(params: dict[str, Any], language: str) -> Visual:
    equations = [parseLatex(str(item)) for item in params["equations"]][:2]
    if len(equations) != 2 or not all(isinstance(item, sympy.Eq) for item in equations):
        raise TemplateError("needs two equations")
    symbols = sorted(getFreeSymbols(equations[0]) | getFreeSymbols(equations[1]), key=str)
    if len(symbols) != 2:
        raise TemplateError("needs two variables")
    x, y = symbols
    rows = []
    for equation in equations:
        side = sympy.expand(equation.lhs - equation.rhs)
        rows.append((side.coeff(x), side.coeff(y), -side.subs({x: 0, y: 0})))
    (a1, b1, c1), (a2, b2, c2) = rows
    solution = sympy.solve([sympy.Eq(a1 * x + b1 * y, c1), sympy.Eq(a2 * x + b2 * y, c2)], [x, y], dict=True)
    if len(solution) != 1:
        raise TemplateError("no unique solution")
    board = Board("Do equations, ek variable gayab", language, "Two equations, one variable disappears")

    def balance(frame: int, left: sympy.Expr, right: sympy.Expr, color: str = "blue") -> None:
        board.draw(frame, {"type": "balance", "x": 110, "y": 150, "width": 420, "left": [f"${tex(left)}$"], "right": [f"${tex(right)}$"], "color": color})

    f = board.say("Pehla taraazu: pehli equation, dono taraf barabar.", "The first balance: equation (1), both sides equal.")
    balance(f, a1 * x + b1 * y, c1)
    board.write(f, f"${tex(a1 * x + b1 * y)} = {tex(c1)} \\quad (1)$")
    f = board.say("Doosra taraazu: doosri equation.", "The second balance: equation (2).")
    balance(f, a2 * x + b2 * y, c2, "purple")
    board.write(f, f"${tex(a2 * x + b2 * y)} = {tex(c2)} \\quad (2)$")
    k1, k2 = abs(b2), abs(b1)  # make the y-coefficients equal in size
    g = sympy.gcd(k1, k2)
    k1, k2 = k1 // g, k2 // g
    if k1 != 1 or k2 != 1:
        f = board.say(
            f"${tex(y)}$ ke coefficient barabar karne ke liye (1) ko ${k1}$ se aur (2) ko ${k2}$ se guna karo.",
            f"Make the ${tex(y)}$ coefficients equal: multiply (1) by ${k1}$ and (2) by ${k2}$.",
        )
        a1, b1, c1, a2, b2, c2 = a1 * k1, b1 * k1, c1 * k1, a2 * k2, b2 * k2, c2 * k2
        board.write(f, f"${tex(a1 * x + b1 * y)} = {tex(c1)} \\quad (1)$")
        board.write(f, f"${tex(a2 * x + b2 * y)} = {tex(c2)} \\quad (2)$")
    subtract = b1 == b2
    a, c = (a1 - a2, c1 - c2) if subtract else (a1 + a2, c1 + c2)
    f = board.say(
        f"Ab dono ko {'ghatao' if subtract else 'jodo'} — ${tex(y)}$ gayab ho jaata hai!",
        f"Now {'subtract' if subtract else 'add'} them — ${tex(y)}$ disappears!",
    )
    balance(f, a * x, c, "green")
    board.write(f, f"(1) {'-' if subtract else '+'} (2): ${tex(a * x)} = {tex(c)}$")
    xValue, yValue = solution[0][x], solution[0][y]
    f = board.say(
        f"Toh ${tex(x)} = {tex(xValue)}$. Ise (1) mein daalo toh ${tex(y)} = {tex(yValue)}$ milta hai.",
        f"So ${tex(x)} = {tex(xValue)}$. Put it in (1) to get ${tex(y)} = {tex(yValue)}$.",
    )
    board.write(f, f"${tex(x)} = {tex(xValue)}, \\quad {tex(y)} = {tex(yValue)}$", "right")
    return board.build()


# ---------- 5. area model: expand brackets / factorise a quadratic ----------


def areaGrid(board: Board, frame: int, rows: list[sympy.Expr], cols: list[sympy.Expr], fill: bool, highlight: set[int]) -> None:
    widths = [170 if col.free_symbols else 90 for col in cols]
    heights = [110 if row.free_symbols else 60 for row in rows]
    left, top = 120, 50
    x = left
    for column, width in zip(cols, widths, strict=True):
        board.draw(frame, {"type": "arrow", "from": [x + 4, top - 18], "to": [x + width - 4, top - 18], "color": "white", "label": f"${tex(column)}$"})
        x += width
    y = top
    for rowIndex, (row, height) in enumerate(zip(rows, heights, strict=True)):
        board.draw(frame, {"type": "arrow", "from": [left - 22, y + 4], "to": [left - 22, y + height - 4], "color": "white", "label": f"${tex(row)}$"})
        x = left
        for colIndex, (column, width) in enumerate(zip(cols, widths, strict=True)):
            cell = rowIndex * len(cols) + colIndex
            color = "gold" if cell in highlight else "blue"
            board.draw(frame, {"type": "rect", "x": x, "y": y, "width": width, "height": height, "color": color, "label": f"${tex(row * column)}$" if fill else "", "highlight": cell in highlight})
            x += width
        y += height


def areaExpand(params: dict[str, Any], language: str) -> Visual:
    expression = parseLatex(str(params["expression"]))
    if not isinstance(expression, sympy.Expr):
        raise TemplateError("needs an expression")
    factors: list[sympy.Expr] = []
    if isinstance(expression, sympy.Pow) and expression.exp == 2 and isinstance(expression.base, sympy.Add):
        factors = [expression.base, expression.base]
    elif isinstance(expression, sympy.Mul):
        factors = [item for item in expression.args if isinstance(item, sympy.Add)]
    if len(factors) != 2 or any(len(item.args) != 2 for item in factors):
        raise TemplateError("needs (a + b)(c + d) or (a + b)^2")
    rows, cols = list(factors[0].args), list(factors[1].args)
    board = Board("Brackets ko dabbon mein kholo", language, "Open the brackets box by box")
    f = board.say(
        f"${tex(expression)}$ ko ek rectangle socho — lambai ${tex(factors[1])}$, chaudai ${tex(factors[0])}$.",
        f"Think of ${tex(expression)}$ as a rectangle — length ${tex(factors[1])}$, width ${tex(factors[0])}$.",
    )
    areaGrid(board, f, rows, cols, False, set())
    board.write(f, f"${tex(expression)} = ({tex(factors[0])})({tex(factors[1])})$")
    f = board.say("Har dabbe ka area: side ko side se guna.", "The area of each box: side times side.")
    areaGrid(board, f, rows, cols, True, {1, 2})
    cells = [row * col for row in rows for col in cols]
    board.write(f, "$" + " + ".join(tex(cell) for cell in cells) + "$")
    expanded = sympy.expand(expression)
    f = board.say(
        f"Chaaron dabbe jodo — beech ke do dabbe ${tex(cells[1])}$ aur ${tex(cells[2])}$ bhoolna mat!",
        f"Add all four boxes — don't forget the two middle boxes ${tex(cells[1])}$ and ${tex(cells[2])}$!",
    )
    board.write(f, f"${tex(expression)} = {tex(expanded)}$", "right")
    return board.build()


def areaFactor(params: dict[str, Any], language: str) -> Visual:
    parsed = parseLatex(str(params["expression"]))
    expression = parsed.lhs - parsed.rhs if isinstance(parsed, sympy.Eq) else parsed
    symbols = list(getFreeSymbols(parsed))
    if len(symbols) != 1:
        raise TemplateError("one variable needed")
    x = symbols[0]
    poly = sympy.Poly(sympy.expand(expression), x)
    if poly.degree() != 2:
        raise TemplateError("not quadratic")
    a, b, c = (poly.coeff_monomial(x**2), poly.coeff_monomial(x), poly.coeff_monomial(1))
    factors = [item for item, power in sympy.factor_list(sympy.expand(expression))[1] for _ in range(power)]
    if len(factors) != 2:
        raise TemplateError("does not split into two brackets")
    p, q = sympy.Poly(factors[0], x).all_coeffs()
    r, s = sympy.Poly(factors[1], x).all_coeffs()
    constant = sympy.factor_list(sympy.expand(expression))[0]
    if constant != 1:
        raise TemplateError("common number factor")
    board = Board("Middle term ko dabbon se todo", language, "Split the middle term with boxes")
    f = board.say(
        f"${tex(a * x**2)}$ aur ${tex(c)}$ kone ke dabbe hain. Beech ka term ${tex(b * x)}$ do dabbon mein tootega."
        if b != 0
        else f"${tex(a * x**2)}$ aur ${tex(c)}$ kone ke dabbe hain. Beech ka term nahi hai — do dabbe ek-doosre ko cancel karenge.",
        f"${tex(a * x**2)}$ and ${tex(c)}$ are the corner boxes. The middle term ${tex(b * x)}$ splits into two boxes."
        if b != 0
        else f"${tex(a * x**2)}$ and ${tex(c)}$ are the corner boxes. There is no middle term — two boxes cancel out.",
    )
    areaGrid(board, f, [p * x, q], [r * x, s], False, set())
    board.write(f, f"${tex(poly.as_expr())} = 0$")
    board.write(f, f"$a \\times c = {tex(a)} \\times {tex(c)} = {tex(a * c)}$")
    m, n = p * s, q * r
    f = board.say(
        f"Aise do numbers chahiye jinka guna ${tex(a * c)}$ aur jod ${tex(b)}$ ho: ${tex(m)}$ aur ${tex(n)}$.",
        f"We need two numbers with product ${tex(a * c)}$ and sum ${tex(b)}$: ${tex(m)}$ and ${tex(n)}$.",
    )
    board.write(f, f"${tex(m)} \\times {tex(n)} = {tex(m * n)}, \\quad {tex(m)} + {tex(n)} = {tex(m + n)}$")
    areaGrid(board, f, [p * x, q], [r * x, s], True, {1, 2})
    board.write(f, f"${tex(poly.as_expr())} = {tex(a * x**2)} + {tex(m * x)} + {tex(n * x)} + {tex(c)}$".replace("+ -", "- "))
    f = board.say(
        f"Rectangle ki sides hi factors hain: $({tex(factors[0])})({tex(factors[1])})$.",
        f"The sides of the rectangle are the factors: $({tex(factors[0])})({tex(factors[1])})$.",
    )
    board.write(f, f"$({tex(factors[0])})({tex(factors[1])}) = 0$", "right")
    roots = sorted(sympy.solve(expression, x), key=lambda value: float(value))
    if roots:
        board.write(f, "$" + ", \\quad ".join(f"{tex(x)} = {tex(root)}" for root in roots) + "$", "right")
    return board.build()


# ---------- 6. number line: integers ----------


def numberLine(params: dict[str, Any], language: str) -> Visual:
    start = int(number(params["start"]))
    moves = [int(number(item)) for item in params["steps"]][:4]
    positions = [start]
    for move in moves:
        positions.append(positions[-1] + move)
    low, high = min(positions) - 2, max(positions) + 2
    if high - low > 30:
        raise TemplateError("too wide for a number line")
    board = Board("Number line par chalo", language, "Walk along the number line")
    f = board.say(f"${start}$ se shuru karte hain.", f"We start at ${start}$.")
    marks = [{"value": start, "label": f"${start}$", "color": "gold"}]
    board.draw(f, {"type": "numberline", "x": 40, "y": 200, "width": 560, "from": low, "to": high, "step": 1, "marks": marks, "jumps": []})
    board.write(f, f"$\\text{{start}} = {start}$")
    jumps: list[dict[str, Any]] = []
    for index, move in enumerate(moves):
        before, after = positions[index], positions[index + 1]
        direction = ("aage (right)" if move > 0 else "peeche (left)", "right" if move > 0 else "left")
        f = board.say(
            f"${tex(move)}$ matlab ${abs(move)}$ kadam {direction[0]}: ${before} {'+' if move > 0 else '-'} {abs(move)} = {after}$.",
            f"${tex(move)}$ means ${abs(move)}$ steps to the {direction[1]}: ${before} {'+' if move > 0 else '-'} {abs(move)} = {after}$.",
        )
        jumps = [*jumps, {"from": before, "to": after, "label": f"${'+' if move > 0 else ''}{move}$", "color": "green" if move > 0 else "red"}]
        board.draw(f, {"type": "numberline", "x": 40, "y": 200, "width": 560, "from": low, "to": high, "step": 1, "marks": [*marks, {"value": after, "label": f"${after}$", "color": "green"}], "jumps": jumps})
        board.write(f, f"${before} {'+' if move > 0 else '-'} {abs(move)} = {after}$", "right" if index == len(moves) - 1 else "normal")
    return board.build()


# ---------- 7. coordinate geometry ----------


def coordinates(params: dict[str, Any], language: str) -> Visual:
    (x1, y1), (x2, y2) = [(number(px), number(py)) for px, py in params["points"][:2]]
    kind = str(params.get("kind") or "distance")
    xs, ys = [x1, x2, 0], [y1, y2, 0]
    axes = {
        "type": "axes", "x": 60, "y": 10, "width": 380, "height": 330,
        "xmin": int(min(xs)) - 2, "xmax": int(max(xs)) + 2, "ymin": int(min(ys)) - 2, "ymax": int(max(ys)) + 2,
    }
    pointA = {"x": float(x1), "y": float(y1), "label": f"$A({tex(x1)}, {tex(y1)})$", "color": "blue"}
    pointB = {"x": float(x2), "y": float(y2), "label": f"$B({tex(x2)}, {tex(y2)})$", "color": "gold"}
    board = Board("Graph par do points", language, "Two points on a graph")
    f = board.say("Dono points graph par lagate hain.", "Plot both points on the graph.")
    board.draw(f, {**axes, "points": [pointA, pointB], "segments": []})
    board.write(f, f"$A({tex(x1)}, {tex(y1)}), \\quad B({tex(x2)}, {tex(y2)})$")
    if kind == "midpoint":
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        f = board.say("Beech ka point dono x ka average aur dono y ka average hota hai.", "The midpoint is the average of the x's and of the y's.")
        mid = {"x": float(mx), "y": float(my), "label": f"$M({tex(mx)}, {tex(my)})$", "color": "green"}
        board.draw(f, {**axes, "points": [pointA, pointB, mid], "segments": [{"from": [float(x1), float(y1)], "to": [float(x2), float(y2)], "color": "white", "dashed": True}]})
        board.write(f, f"$M = \\left(\\frac{{{tex(x1)} + {tex(x2)}}}{{2}}, \\frac{{{tex(y1)} + {tex(y2)}}}{{2}}\\right) = ({tex(mx)}, {tex(my)})$", "right")
        return board.build()
    dx, dy = x2 - x1, y2 - y1
    corner = [float(x2), float(y1)]
    f = board.say(
        f"Ek right triangle banao: aadi doori ${tex(abs(dx))}$ aur khadi doori ${tex(abs(dy))}$.",
        f"Make a right triangle: across ${tex(abs(dx))}$ and up/down ${tex(abs(dy))}$.",
    )
    legs = [
        {"from": [float(x1), float(y1)], "to": corner, "color": "green", "label": f"${tex(abs(dx))}$"},
        {"from": corner, "to": [float(x2), float(y2)], "color": "purple", "label": f"${tex(abs(dy))}$"},
    ]
    board.draw(f, {**axes, "points": [pointA, pointB], "segments": legs})
    board.write(f, f"$x_2 - x_1 = {tex(x2)} - {wrapped(x1)} = {tex(dx)}$")
    board.write(f, f"$y_2 - y_1 = {tex(y2)} - {wrapped(y1)} = {tex(dy)}$")
    distance = sympy.sqrt(dx**2 + dy**2)
    f = board.say(
        f"Pythagoras se: doori $= \\sqrt{{{tex(dx**2)} + {tex(dy**2)}}} = {tex(distance)}$.",
        f"By Pythagoras: distance $= \\sqrt{{{tex(dx**2)} + {tex(dy**2)}}} = {tex(distance)}$.",
    )
    hyp = {"from": [float(x1), float(y1)], "to": [float(x2), float(y2)], "color": "gold", "label": f"${tex(distance)}$"}
    board.draw(f, {**axes, "points": [pointA, pointB], "segments": [*legs, hyp], "highlight": True})
    board.write(f, f"$AB = \\sqrt{{({tex(dx)})^2 + ({tex(dy)})^2}} = \\sqrt{{{tex(dx**2 + dy**2)}}} = {tex(distance)}$", "right")
    return board.build()


# ---------- 8. shapes to scale: mensuration ----------


def shapes(params: dict[str, Any], language: str) -> Visual:
    shape = str(params.get("shape"))
    quantity = str(params.get("quantity") or "area")
    unit = str(params.get("unit") or "")
    u = f"\\text{{ {unit}}}" if unit else ""
    board = Board("Shape ko naap ke dekho", language, "Measure the shape")
    if shape in ("rectangle", "square"):
        length = number(params["length"] if shape == "rectangle" else params["side"])
        breadth = number(params["breadth"]) if shape == "rectangle" else length
        scale = min(360 / float(length), 220 / float(breadth))
        width, height = float(length) * scale, float(breadth) * scale
        f = board.say(f"Ye {shape} hai: ${tex(length)}{u}$ lamba aur ${tex(breadth)}{u}$ chauda.", f"This {shape} is ${tex(length)}{u}$ long and ${tex(breadth)}{u}$ wide.")
        board.draw(f, {"type": "rect", "x": 140, "y": 60, "width": width, "height": height, "color": "blue", "label": ""})
        board.draw(f, {"type": "arrow", "from": [140, 40], "to": [140 + width, 40], "color": "white", "label": f"${tex(length)}$"})
        board.draw(f, {"type": "arrow", "from": [120, 60], "to": [120, 60 + height], "color": "white", "label": f"${tex(breadth)}$"})
        board.write(f, f"$l = {tex(length)}, \\quad b = {tex(breadth)}$")
        if quantity == "perimeter":
            value = 2 * (length + breadth)
            f = board.say("Perimeter matlab chaaron taraf ki poori lambai.", "Perimeter is the total length all the way round.")
            board.write(f, f"$P = 2(l + b) = 2({tex(length)} + {tex(breadth)}) = {tex(value)}{u}$", "right")
            return board.build()
        value = length * breadth
        f = board.say(f"Area matlab kitne unit square isme aate hain: ${tex(length)} \\times {tex(breadth)}$.", f"Area is how many unit squares fit inside: ${tex(length)} \\times {tex(breadth)}$.")
        if length.is_integer and breadth.is_integer and length * breadth <= 300:
            cell = min(width / float(length), height / float(breadth))
            board.draw(f, {"type": "grid", "x": 140, "y": 60, "rows": int(breadth), "cols": int(length), "cell": cell, "filled": int(length * breadth), "color": "blue"})
        board.write(f, f"$A = l \\times b = {tex(length)} \\times {tex(breadth)} = {tex(value)}{u}^2$" if unit else f"$A = {tex(length)} \\times {tex(breadth)} = {tex(value)}$", "right")
        return board.build()
    if shape == "triangle":
        base, height = number(params["base"]), number(params["height"])
        scale = min(360 / float(base), 220 / float(height))
        w, h = float(base) * scale, float(height) * scale
        f = board.say(f"Triangle: base ${tex(base)}$, height ${tex(height)}$.", f"Triangle: base ${tex(base)}$, height ${tex(height)}$.")
        board.draw(f, {"type": "polygon", "points": [[140, 60 + h], [140 + w, 60 + h], [140 + w * 0.35, 60]], "color": "blue", "labels": [{"x": 140 + w / 2, "y": 60 + h + 22, "text": f"${tex(base)}$"}]})
        board.draw(f, {"type": "arrow", "from": [140 + w * 0.35, 60], "to": [140 + w * 0.35, 60 + h], "color": "gold", "label": f"${tex(height)}$"})
        f2 = board.say("Triangle apne rectangle ka aadha hota hai, isliye half lagta hai.", "A triangle is half of its rectangle — that is why we take half.")
        board.draw(f2, {"type": "rect", "x": 140, "y": 60, "width": w, "height": h, "color": "gray", "label": ""})
        value = base * height / 2
        board.write(f2, f"$A = \\frac{{1}}{{2}} \\times {tex(base)} \\times {tex(height)} = {tex(value)}{u}{'^2' if unit else ''}$", "right")
        return board.build()
    if shape == "circle":
        radius = number(params["radius"])
        pi = sympy.Rational(22, 7) if (radius % 7 == 0) else sympy.pi
        f = board.say(f"Circle, radius ${tex(radius)}$.", f"A circle with radius ${tex(radius)}$.")
        board.draw(f, {"type": "circle", "cx": 320, "cy": 180, "r": 120, "color": "blue", "label": ""})
        board.draw(f, {"type": "arrow", "from": [320, 180], "to": [440, 180], "color": "gold", "label": f"$r = {tex(radius)}$"})
        if quantity in ("circumference", "perimeter"):
            value = 2 * pi * radius
            f = board.say("Circumference matlab circle ke charon taraf ki lambai.", "Circumference is the length all the way round.")
            board.write(f, f"$C = 2\\pi r = 2 \\times {tex(pi)} \\times {tex(radius)} = {tex(value)}{u}$", "right")
        else:
            value = pi * radius**2
            f = board.say("Area $= \\pi r^2$.", "Area $= \\pi r^2$.")
            board.write(f, f"$A = \\pi r^2 = {tex(pi)} \\times {tex(radius)}^2 = {tex(value)}{u}{'^2' if unit else ''}$", "right")
        return board.build()
    raise TemplateError("unknown shape")


# ---------- 9. AP staircase ----------


def apStairs(params: dict[str, Any], language: str) -> Visual:
    first, difference, count = number(params["first"]), number(params["difference"]), int(number(params["n"]))
    ask = str(params.get("ask") or "nth_term")
    shown = min(count, 7)
    terms = [first + index * difference for index in range(shown)]
    if any(term <= 0 for term in terms):
        raise TemplateError("staircase needs positive terms")
    tallest = float(max(terms))
    board = Board("AP ek seedhi hai", language, "An AP is a ladder")
    f = board.say(
        f"AP ek seedhi jaisi hai: pehli seedhi ${tex(first)}$, aur har baar ${tex(difference)}$ upar.",
        f"An AP is like a staircase: the first step is ${tex(first)}$, and each step goes up by ${tex(difference)}$.",
    )
    for index, term in enumerate(terms):
        height = 40 + 220 * float(term) / tallest
        board.draw(f, {"type": "rect", "x": 80 + index * 70, "y": 300 - height, "width": 60, "height": height, "color": "gold" if index == 0 else "blue", "label": f"${tex(term)}$"})
    board.write(f, f"$a = {tex(first)}, \\quad d = {tex(difference)}$")
    last = first + (count - 1) * difference
    f = board.say(f"${count}$-vi seedhi tak ${count - 1}$ baar ${tex(difference)}$ judta hai.", f"To reach step ${count}$ we add ${tex(difference)}$ exactly ${count - 1}$ times.")
    board.write(f, f"$a_{{{count}}} = a + ({count} - 1)d = {tex(first)} + {count - 1} \\times {tex(difference)} = {tex(last)}$", "right" if ask == "nth_term" else "normal")
    if ask == "sum":
        total = sympy.Rational(count, 2) * (first + last)
        f = board.say("Sum: pehli aur aakhri seedhi ka jod, ${n}/2$ baar.".replace("{n}", str(count)), f"Sum: first plus last, taken ${count}/2$ times.")
        board.write(f, f"$S_{{{count}}} = \\frac{{{count}}}{{2}}({tex(first)} + {tex(last)}) = {tex(total)}$", "right")
    return board.build()


# ---------- 10. percent on a 10 x 10 grid ----------


def percentGrid(params: dict[str, Any], language: str) -> Visual:
    percent = number(params["percent"])
    if not (0 < percent <= 100 and percent.is_integer):
        raise TemplateError("whole percent up to 100")
    board = Board("Percent matlab 100 mein se", language, "Percent means out of 100")
    f = board.say(f"${tex(percent)}\\%$ matlab 100 dabbon mein se ${tex(percent)}$ dabbe.", f"${tex(percent)}\\%$ means ${tex(percent)}$ boxes out of 100.")
    board.draw(f, {"type": "grid", "x": 170, "y": 20, "rows": 10, "cols": 10, "cell": 30, "filled": int(percent), "color": "gold"})
    board.write(f, f"${tex(percent)}\\% = \\frac{{{tex(percent)}}}{{100}}$")
    if params.get("of") is not None:
        whole = number(params["of"])
        value = percent * whole / 100
        f = board.say(f"Ab ${tex(whole)}$ ka ${tex(percent)}\\%$: ${tex(whole)}$ ko 100 hisson mein baanto aur ${tex(percent)}$ hisse lo.", f"Now ${tex(percent)}\\%$ of ${tex(whole)}$.")
        board.write(f, f"$\\frac{{{tex(percent)}}}{{100}} \\times {tex(whole)} = {tex(value)}$", "right")
    return board.build()


# ---------- 11. quadratic formula ----------


def quadraticParts(text: str) -> tuple[sympy.Symbol, sympy.Expr, sympy.Expr, sympy.Expr]:
    parsed = parseLatex(text)
    expression = parsed.lhs - parsed.rhs if isinstance(parsed, sympy.Eq) else parsed
    symbols = list(getFreeSymbols(parsed))
    if len(symbols) != 1:
        raise TemplateError("one variable needed")
    variable = symbols[0]
    poly = sympy.Poly(sympy.expand(expression), variable)
    if poly.degree() != 2:
        raise TemplateError("not quadratic")
    return variable, poly.coeff_monomial(variable**2), poly.coeff_monomial(variable), poly.coeff_monomial(1)


def quadraticFormula(params: dict[str, Any], language: str) -> Visual:
    x, a, b, c = quadraticParts(str(params["expression"]))
    discriminant = b**2 - 4 * a * c
    if discriminant < 0:
        raise TemplateError("no real roots")
    rootD = sympy.sqrt(discriminant)
    minusB = -b
    board = Board("Quadratic formula, ek-ek step", language, "The quadratic formula, step by step")

    f = board.say(
        f"Sabse pehle $a$, $b$, $c$ pehchaano: $a = {tex(a)}$, $b = {tex(b)}$, $c = {tex(c)}$ — sign ke saath!",
        f"First read $a$, $b$, $c$ with their signs: $a = {tex(a)}$, $b = {tex(b)}$, $c = {tex(c)}$.",
    )
    board.draw(f, {"type": "rect", "x": 100, "y": 80, "width": 130, "height": 60, "color": "blue", "label": f"$a = {tex(a)}$"})
    board.draw(f, {"type": "rect", "x": 255, "y": 80, "width": 130, "height": 60, "color": "purple", "label": f"$b = {tex(b)}$"})
    board.draw(f, {"type": "rect", "x": 410, "y": 80, "width": 130, "height": 60, "color": "gold", "label": f"$c = {tex(c)}$"})
    board.write(f, f"$a = {tex(a)}, \\quad b = {tex(b)}, \\quad c = {tex(c)}$")
    board.write(f, f"${tex(x)} = \\frac{{-b \\pm \\sqrt{{b^2 - 4ac}}}}{{2a}}$")

    f = board.say(
        f"Ab root ke andar wala hissa: $b^2 - 4ac = {tex(discriminant)}$, aur $\\sqrt{{{tex(discriminant)}}} = {tex(rootD)}$.",
        f"Now the part under the root: $b^2 - 4ac = {tex(discriminant)}$, and $\\sqrt{{{tex(discriminant)}}} = {tex(rootD)}$.",
    )
    board.draw(f, {"type": "rect", "x": 170, "y": 70, "width": 300, "height": 60, "color": "gold", "label": f"$b^2 - 4ac = {tex(discriminant)}$"})
    board.draw(f, {"type": "arrow", "from": [320, 140], "to": [320, 196], "color": "green", "label": ""})
    board.draw(f, {"type": "rect", "x": 230, "y": 206, "width": 180, "height": 56, "color": "green", "label": f"$\\sqrt{{{tex(discriminant)}}} = {tex(rootD)}$"})
    board.write(f, f"$b^2 - 4ac = {wrapped(b)}^2 - 4 \\times {wrapped(a)} \\times {wrapped(c)} = {tex(discriminant)}$")
    board.write(f, f"$\\sqrt{{{tex(discriminant)}}} = {tex(rootD)}$")

    if b < 0:
        f = board.say(
            f"Ab dhyan se: formula $-b$ se shuru hota hai. $b = {tex(b)}$ hai, toh $-b = -({tex(b)}) = {tex(minusB)}$ — minus aur minus milke plus!",
            f"Careful: the formula starts with $-b$. Here $b = {tex(b)}$, so $-b = -({tex(b)}) = {tex(minusB)}$ — two minuses make a plus!",
        )
        board.draw(f, {"type": "rect", "x": 120, "y": 90, "width": 170, "height": 60, "color": "red", "label": f"$-b \\neq {tex(b)}$"})
        board.draw(f, {"type": "rect", "x": 350, "y": 90, "width": 170, "height": 60, "color": "green", "label": f"$-b = {tex(minusB)}$"})
        board.write(f, f"$-b = -({tex(b)}) = {tex(minusB)}$", "right")
    else:
        f = board.say(f"Formula $-b$ se shuru hota hai: $-b = {tex(minusB)}$.", f"The formula starts with $-b$: $-b = {tex(minusB)}$.")
        board.draw(f, {"type": "rect", "x": 230, "y": 90, "width": 180, "height": 60, "color": "blue", "label": f"$-b = {tex(minusB)}$"})
        board.write(f, f"$-b = {tex(minusB)}$")

    plus = sympy.nsimplify((minusB + rootD) / (2 * a))
    minus = sympy.nsimplify((minusB - rootD) / (2 * a))
    f = board.say(
        f"$\\pm$ ka matlab do raaste: ek baar plus, ek baar minus — aur poore upar wale ko $2a = {tex(2 * a)}$ se divide karo.",
        f"$\\pm$ means two paths: once plus, once minus — and divide the whole top by $2a = {tex(2 * a)}$.",
    )
    board.draw(f, {"type": "rect", "x": 220, "y": 30, "width": 200, "height": 56, "color": "gold", "label": f"$\\frac{{{tex(minusB)} \\pm {tex(rootD)}}}{{{tex(2 * a)}}}$"})
    board.draw(f, {"type": "arrow", "from": [270, 96], "to": [180, 170], "color": "blue", "label": "$+$"})
    board.draw(f, {"type": "arrow", "from": [370, 96], "to": [460, 170], "color": "purple", "label": "$-$"})
    board.draw(f, {"type": "rect", "x": 90, "y": 180, "width": 180, "height": 60, "color": "green", "label": f"${tex(x)} = {tex(plus)}$"})
    board.draw(f, {"type": "rect", "x": 370, "y": 180, "width": 180, "height": 60, "color": "green", "label": f"${tex(x)} = {tex(minus)}$"})
    board.write(f, f"${tex(x)} = \\frac{{{tex(minusB)} + {tex(rootD)}}}{{{tex(2 * a)}}} = {tex(plus)}$", "right")
    board.write(f, f"${tex(x)} = \\frac{{{tex(minusB)} - {tex(rootD)}}}{{{tex(2 * a)}}} = {tex(minus)}$", "right")
    return board.build()


# ---------- 12. cross multiplication: a/b = c/d ----------


def isOneFraction(text: str) -> bool:
    """'\\frac{x + 1}{3}' or '(x + 1)/3' — not 'x/2 + x/3' (that is the balance template's job)."""
    text = text.strip()
    depth, topLevel = 0, []
    for char in text:
        depth += char in "({"
        depth -= char in ")}"
        if depth == 0:
            topLevel.append(char)
    outside = "".join(topLevel)
    if text.startswith("\\frac"):
        return text.count("\\frac") == 1 and text.endswith("}") and not any(sign in outside[1:] for sign in "+-")
    return outside.count("/") == 1 and not any(sign in outside[1:] for sign in "+-")


def crossMultiplication(params: dict[str, Any], language: str) -> Visual:
    text = str(params["equation"])
    equation = parseLatex(text)
    if not isinstance(equation, sympy.Eq) or len(getFreeSymbols(equation)) != 1:
        raise TemplateError("needs one equation in one variable")
    x = next(iter(getFreeSymbols(equation)))
    if text.count("=") != 1 or not all(isOneFraction(side) for side in text.split("=")):
        raise TemplateError("each side must be one fraction")
    top1, bottom1 = sympy.fraction(sympy.together(equation.lhs))
    top2, bottom2 = sympy.fraction(sympy.together(equation.rhs))
    if bottom1 == 1 or bottom2 == 1:
        raise TemplateError("both sides need a denominator")
    left, right = sympy.expand(bottom2 * top1), sympy.expand(bottom1 * top2)
    solutions = sympy.solve(sympy.Eq(left, right), x)
    if len(solutions) != 1:
        raise TemplateError("no unique solution")
    answer = solutions[0]
    first, second = f"\\frac{{{tex(top1)}}}{{{tex(bottom1)}}}", f"\\frac{{{tex(top2)}}}{{{tex(bottom2)}}}"

    board = Board("Cross-multiplication", language)
    f = board.say(
        f"Dono taraf ek-ek fraction hai: ${first} = {second}$. Neeche wale ko tirchha upar le jaate hain.",
        f"One fraction on each side: ${first} = {second}$. Each bottom moves across, diagonally.",
    )
    board.draw(f, {"type": "rect", "x": 140, "y": 90, "width": 150, "height": 90, "color": "blue", "label": f"${first}$"})
    board.draw(f, {"type": "rect", "x": 350, "y": 90, "width": 150, "height": 90, "color": "gold", "label": f"${second}$"})
    board.draw(f, {"type": "arrow", "from": [250, 170], "to": [390, 100], "color": "green", "label": ""})
    board.draw(f, {"type": "arrow", "from": [390, 170], "to": [250, 100], "color": "purple", "label": ""})
    board.write(f, f"${first} = {second}$")

    f = board.say(
        f"Toh ${tex(bottom2)}$ guna ${tex(top1)}$ barabar ${tex(bottom1)}$ guna ${tex(top2)}$.",
        f"So ${tex(bottom2)}$ times ${tex(top1)}$ equals ${tex(bottom1)}$ times ${tex(top2)}$.",
    )
    board.draw(f, {"type": "balance", "x": 110, "y": 120, "width": 420, "left": [f"${tex(bottom2)}({tex(top1)})$"], "right": [f"${tex(bottom1)}({tex(top2)})$"], "color": "blue"})
    board.write(f, f"${tex(bottom2)}({tex(top1)}) = {tex(bottom1)}({tex(top2)})$")

    f = board.say(
        f"Bracket kholo: ${tex(left)} = {tex(right)}$. Solve karo toh ${tex(x)} = {tex(answer)}$.",
        f"Open the brackets: ${tex(left)} = {tex(right)}$. Solving gives ${tex(x)} = {tex(answer)}$.",
    )
    board.draw(f, {"type": "balance", "x": 110, "y": 120, "width": 420, "left": [f"${tex(x)}$"], "right": [f"${tex(answer)}$"], "color": "green", "highlight": True})
    board.write(f, f"${tex(left)} = {tex(right)}$")
    board.write(f, f"${tex(x)} = {tex(answer)}$", "right")
    return board.build()


# ---------- 13. angle sum: triangle, quadrilateral, straight line, full turn ----------

ANGLE_TOTALS = {"triangle": 180, "quadrilateral": 360, "straight_line": 180, "full_turn": 360}


def angleSum(params: dict[str, Any], language: str) -> Visual:
    figure = str(params.get("figure") or "triangle")
    total = ANGLE_TOTALS.get(figure)
    known = [number(item) for item in params["known"]][:5]
    if total is None or not known or any(angle <= 0 for angle in known) or sum(known) >= total:
        raise TemplateError("angles do not fit")
    missing = total - sum(known)
    names = {"triangle": ("triangle", "triangle"), "quadrilateral": ("quadrilateral", "quadrilateral"),
             "straight_line": ("seedhi line", "straight line"), "full_turn": ("poora chakkar", "full turn")}[figure]
    board = Board(f"Angles ka jod {total}°", language, f"The angles add up to {total}°")
    width = 520 / total
    colors = ["blue", "purple", "green", "red", "gray"]

    def strip(frame: int, withMissing: bool) -> None:
        x = 60.0
        for index, angle in enumerate(known):
            board.draw(frame, {"type": "rect", "x": x, "y": 150, "width": float(angle) * width, "height": 64, "color": colors[index], "label": f"${tex(angle)}^\\circ$"})
            x += float(angle) * width
        board.draw(frame, {"type": "rect", "x": x, "y": 150, "width": float(missing) * width, "height": 64, "color": "gold", "label": f"${tex(missing)}^\\circ$" if withMissing else "?", "highlight": withMissing})

    f = board.say(
        f"Ek {names[0]} ke saare angles milkar hamesha ${total}^\\circ$ banate hain — ye poori patti ${total}^\\circ$ hai.",
        f"All the angles of a {names[1]} always add up to ${total}^\\circ$ — this whole strip is ${total}^\\circ$.",
    )
    board.draw(f, {"type": "arrow", "from": [60, 120], "to": [580, 120], "color": "white", "label": f"${total}^\\circ$"})
    strip(f, False)
    board.write(f, "$" + " + ".join(f"{tex(angle)}^\\circ" for angle in known) + f" + ? = {total}^\\circ$")
    f = board.say(
        f"Jo pata hai unhe jodo: ${' + '.join(tex(angle) for angle in known)} = {tex(sum(known))}$.",
        f"Add the angles we know: ${' + '.join(tex(angle) for angle in known)} = {tex(sum(known))}$.",
    )
    board.write(f, f"${' + '.join(tex(angle) for angle in known)} = {tex(sum(known))}$")
    f = board.say(
        f"Bacha hua hissa: ${total} - {tex(sum(known))} = {tex(missing)}$ — yahi hamara angle hai.",
        f"The part left over: ${total} - {tex(sum(known))} = {tex(missing)}$ — that is our angle.",
    )
    strip(f, True)
    board.write(f, f"$? = {total}^\\circ - {tex(sum(known))}^\\circ = {tex(missing)}^\\circ$", "right")
    return board.build()


# ---------- 14. mean: level the bars ----------


def meanBars(params: dict[str, Any], language: str) -> Visual:
    values = [number(item) for item in params["values"]][:8]
    if len(values) < 2 or any(value <= 0 for value in values):
        raise TemplateError("needs positive values")
    total, count = sum(values), len(values)
    mean = sympy.nsimplify(total / count)
    tallest = float(max(values))
    gap = 520 / count

    def height(value: Any) -> float:
        return 230 * float(value) / tallest

    board = Board("Mean matlab sabko barabar karna", language, "Mean means sharing equally")
    f = board.say(
        "Har number ko ek khamba socho — kuch lambe, kuch chhote.",
        "Think of each number as a bar — some tall, some short.",
    )
    for index, value in enumerate(values):
        board.draw(f, {"type": "rect", "x": 60 + index * gap, "y": 290 - height(value), "width": gap * 0.7, "height": height(value), "color": "blue", "label": f"${tex(value)}$"})
    board.write(f, "$" + ", ".join(tex(value) for value in values) + "$")
    f = board.say(
        f"Sab jodo: ${' + '.join(tex(value) for value in values)} = {tex(total)}$.",
        f"Add them all: ${' + '.join(tex(value) for value in values)} = {tex(total)}$.",
    )
    board.write(f, f"${' + '.join(tex(value) for value in values)} = {tex(total)}$")
    f = board.say(
        f"Ab ye total ${count}$ khambon mein barabar baanto: ${tex(total)} \\div {count} = {tex(mean)}$. Sab khambe ek hi height ke!",
        f"Now share the total equally among ${count}$ bars: ${tex(total)} \\div {count} = {tex(mean)}$. All bars the same height!",
    )
    for index in range(count):
        board.draw(f, {"type": "rect", "x": 60 + index * gap, "y": 290 - height(mean), "width": gap * 0.7, "height": height(mean), "color": "green", "label": f"${tex(mean)}$"})
    board.write(f, f"$\\text{{Mean}} = \\frac{{{tex(total)}}}{{{count}}} = {tex(mean)}$", "right")
    return board.build()


# ---------- 15. proportion: unitary method (direct) and work = workers x days (inverse) ----------


def proportion(params: dict[str, Any], language: str) -> Visual:
    kind = str(params.get("kind") or "direct")
    count, amount, newCount = number(params["count"]), number(params["amount"]), number(params["new_count"])
    if min(count, amount, newCount) <= 0:
        raise TemplateError("positive numbers needed")
    item = str(params.get("item") or "")
    if kind == "inverse":
        work = count * amount
        answer = sympy.nsimplify(work / newCount)
        board = Board("Kaam = log x din", language, "Work = people × days")
        f = board.say(
            f"Poora kaam ek rectangle hai: ${tex(count)}$ log, ${tex(amount)}$ din — har dabba ek aadmi ka ek din.",
            f"The whole job is a rectangle: ${tex(count)}$ people for ${tex(amount)}$ days — each box is one person-day.",
        )
        if work <= 400 and count.is_integer and amount.is_integer:
            board.draw(f, {"type": "grid", "x": 60, "y": 40, "rows": int(count), "cols": int(amount), "cell": min(26, 520 / float(amount), 280 / float(count)), "filled": int(work), "color": "blue"})
        board.write(f, f"$\\text{{work}} = {tex(count)} \\times {tex(amount)} = {tex(work)}$")
        f = board.say(
            f"Kaam utna hi hai — ${tex(work)}$ dabbe. Ab sirf ${tex(newCount)}$ log hain, toh rectangle lamba ho jaayega.",
            f"The job is the same — ${tex(work)}$ boxes. With only ${tex(newCount)}$ people the rectangle gets longer.",
        )
        if work <= 400 and newCount.is_integer and answer.is_integer:
            board.draw(f, {"type": "grid", "x": 60, "y": 40, "rows": int(newCount), "cols": int(answer), "cell": min(26, 520 / float(answer), 280 / float(newCount)), "filled": int(work), "color": "gold", "highlight": True})
        board.write(f, f"$\\text{{days}} = {tex(work)} \\div {tex(newCount)} = {tex(answer)}$", "right")
        return board.build()
    unit = sympy.nsimplify(amount / count)
    answer = sympy.nsimplify(unit * newCount)
    board = Board("Pehle ek ka, phir sabka", language, "First for one, then for all")
    f = board.say(
        f"${tex(count)}$ {item} ka ${tex(amount)}$ hai.",
        f"${tex(count)}$ {item} cost ${tex(amount)}$.",
    )
    if count.is_integer and count <= 12:
        board.draw(f, {"type": "bar", "x": 120, "y": 60, "width": 400, "height": 44, "parts": int(count), "filled": int(count), "color": "blue", "label": f"${tex(count)} \\to {tex(amount)}$"})
    board.write(f, f"${tex(count)} \\to {tex(amount)}$")
    f = board.say(
        f"Ek ka nikaalo: ${tex(amount)} \\div {tex(count)} = {tex(unit)}$.",
        f"Find one first: ${tex(amount)} \\div {tex(count)} = {tex(unit)}$.",
    )
    if count.is_integer and count <= 12:
        board.draw(f, {"type": "bar", "x": 120, "y": 150, "width": 400 / float(count), "height": 44, "parts": 1, "filled": 1, "color": "gold", "label": f"$1 \\to {tex(unit)}$"})
    board.write(f, f"$1 \\to {tex(amount)} \\div {tex(count)} = {tex(unit)}$")
    f = board.say(
        f"Ab ${tex(newCount)}$ ka: ${tex(unit)} \\times {tex(newCount)} = {tex(answer)}$.",
        f"Now for ${tex(newCount)}$: ${tex(unit)} \\times {tex(newCount)} = {tex(answer)}$.",
    )
    if newCount.is_integer and newCount <= 12 and count.is_integer and count <= 12:
        board.draw(f, {"type": "bar", "x": 120, "y": 240, "width": min(500, 400 / float(count) * float(newCount)), "height": 44, "parts": int(newCount), "filled": int(newCount), "color": "green", "label": f"${tex(newCount)} \\to {tex(answer)}$"})
    board.write(f, f"${tex(newCount)} \\to {tex(unit)} \\times {tex(newCount)} = {tex(answer)}$", "right")
    return board.build()


# ---------- 16. probability: favourable boxes out of all outcomes ----------


def probabilityGrid(params: dict[str, Any], language: str) -> Visual:
    total, favourable = number(params["total"]), number(params["favourable"])
    if not (total.is_integer and favourable.is_integer and 0 <= favourable <= total <= 400 and total > 0):
        raise TemplateError("whole counts up to 400")
    columns = 13 if total == 52 else 10 if total % 10 == 0 else min(int(total), 12)
    rows = -(-int(total) // columns)
    probability = sympy.Rational(int(favourable), int(total))
    board = Board("Kitne mein se kitne", language, "How many out of how many")
    f = board.say(f"Kul ${tex(total)}$ possible outcomes — har ek ek dabba.", f"There are ${tex(total)}$ possible outcomes — one box each.")
    cell = min(30, 520 / columns, 300 / rows)
    board.draw(f, {"type": "grid", "x": 60, "y": 30, "rows": rows, "cols": columns, "cell": cell, "filled": 0, "color": "gold"})
    board.write(f, f"$\\text{{total}} = {tex(total)}$")
    f = board.say(f"Inme se ${tex(favourable)}$ hamare kaam ke hain.", f"${tex(favourable)}$ of them are the ones we want.")
    board.draw(f, {"type": "grid", "x": 60, "y": 30, "rows": rows, "cols": columns, "cell": cell, "filled": int(favourable), "color": "gold", "highlight": True})
    board.write(f, f"$\\text{{favourable}} = {tex(favourable)}$")
    f = board.say(
        f"Probability $= \\frac{{{tex(favourable)}}}{{{tex(total)}}} = {tex(probability)}$.",
        f"Probability $= \\frac{{{tex(favourable)}}}{{{tex(total)}}} = {tex(probability)}$.",
    )
    board.write(f, f"$P = \\frac{{{tex(favourable)}}}{{{tex(total)}}} = {tex(probability)}$", "right")
    return board.build()


# ---------- 17. right triangle: Pythagoras, tangent length, heights and distances ----------

TANGENTS = {30: 1 / sympy.sqrt(3), 45: sympy.Integer(1), 60: sympy.sqrt(3)}


def rightTriangle(params: dict[str, Any], language: str) -> Visual:
    angle = params.get("angle")
    base = number(params["base"]) if params.get("base") is not None else None
    height = number(params["height"]) if params.get("height") is not None else None
    hypotenuse = number(params["hypotenuse"]) if params.get("hypotenuse") is not None else None
    board = Board("Right triangle", language)
    lines: list[tuple[str, str, str]] = []  # (hinglish, english, board line)
    unknown = "height"  # the side the question asks for: shown as "?" until it is worked out
    if angle is not None:
        degrees = int(number(angle))
        if degrees not in TANGENTS or base is None:
            raise TemplateError("angle 30, 45 or 60 with the base")
        height = base * TANGENTS[degrees]
        lines.append((
            f"$\\tan {degrees}^\\circ = \\frac{{\\text{{height}}}}{{\\text{{base}}}}$, aur $\\tan {degrees}^\\circ = {tex(TANGENTS[degrees])}$.",
            f"$\\tan {degrees}^\\circ = \\frac{{\\text{{height}}}}{{\\text{{base}}}}$, and $\\tan {degrees}^\\circ = {tex(TANGENTS[degrees])}$.",
            f"$\\text{{height}} = {tex(base)} \\times \\tan {degrees}^\\circ = {tex(base)} \\times {tex(TANGENTS[degrees])} = {tex(height)}$",
        ))
    elif hypotenuse is None and base is not None and height is not None:
        unknown = "hypotenuse"
        hypotenuse = sympy.sqrt(base**2 + height**2)
        lines.append((
            "Pythagoras: lambi side ka square = baaki do sides ke squares ka jod.",
            "Pythagoras: the long side squared = the sum of the squares of the other two.",
            f"$\\text{{hypotenuse}} = \\sqrt{{{tex(base)}^2 + {tex(height)}^2}} = \\sqrt{{{tex(base**2 + height**2)}}} = {tex(hypotenuse)}$",
        ))
    elif hypotenuse is not None and (base is None) != (height is None):
        known = base if base is not None else height
        assert known is not None
        if hypotenuse <= known:
            raise TemplateError("hypotenuse must be the longest side")
        missing = sympy.sqrt(hypotenuse**2 - known**2)
        unknown = "height" if base is not None else "base"
        base, height = (base, missing) if base is not None else (missing, height)
        lines.append((
            "Pythagoras ulta lagao: lambi side ke square mein se jaani hui side ka square ghatao.",
            "Pythagoras the other way: long side squared minus the known side squared.",
            f"$\\sqrt{{{tex(hypotenuse)}^2 - {tex(known)}^2}} = \\sqrt{{{tex(hypotenuse**2 - known**2)}}} = {tex(missing)}$",
        ))
    else:
        raise TemplateError("give two sides, or the base and an angle")
    assert base is not None and height is not None
    scale = min(380 / float(base), 240 / float(height))
    w, h = float(base) * scale, float(height) * scale
    left, bottom = 140.0, 300.0

    def sideLabels(solved: bool) -> list[dict[str, Any]]:
        shown = {"base": base, "height": height, "hypotenuse": hypotenuse}
        text = {name: "?" if name == unknown and not solved else f"${tex(value)}$" if value is not None else "" for name, value in shown.items()}
        return [
            {"x": left + w / 2, "y": bottom + 22, "text": text["base"]},
            {"x": left + w + 34, "y": bottom - h / 2, "text": text["height"]},
            {"x": left + w / 2 - 30, "y": bottom - h / 2 - 16, "text": text["hypotenuse"]},
        ]

    f = board.say(
        "Ye ek right triangle hai — neeche base, khadi height, aur tirchhi hypotenuse.",
        "This is a right triangle — the base along the bottom, the height standing up, the hypotenuse slanting.",
    )
    board.draw(f, {"type": "polygon", "points": [[left, bottom], [left + w, bottom], [left + w, bottom - h]], "color": "blue", "labels": sideLabels(False)})
    board.draw(f, {"type": "rect", "x": left + w - 16, "y": bottom - 16, "width": 16, "height": 16, "color": "white", "label": ""})
    if angle is not None:
        board.write(f, f"$\\text{{base}} = {tex(base)}, \\quad \\text{{angle}} = {int(number(angle))}^\\circ$")
    hinglish, english, line = lines[0]
    f = board.say(hinglish, english)
    board.draw(f, {"type": "polygon", "points": [[left, bottom], [left + w, bottom], [left + w, bottom - h]], "color": "green", "labels": sideLabels(True)})
    board.write(f, line, "right")
    return board.build()


# ---------- 18. simple interest: the same interest added every year ----------


def interestStairs(params: dict[str, Any], language: str) -> Visual:
    principal, rate, years = number(params["principal"]), number(params["rate"]), number(params["time"])
    if not (years.is_integer and 1 <= years <= 8 and principal > 0 and rate > 0):
        raise TemplateError("whole years up to 8")
    yearly = principal * rate / 100
    interest = yearly * years
    board = Board("Har saal utna hi interest", language, "The same interest every year")
    f = board.say(
        f"Simple interest mein har saal ek jaisa interest judta hai: ${tex(principal)}$ ka ${tex(rate)}\\%$.",
        f"In simple interest the same amount is added every year: ${tex(rate)}\\%$ of ${tex(principal)}$.",
    )
    board.write(f, f"$\\text{{1 year}} = \\frac{{{tex(principal)} \\times {tex(rate)}}}{{100}} = {tex(yearly)}$")
    height = 220 / (float(principal) + float(interest)) * float(principal)
    step = 220 / (float(principal) + float(interest)) * float(yearly)
    for year in range(int(years) + 1):
        total = principal + yearly * year
        tall = height + step * year
        board.draw(f, {"type": "rect", "x": 80 + year * 70, "y": 300 - tall, "width": 56, "height": tall, "color": "gold" if year else "blue", "label": f"${tex(total)}$"})
    f = board.say(
        f"${tex(years)}$ saal mein: ${tex(yearly)} \\times {tex(years)} = {tex(interest)}$.",
        f"In ${tex(years)}$ years: ${tex(yearly)} \\times {tex(years)} = {tex(interest)}$.",
    )
    board.write(f, f"$SI = {tex(yearly)} \\times {tex(years)} = {tex(interest)}$", "right")
    board.write(f, f"$\\text{{Amount}} = {tex(principal)} + {tex(interest)} = {tex(principal + interest)}$")
    return board.build()


# ---------- 19. sector of a circle ----------


def sector(params: dict[str, Any], language: str) -> Visual:
    radius, angle = number(params["radius"]), number(params["angle"])
    if not (0 < angle < 360 and radius > 0):
        raise TemplateError("angle between 0 and 360")
    pi = sympy.Rational(22, 7) if str(params.get("pi")) == "22/7" or radius % 7 == 0 else sympy.pi
    whole = pi * radius**2
    part = sympy.nsimplify(angle / 360)
    area = part * whole
    board = Board("Sector: circle ka ek tukda", language, "Sector: a slice of the circle")
    f = board.say(
        f"Poore circle ka area $\\pi r^2 = {tex(whole)}$.",
        f"The whole circle has area $\\pi r^2 = {tex(whole)}$.",
    )
    board.draw(f, {"type": "circle", "cx": 320, "cy": 180, "r": 130, "color": "blue", "label": f"$r = {tex(radius)}$"})
    board.write(f, f"$\\pi r^2 = {tex(pi)} \\times {tex(radius)}^2 = {tex(whole)}$")
    f = board.say(
        f"${tex(angle)}^\\circ$ poore ${360}^\\circ$ ka ${tex(part)}$ hissa hai — toh area bhi utna hi hissa.",
        f"${tex(angle)}^\\circ$ is ${tex(part)}$ of the full $360^\\circ$ — so the area is that part too.",
    )
    board.draw(f, {"type": "circle", "cx": 320, "cy": 180, "r": 130, "color": "gold", "label": f"${tex(angle)}^\\circ$", "sector": [0, float(angle)], "highlight": True})
    board.write(f, f"$\\frac{{{tex(angle)}}}{{360}} = {tex(part)}$")
    board.write(f, f"$\\text{{Area}} = {tex(part)} \\times {tex(whole)} = {tex(area)}$", "right")
    return board.build()


# ---------- 12. exponents: a power is a row of blocks ----------


def blockRow(board: Board, frame: int, count: int, x: float, y: float, color: str, label: str, size: float = 36) -> None:
    for index in range(count):
        board.draw(frame, {"type": "rect", "x": x + index * (size + 6), "y": y, "width": size, "height": size, "color": color, "label": label, "keep": True})


def powerBlocks(params: dict[str, Any], language: str) -> Visual:
    """x^m · x^n: m blocks and n blocks make m + n blocks (multiply -> powers add). Also x^m ÷ x^n and (x^m)^n."""
    base = str(params.get("base") or "x")[:3]
    m, n = int(number(params["m"])), int(number(params["n"]))
    op = str(params.get("op") or "multiply")
    if not (1 <= m <= 9 and 1 <= n <= 9) or (op == "divide" and n >= m) or (op == "power" and m * n > 18):
        raise TemplateError("powers too large to draw")
    b = f"{base}"
    board = Board("Power = kitni baar guna", language, "Power = how many times you multiply")
    f = board.say(
        f"${b}^{{{m}}}$ matlab ${b}$ ko ${m}$ baar guna karna — ${m}$ dabbe, har dabbe mein ${b}$.",
        f"${b}^{{{m}}}$ means ${b}$ multiplied ${m}$ times — ${m}$ blocks, each one ${b}$.",
    )
    blockRow(board, f, m, 40, 40, "blue", f"${b}$")
    board.write(f, f"${b}^{{{m}}} = " + " \\cdot ".join([b] * m) + "$")
    if op == "power":
        f = board.say(
            f"$({b}^{{{m}}})^{{{n}}}$ matlab yeh poora group ${n}$ baar — ${n}$ rows of ${m}$.",
            f"$({b}^{{{m}}})^{{{n}}}$ means this whole group ${n}$ times — ${n}$ rows of ${m}$.",
        )
        for row in range(1, n):
            blockRow(board, f, m, 40, 40 + row * 46, "purple", f"${b}$")
        board.write(f, f"$({b}^{{{m}}})^{{{n}}} = {b}^{{{m} \\times {n}}} = {b}^{{{m * n}}}$", "right")
        return board.build()
    f = board.say(
        f"${b}^{{{n}}}$ — ${n}$ aur dabbe." if op == "multiply" else f"Ab ${b}^{{{n}}}$ se bhaag: ${n}$ dabbe kat jaate hain.",
        f"${b}^{{{n}}}$ — ${n}$ more blocks." if op == "multiply" else f"Now divide by ${b}^{{{n}}}$: ${n}$ blocks cancel.",
    )
    if op == "multiply":
        blockRow(board, f, n, 40, 100, "purple", f"${b}$")
        board.write(f, f"${b}^{{{n}}} = " + " \\cdot ".join([b] * n) + "$")
        f = board.say(
            f"Guna karo toh saare dabbe ek line mein: ${m} + {n} = {m + n}$ dabbe. Isliye powers JUDTI hain.",
            f"Multiply and all blocks stand in one row: ${m} + {n} = {m + n}$ blocks. So the powers ADD.",
        )
        blockRow(board, f, m + n, 40, 180, "green", f"${b}$")
        board.write(f, f"${b}^{{{m}}} \\cdot {b}^{{{n}}} = {b}^{{{m} + {n}}} = {b}^{{{m + n}}}$", "right")
    else:
        for index in range(n):
            x = 40 + index * 42
            board.draw(f, {"type": "line", "from": [x, 76], "to": [x + 36, 40], "color": "red", "keep": True})
        board.write(f, f"$\\frac{{{b}^{{{m}}}}}{{{b}^{{{n}}}}} = {b}^{{{m} - {n}}} = {b}^{{{m - n}}}$", "right")
    return board.build()


def powersMultipliedNotAdded(params: dict[str, Any], language: str) -> Visual:
    """Their x^(m·n) next to the real x^(m+n): 12 blocks drawn vs 7 blocks — the count shows it."""
    base = str(params.get("base") or "x")[:3]
    m, n = int(number(params["m"])), int(number(params["n"]))
    if m * n > 20:
        raise TemplateError("too many blocks")
    board = Board("Guna ya jod?", language, "Multiply or add?")
    f = board.say(
        f"Tumne powers ko guna kiya: ${m} \\times {n} = {m * n}$. Matlab ${m * n}$ dabbe — par itne dabbe aaye kahan se?",
        f"You multiplied the powers: ${m} \\times {n} = {m * n}$. That is ${m * n}$ blocks — where would they come from?",
    )
    for row in range(m):
        blockRow(board, f, n, 40, 40 + row * 40, "red", "", 32)
    board.write(f, f"${base}^{{{m} \\times {n}}} = {base}^{{{m * n}}}$ — ${m * n}$ " + board.pick("dabbe", "blocks"), "wrong")
    f = board.say(
        f"Asal mein bas ${m}$ dabbe aur ${n}$ dabbe hain — ek line mein ${m + n}$.",
        f"There are only ${m}$ blocks and ${n}$ blocks — ${m + n}$ in one row.",
    )
    blockRow(board, f, m, 300, 60, "blue", "", 32)
    blockRow(board, f, n, 300, 104, "purple", "", 32)
    board.write(f, f"${base}^{{{m}}} \\cdot {base}^{{{n}}} = {base}^{{{m + n}}}$ — ${m + n}$ " + board.pick("dabbe", "blocks"), "right")
    board.write(f, "Yaad rakho: same base ka guna $\\to$ powers jodo" if language != "en" else "Remember: same base multiplied $\\to$ add the powers")
    return board.build()


# ---------- 13. solids: a 2.5D drawing, what volume and surface area mean, and the cuboid net ----------


def drawSolid(
    board: Board, frame: int, shape: str, dims: dict[str, sympy.Expr], cx: float, color: str = "blue", size: float = 170
) -> None:
    """A clean oblique drawing with hidden edges dashed. Pixel sizes are scaled, labels carry the real numbers."""
    def keep(element: dict[str, Any]) -> None:
        board.draw(frame, {**element, "keep": True, "color": element.get("color", color)})

    if shape in ("cuboid", "cube"):
        length, b, h = (dims["side"],) * 3 if shape == "cube" else (dims["length"], dims["breadth"], dims["height"])
        scale = size / float(max(length, h, b))
        w, hh, d = float(length) * scale, float(h) * scale, float(b) * scale * 0.5
        x0, y0 = cx - w / 2 - d / 2, 300.0
        front = [[x0, y0], [x0 + w, y0], [x0 + w, y0 - hh], [x0, y0 - hh]]
        keep({"type": "polygon", "points": front, "opacity": 0.22})
        keep({"type": "polygon", "points": [[x0, y0 - hh], [x0 + w, y0 - hh], [x0 + w + d, y0 - hh - d], [x0 + d, y0 - hh - d]], "opacity": 0.12})
        keep({"type": "polygon", "points": [[x0 + w, y0], [x0 + w + d, y0 - d], [x0 + w + d, y0 - hh - d], [x0 + w, y0 - hh]], "opacity": 0.08})
        keep({"type": "line", "from": [x0, y0], "to": [x0 + d, y0 - d], "dashed": True})
        keep({"type": "line", "from": [x0 + d, y0 - d], "to": [x0 + w + d, y0 - d], "dashed": True})
        keep({"type": "line", "from": [x0 + d, y0 - d], "to": [x0 + d, y0 - hh - d], "dashed": True})
        keep({"type": "line", "from": [x0, y0 + 18], "to": [x0 + w, y0 + 18], "color": "gold", "label": f"$l = {tex(length)}$", "labelDy": 18})
        keep({"type": "line", "from": [x0 - 18, y0], "to": [x0 - 18, y0 - hh], "color": "gold", "label": f"$h = {tex(h)}$", "labelDx": -44, "labelDy": 0})
        if shape == "cuboid":
            keep({"type": "line", "from": [x0 + w + 12, y0], "to": [x0 + w + d + 12, y0 - d], "color": "gold", "label": f"$b = {tex(b)}$", "labelDx": 40, "labelDy": 0})
        return
    r = dims["radius"]
    rx = 90.0
    ry = 24.0
    if shape == "cylinder":
        h = dims["height"]
        hh = min(220.0, max(90.0, 190 * float(h) / float(max(h, 2 * r))))
        top, bottom = 300 - hh, 300.0
        keep({"type": "ellipse", "cx": cx, "cy": top, "rx": rx, "ry": ry, "opacity": 0.2})
        keep({"type": "ellipse", "cx": cx, "cy": bottom, "rx": rx, "ry": ry, "part": "front"})
        keep({"type": "ellipse", "cx": cx, "cy": bottom, "rx": rx, "ry": ry, "part": "back"})
        keep({"type": "line", "from": [cx - rx, top], "to": [cx - rx, bottom]})
        keep({"type": "line", "from": [cx + rx, top], "to": [cx + rx, bottom]})
        keep({"type": "line", "from": [cx, top], "to": [cx + rx, top], "color": "gold", "label": f"$r = {tex(r)}$", "labelDy": -14})
        keep({"type": "line", "from": [cx + rx + 22, top], "to": [cx + rx + 22, bottom], "color": "gold", "label": f"$h = {tex(h)}$", "labelDx": 40, "labelDy": 0})
        return
    if shape == "cone":
        h = dims.get("height") or sympy.sqrt(dims["slant"] ** 2 - r**2)
        apex, base = 300 - 210.0, 300.0
        keep({"type": "ellipse", "cx": cx, "cy": base, "rx": rx, "ry": ry, "part": "front"})
        keep({"type": "ellipse", "cx": cx, "cy": base, "rx": rx, "ry": ry, "part": "back"})
        keep({"type": "polygon", "points": [[cx - rx, base], [cx, apex], [cx + rx, base]], "opacity": 0.14})
        keep({"type": "line", "from": [cx, apex], "to": [cx, base], "dashed": True, "color": "gold", "label": f"$h = {tex(h)}$", "labelDx": 26, "labelDy": 0})
        keep({"type": "line", "from": [cx, base], "to": [cx + rx, base], "color": "gold", "label": f"$r = {tex(r)}$", "labelDy": 16})
        if dims.get("slant"):
            keep({"type": "line", "from": [cx + rx, base], "to": [cx, apex], "color": "purple", "label": f"$l = {tex(dims['slant'])}$", "labelDx": 40, "labelDy": 0})
        return
    if shape in ("sphere", "hemisphere"):
        R = 110.0
        centre = 200.0 if shape == "sphere" else 260.0
        if shape == "sphere":
            keep({"type": "circle", "cx": cx, "cy": centre, "r": R, "label": ""})
        else:
            arc = [[cx + R * float(sympy.cos(sympy.pi * k / 24)), centre - R * float(sympy.sin(sympy.pi * k / 24))] for k in range(25)]
            keep({"type": "polygon", "points": arc, "opacity": 0.16})
        keep({"type": "ellipse", "cx": cx, "cy": centre, "rx": R, "ry": 26, "part": "front"})
        keep({"type": "ellipse", "cx": cx, "cy": centre, "rx": R, "ry": 26, "part": "back"})
        keep({"type": "line", "from": [cx, centre], "to": [cx + R, centre], "color": "gold", "label": f"$r = {tex(r)}$", "labelDy": -16})
        return
    raise TemplateError(f"no drawing for {shape}")


SOLID_MEANING = {
    "volume": ("Volume matlab andar kitni jagah — isme kitna paani ya kitne cubes bharenge.", "Volume is the space inside — how much water or how many cubes fill it."),
    "total_surface_area": ("Total surface area matlab bahar ki poori chaadar — saari faces ko dhakne ke liye kitna kaagaz.", "Total surface area is the whole outer skin — the paper needed to cover every face."),
    "curved_surface_area": ("Curved surface area matlab sirf golai wali deewar — upar-neeche ke dhakkan nahi.", "Curved surface area is only the curved wall — not the top and bottom lids."),
    "lateral_surface_area": ("Lateral surface area matlab chaaron deewarein — upar-neeche nahi.", "Lateral surface area is the four walls — not the top and bottom."),
    "surface_area": ("Surface area matlab bahar ki poori sataah.", "Surface area is the whole outer surface."),
}


def solidTemplate(params: dict[str, Any], language: str) -> Visual:
    from app.maths.solvers import FORMULAS  # the same NCERT formulas the answer key was computed with

    shape = str(params.get("shape"))
    quantity = str(params.get("quantity") or "volume")
    pi = {"22/7": sympy.Rational(22, 7), "3.14": sympy.Rational(314, 100)}.get(str(params.get("pi")), sympy.pi)
    dims = {name: number(value) for name, value in (params.get("dimensions") or {}).items() if value is not None}
    if shape not in FORMULAS or quantity not in FORMULAS[shape] or shape not in ("cuboid", "cube", "cylinder", "cone", "sphere", "hemisphere"):
        raise TemplateError("not a solid this template draws")
    formula, compute = FORMULAS[shape][quantity]
    try:
        value = sympy.nsimplify(compute({**dims, "pi": pi}))
    except KeyError as error:
        raise TemplateError(f"missing {error.args[0]}") from error
    board = Board(f"{shape.capitalize()}: dekho, phir naapo", language, f"{shape.capitalize()}: look, then measure")
    f = board.say(
        f"Yeh hai hamara {shape} — iske naap board par likhe hain.",
        f"Here is our {shape} — its measurements are written on it.",
    )
    drawSolid(board, f, shape, dims, 320)
    hinglish, english = SOLID_MEANING.get(quantity, SOLID_MEANING["volume"])
    f = board.say(hinglish, english)
    board.write(f, f"{quantity.replace('_', ' ').capitalize()}: ${formula}$")
    f = board.say("Ab formula mein naap rakho.", "Now put the measurements into the formula.")
    unit = "^3" if quantity == "volume" else "^2"
    board.write(f, f"$= {tex(value)}$ (units${unit}$)", "right")
    return board.build()


def cuboidNet(params: dict[str, Any], language: str) -> Visual:
    """The cuboid opened flat: 6 faces in 3 pairs — lb, bh, hl — so TSA = 2(lb + bh + hl) is just adding faces."""
    dims = {name: number(value) for name, value in (params.get("dimensions") or {}).items()}
    length, b, h = dims["length"], dims["breadth"], dims["height"]
    scale = 70 / float(max(length, b, h))
    L, B, H = float(length) * scale, float(b) * scale, float(h) * scale
    board = Board("Cuboid ko khol ke dekho", language, "Unfold the cuboid")
    f = board.say(
        "Cuboid ko kaat ke seedha bichha do — 6 faces dikhte hain, teen jode.",
        "Cut the cuboid open and lay it flat — 6 faces, in three pairs.",
    )
    x0, y0 = 120.0, 60.0
    faces = [
        (x0 + B, y0, L, B, "blue", f"$lb = {tex(length * b)}$"),
        (x0, y0 + B, B, H, "purple", f"$bh = {tex(b * h)}$"),
        (x0 + B, y0 + B, L, H, "green", f"$lh = {tex(length * h)}$"),
        (x0 + B + L, y0 + B, B, H, "purple", f"$bh = {tex(b * h)}$"),
        (x0 + 2 * B + L, y0 + B, L, H, "green", f"$lh = {tex(length * h)}$"),
        (x0 + B, y0 + B + H, L, B, "blue", f"$lb = {tex(length * b)}$"),
    ]
    for x, y, w, hh, color, label in faces:
        board.draw(f, {"type": "rect", "x": x, "y": y, "width": w, "height": hh, "color": color, "label": label, "keep": True})
    total = 2 * (length * b + b * h + h * length)
    f = board.say("Har jode ko do baar gino — isliye formula mein 2 aata hai.", "Count each pair twice — that is where the 2 comes from.")
    board.write(f, f"$TSA = 2(lb + bh + hl) = 2({tex(length * b)} + {tex(b * h)} + {tex(h * length)}) = {tex(total)}$", "right")
    return board.build()


def volumeNotSurface(params: dict[str, Any], language: str) -> Visual:
    """Volume (space inside) vs surface area (outer skin), side by side on the same solid."""
    shape = str(params.get("shape"))
    dims = {name: number(value) for name, value in (params.get("dimensions") or {}).items() if value is not None}
    board = Board("Andar ki jagah ya bahar ki chaadar?", language, "Space inside or skin outside?")
    f = board.say(
        "Volume andar bhari jagah naapta hai — jaise dibbe mein paani.",
        "Volume measures the space filled inside — like water in a box.",
    )
    drawSolid(board, f, shape, dims, 150, "blue", 120)
    board.write(f, "Volume: andar ki jagah (units$^3$)" if language != "en" else "Volume: space inside (units$^3$)", "wrong")
    f = board.say(
        "Surface area bahar ki chaadar naapti hai — dibbe ko dhakne wala kaagaz.",
        "Surface area measures the outer skin — the paper that wraps the box.",
    )
    drawSolid(board, f, shape, dims, 500, "green", 120)
    board.write(f, "Surface area: bahar ki chaadar (units$^2$)" if language != "en" else "Surface area: outer skin (units$^2$)", "right")
    board.write(f, "Yaad rakho: jagah $\\to$ volume (cube units), chaadar $\\to$ surface area (square units)" if language != "en" else "Remember: space $\\to$ volume, skin $\\to$ surface area")
    return board.build()


# ---------- 14. triangles: basic proportionality (DE ∥ BC) ----------


def proportionality(params: dict[str, Any], language: str) -> Visual:
    """AD/DB = AE/EC when DE ∥ BC; the missing length is computed here, never taken from the AI."""
    known = {key: (number(params[key]) if params.get(key) is not None else None) for key in ("ad", "db", "ae", "ec")}
    missing = [key for key, value in known.items() if value is None]
    if len(missing) != 1:
        raise TemplateError("needs exactly three of AD, DB, AE, EC")
    ad, db, ae, ec = (known[key] or sympy.Symbol("x") for key in ("ad", "db", "ae", "ec"))
    solution = sympy.solve(sympy.Eq(ad * ec, ae * db), sympy.Symbol("x"))
    if len(solution) != 1 or solution[0] <= 0:
        raise TemplateError("no single positive length")
    value = sympy.nsimplify(solution[0])
    A, B, C = (320.0, 40.0), (100.0, 320.0), (540.0, 320.0)
    share = float((known["ad"] or value) / ((known["ad"] or value) + (known["db"] or value)))
    D = (A[0] + (B[0] - A[0]) * share, A[1] + (B[1] - A[1]) * share)
    E = (A[0] + (C[0] - A[0]) * share, A[1] + (C[1] - A[1]) * share)
    def name(key: str) -> str:
        return "x" if known[key] is None else tex(known[key])
    board = Board("Parallel line, barabar ratio", language, "Parallel line, equal ratios")
    f = board.say(
        "Triangle ABC mein DE, BC ke parallel hai — yeh line dono sides ko ek hi ratio mein kaat'ti hai.",
        "In triangle ABC, DE is parallel to BC — it cuts both sides in the same ratio.",
    )
    board.draw(f, {"type": "polygon", "points": [list(A), list(B), list(C)], "keep": True, "opacity": 0.1,
                   "labels": [{"x": A[0], "y": A[1] - 18, "text": "A"}, {"x": B[0] - 16, "y": B[1] + 14, "text": "B"}, {"x": C[0] + 16, "y": C[1] + 14, "text": "C"},
                              {"x": D[0] - 18, "y": D[1], "text": "D"}, {"x": E[0] + 18, "y": E[1], "text": "E"}]})
    board.draw(f, {"type": "line", "from": list(D), "to": list(E), "color": "gold", "keep": True})
    board.draw(f, {"type": "line", "from": [B[0], B[1]], "to": [C[0], C[1]], "color": "gold", "keep": True})
    f = board.say("Upar ke tukde neeche ke tukdon se ek hi ratio mein hain.", "The top pieces and the bottom pieces are in the same ratio.")
    board.draw(f, {"type": "line", "from": list(A), "to": list(D), "color": "blue", "label": f"${name('ad')}$", "labelDx": -30, "labelDy": 0, "keep": True})
    board.draw(f, {"type": "line", "from": list(D), "to": list(B), "color": "purple", "label": f"${name('db')}$", "labelDx": -30, "labelDy": 0, "keep": True})
    board.draw(f, {"type": "line", "from": list(A), "to": list(E), "color": "blue", "label": f"${name('ae')}$", "labelDx": 30, "labelDy": 0, "keep": True})
    board.draw(f, {"type": "line", "from": list(E), "to": list(C), "color": "purple", "label": f"${name('ec')}$", "labelDx": 30, "labelDy": 0, "keep": True})
    board.write(f, f"$\\frac{{AD}}{{DB}} = \\frac{{AE}}{{EC}} \\Rightarrow \\frac{{{name('ad')}}}{{{name('db')}}} = \\frac{{{name('ae')}}}{{{name('ec')}}}$")
    f = board.say("Cross multiply karo aur x nikaalo.", "Cross-multiply and find x.")
    board.write(f, f"$x = {tex(value)}$", "right")
    return board.build()


# ---------- 15. statistics: grouped data as a histogram ----------


def histogram(params: dict[str, Any], language: str) -> Visual:
    """Bars for each class; class mark x = middle of the class; mean = Σfx / Σf."""
    intervals = [str(item) for item in params["intervals"]][:8]
    frequencies = [number(item) for item in params["frequencies"]][: len(intervals)]
    if len(intervals) < 2 or len(frequencies) != len(intervals) or any(value < 0 for value in frequencies):
        raise TemplateError("needs intervals and frequencies")
    bounds = []
    for interval in intervals:
        low, _, high = interval.replace("–", "-").partition("-")
        bounds.append((number(low), number(high)))
    marks = [(low + high) / 2 for low, high in bounds]
    tallest = float(max(frequencies)) or 1.0
    width = 520 / len(intervals)
    board = Board("Data ko dekho, phir mean", language, "Look at the data, then the mean")
    f = board.say("Har class ki frequency ek bar hai — jitni lambi bar, utne zyada log.", "Each class is a bar — the taller the bar, the more values in it.")
    for index, (interval, frequency) in enumerate(zip(intervals, frequencies, strict=True)):
        height = 30 + 200 * float(frequency) / tallest
        board.draw(f, {"type": "rect", "x": 60 + index * width, "y": 300 - height, "width": width - 6, "height": height, "color": "blue", "label": f"${tex(frequency)}$", "keep": True})
        board.draw(f, {"type": "line", "from": [60 + index * width, 316], "to": [60 + (index + 1) * width - 6, 316], "color": "white", "label": interval, "labelDy": 18, "keep": True})
    f = board.say("Har class ka beech wala number — class mark $x$ — us class ki pehchaan hai.", "The middle of each class — the class mark $x$ — stands for that class.")
    board.write(f, "$x = $ " + ", ".join(tex(mark) for mark in marks))
    total_f = sum(frequencies)
    total_fx = sum(frequency * mark for frequency, mark in zip(frequencies, marks, strict=True))
    if total_f == 0:
        raise TemplateError("no data")
    f = board.say("Mean = saare $fx$ ka jod, bata saari frequency ka jod.", "Mean = the sum of all $fx$ over the sum of all frequencies.")
    board.write(f, f"$\\Sigma f = {tex(total_f)}, \\quad \\Sigma fx = {tex(total_fx)}$")
    board.write(f, f"$\\bar{{x}} = \\frac{{\\Sigma fx}}{{\\Sigma f}} = \\frac{{{tex(total_fx)}}}{{{tex(total_f)}}} = {tex(sympy.nsimplify(total_fx / total_f))}$", "right")
    return board.build()


# ---------- 16. Heron: s is HALF the walk round the triangle ----------


def heronTriangle(params: dict[str, Any], language: str, wrongPerimeter: bool = False) -> Visual:
    a, b, c = number(params["a"]), number(params["b"]), number(params["c"])
    if not (a + b > c and b + c > a and a + c > b):
        raise TemplateError("not a triangle")
    s = (a + b + c) / 2
    area = sympy.sqrt(s * (s - a) * (s - b) * (s - c))
    # place the triangle with side c on the base
    cosA = (b**2 + c**2 - a**2) / (2 * b * c)
    scale = 260 / float(max(a, b, c))
    P = (180.0, 300.0)
    Q = (180 + float(c) * scale, 300.0)
    R = (180 + float(b * cosA) * scale, 300 - float(b * sympy.sqrt(1 - cosA**2)) * scale)
    board = Board("Heron: aadha chakkar", language, "Heron: half the perimeter")
    f = board.say(
        f"Teen sides: ${tex(a)}, {tex(b)}, {tex(c)}$. Poora chakkar = perimeter ${tex(a + b + c)}$.",
        f"Three sides: ${tex(a)}, {tex(b)}, {tex(c)}$. Once round = perimeter ${tex(a + b + c)}$.",
    )
    board.draw(f, {"type": "polygon", "points": [list(P), list(Q), list(R)], "keep": True, "opacity": 0.14,
                   "labels": [{"x": (P[0] + Q[0]) / 2, "y": P[1] + 22, "text": f"${tex(c)}$"},
                              {"x": (P[0] + R[0]) / 2 - 22, "y": (P[1] + R[1]) / 2, "text": f"${tex(b)}$"},
                              {"x": (Q[0] + R[0]) / 2 + 22, "y": (Q[1] + R[1]) / 2, "text": f"${tex(a)}$"}]})
    if wrongPerimeter:
        board.write(f, f"$s = {tex(a)} + {tex(b)} + {tex(c)} = {tex(a + b + c)}$ — " + board.pick("yeh poora chakkar hai", "this is the whole perimeter"), "wrong")
    f = board.say(
        f"Heron ka $s$ SEMI-perimeter hai — sirf aadha chakkar: ${tex(s)}$.",
        f"Heron's $s$ is the SEMI-perimeter — only half the way round: ${tex(s)}$.",
    )
    board.write(f, f"$s = \\frac{{{tex(a)} + {tex(b)} + {tex(c)}}}{{2}} = {tex(s)}$", "right")
    f = board.say("Ab har side ko $s$ se ghatao aur formula lagao.", "Now subtract each side from $s$ and use the formula.")
    board.write(f, f"$\\sqrt{{{tex(s)} \\cdot {tex(s - a)} \\cdot {tex(s - b)} \\cdot {tex(s - c)}}} = {tex(area)}$", "right")
    if wrongPerimeter:
        board.write(f, "Yaad rakho: Heron mein $s$ = perimeter ka aadha" if language != "en" else "Remember: in Heron's formula $s$ is half the perimeter")
    return board.build()


# ---------- 17. AP: n terms have n − 1 jumps (fence posts) ----------


def fencePosts(params: dict[str, Any], language: str) -> Visual:
    first, difference, count = number(params["first"]), number(params["difference"]), int(number(params["n"]))
    if count < 2:
        raise TemplateError("needs two or more terms")
    shown = min(count, 7)
    board = Board("Khambe aur jumps", language, "Posts and jumps")
    f = board.say(
        f"Socho ${count}$ khambe ek line mein — pehla khamba $a = {tex(first)}$.",
        f"Think of ${count}$ posts in a row — the first post is $a = {tex(first)}$.",
    )
    for index in range(shown):
        x = 60 + index * 80
        label = f"$a_{{{index + 1 if index < shown - 1 or count == shown else count}}}$"
        board.draw(f, {"type": "rect", "x": x, "y": 120, "width": 14, "height": 140, "color": "gold" if index == 0 else "blue", "label": "", "keep": True})
        board.draw(f, {"type": "line", "from": [x + 7, 280], "to": [x + 7, 280], "color": "white", "label": label, "labelDy": 0, "keep": True})
    f = board.say(
        f"Do khambon ke beech ek jump ($d = {tex(difference)}$). ${count}$ khambon mein jumps sirf ${count - 1}$!",
        f"One jump ($d = {tex(difference)}$) between two posts. ${count}$ posts have only ${count - 1}$ jumps!",
    )
    for index in range(shown - 1):
        x = 60 + index * 80
        board.draw(f, {"type": "arrow", "from": [x + 16, 110], "to": [x + 78, 110], "color": "green", "label": "+d", "keep": True})
    board.write(f, f"$n\\cdot d = {count} \\times {tex(difference)}$ — ek jump zyada", "wrong")
    last = first + (count - 1) * difference
    board.write(f, f"$a_{{{count}}} = a + ({count} - 1)d = {tex(first)} + {count - 1} \\times {tex(difference)} = {tex(last)}$", "right")
    board.write(f, "Yaad rakho: $n$ terms mein $(n-1)$ jumps" if language != "en" else "Remember: $n$ terms have $(n-1)$ jumps")
    return board.build()



# ---------- 18. negative powers: a staircase where each step down divides by the base ----------

NEGATIVE_POWER = re.compile(r"^\s*(\d+)\s*\^\s*\{?\s*\(?\s*-\s*(\d+)\s*\)?\s*\}?\s*$")


def readNegativePower(text: str) -> dict[str, Any] | None:
    """'2^{-3}' -> {"base": 2, "n": 3}. Only a whole-number base from 2 to 10 and powers up to 5 are drawn."""
    match = NEGATIVE_POWER.match(text)
    if not match:
        return None
    base, n = int(match.group(1)), int(match.group(2))
    return {"base": base, "n": n} if 2 <= base <= 10 and 1 <= n <= 5 else None


def negativePower(params: dict[str, Any], language: str) -> Visual:
    """b^n, ..., b^1, b^0 = 1, b^-1, ..., b^-n: every step down DIVIDES by b, so a minus power is a small positive
    fraction, never a negative number."""
    base, n = int(number(params["base"])), int(number(params["n"]))
    if not (2 <= base <= 10 and 1 <= n <= 5):
        raise TemplateError("powers too large to draw")
    top = min(n, 3)
    powers = list(range(top, -n - 1, -1))
    board = Board("Power kam = base se bhaag", language, "One power less = divide by the base")
    step = 520 / len(powers)

    def stair(frame: int, index: int, power: int, color: str) -> None:
        value = sympy.Integer(base) ** power
        height = 40 + 26 * (len(powers) - 1 - index)
        board.draw(frame, {"type": "rect", "x": 60 + index * step, "y": 320 - height, "width": step - 8, "height": height,
                           "color": color, "label": f"${tex(value)}$", "keep": True})
        board.draw(frame, {"type": "line", "from": [60 + index * step, 336], "to": [60 + (index + 1) * step - 8, 336],
                           "color": "white", "label": f"${base}^{{{power}}}$", "labelDy": 18, "keep": True})

    f = board.say(
        f"Upar se shuru karo: ${base}^{{{top}}} = {tex(sympy.Integer(base) ** top)}$. Har seedhi neeche jaate hi power 1 kam hoti hai — aur value ${base}$ se bhaag ho jaati hai.",
        f"Start at the top: ${base}^{{{top}}} = {tex(sympy.Integer(base) ** top)}$. Each step down, the power drops by 1 — and the value is divided by ${base}$.",
    )
    for index, power in enumerate(powers):
        if power >= 0:
            stair(f, index, power, "blue" if power else "gold")
    board.write(f, f"${base}^{{0}} = 1$ — yahan tak har baar $\\div {base}$")
    f = board.say(
        f"Zero ke baad bhi wahi rule: $1 \\div {base}$, phir phir se $\\div {base}$. Value chhoti hoti jaati hai, par kabhi negative nahi.",
        f"Past zero the rule is the same: $1 \\div {base}$, then $\\div {base}$ again. The value gets smaller, never negative.",
    )
    for index, power in enumerate(powers):
        if power < 0:
            stair(f, index, power, "green" if power == -n else "purple")
    answer = sympy.Rational(1, base**n)
    board.write(f, f"${base}^{{-{n}}} = \\frac{{1}}{{{base}^{{{n}}}}} = {tex(answer)}$", "right")
    return board.build()


def negativeIsNotMinus(params: dict[str, Any], language: str) -> Visual:
    """Their -b^n (or b × -n) as a bar below zero, next to the true tiny positive b^-n."""
    base, n = int(number(params["base"])), int(number(params["n"]))
    answer = sympy.Rational(1, base**n)
    board = Board("Minus power ≠ minus number", language, "Minus power ≠ minus number")
    f = board.say(
        f"Agar ${base}^{{-{n}}}$ ko $-{base**n}$ samjho, toh value zero se neeche chali jaati — negative.",
        f"If you read ${base}^{{-{n}}}$ as $-{base**n}$, the value would drop below zero — negative.",
    )
    board.draw(f, {"type": "line", "from": [40, 180], "to": [600, 180], "color": "white", "label": "0", "labelDx": -290, "labelDy": 0, "keep": True})
    board.draw(f, {"type": "rect", "x": 130, "y": 180, "width": 90, "height": 140, "color": "red", "label": f"$-{base**n}$", "keep": True})
    board.write(f, f"${base}^{{-{n}}} = -{base**n}$ ?", "wrong")
    f = board.say(
        f"Par minus power ka matlab hai 'ulta karo': $\\frac{{1}}{{{base}^{{{n}}}}}$ — zero se thoda sa upar, chhota sa positive tukda.",
        f"But a minus power means 'take the reciprocal': $\\frac{{1}}{{{base}^{{{n}}}}}$ — a tiny positive piece just above zero.",
    )
    board.draw(f, {"type": "rect", "x": 400, "y": 168, "width": 90, "height": 12, "color": "green", "label": f"${tex(answer)}$", "keep": True, "highlight": True})
    board.write(f, f"${base}^{{-{n}}} = \\frac{{1}}{{{base}^{{{n}}}}} = {tex(answer)}$", "right")
    board.write(f, "Yaad rakho: minus power $\\to$ ulta (1 upon), negative nahi" if language != "en" else "Remember: a minus power $\\to$ one over, not negative")
    return board.build()

TEMPLATES: dict[str, Callable[[dict[str, Any], str], Visual]] = {
    "division_ladder": divisionLadder,
    "fraction_bars": fractionBars,
    "balance": balanceEquation,
    "cross_multiplication": crossMultiplication,
    "elimination": elimination,
    "area_expand": areaExpand,
    "area_factor": areaFactor,
    "quadratic_formula": quadraticFormula,
    "number_line": numberLine,
    "coordinates": coordinates,
    "shape": shapes,
    "ap_stairs": apStairs,
    "percent_grid": percentGrid,
    "angle_sum": angleSum,
    "mean_bars": meanBars,
    "proportion": proportion,
    "probability_grid": probabilityGrid,
    "right_triangle": rightTriangle,
    "interest_stairs": interestStairs,
    "sector": sector,
    "power_blocks": powerBlocks,
    "solid": solidTemplate,
    "cuboid_net": cuboidNet,
    "proportionality": proportionality,
    "histogram": histogram,
    "heron": heronTriangle,
    "negative_power": negativePower,
}


def buildTemplate(name: str, params: dict[str, Any], language: str) -> Visual | None:
    """The finished visual, or None when the numbers do not fit the template (never a half-right picture)."""
    builder = TEMPLATES.get(name)
    if builder is None or not isinstance(params, dict):
        return None
    try:
        visual = builder(params, language)
    except (TemplateError, KeyError, IndexError, TypeError, ValueError, ZeroDivisionError, LatexParseError,
            sympy.PolynomialError, sympy.SympifyError):
        return None
    return visual if len(visual["frames"]) >= 2 else None


# ---------- choosing a template without any AI, from the question's own maths ----------


def isQuadratic(text: str) -> bool:
    try:
        quadraticParts(text)
    except (TemplateError, LatexParseError, sympy.PolynomialError, TypeError, ValueError):
        return False
    return True


FRACTION_PAIR = re.compile(
    r"^\s*(?:\\frac\{(\d+)\}\{(\d+)\}|(\d+)\s*/\s*(\d+))\s*([+-])\s*(?:\\frac\{(\d+)\}\{(\d+)\}|(\d+)\s*/\s*(\d+))\s*$"
)
ROOT = re.compile(r"^\s*\\sqrt(\[3\])?\{(\d+)\}\s*$")


POWER_PRODUCT = re.compile(r"^\s*([a-z])\^\{?(\d)\}?\s*(?:\\cdot|\\times|\*|×)?\s*([a-z])\^\{?(\d)\}?\s*$")
POWER_QUOTIENT = re.compile(r"^\s*\\frac\{\s*([a-z])\^\{?(\d)\}?\s*\}\{\s*([a-z])\^\{?(\d)\}?\s*\}\s*$")
POWER_OF_POWER = re.compile(r"^\s*\(\s*([a-z])\^\{?(\d)\}?\s*\)\^\{?(\d)\}?\s*$")


def readPowerLaw(text: str) -> dict[str, Any] | None:
    """'x^3 \\cdot x^4' -> multiply, '\\frac{x^7}{x^3}' -> divide, '(x^2)^3' -> power (same letter base only)."""
    for pattern, op in ((POWER_PRODUCT, "multiply"), (POWER_QUOTIENT, "divide")):
        match = pattern.match(text)
        if match and match.group(1) == match.group(3):
            return {"base": match.group(1), "m": int(match.group(2)), "n": int(match.group(4)), "op": op}
    match = POWER_OF_POWER.match(text)
    if match:
        return {"base": match.group(1), "m": int(match.group(2)), "n": int(match.group(3)), "op": "power"}
    return None


def chooseByRule(
    expressions: list[str], mistakeKind: str | None, wrongLatex: str | None
) -> tuple[str, dict[str, Any]] | None:
    """Questions whose maths alone says what to draw — no AI needed, so these visuals are instant and certain.
    Word problems (AP, shapes, interest...) go to the AI chooser, which knows what is being asked."""
    equations = [text for text in expressions if "=" in text]
    if len(equations) == 2:
        return "elimination", {"equations": equations}
    if len(equations) == 1:
        equation = equations[0]
        if isQuadratic(equation):
            usesFormula = "quadratic formula" in (mistakeKind or "") or "\\pm" in (wrongLatex or "")
            if usesFormula or not buildTemplate("area_factor", {"expression": equation}, "en"):
                return "quadratic_formula", {"expression": equation}
            return "area_factor", {"expression": equation}
        if buildTemplate("cross_multiplication", {"equation": equation}, "en"):
            return "cross_multiplication", {"equation": equation}
        return "balance", {"equation": equation}
    if len(expressions) != 1:
        return None
    text = expressions[0]
    powers = readPowerLaw(text)
    if powers:
        return "power_blocks", powers
    negative = readNegativePower(text)
    if negative:
        return "negative_power", negative
    root = ROOT.match(text)
    if root:
        return "division_ladder", {"number": int(root.group(2)), "purpose": "cube_root" if root.group(1) else "square_root"}
    pair = FRACTION_PAIR.match(text)
    if pair:
        p1, q1, sign, p2, q2 = (pair.group(1) or pair.group(3), pair.group(2) or pair.group(4), pair.group(5),
                                pair.group(6) or pair.group(8), pair.group(7) or pair.group(9))
        return "fraction_bars", {"fractions": [[p1, q1], [p2, q2]], "op": sign}
    if buildTemplate("area_expand", {"expression": text}, "en"):  # (x + 3)(x + 5): open the brackets
        return "area_expand", {"expression": text}
    if isQuadratic(text) and buildTemplate("area_factor", {"expression": text}, "en"):  # x^2 + 8x + 15
        return "area_factor", {"expression": text}
    return None


# ---------- a template chosen by the AI must end on the question's own computed answer ----------


def answerValues(answer: dict[str, Any]) -> list[sympy.Expr]:
    kind = answer.get("type")
    texts = (
        [answer.get("latex")] if kind == "expression"
        else list(answer.get("values") or []) if kind == "solution_set"
        else list((answer.get("values") or {}).values()) if kind == "point"
        else []
    )
    try:
        return [number(text) for text in texts if text is not None]
    except TemplateError:
        return []


def showsAnswer(visual: Visual, answer: dict[str, Any]) -> bool:
    """Every value of the answer is the result (last '= ...') of some green line on the board."""
    values = answerValues(answer)
    if not values:
        return False
    results: list[sympy.Expr] = []
    for element in visual["elements"]:
        if element.get("type") != "text" or element.get("tone") != "right":
            continue
        for span in re.findall(r"\$([^$]+)\$", str(element.get("text"))):
            for part in re.split(r",\s*\\quad|\\quad", span):
                last = re.sub(r"\\text\{[^}]*\}|\^\\circ|\\%|\^\{?[23]\}?$", "", part.split("=")[-1]).strip()
                try:
                    results.append(number(last))
                except TemplateError:
                    continue
    return all(any(sympy.simplify(value - result) == 0 for result in results) for value in values)


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def isGrounded(params: Any, source: str) -> bool:
    """Every number the AI put in the params must appear in the question — it may pick, never invent."""
    allowed = {sympy.nsimplify(item.lstrip("-")) for item in NUMBER.findall(source)} | {0, 1, 2, 100}
    texts = [str(item) for item in collectValues(params)]
    return all(sympy.nsimplify(item.lstrip("-")) in allowed for text in texts for item in NUMBER.findall(text))


def collectValues(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [item for inner in value.values() for item in collectValues(inner)]
    if isinstance(value, list):
        return [item for inner in value for item in collectValues(inner)]
    return [value] if isinstance(value, (int, float, str)) else []


def joinVisuals(first: Visual, second: Visual) -> Visual:
    """The mistake picture, then the question done right — one lesson. Later drawings replace earlier ones."""
    offset = len(first["frames"])
    return {
        "title": second["title"],
        "frames": first["frames"] + second["frames"],
        "elements": first["elements"] + [{**element, "frame": element["frame"] + offset} for element in second["elements"]],
    }


def mistakePicture(
    mistakeKind: str | None, language: str, template: str | None = None, params: dict[str, Any] | None = None
) -> Visual | None:
    """THEIR way drawn and seen to fail, next to the right way, with this question's own numbers — the picture a
    student remembers. Built by code, so it is instant and always correct. None when no picture fits the mistake."""
    kind = (mistakeKind or "").lower()
    if "adding fractions" in kind:
        return buildTemplate("fraction_bars", {"fractions": [[1, 2], [1, 3]], "op": "+", "wrong": [2, 5]}, language)
    params = params or {}
    picture = None
    try:
        if template == "sector" and ("arc length" in kind or "circumference" in kind):
            picture = areaNotEdge(params, language)
        elif template == "coordinates" and "square" in kind:
            picture = distanceTriangle(params, language)
        elif template == "shape" and params.get("shape") == "rectangle" and params.get("quantity") == "perimeter":
            picture = halfWayRound(params, language)
        elif template == "power_blocks" and params.get("op") == "multiply":
            picture = powersMultipliedNotAdded(params, language)
        elif template == "negative_power":
            picture = negativeIsNotMinus(params, language)  # any mistake on b^-n: the classic one is reading it as -b^n
        elif template in ("solid", "cuboid_net") and ("volume" in kind and "surface" in kind):
            picture = volumeNotSurface(params, language)
        elif template == "heron" and "perimeter" in kind:
            picture = heronTriangle(params, language, wrongPerimeter=True)
        elif template == "ap_stairs" and "n·d" in kind:
            picture = fencePosts(params, language)
    except (TemplateError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    for element in (picture or {}).get("elements", []):
        element["mistakePicture"] = True  # its ✗ line is a taught wrong rule, kept even after the student's own line
    return picture


def areaNotEdge(params: dict[str, Any], language: str) -> Visual:
    """Arc length (the edge) vs sector area (the inside): the 2πr vs πr² mix-up, drawn."""
    radius, angle = number(params["radius"]), number(params["angle"])
    board = Board("Kinaara ya andar ki jagah?", language, "Edge or the space inside?")
    f = board.say(
        "Tumhare formula mein $2\\pi r$ hai — woh sirf kinaare ki lambai naapta hai, yeh peeli line.",
        "Your formula has $2\\pi r$ — that measures only the edge, this yellow line.",
    )
    board.draw(f, {"type": "circle", "cx": 170, "cy": 170, "r": 110, "color": "gold", "sector": [0, float(angle)], "arc": True, "label": board.pick("tumne naapa: kinaara", "you measured: the edge")})
    board.write(f, f"$\\frac{{{tex(angle)}}}{{360}} \\times 2\\pi \\times {tex(radius)}$ = " + board.pick("arc ki lambai", "arc length"), "wrong")
    f = board.say(
        "Area matlab andar ki poori jagah — hare tukde ko bharne mein kitne square cm lagenge.",
        "Area is the whole space inside — how many square cm fill the green slice.",
    )
    board.draw(f, {"type": "circle", "cx": 470, "cy": 170, "r": 110, "color": "green", "sector": [0, float(angle)], "label": board.pick("area: andar ki jagah", "area: the space inside"), "highlight": True})
    board.write(f, f"$\\frac{{{tex(angle)}}}{{360}} \\times \\pi \\times {tex(radius)}^2$ = " + board.pick("sector ka area", "area of the sector"), "right")
    f = board.say(
        "Yaad rakho: lambai ke liye $r$, jagah ke liye $r^2$. Area hamesha square units mein aata hai.",
        "Remember: length uses $r$, space uses $r^2$. Area always comes in square units.",
    )
    board.write(f, "Yaad rakho: kinaara $\\to 2\\pi r$, andar ki jagah $\\to \\pi r^2$" if language != "en" else "Remember: edge $\\to 2\\pi r$, inside $\\to \\pi r^2$")
    return board.build()


def distanceTriangle(params: dict[str, Any], language: str) -> Visual:
    """Distance is the slanted side of a right triangle: its square is the sum of the two squares (Pythagoras)."""
    (x1, y1), (x2, y2) = [(number(point[0]), number(point[1])) for point in params["points"][:2]]
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    if dx == 0 or dy == 0:
        raise TemplateError("needs a slanted line")
    scale = min(300 / float(dx), 200 / float(dy))
    w, h = float(dx) * scale, float(dy) * scale
    left, bottom = 170.0, 280.0
    board = Board("Distance = triangle ki tirchhi side", language, "Distance = the slanted side of a triangle")
    f = board.say(
        f"Dono points ko jodo: seedha ${tex(dx)}$ aage aur ${tex(dy)}$ upar-neeche — ek right triangle ban gaya.",
        f"Join the points: ${tex(dx)}$ across and ${tex(dy)}$ up or down — a right triangle.",
    )
    board.draw(f, {"type": "polygon", "points": [[left, bottom], [left + w, bottom], [left + w, bottom - h]], "color": "blue",
                   "labels": [{"x": left + w / 2, "y": bottom + 24, "text": f"${tex(dx)}$"}, {"x": left + w + 26, "y": bottom - h / 2, "text": f"${tex(dy)}$"}]})
    board.write(f, f"$x_2 - x_1 = {tex(dx)}, \\quad y_2 - y_1 = {tex(dy)}$")
    f = board.say(
        f"Bina square kiye jodna galat hai: $\\sqrt{{{tex(dx)} + {tex(dy)}}}$ is tirchhi line ki lambai nahi hai.",
        f"Adding without squaring is wrong: $\\sqrt{{{tex(dx)} + {tex(dy)}}}$ is not the length of this slanted line.",
    )
    board.write(f, "$\\sqrt{(x_2 - x_1) + (y_2 - y_1)}$ — " + board.pick("squares ke bina", "without the squares"), "wrong")
    f = board.say(
        f"Pythagoras: tirchhi side ka square = dono sides ke squares ka jod — ${tex(dx)}^2 + {tex(dy)}^2 = {tex(dx**2 + dy**2)}$.",
        f"Pythagoras: the slanted side squared = the sum of the two squares — ${tex(dx)}^2 + {tex(dy)}^2 = {tex(dx**2 + dy**2)}$.",
    )
    board.draw(f, {"type": "arrow", "from": [left, bottom], "to": [left + w, bottom - h], "color": "green", "label": "d", "highlight": True})
    board.write(f, f"$d^2 = {tex(dx)}^2 + {tex(dy)}^2 = {tex(dx**2 + dy**2)}$", "right")
    return board.build()


def halfWayRound(params: dict[str, Any], language: str) -> Visual:
    """Perimeter goes all the way round: l + b is only half the walk."""
    length, breadth = number(params["length"]), number(params["breadth"])
    scale = min(170 / float(length), 150 / float(breadth))
    w, h = float(length) * scale, float(breadth) * scale
    board = Board("Poora chakkar lagao", language, "Go all the way round")
    f = board.say(
        f"$l + b = {tex(length)} + {tex(breadth)}$ sirf do sides hain — yeh aadha chakkar hai.",
        f"$l + b = {tex(length)} + {tex(breadth)}$ is only two sides — half the walk round.",
    )
    board.draw(f, {"type": "rect", "x": 40, "y": 90, "width": w, "height": h, "color": "gray", "label": board.pick("aadha", "half")})
    board.draw(f, {"type": "arrow", "from": [40, 70], "to": [40 + w, 70], "color": "gold", "label": f"${tex(length)}$"})
    board.draw(f, {"type": "arrow", "from": [60 + w, 90], "to": [60 + w, 90 + h], "color": "gold", "label": f"${tex(breadth)}$"})
    board.write(f, f"$l + b = {tex(length + breadth)}$ — " + board.pick("sirf 2 sides", "only 2 sides"), "wrong")
    f = board.say(
        "Perimeter matlab poora chakkar: do lambi sides aur do chaudi sides.",
        "Perimeter is the whole walk round: two long sides and two short sides.",
    )
    x = 360.0
    board.draw(f, {"type": "rect", "x": x, "y": 90, "width": w, "height": h, "color": "green", "label": board.pick("poora", "whole"), "highlight": True})
    board.draw(f, {"type": "arrow", "from": [x, 70], "to": [x + w, 70], "color": "green", "label": f"${tex(length)}$"})
    board.draw(f, {"type": "arrow", "from": [x + w + 20, 90], "to": [x + w + 20, 90 + h], "color": "green", "label": f"${tex(breadth)}$"})
    board.draw(f, {"type": "arrow", "from": [x + w, 110 + h], "to": [x, 110 + h], "color": "green", "label": f"${tex(length)}$"})
    board.draw(f, {"type": "arrow", "from": [x - 20, 90 + h], "to": [x - 20, 90], "color": "green", "label": f"${tex(breadth)}$"})
    board.write(f, f"$P = 2(l + b) = 2 \\times {tex(length + breadth)} = {tex(2 * (length + breadth))}$", "right")
    return board.build()
