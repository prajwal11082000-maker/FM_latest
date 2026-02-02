import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'ui' / 'tasks' / 'task_monitor.py'
text = p.read_text(encoding='utf-8')
orig = text

# 1) Ensure specific class methods are indented to exactly 4 spaces
method_names = [
    'check_device_availability',
    'start_selected_task',
    'complete_selected_task',
    'cancel_selected_task',
    'change_task_status',
    '_poll_handshake_status',
    '_start_completion_watcher',
    '_poll_completion_status',
    '_show_status_popup',
    '_update_status_popup',
    '_close_status_popup',
    '_silent_update_task_status_by_row_id',
]
for name in method_names:
    # Any indentation -> 4 spaces at class scope
    text = re.sub(rf'^[\t ]*def\s+{name}\(', f'    def {name}(', text, flags=re.M)

# 2) Fix nested zone_key inside _derive_start_zone_for_audit
start = text.find('def _derive_start_zone_for_audit(')
if start != -1:
    # limit to next def at class level
    next_def = text.find('\n    def ', start + 1)
    segment_end = next_def if next_def != -1 else len(text)
    segment = text[start:segment_end]
    # Indent 'def zone_key(' to 8 spaces and its inner body to 12 spaces if present
    segment = re.sub(r'^\s*def\s+zone_key\(z:\s*str\):', '        def zone_key(z: str):', segment, flags=re.M)
    # Ensure inner lines start with 12 spaces (keep content as-is otherwise)
    segment = re.sub(r'^(\s{0,8})(s = str\(z\))', r'            \2', segment, flags=re.M)
    segment = re.sub(r'^(\s{0,8})(return \(0, int\(s\)\) if s\.isdigit\(\) else \(1, s\))', r'            \2', segment, flags=re.M)
    text = text[:start] + segment + text[segment_end:]

# 2b) Fix nested has_edge inside _build_zone_sequence_for_map
start_b = text.find('def _build_zone_sequence_for_map(')
if start_b != -1:
    next_def_b = text.find('\n    def ', start_b + 1)
    seg_end_b = next_def_b if next_def_b != -1 else len(text)
    seg_b = text[start_b:seg_end_b]
    # Indent 'def has_edge(' to 8 spaces inside the method body
    seg_b = re.sub(r'^\s*def\s+has_edge\(fz,\s*tz\):', '        def has_edge(fz, tz):', seg_b, flags=re.M)
    text = text[:start_b] + seg_b + text[seg_end_b:]

# 3) Fix nested zone_key inside _build_full_map_sequence under the `if not start_zone:` branch
start2 = text.find('def _build_full_map_sequence(')
if start2 != -1:
    next_def2 = text.find('\n    def ', start2 + 1)
    seg_end2 = next_def2 if next_def2 != -1 else len(text)
    seg2 = text[start2:seg_end2]
    # Indent def zone_key to 12 spaces (inside the if-block)
    seg2 = re.sub(r'^\s*def\s+zone_key\(z\):', '            def zone_key(z):', seg2, flags=re.M)
    # Ensure its body lines have 16 spaces
    seg2 = re.sub(r'^(\s{0,12})(s = str\(z\))', r'                \2', seg2, flags=re.M)
    seg2 = re.sub(r'^(\s{0,12})(return \(0, int\(s\)\) if s\.isdigit\(\) else \(1, s\))', r'                \2', seg2, flags=re.M)
    # Ensure the assignment line for start_zone is at 12 spaces
    seg2 = re.sub(r'^(\s{0,8})start_zone = sorted\(zone_ids, key=zone_key\)\[0\] if zone_ids else None',
                  '            start_zone = sorted(zone_ids, key=zone_key)[0] if zone_ids else None', seg2, flags=re.M)
    text = text[:start2] + seg2 + text[seg_end2:]

# 4) Fix accidental zero-indented view_task_details to class indent if present
text = re.sub(r'^(def\s+view_task_details\()', r'    \1', text, flags=re.M)

if text != orig:
    backup = p.with_suffix('.py.bak_fix2')
    backup.write_text(orig, encoding='utf-8')
    p.write_text(text, encoding='utf-8')
    print('Applied structural indentation fixes. Backup at', backup)
else:
    print('No changes necessary.')
