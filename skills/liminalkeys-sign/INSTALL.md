# Installing the liminalkeys-sign Claude skill

Liminal Keys and PDF signing via this skill are in **public beta**. Liminal Keys is **not** a qualified (or accredited) trust service provider (QTSP).

**Size limit:** Claude rejects skill uploads at **30 MiB**. Releases target **CPython 3.12 and 3.13** (manylinux x86_64) offline wheels. CPython **3.10+** is required by the package. Agent setup and connector details: https://www.liminalkeys.com/docs/agents/

## Bundled with the Claude plugin

This folder ships inside the **Liminal Keys** marketplace plugin. After install, Claude loads **`SKILL.md`**; keep **`wheels/`** next to it for offline sandbox installs.

## Visible stamp (default)

The default PDF appearance is a **branded visible** Liminal Keys stamp (last page, bottom-right). Add **`--invisible-signature`** on `prepare` only when the user explicitly wants no on-page stamp.

## MCP connector authentication

**Default:** URL-only MCP OAuth — **Connect** in Claude and sign in with Liminal Keys (same options as Console). No API key in the shipped `.mcp.json`.

**Optional:** Console-issued `lkag_…` agent API key in **`x-api-key`** only for hosts that **cannot** use MCP OAuth. Create the key in Console → **AI agents**. Use one auth mode per request.

## Install the CLI inside the sandbox

```bash
export SKILL_DIR="<skill folder>"
chmod +x "$SKILL_DIR/bin/liminal-sign"
export PATH="$SKILL_DIR/bin:$PATH"
liminal-sign --version   # expect liminalkeys-sign 0.1.14
```

`liminal-sign` caches the bundled wheel under `~/.cache/liminalkeys-sign` (wheel content hash + version). After upgrading the plugin:

```bash
rm -rf "${LIMINALKEYS_SIGN_CACHE:-$HOME/.cache/liminalkeys-sign}"
```

Manual fallback:

```bash
pip install --no-index --find-links "$SKILL_DIR/wheels" "liminalkeys-sign==0.1.14"
```

Offline wheels include pyHanko dependencies (for example `cryptography`, `lxml`, `aiohttp`). **Pillow is not bundled** (Anthropic's plugin directory caps each file at 5 MiB; Pillow wheels exceed that). The **default** visible stamp uses pre-baked `lk-watermark-device-rgb.bin` (`/LkWm0`) with **no Pillow** at runtime. If the sandbox already has Pillow, `--stamp-logo` and smaller WebP approval previews may work; otherwise those features fall back gracefully (default LK stamp and PNG previews).

**PAdES B-T:** optional MCP `timestamp` (RFC 3161; default TSA is FreeTSA, a non-qualified time-stamping service). `finish` runs a local technical validation, not legal or trust-list validation.

The skill zip ships **`liminalkeys-mcp-keys.json`** and **`liminalkeys_mcp_trust.prod.json`**; the CLI uses bundled trust by default.

See **`SKILL.md`** for the signing tool order.