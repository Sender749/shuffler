import base64
import requests
from vars import *

def get_shortlink(url, api, website):
    """Generate shortlink using API"""
    try:
        main_api = f"https://{website}/api"
        params = {'api': api, 'url': url}
        response = requests.get(main_api, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            return data.get('shortenedUrl')
        else:
            return url
    except Exception as e:
        print(f"Shortlink error: {e}")
        return url

def encode_string(string):
    """Encode string to base64"""
    string_bytes = string.encode("ascii")
    base64_bytes = base64.urlsafe_b64encode(string_bytes)
    return base64_bytes.decode("ascii").strip("=")

def decode_string(base64_string):
    """Decode base64 string"""
    base64_string = base64_string.strip("=")
    base64_string += "=" * (-len(base64_string) % 4)
    base64_bytes = base64_string.encode("ascii")
    string_bytes = base64.urlsafe_b64decode(base64_bytes) 
    return string_bytes.decode("ascii")

def format_time_remaining(seconds):
    """Format seconds into human readable time"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"
