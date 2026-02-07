"""
realTest.py - Real-time bus detection on Torikamera YouTube stream

This script fetches a live YouTube stream (Torikamera) and runs YOLO-based
bus detection on the video frames. It displays annotated frames showing
detected buses and prints detection status to the console.

Performance: Uses frame skipping to reduce YOLO inference load - only 
processes every Nth frame while displaying the last annotated result
for skipped frames (buffering for smooth playback).
"""

import cv2
import time
import yt_dlp
from ultralytics import YOLO

# =============================================================================
# Configuration Constants
# =============================================================================

YOUTUBE_URL = "https://www.youtube.com/watch?v=F7SDNtc5waU"

# Frame skipping: Only run YOLO inference on every Nth frame
# Higher values = less lag but lower detection responsiveness
PROCESS_EVERY_N_FRAMES = 1

# Detection confidence threshold for bus model
BUS_CONFIDENCE_THRESHOLD = 0.40

# Path to custom-trained bus detection model
BUS_MODEL_PATH = "models/best.pt"


# =============================================================================
# Stream URL Extraction
# =============================================================================

def get_stream_url(youtube_url: str) -> str | None:
    """
    Extract the direct HLS stream URL from a YouTube video/livestream.
    
    Uses yt-dlp to bypass YouTube's player and get the raw stream URL
    that can be opened with OpenCV's VideoCapture.
    
    Args:
        youtube_url: YouTube video or livestream URL
        
    Returns:
        Direct stream URL (typically .m3u8) or None if extraction fails
    """
    print("Haetaan suora HLS-stream yt-dlp:llä...")  # "Fetching direct HLS stream with yt-dlp..."

    ydl_opts = {
        "quiet": True,          # Suppress yt-dlp output
        "skip_download": True,  # Don't download, just extract info
        "format": "best"        # Get best quality stream
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            stream_url = info.get("url")
            print("HLS-stream löytyi:", stream_url)  # "HLS stream found:"
            return stream_url
    except Exception as e:
        print("yt-dlp epäonnistui:", e)  # "yt-dlp failed:"
        return None


# =============================================================================
# YOLO Detection Loop
# =============================================================================

def run_yolo(stream_url: str) -> None:
    """
    Run real-time YOLO bus detection on a video stream.
    
    Opens the stream, loads the bus detection model, and processes frames
    in a loop. Uses frame skipping to reduce computational load - only
    runs inference every PROCESS_EVERY_N_FRAMES frames, displaying the
    last annotated frame for skipped frames (buffering).
    
    Args:
        stream_url: Direct URL to video stream (HLS or other OpenCV-compatible format)
    """
    # Open video stream
    cap = cv2.VideoCapture(stream_url)

    if not cap.isOpened():
        print("Stream ei auennut:", stream_url)  # "Stream didn't open:"
        return

    print("YOLO käynnistyy...")  # "YOLO starting..."

    # Load custom-trained bus detection model
    bus_model = YOLO(BUS_MODEL_PATH)

    # State tracking
    last_bus = False           # Was a bus detected in the previous processed frame?
    frame_count = 0            # Frame counter for skipping logic
    last_annotated = None      # Buffered annotated frame for smooth display
    prev_time = 0              # For FPS calculation

    # Main processing loop
    while True:
        ret, frame = cap.read()
        if not ret:
            # Frame read failed (stream hiccup) - try next frame
            continue

        frame_count += 1

        # Only run YOLO inference on every Nth frame for performance
        if frame_count % PROCESS_EVERY_N_FRAMES == 0:
            # Run bus detection
            bus_results = bus_model(frame, conf=BUS_CONFIDENCE_THRESHOLD)
            
            # Check if any bus was detected
            bus_detected = any(
                bus_model.names[int(box.cls[0])] == "bus"
                for box in bus_results[0].boxes
            )

            # Print detection status
            print(f"Bussi: {'KYLLÄ' if bus_detected else 'ei'}")  # "Bus: YES/no"

            # Notify when a new bus enters the frame
            if bus_detected and not last_bus:
                print("🚌 UUSI BUSSI TULI KUVAAN")  # "NEW BUS ENTERED FRAME"

            last_bus = bus_detected

            # Create annotated frame with detection boxes
            last_annotated = bus_results[0].plot()

        # Prepare display frame
        # Use copy to avoid over-drawing FPS on the buffered 'last_annotated' frame
        display_frame = (last_annotated if last_annotated is not None else frame).copy()

        # Calculate and draw FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time) if prev_time > 0 else 0
        prev_time = curr_time
        
        cv2.putText(
            display_frame, 
            f"FPS: {int(fps)}", 
            (10, 50), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            2, 
            (255, 0, 0), 
            3
        )

        cv2.imshow("Torikamera YOLO", display_frame)

        # Check for ESC key (keycode 27) to exit
        if cv2.waitKey(1) == 27:
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    stream_url = get_stream_url(YOUTUBE_URL)
    if stream_url:
        run_yolo(stream_url)
