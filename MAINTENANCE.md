# autobuild Maintenance Guide

## Keeping Windows CI up to date with new Visual Studio releases

### Background

GitHub Actions `windows-latest` is a rolling label: when GitHub upgrades it to
a new Windows runner image, it ships a newer version of Visual Studio. autobuild
needs to know about each Visual Studio major version so it can map it to the
correct C++ toolset identifier (e.g. `v143` for VS 2022, `v145` for VS 2026).

### Strategy

1. **Sentinel in the test suite** — `tests/test_source_environment.py` defines
   `NEWEST_KNOWN_VS_MAJOR`, the two-digit major version prefix of the newest
   Visual Studio that autobuild currently supports (e.g. `"18"` for VS 2026).
   The test `test_newest_vs_known` **fails** (rather than silently skipping)
   whenever `windows-latest` ships an unrecognized major version. This is
   intentional: a failure is a clear signal that action is required.

2. **Pinned runners in `ci.yml`** — older Windows runner images (e.g.
   `windows-2022`) are kept in the matrix so that every still-supported
   toolchain is tested, even after `windows-latest` has moved on.

3. **Retire unsupported runners** — when a Visual Studio version reaches
   end-of-life and Linden no longer needs to support it, its pinned runner
   can be removed from `ci.yml`.

### What to do when `test_newest_vs_known` fails

When `windows-latest` starts shipping a Visual Studio major version newer than
the current `NEWEST_KNOWN_VS_MAJOR`, CI will fail on that runner. Here is what
a developer needs to do to resolve it:

#### Step 1 — Add the new toolset mapping to autobuild source

Open `autobuild/autobuild_tool_source_environment.py` and find the `_VSTOOLSETS`
dictionary (search for `_VSTOOLSETS`). Add an entry for the new VS major version.
For example, if VS 2029 ships as major version `19`, its toolset identifier would
be `v150`:

```python
_VSTOOLSETS = {
    ...
    "18": "v145", # 2026
    "19": "v150", # 2029  <-- add this
}
```

You may also need to add the same major version to the `AUTOBUILD_WIN_CMAKE_GEN`
mapping a little further down in the same file. Search for `"Visual Studio 18 2026"`
to find it. Add the new entry following the same pattern.

#### Step 2 — Update `NEWEST_KNOWN_VS_MAJOR` in the test file

Open `tests/test_source_environment.py` and update the `NEWEST_KNOWN_VS_MAJOR`
constant near the top of the file to match the new major version. The comment on
the same line should also reflect the new VS year. For example:

```python
NEWEST_KNOWN_VS_MAJOR = "19"  # Visual Studio 2029
```

#### Step 3 — Pin the outgoing `windows-latest` image in `ci.yml`

Open `.github/workflows/ci.yaml` and add the runner image that `windows-latest`
used to resolve to (e.g. `windows-2025`) to the `os` matrix list. This ensures
the old toolchain continues to be exercised in CI even though `windows-latest`
has moved on.

```yaml
os: [ubuntu-latest, macos-latest, windows-latest, windows-2025, windows-2022]
```

#### Step 4 — Optionally retire old runner images

Review the `os` matrix in `ci.yml` for any Windows runner images that target
Visual Studio versions Linden Lab no longer supports. Removing them reduces CI
run time. When in doubt, leave them in; it is easy to remove them later.

### Files that need updating (summary)

| File | What to update |
|---|---|
| `autobuild/autobuild_tool_source_environment.py` | `_VSTOOLSETS` dict, `AUTOBUILD_WIN_CMAKE_GEN` mapping |
| `tests/test_source_environment.py` | `NEWEST_KNOWN_VS_MAJOR` constant |
| `.github/workflows/ci.yaml` | `os` matrix — add pinned runner, optionally remove old ones |
