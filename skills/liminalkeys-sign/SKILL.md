---
name: "liminalkeys-sign"
description: "Sign content with a certificate identity in Liminal Keys custody via MCP (hash-only signing; includes optional PAdES PDF helper — private keys never in the sandbox)."
version: "0.1.12"
---

# Liminal Keys hash signing (Claude skill)

Sign a **SHA-256 digest** with a **certificate in Liminal Keys custody**. Private keys never enter the sandbox. **Do not narrate between steps.** Run only the tools and shell commands below, in order, with no duplicate MCP calls.

## Runtime (once per sandbox)

```bash
export SKILL_DIR="<folder containing this file>"
chmod +x "$SKILL_DIR/bin/liminal-sign"
export PATH="$SKILL_DIR/bin:$PATH"
liminal-sign --version   # must print liminalkeys-sign 0.1.12
```

`liminal-sign` installs the bundled wheel into a **content-addressed cache** under `~/.cache/liminalkeys-sign` (override with `LIMINALKEYS_SIGN_CACHE`). The cache key includes the wheel SHA-256 — **do not** run `pip install liminalkeys-sign` from PyPI or hand-roll a venv unless `liminal-sign` is missing from the skill folder.

If `liminal-sign` fails (non-zero exit, missing wheel, `python3`/`pip` error): **stop the signing attempt**, show the stderr to the user, and **do not** substitute another signing path. **Never** improvise.

MCP: admin-configured Liminal Keys endpoint only. Trust pins ship in the skill; omit `--mcp-trust-config` unless overriding.

### Forbidden (branded stamp)

- **No** Python scripts that import `pyhanko` for `prepare` / `embed` / `TextStampStyle` / `PdfSigner`.
- **No** pyHanko CLI or tutorial snippets (`Digitally signed by …` / pink stamp artwork).
- **No** `pip install pyhanko` as a workaround when `liminal-sign` fails.
- PDF signing is **only** `liminal-sign prepare` → MCP `sign_hash` → `liminal-sign finish`.

When the bundled CLI runs, `prepare` and `finish` **fail closed** if the PDF would show pyHanko's default stamp instead of the Liminal Keys plate (`/LkWm0`, `Signed with Liminal Keys`).

## Fixed flow

### 1. Certificates (MCP — exactly once each)

**`list_certificates`** — pass **`client_nonce`** (base64, ≥16 random bytes). Save `NONCE` for later `sign_hash` / `finish`.

**Pick `certificate_id` without asking the user when:**

- Exactly one certificate is allowed for signing, or
- The user already named a subject / id / rule — match that one.

Ask **only** if multiple equally valid signing certs remain.

**`get_certificate_chain`** — **`certificate_id`** + **new** `client_nonce`. Write the full PEM chain once to `$WORK/chain.pem`. Do **not** call `list_certificates` or `get_certificate_chain` again in this attempt.

When Console or the user exposes signer **locale** or **timezone** (e.g. `Europe/Madrid`, `de-DE`), pass them on `prepare` (below). Do not guess timezone.

### 2. Local prepare (one shell command)

**Default:** branded **visible** Liminal Keys stamp (248×96 pt), **last page**, **bottom-right**, LK logo watermark (`/LkWm0`), structured fields (signer, date, issuer, serial when tall enough), footer **Signed with Liminal Keys**, dates like **`CET (UTC+1)`** when timezone is set. Appearance is hashed in CMS signed attributes — set placement/locale **here**, not after `sign_hash`.

```bash
WORK=./lk-sign-work
mkdir -p "$WORK"
liminal-sign prepare --pdf "$PDF" --cert-chain "$WORK/chain.pem" \
  --out "$WORK/state.json" --document-label "$DOCUMENT_LABEL"
```

Add stamp overrides only when the user asks (or locale/timezone from cert metadata):

```bash
# Example: Spanish dates in Madrid time
liminal-sign prepare --pdf "$PDF" --cert-chain "$WORK/chain.pem" \
  --out "$WORK/state.json" --document-label "$DOCUMENT_LABEL" \
  --stamp-locale es-ES --stamp-timezone Europe/Madrid
```

**Invisible field only** when the user explicitly wants no on-page stamp: add **`--invisible-signature`**.

Read **`$WORK/state.json`**: use **`digest_base64`** and **`previews`** on `sign_hash`. Do not re-run `approval-preview` or a second `prepare` for the same PDF.

### 3. `sign_hash` (one call; long-poll)

Call **once** with:

| Field | Value |
|-------|--------|
| `certificate_id` | from step 1 |
| `digest_base64` | from `state.json` |
| `document_label` | short human label (required) |
| `client_nonce` | `NONCE` from step 1 (first attempt for this digest) |
| `previews` | `state.json` → `previews` (required when approval may apply) |
| `poll_timeout_seconds` | **120** (default) unless you need immediate `pending_approval` |

Save the full signed JSON envelope to `$WORK/sign.json` (keep `signature`, `kid`, `nonce`).

**After the user has approved:** on `401`, timeout, transport error, or `pending_approval` after a full poll — call **`sign_hash` again** with the **same** `digest_base64`, **`client_nonce`**, and **`approval_id`**. Never mint a new approval or change nonce after approval. **Never** retry after `decision: denied`.

Optional B-T timestamp only if the user asked: MCP `timestamp` → `$WORK/timestamp.der` (pass to `finish`).

### 4. Finish (one shell command)

```bash
liminal-sign finish --state "$WORK/state.json" --mcp-sign-envelope "$WORK/sign.json" \
  --expected-nonce "$NONCE" --output "$WORK/signed.pdf"
```

Show the validation report printed to stdout. Non-zero exit = not signed.

Add `--timestamp-response "$WORK/timestamp.der"` when step 3 included a timestamp.

## Hard rules

- **One** `list_certificates`, **one** `get_certificate_chain`, **one** `prepare`, **one** primary `sign_hash` (retries only collect with same `approval_id` / `client_nonce`).
- **No** re-listing certs, **no** second chain fetch, **no** extra model commentary between tool calls.
- **Always** run `finish` (includes mandatory validate); never skip the report.
- **Only** the bundled `liminal-sign` commands above may create visible stamps — not pyHanko defaults (`Digitally signed by …`).
- v1: RSA / `sha256_rsa` only.

## Clearing a stale CLI cache

After upgrading the plugin or if the stamp looks like pyHanko's default monospace box:

```bash
rm -rf "${LIMINALKEYS_SIGN_CACHE:-$HOME/.cache/liminalkeys-sign}"
liminal-sign --version
```

Then re-run the signing flow from step 1.

## Stamp overrides (user-requested)

| User says | `prepare` adds |
|-----------|----------------|
| No visible stamp | `--invisible-signature` |
| Different corner / page | `--stamp-anchor …` / `--stamp-page …` |
| Reason on stamp | `--stamp-reason "…"` (or use `--document-label`) |
| Locale / timezone | `--stamp-locale de-DE` / `--stamp-timezone Europe/Madrid` |
| Custom logo instead of LK watermark | `--stamp-logo path.png` |

See `INSTALL.md` for uploading this skill and MCP connector setup.