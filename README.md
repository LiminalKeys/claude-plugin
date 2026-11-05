# Liminal Keys — Claude plugin

> **Draft — private repo.** Install commands work only after this marketplace is published. Do not treat this README as public until Antonio OK.

Liminal Keys is in **public beta**. This marketplace plugin lets Claude **sign a PDF with a company certificate** over MCP (hash only) — the private key never enters the Claude sandbox.

**Version:** 0.1.4 (bundles the `liminalkeys-sign` skill with offline CPython 3.12/3.13 wheels)  
**License:** Apache-2.0  
**Publisher:** Liminal Keys · https://www.liminalkeys.com

> **Positioning (pending Antonio OK):** Standing marketing rule is that Apple code signing is the only use presented as live unless he approves otherwise. This skill is for PDF signing under company certificates; keep or drop that framing after his decision.

## Before you start

1. A [Liminal Console](https://console.liminalkeys.com) account and tenant.
2. Create an **agent API key** in Console (**AI agents** → create key). Keys start with `lkag_`. You need this **before** enabling the plugin so the MCP connector can authenticate.

You’re done when: the plugin is enabled, the agent API key is set for your Claude surface, and the agent can complete a first `sign_hash` on a sample PDF.

## Install

Outcome: Claude can prepare → sign → embed → validate a PDF under your company certificate; private keys stay in Liminal Keys custody.

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

1. `get_certificate_chain` — resolve the leaf/chain for prepare  
2. Local `liminalkeys-sign prepare` — hash CMS signed attributes (32-byte digest)  
3. `sign_hash` — Liminal Keys signs the digest under policy (`document_label` required)  
4. Optional MCP `timestamp` — RFC 3161 token for PAdES B-T  
5. `liminalkeys-sign embed` + mandatory `validate` — verify, embed, and show the validation report  

The CLI enforces the pinned MCP host and response-signing keys shipped in the skill.

## Data: what is sent where

| Data | Destination |
|------|-------------|
| PDF bytes, local digests, CMS state | Stay in the Claude sandbox / your machine |
| Certificate id, 32-byte digest, `document_label`, client nonce | Sent to `https://mcp.liminalkeys.com/mcp` (Liminal Keys MCP) |
| Signed envelopes / signature / timestamp token | Returned from that MCP host to the sandbox |
| Private keys / Key Vault material | Never leave Liminal Keys custody; not present in this plugin |

MCP responses are ES256-signed; the skill verifies them against the bundled JWKS / trust pins for `mcp.liminalkeys.com`.

> **Ops note (private draft):** `mcp.liminalkeys.com` is the intended customer URL (custom domain pending DNS). Live App Service hostname is not advertised here.

## Offline wheels (agent, not you)

Humans normally skip this. The **agent** installs the helper inside the Claude sandbox from the skill directory when needed:

```bash
pip install --no-index --find-links "$SKILL_DIR/wheels" liminalkeys-sign
```

(`$SKILL_DIR` is the skill folder path inside the sandbox.)

## Support

Product site: https://www.liminalkeys.com  
Console: https://console.liminalkeys.com  
Contact: contact@liminalkeys.com
