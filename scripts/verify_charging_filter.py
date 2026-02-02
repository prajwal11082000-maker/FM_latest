import sys
import os
import types
from unittest.mock import MagicMock

# Robust PyQt5 mocking
def mock_qt():
    pyqt5 = types.ModuleType("PyQt5")
    sys.modules["PyQt5"] = pyqt5
    
    qtcore = types.ModuleType("PyQt5.QtCore")
    sys.modules["PyQt5.QtCore"] = qtcore
    pyqt5.QtCore = qtcore
    qtcore.Qt = MagicMock()
    
    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    sys.modules["PyQt5.QtWidgets"] = qtwidgets
    pyqt5.QtWidgets = qtwidgets
    qtwidgets.QListWidgetItem = MagicMock()

mock_qt()

# Add current directory to path
sys.path.append(os.getcwd())

from ui.tasks.device_filter import DeviceFilter

def test_charging_filter():
    print("Running Charging Filter Verification (Robust Mocks)...")
    
    # Mock CSVHandler
    mock_csv_handler = MagicMock()
    
    # Mock devices data
    devices = [
        {'id': '1', 'device_id': 'rob1', 'device_name': 'Robot 1', 'current_map': '1', 'battery_level': '25', 'status': 'working'},
        {'id': '2', 'device_id': 'rob2', 'device_name': 'Robot 2', 'current_map': '1', 'battery_level': '15', 'status': 'working'},
        {'id': '3', 'device_id': 'rob3', 'device_name': 'Robot 3', 'current_map': '2', 'battery_level': '10', 'status': 'working'},
        {'id': '4', 'device_id': 'rob4', 'device_name': 'Robot 4', 'current_map': '1', 'battery_level': '10', 'status': 'charging'},
        {'id': '5', 'device_id': 'rob5', 'device_name': 'Robot 5', 'current_map': '1', 'battery_level': '5', 'status': 'working'},
    ]
    
    # Mock tasks data for busy check
    tasks = [
        {'id': '101', 'status': 'running', 'assigned_device_id': '5'}
    ]
    
    def mock_read_csv(file_type):
        if file_type == 'devices':
            return devices
        if file_type == 'tasks':
            return tasks
        return []
    
    mock_csv_handler.read_csv.side_effect = mock_read_csv
    
    mock_distance_calculator = MagicMock()
    device_filter = DeviceFilter(mock_csv_handler, mock_distance_calculator)
    
    print("\nScenario: Map 1, Charging Task")
    candidates = device_filter.filter_devices(task_type='charging', map_id='1')
    
    expected_results = {
        'rob1': {'selectable': False},
        'rob2': {'selectable': True},
        'rob4': {'selectable': False},
        'rob5': {'selectable': False}
    }
    
    # rob3 should be filtered out entirely because of map_id
    rob3_found = any(c['device']['device_id'] == 'rob3' for c in candidates)
    if rob3_found:
        print("FAIL: rob3 (Map 2) should have been filtered out for Map 1.")
    else:
        print("PASS: rob3 (Map 2) filtered out correctly.")
        
    found_dids = [c['device']['device_id'] for c in candidates]
    print(f"Candidates found: {found_dids}")

    for c in candidates:
        did = c['device']['device_id']
        selectable = c['selectable']
        battery = c['battery']
        status = c['status']
        is_busy = c.get('is_busy', False)
        
        print(f"Device: {did}, Battery: {battery}%, Status: {status}, Busy: {is_busy} -> Selectable: {selectable}")
        
        if did in expected_results:
            if selectable != expected_results[did]['selectable']:
                print(f"FAIL: {did} selectability mismatch. Expected {expected_results[did]['selectable']}, got {selectable}")
            else:
                print(f"PASS: {did} selectability verified.")

    # Sort check: rob2 should be first as it is the only selectable one in Map 1
    if candidates and candidates[0]['device']['device_id'] == 'rob2':
        print("PASS: rob2 is correctly ranked first.")
    else:
        print("FAIL: rob2 is NOT ranked first.")

if __name__ == "__main__":
    try:
        test_charging_filter()
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
