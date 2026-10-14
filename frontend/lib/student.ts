"use client";

// Who is studying on this device (name + class, no login). Several children can share a phone: "Switch".

import { useEffect, useState, useSyncExternalStore } from "react";
import { api, ApiError, type Language, type Progress, type Student } from "@/lib/api";

const STUDENT_KEY = "samjho.student";
const LANGUAGE_KEY = "samjho.language";
const CHANGED_EVENT = "samjho:student-changed";

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // private mode: the app still works, just without history
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // ignore: it is only not remembered
  }
}

let cachedJson: string | null = null;
let cachedStudent: Student | null = null;

export function readStudent(): Student | null {
  const json = readStorage(STUDENT_KEY);
  if (json !== cachedJson) {
    cachedJson = json;
    try {
      cachedStudent = json ? (JSON.parse(json) as Student) : null;
    } catch {
      cachedStudent = null;
    }
  }
  return cachedStudent;
}

function saveStudent(student: Student | null) {
  writeStorage(STUDENT_KEY, student ? JSON.stringify(student) : null);
  window.dispatchEvent(new Event(CHANGED_EVENT));
}

export async function signIn(name: string, classLevel: number): Promise<Student> {
  const student = await api.createStudent(name, classLevel);
  saveStudent(student);
  return student;
}

export const switchStudent = () => saveStudent(null);

/** The student's id, creating a guest profile on first use so checks still count. Never throws. */
export async function ensureStudentId(classLevel: number): Promise<string | null> {
  const student = readStudent();
  if (student) return student.id;
  try {
    return (await signIn("Student", classLevel)).id;
  } catch {
    return null;
  }
}

function watchStudent(onChange: () => void) {
  window.addEventListener(CHANGED_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGED_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useStudent(): Student | null {
  return useSyncExternalStore(watchStudent, readStudent, () => null);
}

/** Streak, totals and chapters for the current student (null while loading or signed out). */
export function useProgress(student: Student | null): Progress | null {
  const [loaded, setLoaded] = useState<{ studentId: string; progress: Progress } | null>(null);
  useEffect(() => {
    let isCurrent = true;
    if (student) {
      api
        .getProgress(student.id)
        .then((progress) => isCurrent && setLoaded({ studentId: student.id, progress }))
        .catch((error: unknown) => {
          // The server no longer knows this student (e.g. a reset database): start a fresh profile.
          if (error instanceof ApiError && error.status === 404) switchStudent();
        });
    }
    return () => {
      isCurrent = false;
    };
  }, [student]);
  // Never show the previous student's numbers after a switch.
  return student && loaded?.studentId === student.id ? loaded.progress : null;
}

export function readLanguage(): Language {
  return readStorage(LANGUAGE_KEY) === "en" ? "en" : "hinglish";
}

export const saveLanguage = (language: Language) => writeStorage(LANGUAGE_KEY, language);
