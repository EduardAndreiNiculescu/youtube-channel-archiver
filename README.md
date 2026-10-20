# YouTube Channel Archiver

**Turn a whole YouTube channel into a Markdown knowledge base: one file per video with description, resource links and the timestamped transcript, plus an index.**

Built to study a creator with 1,200+ videos and shorts without scrubbing through them one by one. Point it at a channel, come back later, then search the folder, grep it, or feed it to an LLM.

```bash
pip install -r requirements.txt

python yt_archive.py channel @3blue1brown --out archive/ --kinds videos --limit 50
python yt_archive.py docs --out archive/        # also pull public Google Docs linked in descriptions
```

```
archive/
├── 00_INDEX.md         table: title, type, transcript status, link count, file
├── index.json          the same, machine-readable
├── VIDEOS/0001_<title>_<id>.md
├── SHORTS/0001_<title>_<id>.md
└── DOCS/gdoc_<id>.txt  exported public Google Docs
```

Each video file:

```markdown
# The last IMO problem AI could not solve
- **Type:** videos
- **URL:** https://www.youtube.com/watch?v=…
- **Transcript:** ok
- **Resource links (2):** …
## Description
…
## Transcript
[00:00] …
[00:07] …
```

## What it handles

- **Long videos, shorts and streams** (`--kinds videos shorts streams`), listed with `yt-dlp` flat extraction (no video downloads).
- **Transcripts** via `youtube-transcript-api`, written as `[mm:ss] text` lines so you can jump to the moment.
- **Resource links**: Google Docs/Drive, Notion, Dropbox and Coda URLs are pulled out of each description and listed at the top of the file, which is usually where creators hide their templates and SOPs.
- **Resumable**: files that already exist with content are skipped, so a large channel can be archived across several runs.
- **Polite**: a configurable `--delay` between requests.
- `docs` exports every **public** Google Doc linked anywhere in the archive as plain text; private docs are skipped.

## Responsible use

For personal study. Transcripts and descriptions belong to their creators: do not republish an archive. The repository ships the tool only.

## License

MIT
