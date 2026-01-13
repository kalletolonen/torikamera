import argparse
import cv2
import time
import os
import yt_dlp
import sys
from datetime import datetime

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
            return info['url']
    except Exception as e:
        print(f"Error extracting stream URL: {e}", file=sys.stderr)
        return None


def extract_frames(stream_url, limit, interval, output_dir):
    """
    Captures frames from the stream at the specified interval.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("Error: Could not open video stream.", file=sys.stderr)
        return

    frames_saved = 0
    last_capture_time = 0
    
    print(f"Starting capture. Target: {limit} frames. Interval: {interval}s.")
    
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
                filename = os.path.join(output_dir, f"torikamera_{timestamp}.jpg")
                
                cv2.imwrite(filename, frame)
                print(f"Saved {filename} ({frames_saved + 1}/{limit})")
                
                frames_saved += 1
                last_capture_time = current_time
            
            # Small sleep to avoid burning CPU, but distinct from the capture interval
            # We need to read frames often to keep the buffer fresh, so we don't just sleep for `interval`.
            # Actually, for live streams, if we don't read, the buffer fills up and we get old frames.
            # So we should run the loop tight but only save when interval passes.
            # However, `cap.read()` is blocking usually to the frame rate.
            
    except KeyboardInterrupt:
        print("\nStopping capture...")
    finally:
        cap.release()
        print(f"Done. Saved {frames_saved} frames to {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Torkamera Stream Ripper")
    parser.add_argument("--url", default="https://torilive.fi/", help="URL of the stream source")
    parser.add_argument("--limit", type=int, default=50, help="Number of frames to capture")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between captures")
    parser.add_argument("--output", default="data/raw", help="Directory to save frames")
    
    args = parser.parse_args()
    
    stream_url = get_stream_url(args.url)
    if not stream_url:
        sys.exit(1)
        
    extract_frames(stream_url, args.limit, args.interval, args.output)

if __name__ == "__main__":
    main()
