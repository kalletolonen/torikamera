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

import argparse
import queue
import threading
import sys

# =============================================================================
# Configuration Constants
# =============================================================================

YOUTUBE_URL = "https://www.youtube.com/watch?v=F7SDNtc5waU"

# Frame skipping: Only run YOLO inference on every Nth frame
# Higher values = less lag but lower detection responsiveness
PROCESS_EVERY_N_FRAMES = 1

# Detection confidence threshold for bus model
BUS_CONFIDENCE_THRESHOLD = 0.10

# Path to custom-trained bus detection model
BUS_MODEL_PATH = "models/best.pt"

# Default buffer size in seconds
DEFAULT_BUFFER_SECONDS = 5


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
# Stream Buffering
# =============================================================================

class StreamBuffer:
    """
    Threaded frame reader to buffer video frames.
    
    Reads frames in a separate thread and puts them into a queue to smooth out
    network jitter during playback.
    """
    def __init__(self, stream_url: str, buffer_seconds: int = 5):
        self.stream_url = stream_url
        self.buffer_seconds = buffer_seconds
        
        # Open stream to get FPS
        self.cap = cv2.VideoCapture(stream_url)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open stream: {stream_url}")
            
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0:
            self.fps = 30 # Fallback default
            
        self.buffer_size = int(self.fps * buffer_seconds)
        self.queue = queue.Queue(maxsize=self.buffer_size * 2) # Allow some headroom
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def start(self):
        """Start the frame reading thread."""
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        print(f"Buffering logic started. Buffer duration: {self.buffer_seconds}s ({self.buffer_size} frames)")

    def _update(self):
        """Internal loop to read frames and put them into queue."""
        while self.running:
            if not self.queue.full():
                ret, frame = self.cap.read()
                if not ret:
                    # Stream ended or error
                    self.running = False
                    break
                self.queue.put(frame)
            else:
                # Queue full, wait a bit to avoid busy loop
                time.sleep(0.01)
        self.cap.release()

    def read(self):
        """Get the next frame from the buffer."""
        if not self.queue.empty():
            return True, self.queue.get()
        return False, None

    def ready(self):
        """Check if buffer is sufficiently filled to start/resume playback."""
        # Consider ready if we have at least 'buffer_size' frames 
        # OR if the stream has stopped (so we drain the remaining frames)
        return self.queue.qsize() >= self.buffer_size or not self.running

    def stop(self):
        """Stop the thread and cleanup."""
        self.running = False
        if self.thread:
            self.thread.join()

# =============================================================================
# YOLO Detection Loop
# =============================================================================

def run_yolo(stream_url: str, buffer_seconds: int = DEFAULT_BUFFER_SECONDS, is_local_file: bool = False) -> None:
    """
    Run real-time YOLO bus detection on a video stream.
    
    Args:
        stream_url: Direct URL to video stream
        buffer_seconds: Seconds of video to buffer before playback
        is_local_file: True if using local file, False if using live stream
    """
    source_label = "LOCAL FILE" if is_local_file else "LIVE STREAM"
    print(f"Source: {source_label}")
    print(f"Starting YOLO with {buffer_seconds}s buffer...")

    # Initialize stream buffer
    try:
        stream = StreamBuffer(stream_url, buffer_seconds)
    except RuntimeError as e:
        print(e)
        return

    stream.start()

    print("YOLO käynnistyy...")  # "YOLO starting..."

    # Load custom-trained bus detection model
    bus_model = YOLO(BUS_MODEL_PATH)

    # State tracking
    last_bus = False           # Was a bus detected in the previous processed frame?
    frame_count = 0            # Frame counter for skipping logic
    last_annotated = None      # Buffered annotated frame for smooth display
    prev_time = 0              # For FPS calculation
    
    # Pre-buffering phase
    print("Buffering stream...")
    while not stream.ready():
        time.sleep(0.1)
        sys.stdout.write(f"\rBuffering: {stream.queue.qsize()}/{stream.buffer_size} frames")
        sys.stdout.flush()
    print("\nPlayback starting!")

    # Main processing loop
    while True:
        # Read from buffer
        ret, frame = stream.read()
        
        if not ret:
            # Buffer empty or stream ended
            if not stream.running:
                print("Stream ended.")
                break
            else:
                # Buffer underrun - wait briefly
                # Ideally unrelated to network since 'read' is fast from queue
                # But if queue is empty, we must wait
                time.sleep(0.001) 
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
        
        # Show source type (local file vs live stream)
        cv2.putText(
            display_frame,
            source_label,
            (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 255) if is_local_file else (0, 255, 0),
            2
        )

        cv2.imshow("Torikamera YOLO", display_frame)

        # Check for ESC key (keycode 27) to exit
        if cv2.waitKey(1) == 27:
            break

    # Cleanup
    stream.stop()
    cv2.destroyAllWindows()


# =============================================================================
# Entry Point
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Real-time bus detection on Torikamera")
    parser.add_argument(
        "--buffer", 
        type=int, 
        default=DEFAULT_BUFFER_SECONDS,
        help=f"Buffer size in seconds (default: {DEFAULT_BUFFER_SECONDS})"
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Path to video file to use instead of live stream"
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # Determine stream source: File or YouTube URL
    if args.source:
        print(f"Using local file as source: {args.source}")
        run_yolo(args.source, 0, is_local_file=True)
    else:
        print("Using live stream from YouTube")
        stream_url = get_stream_url(YOUTUBE_URL)
        if stream_url:
            run_yolo(stream_url, args.buffer, is_local_file=False)
