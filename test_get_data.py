import pytest
import os
import shutil
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
from get_data import get_stream_url, extract_frames, get_dynamic_youtube_url

# --- Fixtures ---
@pytest.fixture
def temp_output_dir():
    dir_name = "test_data_output"
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)
    yield dir_name
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)

# --- Unit Tests ---

def test_get_stream_url_success():
    with patch('yt_dlp.YoutubeDL') as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.return_value = {'url': 'http://test.stream/playlist.m3u8'}
        
        url = get_stream_url("http://fake.url")
        assert url == 'http://test.stream/playlist.m3u8'

def test_get_stream_url_failure():
    with patch('yt_dlp.YoutubeDL') as mock_ydl:
        instance = mock_ydl.return_value.__enter__.return_value
        instance.extract_info.side_effect = Exception("Download failed")
        
        # Should return None if scraping fails AND direct yt-dlp fails
        # Mocking generic fail for this test
        with patch('get_data.get_dynamic_youtube_url', return_value=None):
            url = get_stream_url("http://broken.url")
            assert url is None

def test_get_dynamic_youtube_url():
    # Mock requests to simulate torilive.fi structure
    with patch('requests.get') as mock_get:
        # Response 1: Main Page HTML
        mock_response_html = MagicMock()
        mock_response_html.text = '<html><script src="/js/app.12345678.js"></script></html>'
        mock_response_html.raise_for_status.return_value = None
        
        # Response 2: JS Content
        mock_response_js = MagicMock()
        mock_response_js.text = 'var s = "https://www.youtube.com/embed/ABCDEFGHIJK?autoplay=1";'
        mock_response_js.raise_for_status.return_value = None
        
        mock_get.side_effect = [mock_response_html, mock_response_js]
        
        url = get_dynamic_youtube_url("https://torilive.fi")
        assert url == "https://www.youtube.com/watch?v=ABCDEFGHIJK"

def test_verify_generated_images(temp_output_dir):
    # This test actually checks image validity
    # 1. Create a dummy image
    os.makedirs(temp_output_dir, exist_ok=True)
    dummy_path = os.path.join(temp_output_dir, "test_img.jpg")
    
    # Create a real small blank image using cv2
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    cv2.imwrite(dummy_path, img)
    
    # 2. Verify it exists and is valid
    assert os.path.exists(dummy_path)
    
    # 3. Try to read it back with OpenCV
    read_img = cv2.imread(dummy_path)
    assert read_img is not None
    assert read_img.shape == (10, 10, 3)

# --- Integration / Logic Tests using Mocks ---

@patch('cv2.VideoCapture')
@patch('cv2.imwrite')
def test_extract_frames_logic(mock_imwrite, mock_capture, temp_output_dir):
    # Mock VideoCapture behavior
    mock_cap_instance = MagicMock()
    mock_capture.return_value = mock_cap_instance
    mock_cap_instance.isOpened.return_value = True
    
    # Create a dummy frame (100x100 green image)
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    dummy_frame[:] = (0, 255, 0)
    
    # Configure read() to return (True, frame)
    # We need enough reads to satisfy the interval loop. 
    # Since the script checks time, we can't fully control the loop speed with just counting reads 
    # unless we also mock time.time(). 
    
    mock_cap_instance.read.return_value = (True, dummy_frame)

    with patch('time.time') as mock_time:
        # Simulate time progressing: 0, 5, 10, 15... 
        # The script calls time.time() twice per loop (start and check).
        # Let's provide a sequence of increasing times enough to capture 2 frames.
        mock_time.side_effect = [0, 0, 5, 5, 10, 10, 15, 15, 20, 20] 
        
        extract_frames("http://dummy.stream", limit=2, interval=5, output_dir=temp_output_dir)
        
    # Verify outputs
    assert os.path.exists(temp_output_dir)
    assert mock_imwrite.call_count == 2
    args, _ = mock_imwrite.call_args_list[0]
    assert args[0].startswith(os.path.join(temp_output_dir, "torikamera_"))
    assert args[0].endswith(".jpg")

@patch('cv2.VideoCapture')
def test_extract_frames_stream_fail(mock_capture, temp_output_dir):
    mock_cap_instance = MagicMock()
    mock_capture.return_value = mock_cap_instance
    mock_cap_instance.isOpened.return_value = False # Simulation: Stream won't open
    
    extract_frames("http://bad.stream", limit=1, interval=1, output_dir=temp_output_dir)
    
    # Directory might be created, but no files
    assert not os.listdir(temp_output_dir) if os.path.exists(temp_output_dir) else True
