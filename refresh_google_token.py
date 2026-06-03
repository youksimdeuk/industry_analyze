from google_oauth import GOOGLE_TOKEN_PATH, SCOPES, refresh_google_token


if __name__ == "__main__":
    token_path = refresh_google_token()
    print("New Google OAuth token generated.")
    print(f"Requested scopes: {SCOPES}")
    print(f"Saved token to: {token_path}")
    print("Next step: copy the contents of token.json into the GitHub secret GOOGLE_TOKEN_JSON.")
