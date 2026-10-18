"""Admin Settings in English: the service's own wording (validation errors, lint, publish reasons, rule labels, refusals)
gains `*_en` siblings when the app sends `X-MZ-Lang`, while every configuration the admin edits and posts back stays
byte-identical; without the header nothing changes."""
import copy
import json
import re

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from app.policy import store

BASE = "/api/admin/loan-completion"
client = TestClient(app)
STAFF = {"authorization": f"Bearer {auth.issue('staff', 'STAFF-DANA')}"}
EN = {**STAFF, "X-MZ-Lang": "en"}
HEBREW = re.compile(r"[֐-׿]")


def _dump(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def _bad_policy() -> dict:
    db.connect()
    store.ensure_seeded()
    config = copy.deepcopy(store.published("loan_policy")["config"])
    config["followup"]["call_window"]["days"] = ["SUN", "SAT"]
    config["talk"]["mode"] = "live"
    return config


def test_settings_configs_untouched_and_labels_translated():
    he = client.get(f"{BASE}/settings", headers=STAFF).json()
    en = client.get(f"{BASE}/settings", headers=EN).json()
    for key in ("published", "drafts", "requirement_catalog", "envelope", "prompt_variables", "preview_variables"):
        assert _dump(en[key]) == _dump(he[key]), key
    assert "canonical_en" not in he and en["canonical_en"]["requirements"]["PAYSLIPS"]["label"]
    assert en["environment"]["label_en"] == "Demo environment · Synthetic data"
    assert all(r.get("label_en") and not HEBREW.search(r["label_en"]) for r in en["locked_rules"])
    assert all(v.get("label_en") for v in en["rule_labels"].values())
    assert all(f.get("reason_en") for fields in en["locked_fields"].values() for f in fields)
    assert '_en"' not in _dump(he), "no English without the header"


def test_validate_report_messages_gain_english_config_parts_do_not():
    config = _bad_policy()
    body = {"kind": "loan_policy", "config": config}
    he = client.post(f"{BASE}/validate", headers=STAFF, json=body).json()
    en = client.post(f"{BASE}/validate", headers=EN, json=body).json()
    plain = client.post(f"{BASE}/validate", headers=STAFF, json=body).json()
    assert _dump(he) == _dump(plain) and "_en" not in _dump(he)
    for key in ("diff", "preview", "against"):
        assert _dump(en[key]) == _dump(he[key]), key
    assert he["errors"] and he["warnings"]
    for e in en["errors"] + en["warnings"]:
        if HEBREW.search(e["message"]):
            assert e.get("message_en") and not HEBREW.search(e["message_en"]), e
    stripped = {k: [{kk: vv for kk, vv in x.items() if not kk.endswith("_en")} for x in en[k]] for k in ("errors", "warnings", "lint")}
    assert _dump(stripped) == _dump({k: he[k] for k in ("errors", "warnings", "lint")})
    assert config == _bad_policy(), "the posted configuration is never modified"


def test_publish_reasons_and_refusals_in_english():
    draft = client.post(f"{BASE}/drafts", headers=STAFF, json={"kind": "loan_policy"}).json()
    try:
        he = client.post(f"{BASE}/drafts/{draft['version_id']}/validate", headers=STAFF).json()
        en = client.post(f"{BASE}/drafts/{draft['version_id']}/validate", headers=EN).json()
        assert he["reasons"] == en["reasons"] and "reasons_en" not in he
        assert en["reasons_en"] == ["No changes compared with the active version."]
        refused = client.post(f"{BASE}/drafts/{draft['version_id']}/publish", headers=EN, json={"revision": 999})
        assert refused.status_code == 409 and refused.json()["detail"]["message_en"].startswith("The draft was saved")
        plain = client.post(f"{BASE}/drafts/{draft['version_id']}/publish", headers=STAFF, json={"revision": 999})
        assert "message_en" not in plain.json()["detail"]
        missing = client.get(f"{BASE}/versions/NOPE/diff", headers=EN)
        assert missing.status_code == 404 and missing.json()["detail_en"] == "The version wasn't found"
    finally:
        store.discard_draft(draft["version_id"], store.get(draft["version_id"])["revision"], actor="tests")
