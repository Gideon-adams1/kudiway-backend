# ------------------------------------------------------------
# 🌍 MTN MoMo Sandbox | Create API User for KudiPay
# Author: Gideon (Kudiway)
# ------------------------------------------------------------
import uuid
import requests
import json

# Your MoMo Sandbox credentials
SUBSCRIPTION_KEY = "680cb74e147047ffa5ff5e799792d2ad"
APP_NAME = "KudiPay"
CALLBACK_URL = "https://kudiway.com"

# Generate a new Reference ID (UUID) for this API user
REFERENCE_ID = str(uuid.uuid4())

# MTN Sandbox endpoint
URL = "https://sandbox.momodeveloper.mtn.com/v1_0/apiuser"


# Required headers
HEADERS = {
    "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    "X-Reference-Id": REFERENCE_ID,
    "Content-Type": "application/json",
}

# Request body
BODY = {
    "providerCallbackHost": CALLBACK_URL
}

print("🚀 Creating MoMo API User for:", APP_NAME)
print("🔗 Endpoint:", URL)
print("🧩 Reference ID:", REFERENCE_ID)

# Send request
response = requests.post(URL, headers=HEADERS, json=BODY)

print("\n==================== RESPONSE ====================")
print("Status Code:", response.status_code)
print("Response Text:", response.text)
print("Reference ID (save this):", REFERENCE_ID)
print("==================================================")

# Optional helper for quick debugging
if response.status_code == 201:
    print("✅ Success! API User created successfully.")
elif response.status_code == 400:
    print("⚠️ Bad Request — check body formatting or headers.")
elif response.status_code == 401:
    print("❌ Unauthorized — invalid subscription key.")
elif response.status_code == 403:
    print("🚫 Forbidden — subscription inactive or wrong product.")
else:
    print("❓ Unexpected status, details above.")
