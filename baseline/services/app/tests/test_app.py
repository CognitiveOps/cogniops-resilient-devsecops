import subprocess
import time

import httpx


def test_nginx_container_build_and_serve():
    # Build the image locally
    build = subprocess.run(
        ["docker", "build", "-t", "test-nginx", "."],
        capture_output=True,
        text=True
    )
    assert build.returncode == 0, f"Build failed: {build.stderr}"

    # Run container temporarily (8080)
    container = subprocess.Popen(
        ["docker", "run", "-d", "-p", "8080:8080", "test-nginx"],
        stdout=subprocess.PIPE,
        text=True
    )
    container_id = container.stdout.read().strip()
    time.sleep(2)  # give Nginx a bit of time to start

    # Make HTTP request
    try:
        r = httpx.get("http://localhost:8080", timeout=5)
        assert r.status_code == 200, f"Unexpected status code: {r.status_code}"
        assert "Baseline" in r.text or "nginx" in r.text.lower()
    finally:
        subprocess.run(["docker", "rm", "-f", container_id])
