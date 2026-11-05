---
name: "liminalkeys-sign"
description: "Sign PDFs with a company certificate in Liminal Keys custody via MCP (hash-only PAdES helper; private keys never in the sandbox)."
---

# Liminal Keys PDF signing (Claude skill)

Use this skill when the user asks to sign a PDF with a **company certificate** held in Liminal Keys. Private keys never enter the sandbox.

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
- Input PDF path and target certificate id allowed by the agent's rules.

## Tool order (do not reorder)

1. **`get_certificate_chain`** — Include a fresh **`client_nonce`** (base64, ≥16 random bytes) on every tool call. Resolve the signing certificate id. Save the **signed JSON envelope** and leaf PEM for `prepare` / chain verification.
2. **`liminalkeys-sign prepare`** — Produces `tbs_digest.bin` (32 bytes), `signed_attrs.der`, and `state.pkl` under `--work-dir`. Show the user the **hex digest** from stdout.
3. **`sign_hash`** — Arguments:
   - `digest_base64`: base64 of `tbs_digest.bin` (exactly 32 bytes)
   - **`client_nonce`**: same nonce pattern as step 1 (new nonce per call)
   - **`document_label`**: short human-readable description of the document (required every time; agent-supplied, shown in audit)
   - Save the **signed MCP envelope** JSON; do not strip the `signature`, `kid`, or `nonce` fields.
4. **If `decision` is `denied`** — Stop. **Do not retry** the same or a tweaked request. Tell the user the sign was denied and why if the MCP returned a reason.
5. **Optional B-T timestamp** — After `sign_hash` succeeds, build an RFC 3161 timestamp request for the **SHA-256 hash of the raw RSA signature bytes** (same imprint pyHanko uses). Call MCP **`timestamp`** with the DER request; save the DER response as `timestamp.der`.
6. **`liminalkeys-sign embed`** — Prefer MCP mutual auth:
   - `--mcp-sign-envelope` (signed `sign_hash` JSON), `--expected-nonce`, `--mcp-host` (optional `--mcp-trust-config`; default prod trust + JWKS bootstrap)
   - Optional `--mcp-chain-envelope` + `--chain-trust` to verify chain anchoring before embed
   - Or legacy `--signature` file if envelopes were verified with `liminalkeys-sign mcp-verify` first
   - **Always** pass the leaf `--cert`. Pass `--timestamp-response timestamp.der` when step 5 ran.
7. **`liminalkeys-sign validate`** — **Mandatory.** Run on the output PDF with `--trust` set to the leaf or tenant trust anchor PEM. **Always show the full validation report** to the user. If exit code is non-zero, do **not** treat the file as signed; explain the failure.

## Rules

- **Always** pass a non-empty `document_label` on every `sign_hash` call.
- **Never** retry a denied `sign_hash` in the same signing attempt.
- **Never** skip `validate` or hide its report.
- **Never** embed if local signature verification against the leaf cert fails (the CLI enforces this).
- v1: RSA only; no decrypt tools; no revocation/LTV helpers.

## Example shell flow

```bash
WORK=./lk-sign-work
mkdir -p "$WORK"

DIGEST_HEX=$(liminalkeys-sign prepare contract.pdf --cert "$WORK/leaf.pem" --work-dir "$WORK" | tail -1)

# Call MCP sign_hash with file:$WORK/tbs_digest.bin and document_label="Q4 vendor agreement"

printf '%s' "$SIGNATURE_B64" | base64 -d > "$WORK/signature.bin"

liminalkeys-sign embed --work-dir "$WORK" --cert "$WORK/leaf.pem" \
  --signature "$WORK/signature.bin" --output "$WORK/signed.pdf" \
  --timestamp-response "$WORK/timestamp.der"

liminalkeys-sign validate "$WORK/signed.pdf" --trust "$WORK/leaf.pem" --report "$WORK/validation.txt"
cat "$WORK/validation.txt"
```

Adjust paths for the sandbox OS. Obtain `leaf.pem` from MCP, not from user-supplied key material.
