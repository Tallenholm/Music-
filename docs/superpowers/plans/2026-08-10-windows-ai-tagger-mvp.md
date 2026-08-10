# Music- Windows AI Tagger MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-first desktop music identification/tagging app that fuses local metadata, filename hints, Chromaprint/AcoustID, Apple iTunes Search, and optional local CLAP enrichment, while keeping preview-only behavior as the default and supporting undo for fields Music- changes.

**Architecture:** A `src/` Python package separates pure domain/matching logic from filesystem/tag adapters, network providers, optional AI, orchestration, and PySide6 UI. Heavy or external dependencies are behind small injectable interfaces so core behavior is testable without network access, Qt, `fpcalc`, or AI models.

**Tech Stack:** Python 3.12, PySide6, Mutagen, httpx, Chromaprint `fpcalc`, AcoustID, Apple iTunes Search API, optional PyTorch + Transformers CLAP, pytest, pytest-qt, ruff.

## Global Constraints

- Windows-first application; keep non-UI core portable.
- Preview-only is the default; analysis must never write tags.
- No embedded AcoustID or other secret/API keys.
- AI runs locally and never determines artist/title/album identity.
- Low-confidence matches (<0.85) are never pre-selected for writing.
- Only supported common fields may be changed: title, artist, album, album artist, track number, disc number, date/year, genre, comment, ISRC.
- Undo restores only supported fields changed by Music-.
- Provider failures degrade gracefully and are reported per track.
- No cover-art writing, duplicate deletion, or unattended library-wide writes in MVP.

---

## File Structure

```text
pyproject.toml
README.md
src/music_app/
  __init__.py
  __main__.py
  config.py
  domain.py
  library/
    __init__.py
    scanner.py
    filename_hints.py
    tags.py
    history.py
  identify/
    __init__.py
    fingerprint.py
    acoustid.py
    itunes.py
    matching.py
    pipeline.py
  ai/
    __init__.py
    clap.py
  ui/
    __init__.py
    main_window.py
    workers.py
tests/
  test_scanner.py
  test_filename_hints.py
  test_matching.py
  test_fingerprint.py
  test_acoustid.py
  test_itunes.py
  test_history.py
  test_tag_policy.py
  test_clap_scoring.py
  test_pipeline.py
  test_ui_smoke.py
.github/workflows/ci.yml
```

### Task 1: Project skeleton, domain models, and scanner

**Files:**
- Create: `pyproject.toml`
- Create: `src/music_app/__init__.py`
- Create: `src/music_app/domain.py`
- Create: `src/music_app/library/__init__.py`
- Create: `src/music_app/library/scanner.py`
- Test: `tests/test_scanner.py`

**Interfaces:**
- Produces `SUPPORTED_EXTENSIONS: frozenset[str]`.
- Produces `discover_audio_files(paths: Iterable[Path]) -> list[Path]`.
- Produces immutable dataclasses `TrackTags`, `TrackInput`, `Candidate`, `MatchResult`, `ProposedChange`, `AnalysisResult`.

- [ ] **Step 1: Write failing scanner tests**

```python
from pathlib import Path
from music_app.library.scanner import discover_audio_files


def test_discovers_supported_files_recursively(tmp_path: Path) -> None:
    album = tmp_path / "Album"
    album.mkdir()
    mp3 = album / "01 - Song.mp3"
    flac = album / "02 - Song.flac"
    ignored = album / "cover.jpg"
    mp3.write_bytes(b"")
    flac.write_bytes(b"")
    ignored.write_bytes(b"")

    assert discover_audio_files([tmp_path]) == [mp3, flac]


def test_deduplicates_overlapping_inputs(tmp_path: Path) -> None:
    song = tmp_path / "song.MP3"
    song.write_bytes(b"")
    assert discover_audio_files([tmp_path, song]) == [song]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_scanner.py -v`
Expected: FAIL because `music_app.library.scanner` does not exist.

- [ ] **Step 3: Add package metadata and minimal scanner/domain implementation**

`discover_audio_files` must recurse directories, accept direct files, compare extensions case-insensitively, resolve duplicates, ignore unsupported files, and return a stable case-insensitive path sort.

Use frozen dataclasses and tuples for shared domain state so UI/provider layers cannot mutate analysis results accidentally.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_scanner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -am "feat: add project domain and audio scanner"`

### Task 2: Filename hints and deterministic candidate matching

**Files:**
- Create: `src/music_app/library/filename_hints.py`
- Create: `src/music_app/identify/__init__.py`
- Create: `src/music_app/identify/matching.py`
- Test: `tests/test_filename_hints.py`
- Test: `tests/test_matching.py`

**Interfaces:**
- Produces `parse_filename_hints(path: Path) -> TrackTags`.
- Produces `normalize_text(value: str | None) -> str`.
- Produces `score_candidate(track: TrackInput, candidate: Candidate) -> float`.
- Produces `choose_match(track: TrackInput, candidates: Sequence[Candidate]) -> MatchResult | None`.

- [ ] **Step 1: Write failing filename-hint tests**

```python
def test_parses_track_artist_title_without_overreaching() -> None:
    tags = parse_filename_hints(Path("03 - Kendrick Lamar - Money Trees.flac"))
    assert tags.track_number == "3"
    assert tags.artist == "Kendrick Lamar"
    assert tags.title == "Money Trees"


def test_plain_filename_becomes_title_only() -> None:
    tags = parse_filename_hints(Path("Money Trees.mp3"))
    assert tags.artist is None
    assert tags.title == "Money Trees"
```

- [ ] **Step 2: Run filename RED, implement minimal parser, run GREEN**

Run: `python -m pytest tests/test_filename_hints.py -v`.

- [ ] **Step 3: Write failing matching tests**

```python
def test_exact_artist_title_and_close_duration_scores_high() -> None:
    track = TrackInput(path=Path("x.mp3"), tags=TrackTags(artist="Kendrick Lamar", title="Money Trees"), duration_s=386.0)
    candidate = Candidate(source="itunes", source_id="1", artist="Kendrick Lamar", title="Money Trees", duration_s=386.4)
    assert score_candidate(track, candidate) >= 0.95


def test_bad_artist_cannot_win_on_duration_alone() -> None:
    track = TrackInput(path=Path("x.mp3"), tags=TrackTags(artist="Kendrick Lamar", title="Money Trees"), duration_s=386.0)
    wrong = Candidate(source="itunes", source_id="2", artist="Different Artist", title="Money Trees", duration_s=386.0)
    assert score_candidate(track, wrong) < 0.85
```

- [ ] **Step 4: Run matching RED**

Run: `python -m pytest tests/test_matching.py -v`.
Expected: FAIL because scoring does not exist.

- [ ] **Step 5: Implement weighted scoring and consensus**

Use `difflib.SequenceMatcher` for normalized text similarity. Apply available-field weights from the design (artist .25, title .25, duration .20, album .10, ISRC .10, provider confidence .10), renormalizing when evidence is missing. Duration similarity is 1.0 within 1 second, then decays linearly to 0 at 15 seconds. Exact normalized ISRC is binary. `choose_match` sorts descending and adds at most 0.03 consensus bonus when independent sources agree on normalized artist/title.

- [ ] **Step 6: Run GREEN**

Run: `python -m pytest tests/test_filename_hints.py tests/test_matching.py -v`.
Expected: PASS.

- [ ] **Step 7: Commit**

`git commit -am "feat: add filename hints and match scoring"`

### Task 3: Fingerprint and free metadata provider adapters

**Files:**
- Create: `src/music_app/identify/fingerprint.py`
- Create: `src/music_app/identify/acoustid.py`
- Create: `src/music_app/identify/itunes.py`
- Test: `tests/test_fingerprint.py`
- Test: `tests/test_acoustid.py`
- Test: `tests/test_itunes.py`

**Interfaces:**
- `Fingerprint(duration_s: float, fingerprint: str)`.
- `fingerprint_file(path: Path, runner=subprocess.run, executable="fpcalc") -> Fingerprint`.
- `AcoustIDClient(client_key: str, transport: HttpTransport).lookup(fingerprint: Fingerprint) -> list[Candidate]`.
- `ITunesClient(transport: HttpTransport, country="US").search(artist: str | None, title: str) -> list[Candidate]`.

- [ ] **Step 1: Write failing `fpcalc` parsing tests**

Fake runner output:

```python
completed = SimpleNamespace(returncode=0, stdout='{"duration": 386.0, "fingerprint": "abc"}', stderr="")
```

Assert valid JSON returns `Fingerprint(386.0, "abc")`; non-zero exit, timeout, missing executable, invalid JSON, and missing fingerprint raise `FingerprintError` with user-readable messages.

- [ ] **Step 2: Run RED, implement fingerprint adapter, run GREEN**

Run: `python -m pytest tests/test_fingerprint.py -v`.

- [ ] **Step 3: Write failing AcoustID parser tests**

Use an injected fake transport returning an AcoustID payload with `score`, recording title, artists, releases, and IDs. Assert it maps into `Candidate(source="acoustid", source_confidence=...)` without performing real HTTP.

- [ ] **Step 4: Implement AcoustID client**

POST to `https://api.acoustid.org/v2/lookup` with `client`, `duration`, `fingerprint`, `format=json`, and metadata request `recordings+releases+releasegroups+tracks`. Enforce a maximum request rate of 3/s, a 10-second timeout, and no retries on 4xx. Empty key raises a configuration error before any request.

- [ ] **Step 5: Write failing iTunes parser/cache tests**

Assert Apple `kind == "song"` results map `trackName`, `artistName`, `collectionName`, `trackTimeMillis`, `trackNumber`, `discNumber`, `releaseDate`, and `trackId` into `Candidate`; repeated identical searches call the fake transport once.

- [ ] **Step 6: Implement iTunes client**

GET `https://itunes.apple.com/search` with `term`, `country`, `media=music`, `entity=song`, and `limit=25`. Cache identical queries in memory and space uncached requests to respect Apple's documented approximate rate limit.

- [ ] **Step 7: Run provider GREEN**

Run: `python -m pytest tests/test_fingerprint.py tests/test_acoustid.py tests/test_itunes.py -v`.
Expected: PASS.

- [ ] **Step 8: Commit**

`git commit -am "feat: add fingerprint and metadata providers"`

### Task 4: Safe tag proposal, write policy, history, and undo

**Files:**
- Create: `src/music_app/library/tags.py`
- Create: `src/music_app/library/history.py`
- Test: `tests/test_tag_policy.py`
- Test: `tests/test_history.py`

**Interfaces:**
- `SUPPORTED_WRITE_FIELDS` constant.
- `build_changes(current: TrackTags, proposed: TrackTags) -> tuple[ProposedChange, ...]`.
- `apply_supported_changes(path: Path, changes: Sequence[ProposedChange]) -> None`.
- `HistoryStore(root: Path).record(...) -> HistoryEntry`.
- `HistoryStore.undo_last(writer: TagWriter) -> HistoryEntry | None`.

- [ ] **Step 1: Write failing policy tests**

Assert unchanged values are omitted; unsupported fields cannot be constructed into writes; blank proposed values do not erase nonblank current values by default; normalized equal values do not create churn.

- [ ] **Step 2: Run RED, implement pure change policy, run GREEN**

Run: `python -m pytest tests/test_tag_policy.py -v`.

- [ ] **Step 3: Write failing history tests**

Use a fake writer and temporary directory. Record two fields for one file, then call `undo_last`; assert only those fields are restored and the manifest is marked undone. Assert API keys never appear in serialized entries.

- [ ] **Step 4: Implement JSON history store**

Store manifests under the app config/data directory, not beside audio files. Use UUID operation IDs, UTC timestamps, absolute path, and old/new supported field values. Write manifests atomically via temp file + `os.replace`.

- [ ] **Step 5: Add Mutagen adapter behind lazy import**

Read common tags through `mutagen.File(path, easy=True)` where possible. Handle common write mappings per format; use ID3 `TSRC`/EasyID3 support or explicit ID3 frames for ISRC, Vorbis-style `isrc` for FLAC/Ogg, and MP4 freeform `----:com.apple.iTunes:ISRC` for MP4. Preserve unrelated tags.

- [ ] **Step 6: Run GREEN**

Run: `python -m pytest tests/test_tag_policy.py tests/test_history.py -v`.
Expected: PASS.

- [ ] **Step 7: Commit**

`git commit -am "feat: add safe tag writes and undo history"`

### Task 5: Optional local CLAP enrichment

**Files:**
- Create: `src/music_app/ai/__init__.py`
- Create: `src/music_app/ai/clap.py`
- Test: `tests/test_clap_scoring.py`

**Interfaces:**
- `DEFAULT_GENRES`, `DEFAULT_MOODS`.
- `rank_labels(similarities: Sequence[float], labels: Sequence[str], threshold: float) -> list[tuple[str, float]]`.
- `CLAPAnalyzer(model_name="laion/clap-htsat-unfused").analyze(path: Path) -> AIEnrichment`.

- [ ] **Step 1: Write failing pure scoring tests**

Assert label order follows descending probability, labels below threshold are excluded, and probabilities are normalized from logits with stable softmax.

- [ ] **Step 2: Run RED, implement scoring, run GREEN**

Run: `python -m pytest tests/test_clap_scoring.py -v`.

- [ ] **Step 3: Implement lazy local analyzer**

Only import `torch`, `transformers`, and `numpy` when `analyze` is called. Decode a bounded excerpt to mono 48 kHz WAV through `ffmpeg` in a temporary directory, load PCM, run `ClapProcessor` + `ClapModel` under `torch.no_grad()`, and compare audio/text embeddings for genre and mood prompt lists. Return a structured unavailable/error result rather than crashing when dependencies, ffmpeg, or model files are missing.

- [ ] **Step 4: Verify core tests remain independent of AI install**

Run: `python -m pytest tests/test_clap_scoring.py tests/test_matching.py -v`.
Expected: PASS without downloading a model.

- [ ] **Step 5: Commit**

`git commit -am "feat: add optional local CLAP enrichment"`

### Task 6: Analysis pipeline and PySide6 desktop UI

**Files:**
- Create: `src/music_app/config.py`
- Create: `src/music_app/identify/pipeline.py`
- Create: `src/music_app/ui/__init__.py`
- Create: `src/music_app/ui/workers.py`
- Create: `src/music_app/ui/main_window.py`
- Create: `src/music_app/__main__.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_ui_smoke.py`

**Interfaces:**
- `AppConfig.load()/save()` using platform config directory and environment override for tests.
- `AnalysisPipeline.analyze(track: TrackInput) -> AnalysisResult`.
- `MainWindow` with buttons `add_files_button`, `add_folder_button`, `analyze_button`, `apply_button`, `undo_button`.

- [ ] **Step 1: Write failing pipeline tests**

Inject fake fingerprint/provider/AI adapters. Assert provider failure is captured in `AnalysisResult.errors`, another provider can still win, and confidence bands map to `high/review/low` with low results not pre-selected.

- [ ] **Step 2: Run RED, implement orchestration, run GREEN**

Run: `python -m pytest tests/test_pipeline.py -v`.

- [ ] **Step 3: Write failing Qt smoke test**

```python
def test_main_window_exposes_safe_primary_actions(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Music-"
    assert window.apply_button.isEnabled() is False
    assert "Preview" in window.mode_label.text()
```

- [ ] **Step 4: Run UI RED**

Run: `python -m pytest tests/test_ui_smoke.py -v`.
Expected: FAIL because the UI is not implemented.

- [ ] **Step 5: Implement the desktop UI**

Use Qt Widgets. Provide drag/drop, add-file/folder dialogs, queue table, selected-track inspector with Current/Proposed/Evidence tabs, preview mode label, provider/AI status, and progress. Analysis runs in `QThreadPool` workers; workers emit immutable results. Apply remains disabled until there is at least one explicitly selected proposed change. Undo Last uses `HistoryStore`.

- [ ] **Step 6: Run UI GREEN and complete suite**

Run: `python -m pytest -v`.
Expected: all installed-capability tests pass; AI model download is never required for the suite.

- [ ] **Step 7: Commit**

`git commit -am "feat: add analysis pipeline and desktop UI"`

### Task 7: Documentation and CI verification

**Files:**
- Modify: `README.md`
- Create: `.github/workflows/ci.yml`

**Interfaces:** None; this task validates the full project.

- [ ] **Step 1: Add user/developer README**

Document Windows setup, `python -m music_app`, optional `fpcalc`/ffmpeg requirements, how to obtain and configure an AcoustID client key, optional `pip install -e .[ai]`, preview/apply/undo safety model, supported fields, and current MVP limitations.

- [ ] **Step 2: Add CI**

Matrix: `windows-latest` and `ubuntu-latest`, Python 3.12. Install `.[dev]`, run `ruff check src tests`, then `pytest -v`. Set `QT_QPA_PLATFORM=offscreen` on Linux.

- [ ] **Step 3: Run local verification available in the sandbox**

Run: `python -m compileall -q src tests`.
Run: `python -m pytest -v` where dependencies are present.
Run: `ruff check src tests` where ruff is present.

- [ ] **Step 4: Push branch and inspect GitHub Actions**

Open a draft PR from `feat/windows-ai-tagger-mvp` to `main`. Verify both matrix jobs. If CI exposes dependency/platform defects, fix them test-first and rerun.

- [ ] **Step 5: Final evidence gate**

Before calling the MVP complete, report exact files changed, local commands run and results, CI job results, provider/AI items not live-tested against external services, and any remaining limitations.
