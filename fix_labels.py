"""
Convert mixed detect/segment labels to pure bounding box format.
Polygon lines (>5 fields) are converted to bounding boxes by taking
min/max of the polygon coordinates.
"""
import os
import glob

def polygon_to_bbox(parts):
    """Convert polygon annotation to bbox: class_id cx cy w h"""
    class_id = parts[0]
    coords = [float(x) for x in parts[1:]]
    xs = coords[0::2]  # even indices = x
    ys = coords[1::2]  # odd indices = y
    
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    
    cx = (x_min + x_max) / 2
    cy = (y_min + y_max) / 2
    w = x_max - x_min
    h = y_max - y_min
    
    return f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"

def fix_label_file(filepath):
    converted = 0
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) > 5:
            new_lines.append(polygon_to_bbox(parts))
            converted += 1
        elif len(parts) == 5:
            new_lines.append(line.strip())
    
    with open(filepath, 'w') as f:
        f.write('\n'.join(new_lines) + '\n')
    
    return converted

# Process train and valid labels
total_converted = 0
total_files = 0
for split in ['train', 'valid']:
    label_dir = f"data/labeled/combined/{split}/labels"
    files = glob.glob(os.path.join(label_dir, "*.txt"))
    for f in files:
        c = fix_label_file(f)
        if c > 0:
            total_converted += c
            total_files += 1

# Remove old caches so YOLO re-scans
for cache in glob.glob("data/labeled/combined/*/labels.cache"):
    os.remove(cache)
    print(f"Removed cache: {cache}")

print(f"Done! Converted {total_converted} polygon annotations to bboxes across {total_files} files.")
