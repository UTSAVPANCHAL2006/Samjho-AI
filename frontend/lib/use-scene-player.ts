"use client";

// Plays a list of scenes one after another, in sync with the voice: speak scene N, then show scene N + 1.
// Used by the smart board and the concept visual. Without voice, scenes advance on a reading-speed timer.

import { useEffect, useRef, useState } from "react";
import type { Language } from "@/lib/api";

export type PlayerVoice = {
  canTalk: boolean;
  status: string;
  speakAndWait: (
    text: string,
    language: Language,
    onProgress?: (share: number) => void,
    serverText?: string,
  ) => Promise<boolean>;
  prefetch: (texts: string[], language: Language) => void;
  stopSpeaking: () => void;
};

const MS_PER_CHARACTER = 55;
const MIN_SCENE_MS = 1800;

function waitWithProgress(ms: number, onProgress: (share: number) => void, isCancelled: () => boolean) {
  return new Promise<boolean>((resolve) => {
    const startedAt = performance.now();
    const timer = window.setInterval(() => {
      if (isCancelled()) {
        window.clearInterval(timer);
        resolve(false);
        return;
      }
      const share = Math.min(1, (performance.now() - startedAt) / ms);
      onProgress(share);
      if (share >= 1) {
        window.clearInterval(timer);
        resolve(true);
      }
    }, 60);
  });
}

export function useScenePlayer({
  speeches,
  displays,
  voice,
  language,
  withVoice,
  autoPlay,
}: {
  speeches: string[]; // read by the browser voice (maths already in words)
  displays?: string[]; // the same sentences as shown (maths in $...$), sent to the server voice
  voice: PlayerVoice;
  language: Language;
  withVoice: boolean;
  autoPlay: boolean;
}) {
  const [index, setIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [progress, setProgress] = useState(0);
  const [hasStarted, setHasStarted] = useState(autoPlay);
  const runRef = useRef(0);
  const { speakAndWait, prefetch, stopSpeaking, canTalk } = voice;
  const speaksAloud = withVoice && canTalk;
  const count = speeches.length;

  useEffect(() => {
    if (speaksAloud) prefetch(displays ?? speeches, language);
  }, [speeches, displays, language, speaksAloud, prefetch]);

  useEffect(() => {
    const speech = speeches[index];
    if (!isPlaying || speech === undefined) return;
    const run = ++runRef.current;
    let isCancelled = false;
    const onProgress = (share: number) => {
      if (runRef.current === run) setProgress(share);
    };
    void (async () => {
      const completed = speaksAloud
        ? await speakAndWait(speech, language, onProgress, displays?.[index])
        : await waitWithProgress(Math.max(MIN_SCENE_MS, speech.length * MS_PER_CHARACTER), onProgress, () => isCancelled);
      if (isCancelled || runRef.current !== run) return;
      if (!completed) {
        setIsPlaying(false); // the student started talking, Pause was pressed, or the voice failed
        return;
      }
      if (index + 1 < count) {
        setProgress(0);
        setIndex(index + 1);
      } else {
        setIsPlaying(false);
      }
    })();
    return () => {
      isCancelled = true;
    };
  }, [isPlaying, index, speeches, displays, count, language, speaksAloud, speakAndWait]);

  useEffect(() => () => stopSpeaking(), [stopSpeaking]);

  return {
    index,
    isPlaying,
    hasStarted,
    progress,
    speaksAloud,
    isSpeaking: isPlaying && (!speaksAloud || voice.status === "speaking"),
    overallShare: count ? (index + (hasStarted ? progress : 0)) / count : 0,
    play() {
      setHasStarted(true);
      if (index >= count - 1 && progress >= 1) {
        setIndex(0);
        setProgress(0);
      }
      setIsPlaying(true);
    },
    pause() {
      setIsPlaying(false);
      stopSpeaking();
    },
    goTo(target: number) {
      stopSpeaking();
      setHasStarted(true);
      setProgress(0);
      setIndex(Math.max(0, Math.min(count - 1, target)));
      setIsPlaying(true);
    },
  };
}
