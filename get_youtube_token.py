"""
Run this script ONCE on your local machine to get a YouTube refresh token.
You'll need client_id and client_secret from Google Cloud Console.
Save the printed values as GitHub secrets.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = input("YOUTUBE_CLIENT_ID: ")
CLIENT_SECRET = input("YOUTUBE_CLIENT_SECRET: ")

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(
    client_config,
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
)
creds = flow.run_local_server(port=0)

print("\n--- Copy these as GitHub secrets ---")
print(f"YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
print("------------------------------------")
