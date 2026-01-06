"""Handles uploading screenshots to remote destinations."""

import subprocess
import shutil
from pathlib import Path
from typing import Optional
import db

# Try to import keyring
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False


def upload_screenshot(client_id: int, local_path: Path) -> bool:
    """Upload screenshot to remote if configured. Returns True on success."""
    client = db.get_client(client_id)

    if not client or not client.get('push_screenshots_remote'):
        return True  # No remote configured, that's fine

    method = client.get('screenshot_remote_method')

    if method == 'unc':
        return _upload_unc(client, local_path)
    # Future: elif method == 's3': return _upload_s3(client, local_path)

    return False


def _upload_unc(client: dict, local_path: Path) -> bool:
    """Upload via UNC path using Windows net use."""
    unc_path = client.get('screenshot_unc_path')
    username = client.get('screenshot_unc_username')

    if not unc_path:
        return False

    # Get password from keyring
    password = None
    if KEYRING_AVAILABLE and username:
        try:
            password = keyring.get_password("timertool", f"client_{client['id']}_unc")
        except Exception:
            pass

    # Authenticate with net use (if credentials provided)
    if username and password:
        # Extract server share from path (\\server\share\folder -> \\server\share)
        parts = unc_path.strip('\\').split('\\')
        if len(parts) >= 2:
            share = f"\\\\{parts[0]}\\{parts[1]}"
            try:
                # Delete existing connection first (ignore errors)
                subprocess.run(
                    ['net', 'use', share, '/delete', '/y'],
                    capture_output=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
            except Exception:
                pass

            try:
                # Connect with credentials
                result = subprocess.run(
                    ['net', 'use', share, f'/user:{username}', password],
                    capture_output=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                if result.returncode != 0:
                    print(f"net use failed: {result.stderr.decode()}")
                    return False
            except subprocess.SubprocessError as e:
                print(f"net use error: {e}")
                return False

    # Copy file to remote
    try:
        remote_dir = Path(unc_path)
        remote_dir.mkdir(parents=True, exist_ok=True)
        remote_file = remote_dir / local_path.name
        shutil.copy2(local_path, remote_file)
        return True
    except Exception as e:
        print(f"Screenshot upload failed: {e}")
        return False
