# Installing the liminalkeys-sign Claude skill

This folder is packaged as **`liminalkeys-sign-skill-<version>.zip`** by the GitHub Actions workflow `package-liminalkeys-sign-skill.yml`. The zip is an artifact only (not attached to GitHub Releases by default).

**Size limit:** Claude rejects skill uploads at **30 MiB**. Packaging CI fails if the zip is **≥ 30×1024×1024 bytes**; default wheels target **CPython 3.12 and 3.13** (manylinux x86_64) to stay under that cap.

## Upload to Claude

1. Download the zip (and optional `.sha256` sidecar) from the workflow run artifacts.
2. Verify the checksum if you use the sidecar file.
3. In Claude (Skills / custom skills), upload the zip or point your workspace at the extracted **`liminalkeys-sign/`** folder at the archive root.

Claude loads **`SKILL.md`** as the skill instructions. Keep **`wheels/`** next to it so offline install works inside the agent sandbox.

The zip includes **`liminalkeys-mcp-keys.json`** (public JWKS) and **`liminalkeys_mcp_trust.prod.json`** (host allow list + pinned keys). You do not attach these every chat: after `pip install`, the CLI defaults to the same bundled trust. Pass `--mcp-trust-config` only to override with a custom JSON path.

Offline wheels cover CPython **3.12–3.13** (manylinux x86_64) including compiled dependencies required by pyHanko (for example `aiohttp`, `lxml`, `cryptography`).

## Install the CLI inside the sandbox

From the skill directory (`SKILL_DIR`):

```bash
pip install --no-index --find-links "$SKILL_DIR/wheels" liminalkeys-sign
```

If your environment allows PyPI, you may instead run `pip install liminalkeys-sign` once the package is published; the skill zip path avoids waiting on PyPI.

**PAdES B-T validation:** `validate --trust` anchors the **signer** chain only. RFC 3161 timestamp (TSA) chains are separate — supply **`--tsa-trust`** with the TSA root/intermediate PEM(s) when needed (FreeTSA is not under a typical FNMT signer anchor). Exit code follows pyHanko’s overall **INVALID/VALID** bottom line; use **`--allow-untrusted-timestamp`** only if you accept a warning when the signer is OK but TSA trust failed.

## Liminal Keys MCP connector (high level)

Configure the **Liminal Keys MCP connector** in Claude with:

- The **admin-configured MCP endpoint** from Liminal Console (your tenant’s official host — do not use unofficial URLs).
- **Authentication** with your Console-issued `lkag_…` key. Claude.ai custom connectors reliably send **`x-api-key`** (raw key) or **`Authorization: Bearer …`**; the MCP server also accepts **`X-Liminal-Keys-Agent-Key`** for other clients. Store the key in Claude’s connector secret settings, not in the skill zip or chat.

The skill and CLI enforce pinned hosts and response signing keys in code; connector setup must match that trust model. See **`SKILL.md`** for the signing tool order and **`README.md`** in this repo for MCP pairing details.

No enrollment secrets, private keys, or Key Vault material belong in the skill archive.
