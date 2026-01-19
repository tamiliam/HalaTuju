
import json
import os

def check():
    current_dir = os.getcwd()
    print(f"CWD: {current_dir}")
    
    path = os.path.join(current_dir, 'data', 'course_tags.json')
    print(f"Target Path: {path}")
    
    if not os.path.exists(path):
        print("FILE NOT FOUND")
        return

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"File Size: {len(content)} bytes")
    
    try:
        data = json.loads(content)
        print(f"JSON Loaded Successfully. Type: {type(data)}")
        print(f"Item Count: {len(data)}")
        
        # Check IDs
        ids = [item.get('course_id') for item in data]
        unique_ids = set(ids)
        print(f"Unique IDs: {len(unique_ids)}")
        
        if len(ids) != len(unique_ids):
            print("WARNING: Duplicate IDs found in JSON list!")
            from collections import Counter
            c = Counter(ids)
            dup = {k:v for k,v in c.items() if v > 1}
            print(f"Duplicates: {dup}")
            
        # Check specific ID
        target = "POLY-DIP-004"
        if target in unique_ids:
            print(f"FOUND {target}")
            # print tags
            for item in data:
                if item.get('course_id') == target:
                    print(json.dumps(item, indent=2))
                    break
        else:
            print(f"MISSING {target}")
            
    except Exception as e:
        print(f"JSON ERROR: {e}")

if __name__ == "__main__":
    check()
