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
   playwright install chromium
   ```

   **Windows:**

   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Run Tests**:
   ```bash
   pytest
   ```
3. **Run the Heist**:

   **Live Data (Streamlink/CV2):**

   ```bash
   python3 get_data.py --limit 100 --interval 5
   ```

   **Historical Data (Headless Browser):**

   ```bash
   python get_data.py --history 6.0 12.0 --limit 10
   ```

   _Arguments:_

   - `--limit`: Number of frames to capture.
   - `--interval`: Seconds between frames (Live mode only).
   - `--history`: Hours ago to extract from (e.g., `6.0` for 6 hours ago). Accepts multiple values.

**Output**: High-quality Full-HD JPGs in `data/raw/` (approx 150KB-200KB each).

---

## Project Maintenance and Future Use

### Modifying the Script

The core logic for scraping is in `get_data.py`.

- **Dependencies**: The script uses `playwright` (headless browser) to extract historical frames, bypassing YouTube's API restrictions and providing a visual capture.
- **Nuclear CSS Strategy**: The script injects aggressive CSS and uses a `setInterval` loop to force the YouTube player to full-screen and hide all overlays (search bar, sidebar, gradients).
- **Element-Level Capture**: Screenshots are taken of the `<video>` tag directly, ensuring no white borders or page layout artifacts.
- **Robustness**: The script automatically handles:
  - Cookie consent popups ("Hylkää kaikki").
  - Buffering timeouts (auto-reloads page if stream stalls).

### Troubleshooting

- **Buffering Timeouts**: If the script is stuck on "Waiting for video to buffer", it will automatically reload the page after 30 seconds and retry.
- **Black Frames**: If frames are ~20KB and black, it means the stream hadn't loaded. Rerun the script for that specific hour offset.
- **Headless Issues**: If extraction fails, try running non-headless (modify `get_data.py` `headless=False`) to see what the browser is doing.
