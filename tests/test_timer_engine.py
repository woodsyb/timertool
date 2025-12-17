"""Tests for timer engine."""

import pytest
import tempfile
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import timer_engine


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    original_get_app_dir = db.get_app_dir
    db.get_app_dir = lambda: Path(temp_dir)
    db.DB_PATH = None
    db.init_db()
    yield temp_dir
    db.get_app_dir = original_get_app_dir
    db.DB_PATH = None
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def engine(temp_db):
    """Create a timer engine for testing."""
    return timer_engine.TimerEngine()


class TestTimerEngine:
    """Test timer engine operations."""

    def test_initial_state(self, engine):
        """Test engine starts in stopped state."""
        assert engine.state == 'stopped'
        assert engine.client_id is None
        assert engine.start_time is None

    def test_start_timer(self, engine, temp_db):
        """Test starting the timer."""
        client_id = db.save_client("Test", "", 100.0)
        engine.start(client_id)

        assert engine.state == 'running'
        assert engine.client_id == client_id
        assert engine.start_time is not None

    def test_start_with_track_activity_disabled(self, engine, temp_db):
        """Test starting timer without activity tracking."""
        client_id = db.save_client("Test", "", 100.0, track_activity=False)
        engine.start(client_id, track_activity=False)

        assert engine.state == 'running'
        assert engine._track_activity == False

    def test_pause_timer(self, engine, temp_db):
        """Test pausing the timer."""
        client_id = db.save_client("Test", "", 100.0)
        engine.start(client_id)
        engine.pause()

        assert engine.state == 'paused'
        assert engine.accumulated_seconds >= 0

    def test_resume_timer(self, engine, temp_db):
        """Test resuming the timer."""
        client_id = db.save_client("Test", "", 100.0)
        engine.start(client_id)
        engine.pause()
        engine.resume()

        assert engine.state == 'running'

    def test_stop_timer_creates_entry(self, engine, temp_db):
        """Test stopping timer creates time entry."""
        client_id = db.save_client("Test", "", 100.0)
        engine.start(client_id)

        # Simulate some time passing
        engine.accumulated_seconds = 3600  # 1 hour

        entry_id = engine.stop()

        assert entry_id is not None
        assert engine.state == 'stopped'

        # Verify entry was created
        entry = db.get_time_entry(entry_id)
        assert entry is not None
        assert entry['client_id'] == client_id

    def test_get_elapsed_seconds_stopped(self, engine):
        """Test elapsed seconds when stopped."""
        assert engine.get_elapsed_seconds() == 0

    def test_get_elapsed_seconds_paused(self, engine, temp_db):
        """Test elapsed seconds when paused."""
        client_id = db.save_client("Test", "", 100.0)
        engine.start(client_id)
        engine.accumulated_seconds = 100
        engine.pause()

        assert engine.get_elapsed_seconds() == 100

    def test_discard_idle_time(self, engine, temp_db):
        """Test discarding idle time."""
        client_id = db.save_client("Test", "", 100.0)
        engine.start(client_id)
        engine.accumulated_seconds = 1000
        engine.pause()

        engine.discard_idle_time(300)

        assert engine.accumulated_seconds == 700

    def test_discard_idle_time_not_negative(self, engine, temp_db):
        """Test discarding idle time doesn't go negative."""
        client_id = db.save_client("Test", "", 100.0)
        engine.start(client_id)
        engine.accumulated_seconds = 100
        engine.pause()

        engine.discard_idle_time(500)

        assert engine.accumulated_seconds == 0


class TestCrashRecovery:
    """Test crash recovery functionality."""

    def test_recover_from_crash(self, engine, temp_db):
        """Test crash recovery returns data."""
        client_id = db.save_client("Test", "", 100.0)
        start_time = datetime.now()

        # Simulate crash - save active timer
        db.save_active_timer(client_id, start_time, 3600)

        recovery_data = engine.recover_from_crash()

        assert recovery_data is not None
        assert recovery_data['client_id'] == client_id
        assert recovery_data['accumulated_seconds'] == 3600

    def test_recover_no_crash(self, engine, temp_db):
        """Test recovery returns None when no crash data."""
        recovery_data = engine.recover_from_crash()
        assert recovery_data is None

    def test_apply_recovery_keep(self, engine, temp_db):
        """Test applying recovery data (keep)."""
        client_id = db.save_client("Test", "", 100.0)
        start_time = datetime.now() - timedelta(hours=1)
        last_save = datetime.now()

        recovery_data = {
            'client_id': client_id,
            'start_time': start_time,
            'accumulated_seconds': 3600,
            'last_save_time': last_save
        }

        engine.apply_recovery(keep=True, recovery_data=recovery_data)

        # Should have created a time entry
        entries = db.get_time_entries(client_id=client_id)
        assert len(entries) == 1
        assert entries[0]['duration_seconds'] == 3600

    def test_apply_recovery_discard(self, engine, temp_db):
        """Test applying recovery data (discard)."""
        client_id = db.save_client("Test", "", 100.0)
        start_time = datetime.now()
        db.save_active_timer(client_id, start_time, 3600)

        recovery_data = {
            'client_id': client_id,
            'start_time': start_time,
            'accumulated_seconds': 3600,
            'last_save_time': start_time
        }

        engine.apply_recovery(keep=False, recovery_data=recovery_data)

        # Should NOT have created a time entry
        entries = db.get_time_entries(client_id=client_id)
        assert len(entries) == 0

        # Active timer should be cleared
        assert db.get_active_timer() is None


class TestFormatFunctions:
    """Test formatting functions."""

    def test_format_seconds(self):
        """Test seconds formatting."""
        assert timer_engine.format_seconds(0) == "00:00:00"
        assert timer_engine.format_seconds(61) == "00:01:01"
        assert timer_engine.format_seconds(3661) == "01:01:01"
        assert timer_engine.format_seconds(36000) == "10:00:00"

    def test_format_hours(self):
        """Test hours formatting."""
        assert timer_engine.format_hours(0) == "0.00 hrs"
        assert timer_engine.format_hours(1.5) == "1.50 hrs"
        assert timer_engine.format_hours(10.25) == "10.25 hrs"

    def test_format_currency(self):
        """Test currency formatting."""
        assert timer_engine.format_currency(0) == "$0.00"
        assert timer_engine.format_currency(100) == "$100.00"
        assert timer_engine.format_currency(1234.56) == "$1,234.56"
        assert timer_engine.format_currency(1000000) == "$1,000,000.00"


class TestActivityTracker:
    """Test activity tracker."""

    def test_initial_stats(self):
        """Test initial stats are zero."""
        tracker = timer_engine.ActivityTracker()
        stats = tracker.get_stats()

        assert stats['key_presses'] == 0
        assert stats['mouse_clicks'] == 0
        assert stats['mouse_moves'] == 0

    def test_stop_returns_stats(self):
        """Test stop returns stats."""
        tracker = timer_engine.ActivityTracker()
        tracker.key_presses = 100
        tracker.mouse_clicks = 50
        tracker.mouse_moves = 200

        stats = tracker.stop()

        assert stats['key_presses'] == 100
        assert stats['mouse_clicks'] == 50
        assert stats['mouse_moves'] == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
