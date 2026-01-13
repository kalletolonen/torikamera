# God's Eye: Turku Market Square 👁️

> "Ship it like Hotz, Label it like Karpathy."

This project creates a custom object detection model for the Turku Market Square (Torikamera) to detect Pedestrians, Cyclists, and Buses from a high-angle "God's Eye" view.

## The Master Plan

### Phase 1: The Heist (Data Acquisition) 🕵️

**Philosophy**: "If you can't get the data, you can't train the model. Get it fast, get it raw."
We rip the live stream directly to getting training data.

**How to Run the Ripper:**

1. **Setup Environment** (Run once):

   **Mac/Linux:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

   **Windows:**

   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run Tests**:
   ```bash
   pytest
   ```
3. **Run the Heist**:

   **Mac/Linux:**

   ```bash
   python3 get_data.py --limit 100 --interval 5
   ```

   **Windows:**

   ```powershell
   python get_data.py --limit 100 --interval 5
   ```

   _Arguments:_

   - `--limit`: Number of frames to capture (default: 50).
   - `--interval`: Seconds between frames (default: 5).
   - `--url`: (Optional) Direct YouTube URL if `torilive.fi` parsing fails.

**Output**: High-quality JPGs in `data/raw/`.

To go back in time (up to 12 hours):

**Mac/Linux:**

```bash
python3 get_data.py --history 1 6 11 --limit 5
```

**Windows:**

```powershell
python get_data.py --history 1 6 11 --limit 5
```

_Timeline:_

- `--history 1`: 1 Hour ago.
- `--history 6`: 6 Hours ago.
- `--history 11`: 11 Hours ago (Early morning).

### Phase 2: The Grunt Work (Labeling) 🏷️

**Philosophy**: "The model is only as smart as the teacher. Be a strict teacher."
We use Roboflow to hand-label the data.

1. **Upload**: Push `data/raw/*.jpg` to a new Roboflow project.
2. **Classes**:
   - `Pedestrian` (Walking)
   - `Cyclist` (Riding bike/scooter)
   - `Bus` (Föli yellow buses)
3. **Annotate**: Draw tight boxes. This is a top-down view, so boxes will be square-ish.
4. **Export**: Format `YOLOv8`.

### Phase 3: The Magic (Transfer Learning) 🧠

**Philosophy**: "Don't be a hero. Transfer learn."
We take a brain that knows what a "dog" is and teach it what a "Finn from above" is.

**Training Command:**

```bash
yolo task=detect \
     mode=train \
     model=yolov8n.pt \
     data=path/to/data.yaml \
     epochs=50 \
     imgsz=640
```

_Using `yolov8n.pt` (Nano) for max speed._

---

### Phase 4: Stretch goal

Draw a live heatmap on live video of tårgets moving (pedestrians, bikes & buses)
