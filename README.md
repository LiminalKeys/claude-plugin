# Liminal Keys — Claude plugin

Liminal Keys is in **public beta**. This marketplace plugin lets Claude **sign content by SHA-256 digest** with a **company certificate in Liminal Keys custody** over MCP (hash only). The bundled **liminalkeys-sign** helper can produce PAdES PDFs; detached digest signing works for any file format. Private keys never enter the Claude sandbox.

**Version:** 0.1.11 (bundles the `liminalkeys-sign` skill with offline CPython 3.12/3.13 wheels)  
**License:** Apache-2.0  
**Publisher:** Liminal Keys · https://www.liminalkeys.com

**Skill zip (standalone upload):** https://www.liminalkeys.com/downloads/liminalkeys-sign-skill-0.1.10.zip — see https://www.liminalkeys.com/docs/agents/

## Before you start

1. A [Liminal Console](https://console.liminalkeys.com) account and tenant.
2. In Console → **AI agents**, create an **agent** (for OAuth connector binding and policy). You do **not** need an API key to use the default URL-only sign-in.

You’re done when: the marketplace plugin is enabled, you have **connected** the bundled MCP server (`https://mcp.liminalkeys.com/mcp`) and signed in with your Liminal Keys account, and the agent can complete a first `sign_hash` on a sample document.

Full connector details: https://www.liminalkeys.com/docs/agents/

## Install

Outcome: Claude can resolve a certificate → prepare (optional PAdES) → sign_hash → embed (PDF path) → validate; private keys stay in Liminal Keys custody.

### Connect the MCP server (URL only)

Production endpoint: `https://mcp.liminalkeys.com/mcp` (same URL Console → **AI agents** shows).

Add that URL in Claude and choose **Connect**. Sign in with your Liminal Keys account (Google, Apple, Microsoft work or school, or email code — the same options as Console). Authentication uses **URL-only MCP OAuth** with dynamic client registration: you do not paste a client ID, client secret, or other OAuth app credentials. If you have multiple agents in Console, pick which connection this connector should use when prompted.

This plugin ships `.mcp.json` **without** API-key headers so Claude can complete the OAuth challenge. On **Claude Code**, HTTP MCP servers with no `Authorization` header use MCP OAuth (including dynamic client registration); run **`claude mcp login liminal-keys`** in your shell if you need to (re)authenticate the bundled server name.

### Claude Code

Add this marketplace, install or update the plugin, then start a session and connect as above:

```bash
/plugin marketplace add LiminalKeys/claude-plugin
/plugin install liminal-keys@liminal-keys
```

To upgrade an existing install, run the same `install` command again after refreshing the marketplace.

### claude.ai

1. Open **Customize → Plugins**.
2. Add or refresh the GitHub marketplace **LiminalKeys/claude-plugin**.
3. Enable **Liminal Keys** and **Connect** the bundled MCP URL (URL-only sign-in as above).

### Optional: API key header (hosts without MCP OAuth)

Some clients do not support MCP OAuth yet. In that case you can send a Console-issued `lkag_…` agent API key in **`x-api-key`** instead — **one auth mode per request** (not OAuth and a key together). Issue a 30- or 90-day key in Console → **AI agents**.

Do **not** add a placeholder key to the shipped `.mcp.json` (invalid headers break OAuth). Opt in locally, for example by merging headers into your user or project MCP config:

```json
{
  "mcpServers": {
    "liminal-keys": {
      "type": "http",
      "url": "https://mcp.liminalkeys.com/mcp",
      "headers": {
        "x-api-key": "${LIMINAL_KEYS_AGENT_API_KEY}"
      }
    }
  }
}
```

Set `LIMINAL_KEYS_AGENT_API_KEY` in your environment before starting Claude, or use your host’s secret field for `x-api-key`. Other accepted headers on the MCP server include `Authorization: Bearer …` and `X-Liminal-Keys-Agent-Key`. Never commit real keys into this repository or chat history.

## What the skill does

The bundled **liminalkeys-sign** skill walks the agent through:

1. `list_certificates` **once** → auto-pick `certificate_id` when unambiguous  
2. `get_certificate_chain` **once** → save `chain.pem` (do not re-fetch)  
3. `liminal-sign prepare --pdf … --cert-chain chain.pem --out state.json` — hash, compressed preview, and `sign_hash` fields in one step (cached venv via `bin/liminal-sign`)  
4. `sign_hash` **once** (default **120 s** poll); retries only collect with the same **`client_nonce`** + **`approval_id`**  
5. Optional MCP `timestamp` — RFC 3161 token for PAdES B-T  
6. `liminal-sign finish` — embed + mandatory validate in one command  

The CLI enforces the pinned MCP host and response-signing keys shipped in the skill.

## Data: what is sent where

| Data | Destination |
|------|-------------|
| File bytes, local digests, CMS state | Stay in the Claude sandbox / your machine |
| Certificate id, 32-byte digest, `document_label`, client nonce, optional previews | Sent to `https://mcp.liminalkeys.com/mcp` (Liminal Keys MCP) |
| Signed envelopes / signature / timestamp token | Returned from that MCP host to the sandbox |
| Private keys / Key Vault material | Never leave Liminal Keys custody; not present in this plugin |

MCP responses are ES256-signed; the skill verifies them against the bundled JWKS / trust pins for `mcp.liminalkeys.com`.

## Offline wheels (agent, not you)

Humans normally skip this. The **agent** should put `$SKILL_DIR/bin` on `PATH` and run **`liminal-sign`**, which installs the bundled wheel into a **cached venv** once per version (`~/.cache/liminalkeys-sign` by default). Manual fallback:

```bash
pip install --no-index --find-links "$SKILL_DIR/wheels" "liminalkeys-sign==0.1.10"
```

## Support

Product site: https://www.liminalkeys.com  
Console: https://console.liminalkeys.com  
Contact: contact@liminalkeys.com