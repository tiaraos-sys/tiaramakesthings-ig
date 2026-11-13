"""Download and format images for posts waiting in pending/.

pending/<post-id>/post.json -> {"caption": "...", "image_urls": ["https://..."]}
Each image is saved as 1.jpg, 2.jpg ... at 1080x1350 (Instagram 4:5),
padded with the image's own edge colour so nothing is cropped.
"""
import json
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1350


def to_4x5(img):
    img = img.convert("RGB")
    w, h = img.size
    if abs(w / h - W / H) > 0.01:
        if w / h < W / H:  # too tall: pad the sides
            nw, nh = round(h * W / H), h
        else:              # too wide: pad top and bottom
            nw, nh = w, round(w * H / W)
        canvas = Image.new("RGB", (nw, nh), img.getpixel((2, h // 2)))
        canvas.paste(img, ((nw - w) // 2, (nh - h) // 2))
        img = canvas
    return img.resize((W, H), Image.LANCZOS)


def main():
    for meta_path in sorted((ROOT / "pending").glob("*/post.json")):
        d = meta_path.parent
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        urls = meta.get("image_urls") or []
        if not urls or meta.get("images"):
            continue
        names = []
        for i, url in enumerate(urls, 1):
            req = urllib.request.Request(url, headers={"User-Agent": "ig-poster"})
            with urllib.request.urlopen(req, timeout=60) as r:
                img = Image.open(BytesIO(r.read()))
            name = f"{i}.jpg"
            to_4x5(img).save(d / name, quality=92)
            names.append(name)
        meta["images"] = names
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"PREPARED {d.name}: {len(names)} image(s)")


if __name__ == "__main__":
    main()
