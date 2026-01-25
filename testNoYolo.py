import subprocess
import cv2
import numpy as np

stream_url = "https://torilive.fi/live/stream.m3u8"

ffmpeg_cmd = [
    "ffmpeg",
    "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "-headers", "Referer: https://torilive.fi/",
    "-headers", "Origin: https://torilive.fi",
    "-headers", "Accept: */*",
    "-headers", "Accept-Language: en-US,en;q=0.9",
    "-headers", "Accept-Encoding: identity",
    "-headers", "Connection: keep-alive",
    "-headers", "Sec-Fetch-Site: same-origin",
    "-headers", "Sec-Fetch-Mode: cors",
    "-headers", "Sec-Fetch-Dest: empty",
    "-i", stream_url,
    "-loglevel", "debug",
    "-an",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-"
]



process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

width = 1920
height = 1080
frame_size = width * height * 3

print("Streami käynnistyy...")

while True:
    raw = process.stdout.read(frame_size)
    if not raw:
        continue

    frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))

    cv2.imshow("Torikamera – RAW", frame)

    key = cv2.waitKey(1)
    if key == 27 or key == ord('q'):
        break

process.terminate()
cv2.destroyAllWindows()
