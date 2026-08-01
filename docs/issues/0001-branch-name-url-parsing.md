# Issue 0001: Branch names with slashes in GitHub URLs

**Status:** Open  
**Target phase:** Hardening (post-MVP)  
**Opened:** Phase 2 completion  
**Component:** `repolens/github/url_parser.py`

## Summary

GitHub URLs that include a branch/ref with slashes are parsed incorrectly when
the URL also contains a path suffix after the ref.

## Current behavior

For URLs like:

- `https://github.com/owner/repo/tree/feature/my-branch`
- `https://github.com/owner/repo/tree/main/src`

The parser extracts only the **first path segment** after `tree/` or `blob/` as
the ref (e.g. `feature` or `main`), not the full branch name when it contains
slashes.

## Expected behavior (future)

Resolve the full branch/ref name correctly, including refs with `/` characters,
without treating repository subpaths as part of the ref.

## Why deferred

Not required for Phase 3 correctness. Most analysis uses the repository default
branch when no ref is supplied. Fixing this requires additional heuristics or a
GitHub API lookup and is scoped to a later hardening phase.

## Acceptance criteria (when addressed)

- [ ] `/tree/feature/my-branch` resolves ref to `feature/my-branch` when that is
      the branch name
- [ ] `/tree/main/src` still resolves ref to `main` when `src` is a repo path
- [ ] Unit tests cover slash-containing branch names
- [ ] Documented in README limitations section
