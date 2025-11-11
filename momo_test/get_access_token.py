# ------------------------------------------------------------
# 🌍 MTN MoMo Sandbox | Get Access Token (Collections)
# Author: Gideon (Kudiway)
# ------------------------------------------------------------
import base64
import requests
import urllib3

# Suppress SSL warnings (safe in sandbox)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === Your Sandbox Credentials ===
SUBSCRIPTION_KEY = "680cb74e147047ffa5ff5e799792d2ad"  # Collections Primary Key
API_USER_ID      = "030b2115-41e0-4aa8-9ca6-673dbc397efb"  # Reference ID
API_KEY          = "85726dae4e4347ca8938faa71eacaa1d"      # API Key

# === Correct Sandbox URL for Access Token ===
URL = "https://sandbox.momodeveloper.mtn.com/collection/token/"  # ✅ verified endpoint

# === Build the Authorization Header ===
basic_auth = base64.b64encode(f"{API_USER_ID}:{API_KEY}".encode()).decode()

HEADERS = {
    "Authorization": f"Basic {basic_auth}",
    "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    "X-Target-Environment": "sandbox",
    "Content-Type": "application/json"
}

print("🔐 Requesting access token from MTN MoMo Sandbox...")

# === Send the POST Request ===
try:
    response = requests.post(URL, headers=HEADERS, verify=False)
except Exception as e:
    print("❌ Network or SSL error:", e)
    exit()

# === Display Response ===
print("\n==================== RESPONSE ====================")
print("Status Code:", response.status_code)
print("Response Text:", response.text)
print("==================================================")

# === Basic Status Feedback ===
if response.status_code == 200:
    print("✅ Access token obtained successfully!")
elif response.status_code == 400:
    print("⚠️ Invalid request — check auth or header values.")
elif response.status_code == 401:
    print("🚫 Unauthorized — API key or user ID mismatch.")
elif response.status_code == 404:
    print("❌ Endpoint not found — check token URL path.")
else:
    print("❓ Unexpected status. Details above.")
