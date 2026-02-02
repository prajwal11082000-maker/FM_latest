from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath, QFont

class RobotSprite:
    def __init__(self, position: QPointF, size: float = 8.0, direction: str = 'north', label: str = ''):
        self.position = position
        self.starting_position = position  # Store initial position
        self.size = 30.0  # Increased size for better visibility
        self.color = QColor('#00FF00')  # Bright green color
        self.outline_color = QColor('#FFFFFF')  # White outline for contrast
        self.highlight_color = QColor('#FFD700')  # Gold color for highlights
        self.starting_zone = None  # Store starting zone name
        self.starting_coordinates = None  # Store exact starting coordinates
        self.direction = direction.lower()  # Direction the robot is facing (north, south, east, west)
        # Track last valid cardinal direction to avoid accidental resets on zone transitions
        self.last_valid_direction = self.direction if self.direction in ['north', 'south', 'east', 'west'] else 'north'
        # Optional label (e.g., device_id) to render near the sprite
        self.label = label or ''
        
        # Direction locking state
        self.is_direction_locked = False  # Whether direction is locked due to turn detection
        self.locked_direction = None  # The locked direction
        self.locked_by_turn_type = None  # Type of turn that locked the direction ('left', 'right')
        self.lock_timestamp = None  # When the direction was locked
        
        # Locked state visual properties
        self.locked_color = QColor('#FF4500')  # Orange-red for locked state
        self.locked_highlight_color = QColor('#FF69B4')  # Hot pink for locked triangle
        self.locked_outline_color = QColor('#FFD700')  # Gold outline when locked
    
    def draw(self, painter: QPainter):
        """Draw a highly visible robot marker with direction indicator"""
        painter.save()
        
        # CRITICAL: Validate and enforce lock state before drawing
        if not self.validate_lock_state():
            print(f"DEBUG - 🔧 LOCK STATE CORRECTED during draw")
        
        # Determine colors based on lock state
        if self.is_direction_locked:
            main_color = self.locked_color
            outline_color = self.locked_outline_color
            triangle_color = self.locked_highlight_color
        else:
            main_color = self.color
            outline_color = self.outline_color
            triangle_color = self.highlight_color
        
        # Draw outer glow effect (enhanced for locked state)
        glow_color = QColor(main_color)
        glow_color.setAlpha(60 if self.is_direction_locked else 50)  # More intense glow when locked
        glow_width = 8 if self.is_direction_locked else 6  # Wider glow when locked
        painter.setPen(QPen(glow_color, glow_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(
            self.position,
            self.size/2 + 4,  # Larger size for glow
            self.size/2 + 4
        )
        
        # Draw additional lock indicator ring
        if self.is_direction_locked:
            lock_ring_color = QColor('#FFD700')  # Gold ring for locked state
            lock_ring_color.setAlpha(120)
            painter.setPen(QPen(lock_ring_color, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                self.position,
                self.size/2 + 2,
                self.size/2 + 2
            )
        
        # Draw white outline for visibility
        painter.setPen(QPen(outline_color, 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(
            self.position,
            self.size/2,
            self.size/2
        )
        
        # Draw main robot body
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(main_color))
        painter.drawEllipse(
            self.position,
            self.size/2 - 2,  # Slightly smaller for outline effect
            self.size/2 - 2
        )
        
        # Draw direction indicator (a small triangle)
        triangle_path = QPainterPath()
        triangle_size = self.size/3
        
        # Calculate triangle points based on direction
        center_x = self.position.x()
        center_y = self.position.y()
        
        # Resolve drawing direction with robust fallback to locked or last valid direction
        draw_direction = self.direction
        if draw_direction not in ['north', 'south', 'east', 'west']:
            if self.is_direction_locked and (self.locked_direction in ['north', 'south', 'east', 'west']):
                draw_direction = self.locked_direction
            elif self.last_valid_direction in ['north', 'south', 'east', 'west']:
                draw_direction = self.last_valid_direction
            else:
                draw_direction = 'north'  # ultimate fallback only
        
        if draw_direction == 'north':
            # Triangle pointing up (north)
            triangle_path.moveTo(center_x, center_y - self.size/2)  # Top point
            triangle_path.lineTo(center_x - triangle_size/2, center_y - self.size/2 + triangle_size)  # Bottom left
            triangle_path.lineTo(center_x + triangle_size/2, center_y - self.size/2 + triangle_size)  # Bottom right
        elif draw_direction == 'south':
            # Triangle pointing down (south)
            triangle_path.moveTo(center_x, center_y + self.size/2)  # Bottom point
            triangle_path.lineTo(center_x - triangle_size/2, center_y + self.size/2 - triangle_size)  # Top left
            triangle_path.lineTo(center_x + triangle_size/2, center_y + self.size/2 - triangle_size)  # Top right
        elif draw_direction == 'east':
            # Triangle pointing right (east)
            triangle_path.moveTo(center_x + self.size/2, center_y)  # Right point
            triangle_path.lineTo(center_x + self.size/2 - triangle_size, center_y - triangle_size/2)  # Top left
            triangle_path.lineTo(center_x + self.size/2 - triangle_size, center_y + triangle_size/2)  # Bottom left
        elif draw_direction == 'west':
            # Triangle pointing left (west)
            triangle_path.moveTo(center_x - self.size/2, center_y)  # Left point
            triangle_path.lineTo(center_x - self.size/2 + triangle_size, center_y - triangle_size/2)  # Top right
            triangle_path.lineTo(center_x - self.size/2 + triangle_size, center_y + triangle_size/2)  # Bottom right
        else:
            # Default to north if direction is unknown
            triangle_path.moveTo(center_x, center_y - self.size/2)  # Top point
            triangle_path.lineTo(center_x - triangle_size/2, center_y - self.size/2 + triangle_size)  # Bottom left
            triangle_path.lineTo(center_x + triangle_size/2, center_y - self.size/2 + triangle_size)  # Bottom right
        
        triangle_path.closeSubpath()
        
        # Draw triangle with dynamic color based on lock state
        painter.setBrush(QBrush(triangle_color))
        painter.setPen(QPen(outline_color, 1))
        painter.drawPath(triangle_path)
        
        # Draw center dot with dynamic colors
        painter.setPen(QPen(outline_color, 2))
        painter.setBrush(QBrush(triangle_color))
        painter.drawEllipse(
            self.position,
            3,  # Small center dot
            3
        )

        # Draw device label next to the sprite, if provided
        if self.label:
            painter.setPen(QPen(QColor('#FFFFFF'), 1))
            painter.setFont(QFont('Arial', 10, QFont.Bold))
            # Offset label slightly to the right and above the sprite for readability
            label_x = int(self.position.x() + self.size / 2 + 6)
            label_y = int(self.position.y() - self.size / 2)
            painter.drawText(label_x, label_y, str(self.label))
        
        painter.restore()
        
        # Print debug info with additional details including lock state
        lock_status = "LOCKED" if self.is_direction_locked else "UNLOCKED"

        if self.is_direction_locked:

    
            import time
            if self.lock_timestamp:
                duration = time.time() - self.lock_timestamp

        if self.starting_coordinates:
            print(f"  Starting Coordinates: ({self.starting_coordinates.x()}, {self.starting_coordinates.y()})")
    
    def set_direction(self, direction: str):
        """Update the robot's facing direction
        
        Args:
            direction: Direction the robot should face ('north', 'south', 'east', 'west')
        """
        # STRICT RULE: Direction should ONLY change on actual turns, not zone transitions

        
        # STRICT LOCK PROTECTION: Only update direction if not locked
        if not self.is_direction_locked:
            new_dir = direction.lower()
            self.direction = new_dir
            if new_dir in ['north', 'south', 'east', 'west']:
                self.last_valid_direction = new_dir

        else:
            print(f"DEBUG - ⛔ LOCKED ROBOT: Ignoring direction change from {self.locked_direction} to {direction}")
            print(f"DEBUG - Lock details: {self.get_lock_info()}")
            # Absolutely refuse to change direction when locked
            return
    
    def lock_direction(self, direction: str, turn_type: str = None, force: bool = False):
        """Lock the robot's direction due to turn detection
        
        Args:
            direction: Direction to lock to ('north', 'south', 'east', 'west')
            turn_type: Type of turn that caused the lock ('left', 'right', 'inherited', etc.)
            force: Whether to force the lock even if already locked
        """
        import time
        
        if not self.is_direction_locked or force:
            self.is_direction_locked = True
            self.locked_direction = direction.lower()
            self.direction = direction.lower()  # Update current direction to locked direction
            if self.locked_direction in ['north', 'south', 'east', 'west']:
                self.last_valid_direction = self.locked_direction
            self.locked_by_turn_type = turn_type
            self.lock_timestamp = time.time()
            

        else:
            print(f"DEBUG - Robot direction already locked to {self.locked_direction}, ignoring lock request for {direction}")
    
    def unlock_direction(self):
        """Unlock the robot's direction, allowing free direction changes"""
        self.is_direction_locked = False
        self.locked_direction = None
        self.locked_by_turn_type = None
        self.lock_timestamp = None
        

    
    def get_lock_info(self) -> dict:
        """Get information about the current direction lock state"""
        import time
        
        lock_duration = None
        if self.lock_timestamp:
            lock_duration = time.time() - self.lock_timestamp
            
        return {
            'is_locked': self.is_direction_locked,
            'locked_direction': self.locked_direction,
            'current_direction': self.direction,
            'turn_type': self.locked_by_turn_type,
            'lock_duration': lock_duration,
            'lock_timestamp': self.lock_timestamp
        }
    
    def validate_lock_state(self):
        """Validate and enforce lock state consistency"""
        if self.is_direction_locked and self.locked_direction:
            if self.direction != self.locked_direction:

                # Force direction back to locked direction
                self.direction = self.locked_direction
                return False
        return True
    
    def force_lock_direction(self, direction: str, turn_type: str = "forced"):
        """Force lock direction without any checks - for critical lock enforcement"""
        import time
        
        self.is_direction_locked = True
        self.locked_direction = direction.lower()
        self.direction = direction.lower()  # Force current direction to match
        if self.locked_direction in ['north', 'south', 'east', 'west']:
            self.last_valid_direction = self.locked_direction
        self.locked_by_turn_type = turn_type
        self.lock_timestamp = time.time()
        

    
    def set_direction_for_turn_only(self, direction: str, turn_type: str):
        """Set direction ONLY for actual navigation turns (left/right)
        
        This is the ONLY method that should be used to change robot direction.
        Zone transitions should NOT change direction.
        
        Args:
            direction: New direction after turn ('north', 'south', 'east', 'west')
            turn_type: Type of turn ('left', 'right')
        """
        if turn_type not in ['left', 'right']:
            print(f"DEBUG - ❌ INVALID: set_direction_for_turn_only called with non-turn type: {turn_type}")
            return
        
        previous_direction = self.direction
        self.force_lock_direction(direction, turn_type)

    
    def maintain_direction_across_zones(self):
        """Maintain current direction when moving between zones without turns
        
        This ensures the robot keeps facing the same direction when transitioning
        between zones unless there's an actual navigation turn.
        """

        # Direction remains unchanged - this is the correct behavior
        return self.direction
