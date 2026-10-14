"""List files an agent changed outside its scope (docs/plans/parallel/README.md › Ownership).

    python3 docs/plans/parallel/check_scope.py B      # or C; run inside the agent's worktree

Compares the working tree (committed and uncommitted, including untracked files) with `parallel/scope-v2` (or
`parallel/base` while that ref does not exist). Prints OK or
the offending paths and exits 1. App.tsx is allowed for C but its diff is printed for review."""
from __future__ import annotations

import fnmatch
import subprocess
import sys

P = "mizrahi-touch-ai-demo/"
SHARED = [P + "backend/tests/test_parallel_contracts.py", P + "docs/plans/parallel/CONTRACTS.md",
          P + "backend/app/db.py", P + "backend/app/events.py"]
SCOPE = {
    "B": [P + p for p in ("backend/app/clock.py", "backend/app/followup/*", "backend/app/comms/*",
                          "backend/app/api/followup.py", "backend/app/capabilities.py", "backend/app/flags.py",
                          "backend/policy/scenarios/*", "backend/tests/test_followup_*.py", "backend/tests/test_talk_*.py",
                          "backend/tests/test_upload_links.py", "backend/tests/test_clock.py",
                          "docs/plans/parallel/NOTES-agent-B.md", "docs/plans/07-jeen-talk-handoff.md")],
    "C": [P + p for p in ("backend/app/api/admin.py", "backend/app/policy/validate.py", "backend/app/policy/simulator.py",
                          "backend/app/policy/prompts.py", "backend/app/policy/proposal.py", "backend/app/policy/store.py",
                          "backend/tests/test_admin_*.py", "frontend/src/pages/admin/*", "frontend/src/adminApi.ts",
                          "frontend/src/admin.css", "frontend/src/App.tsx", "e2e/test_admin_ui.py",
                          "docs/plans/parallel/NOTES-agent-C.md")],
}
# merged from Agent B at gate G1: present in C's tree, owned by B
FROM_G1 = SCOPE["B"]


def git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    agent = (sys.argv[1:] or [""])[0].upper()
    if agent not in SCOPE:
        print(__doc__)
        return 2
    base = "parallel/scope-v2" if git("branch", "--list", "parallel/scope-v2") else "parallel/base"
    changed = set(git("diff", "--name-only", base)) | set(git("ls-files", "--others", "--exclude-standard"))
    allowed = SCOPE[agent] + SHARED
    if agent == "C":
        g1 = set(git("diff", "--name-only", base, "parallel/g1-evaluator")) if git("branch", "--list", "parallel/g1-evaluator") else set()
        changed -= {f for f in g1 if any(fnmatch.fnmatch(f, pat) for pat in FROM_G1)}
    outside = sorted(f for f in changed if not any(fnmatch.fnmatch(f, pat) for pat in allowed))
    if agent == "C" and P + "frontend/src/App.tsx" in changed:
        print("\n".join(git("diff", base, "--", P + "frontend/src/App.tsx")))
    if outside:
        print("OUTSIDE SCOPE:\n  " + "\n  ".join(outside))
        return 1
    print(f"OK — {len(changed)} changed path(s), all in Agent {agent}'s scope or the shared additive files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
