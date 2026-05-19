import { useId } from "react";

interface ECGWaveProps {
  className?: string;
  color?: string;
  strokeWidth?: number;
  speed?: number;
}

/** Continuously scrolling ECG-style waveform built with SVG. */
export function ECGWave({
  className,
  color = "#2563eb",
  strokeWidth = 2,
  speed = 6,
}: ECGWaveProps) {
  const id = useId();
  // Repeating QRS-ish path
  const beat =
    "l40 0 l8 -6 l6 14 l8 -42 l8 60 l8 -26 l10 0 l30 0 l8 -4 l6 8 l8 -10 l8 4 l40 0";
  const path = `M0 60 ${beat} ${beat} ${beat} ${beat}`;
  return (
    <svg
      viewBox="0 0 800 120"
      preserveAspectRatio="none"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id={`g-${id}`} x1="0" x2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0" />
          <stop offset="20%" stopColor={color} stopOpacity="0.9" />
          <stop offset="80%" stopColor={color} stopOpacity="0.9" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <g style={{ animation: `dash-flow ${speed}s linear infinite` }}>
        <path
          d={path}
          fill="none"
          stroke={`url(#g-${id})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="2000"
        />
      </g>
    </svg>
  );
}
