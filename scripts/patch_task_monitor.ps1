param()
$ErrorActionPreference = 'Stop'

# Locate file paths
$root = Split-Path -Parent $PSScriptRoot
$taskMon = Join-Path $root 'ui\tasks\task_monitor.py'

if (-not (Test-Path $taskMon)) { throw "task_monitor.py not found at $taskMon" }

# Backup
$backup = "$taskMon.bak_$(Get-Date -Format yyyyMMdd_HHmmss)"
Copy-Item $taskMon $backup

# Read content
$content = [System.IO.File]::ReadAllText($taskMon)

# ---- 1) Ensure extra Qt widgets are imported ----
if ($content -notmatch 'QDialog' -or $content -notmatch 'QProgressBar') {
    $content = $content -replace 'QAbstractItemView\)', 'QAbstractItemView, QDialog, QProgressBar)'
}

# ---- 2) Ensure timedelta is imported ----
$content = [System.Text.RegularExpressions.Regex]::Replace(
    $content,
    '(?m)^\s*from\s+datetime\s+import\s+datetime\s*$','from datetime import datetime, timedelta'
)

# ---- 3) Ensure DeviceDataHandler is imported ----
if ($content -notmatch 'from\s+data_manager\.device_data_handler\s+import\s+DeviceDataHandler') {
    $content = $content -replace 'from\s+data_manager\.csv_handler\s+import\s+CSVHandler', "from data_manager.csv_handler import CSVHandler`r`nfrom data_manager.device_data_handler import DeviceDataHandler"
}

# ---- 4) Initialize helpers/state in __init__ after logger ----
$marker = "self.logger = setup_logger('task_monitor')"
$idx = $content.IndexOf($marker)
if ($idx -ge 0) {
    $insert = @(
        '        self.device_data_handler = DeviceDataHandler()',
        '        self._status_dialog = None',
        '        self._status_dialog_label = None',
        '        self._handshake_timer = None',
        '        self._handshake_deadline = None',
        '        self._handshake_context = None',
        '        self._completion_watchers = {}'
    ) -join "`r`n"
    $pos = $idx + $marker.Length
    # Only insert once
    if ($content.IndexOf('self.device_data_handler = DeviceDataHandler()') -lt 0) {
        $content = $content.Substring(0,$pos) + "`r`n" + $insert + "`r`n" + $content.Substring($pos)
    }
} else {
    throw "Could not find logger initialization marker in __init__."
}

# ---- 5) Replace start_selected_task() body with handshake flow ----
$startKey = 'def start_selected_task(self):'
$endKey = 'def complete_selected_task'
$startIdx = $content.IndexOf($startKey)
if ($startIdx -lt 0) { throw 'Could not locate start_selected_task().' }
$endIdx = $content.IndexOf($endKey, $startIdx)
if ($endIdx -lt 0) { throw 'Could not locate end marker (def complete_selected_task) after start_selected_task().' }

$newStart = @"
    def start_selected_task(self):
        """Start selected task with device handshake and popup flow."""
        if not self.selected_task:
            return

        device_ref = self.selected_task.get('assigned_device_id')
        if not device_ref:
            QMessageBox.warning(self, "No Device", "Assign a device to this task before starting.")
            return

        if not self.check_device_availability(device_ref):
            QMessageBox.warning(
                self,
                "Device Busy",
                "The device assigned to this task is currently running another task. "
                "Please wait for the device to complete its current task or assign a different device."
            )
            return

        self._show_status_popup("Please wait, we are checking robot's current status...")

        task_id_str = self.selected_task.get('task_id')
        try:
            self.device_data_handler.set_task_status_for_task(device_ref, task_id_str, 'run_task')
        except Exception as e:
            self.logger.error(f"Failed to write run_task command: {e}")

        self._handshake_context = {
            'task_pk': self.selected_task.get('id'),
            'task_id': task_id_str,
            'device_ref': device_ref,
        }
        self._handshake_deadline = datetime.now() + timedelta(seconds=30)
        if self._handshake_timer:
            try:
                self._handshake_timer.stop()
            except Exception:
                pass
        self._handshake_timer = QTimer(self)
        self._handshake_timer.setInterval(1000)
        self._handshake_timer.timeout.connect(self._poll_handshake_status)
        self._handshake_timer.start()
"@

$content = $content.Substring(0,$startIdx) + $newStart + "`r`n" + $content.Substring($endIdx)

# ---- 6) Insert helper methods before view_task_details() ----
$viewKey = 'def view_task_details(self):'
$viewIdx = $content.IndexOf($viewKey)
if ($viewIdx -lt 0) { throw 'Could not locate view_task_details() to insert helpers before.' }

$helpers = @"
    def _poll_handshake_status(self):
        try:
            ctx = self._handshake_context or {}
            if not ctx:
                return
            latest = self.device_data_handler.get_latest_task_status_for_task(ctx['device_ref'], ctx['task_id'])
            if str(latest).lower() == 'executing_task':
                self._update_status_popup("Executing the task...")
                self._close_status_popup()
                self._silent_update_task_status_by_row_id(ctx['task_pk'], 'running', 'started_at')
                if self._handshake_timer:
                    self._handshake_timer.stop()
                    self._handshake_timer = None
                self._start_completion_watcher(ctx['task_id'], ctx['device_ref'], ctx['task_pk'])
                return

            if str(latest).lower() == 'task_completed':
                self._close_status_popup()
                if self._handshake_timer:
                    self._handshake_timer.stop()
                    self._handshake_timer = None
                self._silent_update_task_status_by_row_id(ctx['task_pk'], 'completed', 'completed_at')
                return

            if datetime.now() > (self._handshake_deadline or datetime.now()):
                self._update_status_popup("Device did not acknowledge execution in time.")
                QTimer.singleShot(1500, self._close_status_popup)
                if self._handshake_timer:
                    self._handshake_timer.stop()
                    self._handshake_timer = None
        except Exception as e:
            self.logger.error(f"Handshake polling failed: {e}")
            try:
                self._close_status_popup()
            except Exception:
                pass
            if self._handshake_timer:
                self._handshake_timer.stop()
                self._handshake_timer = None

    def _start_completion_watcher(self, task_id: str, device_ref, task_pk):
        try:
            if task_id in self._completion_watchers:
                try:
                    self._completion_watchers[task_id].stop()
                except Exception:
                    pass
            timer = QTimer(self)
            timer.setInterval(1000)
            timer.timeout.connect(lambda tid=task_id, dev=device_ref, pk=task_pk: self._poll_completion_status(tid, dev, pk))
            self._completion_watchers[task_id] = timer
            timer.start()
        except Exception as e:
            self.logger.error(f"Failed to start completion watcher for {task_id}: {e}")

    def _poll_completion_status(self, task_id: str, device_ref, task_pk):
        try:
            latest = self.device_data_handler.get_latest_task_status_for_task(device_ref, task_id)
            if str(latest).lower() == 'task_completed':
                try:
                    t = self._completion_watchers.get(task_id)
                    if t:
                        t.stop()
                        del self._completion_watchers[task_id]
                except Exception:
                    pass
                self._silent_update_task_status_by_row_id(task_pk, 'completed', 'completed_at')
        except Exception as e:
            self.logger.error(f"Completion polling failed for {task_id}: {e}")

    def _show_status_popup(self, message: str):
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle("Task Status")
            dlg.setModal(False)
            layout = QVBoxLayout(dlg)
            lbl = QLabel(message)
            lbl.setStyleSheet("color: #ffffff;")
            prg = QProgressBar()
            prg.setRange(0, 0)
            layout.addWidget(lbl)
            layout.addWidget(prg)
            dlg.setStyleSheet("QDialog { background-color: #2b2b2b; }")
            dlg.setFixedSize(360, 120)
            self._status_dialog = dlg
            self._status_dialog_label = lbl
            dlg.show()
        except Exception as e:
            self.logger.error(f"Failed to show status popup: {e}")

    def _update_status_popup(self, message: str):
        try:
            if self._status_dialog_label:
                self._status_dialog_label.setText(message)
        except Exception:
            pass

    def _close_status_popup(self):
        try:
            if self._status_dialog:
                self._status_dialog.close()
        finally:
            self._status_dialog = None
            self._status_dialog_label = None

    def _silent_update_task_status_by_row_id(self, row_pk: str, new_status: str, timestamp_field: str = None):
        try:
            update_data = {'status': new_status}
            if timestamp_field:
                update_data[timestamp_field] = datetime.now().isoformat()
            if new_status == 'completed':
                try:
                    task = next((t for t in self.current_tasks if str(t.get('id')) == str(row_pk)), None)
                    if task and task.get('started_at'):
                        started_time = datetime.fromisoformat(task['started_at'].replace('Z', ''))
                        completed_time = datetime.now()
                        duration_minutes = int((completed_time - started_time).total_seconds() / 60)
                        update_data['actual_duration'] = duration_minutes
                except Exception as e:
                    self.logger.warning(f"Could not calculate duration silently: {e}")
            try:
                if self.api_client.is_authenticated():
                    if new_status == 'running':
                        self.tasks_api.start_task(row_pk)
                    elif new_status == 'completed':
                        self.tasks_api.complete_task(row_pk)
                    else:
                        self.tasks_api.update_task(row_pk, {'status': new_status})
            except Exception {
                # ignore API errors silently
            }
            if self.csv_handler.update_csv_row('tasks', row_pk, update_data):
                for i, t in enumerate(self.current_tasks):
                    if str(t.get('id')) == str(row_pk):
                        self.current_tasks[i].update(update_data)
                        break
                if self.selected_task and str(self.selected_task.get('id')) == str(row_pk):
                    self.selected_task.update(update_data)
                self.apply_filters()
                self.update_action_buttons()
        except Exception as e:
            self.logger.error(f"Silent status update failed for row {row_pk}: {e}")
"@

$content = $content.Insert($viewIdx, $helpers + "`r`n")

# Save
[System.IO.File]::WriteAllText($taskMon, $content, [System.Text.Encoding]::UTF8)
Write-Host "Patched task_monitor.py successfully. Backup at $backup"
