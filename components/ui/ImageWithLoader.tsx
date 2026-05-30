"use client";

import { useState } from "react";

type Props = {
  src: string;
  alt: string;
  className?: string;
};

export function ImageWithLoader({ src, alt, className = "" }: Props) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  return (
    <div className={`relative ${className}`}>
      {!loaded && !error && (
        <div className="absolute inset-0 bg-gray-100 animate-pulse rounded min-h-[120px]" />
      )}
      {error ? (
        <div className="bg-gray-100 text-gray-400 text-sm flex items-center justify-center min-h-[80px] rounded">
          Image unavailable
        </div>
      ) : (
        <img
          src={src}
          alt={alt}
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
          className={`max-w-full transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
        />
      )}
    </div>
  );
}
