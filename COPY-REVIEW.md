# Copy review — private draft

Repo: private `LiminalKeys/claude-plugin`. Do **not** make public until Antonio OK.

## Gates
1. Marketing copy review (2026-11-05) — public beta, soft MCP wording, key polish applied.
2. UX skim (2026-11-05) — before-you-start, Claude Code vs claude.ai key paste, plugin@marketplace note, agent-runs-wheels, outcome-first Install applied.
3. **Antonio (bundle for PM):**
   - Approve PDF/company-certificate signing as public live framing (else rewrite).
   - Approve public beta line + “Liminal Keys MCP” (not “production”) wording.
   - Confirm `contact@liminalkeys.com` as public support (matches site today).
   - DNS: CNAME `mcp` → MCP App Service hostname so `mcp.liminalkeys.com` resolves (preferred over advertising azurewebsites).
4. Custom domain must be live before public install docs claim that host.

## Check
- Publisher Liminal Keys only, Apache-2.0, no personal names, no App Store links
- Skill liminalkeys-sign 0.1.4
- `.mcp.json` → `https://mcp.liminalkeys.com/mcp` with API-key placeholder only
