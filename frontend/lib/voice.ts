"use client";

// Voice for the tutor.
//   Listen: tap the mic once, speak; recording stops by itself when you pause. The audio is turned into a
//           16 kHz WAV (every speech API accepts it) and sent to Sarvam through the backend.
//   Speak:  the tutor's reply is spoken by Sarvam's Indian voice. The student talking stops it (barge-in).
// If the server has no Sarvam key, the browser's own speech is used. Every failure is shown; typing always works.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Language } from "@/lib/api";

export type VoiceStatus = "idle" | "listening" | "transcribing" | "speaking";
type Provider = "loading" | "sarvam" | "browser" | "none";

const SAMPLE_RATE = 16000;
const SPEECH_LEVEL = 0.02; // loudness that counts as talking
const PAUSE_MS = 1300; // quiet this long after talking = done
const GIVE_UP_MS = 7000; // nothing said at all
const MAX_MS = 30000;

class VoiceError extends Error {}

// ---------- recording one answer ----------

async function recordAnswer(
  onSpeechStart: () => void,
  stopRef: { current: (() => void) | null },
): Promise<{ wav: Blob | null }> {
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    throw new VoiceError("This browser cannot record audio. Please type instead.");
  }
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch (error) {
    const blocked =
      error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "SecurityError");
    throw new VoiceError(
      blocked
        ? "Microphone is blocked. Allow the mic for this site (address bar → site settings), or type instead."
        : "Could not start the microphone. Please type instead.",
    );
  }
  const recorder = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  const context = new AudioContext();
  const analyser = context.createAnalyser();
  context.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  const startedAt = performance.now();
  let heardSpeech = false;
  let lastLoudAt = startedAt;
  const stop = () => recorder.state === "recording" && recorder.stop();
  stopRef.current = stop;

  const timer = window.setInterval(() => {
    analyser.getFloatTimeDomainData(samples);
    const loudness = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
    const now = performance.now();
    if (loudness > SPEECH_LEVEL) {
      if (!heardSpeech) onSpeechStart();
      heardSpeech = true;
      lastLoudAt = now;
    }
    if (
      (heardSpeech && now - lastLoudAt > PAUSE_MS) ||
      (!heardSpeech && now - startedAt > GIVE_UP_MS) ||
      now - startedAt > MAX_MS
    ) {
      stop();
    }
  }, 100);

  return new Promise((resolve, reject) => {
    recorder.ondataavailable = (event) => chunks.push(event.data);
    recorder.onstop = async () => {
      window.clearInterval(timer);
      stream.getTracks().forEach((track) => track.stop());
      try {
        if (!heardSpeech) return resolve({ wav: null });
        const decoded = await context.decodeAudioData(await new Blob(chunks).arrayBuffer());
        const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * SAMPLE_RATE), SAMPLE_RATE);
        const source = offline.createBufferSource();
        source.buffer = decoded;
        source.connect(offline.destination);
        source.start();
        resolve({ wav: encodeWav((await offline.startRendering()).getChannelData(0)) });
      } catch {
        reject(new VoiceError("Could not process the recording. Please try again or type."));
      } finally {
        void context.close();
      }
    };
    recorder.start();
  });
}

export function encodeWav(samples: Float32Array): Blob {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const text = (offset: number, value: string) =>
    [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true); // PCM header size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, SAMPLE_RATE, true);
  view.setUint32(28, SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, index) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + index * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return new Blob([view.buffer], { type: "audio/wav" });
}

// ---------- the hook used by the tutor ----------

interface BrowserRecognition {
  lang: string;
  onresult: ((event: { results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

function getBrowserRecognition(): (new () => BrowserRecognition) | null {
  const speechWindow = window as unknown as Record<string, (new () => BrowserRecognition) | undefined>;
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

const LOCALES: Record<Language, string> = { en: "en-IN", hinglish: "hi-IN" };

export function useVoice() {
  const [provider, setProvider] = useState<Provider>("loading");
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const finishRef = useRef<((completed: boolean) => void) | null>(null); // ends the sentence being spoken
  const audioCacheRef = useRef(new Map<string, Promise<string>>()); // Sarvam audio per sentence, fetched ahead

  useEffect(() => {
    const fallback = () => (getBrowserRecognition() && "speechSynthesis" in window ? "browser" : "none");
    api
      .voiceMode()
      .then((mode) => setProvider(mode.provider === "sarvam" ? "sarvam" : fallback()))
      .catch(() => setProvider(fallback()));
  }, []);

  const stopSpeaking = useCallback(() => {
    const finish = finishRef.current;
    finishRef.current = null;
    finish?.(false); // tell the smart board this sentence was interrupted
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    audioRef.current?.pause();
    setStatus((current) => (current === "speaking" ? "idle" : current));
  }, []);

  const fetchAudio = useCallback((text: string, language: Language): Promise<string> => {
    const key = `${language}|${text}`;
    const cache = audioCacheRef.current;
    if (!cache.has(key)) {
      const request = api.speak(text, language).then((result) => `data:audio/wav;base64,${result.audio_base64}`);
      request.catch(() => cache.delete(key)); // a failed fetch is retried next time
      cache.set(key, request);
    }
    return cache.get(key) as Promise<string>;
  }, []);

  /** Fetch the audio of the next sentences while the current one plays, so the board never waits. */
  const prefetch = useCallback(
    (texts: string[], language: Language) => {
      if (provider !== "sarvam") return;
      texts.forEach((text) => void fetchAudio(text, language).catch(() => undefined));
    },
    [provider, fetchAudio],
  );

  /** Speak one sentence. Resolves true when it finished, false when it was interrupted or failed.
   * onProgress(0..1) lets the board move its caption bar in time with the voice.
   * serverText: the sentence as displayed (maths in $...$) — the server turns it into teacher-speak for Sarvam. */
  const speakAndWait = useCallback(
    (
      text: string,
      language: Language,
      onProgress?: (share: number) => void,
      serverText?: string,
    ): Promise<boolean> => {
      if (provider !== "sarvam" && provider !== "browser") return Promise.resolve(false);
      stopSpeaking();
      return new Promise<boolean>((resolve) => {
        let isDone = false;
        const finish = (completed: boolean) => {
          if (isDone) return;
          isDone = true;
          if (finishRef.current === finish) finishRef.current = null;
          setStatus((current) => (current === "speaking" ? "idle" : current));
          resolve(completed);
        };
        finishRef.current = finish;
        setStatus("speaking");
        if (provider === "browser") {
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.lang = LOCALES[language];
          utterance.rate = 0.95;
          utterance.onboundary = (event) => onProgress?.(Math.min(1, event.charIndex / Math.max(1, text.length)));
          utterance.onend = () => {
            onProgress?.(1);
            finish(true);
          };
          utterance.onerror = () => finish(false);
          window.speechSynthesis.speak(utterance);
          return;
        }
        fetchAudio(serverText ?? text, language)
          .then(async (url) => {
            if (isDone) return;
            const audio = new Audio(url);
            audioRef.current = audio;
            audio.ontimeupdate = () => audio.duration && onProgress?.(audio.currentTime / audio.duration);
            audio.onended = () => {
              onProgress?.(1);
              finish(true);
            };
            audio.onerror = () => finish(false);
            await audio.play();
          })
          .catch((caught: unknown) => {
            const blocked = caught instanceof DOMException && caught.name === "NotAllowedError";
            setError(
              blocked
                ? "Your browser blocked the voice. Press ▶ on the board to hear it."
                : "Could not play the voice. The board and text still work.",
            );
            finish(false);
          });
      });
    },
    [provider, stopSpeaking, fetchAudio],
  );

  const speak = useCallback(
    async (text: string, language: Language) => {
      if (provider !== "sarvam" && provider !== "browser") return;
      stopSpeaking();
      try {
        if (provider === "browser") {
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.lang = LOCALES[language];
          utterance.onend = () => setStatus("idle");
          setStatus("speaking");
          window.speechSynthesis.speak(utterance);
          return;
        }
        const { audio_base64 } = await api.speak(text, language);
        const audio = new Audio(`data:audio/wav;base64,${audio_base64}`);
        audioRef.current = audio;
        audio.onended = () => setStatus("idle");
        setStatus("speaking");
        await audio.play();
      } catch (caught) {
        setStatus("idle");
        const blocked = caught instanceof DOMException && caught.name === "NotAllowedError";
        setError(
          blocked
            ? "Your browser blocked the voice. Tap 🔊 on the message to hear it."
            : "Could not play the voice. The text is still here.",
        );
      }
    },
    [provider, stopSpeaking],
  );

  const listen = useCallback(
    async (language: Language, onText: (text: string) => void) => {
      stopSpeaking(); // the student talks, the tutor stops
      setError(null);
      try {
        if (provider === "browser") {
          const Recognition = getBrowserRecognition();
          if (!Recognition) throw new VoiceError("This browser cannot listen. Please type instead.");
          const recognition = new Recognition();
          recognition.lang = LOCALES[language];
          recognition.onresult = (event) => onText(event.results[0][0].transcript.trim());
          recognition.onerror = () => setError("Could not hear you. Allow the mic, or type instead.");
          recognition.onend = () => setStatus("idle");
          stopRef.current = () => recognition.stop();
          setStatus("listening");
          recognition.start();
          return;
        }
        if (provider !== "sarvam") throw new VoiceError("Voice is not available here. Please type instead.");
        setStatus("listening");
        const { wav } = await recordAnswer(stopSpeaking, stopRef);
        if (!wav) throw new VoiceError("I could not hear anything. Tap the mic and speak a little louder.");
        setStatus("transcribing");
        const { text } = await api.listen(wav, language);
        setStatus("idle");
        if (text.trim()) onText(text.trim());
        else setError("I could not catch that. Please say it again or type it.");
      } catch (caught) {
        setStatus("idle");
        setError(
          caught instanceof VoiceError || caught instanceof ApiError
            ? caught.message
            : "Voice did not work this time. Please type.",
        );
      }
    },
    [provider, stopSpeaking],
  );

  const stopListening = useCallback(() => stopRef.current?.(), []);

  useEffect(() => stopSpeaking, [stopSpeaking]);

  return {
    canTalk: provider === "sarvam" || provider === "browser",
    status,
    error,
    clearError: () => setError(null),
    speak,
    speakAndWait,
    prefetch,
    stopSpeaking,
    listen,
    stopListening,
  };
}
