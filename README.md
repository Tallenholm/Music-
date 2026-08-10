# Music-

**Music-** is a Windows-first, local-first desktop application for identifying messy music files, comparing independent metadata evidence, enriching tags with optional local AI, previewing every proposed change, and safely writing only what you approve.

The project is intentionally **not centered on one metadata database**. MusicBrainz can be added as another provider later, but the MVP starts with local tags/filenames, Chromaprint + AcoustID, Apple iTunes Search, deterministic evidence fusion, and optional CLAP audio understanding.

## Current MVP capabilities

- Drag/drop files and folders into a native Qt desktop app.
- Scan MP3, FLAC, M4A/MP4, OGG/Opus, WAV, and AIFF.
- Read existing tags with Mutagen without modifying the source file.
- Parse conservative artist/title/track-number hints from filenames.
- Generate Chromaprint fingerprints with `fpcalc` when configured.
- Query AcoustID with a user-supplied free client key.
- Query the public Apple iTunes Search catalog as an independent metadata source.
- Score candidates using artist, title, duration, album, ISRC, provider confidence, and independent-source agreement.
- Optionally classify genre and mood locally with CLAP (`laion/clap-htsat-unfused`).
- Show Current / Proposed / Evidence views before writing.
- Only pre-select high-confidence matches by default.
- Record field-level history before writes and support **Undo Last**.

## Safety model

Music- starts in **Preview mode**. Analysis does not write tags. `Apply Selected` is disabled until a track has proposed changes and is explicitly selected.

The MVP only writes these common fields:

- title
- artist
- album
- album artist
- track number
- disc number
- date/year
- genre
- comment
- ISRC

Blank proposals do not erase existing nonblank values. Undo restores only fields Music- changed and leaves unrelated embedded metadata alone.

## Windows setup

### 1. Install Python 3.12

Use a 64-bit Python 3.12 installation.

### 2. Install ffmpeg and fpcalc

With Chocolatey:

```powershell
choco install ffmpeg fpcalc -y
```

`ffmpeg` is used for real audio decoding and local-AI excerpts. `fpcalc` is the Chromaprint command-line fingerprint tool.

### 3. Install Music-

```powershell
git clone https://github.com/Tallenholm/Music-.git
cd Music-
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 4. Launch

```powershell
python -m music_app
```

or, after installation:

```powershell
music-ai-tagger
```

## AcoustID configuration

Music- never embeds an AcoustID key. Create your own client key through AcoustID and place it in Music-'s user config file.

On Windows the app uses the platform user-config directory. To make development/testing explicit, you can set:

```powershell
$env:MUSIC_APP_CONFIG_DIR="$HOME\Music-Config"
```

Then create/save `config.json` using this shape:

```json
{
  "acoustid_client_key": "YOUR_CLIENT_KEY",
  "enable_acoustid": true,
  "enable_itunes": true,
  "enable_ai": false,
  "preselect_confidence": 0.95,
  "rename_template": "{artist} - {title}"
}
```

No API key is written to tag history.

## Optional local AI

The AI layer is optional and runs locally after the model is available on your machine.

```powershell
python -m pip install -e ".[ai]"
```

Then set `"enable_ai": true` in the config. The MVP uses CLAP to rank genre and mood labels from the audio itself. AI enrichment **never decides identity fields** such as artist, title, or album.

## Development

```powershell
python -m pip install -e ".[dev]"
ruff check src tests
pytest -v
```

The test suite includes real audio integration: ffmpeg encodes an actual MP3, Mutagen writes/reopens real ID3 metadata, history undo is exercised against that file, and CI runs real `fpcalc`. CI also performs a live Apple iTunes Search smoke test rather than treating controlled provider fixtures as proof that the external service works.

## Confidence bands

- **High:** `>= 0.95` — eligible for default selection.
- **Review:** `0.85–0.949` — requires review.
- **Low:** `< 0.85` — never pre-selected.

The matching engine is deterministic and inspectable; the AI layer is enrichment, not a hidden identity oracle.

## Current limitations

- AcoustID requires your own client key and has not yet been included in unauthenticated CI because no credential is embedded.
- CLAP model inference is optional and is not downloaded during normal tests.
- Cover-art writing and duplicate deletion are intentionally excluded from the MVP.
- The first release target is Windows. The non-UI core remains portable.
- File renaming is designed into configuration but is not yet enabled in the first UI slice; metadata safety is being completed first.

## License

MIT.
