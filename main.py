import os
import re
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp
import asyncio
import threading

app = FastAPI()

# Temporary directory for downloaded files
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class VideoRequest(BaseModel):
    url: str


def remove_file(path: str):
    """Delete the generated file after it has been delivered to the client."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# 1- Fetch metadata endpoint
@app.post("/api/info")
async def get_video_info(request: VideoRequest):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": False, #just meta data
        "nocheckcertificate": True,
        "socket_timeout" : 5,
        "ignore_no_formats_error": True,
        "noplaylist": True,
    }
    def extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(request.url, download=False)

    try:
        # Run blocking network call in a separate thread so event loop remains responsive
        info = await asyncio.to_thread(extract)
        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to fetch video information: {str(e)}"
        )


# 2- Download and convert endpoint
@app.get("/api/download")
async def download_file(
    request: Request,
    url: str,
    background_tasks: BackgroundTasks,
    format: str = "mp3",
):
    format = format.lower()

    # Thread-safe event to signal client disconnect without blocking worker threads
    stop_event = threading.Event()

    # Background coroutine that watches for client disconnection
    async def watch_disconnect():
        try:
            while not stop_event.is_set():
                if await request.is_disconnected():
                    stop_event.set()
                    break
                await asyncio.sleep(0.5)
        except Exception:
            pass

    disconnect_watcher = asyncio.create_task(watch_disconnect())

    # Instant check within hook without blocking thread execution
    def cancel_hook(d):
        if stop_event.is_set():
            raise yt_dlp.utils.DownloadCancelled("Client disconnected or cancelled.")

    if format == "mp4":
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
            "progress_hooks": [cancel_hook],
            "merge_output_format": "mp4",
            "nocheckcertificate": True,
            "noplaylist": True,
            "quiet": False,  # Keep output visible in console for debugging

        }
        media_type = "video/mp4"
        ext = "mp4"
    else:
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                },
                {"key": "FFmpegMetadata"},
            ],
            "progress_hooks": [cancel_hook],
            "nocheckcertificate": True,
            "noplaylist": True,
            "quiet": False,  # Keep output visible in console for debugging
        }
        media_type = "audio/mpeg"
        ext = "mp3"

    video_id = None
    try:
        # Execute blocking download task in thread pool
        def extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)

        info = await asyncio.to_thread(extract)
        video_id = info.get("id")

        # Sanitize forbidden filename characters for filesystem compatibility
        raw_title = info.get("title", "download")
        clean_title = re.sub(r'[\\/*?:"<>|]', "", raw_title).strip()
        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=500,
                detail="Conversion completed but output file was not found.",
            )

        # Schedule automatic disk cleanup after file transmission finishes
        background_tasks.add_task(remove_file, file_path)

        return FileResponse(
            path=file_path,
            filename=f"{clean_title}.{ext}",
            media_type=media_type,
        )

    except yt_dlp.utils.DownloadCancelled:
        print("Download task aborted: Client disconnected.")
        # Clean up any partial files left behind
        if video_id:
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(video_id):
                    try:
                        os.remove(os.path.join(DOWNLOAD_DIR, f))
                    except Exception:
                        pass
        raise HTTPException(
            status_code=499, detail="Client Closed Request / Download Aborted"
        )

    except Exception as e:
        print(f"Download error: {e}")
        raise HTTPException(
            status_code=400, detail=f"Download failed: {str(e)}"
        )
    finally:
        # Stop and clean up the background disconnect watcher
        stop_event.set()
        disconnect_watcher.cancel()


# 3. Mount static directory for frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import time
    import uvicorn
    import webbrowser

    def open_browser():
        # Give Uvicorn 1 second to bind to the socket and start accepting connections
        time.sleep(1)
        webbrowser.open("http://127.0.0.1:8000")

    # Launch browser opener in a detached daemon thread before starting the blocking server loop
    threading.Thread(target=open_browser, daemon=True).start()

    # Start the ASGI server (reload is disabled to prevent duplicate browser tabs on process reload)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)

