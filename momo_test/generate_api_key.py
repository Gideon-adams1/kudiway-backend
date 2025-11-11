# ------------------------------------------------------------
# 🌍 MTN MoMo Sandbox | Generate API Key for KudiPay
# Author: Gideon (Kudiway)
# ------------------------------------------------------------
import requests

# Use the same Primary Key and Reference ID from your previous step
SUBSCRIPTION_KEY = "680cb74e147047ffa5ff5e799792d2ad"
REFERENCE_ID = "030b2115-41e0-4aa8-9ca6-673dbc397efb"

URL = f"https://sandbox.momodeveloper.mtn.com/v1_0/apiuser/{REFERENCE_ID}/apikey"

HEADERS = {
    "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    "Content-Type": "application/json",
}

print("🔑 Generating API Key for Reference ID:", REFERENCE_ID)
print("🔗 Endpoint:", URL)

response = requests.post(URL, headers=HEADERS)

print("\n==================== RESPONSE ====================")
print("Status Code:", response.status_code)
print("Response Text:", response.text)
print("==================================================")

if response.status_code == 201:
    print("✅ API Key generated successfully!")
else:
    print("⚠️ Something went wrong — check the response above.")
