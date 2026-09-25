// Line icons (24 px grid, stroke = currentColor).
import type { ReactNode } from 'react';

const I = ({ children }: { children: ReactNode }) => (
  <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{children}</svg>
);

export const Icon = {
  play: () => <I><path d="M7 5v14l11-7z" /></I>,
  flag: () => <I><path d="M5 21V4" /><path d="M5 4h11l-2 4 2 4H5" /></I>,
  map: () => <I><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z" /><path d="M9 4v14M15 6v14" /></I>,
  camera: () => <I><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></I>,
  car: () => <I><path d="M4 16v-4l2-5h12l2 5v4" /><path d="M3 16h18v3H3z" /><circle cx="7.5" cy="19" r="1.5" /><circle cx="16.5" cy="19" r="1.5" /><path d="M6 12h12" /></I>,
  sun: () => <I><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></I>,
  moon: () => <I><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" /></I>,
  beamLow: () => <I><path d="M9 6a6 6 0 0 0 0 12z" /><path d="M13 9l7 2M13 13l7 2M13 17l7 2" /></I>,
  beamHigh: () => <I><path d="M9 6a6 6 0 0 0 0 12z" /><path d="M13 8h8M13 12h8M13 16h8" /></I>,
  beamOff: () => <I><path d="M9 6a6 6 0 0 0 0 12z" /><path d="M4 4l16 16" /></I>,
  gear: () => <I><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></I>,
  keys: () => <I><rect x="2" y="6" width="20" height="12" rx="2" /><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" /></I>,
  music: () => <I><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></I>,
  timer: () => <I><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2 2M9 2h6" /></I>,
  home: () => <I><path d="M3 11 12 4l9 7" /><path d="M5 10v10h14V10" /></I>,
  book: () => <I><path d="M4 5a2 2 0 0 1 2-2h14v16H6a2 2 0 0 0-2 2z" /><path d="M4 19V5" /></I>,
  chevL: () => <I><path d="M15 6l-6 6 6 6" /></I>,
  chevR: () => <I><path d="M9 6l6 6-6 6" /></I>,
  rec: () => <I><circle cx="12" cy="12" r="6" /></I>,
  mountain: () => <I><path d="M3 20 9.5 8l4 7 2.5-4L21 20z" /></I>,
  winch: () => <I><circle cx="8" cy="12" r="4" /><path d="M12 12h9M18 9v6" /></I>,
};

/** brand mark: pine over a ridge line */
export function BrandMark({ size = 46 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <defs>
        <linearGradient id="bm" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f6c066" />
          <stop offset="1" stopColor="#e46f3c" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="46" height="46" rx="13" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.18)" />
      <path d="M6 36 17 22l6 8 5-6 14 12z" fill="url(#bm)" opacity="0.9" />
      <path d="M31 8l6 10h-3l5 8h-4l4 7H23l4-7h-4l5-8h-3z" fill="#7fd3c4" />
      <rect x="30" y="33" width="2" height="4" fill="#7fd3c4" />
    </svg>
  );
}
