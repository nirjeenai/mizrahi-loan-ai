import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCase } from "../../caseContext";
import { followupApi } from "../../followupApi";

/** The secure completion link a (simulated) JEEN Talk call or message sends: /customer/link#t=<token>. The token stays
 *  in the fragment (never sent as a URL); the server redeems it into a session for that one case and names the
 *  requirement to complete, which opens its upload. */
export function LinkLanding() {
  const nav = useNavigate();
  const { setCaseId, reload } = useCase();
  const [state, setState] = useState<"checking" | "expired" | "invalid">("checking");
  useEffect(() => {
    const token = new URLSearchParams(window.location.hash.slice(1)).get("t") || "";
    history.replaceState(null, "", window.location.pathname);          // the token leaves the address bar at once
    followupApi.redeem(token).then((r) => {
      if ((r.state === "ok" || r.state === "resolved") && r.case_id && r.target) {
        setCaseId(r.case_id);
        reload();
        nav(r.state === "ok" ? r.target : "/customer/documents", { replace: true });
      } else setState(r.state === "expired" ? "expired" : "invalid");
    }).catch(() => setState("invalid"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="card" style={{ marginTop: 16 }} data-testid="link-landing" data-state={state}>
      {state === "checking" ? <><span className="spinner" /> פותחים את הקישור המאובטח…</>
        : state === "expired" ? "תוקף הקישור פג. אפשר להשלים את המסמכים ישירות מכאן, במסמכים."
          : "הקישור אינו תקין. אפשר להשלים את המסמכים ישירות מכאן, במסמכים."}
    </div>
  );
}
