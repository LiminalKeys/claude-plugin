# Installing the liminalkeys-sign Claude skill

**Size limit:** Claude rejects skill uploads at **30 MiB**. Releases target **CPython 3.12 and 3.13** (manylinux x86_64) offline wheels to stay under that cap. On **macOS** (Claude Code) the same offline set applies; CPython **3.10+** is required (`requires-python` on the package).

## Public download (0.1.12)

Download the skill zip from Liminal Keys (same layout as this plugin folder):

- **Zip:** https://www.liminalkeys.com/downloads/liminalkeys-sign-skill-0.1.12.zip
- **SHA-256:** https://www.liminalkeys.com/downloads/liminalkeys-sign-skill-0.1.12.zip.sha256

Setup context: https://www.liminalkeys.com/docs/agents/

1. Download the zip (and optional `.sha256` sidecar) and verify the checksum if you use the sidecar file.
2. In Claude (Skills / custom skills), upload the zip or point your workspace at the extracted **`liminalkeys-sign/`** folder at the archive root.

Claude loads **`SKILL.md`** as the skill instructions. Keep **`wheels/`** next to it so offline install works inside the agent sandbox.

The zip includes **`liminalkeys-mcp-keys.json`** (public JWKS) and **`liminalkeys_mcp_trust.prod.json`** (host allow list + pinned keys). You do not attach these every chat: after `pip install`, the CLI defaults to the same bundled trust. Pass `--mcp-trust-config` only to override with a custom JSON path.

Offline wheels cover CPython **3.12–3.13** (manylinux x86_64) including compiled dependencies required by pyHanko (for example `aiohttp`, `lxml`, `cryptography`, **Pillow** for both 3.12 and 3.13). The **default branded stamp** embeds a **pre-baked DeviceRGB image XObject** (`lk-watermark-device-rgb.bin`) without Pillow at runtime (macOS and Linux sandboxes match). **`--stamp-logo`** still requires Pillow (offline wheels on Linux x86_64 cp312/cp313; PyPI when the sandbox allows).

## Install the CLI inside the sandbox

Preferred — cached venv (no `pip install` every signing run):

```bash
export SKILL_DIR="<skill folder>"
chmod +x "$SKILL_DIR/bin/liminal-sign"
export PATH="$SKILL_DIR/bin:$PATH"
liminal-sign --version
```

Manual fallback from `SKILL_DIR`:

```bash
pip install --no-index --find-links "$SKILL_DIR/wheels" "liminalkeys-sign==0.1.12"
```

If your environment allows PyPI, you may instead run `pip install liminalkeys-sign` once the package is published; the skill zip path avoids waiting on PyPI.

**PAdES B-T validation:** `validate --trust` anchors the **signer** chain only. RFC 3161 timestamp (TSA) chains are separate — supply **`--tsa-trust`** with the TSA root/intermediate PEM(s) when needed (FreeTSA is not under a typical FNMT signer anchor). Timestamps are **optional**; default MCP TSA is **FreeTSA** (**non-qualified** — disclose to end users). Exit code follows pyHanko’s overall **INVALID/VALID** bottom line; use **`--allow-untrusted-timestamp`** only if you accept a warning when the signer is OK but TSA trust failed.

PDF signing via this skill is **closed beta / design-partner tooling**. Liminal Keys is not a qualified trust service provider.

### Sample agent prompts (visible vs invisible)

- **Invisible (default):** “Sign this PDF without a visible stamp.” → `prepare` with no `--visible-signature`.
- **Last page, bottom-right:** “Put the signature in the bottom-right corner of the last page with a normal margin.” → `--visible-signature --stamp-page last --stamp-anchor bottom-right`.
- **Reason line:** “Add a visible stamp that says this is for vendor onboarding.” → add `--stamp-reason "Vendor onboarding"`.
- **Logo + locale:** “Use our PNG logo on the stamp and show dates in German format.” → `--stamp-logo ./brand.png --stamp-locale de-DE`.

## Liminal Keys MCP connector (high level)

Configure the **Liminal Keys MCP connector** in Claude with:

- The **admin-configured MCP endpoint** from Liminal Console (your tenant’s official host — do not use unofficial URLs).
- **Authentication** with your Console-issued `lkag_…` key. Claude.ai custom connectors reliably send **`x-api-key`** (raw key) or **`Authorization: Bearer …`**; the MCP server also accepts **`X-Liminal-Keys-Agent-Key`** for other clients. Store the key in Claude’s connector secret settings, not in the skill zip or chat.

The skill and CLI enforce pinned hosts and response signing keys in code; connector setup must match that trust model. See **`SKILL.md`** for the signing tool order and the product docs for MCP pairing details.

No enrollment secrets, private keys, or Key Vault material belong in the skill archive.
