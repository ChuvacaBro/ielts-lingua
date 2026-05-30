"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Plays an audio source ONCE through, with no seeking and no pause control.
 * Mimics the real exam: you can adjust volume only.
 *
 * Surfaces loading/network errors to the user instead of failing silently —
 * the remote source (practicepteonline.com) often refuses cross-origin
 * playback unless the file has been downloaded locally via
 * `npm run fetch:audio` (or placed manually in public/audio/<id>.mp3).
 */
export function OnceAudio({
  src,
  onEnded,
  onLoadedMetadata,
  onTimeUpdate,
}: {
  src: string;
  onEnded?: () => void;
  onLoadedMetadata?: (durationSec: number) => void;
  onTimeUpdate?: (currentTime: number) => void;
}) {
  const ref = useRef<HTMLAudioElement>(null);
  const [started, setStarted] = useState(false);
  const [volume, setVolume] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const isLocal = src.startsWith("/audio/");

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Block backward seeks while playing; allow native forward (none from UI).
    const onSeek = () => {
      if (started && el.currentTime > 0) {
        // no-op: HTML5 `seeking` isn't cancelable, but we hide controls anyway
      }
    };
    el.addEventListener("seeking", onSeek);
    return () => el.removeEventListener("seeking", onSeek);
  }, [started]);

  async function handlePlay() {
    setError(null);
    const el = ref.current;
    if (!el) return;
    try {
      await el.play();
      setStarted(true);
    } catch (e) {
      setError(
        `Couldn't start audio: ${(e as Error).message}. ` +
          (isLocal
            ? "Check that the MP3 exists in public/audio/."
            : "The remote site may be blocking the request. Run `npm run fetch:audio` to download it locally, or place an MP3 at public/audio/" +
              src.split("/").pop()),
      );
    }
  }

  return (
    <div className="border border-exam-border p-3 bg-gray-50">
      <div className="flex items-center gap-3">
        <button
          className="bg-exam-accent text-white px-3 py-1 text-sm disabled:opacity-50"
          onClick={handlePlay}
          disabled={started}
        >
          {started ? "Playing…" : "▶ Start audio"}
        </button>
        <span className="text-xs text-gray-600">
          Once playing, you cannot pause or rewind — exactly like the real exam.
        </span>
        <span className="text-xs text-gray-500 ml-2">
          source: {isLocal ? "local file" : "remote URL"}
        </span>
        <label className="ml-auto text-xs flex items-center gap-1">
          Vol
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={volume}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              setVolume(v);
              if (ref.current) ref.current.volume = v;
            }}
          />
        </label>
      </div>
      {error && (
        <div className="mt-2 text-sm text-red-700 bg-red-50 border border-red-300 p-2">
          {error}
          <details className="mt-1 text-xs text-gray-700">
            <summary className="cursor-pointer">Show full URL</summary>
            <code className="break-all">{src}</code>
          </details>
        </div>
      )}
      <audio
        ref={ref}
        src={src}
        // `preload="auto"` triggers the network request immediately so we
        // surface 4xx/hotlink errors before the user clicks Play.
        // (No `crossOrigin` — that would force CORS and break cross-origin
        // playback for sites that don't send CORS headers.)
        preload="auto"
        onError={(e) => {
          const el = e.currentTarget as HTMLAudioElement;
          const code = el.error?.code;
          const codes: Record<number, string> = {
            1: "MEDIA_ERR_ABORTED",
            2: "MEDIA_ERR_NETWORK",
            3: "MEDIA_ERR_DECODE",
            4: "MEDIA_ERR_SRC_NOT_SUPPORTED (likely 4xx, CORS, or hotlink-blocked)",
          };
          setError(`Audio load failed: ${code ? codes[code] : "unknown error"}.`);
        }}
        onEnded={onEnded}
        onLoadedMetadata={(e) =>
          onLoadedMetadata?.((e.target as HTMLAudioElement).duration)
        }
        onTimeUpdate={(e) =>
          onTimeUpdate?.((e.target as HTMLAudioElement).currentTime)
        }
      />
    </div>
  );
}
