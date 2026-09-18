"""Single-owner administrative deployment, reachable only through SSM."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

allowed = {'OPENAI_API_KEY', 'MESHY_API_KEY', 'OPENAI_API_BASE', 'AVATAR_IMAGE_MODEL'}
values = json.loads(Path('/run/studio-secrets.json').read_text())
if not values.get('OPENAI_API_KEY') or not values.get('MESHY_API_KEY'):
    raise SystemExit('Provider credentials are not configured')
os.environ.update({key: str(value) for key, value in values.items() if key in allowed})
if not os.environ.get('ASSET_S3_BUCKET'):
    raise SystemExit('S3 bucket is required')
children = [subprocess.Popen(['python', '-m', 'uvicorn', 'src.api.server:app', '--host', '127.0.0.1', '--port', '8000', '--workers', '1', '--no-proxy-headers']),
            subprocess.Popen(['nginx', '-g', 'daemon off;'])]
def stop(*_):
    for child in children:
        child.terminate()
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    while all(child.poll() is None for child in children):
        time.sleep(1)
finally:
    stop()
    for child in children:
        try: child.wait(timeout=20)
        except subprocess.TimeoutExpired: child.kill()
