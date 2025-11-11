# ------------------------------------------------------------
# 💰 MTN MoMo Sandbox | Check Payment Status
# Author: Gideon (Kudiway)
# ------------------------------------------------------------
import requests
import urllib3

# Disable SSL warnings (safe for sandbox)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === 🔑 Credentials (yours) ===
SUBSCRIPTION_KEY = "680cb74e147047ffa5ff5e799792d2ad"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSMjU2In0.eyJjbGllbnRJZCI6IjAzMGIyMTE1LTQxZTAtNGFhOC05Y2E2LTY3M2RiYzM5N2VmYiIsImV4cGlyZXMiOiIyMDI1LTExLTExVDE4OjQ5OjE3LjMwNCIsInNlc3Npb25JZCI6ImM5N2JjMzkwLWUzN2YtNDE2Zi04YzRlLTBiMjk2NGNiYTA1MCJ9.Q_uACAlbBaayUQISy5BUkd3DW0yh-bLxuvUa6CibMnx--H14wd8K7idVsUqod8L8NTGqZ1uPVBVYBxznefh65rdK1UKxGGUfHHH_AScUUbsMbwgpg-Ew-aFykrSvc7qAbl3hxPk72FzxmIj3TZ_G6EWXUvb1zB8M4k4anmGmE4v_n1iTSapLivRjMCzB9zc8iHVwAW7I5r5jM5xLoO9Y5qqZrvIHT1Ovi9LQBplCNrS7deW49noPbNZxScvXT4C0wR2D8DU7NPqdk4yIznMF7nEDQ6-uJeRZoPZM17ibDMrHAEHlUMlo8SAsvqwCHLwrvT49JJ7w3PkpbJDjGDGmxg"

# === 🧾 Reference ID from your last successful payment ===
REFERENCE_ID = "9f367d73-5391-49da-888a-2499f8396c17"

# === 🔗 MoMo API Endpoint ===
URL = f"https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay/{REFERENCE_ID}"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "X-Target-Environment": "sandbox",
    "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
}

print(f"🔍 Checking payment status for Reference ID: {REFERENCE_ID}")
response = requests.get(URL, headers=headers, verify=False)

print("\n==================== RESPONSE ====================")
print("Status Code:", response.status_code)
print("Response Text:", response.text)
print("==================================================")

# === ✅ Success check ===
if response.status_code == 200:
    if '"SUCCESSFUL"' in response.text.upper():
        print("✅ Payment completed successfully!")
    elif '"PENDING"' in response.text.upper():
        print("⏳ Payment still pending...")
    elif '"FAILED"' in response.text.upper():
        print("❌ Payment failed.")
    else:
        print("⚠️ Unknown status — see response above.")
else:
    print("⚠️ Something went wrong — check the response details.")
