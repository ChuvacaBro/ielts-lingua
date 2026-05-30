"use client";

import { useEffect, useRef, useState } from "react";

export type UseExamTimerOpts = {
  durationSec: number;
  onWarn10?: () => void;
  onWarn5?: () => void;
  onExpire: () => void;
  /** Pause is disabled by default (real exam doesn't allow it). */
  startImmediately?: boolean;
};

export function useExamTimer({
  durationSec,
  onWarn10,
  onWarn5,
  onExpire,
  startImmediately = true,
}: UseExamTimerOpts) {
  const [remaining, setRemaining] = useState(durationSec);
  const [running, setRunning] = useState(startImmediately);
  const warned10 = useRef(false);
  const warned5 = useRef(false);
  const fired = useRef(false);

  useEffect(() => {
    if (!running) return;
    const start = Date.now();
    const initial = remaining;
    const t = setInterval(() => {
      const left = initial - Math.floor((Date.now() - start) / 1000);
      setRemaining(Math.max(0, left));
      if (!warned10.current && left <= 600 && left > 595) {
        warned10.current = true;
        onWarn10?.();
      }
      if (!warned5.current && left <= 300 && left > 295) {
        warned5.current = true;
        onWarn5?.();
      }
      if (left <= 0 && !fired.current) {
        fired.current = true;
        onExpire();
        clearInterval(t);
      }
    }, 1000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  function start() {
    setRunning(true);
  }

  return { remaining, running, start };
}

export function formatMMSS(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}
