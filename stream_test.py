
import subprocess
import cv2
import numpy as np
from ultralytics import YOLO

# -----------------------------
# Lataa YOLO-mallit
# -----------------------------
bus_model = YOLO("models/best.pt")        # sinun bussimalli
person_model = YOLO("yolov8n.pt")         # COCO-malli ihmisille

# -----------------------------
# FFmpeg-komento Toriliven streamiin
# -----------------------------
stream_url = "https://torilive.fi/live/stream.m3u8"

ffmpeg_cmd = [
    "ffmpeg",
    "-user_agent", "Mozilla/5.0",
    "-i", stream_url,
    "-loglevel", "quiet",
    "-an",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-"
]

process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

# Toriliven resoluutio (1080p)
width = 1920
height = 1080
frame_size = width * height * 3

print("Streami käynnistyy...")

last_bus_detected = False

# -----------------------------
# Pääsilmukka
# -----------------------------
while True:
    raw_frame = process.stdout.read(frame_size)
    if not raw_frame:
        continue

    frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))

    # -----------------------------
    # Ihmisten tunnistus
    # -----------------------------
    person_results = person_model(frame, conf=0.35)
    person_count = 0

    for box in person_results[0].boxes:
        cls = int(box.cls[0])
        if person_model.names[cls] == "person":
            person_count += 1

    # -----------------------------
    # Bussin tunnistus
    # -----------------------------
    bus_results = bus_model(frame, conf=0.40)
    bus_detected = False

    for box in bus_results[0].boxes:
        cls = int(box.cls[0])
        if bus_model.names[cls] == "bus":
            bus_detected = True

    # Ilmoitus kun uusi bussi tulee kuvaan
    if bus_detected and not last_bus_detected:
        print("🚌 UUSI BUSSI TULI KUVAAN")

    last_bus_detected = bus_detected

    # -----------------------------
    # Piirrä annotaatiot
    # -----------------------------
    annotated = frame.copy()

    # Bussit
    annotated = bus_results[0].plot()

    # Ihmiset
    annotated = person_results[0].plot()

    # Ihmismäärä ruudulle
    cv2.putText(
        annotated,
        f"Ihmisiä: {person_count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 255, 0),
        3
    )

    cv2.imshow("Torikamera – YOLO", annotated)

    if cv2.waitKey(1) == 27:  # ESC lopettaa
        break

process.terminate()
cv2.destroyAllWindows()
