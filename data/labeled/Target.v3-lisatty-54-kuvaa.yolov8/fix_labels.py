import os
import glob

base_dir = '/Users/kalle.tolonen/test/torikamera/data/labeled/Target.v3-lisatty-54-kuvaa.yolov8'

# 1. Swap in txt files
count_swapped = 0
for split in ['train', 'valid', 'test']:
    labels_dir = os.path.join(base_dir, split, 'labels')
    if not os.path.exists(labels_dir):
        continue
    
    for txt_file in glob.glob(os.path.join(labels_dir, '*.txt')):
        with open(txt_file, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        changed = False
        for line in lines:
            parts = line.strip().split()
            if not parts:
                continue
            
            try:
                class_id = int(parts[0])
                if class_id == 2:
                    parts[0] = '3'
                    changed = True
                elif class_id == 3:
                    parts[0] = '2'
                    changed = True
            except ValueError:
                pass
                
            new_lines.append(' '.join(parts) + '\n')
            
        if changed:
            with open(txt_file, 'w') as f:
                f.writelines(new_lines)
            count_swapped += 1

print(f"Swapped labels in {count_swapped} txt files.")

# 2. Swap in data.yaml
yaml_path = os.path.join(base_dir, 'data.yaml')
if os.path.exists(yaml_path):
    with open(yaml_path, 'r') as f:
        content = f.read()
    
    if "['Bus', 'Car', 'Delivery', 'Two-wheeler']" in content:
        content = content.replace("['Bus', 'Car', 'Delivery', 'Two-wheeler']", "['Bus', 'Car', 'Two-wheeler', 'Delivery']")
        with open(yaml_path, 'w') as f:
            f.write(content)
        print("Updated data.yaml")

print("Finished swapping labels 2 and 3.")
