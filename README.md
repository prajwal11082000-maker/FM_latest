# Warehouse Management System — Comprehensive Project Report
## 1. Project Overview
### 1.1 Introduction and Purpose

The Warehouse Management System (WMS) is a desktop-first application built using Python (PyQt5) that enables management of devices (robots), maps, zones, racks, SKU locations, products, users, and tasks.
It is designed for offline-first operation using CSV files while offering hybrid synchronization through optional REST API integration.

### 1.2 Problem Statement

Maintain an inventory of devices, products, and users.

Design and manage warehouse maps, zones, stops, and racks.

Create and monitor robot-executed tasks.

Track robot movements and plan optimal routes — without relying on a heavy backend.


### 1.3 Objectives

Provide robust offline functionality via CSVs with automatic repair and migration.

Deliver clean and modular UI for devices, tasks, maps, racks, and SKU locations.

Enable live device tracking using per-device log CSVs.

Support path planning and command generation for robots.

Allow optional API synchronization with remote servers for hybrid operation.


## 2. Technologies, Frameworks, and Tools Used

### Category	Tools/Frameworks
Language	Python

UI Framework	PyQt5

Data Management	pandas

HTTP Client	requests

Utilities	python-dateutil, Pillow, matplotlib, numpy



## 3. System Architecture / Project Structure
### 3.1 Top-Level Structure


main.py — Application entry point. Initializes UI, logger, theme, timers, and CSV structure.

api/ — REST wrappers (client.py, auth.py, devices.py, tasks.py, etc.).

config/ — Global settings and constants.

data/ — Contains CSV files, backups, logs, and navigation states.

data_manager/ — Core CSV and synchronization handlers.

robot_navigation/ — A* pathfinding and robot navigation logic.

services/ — Background sync and path planner services.

ui/ — PyQt5 interface pages and widgets.

utils/ — Logger, helpers, validators, navigation utilities.

scripts/ — One-off maintenance and patch scripts.

resources/ — Icons, themes, and stylesheets.

## 4. Roles of Key Components
### Layer	Module	Description

#### UI Layer	

ui/main_window.py	Controls all pages through a sidebar and stacked widgets.

#### Data Layer	

CSVHandler, DeviceDataHandler, SyncManager:	Ensures reliable CSV handling, logging, and synchronization.

#### Robotics Layer	

astar_planner.py, path_planner_service.py:	Generates robot movement paths and commands.

#### Automation Layer	

sync_service.py:	Automates device-location updates and periodic syncs.

#### API Layer	

api/client.py:	Provides hybrid REST API integration.


## 5. Configuration and Environment Setup
Steps:

Install dependencies

pip install -r requirements.txt


Optional API setup:
Update API_BASE_URL in config/settings.py if backend sync is required.

Launch the application

python main.py


Data initialization:
The app automatically creates data directories and CSV files on first run.

## 6. Features and Functionalities
### 6.1 Dashboard

Central overview of system status and activity summaries.

### 6.2 Device Management

Add, edit, or delete device entries.

Live facing direction and current location derived from per-device logs.

Reset device state and export telemetry data.

### 6.3 Task Management

Create tasks (Picking, Storing, Auditing) with validation.

Track status lifecycle (Created → Started → Completed → Canceled).

Device handshake mechanism using <device_id>_task.csv.

Generate robot paths using A* planner.

### 6.4 Map Management

Manage maps, zones, and stops.

Configure racks and SKU locations.

Interactive visualization of warehouse zones.

### 6.5 User and Product Management

CRUD operations for users and products.

Filter by status or creation date.

View aggregated product quantities from SKUs.

### 6.6 Device Tracking

Real-time visualization of device position and facing direction.

Integrates seamlessly with logs and map viewer.

### 6.7 Offline-First with Hybrid Option

Operates fully offline with CSVs.

Automatically switches to REST API if available.

### 6.8 Automation and Utilities

sync_device_locations.py — Updates device CSVs from latest log data.

services/sync_service.py — Scheduled synchronization.

scripts/* — Maintenance utilities for normalization or fixes.

## 7. Database and Data Files
### Primary Data (CSV Files in data/):

devices.csv — Device registry.

tasks.csv — Task lifecycle data.

users.csv — User directory.

maps.csv — Map metadata.

zones.csv — Zone connections.

stops.csv — Stop definitions.

racks.csv — Rack information.

sku_location.csv — SKU slot data.

products.csv — Product registry.

### Per-Device Logs (data/device_logs/):

<device_id>.csv — Live telemetry.

<device_id>_task.csv — Task execution handshake.

path_{device_id}.csv — Command sequence for robot.

### Other Files

zone_navigation.json — Cached navigation state.

backup/ — Timestamped CSV backups.

logs/ — Application logs.

## 8. Project Workflow

### Startup

Initialize app, logger, and theme.

Validate and create all CSV headers via CSVHandler.

Load MainWindow with sidebar and pages.

### UI Navigation

Sidebar triggers stacked widget page changes.

Each page loads and refreshes its respective data.

### Device-Task Interaction

Task creation writes to tasks.csv.

“Start Task” triggers a handshake via <device_id>_task.csv.

Robot executes and updates task state via logs.

### Path Planning

path_planner_service computes optimal route using A*.

Saves executable path as CSV commands.

### Synchronization

Periodic background job updates devices.csv from device logs.

Optionally syncs with API when available.

## 9. Testing and Validation
Built-in Validations

Header verification and schema migration.

ID assignment and timestamping.

Automatic backup before every write.

Add unit tests for data handlers and path planner.

Implement integration tests for log synchronization.

Introduce API contract tests for hybrid endpoints.

## 10. Observability

Application logs written to logs/warehouse_app_YYYYMMDD.log.

Status bar shows current mode (CSV/Hybrid) and sync state.

Backup mechanism ensures safe CSV recovery.

## 11. Conclusion

Complete offline-first WMS with an elegant PyQt5 interface.

Fully functional device tracking, path planning, and task monitoring.

Automatic CSV repair and backup ensuring data safety.

Hybrid design allowing seamless API integration.

CSV header mismatch	Implemented header verification and migration logic.

Reliable task-device handshake	Created per-device task CSV and polling mechanism.

Synchronization consistency	Built SyncService with backup and recovery system.

### Future Enhancements

Move to SQLite/PostgreSQL with ORM-based backend.

Replace polling with event-driven updates (WebSockets).

Expand unit and integration tests.

Package as standalone desktop executable (PyInstaller).

Extend API schemas for scalability.
