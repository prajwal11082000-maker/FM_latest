import io, sys, re, os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'ui' / 'tasks' / 'task_monitor.py'

text = path.read_text(encoding='utf-8')
orig = text

# Ensure def lines are indented to 4 spaces (class scope)
method_names = [
    'start_selected_task',
    'complete_selected_task',
    'cancel_selected_task',
    'change_task_status',
    'view_task_details',
    '_poll_handshake_status',
    '_start_completion_watcher',
    '_poll_completion_status',
    '_show_status_popup',
    '_update_status_popup',
    '_close_status_popup',
    '_silent_update_task_status_by_row_id',
]
for name in method_names:
    text = re.sub(rf'^[\t ]*def {name}\(', f'    def {name}(', text, flags=re.M)

# Fix a curly-brace except if any
text = text.replace('except Exception {', 'except Exception:')

# Minimal sanity: ensure class header exists
if 'class TaskMonitorWidget(QWidget):' not in text:
    print('TaskMonitorWidget class not found; aborting to avoid corruption.', file=sys.stderr)
    sys.exit(1)

if text != orig:
    backup = path.with_suffix('.py.bak_fix')
    backup.write_text(orig, encoding='utf-8')
    path.write_text(text, encoding='utf-8')
    print('Applied indentation fixes to task_monitor.py. Backup at', backup)
else:
    print('No changes needed.')
