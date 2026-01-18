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

from playwright.sync_api import sync_playwright

def extract_frames_history(youtube_url, history_hours, limit, duration, output_dir):
    """
    Uses Playwright to capture frames from the YouTube player by seeking.
    This bypasses API restrictions by acting as a real user.
    """
    print(f"Starting HISTORY capture via Browser. Offsets: {history_hours} hours ago.")
    
    with sync_playwright() as p:
        # Launch browser (headless=True by default)
        browser = p.chromium.launch()
        # Set viewport to 1080p for HD capture
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        
        # Go to video directly (Embed blocked by overlays/consent often)
        print(f"Navigating to {youtube_url}...")
        page.goto(youtube_url)
        
        # Wait a bit for page load
        time.sleep(5)
        
        # Dynamic Popup Killer
        print("Scanning for popups...")
        try:
             buttons = page.locator("button").all()
             for btn in buttons:
                 try:
                     if not btn.is_visible(): continue
                     txt = btn.inner_text().lower()
                     if "reject" in txt or "hylkää" in txt or "google" in txt: 
                         print(f"Clicking button with text: '{txt}'")
                         btn.click()
                         time.sleep(2)
                         break
                 except:
                     pass
        except Exception as e:
             print(f"Popup scan error: {e}")

        # Press ESC just in case of other overlays
        page.keyboard.press("Escape")
        time.sleep(0.5)

        # Force Play if paused
        try:
             if page.locator("button.ytp-play-button[title^='Play']").is_visible(timeout=1000):
                 print("Starting video...")
                 page.keyboard.press("k") # Toggle play
        except:
             pass

        # Wait for video element
        print("Waiting for video element...")
        page.wait_for_selector("video", timeout=30000)
        
        # INJECT "NUCLEAR" CSS LOOP TO MAKE PLAYER FULLSCREEN AND HIDE ALL UI
        # We use a loop because YouTube loves to re-render elements.
        print("Applying Nuclear CSS Loop to remove all overlays...")
        page.evaluate("""
            const interval = setInterval(() => {
                // 0. RESET PAGE
                document.documentElement.style.margin = '0';
                document.documentElement.style.padding = '0';
                document.documentElement.style.background = '#000';
                document.body.style.margin = '0';
                document.body.style.padding = '0';
                document.body.style.background = '#000';
                document.body.style.overflow = 'hidden';
                
                // 1. Maximize Player Container
                const player = document.querySelector('#movie_player');
                if (player) {
                    player.style.position = 'fixed !important';
                    player.style.top = '0px !important';
                    player.style.left = '0px !important';
                    player.style.width = '100vw !important';
                    player.style.height = '100vh !important';
                    player.style.zIndex = '2147483647 !important';
                    player.style.background = '#000';
                    player.style.margin = '0 !important';
                    player.style.padding = '0 !important';
                }

                // 2. Maximize Video Element (Fixes white frame/letterboxing)
                const video = document.querySelector('video');
                if (video) {
                    video.style.objectFit = 'cover'; // or 'contain' if they want full video without crop, but 'cover' removes black/white bars
                    video.style.width = '100vw !important';
                    video.style.height = '100vh !important';
                    video.style.top = '0px !important';
                    video.style.left = '0px !important';
                }
                
                // 3. Hide surrounding page elements
                const selectorsToHide = [
                    'ytd-masthead', 
                    '#masthead-container',
                    '#secondary', 
                    '#guide', 
                    '#comments', 
                    '#related',
                    'ytd-watch-next-secondary-results-renderer',
                    'div#placeholder-player',
                    '#below',
                    'ytd-merch-shelf-renderer',
                    'ytd-player-legacy-desktop-watch-ads-renderer',
                    '#chat' 
                ];
                selectorsToHide.forEach(sel => {
                    const els = document.querySelectorAll(sel);
                    els.forEach(el => el.style.display = 'none');
                });

                // 3. Hide Player Internal Overlays (Controls, Gradients, Title)
                // We restart this check in case DOM changes
                if (!document.getElementById('nuclear-style')) {
                    const style = document.createElement('style');
                    style.id = 'nuclear-style';
                    style.textContent = `
                        .ytp-chrome-top, .ytp-chrome-bottom, 
                        .ytp-gradient-top, .ytp-gradient-bottom,
                        .ytp-watermark, .ytp-ce-element,
                        .ytp-hover-progress, .ytp-bezel,
                        .ytp-spinner, .ytp-ad-overlay-container,
                        .annotation, .iv-module,
                        .ytp-paid-content-overlay,
                        .ytp-suggested-action,
                        button.ytp-button.ytp-cards-button,
                        .ytp-pause-overlay
                        { display: none !important; }
                    `;
                    document.head.appendChild(style);
                }
            }, 100);
        """)
        
        # Give the loop a moment to win
        time.sleep(2)
        
        # Ensure controls are hidden interaction-wise too
        try:
            page.evaluate("if(document.querySelector('#movie_player')) document.querySelector('#movie_player').classList.add('ytp-autohide')")
        except:
            pass

        # Get live duration/latency info to calculate absolute seek time?
        # Actually, for live streams, 'seekTo' works with 'seconds from START of event' or similar?
        # Or does it support negative offset from live?
        # YouTube Player API: player.seekTo(seconds, allowSeekAhead).
        # For live streams, seekTo seeks to a time relative to the stream start.
        # We need to know the 'duration' or 'current time' of the live stream to subtract.
        # Video element 'duration' attribute is often just the buffer or huge number.
        # Calling 'player.getDuration()' returns duration of video (or elapsed time of live stream?).
        # 'player.getCurrentTime()' returns time since stream start.
        
        # Let's get current player time first.
        # Ensure player is loaded.
        page.wait_for_function("document.querySelector('video') && !isNaN(document.querySelector('video').duration)")

        # Ensure we are 'live' to establish baseline or just read the current time.
        # It's safest to assume the page load puts us at 'live edge' ish.
        # Wait a sec for buffer
        time.sleep(2)
        
        live_time = page.evaluate("document.querySelector('video').currentTime")
        print(f"Current Stream Time (Live Edge approx): {live_time}s")
        
        for hours_ago in history_hours:
            print(f"--- Processing: {hours_ago} hours ago ---")
             
            # Calculate target time in seconds
            seek_seconds_back = float(hours_ago) * 3600
            target_time = max(0, live_time - seek_seconds_back)
            
            # REFRESH LOGIC: If we are deep seeking, sometimes a fresh page load helps.
            # But let's try seek first. If it fails, we reload and retry.
            
            MAX_RETRIES = 2
            for attempt in range(MAX_RETRIES):
                print(f"Seeking to {target_time}s (Live - {seek_seconds_back}s)... Attempt {attempt+1}")
                
                # Seek
                page.evaluate(f"document.querySelector('video').currentTime = {target_time}")
                
                # Wait for buffering with retry
                print("Waiting for video to buffer...")
                buffered = False
                for _ in range(15): # Try for 30 seconds
                    time.sleep(2)
                    try:
                        rs = page.evaluate("document.querySelector('video').readyState")
                        if rs >= 3: # HAVE_FUTURE_DATA or HAVE_ENOUGH_DATA
                            buffered = True
                            print(f"Buffered! ReadyState: {rs}")
                            break
                        else:
                             print(f"Still buffering... ReadyState: {rs}")
                             # Try nudging play if stuck
                             if rs == 0:
                                 page.mouse.click(960, 540)
                    except:
                        pass
                
                if buffered:
                    break
                else:
                    print("Warning: Buffering timed out.")
                    if attempt < MAX_RETRIES - 1:
                        print("Reloading page to clear stalled buffer...")
                        page.reload()
                        # Re-run popup and CSS logic
                        time.sleep(5)
                        # ... (We'd need to re-run the whole setup logic here, which is messy in a loop)
                        # Simplified: Just try seeking again, maybe jump a bit?
                        # Actually, better to just accept it or warn.
                        # Let's try attempting to seek a bit forward?
                        target_time += 10
                        print(f"Retrying seek 10s forward: {target_time}")
            
            # Debug ready state
            ready_state = page.evaluate("document.querySelector('video').readyState")
            print(f"Video ReadyState: {ready_state} (4=HAVE_ENOUGH_DATA)")

            # Approximate timestamp for filename
            td = timedelta(hours=hours_ago)
            past_time = datetime.now() - td
            timestamp_str = past_time.strftime("%Y%m%d_%H%M%S")
            
            # Capture frames
            # We can advance explicitly by frame interval
            # But 'seek' might buffer. We should wait for 'seeking' to be false?
            
            for i in range(limit):
                # Wait for buffer (simple sleep for hackiness, better: check readyState)
                time.sleep(1.0) 
                
                # Check if stalled/buffering?
                # For now just screenshot.
                
                filename = os.path.join(output_dir, f"torikamera_{timestamp_str}_h{int(hours_ago)}h_f{i}.jpg")
                
                # Screenshot ONLY the video element to avoid any page borders
                page.locator("video").screenshot(path=filename)
                
                print(f"Saved {filename}")
                
                # Advance 1 second? or small step?
                # Limit implies frames, usually consecutive? or spaced?
                # Original script used whole video clip. Here we take snapshots.
                # Let's advance 0.2s
                page.evaluate("document.querySelector('video').currentTime += 0.2")

        browser.close()

def main():
    parser = argparse.ArgumentParser(description="Torkamera Stream Ripper")
    parser.add_argument("--url", default="https://torilive.fi/", help="URL of the stream source")
    parser.add_argument("--limit", type=int, default=5, help="Number of frames to capture") # Default lowered for browser
    parser.add_argument("--interval", type=int, default=5, help="Seconds between captures (Live mode)")
    parser.add_argument("--output", default="data/raw", help="Directory to save frames")
    
    # Time Travel Arguments
    parser.add_argument("--history", type=float, nargs='+', help="List of hour offsets to scrape from past (e.g. 0.5 2 12)")
    parser.add_argument("--duration", type=int, default=10, help="Ignored in Browser Mode")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)

    # Resolve URL
    stream_url, youtube_url = get_stream_url(args.url)
    if not youtube_url:
        sys.exit(1)

    if args.history:
        # History Mode (Browser)
        extract_frames_history(youtube_url, args.history, args.limit, args.duration, args.output)
    else:
        # Live Mode (CV2)
        extract_frames_live(stream_url, args.limit, args.interval, args.output)

if __name__ == "__main__":
    main()
