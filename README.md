# Liminal Keys — Claude plugin

Liminal Keys is in **public beta**. This marketplace plugin connects Claude to Liminal Keys so an agent can sign PDFs with a company certificate without putting the private key in the agent sandbox: prepare the PDF, request a signature over MCP (hash only), embed the result, and validate it. Private signing keys stay in Liminal Keys custody and never enter the Claude sandbox.

**Version:** 0.1.4 (bundles the `liminalkeys-sign` skill with offline CPython 3.12/3.13 wheels)  
**License:** Apache-2.0  
**Publisher:** Liminal Keys · https://www.liminalkeys.com

> **Note (draft):** This skill is for PDF signing under company certificates. Public positioning as a live capability awaits Antonio’s OK (standing marketing rule: Apple code signing is the only use presented as live unless otherwise approved).

## Install

### Claude Code

Add this marketplace, then install the plugin:

```bash
/plugin marketplace add LiminalKeys/claude-plugin
/plugin install liminal-keys@liminal-keys
```

### claude.ai

Open **Customize → Plugins → Add marketplace**, then add the GitHub marketplace `LiminalKeys/claude-plugin` and enable **Liminal Keys**.

## Agent API key

Create an agent API key in Liminal Console (AI agents); keys start with `lkag_`. Configure it for the MCP connector:

- Prefer the `x-api-key` header with the raw key (recommended for Claude.ai custom connectors).
- For Claude Code, set the environment variable before starting a session:

```bash
export LIMINAL_KEYS_AGENT_API_KEY=YOUR_LIMINAL_KEYS_AGENT_API_KEY
```

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

## Offline wheels

Install the helper inside the sandbox from the skill directory:

```bash
pip install --no-index --find-links "$SKILL_DIR/wheels" liminalkeys-sign
```

## Support

Product site: https://www.liminalkeys.com  
Console: https://console.liminalkeys.com  
Contact: contact@liminalkeys.com
