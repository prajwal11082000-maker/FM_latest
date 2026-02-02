import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / 'ui' / 'tasks' / 'task_monitor.py'
text = p.read_text(encoding='utf-8')
orig = text

# Fix curly excepts
text = text.replace('except Exception {', 'except Exception:')

# Ensure methods under the class are at 4 spaces indentation
class_idx = text.find('class TaskMonitorWidget(QWidget):')
if class_idx != -1:
    pre = text[:class_idx]
    body = text[class_idx:]
    # Within the class, normalize def indentation to 4 spaces
    def_pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(', re.M)
    def repl(m):
        indent, name = m.group(1), m.group(2)
        # ensure exactly 4 spaces
        return '    ' + f'def {name}('
    body = def_pattern.sub(repl, body)
    text = pre + body

# Also ensure view_task_details def has correct indent (in case)
text = re.sub(r'^\s*def view_task_details\(', '    def view_task_details(', text, flags=re.M)

if text != orig:
    backup = p.with_suffix('.py.bak_norm')
    backup.write_text(orig, encoding='utf-8')
    p.write_text(text, encoding='utf-8')
    print('Normalized indentation in task_monitor.py; backup at', backup)
else:
    print('No changes made')
