from pathlib import Path

root = Path(__file__).resolve().parents[1]
file_path = root / 'ui' / 'tasks' / 'task_monitor.py'
text = file_path.read_text(encoding='utf-8')

start_anchor = 'def check_device_availability(self, device_id):'
end_anchor = 'def view_task_details(self):'

start_idx = text.find(start_anchor)
end_idx = text.find(end_anchor)
if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
    raise SystemExit('Anchors not found or in wrong order')

new_block = '''def check_device_availability(self, device_id):
        """Check if a device is available (not running another task)"""
        if not device_id:
            return True
        tasks = self.csv_handler.read_csv('tasks')
        device_tasks = [t for t in tasks if (
            t.get('assigned_device_id') == str(device_id) and
            t.get('status', '').lower() == 'running'
        )]
        return len(device_tasks) == 0

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
        # Show popup while we request execution
        self._show_status_popup("Please wait, we are checking robot's current status...")
        # Write the 'run_task' command to <device_id>_task.csv for this task
        task_id_str = self.selected_task.get('task_id')
        try:
            self.device_data_handler.set_task_status_for_task(device_ref, task_id_str, 'run_task')
        except Exception as e:
            self.logger.error(f"Failed to write run_task command: {e}")
        # Start polling for 'executing_task'
        self._handshake_context = {
            'task_pk': self.selected_task.get('id'),
            'task_id': task_id_str,
            'device_ref': device_ref,
        }
        from datetime import datetime, timedelta
        self._handshake_deadline = datetime.now() + timedelta(seconds=30)
        if self._handshake_timer:
            try:
                self._handshake_timer.stop()
            except Exception:
                pass
        from PyQt5.QtCore import QTimer
        self._handshake_timer = QTimer(self)
        self._handshake_timer.setInterval(1000)
        self._handshake_timer.timeout.connect(self._poll_handshake_status)
        self._handshake_timer.start()

    def complete_selected_task(self):
        """Complete selected task"""
        if not self.selected_task:
            return
        task_name = self.selected_task.get('task_name', 'Unknown')
        reply = QMessageBox.question(
            self, "Complete Task",
            f"Mark task '{task_name}' as completed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.change_task_status('completed', 'completed_at')

    def cancel_selected_task(self):
        """Cancel selected task"""
        if not self.selected_task:
            return
        task_name = self.selected_task.get('task_name', 'Unknown')
        reply = QMessageBox.question(
            self, "Cancel Task",
            f"Cancel task '{task_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.change_task_status('cancelled')

    def change_task_status(self, new_status, timestamp_field=None):
        """Change task status in CSV"""
        try:
            task_id = self.selected_task.get('id')
            # First try API if available
            if self.api_client.is_authenticated():
                if new_status == 'running':
                    response = self.tasks_api.start_task(task_id)
                elif new_status == 'completed':
                    response = self.tasks_api.complete_task(task_id)
                else:
                    # For cancel or other status changes, update directly
                    response = self.tasks_api.update_task(task_id, {'status': new_status})
                if 'error' not in response:
                    QMessageBox.information(self, "Success", f"Task {new_status} successfully!")
                    self.refresh_data()
                    return
                else:
                    self.logger.warning(f"API call failed: {response['error']}, falling back to CSV")
            # Fallback to CSV update
            update_data = {'status': new_status}
            # Add timestamp if specified
            if timestamp_field:
                from datetime import datetime
                update_data[timestamp_field] = datetime.now().isoformat()
            # If completing a task, calculate actual duration
            if new_status == 'completed' and self.selected_task.get('started_at'):
                try:
                    from datetime import datetime
                    started_time = datetime.fromisoformat(self.selected_task['started_at'].replace('Z', ''))
                    completed_time = datetime.now()
                    duration_minutes = int((completed_time - started_time).total_seconds() / 60)
                    update_data['actual_duration'] = duration_minutes
                except Exception as e:
                    self.logger.warning(f"Could not calculate duration: {e}")
            if self.csv_handler.update_csv_row('tasks', task_id, update_data):
                QMessageBox.information(self, "Success", f"Task {new_status} successfully!")
                # Update the current task data
                self.selected_task.update(update_data)
                self.current_tasks[self.selected_task_index].update(update_data)
                # Refresh the display
                self.apply_filters()
                self.show_task_details(self.selected_task)
                self.update_action_buttons()
            else:
                raise Exception("Failed to update CSV")
        except Exception as e:
            self.logger.error(f"Error changing task status: {e}")
            QMessageBox.critical(self, "Error", f"Failed to change task status: {e}")

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
            from datetime import datetime
            if datetime.now() > (self._handshake_deadline or datetime.now()):
                self._update_status_popup("Device did not acknowledge execution in time.")
                from PyQt5.QtCore import QTimer
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
            from PyQt5.QtCore import QTimer
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
            from PyQt5.QtWidgets import QVBoxLayout
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
                from datetime import datetime
                update_data[timestamp_field] = datetime.now().isoformat()
            if new_status == 'completed':
                try:
                    from datetime import datetime
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
            except Exception:
                pass
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
'''

# Ensure correct indentation for class scope: prepend 4 spaces to each line
indented_block = '\n'.join('    ' + line if line.strip() else '' for line in new_block.splitlines()) + '\n'

new_text = text[:start_idx] + indented_block + text[end_idx:]

# Write backup and new content
backup = file_path.with_suffix('.py.rewrite_bak')
backup.write_text(text, encoding='utf-8')
file_path.write_text(new_text, encoding='utf-8')
print('Rewrote methods block in task_monitor.py; backup at', backup)
