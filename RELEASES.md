# Releases

Ship **tagged GitHub Releases** when the product moves — not every commit.
Aim for roughly **every 1–2 weeks**, or sooner after a desk / trader milestone.

User-facing history lives in [`CHANGELOG.md`](CHANGELOG.md). When you cut a tag, move the relevant **Unreleased** bullets into a new version section.

## When to cut a release

Cut one if any of these landed since the last tag:

- Paper desk UX users can see (new screen, charts, copy, design)
- Trader defaults / risk / promote-gate changes
- Docs that change how strangers run the project (README, FRIENDS, compose)

Skip a release for pure chore/docs typos unless bundled with the above.

## Checklist

1. `main` is green locally: `docker run --rm ai-stock-checker pytest -q -m "not network"`
2. Desk up: `./scripts/smoke_desk_http.sh`
3. Refresh screenshots: capture tab PNGs → `./scripts/make_desk_tour_gif.sh` (and still JPGs via `./scripts/capture_desk_screenshots.sh`)
4. Update README hero copy if the story changed
5. `./scripts/cut_release.sh vX.Y.Z` — creates annotated tag + GitHub Release notes

Versioning: **semver**. Bump **minor** for user-visible desk/trader features; **patch** for fixes; **major** only for breaking compose/CLI contracts.

## Agents

On improve ticks: if enough shippable product work accumulated since `git describe --tags --abbrev=0`, propose/cut a release (don’t spam daily tags). Keep README screenshots current when UI changes.
