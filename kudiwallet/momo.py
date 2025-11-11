# ------------------------------------------------------------
# 💳 MTN MoMo API Helper for KudiPay (Sandbox Mode)
# Author: Gideon (Kudiway)
# ------------------------------------------------------------
import requests
import uuid
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === 🔑 Credentials (yours) ===
SUBSCRIPTION_KEY = "680cb74e147047ffa5ff5e799792d2ad"
API_USER_ID = "030b2115-41e0-4aa8-9ca6-673dbc397efb"
CALLBACK_URL = "https://kudiway.com/momo/callback/"
BASE_URL = "https://sandbox.momodeveloper.mtn.com"
TARGET_ENV = "sandbox"

# ------------------------------------------------------------
# 🧾 Generate Access Token
# ------------------------------------------------------------
def get_access_token(api_key: str) -> str:
    """Get MoMo API access token using API Key and User ID"""
    url = f"{BASE_URL}/collection/token/"
    headers = {
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Authorization": f"Basic {requests.utils.to_native_string(uuid.uuid4())}",  # placeholder
    }
    # ✅ Real Authorization header
    import base64
    basic = base64.b64encode(f"{API_USER_ID}:{api_key}".encode()).decode()
    headers["Authorization"] = f"Basic {basic}"

    print("🔐 Requesting MoMo access token...")
    resp = requests.post(url, headers=headers, verify=False)
    if resp.status_code == 200:
        return resp.json().get("access_token")
    else:
        print("⚠️ Failed to obtain access token:", resp.text)
        return None


# ------------------------------------------------------------
# 💰 Request a Payment from User
# ------------------------------------------------------------
def request_payment(amount: str, phone: str, external_id="KudiPayTxn123", api_key=None):
    """Request payment from user’s MoMo wallet"""
    if api_key is None:
        print("⚠️ API Key required for payment request")
        return None

    token = get_access_token(api_key)
    if not token:
        print("❌ Could not obtain access token")
        return None

    ref_id = str(uuid.uuid4())
    url = f"{BASE_URL}/collection/v1_0/requesttopay"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Reference-Id": ref_id,
        "X-Target-Environment": TARGET_ENV,
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "amount": str(amount),
        "currency": "EUR",
        "externalId": external_id,
        "payer": {"partyIdType": "MSISDN", "partyId": phone},
        "payerMessage": "Payment via KudiPay",
        "payeeNote": "Thanks for using Kudiway!",
    }

    print(f"💳 Sending MoMo payment request for ₵{amount} to {phone}...")
    resp = requests.post(url, headers=headers, json=payload, verify=False)
    print("Response:", resp.status_code, resp.text)

    if resp.status_code == 202:
        return {"reference_id": ref_id, "status": "pending"}
    return {"error": resp.text}


# ------------------------------------------------------------
# 🔍 Check Payment Status
# ------------------------------------------------------------
def check_payment_status(reference_id: str, api_key: str):
    """Check status of a previous payment request"""
    token = get_access_token(api_key)
    if not token:
        return {"error": "Access token failure"}

    url = f"{BASE_URL}/collection/v1_0/requesttopay/{reference_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Target-Environment": TARGET_ENV,
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
    }
    resp = requests.get(url, headers=headers, verify=False)
    try:
        return resp.json()
    except Exception:
        return {"error": resp.text}
