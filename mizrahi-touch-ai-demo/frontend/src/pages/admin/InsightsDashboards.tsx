import { useSearchParams } from "react-router-dom";
import { useLang } from "../../i18n";
import { InsightsTab } from "./InsightsTab";
import { InsightsV2 } from "./InsightsV2";
import "./insightsV2.css";

/** Which presentation of "ביצועים ותובנות" is shown: `?dash=v2`, otherwise V1. A display choice only; it never touches
 *  the loan policy's versions. */
type Dash = "v1" | "v2";
const DASHES: [Dash, string][] = [["v1", "V1, מקורי"], ["v2", "V2, חדש"]];
const DASHES_EN: Record<Dash, string> = { v1: "V1, original", v2: "V2, new" };

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
  const { t } = useLang();
  return (
    <div className="ins2-switch" role="radiogroup" aria-label={t("תצוגת לוח הביצועים", "Performance dashboard view")} data-testid="dash-switch">
      <span className="ins2-switch-label">{t("תצוגת הלוח", "Dashboard view")}</span>
      {DASHES.map(([k, label]) => (
        <button key={k} type="button" role="radio" aria-checked={dash === k} className={dash === k ? "on" : ""}
          onClick={() => setDash(k)} data-testid={`dash-${k}`}>{t(label, DASHES_EN[k])}</button>
      ))}
    </div>
  );
}

export function InsightsDashboards(props: { activeGrace?: number; activeVersion?: number }) {
  const [dash] = useDash();
  return dash === "v2" ? <InsightsV2 {...props} /> : <InsightsTab {...props} />;
}
