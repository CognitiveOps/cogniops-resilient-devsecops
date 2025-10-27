import subprocess
import time
import socket
from pathlib import Path
from urllib.request import urlopen, URLError, HTTPError

def wait_for_port(host: str, port: int, timeout: float = 30):
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return True
            except OSError:
                time.sleep(0.2)
    return False

def http_get_with_retries(url: str, timeout: float = 5, attempts: int = 20, delay: float = 0.5):
    last_exc = None
    for _ in range(attempts):
        try:
            with urlopen(url, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", errors="ignore")
        except (ConnectionResetError, URLError, HTTPError) as e:
            last_exc = e
            time.sleep(delay)
    raise last_exc if last_exc else RuntimeError("HTTP retries exhausted")

def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True)

def test_nginx_container_build_and_serve():
    # Resolve Dockerfile path relative to this test file
    dockerfile_path = Path(__file__).resolve().parents[1] / "Dockerfile"
    context_dir = dockerfile_path.parent
    assert dockerfile_path.exists(), f"Dockerfile not found at {dockerfile_path}"

    # Build image
    build = docker("build", "-t", "test-nginx", "-f", str(dockerfile_path), str(context_dir))
    assert build.returncode == 0, f"Build failed:\nSTDOUT:\n{build.stdout}\nSTDERR:\n{build.stderr}"

    container_name = "test-nginx-c"
    try:
        # Run container
        run = docker("run", "-d", "-p", "8080:8080", "--name", container_name, "test-nginx")
        assert run.returncode == 0, f"Run failed:\nSTDOUT:\n{run.stdout}\nSTDERR:\n{run.stderr}"

        # Wait for port open
        assert wait_for_port("127.0.0.1", 8080, 30), "Nginx port 8080 did not open in time"

        # Probe with retries (handles brief crashes/restarts or slow start)
        status, body = http_get_with_retries("http://127.0.0.1:8080", timeout=5, attempts=20, delay=0.5)
        assert status == 200, f"Unexpected HTTP status: {status}"
        assert "<html" in body.lower(), "Response does not look like HTML content"

    except Exception as e:
        # Helpful diagnostics on failure
        ps = docker("ps", "-a", "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}")
        logs = docker("logs", container_name)
        inspect = docker("inspect", container_name)
        raise AssertionError(
            f"Test failed with exception: {e}\n\n"
            f"=== docker ps -a ===\n{ps.stdout or ps.stderr}\n"
            f"=== docker logs {container_name} ===\n{logs.stdout or logs.stderr}\n"
            f"=== docker inspect {container_name} ===\n{inspect.stdout or inspect.stderr}\n"
        )
    finally:
        docker("rm", "-f", container_name)
        docker("rmi", "-f", "test-nginx")
