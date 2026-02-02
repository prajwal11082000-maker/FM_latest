import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'ui' / 'tasks' / 'task_monitor.py'
text = p.read_text(encoding='utf-8')
orig = text

# Fix curly excepts
text = text.replace('except Exception {', 'except Exception:')

# Normalize function indentation within the TaskMonitorWidget class
class_match = re.search(r'^(\s*)class\s+TaskMonitorWidget\(QWidget\):', text, flags=re.M)
if not class_match:
    raise SystemExit('TaskMonitorWidget class not found')
class_start = class_match.end()
pre = text[:class_start]
body = text[class_start:]

# Replace any def indentation to exactly 4 spaces within the class body
body = re.sub(r'^(\s*)def\s+', '    def ', body, flags=re.M)

# Ensure there is a newline before each 'def' for clarity (optional)
body = re.sub(r'\n\s*\n\s*\n', '\n\n', body)

new_text = pre + body

if new_text != orig:
    backup = p.with_suffix('.py.bak_final')
    backup.write_text(orig, encoding='utf-8')
    p.write_text(new_text, encoding='utf-8')
    print('Finalized indentation fixes. Backup at', backup)
else:
    print('No changes needed')
