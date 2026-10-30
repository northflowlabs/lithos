# Refreshing the data

A scene ends where the two frames it uses stop sharing dates, and COMET publishes new
interferograms at its own pace. Nothing here runs by itself. There are two ways to rebuild.

## By hand

```bash
pip install -e packages/core -e "packages/ingest[scenes]" matplotlib
python -m lithos_ingest.frames              # refresh the frame index (about 45 minutes)
python -m lithos_ingest.scene bologna       # rebuild the scene
python -m lithos_ingest.export_web_assets   # refresh the web app's stored files
python -m lithos_ingest.render_hero         # refresh the README image
```

Products already read stay in `data/cache`, so a rebuild only asks the archive for new ones.
A build solves the scene five times, which takes a few minutes. The first build reads about 1,400
products at the default limit of two a second,
which takes about 15 minutes. Set `LICSAR_RATE_LIMIT_RPS` to change that limit, and keep it
low: the archive is a public service.

## On GitHub

The `Refresh scenes` workflow does the same on a free GitHub-hosted runner, as this is a public
repository, and opens a pull request with the result. Nothing goes live until a person merges
it and the site is deployed.

It needs one setting: Settings, Actions, General, "Allow GitHub Actions to create and approve
pull requests". It has no schedule. To add one after a few runs by hand, add this under `on:`:

```yaml
  schedule:
    - cron: "0 5 1 * *" # first of the month
```

## What to check before merging

- `window` and `last_epoch` in `data/scenes/<slug>/meta.json`: the window is what was solved.
- `checks` in the same file: same-date double differences against GNSS stations it was not tied
  to. `caveat` is built from them and travels with the data.
- `robustness`, `verdicts_held` and `change_candidates`: how many verdicts survived each variant.

A pull request opened by the workflow's token does not trigger CI. Close and reopen it, or run CI by
hand, before merging.
- `filters`: how many cells each filter removed, against the previous build.

If COMET stops publishing one of a scene's frames, the window stops moving. Pick another frame
pair in `SCENES` in `lithos_ingest/scene.py`; `LicsarSource().frames_over(bbox)` lists them with
their newest dates.
