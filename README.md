# Liminal Keys — Claude plugin

Liminal Keys is in **public beta**. This marketplace plugin lets Claude **sign content by SHA-256 digest** with a **company certificate in Liminal Keys custody** over MCP (hash only). The bundled **liminalkeys-sign** helper can produce PAdES PDFs; detached digest signing works for any file format. Private keys never enter the Claude sandbox.

**Version:** 0.1.10 (bundles the `liminalkeys-sign` skill with offline CPython 3.12/3.13 wheels)  
**License:** Apache-2.0  
**Publisher:** Liminal Keys · https://www.liminalkeys.com

**Skill zip (standalone upload):** https://www.liminalkeys.com/downloads/liminalkeys-sign-skill-0.1.10.zip — see https://www.liminalkeys.com/docs/agents/

## Before you start

1. A [Liminal Console](https://console.liminalkeys.com) account and tenant.
2. Create an **agent API key** in Console (**AI agents** → create key). Keys start with `lkag_`. You need this **before** enabling the plugin so the MCP connector can authenticate.

You’re done when: the plugin is enabled, the agent API key is set for your Claude surface, and the agent can complete a first `sign_hash` on a sample document.

## Install

Outcome: Claude can resolve a certificate → prepare (optional PAdES) → sign_hash → embed (PDF path) → validate; private keys stay in Liminal Keys custody.

### Claude Code

Add this marketplace, then install the plugin. The marketplace id and plugin id are both `liminal-keys` on purpose (`liminal-keys@liminal-keys` means plugin@marketplace):

```bash
/plugin marketplace add LiminalKeys/claude-plugin
/plugin install liminal-keys@liminal-keys
```

Then set the agent API key in your environment before starting a session:

```bash
export LIMINAL_KEYS_AGENT_API_KEY=YOUR_LIMINAL_KEYS_AGENT_API_KEY
```

### claude.ai

1. Open **Customize → Plugins → Add marketplace**, add GitHub marketplace `LiminalKeys/claude-plugin`, and enable **Liminal Keys**.
2. Open the connector / plugin **secret** (or API key) field for this MCP server and paste your Console agent API key as the `x-api-key` value (raw key, no `Bearer` prefix). Prefer that header for Claude.ai custom connectors.

Replace the placeholder with your Console-issued key. Never commit real keys into this repository, `.mcp.json`, or chat history. Other accepted headers on the MCP server include `Authorization: Bearer …` and `X-Liminal-Keys-Agent-Key`.

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
