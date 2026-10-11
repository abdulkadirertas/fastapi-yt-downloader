# FastAPI YouTube Downloader

A lightweight, asynchronous web application to preview and download YouTube videos as MP4 or convert them to MP3 audio files. Built with FastAPI, `yt-dlp`, and FFmpeg.

---

## Features

- **Instant Metadata Preview:** Fetches video title, duration, and thumbnail without parsing stream signatures upfront.
- **Asynchronous Execution:** Handles heavy download and conversion tasks without blocking the main web server.
- **Smart Cancellation:** Detects client disconnects and cancels active background tasks to save server resources.
- **Automatic Storage Cleanup:** Deletes downloaded temporary media files immediately after delivery.
- **Embedded Browser Launch:** Automatically opens the local web interface on startup.

---

## Prerequisites

Ensure you have the following installed on your system:

1. **Python 3.10+**
2. **FFmpeg** (Required for audio extraction and video muxing)
   - Must be accessible via your system's `PATH`.
3. **Deno** (Recommended)
   - Used by `yt-dlp` to resolve YouTube challenge signatures.

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/](https://github.com/)<your-username>/fastapi-yt-downloader.git
   cd fastapi-yt-downloader
