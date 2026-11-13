"""Publish approved posts from queue/ to Instagram, then move them to posted/.

Each post is a folder: queue/<post-id>/
  post.json  -> {"caption": "...", "images": ["1.jpg", "2.jpg"]}
  1.jpg ...  -> the images (JPEG). 1 image = single post, 2-10 = carousel.

Secrets: IG_TOKEN, IG_USER_ID. Env: GITHUB_REPOSITORY, GITHUB_SHA.
"""
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_VERSION = "v25.0"
HOSTS = ["https://graph.instagram.com", "https://graph.facebook.com"]
TOKEN = os.environ["IG_TOKEN"].strip()
USER_ID = os.environ["IG_USER_ID"].strip()
REPO = os.environ["GITHUB_REPOSITORY"]
SHA = os.environ["GITHUB_SHA"]
ROOT = Path(__file__).resolve().parent.parent
QUEUE, POSTED, FAILED = ROOT / "queue", ROOT / "posted", ROOT / "failed"


class ApiError(Exception):
    pass


def call(host, method, path, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    url = f"{host}/{API_VERSION}/{path}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise ApiError(e.read().decode(errors="replace")) from None


def pick_host():
    """Use whichever Graph host accepts this token."""
    errors = []
    for host in HOSTS:
        try:
            call(host, "GET", USER_ID, {"fields": "id,username"})
            return host
        except ApiError as e:
            errors.append(f"{host}: {e}")
    raise SystemExit("Token rejected by both hosts:\n" + "\n".join(errors))


def wait_ready(host, container_id):
    for _ in range(30):
        status = call(host, "GET", container_id, {"fields": "status_code"}).get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise ApiError(f"container {container_id} status {status}")
        time.sleep(5)
    raise ApiError(f"container {container_id} not ready after 150s")


def publish(host, post_dir):
    meta = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    caption = meta.get("caption", "")
    images = meta.get("images") or sorted(
        p.name for p in post_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg")
    )
    if not 1 <= len(images) <= 10:
        raise ApiError(f"need 1-10 images, got {len(images)}")
    rel = post_dir.relative_to(ROOT).as_posix()
    urls = [
        f"https://raw.githubusercontent.com/{REPO}/{SHA}/{rel}/{urllib.parse.quote(name)}"
        for name in images
    ]

    if len(urls) == 1:
        container = call(host, "POST", f"{USER_ID}/media",
                         {"image_url": urls[0], "caption": caption})["id"]
    else:
        children = []
        for u in urls:
            cid = call(host, "POST", f"{USER_ID}/media",
                       {"image_url": u, "is_carousel_item": "true"})["id"]
            wait_ready(host, cid)
            children.append(cid)
        container = call(host, "POST", f"{USER_ID}/media",
                         {"media_type": "CAROUSEL", "children": ",".join(children),
                          "caption": caption})["id"]
    wait_ready(host, container)
    media_id = call(host, "POST", f"{USER_ID}/media_publish", {"creation_id": container})["id"]
    link = call(host, "GET", media_id, {"fields": "permalink"}).get("permalink", "")
    return media_id, link


def main():
    posts = sorted(p for p in QUEUE.iterdir() if p.is_dir() and (p / "post.json").exists()) \
        if QUEUE.exists() else []
    if not posts:
        print("Queue empty.")
        return
    host = pick_host()
    failures = 0
    for post_dir in posts:
        try:
            media_id, link = publish(host, post_dir)
            (post_dir / "result.json").write_text(json.dumps(
                {"status": "posted", "media_id": media_id, "permalink": link,
                 "posted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2))
            dest = POSTED
            print(f"POSTED {post_dir.name}: {link}")
        except ApiError as e:
            (post_dir / "result.json").write_text(json.dumps(
                {"status": "failed", "error": str(e)}, indent=2))
            dest = FAILED
            failures += 1
            print(f"FAILED {post_dir.name}: {e}")
        dest.mkdir(exist_ok=True)
        shutil.move(str(post_dir), str(dest / post_dir.name))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
