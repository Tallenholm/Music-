# Music- Windows AI Tagger MVP Design

## Product Goal

Build a Windows-first desktop application that can safely identify, enrich, preview, tag, rename, and undo changes to local music files. The application is local-first and free/open-source by default. External services are optional evidence sources rather than a single source of truth.

## MVP User Flow

1. User drags audio files or a folder into the app, or uses Add Files / Add Folder.
2. Music- scans supported audio files and reads their existing metadata without modifying anything.
3. For each file, Music- derives identification evidence from:
   - existing tags,
   - filename/path hints,
   - Chromaprint fingerprinting through `fpcalc`,
   - AcoustID lookup when the user has configured a free client key,
   - Apple iTunes Search metadata as an independent catalog source.
4. A fusion engine scores candidate matches using title, artist, album, duration, ISRC, fingerprint confidence, and source agreement.
5. Optional local AI enrichment uses CLAP to classify genre/style and mood from the audio itself.
6. The UI shows current tags, proposed tags, evidence sources, conflicts, and a confidence score.
7. The user can apply only selected high-confidence changes. Dry-run / preview is the default.
8. Before writing, Music- records the fields it is about to change in a local history manifest. The user can undo the last applied operation for those fields.

## Platform and Technology

- Python 3.12.
- PySide6 / Qt 6 for the desktop application.
- Mutagen for reading and writing common audio metadata.
- `fpcalc` from Chromaprint for fingerprints.
- AcoustID web service for fingerprint lookup. The user supplies their own free client key; no key is embedded in the application.
- Apple iTunes Search API as the first independent metadata catalog provider.
- Optional Hugging Face Transformers + PyTorch + CLAP (`laion/clap-htsat-unfused`) for local zero-shot audio classification.
- `httpx` for network requests.
- `pytest` for tests.
- `ruff` for linting.

## Supported Files in MVP

The scanner recognizes: MP3, FLAC, M4A/MP4, OGG/Opus, WAV, and AIFF. Unsupported files are ignored and reported rather than treated as failures.

## Architecture

### `music_app.domain`

Small immutable data models shared across the application:

- `TrackInput`: path, existing tags, duration, filename hints.
- `Candidate`: normalized metadata from one evidence source.
- `Evidence`: per-field score/explanation.
- `MatchResult`: winning candidate, confidence, alternatives, conflict flags.
- `ProposedChange`: old/new values per writable field.
- `AnalysisResult`: one track's complete analysis state.

The domain layer has no Qt or network dependency.

### `music_app.library`

- `scanner.py`: recursive file discovery and safe path filtering.
- `tags.py`: Mutagen-backed tag read/write adapter and common-field normalization.
- `history.py`: JSON manifest for changed fields and undo operations.
- `filename_hints.py`: conservative parsing of common `Artist - Title` / track-number filename forms.

Tag writes are explicit. Analysis never calls a write method.

### `music_app.identify`

- `fingerprint.py`: invokes `fpcalc -json` with a timeout and validates output.
- `acoustid.py`: lookup adapter with rate limiting, retries, and client-key configuration.
- `itunes.py`: Apple iTunes Search adapter with a low request rate and in-memory query cache.
- `matching.py`: source-independent normalization and confidence scoring.
- `pipeline.py`: orchestrates local hints, fingerprint lookup, catalog lookup, and fusion.

Provider failures degrade gracefully. A failed provider never blocks local scanning, preview, or another provider.

### `music_app.ai`

- `clap.py`: optional local AI enrichment. Imports heavy dependencies lazily and reports a clear unavailable state when the AI extra is not installed.
- CLAP analyzes a bounded excerpt decoded by `ffmpeg`; it does not upload audio.
- MVP genre labels: hip-hop, rap, rock, pop, electronic, house, techno, metal, jazz, classical, country, r&b, soul, reggae, folk, ambient.
- MVP mood labels: energetic, chill, dark, uplifting, aggressive, melancholic, romantic, dreamy.
- Only labels over a configurable probability threshold are proposed.

AI labels enrich metadata; they do not override identity fields such as artist/title/album.

### `music_app.ui`

PySide6 desktop UI with four primary areas:

1. Toolbar: Add Files, Add Folder, Analyze, Apply Selected, Undo Last.
2. Track queue table: file, artist/title hint, status, confidence, conflict indicator.
3. Inspector: Current / Proposed / Evidence tabs for the selected track.
4. Bottom status area: provider availability, configured AcoustID key status, AI availability, progress.

Long-running work runs outside the GUI thread and reports progress through signals.

## Matching and Confidence

Candidate scores are 0.0-1.0. The default scoring model is deterministic and inspectable:

- Artist similarity: 0.25
- Title similarity: 0.25
- Duration similarity: 0.20
- Album similarity: 0.10
- ISRC exact match: 0.10
- Provider/fingerprint confidence: 0.10

When a field is unavailable, its weight is removed and the remaining weights are normalized. Agreement across independent sources adds a small consensus bonus capped so the final score remains <= 1.0.

Confidence bands:

- >= 0.95: High; eligible for one-click selection.
- 0.85-0.949: Review.
- < 0.85: Low; never pre-selected for write.

No identity tag is auto-written merely because AI labels are confident.

## Safety Rules

- The default application state is preview-only.
- Analyze never modifies files.
- Apply requires explicit user action.
- Low-confidence matches are not pre-selected.
- Existing tags remain visible next to proposed values.
- Only explicitly supported common fields are written in MVP: title, artist, album, album artist, track number, disc number, year/date, genre, comment, ISRC.
- History manifests record old and new values for every changed supported field before save.
- Undo restores only fields Music- changed; unrelated embedded metadata is left untouched.
- Network timeouts and provider errors are surfaced per track without crashing the queue.

## Configuration

Configuration is stored in the user's application config directory, never inside the repository or audio folders. MVP settings:

- AcoustID client key.
- Enable/disable AcoustID.
- Enable/disable iTunes metadata.
- Enable/disable local AI.
- Minimum confidence for pre-selection (default 0.95).
- Filename rename template (default `{artist} - {title}`).

Secrets are never committed, logged, or written into history manifests.

## Packaging

The source project uses standard `pyproject.toml`. Development starts with `python -m music_app`. A Windows packaging workflow can later use Qt's `pyside6-deploy`; the MVP repository includes CI tests before packaging automation is treated as release-ready.

## Testing

- Domain and matching tests run without Qt, network access, `fpcalc`, or AI dependencies.
- Provider parsing is tested with injected/fake HTTP transports.
- Fingerprint parsing is tested with an injected subprocess runner.
- Tag policy/history behavior is unit-tested independently from Mutagen I/O.
- Qt smoke tests verify the main window constructs and exposes primary controls when PySide6 is installed.
- GitHub Actions runs tests and lint on Windows and Linux.

## Explicit Non-Goals for MVP

- No automatic unattended library-wide writes.
- No cloud AI requirement.
- No embedded commercial API keys.
- No direct Spotify/Apple Music authenticated API integration.
- No cover-art downloading/writing in the first implementation.
- No duplicate-file deletion.
- No acoustic duplicate detection beyond exposing fingerprint IDs.
- No macOS/Linux packaging guarantee yet, although the core is kept portable.

## Success Criteria

The first releasable MVP is successful when a Windows user can add a folder, analyze supported tracks, see multiple-source evidence and confidence, optionally run local AI enrichment, preview proposed metadata, safely apply selected fields, and undo those supported-field changes; all core tests and CI must pass before the branch is treated as complete.
