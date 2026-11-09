---
name: "liminalkeys-sign"
description: "Sign content with a certificate identity in Liminal Keys custody via MCP (hash-only signing; includes optional PAdES PDF helper — private keys never in the sandbox)."
version: "0.1.9"
---

# Liminal Keys hash signing (Claude skill)

Use this skill when the user asks to sign **a SHA-256 digest** with a **certificate identity you already hold** in Liminal Keys custody (closed beta / design-partner path). Liminal Keys signs **the hash you send** — file format is up to your pipeline (PDF PAdES via `prepare`/`embed` is one supported example). Private keys never enter the sandbox. Liminal Keys is not a qualified trust service provider and does not issue publicly trusted document certificates except labelled self-signed testing identities.

## Install

From the skill directory (the folder that contains this file and `wheels/`):

```bash
pip install --no-index --find-links "$SKILL_DIR/wheels" liminalkeys-sign
```

Set `SKILL_DIR` to that folder path in the sandbox. When PyPI publication is available for your version, `pip install liminalkeys-sign` is an optional fallback if the sandbox allows index access.

See **`INSTALL.md`** for uploading the skill zip to Claude and MCP connector setup at a high level.

## Prerequisites

- **MCP connector URL must be the admin-configured Liminal Keys endpoint** (your tenant's official MCP host from Console). Do not point connectors at unofficial or user-supplied URLs; **`liminalkeys-sign` enforces the pinned host and service signing key in code**, not via prompt instructions alone.
- Liminal Keys MCP connector configured (API key header in v1).
- **MCP trust (no attach required):** The skill zip ships **`liminalkeys-mcp-keys.json`** (production JWKS, kid `mcp-response-v1`) and **`liminalkeys_mcp_trust.prod.json`**. After `pip install`, omit `--mcp-trust-config` — the wheel bundles the same pins for offline verification. Override only when you need a custom trust file: `--mcp-trust-config /path/to.json`.
- For the bundled PAdES PDF path: input PDF path and target certificate id allowed by the agent's rules.

## Tool order (do not reorder)

1. **`list_certificates`** — Include **`client_nonce`** (base64, ≥16 random bytes). Pick the **`certificate_id`** to sign with (subject, expiry, policy).
2. **`get_certificate_chain`** — Pass that **`certificate_id`** and a **new** **`client_nonce`** for this call. Save the **signed JSON envelope** and write the leaf PEM to `$WORK/leaf.pem` for `prepare` / chain verification.
3. **`liminalkeys-sign prepare`** — Produces `tbs_digest.bin` (32 bytes), `signed_attrs.der`, and `state.pkl` under `--work-dir`. Signature fields are **invisible by default**. Use `--visible-signature` only when the user wants an on-page stamp; optional `--stamp-page` (`first` | `last` | page number), `--stamp-anchor` (corners), `--stamp-margin` (points from the page edge), `--stamp-reason`, `--stamp-logo` (PNG/JPEG), and `--stamp-locale` (BCP47 date formatting). Visible stamps render **signer name, date, and optional reason** (pyHanko appearance). Show the user the **hex digest** from stdout.

### Natural language → `prepare` flags (visible stamp)

| User says | `prepare` flags |
|-----------|-----------------|
| “Sign invisibly” (default) | omit `--visible-signature` |
| “Bottom-right stamp on the last page” | `--visible-signature --stamp-page last --stamp-anchor bottom-right` |
| “Top-left stamp, 48 pt margin” | `--visible-signature --stamp-anchor top-left --stamp-margin 48` |
| “First page, bottom-left, reason Contract countersign” | `--visible-signature --stamp-page first --stamp-anchor bottom-left --stamp-reason "Contract countersign"` |
| “Page 3 stamp” | `--visible-signature --stamp-page 3` |
| “Stamp with our logo and German dates” | `--visible-signature --stamp-logo ./logo.png --stamp-locale de-DE` |
| “Visible stamp, UK date format” | `--visible-signature --stamp-locale en-GB` |
4. **Before `sign_hash` (when approval may apply)** — Render page 1 as a small PNG when you can (`pdftoppm -png -r 50 -f 1 -l 1` for PDFs), or run `liminalkeys-sign approval-preview --digest-hex "$DIGEST_HEX" --output "$WORK/approval.png"` (or omit `--output` to print base64). You **must** pass at least one preview in `sign_hash` `previews` on the **first** attempt for the digest — do not skip previews and hope a retry will attach them.
5. **`sign_hash`** — Arguments:
   - `certificate_id`: UUID from step 1
   - `digest_base64`: base64 of the 32-byte digest (from `prepare` / your own hashing step)
   - **`client_nonce`**: fresh random base64 (≥16 bytes) on the **first** sign attempt for this digest; **reuse the exact same value** when polling or collecting after `pending_approval` (changing it creates a duplicate approval).
   - **`approval_id`** (optional): UUID from the `pending_approval` JSON — pass it on every repeat until you receive a signature envelope.
   - **`poll_timeout_seconds`** (optional, 0–120, **default 120**): MCP long-polls with the same `approval_id` and `client_nonce` until signed, rejected, expired, or timeout. Pass **`0`** only when you need an immediate `pending_approval` JSON without waiting.
   - **`document_label`**: short human-readable description of what is being signed (required every time; agent-supplied, shown in audit)
   - **`previews`** (**required** when policy may require human approval in Console): send **at least one** small thumbnail — `{ "content_type": "image/png" | "image/jpeg" | "image/webp", "content_base64": "..." }`, up to **3** total, each **≤ 1 MiB decoded**. **Always** include the output of `liminalkeys-sign approval-preview` (or your own small page-1 PNG) on the **first** call. Previews are **agent-rendered, unverified** context for approvers only (not proof of digest).
   - Save the **signed MCP envelope** JSON; do not strip the `signature`, `kid`, or `nonce` fields.
6. **If `decision` is `denied`** — Stop. **Do not retry** the same or a tweaked request. Tell the user the sign was denied and why if the MCP returned a reason.
7. **Optional B-T timestamp (off by default)** — Only if the user wants a document timestamp: build an RFC 3161 timestamp request for the **SHA-256 hash of the raw RSA signature bytes** (same imprint pyHanko uses). Call MCP **`timestamp`** with the DER request; save the DER response as `timestamp.der`. Default TSA is **FreeTSA** (non-qualified; disclose that to the user — no legal presumption of time accuracy).
8. **`liminalkeys-sign embed`** — Prefer MCP mutual auth:
   - `--mcp-sign-envelope` (signed `sign_hash` JSON), `--expected-nonce`, `--mcp-host` (optional `--mcp-trust-config`; default prod trust + JWKS bootstrap)
   - Optional `--mcp-chain-envelope` + `--chain-trust` to verify chain anchoring before embed
   - Or legacy `--signature` file if envelopes were verified with `liminalkeys-sign mcp-verify` first
   - **Always** pass the leaf `--cert`. Pass `--timestamp-response timestamp.der` when step 7 ran.
9. **`liminalkeys-sign validate`** — **Mandatory.** Run on the output PDF with `--trust` set to the leaf or tenant trust anchor PEM. **Always show the full validation report** to the user. If exit code is non-zero, do **not** treat the file as signed; explain the failure.

## Rules

- **Always** pass a non-empty `document_label` on every `sign_hash` call.
- **When approval flows apply**, **always** send at least one **small PNG preview** (page 1 for PDFs); do not leave approvers with an empty preview panel. Malformed previews are omitted with warnings, not a hard tool failure — correct and call `sign_hash` again on the first attempt if needed.
- **`sign_hash` blocks up to `poll_timeout_seconds` (default 120)** while approval is pending. If it still returns `pending_approval`, **immediately** call again with **`approval_id`** and the **same `client_nonce`** (or reconnect MCP only if `approval_id` is missing from the tool schema).
- **Never** retry a denied `sign_hash` in the same signing attempt.
- **Never** skip `validate` or hide its report.
- **Never** embed if local signature verification against the leaf cert fails (the CLI enforces this).
- v1: RSA only; no decrypt tools; no revocation/LTV helpers.

## Example shell flow

```bash
WORK=./lk-sign-work
mkdir -p "$WORK"
NONCE=$(openssl rand -base64 24)

# MCP list_certificates with client_nonce=$NONCE → pick certificate_id
# MCP get_certificate_chain with certificate_id + fresh client_nonce → save chain; write leaf to $WORK/leaf.pem

DIGEST_HEX=$(liminalkeys-sign prepare contract.pdf --cert "$WORK/leaf.pem" --work-dir "$WORK" | tail -1)
PREVIEW_B64=$(liminalkeys-sign approval-preview --digest-hex "$DIGEST_HEX")
DIGEST_B64=$(base64 -w0 "$WORK/tbs_digest.bin")

# MCP sign_hash: certificate_id, digest_base64=$DIGEST_B64, document_label, client_nonce=$NONCE,
# previews=[{content_type:"image/png", content_base64: PREVIEW_B64}] → save $WORK/sign.json
# If pending_approval: call sign_hash again with same digest, client_nonce=$NONCE, and approval_id

liminalkeys-sign embed --work-dir "$WORK" --cert "$WORK/leaf.pem" \
  --mcp-sign-envelope "$WORK/sign.json" --expected-nonce "$NONCE" --mcp-host mcp.liminalkeys.com \
  --output "$WORK/signed.pdf"

liminalkeys-sign validate "$WORK/signed.pdf" --trust "$WORK/leaf.pem" --report "$WORK/validation.txt"
cat "$WORK/validation.txt"
```

Adjust paths for the sandbox OS. Obtain `leaf.pem` from MCP, not from user-supplied key material. Add `--timestamp-response timestamp.der` to `embed` only when the user asked for a timestamp and step 7 produced `timestamp.der`.
