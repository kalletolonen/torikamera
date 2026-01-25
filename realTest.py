import cv2
import yt_dlp
from ultralytics import YOLO

YOUTUBE_URL = "https://www.youtube.com/watch?v=F7SDNtc5waU"

def get_stream_url(youtube_url):
    print("Haetaan suora HLS-stream yt-dlp:llä...")

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "format": "best"
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            stream_url = info.get("url")
            print("HLS-stream löytyi:", stream_url)
            return stream_url
    except Exception as e:
        print("yt-dlp epäonnistui:", e)
        return None


def run_yolo(stream_url):
    cap = cv2.VideoCapture(stream_url)

    if not cap.isOpened():
        print("Stream ei auennut:", stream_url)
        return

    print("YOLO käynnistyy...")

    person_model = YOLO("yolov8n.pt")
    bus_model = YOLO("models/best.pt")

    last_bus = False

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # Ihmiset
        person_results = person_model(frame, conf=0.35)
        person_count = sum(
            1 for box in person_results[0].boxes
            if person_model.names[int(box.cls[0])] == "person"
        )

        # Bussit
        bus_results = bus_model(frame, conf=0.40)
        bus_detected = any(
            bus_model.names[int(box.cls[0])] == "bus"
            for box in bus_results[0].boxes
        )

        print(f"Ihmisiä: {person_count} | Bussi: {'KYLLÄ' if bus_detected else 'ei'}")

        if bus_detected and not last_bus:
            print("🚌 UUSI BUSSI TULI KUVAAN")

        last_bus = bus_detected

        # Piirrä
        annotated = frame.copy()
        annotated = person_results[0].plot()
        annotated = bus_results[0].plot()

        cv2.imshow("Torikamera YOLO", annotated)

        if cv2.waitKey(1) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    stream_url = get_stream_url(YOUTUBE_URL)
    if stream_url:
        run_yolo(stream_url)
