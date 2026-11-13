# TiaraMakesThings Instagram poster

- `pending/<id>/post.json` — Penny's draft posts: `{"caption": "...", "image_urls": [...]}`. A GitHub Action downloads the images and formats them to 1080x1350.
- `queue/<id>/` — approved on HQ, waiting for the daily 3 pm Alaska post (one per day, oldest first).
- `posted/<id>/result.json` — the Instagram link once live. `failed/<id>/result.json` — the error.
- Post right now: Actions → Post to Instagram → Run workflow → check "Post now".
