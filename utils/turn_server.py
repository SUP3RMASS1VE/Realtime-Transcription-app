import os
from typing import Literal, Optional, Dict, Any
import requests

from fastrtc import get_hf_turn_credentials, get_twilio_turn_credentials


def get_rtc_credentials(
    provider: Literal["hf", "twilio", "cloudflare"] = "hf",
    **kwargs
) -> Dict[str, Any]:
    """
    Get RTC configuration for different TURN server providers.
    
    Args:
        provider: The TURN server provider to use ('hf', 'twilio', or 'cloudflare')
        **kwargs: Additional arguments passed to the specific provider's function
    
    Returns:
        Dictionary containing the RTC configuration
    """
    try:
        if provider == "hf":
            return get_hf_credentials(**kwargs)
        elif provider == "twilio":
            return get_twilio_credentials(**kwargs)
        elif provider == "cloudflare":
            return get_cloudflare_credentials(**kwargs)
    except Exception as e:
        raise Exception(f"Failed to get RTC credentials ({provider}): {str(e)}")


def get_hf_credentials(token: Optional[str] = None) -> Dict[str, Any]:
    """
    Get credentials for Hugging Face's community TURN server.
    
    Required setup:
    1. Create a Hugging Face account at huggingface.co
    2. Visit: https://huggingface.co/spaces/fastrtc/turn-server-login
    3. Set HF_TOKEN environment variable or pass token directly
    """
    token = token or os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN environment variable not set")
    
    try:
        return get_hf_turn_credentials(token=token)
    except Exception as e:
        raise Exception(f"Failed to get HF TURN credentials: {str(e)}")


def get_twilio_credentials(
    account_sid: Optional[str] = None,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get credentials for Twilio's TURN server.
    
    Required setup:
    1. Create a free Twilio account at: https://login.twilio.com/u/signup
    2. Get your Account SID and Auth Token from the Twilio Console
    3. Set environment variables:
       - TWILIO_ACCOUNT_SID (or pass directly)
       - TWILIO_AUTH_TOKEN (or pass directly)
    """
    account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token:
        raise ValueError("Twilio credentials not found. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN env vars")
    
    try:
        return get_twilio_turn_credentials(account_sid=account_sid, auth_token=auth_token)
    except Exception as e:
        raise Exception(f"Failed to get Twilio TURN credentials: {str(e)}")


def get_cloudflare_credentials(
    key_id: Optional[str] = None,
    api_token: Optional[str] = None,
    ttl: int = 86400
) -> Dict[str, Any]:
    """
    Get credentials for Cloudflare's TURN server.
    
    Required setup:
    1. Create a free Cloudflare account
    2. Go to Cloudflare dashboard -> Calls section
    3. Create a TURN App and get the Turn Token ID and API Token
    4. Set environment variables:
       - TURN_KEY_ID
       - TURN_KEY_API_TOKEN
    
    Args:
        key_id: Cloudflare Turn Token ID (optional, will use env var if not provided)
        api_token: Cloudflare API Token (optional, will use env var if not provided)
        ttl: Time-to-live for credentials in seconds (default: 24 hours)
    """
    key_id = key_id or os.environ.get("TURN_KEY_ID")
    api_token = api_token or os.environ.get("TURN_KEY_API_TOKEN")
    
    if not key_id or not api_token:
        raise ValueError("Cloudflare credentials not found. Set TURN_KEY_ID and TURN_KEY_API_TOKEN env vars")
    
    response = requests.post(
        f"https://rtc.live.cloudflare.com/v1/turn/keys/{key_id}/credentials/generate",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json={"ttl": ttl},
    )
    
    if response.ok:
        return {"iceServers": [response.json()["iceServers"]]}
    else:
        raise Exception(
            f"Failed to get Cloudflare TURN credentials: {response.status_code} {response.text}"
        )
    

if __name__ == "__main__":
    # Test
    print(get_rtc_credentials(provider="hf"))