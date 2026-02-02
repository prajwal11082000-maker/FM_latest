import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'ui' / 'tasks' / 'task_monitor.py'
text = p.read_text(encoding='utf-8')
orig = text

# 1) Replace any 'except Exception {' with proper colon
text = text.replace('except Exception {', 'except Exception:')

# 2) Reindent all top-level defs within TaskMonitorWidget to 4 spaces
class_pat = re.compile(r'^(\s*)class\s+TaskMonitorWidget\(QWidget\):', re.M)
m = class_pat.search(text)
if not m:
    raise SystemExit('TaskMonitorWidget class not found')
class_start = m.start()

# Scan after class header
after = text[m.end():]
lines = after.splitlines(True)

for i, line in enumerate(lines):
    if re.match(r'^\s*def\s+\w+\s*\(', line):
        # force 4-space indent
        trimmed = line.lstrip()
        lines[i] = '    ' + trimmed

# 3) Join back
new_after = ''.join(lines)
text = text[:m.end()] + new_after

if text != orig:
    backup = p.with_suffix('.py.reindent_bak')
    backup.write_text(orig, encoding='utf-8')
    p.write_text(text, encoding='utf-8')
    print('Reindented TaskMonitorWidget methods. Backup at', backup)
else:
    print('No changes made')
