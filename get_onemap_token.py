"""Request a OneMap token interactively and save it to the project's .env file.

Run: python get_onemap_token.py
Credentials are sent only to OneMap and are not saved. The token is not printed.
"""

import json
from datetime import datetime, timedelta, timezone
from getpass import getpass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import set_key


TOKEN_URL = "https://www.onemap.gov.sg/api/auth/post/getToken"
SINGAPORE_TIMEZONE = timezone(timedelta(hours=8))


def request_token(email, password):
    """Return a validated token and expiry without exposing provider responses."""
    body = json.dumps({"email": email, "password": password}).encode("utf-8")
    request = Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            payload = json.load(response)
    except HTTPError as error:
        status = error.code
        error.close()
        if status in (401, 403, 404):
            raise RuntimeError("OneMap rejected the login. Check your registered account credentials.") from None
        if status == 429:
            raise RuntimeError("OneMap's request limit was reached. Try again later.") from None
        raise RuntimeError("OneMap could not issue a token. Try again later.") from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("Could not reach OneMap. Check your connection and try again.") from None
    except (ValueError, UnicodeError):
        raise RuntimeError("OneMap returned an invalid response. No token was saved.") from None

    if not isinstance(payload, dict):
        raise RuntimeError("OneMap returned an invalid response. No token was saved.")
    token = payload.get("access_token")
    if not isinstance(token, str) or not token or any(char.isspace() for char in token):
        raise RuntimeError("OneMap did not return a valid token. No token was saved.")
    try:
        timestamp = payload["expiry_timestamp"]
        if isinstance(timestamp, bool):
            raise ValueError
        expiry = datetime.fromtimestamp(int(timestamp), SINGAPORE_TIMEZONE)
        if expiry <= datetime.now(SINGAPORE_TIMEZONE):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        raise RuntimeError("OneMap returned an invalid token expiry. No token was saved.") from None
    return token, expiry


def main():
    """Prompt in the user's terminal; keep the existing .env settings intact."""
    try:
        email = input("OneMap registered email: ").strip()
        password = getpass("OneMap password (hidden): ")
        if not email or not password:
            print("Email and password are required. No token was saved.")
            return 1
        token, expiry = request_token(email, password)
        env_path = Path(__file__).resolve().parent / ".env"
        saved, _, _ = set_key(str(env_path), "ONEMAP_ACCESS_TOKEN", token, quote_mode="always")
        if not saved:
            raise OSError
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. No token was saved.")
        return 1
    except RuntimeError as error:
        print(str(error))
        return 1
    except OSError:
        print("Could not save the token to .env. Check file permissions.")
        return 1

    print("OneMap token saved to .env. Other settings were preserved.")
    print(f"Expires: {expiry:%Y-%m-%d %H:%M:%S} SGT")
    print("Restart running apps to use the new token. For Docker: docker compose up -d --force-recreate gui")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
