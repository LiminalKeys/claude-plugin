# Liminal Keys plugin for Claude

**Liminal Keys** lets Claude sign documents and files with your own certificate, under your rules, with approval on your phone. PDFs come back with a visible signature; other file types can be signed too.

This repository is the official Claude plugin (`LiminalKeys/claude-plugin`). Private keys stay in Key Vault and are never sent to Claude, the sandbox, or this plugin. Workspace policy (deny, require approval, or auto-sign) is the control layer: Claude never signs on its own authority.

Liminal Keys also supports separate **app and code signing** (Mac, Xcode, CI) — see [app & code signing docs](https://www.liminalkeys.com/docs/app-signing/). Agent setup: [Sign with Claude](https://www.liminalkeys.com/docs/agents/claude/).

**Version:** 0.1.14 (bundles the `liminalkeys-sign` skill with offline CPython 3.12/3.13 wheels on Linux x86_64)  
**License:** Apache-2.0  
**Publisher:** Liminal Keys · https://www.liminalkeys.com · Operated by Liminal Keys, SL ([Legal notice](https://www.liminalkeys.com/legal-notice))

## Install on claude.ai

1. Open **Customize → Plugins**.
2. **When listed in Anthropic's plugin directory:** find **Liminal Keys** and choose **Add**.
3. **Until then:** **+ Add → Add marketplace**, enter **LiminalKeys/claude-plugin**, tap **Sync**, find **Liminal Keys**, and tap **Add**.
4. Open the plugin's **Connectors** tab and choose **Connect**. Sign in with Liminal Keys (Google, Apple, Microsoft work or school, or email code).
5. **Do not** also add a custom Liminal Keys connector in Claude's global connector settings — the plugin already ships the MCP server.

Turn on **code execution** and file creation in Claude (**Settings → Capabilities**) when you need the bundled signing skill in the sandbox.

### Claude Code

```bash
/plugin marketplace add LiminalKeys/claude-plugin
/plugin install liminal-keys@liminal-keys
```

To upgrade, refresh the marketplace, run the install command again, and start a new session. On **Claude Code**, run **`claude mcp login liminal-keys`** to (re)authenticate when Connect expires.

## First-time Liminal Keys setup

Before the first signature succeeds:

1. Create a [Liminal Keys account](https://console.liminalkeys.com/?signup=1).
2. Import or issue a **signing certificate** in Console.
3. In **AI agents**, create an **agent** (this is what Claude connects to).
4. In **Policy rules**, add a rule whose subject is that agent (allow or **require approval**).
5. Click **Apply policy** so the rule is live. Signing is denied until a rule allows the agent.

Agent setup: https://www.liminalkeys.com/docs/agents/

## Example prompts

- “List the signing certificates available for this agent.”
- “Sign this contract PDF with my Liminal Keys certificate and show the validation report.”
- “Compute the SHA-256 digest of `vendor-agreement.docx`, sign it with Liminal Keys, and tell me what to embed for my format.”

**Typical PDF flow** (bundled skill): `list_certificates` → `get_certificate_chain` → `liminal-sign prepare` → `sign_hash` → optional MCP `timestamp` → `liminal-sign finish`.

**Other file types:** compute the digest your format requires, call `sign_hash`, and assemble the signed artifact yourself.

**MCP tools:** `list_certificates`, `get_certificate_chain`, `sign_hash`, optional `timestamp`.

v1: RSA / `sha256_rsa` over a 32-byte digest.

After upgrading the plugin, clear a stale CLI cache if needed:

```bash
rm -rf "${LIMINALKEYS_SIGN_CACHE:-$HOME/.cache/liminalkeys-sign}"
liminal-sign --version   # expect 0.1.14
```

## Connect

Production MCP URL: `https://mcp.liminalkeys.com/mcp` (same as Console → **AI agents**).

The shipped `.mcp.json` is **URL-only** (no API-key header). In Claude, choose **Connect** and sign in with Liminal Keys. You do not paste a client ID, client secret, or API key. If you have several agents, pick which connection to use when prompted.

## Approvals and policy

Signing follows your workspace policy (deny, require approval, or auto-sign); we recommend **Require approval** for any signature that binds a person or organization.

With approval required, approvers approve or reject in **LK Approvals** (web app on your phone). `sign_hash` waits up to **120 s**; if still pending it returns `pending_approval`: continue with the same `client_nonce` and `approval_id`. If **denied**, don't retry without fixing policy or the request. Requests expire if not decided (default **10 minutes**).

The **preview** and **label** come from the agent and are **not checked against the digest**: approve only requests you recognise.

Claude never signs on its own authority; signatures are attributed to the certificate holder, not the AI agent.

Use only certificates you are entitled to use. Outcomes appear in Console → **Sign audit**.

## Data: what goes where

The file's full bytes stay where Claude runs the skill and are **not** uploaded to Liminal Keys.

The **digest**, **certificate id**, **document label**, and **nonce** go to the MCP server.

**Approval preview:** for PDFs, a small low-resolution image of the first page (a blank placeholder if it can't be rendered).

**Signature**, **chain**, and **timestamp token** are returned from MCP to the sandbox.

**Private keys** are held by Liminal Keys.

Liminal Keys keeps an audit record of each request and decision and technical logs, as described in the [Privacy Policy](https://www.liminalkeys.com/privacy). Preview images are deleted once the request is decided or expires. If timestamps are enabled, only the digest-based timestamp request goes to the time-stamping authority.

**Claude and your files.** Claude, provided by Anthropic, reads the file and your conversation to run the skill. Anthropic processes that content under its own terms and privacy policy, not Liminal Keys'. Only share documents you are allowed to share with your AI provider.

MCP responses are ES256-signed; the skill verifies them against bundled trust pins for `mcp.liminalkeys.com`.

## Legal effect

Liminal Keys creates an electronic signature with **your** certificate. Liminal Keys is **not** a qualified (or accredited) trust service provider, is not listed on any EU or national trusted list, and does not operate a qualified signature creation device (QSCD). It does not issue publicly trusted certificates.

The legal effect of a signature depends on the certificate you use, how signing is authorised (policy and approvals), and the law that applies where the signature is relied on. In the EU, eIDAS distinguishes simple, advanced and qualified electronic signatures; signatures through Liminal Keys are **not** qualified electronic signatures even if your certificate is qualified, because Liminal Keys does not operate a QSCD. Other jurisdictions have their own rules.

We do not promise that a signature is equivalent to a handwritten signature, or that it will be accepted by any court, authority, or counterparty. Check the requirements for your use case and jurisdiction before you rely on it. See the [Terms of Service](https://www.liminalkeys.com/terms), section 4.

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| Signing **denied** | Add a **policy rule** that allows the agent (Console → Policy rules) and **Apply policy**. |
| `pending_approval` | Resume `sign_hash` with the **same** `client_nonce` and `approval_id`. |
| **401** / Connect expired | Reconnect on the plugin **Connectors** tab or run `claude mcp login liminal-keys`. |
| Wrong certificate picked | Name the subject in chat or narrow policy; re-run from `list_certificates`. |
| **No branded stamp** | Upgrade plugin, clear `~/.cache/liminalkeys-sign`, new session; use only `liminal-sign prepare` / `finish`. |
| **`liminal-sign` install failed** | Check `python3` (offline wheels target CPython 3.12–3.13 on Linux x86_64); see `skills/liminalkeys-sign/INSTALL.md`. |
| **Duplicate MCP tools** | Remove a custom Liminal Keys connector; keep the plugin only. |

## Optional API key (hosts without MCP OAuth)

Some clients do not support MCP OAuth yet. Create an `lkag_…` agent API key in Console → **AI agents** and add it locally — **one auth mode per request**. Do not put placeholders in the shipped `.mcp.json`; merge headers in your user or project MCP config:

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

Set `LIMINAL_KEYS_AGENT_API_KEY` in your environment before starting Claude. Never commit real keys.

## Beta and disclaimer

Liminal Keys and this plugin are in **public beta** and may change. Nothing in this repository is legal advice. You are responsible for deciding whether a signature meets the legal, regulatory and contractual requirements of your use case.

The software in this repository is provided "as is", without warranties, under the Apache License 2.0. Use of the Liminal Keys service is governed by the [Terms of Service](https://www.liminalkeys.com/terms).

## License

Copyright 2026 Liminal Keys, SL. Licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE).

Bundled wheels in `skills/liminalkeys-sign/wheels/` are third-party packages (for example pyHanko, cryptography, lxml, aiohttp) under their own licenses.

## Trademarks

Claude is a trademark of Anthropic, PBC. This plugin is made by Liminal Keys, SL and is not made, endorsed or sponsored by Anthropic.

## Legal

Operated by Liminal Keys, SL · [Legal notice](https://www.liminalkeys.com/legal-notice) · [Terms](https://www.liminalkeys.com/terms) · [Privacy](https://www.liminalkeys.com/privacy) · legal@liminalkeys.com

## Support

support@liminalkeys.com · https://www.liminalkeys.com/docs/agents/