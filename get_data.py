import argparse
import cv2
import time
import os
import yt_dlp
import sys
import subprocess
from datetime import datetime, timedelta

import requests
import re
from urllib.parse import urljoin

def get_dynamic_youtube_url(base_url="https://torilive.fi"):
    """
    Scrapes torilive.fi to find the current embedded YouTube URL.
    1. Fetches the main page.
    2. Finds the 'app.*.js' script.
    3. Fetches the JS and regex searches for the YouTube embed URL.
    """
    try:
        print(f"Scraping {base_url} for YouTube ID...")
        # 1. Fetch Request
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        html = response.text

        # 2. Find app.js
        # Look for <script ... src="/js/app.CONTENTHASH.js">
        # HTML5 allows unquoted attributes, e.g. src=/js/app.04eec67a.js
        match_js = re.search(r'src=["\']?(/js/app\.[a-z0-9]+\.js)', html)
        if not match_js:
            print("Could not find app.js script in HTML.")
            return None
        
        js_path = match_js.group(1).rstrip('"\'>') # Clean up any trailing quote/bracket if greedy
        
        js_path = match_js.group(1)
        js_url = urljoin(base_url, js_path)
        print(f"Found App JS: {js_url}")

        # 3. Fetch JS and search for YouTube ID
        js_response = requests.get(js_url, timeout=10)
        js_response.raise_for_status()
        js_content = js_response.text

        # Regex for standard YouTube embed or shortened URL
        # The file viewed previously had: src:"https://www.youtube.com/embed/F7SDNtc5waU?autoplay=1..."
        match_yt = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]{11})', js_content)
        if match_yt:
            yt_id = match_yt.group(1)
            full_url = f"https://www.youtube.com/watch?v={yt_id}"
            print(f"Found Dynamic YouTube URL: {full_url}")
            return full_url
        
        print("Could not find YouTube embed ID in JS.")
        return None

    except Exception as e:
        print(f"Error scraping dynamic URL: {e}")
        return None

def get_stream_url(url):
    """
    Resolves the stream URL.
    If the input is 'https://torilive.fi/', it attempts to scrape the real YouTube URL first.
    Then uses yt-dlp to get the HLS stream.
    """
    # If it's the base site, try to scrape the dynamic ID
    if "torilive.fi" in url:
        scraped_url = get_dynamic_youtube_url(url)
        if scraped_url:
            url = scraped_url
            
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
    }
    print(f"Resolving stream URL for: {url}...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info['url'], url # Return both stream URL and the resolved YouTube URL
    except Exception as e:
        print(f"Error extracting stream URL: {e}", file=sys.stderr)
        return None, url


def extract_frames_live(stream_url, limit, interval, output_dir):
    """
    Captures frames from the LIVE stream at the specified interval.
    """
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("Error: Could not open video stream.", file=sys.stderr)
        return

    frames_saved = 0
    last_capture_time = 0
    
    print(f"Starting LIVE capture. Target: {limit} frames. Interval: {interval}s.")
    
    try:
        while frames_saved < limit:
            ret, frame = cap.read()
            if not ret:
                print("Stream ended or failed to read frame.")
                break

            current_time = time.time()
            if current_time - last_capture_time >= interval:
                # Sanity check: Ensure frame has content (not empty/black)
                if frame.size == 0 or cv2.countNonZero(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)) == 0:
                    print("Skipping empty/black frame.")
                    continue

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(output_dir, f"torikamera_{timestamp}_live.jpg")
                
                cv2.imwrite(filename, frame)
                print(f"Saved {filename} ({frames_saved + 1}/{limit})")
                
                frames_saved += 1
                last_capture_time = current_time
            
    except KeyboardInterrupt:
        print("\nStopping capture...")
    finally:
        cap.release()
        print(f"Done. Saved {frames_saved} frames to {output_dir}")

def extract_frames_history(youtube_url, history_hours, limit, duration, output_dir):
    """
    Uses streamlink to download segments from the past and extract frames.
    """
    print(f"Starting HISTORY capture. Offsets: {history_hours} hours ago.")
    
    # Calculate offset logic
    # streamlink --hls-start-offset HH:MM:SS (from end if live)
    for hours_ago in history_hours:
        print(f"--- Processing: {hours_ago} hours ago ---")
        
        # Convert hours to HH:MM:SS
        td = timedelta(hours=hours_ago)
        # Handle cases > 24h just in case (though HLS window is usually only 12h)
        total_seconds = int(td.total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        offset_str = f"{h:02}:{m:02}:{s:02}"
        
        # Approximate timestamp for filename
        past_time = datetime.now() - td
        timestamp_str = past_time.strftime("%Y%m%d_%H%M%S")
        
        temp_video = os.path.join(output_dir, f"temp_{timestamp_str}.ts")
        
        # Streamlink command
        # --hls-start-offset: Amount of time to skip from the beginning of the stream. 
        # For live streams, this is a negative offset from the end of the stream.
        # But streamlink syntax for negative offset uses the same value, just implies it for live.
        # Wait, typically standard streamlink needs explicit negative for some inputs, but for --hls-start-offset it says:
        # "For live streams, this is a negative offset from the end of the stream."
        # This implies we pass positive duration "02:00:00" and it goes back 2 hours.
        
        # Streamlink command needs to point to the venv executable if possible, or just "streamlink" if in path.
        # Since we are running via venv python, we can try to find streamlink in the same bin dir.
        venv_bin = os.path.dirname(sys.executable)
        streamlink_exe = os.path.join(venv_bin, "streamlink")
        if not os.path.exists(streamlink_exe):
             # Fallback to assumming it's in path
             streamlink_exe = "streamlink"

        cmd = [
            streamlink_exe,
            "--hls-start-offset", offset_str,
            "--hls-duration", str(duration),
            "-o", temp_video,
            youtube_url,
            "best"
        ]
        
        print(f"Downloading clip (Offset: {offset_str}, Duration: {duration}s)...")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to download segment: {e}")
            continue
            
        if not os.path.exists(temp_video):
            print("Download failed, temp file not found.")
            continue
            
        # Extract frames from temp video
        cap = cv2.VideoCapture(temp_video)
        frames_extracted = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
             print("Could not read video file stats.")
             cap.release()
             os.remove(temp_video)
             continue
             
        # Distribute extraction evenly across the clip
        step = max(1, total_frames // limit)
        
        for i in range(limit):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i * step)
            ret, frame = cap.read()
            if not ret:
                break
                
            filename = os.path.join(output_dir, f"torikamera_{timestamp_str}_h{int(hours_ago)}h_f{i}.jpg")
            cv2.imwrite(filename, frame)
            print(f"Saved {filename}")
            frames_extracted += 1
            
        cap.release()
        os.remove(temp_video) # Cleanup
        print(f"Extracted {frames_extracted} frames from {hours_ago} hours ago.")


def main():
    parser = argparse.ArgumentParser(description="Torkamera Stream Ripper")
    parser.add_argument("--url", default="https://torilive.fi/", help="URL of the stream source")
    parser.add_argument("--limit", type=int, default=50, help="Number of frames to capture")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between captures (Live mode)")
    parser.add_argument("--output", default="data/raw", help="Directory to save frames")
    
    # Time Travel Arguments
    parser.add_argument("--history", type=float, nargs='+', help="List of hour offsets to scrape from past (e.g. 0.5 2 12)")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds to download for historical clips")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)

    # Resolve URL
    stream_url, youtube_url = get_stream_url(args.url)
    if not stream_url:
        sys.exit(1)

    if args.history:
        # History Mode (Streamlink)
        # We need the YouTube URL, not the resolved HLS URL for streamlink (usually)
        # because streamlink handles the HLS resolution and seeking itself.
        extract_frames_history(youtube_url, args.history, args.limit, args.duration, args.output)
    else:
        # Live Mode (CV2)
        extract_frames_live(stream_url, args.limit, args.interval, args.output)

if __name__ == "__main__":
    main()
