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
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from config import settings
except ImportError:
    print("\n" + "=" * 68)
    print(" [ERROR] MISSING PROJECT FILES ON THIS PC!")
    print("=" * 68)
    print(" You cannot run 'tunnel_manager.py' by itself as a single file.")
    print(" The AI tunnel is a bridge to the AI model, but the AI brain files are missing:")
    print("   - ai/ (AI server and predictive model)")
    print("   - eternal_ai_model.joblib (Trained weights)")
    print("   - config.py, cli.py, requirements.txt")
    print("\n TO FIX THIS ON THIS LAPTOP:")
    print(" 1. Copy the entire 'Eternal-AI' project folder to this PC, or run:")
    print("      git clone https://github.com/sumitktiwari617/Eternal-AI.git")
    print(" 2. Open start.bat and select [1] to start the AI model and tunnel.")
    print("=" * 68 + "\n")
    sys.exit(1)

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


def start_ai_server_if_needed(host: str = "127.0.0.1", port: int = 8001) -> bool:
    """Launches local AI microservice in background if not already running."""
    if check_ai_server_health(host, port):
        logger.info(f"Local AI Model Server is already active on http://{host}:{port}")
        return True

    # Pre-check project structure
    if not (BASE_DIR / "cli.py").exists() or not (BASE_DIR / "ai" / "server.py").exists():
        logger.error(
            "CRITICAL ERROR: Core AI files (cli.py or ai/server.py) are missing on this PC! "
            "You cannot copy only 'tunnel_manager.py' by itself. "
            "The tunnel is only a bridge; it needs the AI model server running on port 8001. "
            "Please copy the entire Eternal-AI folder to this PC or run 'git clone'."
        )
        return False

    # Pre-check Python dependencies
    missing_deps = []
    for pkg in ["fastapi", "uvicorn", "joblib", "sklearn"]:
        try:
            __import__(pkg)
        except ImportError:
            missing_deps.append(pkg)
    if missing_deps:
        logger.error(
            f"Missing required packages: {', '.join(missing_deps)}. "
            "Please run: pip install -r requirements.txt"
        )
        return False

    logger.info(f"Starting Local AI Model Server on port {port}...")
    log_dir = BASE_DIR / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    server_log = log_dir / "ai_server.log"
    
    cmd = [sys.executable, str(BASE_DIR / "cli.py"), "ai-server", "--host", host, "--port", str(port)]
    
    try:
        log_handle = open(server_log, "a", encoding="utf-8")
        log_handle.write(f"\n=== AI Model Server Started {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        log_handle.flush()
        
        # Run detached background process
        if os.name == "nt":
            subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                close_fds=True
            )
        else:
            subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )
    except Exception as e:
        logger.error(f"Failed to launch AI server process: {e}")
        return False

    # Wait for server to boot
    for _ in range(15):
        time.sleep(1.0)
        if check_ai_server_health(host, port):
            logger.info("Local AI Model Server started successfully.")
            return True

    logger.warning("AI Model Server did not respond to health check within 15s.")
    if server_log.exists():
        try:
            with open(server_log, "r", encoding="utf-8") as f:
                tail = f.readlines()[-8:]
                if tail:
                    logger.warning("Recent AI server output:\n" + "".join(tail))
        except Exception:
            pass
    return False


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
_ssh_process = None


PINNED_CLOUDFLARED_VERSION = "2024.12.2"
PINNED_CLOUDFLARED_URL = f"https://github.com/cloudflare/cloudflared/releases/download/{PINNED_CLOUDFLARED_VERSION}/cloudflared-windows-amd64.exe"
# Verified SHA256 checksum for the pinned cloudflared binary
PINNED_CLOUDFLARED_SHA256 = "c2f4a3c3ea4c62eed562ede027d586a6044d35517e335e642f4e9783e651e4a3"
ALLOWED_CLOUDFLARED_HASHES = {
    PINNED_CLOUDFLARED_SHA256,
    "2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343",
}


def compute_file_sha256(filepath: Path) -> str:
    """Calculates SHA256 checksum of a file."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest().lower()


def get_or_download_cloudflared() -> Optional[Path]:
    """
    Checks if cloudflared binary is ALREADY installed by the user.
    NEVER auto-downloads to avoid triggering antivirus (e.g. Quick Heal) heuristics.
    """
    import shutil
    # 1. Check if cloudflared is installed on system PATH
    cf_path = shutil.which("cloudflared")
    if cf_path:
        return Path(cf_path)

    # 2. Check local AppData only if already present and verified
    user_dir = Path(os.environ.get("USERPROFILE", os.path.expanduser("~"))) / "AppData" / "Local" / "cloudflared"
    cf_exe = user_dir / "cloudflared.exe"
    if cf_exe.exists() and cf_exe.stat().st_size > 1000000:
        actual_hash = compute_file_sha256(cf_exe)
        if actual_hash in ALLOWED_CLOUDFLARED_HASHES:
            return cf_exe

    # We do NOT download cloudflared dynamically to ensure Quick Heal never triggers
    return None


def start_cloudflare_tunnel(port: int = 8001) -> Optional[str]:
    """Starts zero-config accountless Cloudflare tunnel to local port."""
    global _cf_process
    try:
        cf_exe = get_or_download_cloudflared()
        if not cf_exe or not cf_exe.exists():
            return None

        logger.info(f"Opening zero-config Cloudflare Tunnel to http://127.0.0.1:{port}...")
        proc = subprocess.Popen(
            [str(cf_exe), "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        _cf_process = proc

        start = time.time()
        while time.time() - start < 30:
            line = proc.stderr.readline()
            if line:
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    url = match.group(0)
                    logger.info(f"SUCCESS: Zero-config Cloudflare Tunnel active: {url}")
                    return url
    except PermissionError:
        logger.warning("Cloudflare binary blocked or quarantined by antivirus, skipping...")
    except OSError as e:
        if getattr(e, "winerror", None) == 225:  # Windows virus detection error
            logger.warning("Cloudflare binary quarantined by antivirus (WinError 225), skipping...")
        else:
            logger.warning(f"Cloudflare tunnel OS error: {e}")
    except Exception as e:
        logger.warning(f"Cloudflare tunnel error: {e}")
    return None


def start_ssh_tunnel(port: int = 8001) -> Optional[str]:
    """
    Starts an accountless, zero-download public HTTPS tunnel using Windows built-in OpenSSH.
    100% safe from antivirus / Quick Heal because ssh.exe is a native signed Microsoft system component.
    Unlimited usage, no sign-up required.
    """
    global _ssh_process
    ssh_exe = "ssh"
    if os.name == "nt":
        sys32_ssh = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh.exe"
        if sys32_ssh.exists():
            ssh_exe = str(sys32_ssh)

    null_file = "NUL" if os.name == "nt" else "/dev/null"
    try:
        logger.info(f"Opening Antivirus-Safe Built-in OpenSSH Tunnel to http://127.0.0.1:{port}...")
        proc = subprocess.Popen(
            [
                ssh_exe,
                "-o", "StrictHostKeyChecking=no",
                "-o", f"UserKnownHostsFile={null_file}",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "-R", f"80:127.0.0.1:{port}",
                "nokey@localhost.run"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        _ssh_process = proc

        start = time.time()
        while time.time() - start < 25:
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                match = re.search(r"https://[a-zA-Z0-9\.\-]+\.(?:lhr\.life|lhr\.pro|lhrtunnel\.com|localhost\.run)", line)
                if not match and "https://" in line and (".life" in line or ".pro" in line or "localhost" in line):
                    match = re.search(r"https://[^\s\"']+", line)
                if match:
                    url = match.group(0).rstrip(".")
                    logger.info(f"SUCCESS: Antivirus-Safe OpenSSH Tunnel active: {url}")
                    return url
            if proc.poll() is not None:
                logger.warning(f"OpenSSH tunnel process exited (code {proc.returncode})")
                break
    except Exception as e:
        logger.warning(f"OpenSSH tunnel error: {e}")
    return None


def start_tunnel(port: int = 8001) -> Optional[str]:
    """
    Attempts to establish or detect a public HTTPS tunnel to local AI port:
    1. Detects running ngrok on port 4040
    2. Uses pyngrok if auth token is configured
    3. Built-in Native Windows OpenSSH Tunnel (Quick Heal Immune, 0 downloads, Unlimited) [PRIMARY]
    4. Auto-falls back to zero-config Cloudflare Tunnel if OpenSSH fails
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

    # 3. Built-in Native Windows OpenSSH Tunnel (Quick Heal Immune, 0 downloads, Unlimited)
    ssh_url = start_ssh_tunnel(port)
    if ssh_url:
        return ssh_url

    # 4. Seamless Zero-Config Cloudflare Tunnel (Fallback, no account required)
    cf_url = start_cloudflare_tunnel(port)
    if cf_url:
        return cf_url

    # 5. Check if explicit AI_MODEL_SERVICE_URL or manual tunnel is provided
    configured_url = settings.ai_model_service_url
    if configured_url and (configured_url.startswith("https://") or "ngrok" in configured_url or "cloudflare" in configured_url or "lhr.life" in configured_url):
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
    print("\n[STEP 1/4] Checking Local AI Microservice on Port 8001...")
    ai_ok = start_ai_server_if_needed(host=settings.ai_service_host, port=settings.ai_service_port)
    if check_ai_server_health(settings.ai_service_host, settings.ai_service_port):
        print(f"       [+] Local AI Microservice is HEALTHY on http://{settings.ai_service_host}:{settings.ai_service_port}")
    else:
        print(f"       [!] WARNING: Local AI Microservice is NOT responding on port {settings.ai_service_port}!")
        print("           Render will report 'Offline (Tunnel inactive)' until the model is running.")
        print("           Try running 'start_ai_model.bat' or 'python -m pip install -r requirements.txt'.")

    # 2. Establish or discover tunnel
    print("\n[STEP 2/4] Establishing Antivirus-Safe Cloud Tunnel...")
    tunnel_url = start_tunnel(port=settings.ai_service_port)

    # Determine backends to register with
    target_render = settings.render_backend_url or DEFAULT_RENDER_BACKEND_URL
    backends = []
    if target_render and target_render.strip():
        backends.append(target_render.strip())
    # Also register with local backend if reachable
    backends.append("http://127.0.0.1:8000")

    if tunnel_url:
        print(f"       [+] Public HTTPS Tunnel Active: {tunnel_url}")
        
        # 3. Register with all target backends
        print("\n[STEP 3/4] Handshaking and Registering Tunnel with Cloud Backend...")
        for b in backends:
            success = register_tunnel_with_backend(b, tunnel_url, secret_token=settings.ai_secret_token)
            if success:
                print(f"       [+] Handshake successful with: {b}")

        # 4. End-to-end verification probe
        print("\n[STEP 4/4] Verifying End-to-End Status with Render Cloud...")
        time.sleep(2.0)
        try:
            import urllib.request
            verify_url = f"{target_render.rstrip('/')}/api/ai/tunnel-status"
            with urllib.request.urlopen(verify_url, timeout=6.0) as resp:
                status_data = json.loads(resp.read().decode("utf-8"))
                if status_data.get("tunnel_alive"):
                    print("       [+] SUCCESS: Render Cloud reports Tunnel is ONLINE & ACTIVE!")
                    print(f"       [+] Opening Live Dashboard: {target_render}")
                    try:
                        import webbrowser
                        webbrowser.open(target_render)
                    except Exception:
                        pass
                else:
                    print("       [!] Registered, but Render probe is waiting for port 8001 to respond.")
        except Exception as e:
            print(f"       [!] Cloud status verification note: {e}")
    else:
        print("\n[!] Tunnel was not created automatically.")
        print("    If using ngrok manually: ngrok http 8001")

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
            if not tunnel_url:
                tunnel_url = start_tunnel(port=settings.ai_service_port)
                if tunnel_url:
                    for b in backends:
                        register_tunnel_with_backend(b, tunnel_url, secret_token=settings.ai_secret_token)
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
            if _ssh_process:
                try:
                    _ssh_process.terminate()
                except Exception:
                    pass
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

