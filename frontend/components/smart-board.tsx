"use client";

// The smart board: the teacher speaks one sentence at a time while that sentence's maths is written in chalk.
// Voice and board stay in sync — a sentence ends, the next line is written. The student talking (or Pause)
// stops both. Without voice, the board still plays with captions on a timer.

import { useMemo } from "react";
import type { BoardScene, Language } from "@/lib/api";
import { useScenePlayer, type PlayerVoice } from "@/lib/use-scene-player";
import { BoardShell, PlayerBar } from "@/components/board-chrome";
import { MathText, MixedMath } from "@/components/math";

interface SmartBoardProps {
  scenes: BoardScene[];
  voice: PlayerVoice;
  language: Language;
  withVoice: boolean;
  autoPlay?: boolean;
  kicker?: string;
  title?: string;
  pinnedLine?: { line_no: number; latex: string } | null;
  pinnedLabel?: string;
}

export function SmartBoard({
  scenes,
  voice,
  language,
  withVoice,
  autoPlay = true,
  kicker = "Board",
  title,
  pinnedLine = null,
  pinnedLabel = "Your line",
}: SmartBoardProps) {
  const speeches = useMemo(() => scenes.map((scene) => scene.speech), [scenes]);
  const displays = useMemo(() => scenes.map((scene) => scene.voiceText ?? scene.text), [scenes]);
  const player = useScenePlayer({ speeches, displays, voice, language, withVoice, autoPlay });
  const { index: sceneIndex } = player;

  if (scenes.length === 0) return null;
  const current = scenes[sceneIndex];
  const written = scenes
    .slice(0, sceneIndex + 1)
    .flatMap((scene, index) => scene.maths.map((latex, part) => ({ latex, scene: index, key: `${index}-${part}` })));

  return (
    <BoardShell
      kicker={kicker}
      title={title}
      isSpeaking={player.isSpeaking}
      statusLabel={player.isPlaying ? "teaching" : "paused"}
      footer={
        <PlayerBar
          caption={<MixedMath text={current.text} />}
          index={sceneIndex}
          count={scenes.length}
          share={player.overallShare}
          isPlaying={player.isPlaying}
          captionsOnly={!player.speaksAloud}
          onPlay={player.play}
          onPause={player.pause}
          onSeek={player.goTo}
        />
      }
    >
      <div className="chalk-panel min-h-48 space-y-1.5 px-4 py-4 sm:px-6">
        {pinnedLine ? (
          <div
            className={`mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl px-3 py-2.5 transition duration-500 ${
              sceneIndex === 0 ? "bg-chalk-red/10" : ""
            }`}
          >
            <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-chalk-red">
              {pinnedLabel} {pinnedLine.line_no}
            </span>
            <span className="overflow-x-auto text-xl text-chalk/90 underline decoration-chalk-red decoration-wavy decoration-[1.5px] underline-offset-[10px]">
              <MathText latex={pinnedLine.latex} />
            </span>
          </div>
        ) : null}
        {written.length === 0 && !pinnedLine ? (
          <p className="py-8 text-center font-hand text-3xl text-chalk/30">listen…</p>
        ) : null}
        {written.map((line) => {
          const isCurrent = line.scene === sceneIndex;
          return (
            <div
              key={line.key}
              className={`board-write overflow-x-auto rounded-lg px-3 py-2 text-[1.35rem] transition-all duration-700 ${
                isCurrent ? "chalk-current text-chalk" : "text-chalk/45"
              }`}
            >
              <MathText latex={line.latex} />
            </div>
          );
        })}
      </div>
    </BoardShell>
  );
}

/** A solution (steps with explanations) as board scenes: each step is said while its line is written. */
export function scenesFromSolution(steps: { explain: string; latex: string | null; speech: string }[]): BoardScene[] {
  return steps.map((step) => ({
    text: step.explain || (step.latex ? `$${step.latex}$` : ""),
    speech: step.speech || step.explain,
    maths: step.latex ? [step.latex] : [],
    voiceText: step.latex ? `${step.explain} $${step.latex}$` : step.explain,
  }));
}
