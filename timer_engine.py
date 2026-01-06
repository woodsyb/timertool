"""Timer engine with stopwatch logic, inactivity detection, and crash recovery."""

import ctypes
import random
import time
from datetime import datetime
from typing import Optional, Callable, List
import db

# Try to import pynput for activity tracking
try:
    from pynput import mouse, keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class LASTINPUTINFO(ctypes.Structure):
    """Windows API structure for last input info."""
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]


def get_idle_seconds() -> int:
    """Get system-wide idle time in seconds using Windows API."""
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis // 1000
    except Exception:
        return 0  # Can't detect, assume active


class ActivityTracker:
    """Tracks keyboard and mouse activity."""

    def __init__(self):
        self.key_presses = 0
        self.mouse_clicks = 0
        self.mouse_moves = 0
        self._last_move_time = 0
        self._running = False
        self._mouse_listener = None
        self._keyboard_listener = None

    def start(self):
        """Start tracking activity."""
        if not PYNPUT_AVAILABLE or self._running:
            return

        self.key_presses = 0
        self.mouse_clicks = 0
        self.mouse_moves = 0
        self._running = True

        try:
            self._mouse_listener = mouse.Listener(
                on_click=self._on_click,
                on_move=self._on_move
            )
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key
            )
            self._mouse_listener.start()
            self._keyboard_listener.start()
        except Exception:
            self._running = False

    def stop(self) -> dict:
        """Stop tracking and return stats."""
        self._running = False
        stats = {
            'key_presses': self.key_presses,
            'mouse_clicks': self.mouse_clicks,
            'mouse_moves': self.mouse_moves
        }

        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
            self._keyboard_listener = None

        return stats

    def get_stats(self) -> dict:
        """Get current stats without stopping."""
        return {
            'key_presses': self.key_presses,
            'mouse_clicks': self.mouse_clicks,
            'mouse_moves': self.mouse_moves
        }

    def _on_key(self, key):
        """Handle key press."""
        if self._running:
            self.key_presses += 1

    def _on_click(self, x, y, button, pressed):
        """Handle mouse click."""
        if self._running and pressed:
            self.mouse_clicks += 1

    def _on_move(self, x, y):
        """Handle mouse move (throttled to avoid counting every pixel)."""
        if self._running:
            now = time.time()
            if now - self._last_move_time > 0.1:  # Count at most 10 moves/sec
                self.mouse_moves += 1
                self._last_move_time = now


class ScreenshotCapture:
    """Captures screenshots at random intervals for proof of work."""

    INTERVAL = 600  # 10 minutes in seconds

    def __init__(self):
        self.client_id: Optional[int] = None
        self.captured_ids: List[int] = []  # screenshot IDs captured this session
        self._running = False
        self._next_capture_time: Optional[float] = None
        self._current_window_end: Optional[float] = None

    def start(self, client_id: int):
        """Start screenshot capture for a client."""
        self.client_id = client_id
        self.captured_ids = []
        self._running = True
        self._schedule_next_capture()

    def stop(self) -> List[int]:
        """Stop capture and return list of screenshot IDs from this session."""
        self._running = False
        ids = self.captured_ids.copy()
        self.captured_ids = []
        return ids

    def _schedule_next_capture(self):
        """Schedule random time within current 10-min window."""
        now = time.time()
        self._current_window_end = now + self.INTERVAL
        # Random time within window (not in first 30s to avoid immediate capture)
        self._next_capture_time = now + random.randint(30, self.INTERVAL - 30)

    def tick(self) -> Optional[dict]:
        """Called every second. Returns capture info if screenshot taken."""
        if not self._running:
            return None

        now = time.time()

        # Check if we've passed into a new window without capturing
        if self._current_window_end and now >= self._current_window_end:
            self._schedule_next_capture()

        # Check if it's time to capture
        if self._next_capture_time and now >= self._next_capture_time:
            self._next_capture_time = None  # Clear to prevent re-capture
            return self._capture()

        return None

    def reschedule_in_window(self):
        """Called when user deletes screenshot - try again in same window if time permits."""
        if not self._running or not self._current_window_end:
            return

        now = time.time()
        remaining = self._current_window_end - now
        if remaining > 60:  # At least 1 min left in window
            self._next_capture_time = now + random.randint(30, max(31, int(remaining) - 30))

    def _capture(self) -> Optional[dict]:
        """Take screenshot, save to disk, return info for popup."""
        try:
            from PIL import ImageGrab, Image

            # Capture primary monitor (PIL default)
            img = ImageGrab.grab()

            # Save full screenshot
            screenshots_dir = db.get_screenshots_dir() / str(self.client_id)
            screenshots_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"screenshot_{timestamp}.png"
            filepath = screenshots_dir / filename
            img.save(filepath, 'PNG', optimize=True)

            # Create thumbnail for popup (200px wide)
            thumb_width = 200
            ratio = thumb_width / img.width
            thumb_size = (thumb_width, int(img.height * ratio))
            thumbnail = img.resize(thumb_size, Image.Resampling.LANCZOS)

            # Save to DB
            screenshot_id = db.save_screenshot(self.client_id, str(filepath))
            self.captured_ids.append(screenshot_id)

            # Schedule next window
            self._schedule_next_capture()

            return {
                'screenshot_id': screenshot_id,
                'thumbnail': thumbnail,  # PIL Image for popup
                'filepath': filepath
            }
        except Exception as e:
            print(f"Screenshot capture failed: {e}")
            # Schedule next anyway
            self._schedule_next_capture()
            return None


class TimerEngine:
    """Manages stopwatch state and persistence."""

    def __init__(self):
        self.client_id: Optional[int] = None
        self.start_time: Optional[datetime] = None
        self.pause_time: Optional[datetime] = None
        self.accumulated_seconds: int = 0
        self.current_entry_id: Optional[int] = None
        self.state: str = 'stopped'  # stopped, running, paused

        # Callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_idle_detected: Optional[Callable] = None
        self.on_screenshot: Optional[Callable] = None  # Called when screenshot captured

        # Settings
        self.inactivity_timeout = int(db.get_setting('inactivity_timeout_minutes', '10')) * 60
        self.auto_save_interval = int(db.get_setting('auto_save_interval_seconds', '30'))

        # Idle tracking
        self._idle_notified = False
        self._last_save_time = datetime.now()

        # Activity tracking
        self.activity_tracker = ActivityTracker()
        self._track_activity = False

        # Screenshot capture
        self.screenshot_capture = ScreenshotCapture()
        self._capture_screenshots = False

    def start(self, client_id: int, track_activity: bool = True, capture_screenshots: bool = False):
        """Start the timer for a client."""
        if self.state == 'running':
            return

        self.client_id = client_id
        self.start_time = datetime.now()
        self.accumulated_seconds = 0
        self.state = 'running'
        self._idle_notified = False
        self._track_activity = track_activity
        self._capture_screenshots = capture_screenshots

        # Start activity tracking if enabled for this client
        if track_activity:
            self.activity_tracker.start()

        # Start screenshot capture if enabled for this client
        if capture_screenshots:
            self.screenshot_capture.start(client_id)

        # Save to active_timer for crash recovery
        db.save_active_timer(client_id, self.start_time, 0)

        if self.on_state_change:
            self.on_state_change('running')

    def stop(self, description: str = '') -> Optional[int]:
        """Stop the timer and save the entry. Returns entry ID."""
        if self.state == 'stopped':
            return None

        end_time = datetime.now()
        total_seconds = self.get_elapsed_seconds()

        # Stop activity tracking and get stats
        activity_stats = self.activity_tracker.stop()

        # Stop screenshot capture and get IDs
        screenshot_ids = self.screenshot_capture.stop()

        # Save the time entry with activity stats
        entry_id = db.save_time_entry(
            client_id=self.client_id,
            start_time=self.start_time,
            end_time=end_time,
            duration_seconds=total_seconds,
            description=description,
            entry_type='stopwatch',
            key_presses=activity_stats.get('key_presses', 0),
            mouse_clicks=activity_stats.get('mouse_clicks', 0),
            mouse_moves=activity_stats.get('mouse_moves', 0)
        )

        # Link screenshots to the entry
        if screenshot_ids:
            db.link_screenshots_to_entry(screenshot_ids, entry_id)

        # Clear active timer
        db.clear_active_timer()

        # Reset state
        self.client_id = None
        self.start_time = None
        self.pause_time = None
        self.accumulated_seconds = 0
        self.current_entry_id = None
        self.state = 'stopped'

        if self.on_state_change:
            self.on_state_change('stopped')

        return entry_id

    def get_activity_stats(self) -> dict:
        """Get current activity stats."""
        return self.activity_tracker.get_stats()

    def pause(self):
        """Pause the timer."""
        if self.state != 'running':
            return

        self.pause_time = datetime.now()
        self.accumulated_seconds = self.get_elapsed_seconds()
        self.state = 'paused'

        # Update active timer
        db.update_active_timer(self.accumulated_seconds)

        if self.on_state_change:
            self.on_state_change('paused')

    def resume(self):
        """Resume the timer from pause."""
        if self.state != 'paused':
            return

        # Adjust start time to account for pause
        self.start_time = datetime.now()
        self.pause_time = None
        self.state = 'running'
        self._idle_notified = False

        # Update active timer
        db.save_active_timer(self.client_id, self.start_time, self.accumulated_seconds)

        if self.on_state_change:
            self.on_state_change('running')

    def discard_idle_time(self, idle_seconds: int):
        """Discard idle time from the accumulated total."""
        if self.state == 'paused':
            self.accumulated_seconds = max(0, self.accumulated_seconds - idle_seconds)
            db.update_active_timer(self.accumulated_seconds)

    def get_elapsed_seconds(self) -> int:
        """Get total elapsed seconds including accumulated."""
        if self.state == 'stopped':
            return 0
        elif self.state == 'paused':
            return self.accumulated_seconds
        else:
            current = (datetime.now() - self.start_time).total_seconds()
            return self.accumulated_seconds + int(current)

    def tick(self):
        """Called periodically to check idle, auto-save, and screenshot capture."""
        if self.state != 'running':
            return

        # Check for inactivity
        idle_secs = get_idle_seconds()
        if idle_secs >= self.inactivity_timeout and not self._idle_notified:
            self._idle_notified = True
            self.pause()
            if self.on_idle_detected:
                self.on_idle_detected(idle_secs)

        # Auto-save
        now = datetime.now()
        if (now - self._last_save_time).total_seconds() >= self.auto_save_interval:
            db.update_active_timer(self.get_elapsed_seconds())
            self._last_save_time = now

        # Check for screenshot capture
        if self._capture_screenshots:
            capture_result = self.screenshot_capture.tick()
            if capture_result and self.on_screenshot:
                self.on_screenshot(capture_result)

    def recover_from_crash(self) -> Optional[dict]:
        """Check for and return crash recovery data."""
        active = db.get_active_timer()
        if active and active['client_id']:
            return {
                'client_id': active['client_id'],
                'start_time': datetime.fromisoformat(active['start_time']),
                'accumulated_seconds': active['accumulated_seconds'],
                'last_save_time': datetime.fromisoformat(active['last_save_time'])
            }
        return None

    def apply_recovery(self, keep: bool, recovery_data: dict):
        """Apply or discard recovered timer data."""
        if keep:
            # Save as completed entry
            db.save_time_entry(
                client_id=recovery_data['client_id'],
                start_time=recovery_data['start_time'],
                end_time=recovery_data['last_save_time'],
                duration_seconds=recovery_data['accumulated_seconds'],
                entry_type='stopwatch'
            )
        # Clear either way
        db.clear_active_timer()


def format_seconds(seconds: int) -> str:
    """Format seconds as HH:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_hours(hours: float) -> str:
    """Format hours as X.XX hrs."""
    return f"{hours:.2f} hrs"


def format_currency(amount: float) -> str:
    """Format amount as currency."""
    return f"${amount:,.2f}"
