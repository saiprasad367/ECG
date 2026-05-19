import { useMemo, useEffect, useState } from "react";
import { motion } from "framer-motion";

interface ParticlesProps {
  count?: number;
  className?: string;
}

export function Particles({ count = 24, className }: ParticlesProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const dots = useMemo(
    () => {
      if (!mounted) return [];
      return Array.from({ length: count }, (_, i) => ({
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: 2 + Math.random() * 5,
        delay: Math.random() * 4,
        dur: 5 + Math.random() * 6,
        hue: ["#3b82f6", "#06b6d4", "#8b5cf6", "#10b981"][i % 4],
      }));
    },
    [count, mounted],
  );

  if (!mounted) {
    return null;
  }

  return (
    <div className={`pointer-events-none absolute inset-0 overflow-hidden ${className ?? ""}`}>
      {dots.map((d, i) => (
        <motion.span
          key={i}
          className="absolute rounded-full blur-[1px]"
          style={{
            left: `${d.x}%`,
            top: `${d.y}%`,
            width: d.size,
            height: d.size,
            background: d.hue,
            opacity: 0.5,
          }}
          animate={{ y: [0, -30, 0], opacity: [0.2, 0.8, 0.2] }}
          transition={{ duration: d.dur, delay: d.delay, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}

