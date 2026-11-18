# Changelog

## 0.1.12 (2026-11-18)

- **Root-cause fix for pyHanko default stamps**: `prepare` / `finish` fail closed when the PDF would show pyHanko's `Digitally signed by …` default (`stamp_branding_guard`).
- **`bin/liminal-sign`**: cache key includes bundled wheel **SHA-256** (not version alone); clear errors when offline install fails (no silent fallback).
- **SKILL.md**: forbid hand-written pyHanko signing; require `liminal-sign --version` **0.1.12**; document cache reset.
- **CI**: rebuild check — bundled `skills/liminalkeys-sign/wheels/liminalkeys_sign-*.whl` must match `packages/liminalkeys-sign` source.
- Plugin/marketplace manifests and skill wheel synced to **0.1.12**.

## 0.1.10 (2026-11-15)

- **`prepare --out state.json`**: single step for CMS hash, compressed page-1 preview (WebP when Pillow + `pdftoppm` available), and `sign_hash` payload (`digest_base64`, `previews`, artifact paths).
- **`prepare --cert-chain`**: split a PEM chain file into leaf + intermediates; optional `--pdf` alias.
- **`finish`**: `embed` + mandatory `validate` in one command, driven by `state.json`.
- **`liminal-sign` console alias** matching `liminalkeys-sign`.
- Skill **`bin/liminal-sign`**: installs the bundled wheel into a versioned cache venv once per machine/session (no repeated `pip install` each signing run); falls back to `--target` site-packages when `venv` is unavailable.
- Offline wheels: add **`typing_extensions`** (pyHanko → `aiohttp` dependency) for resolver-free sandbox installs.
- **`bin/liminal-sign`**: always `python3 -m liminalkeys_sign` (no PATH recursion); recursion guard env `LIMINAL_SIGN_IN_RUN_CLI`.
- **Pillow**: cp312 + cp313 manylinux wheels for `--stamp-logo` only; default watermark via **`lk-watermark-device-rgb.bin`** (`/LkWm0` DeviceRGB XObject, no Pillow at runtime).
- **SKILL.md**: fixed minimal MCP/tool flow — one certificate list, one chain fetch, no re-listing, no narration between steps; `sign_hash` retry uses the same `approval_id` / `client_nonce`.
- **Branded visible stamp** (from liminal-keys): neutral plate, LK watermark (`lk-square-mark-cropped.png`), WinAnsi ellipsis, serial grouping, locale/timezone dates, 248×96 default; **visible stamp is prepare default** (`--invisible-signature` to opt out).

## 0.1.9

- Initial packaged skill with invisible-by-default PAdES, approval previews, MCP envelope embed, and validation gate.