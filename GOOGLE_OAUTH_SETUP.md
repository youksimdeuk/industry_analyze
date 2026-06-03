# Google OAuth token refresh

This project requires a Google OAuth token whose scopes match the app code.

Current required scopes:

- `https://www.googleapis.com/auth/drive`
- `https://www.googleapis.com/auth/spreadsheets`

## Why GitHub Actions failed

The workflow read `token.json` from the GitHub secret `GOOGLE_TOKEN_JSON`, but that token was issued only for `drive.readonly`.
When the app tried to refresh it with broader scopes, Google returned `invalid_scope`.

## Proper fix

1. Put a valid `credentials.json` in the project root.
2. Run:

```bash
python refresh_google_token.py
```

3. Complete the browser login and consent flow.
4. Open the new `token.json`.
5. Copy its full JSON into the GitHub repository secret `GOOGLE_TOKEN_JSON`.
6. Re-run the GitHub Actions workflow.

## Notes

- GitHub Actions cannot complete the browser-based OAuth consent flow by itself.
- If scopes change again later, regenerate `token.json` the same way.
