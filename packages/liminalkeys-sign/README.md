# liminalkeys-sign

PAdES helper for Liminal Keys agent signing. See the skill `SKILL.md` in the Claude plugin for the minimal orchestration flow.

## Fast path (0.1.10+)

```bash
liminal-sign prepare --pdf doc.pdf --cert-chain chain.pem --out state.json
# MCP sign_hash once using fields from state.json (digest_base64, previews)
liminal-sign finish --state state.json --mcp-sign-envelope sign.json \
  --expected-nonce "$NONCE" --output signed.pdf
```

Bundled skill installs use `skills/liminalkeys-sign/bin/liminal-sign` with a cached venv.