
# Standalone verification of the filtering logic implemented in DeviceFilter
import re

def parse_battery(battery_value) -> int:
    try:
        if battery_value is None:
            return 0
        battery_str = str(battery_value).strip()
        if not battery_str:
            return 0
        return int(float(battery_str))
    except (ValueError, TypeError):
        return 0

def filter_devices_logic(devices, tasks, task_type, map_id=None):
    candidates = []
    seen_ids = set()
    
    # Pre-read tasks for busy check
    running_tasks = [t for t in tasks if t.get('status', '').lower() == 'running']
    
    for device in devices:
        device_id = device.get('id')
        if not device_id or str(device_id) in seen_ids:
            continue
        seen_ids.add(str(device_id))
        
        # Parse device properties
        battery = parse_battery(device.get('battery_level', '0'))
        status = (device.get('status', '') or '').strip().lower()
        device_map = str(device.get('current_map', ''))

        # Strict Map Filtering
        if map_id and device_map != str(map_id):
            continue
        
        # Check basic selectability
        if task_type == 'charging':
            battery_eligible = battery < 20
            status_eligible = status != 'charging'
            
            # Check if device is already running a task
            device_id_str = str(device.get('id'))
            is_busy = False
            for t in running_tasks:
                sid = str(t.get('assigned_device_id') or '').strip()
                mids = [s.strip() for s in str(t.get('assigned_device_ids') or '').split(',') if s.strip()]
                if sid == device_id_str or device_id_str in mids:
                    is_busy = True
                    break
            
            basic_selectable = battery_eligible and status_eligible and not is_busy
        else:
            basic_selectable = battery > 20 and status in ['working', 'charging']
        
        selectable = basic_selectable
        
        candidates.append({
            'device_id': device.get('device_id'),
            'battery': battery,
            'selectable': selectable,
            'status': status,
            'is_busy': is_busy if task_type == 'charging' else False
        })
    
    # Sort by battery descending, then by selectability
    candidates.sort(key=lambda x: (0 if x['selectable'] else 1, -x['battery']))
    return candidates

def test():
    print("Verifying Standalone Filtering Logic...")
    
    devices = [
        {'id': '1', 'device_id': 'rob1', 'device_name': 'Robot 1', 'current_map': '1', 'battery_level': '25', 'status': 'working'},
        {'id': '2', 'device_id': 'rob2', 'device_name': 'Robot 2', 'current_map': '1', 'battery_level': '15', 'status': 'working'},
        {'id': '3', 'device_id': 'rob3', 'device_name': 'Robot 3', 'current_map': '2', 'battery_level': '10', 'status': 'working'},
        {'id': '4', 'device_id': 'rob4', 'device_name': 'Robot 4', 'current_map': '1', 'battery_level': '10', 'status': 'charging'},
        {'id': '5', 'device_id': 'rob5', 'device_name': 'Robot 5', 'current_map': '1', 'battery_level': '5', 'status': 'working'},
    ]
    
    tasks = [
        {'id': '101', 'status': 'running', 'assigned_device_id': '5'}
    ]
    
    print("\nScenario 1: Map 1, Task Type 'charging'")
    candidates = filter_devices_logic(devices, tasks, 'charging', map_id='1')
    
    # Expected: 
    # rob2: Selectable (15% < 20%, same map, not busy, not charging)
    # rob1: Not selectable (25% >= 20%)
    # rob4: Not selectable (Already charging)
    # rob5: Not selectable (Busy in task 101)
    # rob3: Missing (Different map)
    
    expected = {
        'rob2': True,
        'rob1': False,
        'rob4': False,
        'rob5': False
    }
    
    print("Found Candidates:", [c['device_id'] for c in candidates])
    
    for c in candidates:
        did = c['device_id']
        sel = c['selectable']
        if did in expected:
            if sel == expected[did]:
                print(f"PASS: {did} selectable={sel}")
            else:
                print(f"FAIL: {did} selectable={sel} (expected {expected[did]})")
        else:
            print(f"FAIL: {did} should not be in results for Map 1")

    # Check rob3 exclusion
    if any(c['device_id'] == 'rob3' for c in candidates):
        print("FAIL: rob3 (Map 2) was not filtered out")
    else:
        print("PASS: rob3 (Map 2) was correctly filtered out")

    # Check sorting
    if candidates and candidates[0]['device_id'] == 'rob2':
        print("PASS: rob2 is the first candidate (selectable)")
    else:
        print("FAIL: rob2 is not the first candidate")

    print("\nScenario 2: Map 2, Task Type 'charging'")
    candidates_map2 = filter_devices_logic(devices, tasks, 'charging', map_id='2')
    # Expected only rob3: Selectable (10% < 20%, map 2, not busy, not charging)
    if len(candidates_map2) == 1 and candidates_map2[0]['device_id'] == 'rob3' and candidates_map2[0]['selectable']:
        print("PASS: Map 2 filtered correctly for rob3")
    else:
        print(f"FAIL: Map 2 filtering error. Got: {[c['device_id'] for c in candidates_map2]}")

if __name__ == "__main__":
    test()
