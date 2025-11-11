# ------------------------------------------------------------
# 💰 MTN MoMo Sandbox | Request a Payment (C2B)
# Author: Gideon (Kudiway)
# ------------------------------------------------------------
import requests
import uuid
import urllib3

# Disable SSL verification warnings (safe for sandbox only)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === 🔑 Credentials (yours) ===
SUBSCRIPTION_KEY = "680cb74e147047ffa5ff5e799792d2ad"
API_USER_ID = "030b2115-41e0-4aa8-9ca6-673dbc397efb"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSMjU2In0.eyJjbGllbnRJZCI6IjAzMGIyMTE1LTQxZTAtNGFhOC05Y2E2LTY3M2RiYzM5N2VmYiIsImV4cGlyZXMiOiIyMDI1LTExLTExVDE4OjQ5OjE3LjMwNCIsInNlc3Npb25JZCI6ImM5N2JjMzkwLWUzN2YtNDE2Zi04YzRlLTBiMjk2NGNiYTA1MCJ9.Q_uACAlbBaayUQISy5BUkd3DW0yh-bLxuvUa6CibMnx--H14wd8K7idVsUqod8L8NTGqZ1uPVBVYBxznefh65rdK1UKxGGUfHHH_AScUUbsMbwgpg-Ew-aFykrSvc7qAbl3hxPk72FzxmIj3TZ_G6EWXUvb1zB8M4k4anmGmE4v_n1iTSapLivRjMCzB9zc8iHVwAW7I5r5jM5xLoO9Y5qqZrvIHT1Ovi9LQBplCNrS7deW49noPbNZxScvXT4C0wR2D8DU7NPqdk4yIznMF7nEDQ6-uJeRZoPZM17ibDMrHAEHlUMlo8SAsvqwCHLwrvT49JJ7w3PkpbJDjGDGmxg"

# === 🔗 MoMo API Endpoint ===
URL = "https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay"

# === 🧾 Generate unique Reference ID for each transaction ===
ref_id = str(uuid.uuid4())
print(f"🪪 Reference ID for this transaction: {ref_id}")

# === 💵 Payment details ===
payload = {
    "amount": "5",  # test amount
    "currency": "EUR",  # sandbox uses EUR
    "externalId": "KudiPayTest123",
    "payer": {
        "partyIdType": "MSISDN",
        "partyId": "46733123453"  # MTN sandbox test number
    },
    "payerMessage": "Test Payment from KudiPay",
    "payeeNote": "Sandbox test transaction"
}

# === 🧾 Headers ===
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "X-Reference-Id": ref_id,
    "X-Target-Environment": "sandbox",
    "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    "Content-Type": "application/json"
}

print("💳 Sending payment request to MoMo Sandbox...")
response = requests.post(URL, headers=headers, json=payload, verify=False)

print("\n==================== RESPONSE ====================")
print("Status Code:", response.status_code)
print("Response Text:", response.text)
print("==================================================")

# === ✅ Check result ===
if response.status_code == 202:
    print(f"✅ Payment request accepted! Use this Reference ID to check status:\n➡️ {ref_id}")
else:
    print("⚠️ Something went wrong — check details above.")
