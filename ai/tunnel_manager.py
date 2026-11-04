"""
ETERNAL AI - Dynamic Portable Tunnel & Cloud Handshake Manager
Enables zero-reconfiguration mobility:
Copy this codebase to any desktop PC, run this manager (or start_ai_tunnel.bat),
and your local AI model automatically exposes itself via tunnel and registers
its public URL with your deployed cloud backend (e.g. Render).
"""

import sys
import os
import time
import json
import logging
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TunnelManager")


def check_ai_server_health(host: str = "127.0.0.1", port: int = 8001) -> bool:
    """Checks if local AI model server is active and healthy."""
    import urllib.request
    url = f"http://{host}:{port}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ETERNAL-Probe"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_ai_server_if_needed(host: str = "127.0.0.1", port: int = 8001):
    """Launches local AI microservice in background if not already running."""
    if check_ai_server_health(host, port):
        logger.info(f"Local AI Model Server is already active on http://{host}:{port}")
        return

    logger.info(f"Starting Local AI Model Server on port {port}...")
    cmd = [sys.executable, str(BASE_DIR / "cli.py"), "ai-server", "--host", host, "--port", str(port)]
    
    # Run detached background process
    if os.name == "nt":
        subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True
        )
    else:
        subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )

    # Wait for server to boot
    for _ in range(15):
        time.sleep(1.0)
        if check_ai_server_health(host, port):
            logger.info("Local AI Model Server started successfully.")
            return

    logger.warning("AI Model Server did not respond to health check within 15s, continuing...")


def get_existing_ngrok_url() -> Optional[str]:
    """Queries running local ngrok web API (port 4040) for active public tunnel URL."""
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels", headers={"User-Agent": "ETERNAL-Probe"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for t in data.get("tunnels", []):
                pub_url = t.get("public_url", "")
                if pub_url.startswith("https://"):
                    return pub_url
                elif pub_url.startswith("http://"):
                    return pub_url.replace("http://", "https://")
    except Exception:
        pass
    return None


DEFAULT_RENDER_BACKEND_URL = "https://eternal-ai-3oat.onrender.com"
DEFAULT_ADMIN_KEY = "admin_aa3797c179a6236618316e26"
DEFAULT_AI_TOKEN = "ai_2abc92e5c7993432bb3b002a"
_cf_process = None


def get_or_download_cloudflared() -> Optional[Path]:
    """Retrieves or auto-downloads standalone Cloudflare quick tunnel binary."""
    user_dir = Path(os.environ.get("USERPROFILE", os.path.expanduser("~"))) / "AppData" / "Local" / "cloudflared"
    user_dir.mkdir(parents=True, exist_ok=True)
    cf_exe = user_dir / "cloudflared.exe"
    if cf_exe.exists() and cf_exe.stat().st_size > 1000000:
        return cf_exe

    try:
        import urllib.request
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        logger.info("Downloading standalone zero-config Cloudflare tunnel...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40.0) as resp:
            data = resp.read()
        with open(cf_exe, "wb") as f:
            f.write(data)
        logger.info("Cloudflare tunnel binary ready.")
        return cf_exe
    except Exception as e:
        logger.warning(f"Failed to auto-download cloudflared: {e}")
        return None


def start_cloudflare_tunnel(port: int = 8001) -> Optional[str]:
    """Starts zero-config accountless Cloudflare tunnel to local port."""
    global _cf_process
    cf_exe = get_or_download_cloudflared()
    if not cf_exe or not cf_exe.exists():
        return None

    try:
        logger.info(f"Opening zero-config Cloudflare Tunnel to http://127.0.0.1:{port}...")
        proc = subprocess.Popen(
            [str(cf_exe), "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        _cf_process = proc

        start = time.time()
        while time.time() - start < 15:
            line = proc.stderr.readline()
            if line:
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    url = match.group(0)
                    logger.info(f"SUCCESS: Zero-config Cloudflare Tunnel active: {url}")
                    return url
    except Exception as e:
        logger.warning(f"Cloudflare tunnel error: {e}")
    return None


def start_tunnel(port: int = 8001) -> Optional[str]:
    """
    Attempts to establish or detect a public HTTPS tunnel to local AI port:
    1. Detects running ngrok on port 4040
    2. Uses pyngrok if auth token is configured
    3. Auto-falls back to zero-config Cloudflare Tunnel (no account required)
    """
    # 1. Check existing ngrok
    existing_url = get_existing_ngrok_url()
    if existing_url:
        logger.info(f"Detected existing ngrok tunnel: {existing_url}")
        return existing_url

    # 2. Try pyngrok if token is provided
    if getattr(settings, "ngrok_authtoken", None):
        try:
            from pyngrok import ngrok, conf
            ngrok.set_auth_token(settings.ngrok_authtoken.strip())
            tunnel = ngrok.connect(port, "http")
            url = tunnel.public_url
            if url.startswith("http://"):
                url = url.replace("http://", "https://")
            logger.info(f"Created pyngrok tunnel: {url}")
            return url
        except Exception as e:
            logger.debug(f"pyngrok attempt: {e}")

    # 3. Seamless Zero-Config Cloudflare Tunnel (100% Free, No login, No auth token needed)
    cf_url = start_cloudflare_tunnel(port)
    if cf_url:
        return cf_url

    # 4. Check if explicit AI_MODEL_SERVICE_URL or manual tunnel is provided
    configured_url = settings.ai_model_service_url
    if configured_url and (configured_url.startswith("https://") or "ngrok" in configured_url or "cloudflare" in configured_url):
        logger.info(f"Using pre-configured tunnel URL from settings: {configured_url}")
        return configured_url

    return None


def register_tunnel_with_backend(backend_url: str, tunnel_url: str, secret_token: Optional[str] = None) -> bool:
    """
    Registers this PC's public tunnel URL with the specified backend (local or cloud Render).
    """
    import urllib.request
    endpoint = f"{backend_url.rstrip('/')}/api/ai/register-tunnel"
    token = secret_token or getattr(settings, "ai_secret_token", None) or DEFAULT_AI_TOKEN
    admin_key = getattr(settings, "admin_api_key", None) or DEFAULT_ADMIN_KEY

    payload = {
        "tunnel_url": tunnel_url,
        "secret_token": token
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ETERNAL-Tunnel-Manager/2.0",
        "X-Admin-Key": admin_key,
        "X-AI-Secret-Token": token
    }

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                logger.info(f"SUCCESS: Tunnel registered with {backend_url} -> {body.get('message')}")
                return True
    except Exception as e:
        logger.warning(f"Failed to register tunnel with {backend_url}: {e}")
    return False


def ping_backend(backend_url: str):
    """Pings the backend to prevent free cloud instances from sleeping."""
    import urllib.request
    endpoint = f"{backend_url.rstrip('/')}/api/status"
    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "ETERNAL-Heartbeat/2.0"})
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            pass
    except Exception:
        pass


def run_tunnel_manager():
    """Main lifecycle coordinator for PC-to-Cloud AI connectivity."""
    print("=" * 68)
    print("   ETERNAL AI - PORTABLE TUNNEL & CLOUD HANDSHAKE MANAGER")
    print("   Connects this desktop's AI model to your deployed Cloud Backend")
    print("=" * 68)

    # 1. Ensure AI server is running locally
    start_ai_server_if_needed(host=settings.ai_service_host, port=settings.ai_service_port)

    # 2. Establish or discover tunnel
    tunnel_url = start_tunnel(port=settings.ai_service_port)

    # Determine backends to register with
    target_render = settings.render_backend_url or DEFAULT_RENDER_BACKEND_URL
    backends = []
    if target_render and target_render.strip():
        backends.append(target_render.strip())
    # Also register with local backend if reachable
    backends.append("http://127.0.0.1:8000")

    if tunnel_url:
        print(f"\n[+] Active Public Tunnel: {tunnel_url}")
        print(f"[+] Local AI Microservice: http://{settings.ai_service_host}:{settings.ai_service_port}")
        
        # 3. Register with all target backends
        for b in backends:
            register_tunnel_with_backend(b, tunnel_url, secret_token=settings.ai_secret_token)
    else:
        print("\n[!] Tunnel was not created automatically.")
        print("    If you are running ngrok manually, run: ngrok http 8001")
        print("    Or if testing on Localhost only, local backend will use http://127.0.0.1:8001")

    print("\n" + "=" * 68)
    print("   AI MODEL STATUS: ACTIVE & READY FOR PREDICTIONS")
    print("   Keep this window open while trading!")
    print("   Heartbeat is keeping your cloud Render backend awake.")
    print("   Press Ctrl+C to stop.")
    print("=" * 68 + "\n")

    # 4. Continuous keep-alive heartbeat loop (every 45s)
    heartbeat_count = 0
    while True:
        try:
            time.sleep(45.0)
            heartbeat_count += 1
            
            # Check if tunnel is still alive or refreshed
            current_tunnel = get_existing_ngrok_url() or tunnel_url
            if current_tunnel and current_tunnel != tunnel_url:
                logger.info(f"Tunnel URL refreshed: {current_tunnel}")
                tunnel_url = current_tunnel
                for b in backends:
                    register_tunnel_with_backend(b, tunnel_url, secret_token=settings.ai_secret_token)

            # Send keepalive ping to cloud backend to prevent cold start / sleep
            target_render = settings.render_backend_url or DEFAULT_RENDER_BACKEND_URL
            if target_render:
                ping_backend(target_render)

            if heartbeat_count % 10 == 0:
                logger.info(f"Heartbeat tick #{heartbeat_count} | AI Server Healthy on port {settings.ai_service_port}")

        except KeyboardInterrupt:
            logger.info("Tunnel manager shutting down by user request.")
            if _cf_process:
                try:
                    _cf_process.terminate()
                except Exception:
                    pass
            break
        except Exception as e:
            logger.debug(f"Heartbeat error: {e}")


if __name__ == "__main__":
    run_tunnel_manager()

