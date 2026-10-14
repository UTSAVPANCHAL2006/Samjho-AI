// Short teacher remarks for each kind of mistake the server can prove (backend/app/maths/misconceptions.py).

const REMARKS: [string, string][] = [
  ["sign of -b", "Watch the sign of −b!"],
  ["dividing by 2 instead of 2a", "Divide the whole thing by 2a"],
  ["forgot the square root", "You forgot to take the square root"],
  ["adding fractions", "Fractions don't add like this!"],
  ["squaring a bracket", "A bracket doesn't square like this"],
  ["square root", "A root doesn't split over a plus"],
  ["minus sign before a bracket", "The minus applies to every term"],
  ["multiplying into a bracket", "Multiply the outside number into every term"],
  ["moving terms", "The sign flips when a term crosses over"],
  ["calculation slip", "A small calculation slip"],
  ["arc length formula instead of the area", "Area uses πr², not 2πr"],
  ["forgot to square", "You forgot to square"],
  ["diameter", "Use the radius, not the diameter"],
  ["θ/360", "You forgot to multiply by θ/360"],
  ["adding the coordinates", "Subtract the coordinates, don't add them"],
  ["multiplying an equation", "Multiply both sides by the same number"],
  ["simple interest instead of compound", "This is compound interest"],
  ["divide by 100", "You forgot to divide by 100"],
  ["formula", "Check the formula again"],
];

export function mistakeRemark(kind: string | null | undefined): string {
  if (!kind) return "Mistake here";
  const lowered = kind.toLowerCase();
  return REMARKS.find(([key]) => lowered.includes(key))?.[1] ?? "Mistake here";
}
