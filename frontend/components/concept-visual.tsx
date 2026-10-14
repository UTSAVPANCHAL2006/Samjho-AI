"use client";

// Concept visual: draws the AI's "visual recipe" (checked by SymPy on the server) on a dark board, frame by frame,
// in sync with the voice reading each frame's caption. The AI chooses the blocks; this file decides how they look,
// so every visual has the same premium style.

import { useMemo, useState, type ReactNode } from "react";
import type { ConceptVisualData, Language, VisualElement } from "@/lib/api";
import { useScenePlayer, type PlayerVoice } from "@/lib/use-scene-player";
import { BoardShell, PlayerBar } from "@/components/board-chrome";
import { MixedMath } from "@/components/math";

const WIDTH = 640;
const HEIGHT = 360;

const PALETTE: Record<string, string> = {
  blue: "#9cc8ff",
  purple: "#c9b2ff",
  gold: "#f2d27a",
  green: "#a6e3bc",
  red: "#ff9b93",
  gray: "#4a5a52",
  white: "#ece8dc",
};

type Point = [number, number];
type AnyRecord = Record<string, unknown>;

// ---------- small, defensive readers (the recipe comes from an AI) ----------

const num = (value: unknown, fallback = 0): number => {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};
const str = (value: unknown): string => (typeof value === "string" ? value : value == null ? "" : String(value));
const colorOf = (value: unknown): string => PALETTE[str(value)] ?? PALETTE.blue;
const pointOf = (value: unknown): Point =>
  Array.isArray(value) ? [num(value[0]), num(value[1])] : [0, 0];
const listOf = (value: unknown): AnyRecord[] =>
  Array.isArray(value) ? value.filter((item): item is AnyRecord => typeof item === "object" && item !== null) : [];

/** Words and $maths$ placed on the SVG. A label written as raw LaTeX ('2744 \\div 2') is shown as maths,
 * and long labels shrink to fit their box instead of spilling over it. */
function Label({
  x,
  y,
  text,
  color = PALETTE.white,
  size = 19,
  width = 240,
  align = "center",
}: {
  x: number;
  y: number;
  text: string;
  color?: string;
  size?: number;
  width?: number;
  align?: "center" | "left" | "right";
}) {
  if (!text) return null;
  const shown = !text.includes("$") && /\\[a-zA-Z]|\^|_\{/.test(text) ? `$${text}$` : text;
  const visibleLength = shown.replace(/\$|\\[a-zA-Z]+|[{}^_]/g, "").length;
  const fitted = Math.max(11, Math.min(size, (width * 1.7) / Math.max(1, visibleLength)));
  const height = fitted * 2.6;
  const left = align === "center" ? x - width / 2 : align === "right" ? x - width : x;
  const justify = align === "center" ? "center" : align === "right" ? "flex-end" : "flex-start";
  return (
    <foreignObject x={left} y={y - height / 2} width={width} height={height} overflow="visible">
      <div className="chalk-text flex h-full items-center leading-tight" style={{ color, fontSize: fitted, justifyContent: justify }}>
        <span className="whitespace-nowrap">{shown.includes("$") ? <MixedMath text={shown} /> : shown}</span>
      </div>
    </foreignObject>
  );
}

// ---------- the drawing blocks ----------

function Bar({ element }: { element: VisualElement }) {
  const x = num(element.x, 40);
  const y = num(element.y, 60);
  const width = num(element.width, 240);
  const height = num(element.height, 44);
  const parts = Math.max(1, Math.min(40, Math.round(num(element.parts, 1))));
  const filled = Math.max(0, Math.min(parts, Math.round(num(element.filled, parts))));
  const gap = parts > 12 ? 2 : 4;
  const partWidth = (width - gap * (parts - 1)) / parts;
  const color = colorOf(element.color);
  return (
    <g>
      {Array.from({ length: parts }, (_, index) => (
        <rect
          key={index}
          x={x + index * (partWidth + gap)}
          y={y}
          width={partWidth}
          height={height}
          rx={Math.min(8, partWidth / 4)}
          fill={index < filled ? color : PALETTE.gray}
          opacity={index < filled ? 0.95 : 0.55}
        />
      ))}
      {element.labelSide === "left" ? (
        <Label x={x - 14} y={y + height / 2} text={str(element.label)} color={color} size={21} width={110} align="right" />
      ) : (
        <Label x={x + width / 2} y={y - 22} text={str(element.label)} color={color} size={21} width={Math.max(120, width)} />
      )}
    </g>
  );
}

function Grid({ element }: { element: VisualElement }) {
  const x = num(element.x, 40);
  const y = num(element.y, 40);
  const rows = Math.max(1, Math.min(20, Math.round(num(element.rows, 10))));
  const cols = Math.max(1, Math.min(20, Math.round(num(element.cols, 10))));
  const cell = Math.max(6, Math.min(40, num(element.cell, 16)));
  const filled = Math.round(num(element.filled, 0));
  const color = colorOf(element.color);
  return (
    <g>
      {Array.from({ length: rows * cols }, (_, index) => (
        <rect
          key={index}
          x={x + (index % cols) * cell + 1}
          y={y + Math.floor(index / cols) * cell + 1}
          width={cell - 2}
          height={cell - 2}
          rx={2}
          fill={index < filled ? color : PALETTE.gray}
          opacity={index < filled ? 0.9 : 0.4}
        />
      ))}
    </g>
  );
}

function NumberLine({ element }: { element: VisualElement }) {
  const x = num(element.x, 40);
  const y = num(element.y, 200);
  const width = num(element.width, 560);
  const from = num(element.from, 0);
  const to = num(element.to, 10);
  const span = to - from || 1;
  let step = Math.abs(num(element.step, 1)) || 1;
  while (span / step > 24) step *= 2; // never more than ~24 ticks
  const toX = (value: number) => x + ((value - from) / span) * width;
  const ticks: number[] = [];
  for (let value = from; value <= to + 1e-9; value += step) ticks.push(Number(value.toFixed(6)));
  return (
    <g>
      <line x1={x - 8} y1={y} x2={x + width + 8} y2={y} stroke={PALETTE.white} strokeOpacity={0.6} strokeWidth={2} />
      {ticks.map((value) => (
        <g key={value}>
          <line x1={toX(value)} y1={y - 6} x2={toX(value)} y2={y + 6} stroke={PALETTE.white} strokeOpacity={0.5} />
          <text x={toX(value)} y={y + 24} textAnchor="middle" fontSize={12} fill={PALETTE.white} opacity={0.6}>
            {value}
          </text>
        </g>
      ))}
      {listOf(element.jumps).map((jump, index) => {
        const start = toX(num(jump.from));
        const end = toX(num(jump.to));
        const lift = Math.min(70, Math.abs(end - start) / 2 + 18);
        const color = colorOf(jump.color ?? element.color);
        return (
          <g key={`jump-${index}`}>
            <path
              d={`M ${start} ${y - 8} Q ${(start + end) / 2} ${y - lift} ${end} ${y - 8}`}
              fill="none"
              stroke={color}
              strokeWidth={2.5}
              markerEnd="url(#arrow-head)"
              className="visual-draw"
            />
            <Label x={(start + end) / 2} y={y - lift - 6} text={str(jump.label)} color={color} size={14} />
          </g>
        );
      })}
      {listOf(element.marks).map((mark, index) => {
        const color = colorOf(mark.color ?? element.color);
        return (
          <g key={`mark-${index}`}>
            <circle cx={toX(num(mark.value))} cy={y} r={7} fill={color} />
            <Label x={toX(num(mark.value))} y={y + 46} text={str(mark.label)} color={color} size={14} />
          </g>
        );
      })}
    </g>
  );
}

function Axes({ element }: { element: VisualElement }) {
  const x = num(element.x, 60);
  const y = num(element.y, 20);
  const width = num(element.width, 360);
  const height = num(element.height, 320);
  const xmin = num(element.xmin, -10);
  const xmax = num(element.xmax, 10);
  const ymin = num(element.ymin, -10);
  const ymax = num(element.ymax, 10);
  const toX = (value: number) => x + ((value - xmin) / (xmax - xmin || 1)) * width;
  const toY = (value: number) => y + height - ((value - ymin) / (ymax - ymin || 1)) * height;
  const step = Math.max(1, Math.ceil((xmax - xmin) / 12));
  const gridX: number[] = [];
  for (let value = Math.ceil(xmin); value <= xmax; value += step) gridX.push(value);
  const stepY = Math.max(1, Math.ceil((ymax - ymin) / 12));
  const gridY: number[] = [];
  for (let value = Math.ceil(ymin); value <= ymax; value += stepY) gridY.push(value);
  return (
    <g>
      {gridX.map((value) => (
        <line key={`gx${value}`} x1={toX(value)} y1={y} x2={toX(value)} y2={y + height} stroke={PALETTE.white} strokeOpacity={0.06} />
      ))}
      {gridY.map((value) => (
        <line key={`gy${value}`} x1={x} y1={toY(value)} x2={x + width} y2={toY(value)} stroke={PALETTE.white} strokeOpacity={0.06} />
      ))}
      {ymin <= 0 && ymax >= 0 ? (
        <line x1={x} y1={toY(0)} x2={x + width} y2={toY(0)} stroke={PALETTE.white} strokeOpacity={0.55} strokeWidth={1.5} />
      ) : null}
      {xmin <= 0 && xmax >= 0 ? (
        <line x1={toX(0)} y1={y} x2={toX(0)} y2={y + height} stroke={PALETTE.white} strokeOpacity={0.55} strokeWidth={1.5} />
      ) : null}
      {gridX.filter((value) => value !== 0).map((value) => (
        <text key={`lx${value}`} x={toX(value)} y={Math.min(y + height, Math.max(y, toY(0))) + 14} textAnchor="middle" fontSize={10} fill={PALETTE.white} opacity={0.4}>
          {value}
        </text>
      ))}
      {gridY.filter((value) => value !== 0).map((value) => (
        <text key={`ly${value}`} x={Math.min(x + width, Math.max(x, toX(0))) - 6} y={toY(value) + 3} textAnchor="end" fontSize={10} fill={PALETTE.white} opacity={0.4}>
          {value}
        </text>
      ))}
      {listOf(element.segments).map((segment, index) => {
        const [x1, y1] = pointOf(segment.from);
        const [x2, y2] = pointOf(segment.to);
        const color = colorOf(segment.color ?? element.color);
        return (
          <g key={`seg-${index}`}>
            <line
              x1={toX(x1)}
              y1={toY(y1)}
              x2={toX(x2)}
              y2={toY(y2)}
              stroke={color}
              strokeWidth={2.5}
              strokeDasharray={segment.dashed ? "6 5" : undefined}
              className="visual-draw"
            />
            <Label x={(toX(x1) + toX(x2)) / 2 + 14} y={(toY(y1) + toY(y2)) / 2 - 12} text={str(segment.label)} color={color} size={14} />
          </g>
        );
      })}
      {listOf(element.points).map((point, index) => {
        const color = colorOf(point.color ?? element.color);
        const px = toX(num(point.x));
        const py = toY(num(point.y));
        return (
          <g key={`pt-${index}`}>
            <circle cx={px} cy={py} r={9} fill={color} opacity={0.25} />
            <circle cx={px} cy={py} r={5} fill={color} />
            <Label x={px + 60} y={py - 14} text={str(point.label)} color={color} size={14} width={120} align="left" />
          </g>
        );
      })}
    </g>
  );
}

function balanceLayout(element: VisualElement) {
  const width = Math.max(380, Math.min(WIDTH - 40, num(element.width, 420))); // room for two pans that never touch
  return {
    width,
    x: Math.max(20, Math.min(WIDTH - 20 - width, num(element.x, 120))),
    y: Math.max(40, Math.min(HEIGHT - 170, num(element.y, 120))),
  };
}

function Balance({ element }: { element: VisualElement }) {
  const { width, x, y } = balanceLayout(element);
  const tilt = Math.max(-1, Math.min(1, Math.round(num(element.tilt, 0))));
  const center = x + width / 2;
  const angle = tilt * 7;
  const panItems = (items: unknown) => (Array.isArray(items) ? items.map(str).filter(Boolean).slice(0, 4) : []);
  const armLength = width / 2 - 70; // pans (140 wide) stay inside x .. x + width
  const pan = (side: -1 | 1, items: string[]) => {
    const panX = center + side * armLength;
    const drop = side * Math.sin((angle * Math.PI) / 180) * armLength;
    return (
      <g transform={`translate(0 ${drop})`}>
        <line x1={panX} y1={y} x2={panX - 50} y2={y + 70} stroke={PALETTE.white} strokeOpacity={0.35} />
        <line x1={panX} y1={y} x2={panX + 50} y2={y + 70} stroke={PALETTE.white} strokeOpacity={0.35} />
        <path d={`M ${panX - 70} ${y + 70} Q ${panX} ${y + 98} ${panX + 70} ${y + 70} Z`} fill={colorOf(element.color)} opacity={0.3} />
        {items.map((item, index) => (
          <g key={index}>
            <rect x={panX - 56} y={y + 36 - index * 34} width={112} height={30} rx={8} fill={colorOf(element.color)} opacity={0.9} />
            <Label x={panX} y={y + 51 - index * 34} text={item} color="#1e2b25" size={15} width={112} />
          </g>
        ))}
      </g>
    );
  };
  return (
    <g>
      <path d={`M ${center} ${y} L ${center - 26} ${y + 150} L ${center + 26} ${y + 150} Z`} fill={PALETTE.gray} />
      <g transform={`rotate(${angle} ${center} ${y})`}>
        <rect x={center - armLength - 10} y={y - 4} width={armLength * 2 + 20} height={8} rx={4} fill={PALETTE.white} opacity={0.85} />
      </g>
      <circle cx={center} cy={y} r={7} fill={PALETTE.gold} />
      {pan(-1, panItems(element.left))}
      {pan(1, panItems(element.right))}
    </g>
  );
}

function Shape({ element }: { element: VisualElement }) {
  const color = colorOf(element.color);
  if (element.type === "rect") {
    const x = num(element.x);
    const y = num(element.y);
    const width = num(element.width, 100);
    const height = num(element.height, 60);
    return (
      <g>
        <rect x={x} y={y} width={width} height={height} rx={6} fill={color} fillOpacity={0.22} stroke={color} strokeWidth={2} />
        <Label x={x + width / 2} y={y + height / 2} text={str(element.label)} color={PALETTE.white} width={Math.max(40, width - 12)} />
      </g>
    );
  }
  if (element.type === "circle") {
    const cx = num(element.cx, 320);
    const cy = num(element.cy, 180);
    const r = Math.max(4, num(element.r, 60));
    const sector = Array.isArray(element.sector) ? element.sector.map((value) => num(value)) : null;
    const pointAt = (degrees: number): Point => [
      cx + r * Math.cos((degrees * Math.PI) / 180),
      cy - r * Math.sin((degrees * Math.PI) / 180),
    ];
    return (
      <g>
        <circle cx={cx} cy={cy} r={r} fill={color} fillOpacity={sector ? 0.08 : 0.2} stroke={color} strokeWidth={element.arc ? 1 : 2} />
        {sector && sector.length === 2 ? (
          (() => {
            const [start, end] = sector;
            const [sx, sy] = pointAt(start);
            const [ex, ey] = pointAt(end);
            const large = Math.abs(end - start) > 180 ? 1 : 0;
            if (element.arc) {
              // Only the edge: "the length round the curve", drawn thick so it reads as a line, not a region.
              return <path d={`M ${sx} ${sy} A ${r} ${r} 0 ${large} 0 ${ex} ${ey}`} fill="none" stroke={color} strokeWidth={7} strokeLinecap="round" />;
            }
            return (
              <path d={`M ${cx} ${cy} L ${sx} ${sy} A ${r} ${r} 0 ${large} 0 ${ex} ${ey} Z`} fill={color} fillOpacity={0.55} stroke={color} />
            );
          })()
        ) : null}
        <Label x={cx} y={cy + r + 20} text={str(element.label)} color={color} />
      </g>
    );
  }
  if (element.type === "polygon") {
    const points = Array.isArray(element.points) ? element.points.map(pointOf) : [];
    if (points.length < 2) return null;
    return (
      <g>
        <polygon
          points={points.map(([px, py]) => `${px},${py}`).join(" ")}
          fill={color}
          fillOpacity={num(element.opacity, 0.18)}
          stroke={color}
          strokeWidth={2.5}
          strokeDasharray={element.dashed ? "6 6" : undefined}
          strokeLinejoin="round"
          className="visual-draw"
        />
        {listOf(element.labels).map((label, index) => (
          <Label key={index} x={num(label.x)} y={num(label.y)} text={str(label.text)} color={PALETTE.white} size={14} />
        ))}
      </g>
    );
  }
  return null;
}

/** An ellipse for solids: "front" draws the lower half (seen), "back" the upper half dashed (hidden), "full" both. */
function Ellipse({ element }: { element: VisualElement }) {
  const cx = num(element.cx, 320);
  const cy = num(element.cy, 180);
  const rx = Math.max(2, num(element.rx, 80));
  const ry = Math.max(2, num(element.ry, 22));
  const color = colorOf(element.color);
  const part = str(element.part) || "full";
  const lower = `M ${cx - rx} ${cy} A ${rx} ${ry} 0 0 0 ${cx + rx} ${cy}`;
  const upper = `M ${cx - rx} ${cy} A ${rx} ${ry} 0 0 1 ${cx + rx} ${cy}`;
  return (
    <g>
      {part === "full" ? (
        <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill={color} fillOpacity={num(element.opacity, 0.16)} stroke={color} strokeWidth={2.5} />
      ) : null}
      {part === "front" ? <path d={lower} fill="none" stroke={color} strokeWidth={2.5} /> : null}
      {part === "back" ? <path d={upper} fill="none" stroke={color} strokeWidth={2} strokeDasharray="6 6" opacity={0.7} /> : null}
      <Label x={cx} y={cy - ry - 16} text={str(element.label)} color={color} size={15} />
    </g>
  );
}

/** A plain edge (solids, parallel lines); dashed for a hidden edge. */
function Line({ element }: { element: VisualElement }) {
  const [x1, y1] = pointOf(element.from);
  const [x2, y2] = pointOf(element.to);
  const color = colorOf(element.color);
  return (
    <g>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={color}
        strokeWidth={element.dashed ? 2 : 2.5}
        strokeDasharray={element.dashed ? "6 6" : undefined}
        opacity={element.dashed ? 0.7 : 1}
        strokeLinecap="round"
      />
      <Label x={(x1 + x2) / 2 + num(element.labelDx)} y={(y1 + y2) / 2 + num(element.labelDy, -16)} text={str(element.label)} color={color} size={15} />
    </g>
  );
}

/** An angle mark: an arc from `start` to `end` degrees (counter-clockwise, 0 = right) with its value. */
function Angle({ element }: { element: VisualElement }) {
  const cx = num(element.cx, 320);
  const cy = num(element.cy, 180);
  const r = Math.max(10, num(element.r, 34));
  const start = num(element.start);
  const end = num(element.end, 60);
  const color = colorOf(element.color);
  const at = (degrees: number, radius: number): Point => [
    cx + radius * Math.cos((degrees * Math.PI) / 180),
    cy - radius * Math.sin((degrees * Math.PI) / 180),
  ];
  const [sx, sy] = at(start, r);
  const [ex, ey] = at(end, r);
  const [lx, ly] = at((start + end) / 2, r + 22);
  const large = Math.abs(end - start) > 180 ? 1 : 0;
  return (
    <g>
      <path d={`M ${cx} ${cy} L ${sx} ${sy} A ${r} ${r} 0 ${large} 0 ${ex} ${ey} Z`} fill={color} fillOpacity={0.3} stroke={color} strokeWidth={2} />
      <Label x={lx} y={ly} text={str(element.label)} color={color} size={15} width={90} />
    </g>
  );
}

function Arrow({ element }: { element: VisualElement }) {
  const [x1, y1] = pointOf(element.from);
  const [x2, y2] = pointOf(element.to);
  const color = colorOf(element.color);
  return (
    <g style={{ color }}>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={2.5} markerEnd="url(#arrow-head)" className="visual-draw" />
      <Label x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 16} text={str(element.label)} color={color} size={14} />
    </g>
  );
}

function Mark({ element }: { element: VisualElement }) {
  const x = num(element.x, 320);
  const y = num(element.y, 180);
  if (element.kind === "cross") {
    return (
      <path d={`M ${x - 14} ${y - 14} L ${x + 14} ${y + 14} M ${x + 14} ${y - 14} L ${x - 14} ${y + 14}`} stroke={PALETTE.red} strokeWidth={5} strokeLinecap="round" className="visual-draw" />
    );
  }
  return (
    <path d={`M ${x - 16} ${y} L ${x - 4} ${y + 13} L ${x + 18} ${y - 16}`} fill="none" stroke={PALETTE.green} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" className="visual-draw" />
  );
}

function drawElement(element: VisualElement): ReactNode {
  switch (element.type) {
    case "bar":
      return <Bar element={element} />;
    case "grid":
      return <Grid element={element} />;
    case "numberline":
      return <NumberLine element={element} />;
    case "axes":
      return <Axes element={element} />;
    case "balance":
      return <Balance element={element} />;
    case "rect":
    case "circle":
    case "polygon":
      return <Shape element={element} />;
    case "arrow":
      return <Arrow element={element} />;
    case "ellipse":
      return <Ellipse element={element} />;
    case "line":
      return <Line element={element} />;
    case "angle":
      return <Angle element={element} />;
    case "mark":
      return <Mark element={element} />;
    case "text":
      return (
        <Label
          x={num(element.x, 320)}
          y={num(element.y, 30)}
          text={str(element.text)}
          color={colorOf(element.color ?? "white")}
          size={Math.max(12, Math.min(28, num(element.size, 16)))}
          width={560}
        />
      );
    default:
      return null;
  }
}

// ---------- which elements are on the board in a frame ----------

/** Elements shown in a frame. An older drawing is hidden when a newer one overlaps it — the AI often draws
 * "the bar after this step" on top of the old bar. Nothing is ever drawn on top of something else. */
function visibleElements(elements: VisualElement[], frame: number): VisualElement[] {
  const shown = elements.filter((element) => element.frame <= frame);
  return shown.filter((element) => {
    if (element.keep) return true; // a solid or figure that later frames label and highlight stays on the board
    const box = boundsOf(element);
    return !shown.some((other) => {
      if (other === element || other.frame <= element.frame) return false;
      if (!box) return false;
      const otherBox = boundsOf(other);
      return otherBox ? overlapShare(box, otherBox) > 0.15 : false;
    });
  });
}

function overlapShare(first: Box, second: Box): number {
  const width = Math.min(first[2], second[2]) - Math.max(first[0], second[0]);
  const height = Math.min(first[3], second[3]) - Math.max(first[1], second[1]);
  if (width <= 0 || height <= 0) return 0;
  const area = (box: Box) => Math.max(1, (box[2] - box[0]) * (box[3] - box[1]));
  return (width * height) / Math.min(area(first), area(second));
}

// ---------- layout: drawings in a zoomed figure, written lines as "chalk notes" beside it ----------

type Tone = "wrong" | "right" | "now" | "normal";

interface Note {
  text: string;
  frame: number;
  tone: Tone;
}

/** '\\textbf{plus}' outside $...$ shows as raw LaTeX; keep just the word. */
function cleanNoteText(text: string): string {
  return text
    .split(/(\$[^$]+\$)/)
    .map((part) =>
      part.startsWith("$") ? part : part.replace(/\\(?:textbf|textit|text|mathrm|mathbf|emph)\{([^{}]*)\}/g, "$1"),
    )
    .join("");
}

function toneOf(element: VisualElement): Tone {
  const tone = str(element.tone);
  if (tone === "wrong" || tone === "right") return tone;
  if (element.color === "red") return "wrong";
  if (element.color === "green") return "right";
  return "normal";
}

/** Text elements become notes; a ✓ / ✗ mark in a frame colours that frame's last note. */
function buildNotes(elements: VisualElement[]): Note[] {
  const notes: Note[] = elements
    .filter((element) => element.type === "text" && str(element.text).trim())
    .map((element) => ({ text: cleanNoteText(str(element.text)), frame: element.frame, tone: toneOf(element) }));
  for (const mark of elements.filter((element) => element.type === "mark")) {
    const frameNotes = notes.filter((note) => note.frame === mark.frame);
    if (frameNotes.some((note) => note.tone !== "normal")) continue; // the frame already says which line is right/wrong
    const target = frameNotes[frameNotes.length - 1];
    if (target && target.tone === "normal") target.tone = mark.kind === "cross" ? "wrong" : "right";
  }
  return notes;
}

const isDrawing = (element: VisualElement) => element.type !== "text" && element.type !== "mark";

type Box = [number, number, number, number]; // minX, minY, maxX, maxY

function boundsOf(element: VisualElement): Box | null {
  const box = (x: number, y: number, width: number, height: number): Box => [x, y, x + width, y + height];
  const ofPoints = (points: Point[], pad: number): Box | null =>
    points.length
      ? [
          Math.min(...points.map((point) => point[0])) - pad,
          Math.min(...points.map((point) => point[1])) - pad,
          Math.max(...points.map((point) => point[0])) + pad,
          Math.max(...points.map((point) => point[1])) + pad,
        ]
      : null;
  switch (element.type) {
    case "bar":
      return element.labelSide === "left"
        ? box(num(element.x, 40) - 120, num(element.y, 60) - 6, num(element.width, 240) + 120, num(element.height, 44) + 12)
        : box(num(element.x, 40), num(element.y, 60) - 44, num(element.width, 240), num(element.height, 44) + 50);
    case "grid": {
      const cell = Math.max(6, Math.min(40, num(element.cell, 16)));
      return box(num(element.x, 40), num(element.y, 40), num(element.cols, 10) * cell, num(element.rows, 10) * cell);
    }
    case "numberline":
      return box(num(element.x, 40) - 20, num(element.y, 200) - 100, num(element.width, 560) + 40, 170);
    case "axes":
      return box(num(element.x, 60) - 34, num(element.y, 20) - 20, num(element.width, 360) + 110, num(element.height, 320) + 44);
    case "balance": {
      const layout = balanceLayout(element);
      return box(layout.x, layout.y - 140, layout.width, 300);
    }
    case "rect":
      return box(num(element.x), num(element.y), num(element.width, 100), num(element.height, 60));
    case "circle": {
      const r = Math.max(4, num(element.r, 60));
      return box(num(element.cx, 320) - r, num(element.cy, 180) - r, 2 * r, 2 * r + 40);
    }
    case "polygon":
      return ofPoints(Array.isArray(element.points) ? element.points.map(pointOf) : [], 28);
    case "arrow":
      return ofPoints([pointOf(element.from), pointOf(element.to)], 30);
    case "line": {
      // Include where the label sits (labelDx / labelDy), so a side label is never cut off at the figure's edge.
      const [[x1, y1], [x2, y2]] = [pointOf(element.from), pointOf(element.to)];
      const label: Point = [(x1 + x2) / 2 + num(element.labelDx), (y1 + y2) / 2 + num(element.labelDy, -16)];
      return ofPoints([[x1, y1], [x2, y2], ...(element.label ? [label] : [])], 34);
    }
    case "ellipse": {
      const [rx, ry] = [Math.max(2, num(element.rx, 80)), Math.max(2, num(element.ry, 22))];
      return box(num(element.cx, 320) - rx, num(element.cy, 180) - ry - 34, 2 * rx, 2 * ry + 40);
    }
    case "angle": {
      const r = Math.max(10, num(element.r, 34)) + 34;
      return box(num(element.cx, 320) - r, num(element.cy, 180) - r, 2 * r, 2 * r);
    }
    default:
      return null;
  }
}

/** A viewBox around every drawing, so the figure is zoomed in instead of floating in empty space. */
function figureViewBox(elements: VisualElement[]): string | null {
  const boxes = elements.filter(isDrawing).map(boundsOf).filter((box): box is Box => box !== null);
  if (!boxes.length) return null;
  let [minX, minY, maxX, maxY] = [
    Math.min(...boxes.map((box) => box[0])),
    Math.min(...boxes.map((box) => box[1])),
    Math.max(...boxes.map((box) => box[2])),
    Math.max(...boxes.map((box) => box[3])),
  ];
  const pad = 16;
  const minWidth = 260;
  const minHeight = 200;
  if (maxX - minX < minWidth) [minX, maxX] = [(minX + maxX - minWidth) / 2, (minX + maxX + minWidth) / 2];
  if (maxY - minY < minHeight) [minY, maxY] = [(minY + maxY - minHeight) / 2, (minY + maxY + minHeight) / 2];
  return `${minX - pad} ${minY - pad} ${maxX - minX + 2 * pad} ${maxY - minY + 2 * pad}`;
}

/** Bars stacked one above another get their label on the left (above would hit the bar on top);
 * bars side by side get it above (on the left it would hit the neighbour). */
function placeBarLabels(elements: VisualElement[]): VisualElement[] {
  const bars = elements.filter((element) => element.type === "bar");
  return elements.map((element) => {
    if (element.type !== "bar") return element;
    const [x, y, width] = [num(element.x, 40), num(element.y, 60), num(element.width, 240)];
    const hasBarJustAbove = bars.some((other) => {
      if (other === element) return false;
      const [otherX, otherY, otherWidth] = [num(other.x, 40), num(other.y, 60), num(other.width, 240)];
      const sharesColumn = otherX < x + width && x < otherX + otherWidth;
      return sharesColumn && otherY < y && y - otherY < 90;
    });
    return { ...element, labelSide: hasBarJustAbove ? "left" : "above" };
  });
}

/** A wide, short figure (bars, a number line) reads better across the full board, with the notes below it. */
function isWideFigure(viewBox: string): boolean {
  const [, , width, height] = viewBox.split(" ").map(Number);
  return width / height > 1.7;
}

const NOTE_STYLES: Record<Tone, string> = {
  wrong: "text-chalk-red",
  right: "text-chalk-green",
  now: "chalk-current text-chalk",
  normal: "text-chalk/55",
};

/** The last frame's "Yaad rakho: ..." line is the lesson's one rule: shown as a card, not as another note. */
const REMEMBER = /^(yaad rakho|remember)\s*:\s*/i;
const isRememberNote = (note: Note) => REMEMBER.test(note.text);
const ruleWords = (text: string) => text.replace(REMEMBER, "").replace(/[$\s]/g, "").toLowerCase();
const isSameRule = (caption: string, rule: string) => ruleWords(caption) === ruleWords(rule);

/** One idea at a time, like a teacher at the board: this frame's lines large, the two before it faint,
 * anything older folded away behind "+N pehle ke steps". */
function NotesPanel({ notes, frame }: { notes: Note[]; frame: number }) {
  const [showAll, setShowAll] = useState(false);
  const shown = notes.filter((note) => note.frame <= frame && !isRememberNote(note));
  if (!shown.length) return null;
  const earlier = shown.filter((note) => note.frame < frame);
  const recent = showAll ? earlier : earlier.slice(-2);
  const folded = earlier.length - recent.length;
  const visible = [...recent, ...shown.filter((note) => note.frame === frame)];
  return (
    <div className="space-y-1.5">
      {folded > 0 ? (
        <button
          onClick={() => setShowAll(true)}
          className="ml-3 rounded-full px-2.5 py-1 text-xs font-semibold text-chalk/45 ring-1 ring-chalk/15 hover:text-chalk/80"
        >
          + {folded} earlier steps
        </button>
      ) : null}
      <ol className="space-y-1.5" aria-label="Steps on the board">
        {visible.map((note) => {
          const isNow = note.frame === frame;
          const tone: Tone = note.tone !== "normal" ? note.tone : isNow ? "now" : "normal";
          const number = shown.indexOf(note) + 1;
          return (
            <li
              key={`${note.frame}-${number}`}
              className={`chalk-note flex items-start gap-3 rounded-xl px-3 py-2 leading-relaxed transition-all duration-500 ${NOTE_STYLES[tone]} ${
                isNow ? `board-write text-[19px] sm:text-[20px] ${tone !== "now" ? "chalk-current" : ""}` : "text-[15px] opacity-70"
              }`}
            >
              <span
                className={`mt-1 w-5 shrink-0 text-center font-hand text-xl leading-none ${
                  tone === "wrong" ? "text-chalk-red" : tone === "right" ? "text-chalk-green" : "text-chalk/35"
                }`}
                aria-hidden
              >
                {tone === "wrong" ? "✗" : tone === "right" ? "✓" : number}
              </span>
                <span className="min-w-0 overflow-x-auto py-1">
                <MixedMath text={note.text} />
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** The finale: the one rule to remember, centred on the board in big chalk handwriting. */
function RememberCard({ text }: { text: string }) {
  const [label, rule] = [text.match(REMEMBER)?.[1] ?? "Remember", text.replace(REMEMBER, "")];
  return (
    <div className="remember-card mx-auto my-4 max-w-2xl rounded-[1.5rem] px-6 py-8 text-center sm:px-10 sm:py-10">
      <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-chalk-yellow">{label}</p>
      <p className="mt-3 font-chalk text-[1.4rem] leading-snug text-chalk sm:text-[1.65rem]">
        <MixedMath text={rule} />
      </p>
    </div>
  );
}

// ---------- the player ----------

export function ConceptVisual({
  visual,
  voice,
  language,
  withVoice = true,
  autoPlay = false,
}: {
  visual: ConceptVisualData;
  voice: PlayerVoice;
  language: Language;
  withVoice?: boolean;
  autoPlay?: boolean;
}) {
  const speeches = useMemo(
    () => visual.frames.map((frame) => frame.caption.replace(/\$/g, "")),
    [visual.frames],
  );
  const displays = useMemo(() => visual.frames.map((frame) => frame.caption), [visual.frames]);
  const player = useScenePlayer({ speeches, displays, voice, language, withVoice, autoPlay });
  const frame = player.index;
  const drawings = useMemo(() => placeBarLabels(visual.elements.filter(isDrawing)), [visual.elements]);
  const notes = useMemo(() => buildNotes(visual.elements), [visual.elements]);
  // Fit the figure to what is on the board SO FAR (not to shapes still to come), so the current drawing is big;
  // no drawing panel at all while the board is still on the student's own line.
  const drawnSoFar = useMemo(() => drawings.filter((element) => element.frame <= frame), [drawings, frame]);
  const viewBox = useMemo(
    () => (visibleElements(drawings, frame).length ? figureViewBox(drawnSoFar) : null),
    [drawings, drawnSoFar, frame],
  );
  // The board's first "Yaad rakho" is the real rule (from the mistake picture); a later one is often only a recap
  // of the mistake. The finale always shows that first rule again, so the lesson ends on the idea itself.
  // Shown only on the board's last frame, so a mistake picture that also states its rule is still seen first.
  const rules = notes.filter(isRememberNote);
  const remember = frame === visual.frames.length - 1 && rules.length ? rules[0] : undefined;

  return (
    <BoardShell
      kicker="Watch and understand"
      title={visual.title}
      isSpeaking={player.isSpeaking}
      statusLabel={player.isPlaying ? "playing" : "paused"}
      footer={
        <PlayerBar
          caption={
            // the finale card already shows the rule in big chalk: the same words again underneath is noise
            remember && isSameRule(visual.frames[frame]?.caption ?? "", remember.text) ? null : (
              <MixedMath text={cleanNoteText(visual.frames[frame]?.caption ?? "")} />
            )
          }
          index={frame}
          count={visual.frames.length}
          share={player.overallShare}
          isPlaying={player.isPlaying}
          captionsOnly={!player.speaksAloud}
          onPlay={player.play}
          onPause={player.pause}
          onSeek={player.goTo}
        />
      }
    >
      {remember ? <RememberCard text={remember.text} /> : null}
      <div
        hidden={Boolean(remember)}
        className={`grid gap-3 ${viewBox && notes.length && !isWideFigure(viewBox) ? "md:grid-cols-[1.45fr_1fr]" : ""}`}
      >
        {viewBox ? (
          <div className="chalk-panel p-2">
            <svg
              viewBox={viewBox}
              className={`h-auto w-full ${isWideFigure(viewBox) ? "max-h-[20rem]" : "max-h-[26rem]"}`}
              role="img"
              aria-label={visual.frames[frame]?.caption}
            >
              <defs>
                <marker id="arrow-head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
                </marker>
                <filter id="visual-glow" x="-30%" y="-30%" width="160%" height="160%">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter id="chalk-texture">
                  <feTurbulence type="fractalNoise" baseFrequency="1.4" numOctaves="1" result="noise" />
                  <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.4" />
                </filter>
              </defs>
              <g filter="url(#chalk-texture)">
                {visibleElements(drawings, frame).map((element) => {
                  const index = drawings.indexOf(element);
                  return (
                    <g
                      key={`${index}-${element.frame}`}
                      // The new shape is drawn stroke by stroke and glows; older ones step back so the eye follows the teacher.
                      className={element.frame === frame ? "visual-appear drawing-now" : "visual-appear"}
                      opacity={element.frame < frame ? 0.38 : 1}
                      filter={element.frame === frame ? "url(#visual-glow)" : undefined}
                      style={{ color: colorOf(element.color) }}
                    >
                      {drawElement(element)}
                    </g>
                  );
                })}
              </g>
            </svg>
          </div>
        ) : null}
        {notes.length ? (
          <div className={`chalk-panel overflow-y-auto px-2 py-3 ${viewBox && isWideFigure(viewBox) ? "max-h-60" : "max-h-[26rem]"}`}>
            <NotesPanel notes={notes} frame={frame} />
          </div>
        ) : null}
      </div>
    </BoardShell>
  );
}
