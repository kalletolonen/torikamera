
"""
record_stream.py - Record 60 seconds of the Torikamera stream

This script helps create a backup video file for demo purposes in case
the live stream is unavailable. It uses yt-dlp to fetch the stream URL
and ffmpeg to record a 60-second clip.
"""

import subprocess
import time
import sys
import os
import yt_dlp

# Duration to record in seconds (1 minute)
RECORD_DURATION = 60
OUTPUT_FILENAME = "backup_stream.mp4"
YOUTUBE_URL = "https://www.youtube.com/watch?v=F7SDNtc5waU"

def get_stream_url(youtube_url):
    """Fetch direct stream URL using yt-dlp."""
    print("Fetching stream URL...")
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "format": "best"
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            return info.get("url")
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return None

def record_stream(stream_url, output_file, duration):
    """Record stream using ffmpeg."""
    print(f"Recording {duration} seconds to {output_file}...")
    
    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg is not installed or not in PATH.")
        return

    # ffmpeg command to record stream
    # -i: input url
    # -t: duration
    # -c copy: copy streams without re-encoding (fast)
    # -y: overwrite output file
    cmd = [
        "ffmpeg",
        "-i", stream_url,
        "-t", str(duration),
        "-c", "copy",
        "-y",
        output_file
    ]

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # simple progress indicator
        for left in range(duration, 0, -1):
            sys.stdout.write(f"\rRecording... {left}s remaining")
            sys.stdout.flush()
            time.sleep(1)
            if process.poll() is not None:
                break
        
        print("\nFinishing recording...")
        process.wait()
        
        if process.returncode == 0:
            print(f"Success! Saved to {os.path.abspath(output_file)}")
        else:
            _, stderr = process.communicate()
            print(f"ffmpeg error: {stderr.decode()}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    url = get_stream_url(YOUTUBE_URL)
    if url:
        record_stream(url, OUTPUT_FILENAME, RECORD_DURATION)
