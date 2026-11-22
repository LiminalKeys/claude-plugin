# Liminal Keys plugin for Claude

**Liminal Keys** lets AI agents sign documents and digests with a certificate you or your organization hold. Private keys stay in Key Vault and are never sent to Claude, the sandbox, or this plugin. Workspace policy (deny, require approval, or auto-sign) is the control layer: Claude never signs on its own authority; the signature is attributed to the certificate holder.

This repository is the official **Claude plugin** (`liminal-keys`, currently 0.1.12): it installs the `liminalkeys-sign` skill and wires the MCP connector. The bundled skill adds a local **PDF/PAdES** path with a branded visible stamp (or an invisible signature). Start here:

- [Sign PDFs and documents with Claude (AI agents docs)](https://www.liminalkeys.com/docs/agents/)
- Company site: [liminalkeys.com](https://www.liminalkeys.com/)

Liminal Keys also supports a separate **app and code signing** workflow (Mac, Xcode, CI). That is not this repository — see [app & code signing docs](https://www.liminalkeys.com/docs/app-signing/).

Liminal Keys is in **public beta**. This plugin lets Claude request a **SHA-256 digest signature** with **any signing certificate you or your organization hold in Liminal Keys** (RSA with SHA-256 today). Signing is **format-agnostic at the cryptographic level**: the MCP server signs the hash, and you can use it to build **PAdES, CAdES, XAdES and other formats**; the format and its conformance depend on the client that computes the digest and assembles the file. Apart from the bundled PDF helper, this repository does not build those containers. The bundled **liminalkeys-sign** skill adds a local **PDF/PAdES** path with a branded visible stamp (or an invisible signature). Private keys are held by Liminal Keys and are not sent to Claude, the sandbox or this plugin.

**Version:** 0.1.12 (bundles the `liminalkeys-sign` skill with offline CPython 3.12/3.13 wheels)  
**License:** Apache-2.0  
**Publisher:** Liminal Keys · https://www.liminalkeys.com · Operated by Liminal Keys, SL ([Legal notice](https://www.liminalkeys.com/legal-notice))

## Before you start

1. A [Console](https://console.liminalkeys.com) account and workspace.
2. In Console → **AI agents**, create an **agent** (connector binding and policy). No API key is needed for the default connector — you sign in on **Connect**.
3. In Console → **Policy rules**, add a rule whose subject is that agent (allow or require approval). Signing is denied until a rule allows the agent.

You’re done when the plugin is enabled, the MCP server is connected and you have signed in with Liminal Keys, and a first test signature succeeds.

Agent setup: https://www.liminalkeys.com/docs/agents/

## Install

### Claude Code

```bash
/plugin marketplace add LiminalKeys/claude-plugin
/plugin install liminal-keys@liminal-keys
```

To upgrade, refresh the marketplace, run the install command again, and start a new session.

### claude.ai

1. **Customize → Plugins**
2. Add or refresh marketplace **LiminalKeys/claude-plugin**
3. Enable **Liminal Keys**, **Connect**, and sign in

## Connect

Production MCP URL: `https://mcp.liminalkeys.com/mcp` (same as Console → **AI agents**).

The shipped `.mcp.json` is **URL-only** (no API-key header). In Claude, choose **Connect** and sign in with the same options as Console (Google, Apple, Microsoft work or school account, or email code when enabled). You do not paste a client ID, client secret, or API key. If you have several agents, pick which connection to use when prompted.

On **Claude Code**, run **`claude mcp login liminal-keys`** in your shell to (re)authenticate the bundled server name.

## First signature

Example prompts:

- “List the signing certificates available for this agent.”
- “Sign `contract.pdf` with Liminal Keys and show the validation report.”
- “Sign the SHA-256 digest of `release-manifest.json` (detached); I will assemble the format myself.”

**PDF flow** (bundled skill):

1. `list_certificates` (once)
2. `get_certificate_chain` (once) → `chain.pem`
3. `liminal-sign prepare` → digest, preview, branded stamp options
4. `sign_hash` (once; default **120 s** poll)
5. Optional MCP `timestamp` (RFC 3161, by default from FreeTSA, a non-qualified time-stamping service) embedded as a signature timestamp. The helper does not add long-term validation data (no B-LT/B-LTA).
6. `liminal-sign finish` — embed the signature and run a local technical check (document integrity and signature against the signer's certificate). This check is not a legal or trust-list validation.

**MCP tools:** `list_certificates`, `get_certificate_chain`, `sign_hash`, optional `timestamp`.

v1: RSA / `sha256_rsa` over a 32-byte digest.

For **non-PDF formats**, you compute the digest your format requires, call `sign_hash`, and assemble the signed artifact yourself; you are responsible for the resulting format and its conformance.

After upgrading the plugin, clear a stale CLI cache if needed:

```bash
rm -rf "${LIMINALKEYS_SIGN_CACHE:-$HOME/.cache/liminalkeys-sign}"
liminal-sign --version   # expect 0.1.12
```

## Approvals and policy

Signing follows your workspace policy (deny, require approval, or auto-sign); we recommend **Require approval** for any signature that binds a person or organization.

With approval required, the approvers named in the rule approve or reject in **LK Approvals** (a web app you can install on your phone). `sign_hash` waits up to **120 s**; if still pending it returns `pending_approval`: continue with the same `client_nonce` and `approval_id` (it collects the same request, no second approval). If **denied**, don't retry; fix the policy or request. Requests expire if not decided (default **10 minutes**).

The **preview** and **label** come from the agent and are **not checked against the digest**: approve only requests you recognise.

Claude never signs on its own authority; signatures are attributed to the certificate holder, not the AI agent.

Use only certificates you are entitled to use (holder or authorised; some issuers forbid third-party cloud custody; check before importing). If a certificate belongs to an individual, set the policy so the holder approves each signature.

Outcomes appear in Console → **Sign audit**.

## Data: what goes where

The file's full bytes stay where Claude runs the skill and are **not** uploaded to Liminal Keys.

The **digest**, **certificate id**, **document label**, and **nonce** go to the MCP server.

**Approval preview:** for PDFs, a small low-resolution image of the first page, which can contain readable content (a blank placeholder if it can't be rendered).

**Signature**, **chain**, and **timestamp token** are returned from MCP to the sandbox.

**Private keys** are held by Liminal Keys.

Liminal Keys also keeps an audit record of each request and decision (including the digest and document label) and technical logs (such as IP address and time), as described in the [Privacy Policy](https://www.liminalkeys.com/privacy). Preview images are deleted once the request is decided or expires. If timestamps are enabled, only the digest-based timestamp request goes to the time-stamping authority.

**Claude and your files.** Claude, provided by Anthropic, reads the file and your conversation to run the skill. Anthropic processes that content under its own terms and privacy policy, not Liminal Keys'. Only share documents you are allowed to share with your AI provider.

MCP responses are ES256-signed; the skill verifies them against bundled trust pins for `mcp.liminalkeys.com`.

## Legal effect

Liminal Keys creates an electronic signature with **your** certificate. Liminal Keys is not a qualified (or accredited) trust service provider, is not listed on any EU or national trusted list, and does not operate a qualified signature creation device (QSCD). It does not issue publicly trusted certificates.

The legal effect of a signature depends on:

- the certificate you use and the rules of the authority that issued it;
- how the key is held and how signing is authorised (for example your workspace policy and approvals);
- the law that applies where the signature is relied on, and what the receiving party accepts.

Examples only, not a claim of conformance with any of them: in the EU, eIDAS (Regulation (EU) No 910/2014, as amended) distinguishes simple, advanced and qualified electronic signatures, and a qualified signature requires a qualified certificate **and** a qualified signature creation device. Because Liminal Keys does not operate a QSCD, signatures made through Liminal Keys are not qualified electronic signatures, even if your certificate is qualified. Other jurisdictions have their own rules, for example the US ESIGN Act and UETA, the UK Electronic Communications Act 2000 and UK eIDAS, Switzerland's ZertES, and national laws across Latin America and elsewhere.

We do not promise that a signature is equivalent to a handwritten signature, or that it will be accepted by any court, authority, PDF reader or other party. Check the requirements for your use case and jurisdiction before you rely on it. See the [Terms of Service](https://www.liminalkeys.com/terms), section 4.

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| Signing **denied** | Add a **policy rule** that allows the agent (Console → Policy rules). |
| `pending_approval` | Resume `sign_hash` with the **same** `client_nonce` and `approval_id`. |
| **401** / Connect expired | Reconnect in Claude or run `claude mcp login liminal-keys`. |
| Wrong certificate picked | Name the subject in chat or narrow policy; re-run from `list_certificates`. |
| **No branded stamp** / branding self-check failed | Upgrade plugin, clear `~/.cache/liminalkeys-sign`, new session; use only `liminal-sign prepare` / `finish`. |
| **`liminal-sign` install failed** | Check `python3` version (offline wheels target CPython 3.12–3.13 on Linux x86_64); see `skills/liminalkeys-sign/INSTALL.md`. |

## Optional API key (hosts without MCP OAuth)

Some clients do not support MCP OAuth yet. Create an `lkag_…` agent API key in Console → **AI agents** and add it locally — **one auth mode per request** (not OAuth plus a key). Do not put placeholders in the shipped `.mcp.json`; merge headers in your user or project MCP config:

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

Liminal Keys and this plugin are in **public beta** and may change. Nothing in this repository is legal advice. You are responsible for deciding whether a signature made with this plugin meets the legal, regulatory and contractual requirements of your use case in the jurisdictions where it will be relied on.

The software in this repository is provided "as is", without warranties, under the Apache License 2.0. Use of the Liminal Keys service is governed by the [Terms of Service](https://www.liminalkeys.com/terms), including its warranty and liability sections.

## License

Copyright 2026 Liminal Keys, SL. Licensed under the [Apache License 2.0](LICENSE). See `NOTICE`.

The bundled wheels in `skills/liminalkeys-sign/wheels/` are third-party packages (for example pyHanko, cryptography, lxml, aiohttp, Pillow) distributed under their own licenses, included in each wheel.

## Trademarks

Claude is a trademark of Anthropic, PBC. This plugin is made by Liminal Keys, SL and is not made, endorsed or sponsored by Anthropic. Other names (such as Google, Apple, Microsoft and Adobe) are trademarks of their owners and are used only to describe compatibility.

## Legal

Operated by Liminal Keys, SL · [Legal notice](https://www.liminalkeys.com/legal-notice) · [Terms](https://www.liminalkeys.com/terms) · [Privacy](https://www.liminalkeys.com/privacy) · [Cookies](https://www.liminalkeys.com/cookies) · legal@liminalkeys.com

## Support

support@liminalkeys.com · https://www.liminalkeys.com/docs/agents/