# claude-plugin — agent instructions

## CI runners (public repo exception)

**This repository is public.** LiminalKeys org **self-hosted runners are not registered for public repos** (and must stay that way): otherwise fork PRs could run arbitrary workflow code on owners’ PCs.

- CI jobs here use **GitHub-hosted** runners (e.g. `ubuntu-latest`). Public repos get included GitHub Actions minutes.
- **Private** LiminalKeys repos (e.g. `outlook-attach-mcp`, `WatchTeams`) use **only** `runs-on: self-hosted` — org Actions budget is zero on GitHub-hosted.

### Runner policy in this repo

- `scripts/ci/check_runner_policy.py` allows GitHub-hosted `runs-on` when `.github/runner-allowlist.yml` sets `allow_github_hosted: true` (this repo only).
- Do not switch this repo to `self-hosted` without also changing org runner group visibility (not recommended).
- macOS/Xcode jobs in other repos use `.github/runner-allowlist.yml` job entries and `[self-hosted, macOS]`; not applicable here today.