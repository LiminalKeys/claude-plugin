# claude-plugin — agent instructions

## CI runners (org policy)

LiminalKeys uses **self-hosted runners only** — no GitHub-hosted `ubuntu-latest` / `macos-*` / `windows-*` (org Actions budget is zero).

- Set `runs-on: self-hosted` for every job unless the job truly needs **macOS / Xcode**.
- macOS-only jobs must be listed in `.github/runner-allowlist.yml` and may use `runs-on: [self-hosted, macOS]`.
- Do not use Docker in workflow steps on runners.
- Workflow steps should be **cross-platform** (`shell: bash`, resolve `python`/`py` via `.github/actions/liminal-self-hosted-bootstrap` — do not rely on `actions/setup-python` when it fails on Windows).
- The `runner-policy` CI job fails if any workflow job violates the above.