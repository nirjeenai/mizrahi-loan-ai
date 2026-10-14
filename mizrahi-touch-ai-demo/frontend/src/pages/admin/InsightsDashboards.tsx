import { useSearchParams } from "react-router-dom";
import { InsightsTab } from "./InsightsTab";
import { InsightsV2 } from "./InsightsV2";
import "./insightsV2.css";

/** Which presentation of "ביצועים ותובנות" is shown: `?dash=v2`, otherwise V1. A display choice only; it never touches
 *  the loan policy's versions. */
type Dash = "v1" | "v2";
const DASHES: [Dash, string][] = [["v1", "V1 — מקורי"], ["v2", "V2 — חדש"]];

function useDash(): [Dash, (d: Dash) => void] {
  const [params, setParams] = useSearchParams();
  const dash: Dash = params.get("dash") === "v2" ? "v2" : "v1";
  const set = (d: Dash) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    if (d === "v1") next.delete("dash"); else next.set("dash", d);
    return next;
  }, { replace: true });
  return [dash, set];
}

export function DashSwitch() {
  const [dash, setDash] = useDash();
  return (
    <div className="ins2-switch" role="radiogroup" aria-label="תצוגת לוח הביצועים" data-testid="dash-switch">
      <span className="ins2-switch-label">תצוגת הלוח</span>
      {DASHES.map(([k, label]) => (
        <button key={k} type="button" role="radio" aria-checked={dash === k} className={dash === k ? "on" : ""}
          onClick={() => setDash(k)} data-testid={`dash-${k}`}>{label}</button>
      ))}
    </div>
  );
}

export function InsightsDashboards(props: { activeGrace?: number; activeVersion?: number }) {
  const [dash] = useDash();
  return dash === "v2" ? <InsightsV2 {...props} /> : <InsightsTab {...props} />;
}
