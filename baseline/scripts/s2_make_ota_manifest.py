import argparse, json, hashlib, time, os

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)          # full image ref (e.g. REGION-docker.pkg.dev/PROJ/repo/app:sha)
    p.add_argument("--digest", required=True)         # image digest (sha256:...)
    p.add_argument("--outdir", required=True)         # baseline/metrics/s2/artifacts
    p.add_argument("--version", required=False, default="")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    manifest = {
        "image": args.image,
        "digest": args.digest,
        "version": args.version or args.digest.replace("sha256:","")[:12],
        "ts": int(time.time())
    }
    path = os.path.join(args.outdir, f"ota_{manifest['version']}.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)

    # produce checksum file for integrity
    chk = sha256_file(path)
    with open(path + ".sha256", "w") as f:
        f.write(chk + "  " + os.path.basename(path) + "\n")

    print(json.dumps({"manifest": path, "sha256": chk}))


if __name__ == "__main__":
    main()
