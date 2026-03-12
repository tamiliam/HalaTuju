
import re
import os

def repair():
    file_path = 'c:/Users/tamil/Python/HalaTuju/data/courses.csv'
    backup_path = file_path + '.bak'
    
    if not os.path.exists(backup_path):
        # Create backup first
        with open(file_path, 'r', encoding='cp1252') as f:
            content = f.read()
        with open(backup_path, 'w', encoding='cp1252') as f:
            f.write(content)
        print(f"Backed up to {backup_path}")
    
    with open(file_path, 'r', encoding='cp1252') as f:
        lines = f.readlines()
        
    print(f"Original line count: {len(lines)}")
    
    fixed_lines = []
    current_line = ""
    
    # Pattern for valid start of row: 'ID,Name,...'
    # ID usually looks like 'POLY-...' or 'KKOM-...' or 'IL...'
    # But checking for simple 'starts with quote' or 'starts with alphanumeric' might be tricky.
    # Looking at the file, IDs don't seem quoted? 'POLY-DIP-063,Diploma...'
    # So valid line starts with 'PREFIX-...'.
    
    # Let's assume valid lines contain at least one comma within the first 20 chars?
    # Or strict definition: Starts with POLY, KKOM, IL, MST, U...
    
    id_pattern = re.compile(r'^(POLY|KKOM|IL|MST|U)', re.IGNORECASE)
    
    # Header
    fixed_lines.append(lines[0].strip())
    
    buffer = ""
    
    for line in lines[1:]:
        s_line = line.strip()
        if not s_line: continue # Skip empty
        
        # Heuristic: If line starts with a known ID prefix, it's a NEW row.
        # Otherwise, it's a continuation of the previous row.
        # Also, check if it looks like a continuation (starts with *)
        
        is_new_row = False
        if id_pattern.match(s_line):
           is_new_row = True
        
        # Fallback: Sometimes ID might be quoted?
        # But mostly likely unquoted.
        
        if is_new_row:
            if buffer:
                fixed_lines.append(buffer)
            buffer = s_line
        else:
            # Continuation
            # Append to buffer with a space separator
            if buffer:
                buffer += " " + s_line
            else:
                # Should not happen (orphaned continuation at start), but safeguard
                buffer = s_line

    # Append last buffer
    if buffer:
        fixed_lines.append(buffer)
        
    print(f"Fixed line count: {len(fixed_lines)}")
    
    temp_out = file_path.replace('.csv', '_fixed.csv')
    
    # Write to temp
    with open(temp_out, 'w', encoding='cp1252') as f:
        f.write('\n'.join(fixed_lines))
        f.write('\n')
        
    print(f"Repaired data written to {temp_out}")
    
    # Try to replace
    try:
        os.replace(temp_out, file_path)
        print("Successfully overwrote courses.csv")
    except OSError as e:
        print(f"Could not overwrite courses.csv directly (Locked?): {e}")
        print("Please manually rename courses_fixed.csv to courses.csv if needed.")

if __name__ == "__main__":
    repair()
