import requests
import json
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
import os
import sys
import random
import re
import logging
import traceback

load_dotenv(override=True) 
# ================== CONFIG (GLOBAL) ==================
username = os.environ.get("NAUKRI_USERNAME")
password = os.environ.get("NAUKRI_PASSWORD")
file_id = os.environ.get("FILE_ID")
form_key = os.environ.get("FORM_KEY")   # Extract manually from network tab
filename = os.environ.get("FILENAME") 
DEBUG = os.environ.get("NAUKRI_DEBUG", os.environ.get("DEBUG", "0")).lower() in ("1", "true", "yes")

# --- PROXY CONFIG ---
proxy_url = os.environ.get("PROXY_URL")
proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None


def setup_logger():
    level = logging.DEBUG if DEBUG else logging.INFO
    logger = logging.getLogger("naukri_updater")
    logger.setLevel(level)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    return logger


logger = setup_logger()


# ================== UTIL ==================
def generate_file_key(length):
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ''.join(random.choice(chars) for _ in range(length))


# ================== LOGIN CLIENT ==================
class NaukriLoginClient:
    LOGIN_URL = "https://www.naukri.com/central-login-services/v1/login"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        
        # Apply proxy to the session if it exists
        if proxies:
            self.session.proxies.update(proxies)

    def _get_headers(self):
        return {
            "accept": "application/json",
            "appid": "105",
            "clientid": "d3skt0p",
            "content-type": "application/json",
            "referer": "https://www.naukri.com/nlogin/login",
            "systemid": "jobseeker",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
        }

    def _get_payload(self):
        return {
            "username": self.username,
            "password": self.password
        }

    def login(self):
        response = self.session.post(
            self.LOGIN_URL,
            headers=self._get_headers(),
            json=self._get_payload()
        )
        print(response.text); print(response.text); response.raise_for_status()
        logger.info(f"Login status: {response.status_code}")
        logger.debug("Login response (truncated): %s", response.text[:1000])
        return response

    def get_cookies(self):
        return self.session.cookies.get_dict()

    def get_bearer_token(self):
        token = self.get_cookies().get("nauk_at")
        logger.debug("Bearer token present: %s", bool(token))
        return token

    def fetch_profile_id(self):
        resp = self.session.get(
            "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/dashboard",
            headers={
                "accept": "application/json",
                "appid": "105",
                "clientid": "d3skt0p",
                "systemid": "Naukri",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "authorization": f"Bearer {self.get_bearer_token()}",
            },
        )

        resp.raise_for_status()
        data = resp.json()

        profile_id = data.get("dashBoard", {}).get("profileId") or data.get("profileId")

        if not profile_id:
            raise Exception("Profile ID not found")
        logger.info(f"Profile ID: {profile_id}")
        logger.debug("Profile dashboard payload keys: %s", list(data.keys()))
        return profile_id

    def build_required_cookies(self):
        cookies = self.get_cookies()

        result = {
            "test": "naukri.com",
            "is_login": "1"
        }

        for key in ["nauk_rt", "nauk_sid", "MYNAUKRI[UNID]"]:
            if cookies.get(key):
                result[key] = cookies[key]

        return result


# ================== MAIN ==================
def update_resume() -> dict:
    """
    Uses global config variables only.
    """

    # ---- VALIDATION ----
    if not username or not password:
        return {"success": False, "error": "Username/password missing"}

    if not file_id:
        return {"success": False, "error": "file_id missing"}

    if not form_key:
        return {"success": False, "error": "form_key missing"}

    # ---- FILENAME ----
    today = datetime.now()
    final_filename = f"{filename}_{today.strftime('%d_%B_%Y').lower()}.pdf"

    FILE_KEY = "U" + generate_file_key(13)

    # ---- LOGIN ----
    client = NaukriLoginClient(username, password)

    try:
        client.login()
    except Exception as e:
        logger.debug(traceback.format_exc())
        return {"success": False, "error": f"Login failed: {e}"}

    token = client.get_bearer_token()

    if not token:
        logger.debug("Bearer token missing after login")
        return {"success": False, "error": "Bearer token missing"}

    cookies = client.build_required_cookies()
    logger.debug("Built cookie keys: %s", list(cookies.keys()))

    # ---- DOWNLOAD ----
    drive_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    try:
        res = requests.get(drive_url, proxies=proxies)
        res.raise_for_status()
    except Exception as e:
        logger.debug(traceback.format_exc())
        return {"success": False, "error": f"Download failed: {e}"}

    if res.content[:4] != b'%PDF':
        logger.debug("Downloaded file header (first 16 bytes): %s", res.content[:16])
        return {"success": False, "error": "Invalid PDF"}

    # ---- UPLOAD ----
    upload_resp = requests.post(
        "https://filevalidation.naukri.com/file",
        headers={
            "accept": "application/json",
            "appid": "105",
            "origin": "https://www.naukri.com",
            "referer": "https://www.naukri.com/",
            "systemid": "fileupload",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        },
        files={"file": (final_filename, BytesIO(res.content), "application/pdf")},
        data={
            "formKey": form_key,
            "fileName": final_filename,
            "uploadCallback": "true",
            "fileKey": FILE_KEY,
        },
        proxies=proxies
    )

    try:
        upload_resp.raise_for_status()
    except Exception as e:
        logger.debug("Upload response status: %s", getattr(upload_resp, 'status_code', None))
        logger.debug(traceback.format_exc())
        try:
            logger.debug("Upload response text: %s", upload_resp.text[:1000])
        except Exception:
            pass
        return {"success": False, "error": f"Upload failed: {e}"}

    # ---- PARSE FILE KEY ----
    try:
        upload_json = upload_resp.json()
        logger.debug("Upload JSON keys: %s", list(upload_json.keys()) if isinstance(upload_json, dict) else type(upload_json))
        if FILE_KEY not in upload_json:
            FILE_KEY = next(iter(upload_json.keys()))
    except Exception:
        logger.debug("Failed to parse upload response as JSON")
        logger.debug(traceback.format_exc())

    # ---- PROFILE UPDATE ----
    profile_id = client.fetch_profile_id()

    profile_url = f"https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/profiles/{profile_id}/advResume"

    payload = {
        "textCV": {
            "formKey": form_key,
            "fileKey": FILE_KEY,
            "textCvContent": None
        }
    }

    try:
        resp = client.session.post(
            profile_url,
            headers={
                "accept": "application/json",
                    "appid": "105",
                    "clientid": "d3skt0p",
                    "systemid": "Naukri",
                "authorization": f"Bearer {token}",
                "content-type": "application/json",
                "origin": "https://www.naukri.com",
                "referer": "https://www.naukri.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "x-http-method-override": "PUT",
            },
            cookies=cookies,
            data=json.dumps(payload)
        )

        resp.raise_for_status()
        logger.info("Profile update status: %s", resp.status_code)
        logger.debug("Profile update response (truncated): %s", resp.text[:1000])

    except Exception as e:
        logger.debug(traceback.format_exc())
        try:
            logger.debug("Profile update response text: %s", resp.text)
        except Exception:
            pass
        return {"success": False, "error": f"Profile update failed: {e}"}

    return {
        "success": True,
        "message": "Resume updated successfully"
    }


# ================== HANDLER ==================
def handler(event, context):
    logger.info("Cron job started")

    return {
        "status": update_resume(),
        "message": "Cron executed successfully"
    }


if __name__ == "__main__":
    result = handler("event", "context")
    print(result)
    
    # Fail the script explicitly if success is False
    if not result.get("status", {}).get("success"):
        sys.exit(1)
