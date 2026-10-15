"use client";

import { useEffect, useState } from "react";
import { Car } from "lucide-react";

export default function ProductImage({ src, alt, className = "", priority = false }: {
  src: string; alt: string; className?: string; priority?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (failed) return <div className={`image-unavailable ${className}`}><Car size={40} strokeWidth={1} /><span>暂无图片</span></div>;
  // Remote catalog assets have variable dimensions; the parent owns their stable aspect ratio.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt={alt} className={className} loading={priority ? "eager" : "lazy"} onError={() => setFailed(true)} />;
}
