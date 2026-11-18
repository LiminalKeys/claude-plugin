# Liminal Keys — Claude plugin

Liminal Keys is in **public beta**. This plugin lets Claude **sign a SHA-256 digest** with a **signing certificate you hold in Liminal Keys** (personal, qualified, company, code signing, or other types your tenant allows) over MCP. Signing is **format-agnostic**: the server signs the hash, so the same flow works for **PAdES, XAdES, CAdES, JAdES**, and other formats you implement outside this repo. The bundled **liminalkeys-sign** skill adds a **local PDF/PAdES helper** with the branded on-page stamp; the plugin itself is not PDF-only. Private keys never enter the Claude sandbox.

**Version:** 0.1.12 (bundles the `liminalkeys-sign` skill with offline CPython 3.12/3.13 wheels)  
**License:** Apache-2.0  
**Publisher:** Liminal Keys · https://www.liminalkeys.com

**Skill zip (standalone upload):** https://www.liminalkeys.com/downloads/liminalkeys-sign-skill-0.1.12.zip — https://www.liminalkeys.com/docs/agents/

## Before you start

1. A [Liminal Console](https://console.liminalkeys.com) account and tenant.
2. In Console → **AI agents**, create an **agent** (connector binding and policy). You do **not** need an API key for the default connector.

You’re done when the plugin is enabled, the bundled MCP server is **connected** and you have signed in with Liminal Keys, and a test `sign_hash` succeeds.

Docs: https://www.liminalkeys.com/docs/agents/

## Install

### Claude Code

```bash
/plugin marketplace add LiminalKeys/claude-plugin
/plugin install liminal-keys@liminal-keys
```

Run `/plugin install` again after marketplace updates to upgrade.

### claude.ai

1. **Customize → Plugins**
2. Add or refresh marketplace **LiminalKeys/claude-plugin**
3. Enable **Liminal Keys** and **Connect** the bundled MCP server

### Connect (URL-only OAuth)

Production MCP URL: `https://mcp.liminalkeys.com/mcp` (same as Console → **AI agents**).

In Claude, **Connect** and sign in with your Liminal Keys account. The shipped `.mcp.json` is URL-only (no API-key header) so OAuth and dynamic client registration work. On **Claude Code**, use **`claude mcp login liminal-keys`** if you need to (re)authenticate.

### Optional: API key (hosts without MCP OAuth)

If your host cannot do MCP OAuth, send a Console-issued `lkag_…` agent API key in **`x-api-key`** — **one auth mode per request**, not OAuth plus a key. Create the key in Console → **AI agents**. Do not put placeholders in the shipped `.mcp.json`; merge headers in your local MCP config and set `LIMINAL_KEYS_AGENT_API_KEY` in the environment. Never commit real keys.

## What the bundled skill does (PDF path)

For PDFs, **liminalkeys-sign** runs:

1. `list_certificates` once → pick `certificate_id` when unambiguous  
2. `get_certificate_chain` once → `chain.pem`  
3. `liminal-sign prepare` — digest, preview, branded stamp options  
4. `sign_hash` once (default **120 s** poll); retries use the same `client_nonce` and `approval_id`  
5. Optional MCP `timestamp` for PAdES B-T  
6. `liminal-sign finish` — embed and validate  

Non-PDF formats: compute the digest your format requires, call `sign_hash`, and assemble the signed artifact with your own tooling; keys stay in Liminal Keys custody.

After upgrading, clear a stale CLI cache if needed:

```bash
rm -rf "${LIMINALKEYS_SIGN_CACHE:-$HOME/.cache/liminalkeys-sign}"
liminal-sign --version   # expect 0.1.12
```

## Data

| Data | Where |
|------|--------|
| File bytes, digests, CMS/PAdES state | Sandbox / your machine |
| Certificate id, digest, label, nonce, previews | `https://mcp.liminalkeys.com/mcp` |
| Signatures, timestamps, chains | Returned from MCP to the sandbox |
| Private keys | Liminal Keys custody only |

MCP responses are ES256-signed; the skill verifies them against bundled trust pins for `mcp.liminalkeys.com`.

## Support

https://www.liminalkeys.com · https://console.liminalkeys.com · contact@liminalkeys.com