/** The Touch progress ring: orange arc over a dashed grey track, step and label in the middle.
 *  `compact` draws the small ring of the home-screen stage card: the step only, the label sits beside it. */
export function StageRing({ step, of, label, compact = false }: { step: number; of: number; label: string; compact?: boolean }) {
  const size = compact ? 78 : 176;
  const r = 74;
  const c = 2 * Math.PI * r;
  const progress = Math.max(0.04, Math.min(1, step / of));
  const ticks = Array.from({ length: compact ? 40 : 64 }, (_, i) => i);
  return (
    <div className={`ring-wrap${compact ? " compact" : ""}`} role="img" aria-label={`שלב ${step} מתוך ${of}: ${label}`}>
      <svg width={size} height={size} viewBox="0 0 176 176" aria-hidden>
        {ticks.map((i) => {
          const a = (i / ticks.length) * Math.PI * 2;
          const x1 = 88 + Math.cos(a) * 66, y1 = 88 + Math.sin(a) * 66;
          const x2 = 88 + Math.cos(a) * 82, y2 = 88 + Math.sin(a) * 82;
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#d4d8de" strokeWidth={compact ? 4 : 2} strokeLinecap="round" />;
        })}
        <defs>
          <linearGradient id="ringGrad" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#ffb26b" />
            <stop offset="1" stopColor="#ff780b" />
          </linearGradient>
        </defs>
        <circle cx="88" cy="88" r={r} fill="none" stroke="url(#ringGrad)" strokeWidth={compact ? 14 : 10} strokeLinecap="round"
          strokeDasharray={`${c * progress} ${c}`} transform="rotate(-90 88 88)" />
        <circle cx={88 + Math.cos(progress * 2 * Math.PI - Math.PI / 2) * r} cy={88 + Math.sin(progress * 2 * Math.PI - Math.PI / 2) * r}
          r={compact ? 10 : 6} fill="#fff" stroke="#ff780b" strokeWidth={compact ? 5 : 3} />
      </svg>
      <div className="ring-center" aria-hidden>
        <div className="ring-step"><span className="ltr">{step}/{of}</span></div>
        {!compact && <>
          <div className="ring-label">{label.split(" ").slice(0, 1).join(" ")}<br />{label.split(" ").slice(1).join(" ")}</div>
          <div className="ring-tag">שלב במערכת הבנק</div>
        </>}
      </div>
    </div>
  );
}
