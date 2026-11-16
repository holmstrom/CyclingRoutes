"""Start the backend server as a detached subprocess."""
import subprocess
import sys
import time

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=open(".tmp/backend.log", "w"),
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
)
print(f"Backend started (PID {proc.pid})")
time.sleep(3)

import urllib.request
try:
    resp = urllib.request.urlopen("http://127.0.0.1:8000/api/health")
    print(f"Health check: {resp.read().decode()}")
except Exception as e:
    print(f"Health check failed: {e}")
