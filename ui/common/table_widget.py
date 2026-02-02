from PyQt5.QtWidgets import (QTableWidget, QTableWidgetItem, QHeaderView,
                             QVBoxLayout, QWidget, QHBoxLayout, QPushButton,
                             QLineEdit, QLabel, QAbstractItemView, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class DataTableWidget(QWidget):
    # Signals
    row_selected = pyqtSignal(int)
    row_double_clicked = pyqtSignal(int)

    def __init__(self, headers, searchable=True, selectable=True):
        super().__init__()
        self.headers = headers
        self.searchable = searchable
        self.selectable = selectable
        self.all_data = []  # Store all data for searching

        self.setup_ui()
        self.setup_table()

    def setup_ui(self):
        """Setup table widget UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # Set size policy to expand both horizontally and vertically
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Search bar (if enabled)
        if self.searchable:
            search_layout = QHBoxLayout()

            search_label = QLabel("Search:")
            search_label.setStyleSheet("color: #cccccc;")
            search_layout.addWidget(search_label)

            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("Type to search...")
            self.search_input.textChanged.connect(self.filter_table)
            self.search_input.setStyleSheet("""
                QLineEdit {
                    background-color: #404040;
                    border: 1px solid #555555;
                    padding: 6px;
                    border-radius: 4px;
                    color: #ffffff;
                }
            """)
            search_layout.addWidget(self.search_input)

            # Clear search button
            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(self.clear_search)
            clear_btn.setMaximumWidth(60)
            clear_btn.setStyleSheet("""
                QPushButton {
                    background-color: #555555;
                    border: 1px solid #666666;
                    padding: 6px;
                    border-radius: 4px;
                    color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
            """)
            search_layout.addWidget(clear_btn)

            layout.addLayout(search_layout)

        # Table with better sizing and scroll bar support
        self.table = QTableWidget()
        # Set size policy to expand both horizontally and vertically
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumHeight(200)  # Minimum height to prevent clipping
        
        # Ensure vertical scroll bar is always visible for easier navigation
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Set the table to take up all available space
        layout.addWidget(self.table, 1)  # Add stretch factor of 1

    def setup_table(self):
        """Setup table properties"""
        # Set headers
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)

        # Table styling
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #404040;
                alternate-background-color: #454545;
                gridline-color: #555555;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #ff6b35;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                padding: 12px 8px;
                border: 1px solid #666666;
                font-weight: bold;
                font-size: 12px;
                color: #ff6b35;
                margin: 1px;
                border-radius: 3px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QScrollBar:vertical {
                background-color: #404040;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #ff6b35;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #e55a2b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Table properties
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        
        # Explicitly set header visibility
        self.table.horizontalHeader().setVisible(True)
        # Add explicit styling to force header visibility
        self.table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #2a2a2a;
                padding: 12px 8px;
                border: 1px solid #666666;
                font-weight: bold;
                font-size: 12px;
                color: #ff6b35;
                margin: 1px;
                border-radius: 3px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                height: 25px;
                min-height: 25px;
            }
        """)

        if not self.selectable:
            self.table.setSelectionMode(QAbstractItemView.NoSelection)

        # Auto-resize columns with intelligent sizing
        header = self.table.horizontalHeader()
        
        # Set minimum section sizes to prevent squishing
        header.setMinimumSectionSize(100)
        header.setDefaultSectionSize(150)
        
        # Set minimum header height for better visibility
        header.setMinimumHeight(80)
        
        # Initially set all columns to Interactive mode for proper sizing
        header.setSectionResizeMode(QHeaderView.Interactive)
        
        # Enable column resizing by user
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        
        # Set specific column widths based on typical content
        self.setup_column_widths()
        
        # Make table horizontally scrollable and keep vertical scroll bar visible
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Apply stretch to last column only if we have enough space
        if len(self.headers) > 0:
            # Use ResizeToContents for better auto-sizing, fallback to stretch if needed
            for i in range(len(self.headers)):
                if i == len(self.headers) - 1:  # Last column
                    header.setSectionResizeMode(i, QHeaderView.Stretch)
                else:
                    header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        # Connect signals
        if self.selectable:
            self.table.cellClicked.connect(self.on_cell_clicked)
            self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

    def add_row(self, row_data):
        """Add a single row to the table"""
        self.all_data.append(row_data)
        self._add_row_to_table(row_data)

    def _add_row_to_table(self, row_data):
        """Internal method to add row to table widget"""
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        for col, data in enumerate(row_data):
            item = QTableWidgetItem(str(data))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make read-only

            # Color coding for status columns
            if col < len(self.headers):
                header = self.headers[col].lower()
                if 'status' in header:
                    self._apply_status_color(item, str(data).lower())
                elif 'priority' in header:
                    self._apply_priority_color(item, str(data).lower())

            self.table.setItem(row_position, col, item)

    def _apply_status_color(self, item, status):
        """Apply color coding based on status"""
        color_map = {
            'working': '#10B981',
            'running': '#10B981',
            'completed': '#8B5CF6',
            'charging': '#F59E0B',
            'pending': '#3B82F6',
            'failed': '#EF4444',
            'issues': '#EF4444',
            'cancelled': '#6B7280',
            'maintenance': '#F59E0B'
        }

        color = color_map.get(status, '#ffffff')
        item.setForeground(Qt.white)
        item.setBackground(Qt.transparent)
        item.setData(Qt.UserRole, color)  # Store color for later use

    def _apply_priority_color(self, item, priority):
        """Apply color coding based on priority"""
        color_map = {
            'urgent': '#EF4444',
            'high': '#F59E0B',
            'medium': '#3B82F6',
            'low': '#6B7280'
        }

        color = color_map.get(priority, '#ffffff')
        item.setForeground(Qt.white)
        item.setBackground(Qt.transparent)
        item.setData(Qt.UserRole, color)

    def clear_data(self):
        """Clear all table data"""
        self.all_data.clear()
        self.table.setRowCount(0)
        # Ensure header remains visible
        self.table.horizontalHeader().setVisible(True)
        # Reset column widths when clearing data
        self.setup_column_widths()

    def filter_table(self, search_text):
        """Filter table based on search text"""
        if not self.searchable:
            return

        self.table.setRowCount(0)

        if not search_text:
            # Show all data
            for row_data in self.all_data:
                self._add_row_to_table(row_data)
        else:
            # Filter data
            search_text = search_text.lower()
            for row_data in self.all_data:
                if any(search_text in str(cell).lower() for cell in row_data):
                    self._add_row_to_table(row_data)
        
        # Ensure header remains visible after filtering
        self.table.horizontalHeader().setVisible(True)
        
        # Optimize column widths after filtering
        if self.table.rowCount() > 0:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(50, self.optimize_column_widths)

    def clear_search(self):
        """Clear search and show all data"""
        if self.searchable and hasattr(self, 'search_input'):
            self.search_input.clear()

    def on_cell_clicked(self, row, column):
        """Handle cell click"""
        self.row_selected.emit(row)

    def on_cell_double_clicked(self, row, column):
        """Handle cell double click"""
        self.row_double_clicked.emit(row)

    def get_selected_row_data(self):
        """Get data from selected row"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(current_row, col)
                row_data.append(item.text() if item else "")
            return row_data
        return None

    def set_data(self, data_list):
        """Set all table data at once with enhanced scroll bar support"""
        self.clear_data()
        for row_data in data_list:
            self.add_row(row_data)
        
        # Ensure header visibility is maintained
        self.table.horizontalHeader().setVisible(True)
        
        # Force scroll bar visibility and proper configuration
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Optimize column widths after all data is loaded
        if data_list:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(50, self.optimize_column_widths)
            # Ensure scroll bars are properly configured after data is loaded
            QTimer.singleShot(100, self.ensure_scroll_bars)
            # Force scroll bar update after a short delay
            QTimer.singleShot(150, self.force_scroll_bar_update)
        else:
            # Even with no data, ensure scroll bars are configured
            self.ensure_scroll_bars()
            self.force_scroll_bar_update()

    def get_row_count(self):
        """Get number of rows"""
        return self.table.rowCount()

    def sort_by_column(self, column, ascending=True):
        """Sort table by specific column"""
        order = Qt.AscendingOrder if ascending else Qt.DescendingOrder
        self.table.sortItems(column, order)
    
    def setup_column_widths(self):
        """Set intelligent column widths based on content and header text"""
        header = self.table.horizontalHeader()
        
        for i, header_text in enumerate(self.headers):
            # Set widths based on common column patterns
            width = self.get_optimal_width(header_text.lower())
            if width:
                header.resizeSection(i, width)
    
    def get_optimal_width(self, header_text):
        """Get optimal width for column based on header text"""
        # Define optimal widths for different column types - increased values
        width_map = {
            'id': 100,
            'stop id': 140,
            'name': 200,
            'zone': 220,
            'position': 130,
            'position (x,y)': 130,

            'bins': 100,
            'bins (l/r)': 120,
            'rack levels': 110,
            'rack distances': 180,
            'total height': 120,
            'created': 120,
            'status': 120,
            'priority': 110,
            'from zone': 140,
            'to zone': 140,
            'distance': 110,
            'type': 120,
            'description': 280,
            'coordinates': 140,
            'vehicle': 120,
        }
        
        # Look for exact matches first
        if header_text in width_map:
            return width_map[header_text]
        
        # Look for partial matches
        for pattern, width in width_map.items():
            if pattern in header_text:
                return width
        
        # Default width for unknown columns - increased from 120
        return 150
    
    def optimize_column_widths(self):
        """Optimize column widths after data is loaded"""
        if self.table.rowCount() == 0:
            self.setup_column_widths()  # Set default widths even without data
            return
        
        header = self.table.horizontalHeader()
        
        # Store current resize modes
        original_modes = []
        for i in range(len(self.headers)):
            original_modes.append(header.sectionResizeMode(i))
        
        # First, apply optimal widths from our predefined map
        for i, header_text in enumerate(self.headers):
            optimal_width = self.get_optimal_width(header_text.lower())
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            header.resizeSection(i, optimal_width)
        
        # Then temporarily set to ResizeToContents to measure content
        for i in range(len(self.headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        # Let Qt calculate optimal widths based on content
        self.table.resizeColumnsToContents()
        
        # Apply intelligent constraints based on content and header
        for i in range(len(self.headers)):
            content_width = header.sectionSize(i)
            optimal_width = self.get_optimal_width(self.headers[i].lower())
            
            # Use the larger of content width or optimal width, with constraints
            min_width = 100  # Increased minimum
            max_width = 350  # Increased maximum
            
            # Adjust based on column type with better constraints
            header_text = self.headers[i].lower()
            if 'id' in header_text and len(header_text) <= 10:
                min_width = 80
                max_width = 150
            elif 'name' in header_text or 'description' in header_text:
                min_width = 150
                max_width = 300
            elif 'zone' in header_text:
                min_width = 120
                max_width = 250
            elif 'position' in header_text or 'coordinate' in header_text:
                min_width = 120
                max_width = 180
            elif 'distance' in header_text or 'height' in header_text:
                min_width = 100
                max_width = 200
            elif 'bins' in header_text or 'level' in header_text:
                min_width = 80
                max_width = 120
            
            # Choose the best width: preference for optimal, but accommodate content
            final_width = max(min_width, min(max(content_width, optimal_width), max_width))
            
            # Set back to interactive and apply final width
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            header.resizeSection(i, final_width)
        
        # Set last column to stretch after all widths are set
        if len(self.headers) > 0:
            header.setSectionResizeMode(len(self.headers) - 1, QHeaderView.Stretch)
        
        # Ensure scroll bars are properly configured after data is loaded
        self.ensure_scroll_bars()
    
    def ensure_scroll_bars(self):
        """Ensure scroll bars are properly configured for the table"""
        # Force update of scroll bar policies
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Force the table to recalculate its size and show scroll bars if needed
        self.table.updateGeometry()
        self.table.update()
        
        # Force a layout update to ensure scroll bars appear
        self.table.viewport().update()
    
    def force_scroll_bar_update(self):
        """Force scroll bar visibility and styling update"""
        # Ensure vertical scroll bar is always visible
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # Force scroll bar to be visible even with no content
        vertical_scroll_bar = self.table.verticalScrollBar()
        if vertical_scroll_bar:
            vertical_scroll_bar.setVisible(True)
            vertical_scroll_bar.update()
        
        # Update table geometry to accommodate scroll bars
        self.table.updateGeometry()
        self.table.repaint()
        
        # Force parent widget updates
        if self.parent():
            self.parent().updateGeometry()
            self.parent().update()
