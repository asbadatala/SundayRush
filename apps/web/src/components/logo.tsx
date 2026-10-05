/** Football-with-laces mark. (The browser-tab icon, src/app/icon.svg, is the "SR" monogram.) */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <ellipse cx="16" cy="16" rx="14" ry="8.5" transform="rotate(-35 16 16)" className="fill-pigskin" />
      <g className="stroke-white" strokeLinecap="round" fill="none">
        <path d="M12 20L20 12M13 17l2 2M15 15l2 2M17 13l2 2" strokeWidth="1.6" />
        <path d="M6.5 13.5l1.6 2.6M23.9 15.9l1.6 2.6" strokeWidth="1.4" opacity="0.8" />
      </g>
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="font-heading text-[22px] leading-none font-bold tracking-[0.04em] uppercase">
      Sunday<span className="text-primary">Rush</span>
    </span>
  );
}
