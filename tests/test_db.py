"""Tests for database operations."""

import pytest
import tempfile
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import db


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp()

    # Override db paths
    original_get_app_dir = db.get_app_dir
    db.get_app_dir = lambda: Path(temp_dir)
    db.DB_PATH = None  # Reset cached path

    # Initialize fresh db
    db.init_db()

    yield temp_dir

    # Restore
    db.get_app_dir = original_get_app_dir
    db.DB_PATH = None

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestClients:
    """Test client CRUD operations."""

    def test_save_client(self, temp_db):
        """Test creating a new client."""
        client_id = db.save_client("Test Contact", "Test Company", 100.0)
        assert client_id > 0

        client = db.get_client(client_id)
        assert client is not None
        assert client['contact_name'] == "Test Contact"
        assert client['company_name'] == "Test Company"
        assert client['hourly_rate'] == 100.0
        assert client['track_activity'] == 1  # Default on

    def test_save_client_with_track_activity_off(self, temp_db):
        """Test creating client with activity tracking disabled."""
        client_id = db.save_client("No Track", "", 50.0, track_activity=False)
        client = db.get_client(client_id)
        assert client['track_activity'] == 0

    def test_update_client(self, temp_db):
        """Test updating a client."""
        client_id = db.save_client("Original", "", 100.0)
        db.update_client(client_id, "Updated", "New Company", 150.0, track_activity=False)

        client = db.get_client(client_id)
        assert client['contact_name'] == "Updated"
        assert client['company_name'] == "New Company"
        assert client['hourly_rate'] == 150.0
        assert client['track_activity'] == 0

    def test_get_clients(self, temp_db):
        """Test getting all clients."""
        db.save_client("Client A", "", 100.0)
        db.save_client("Client B", "", 200.0)

        clients = db.get_clients()
        assert len(clients) == 2

    def test_toggle_favorite(self, temp_db):
        """Test toggling client favorite status."""
        client_id = db.save_client("Test", "", 100.0)

        # Initially not favorite
        client = db.get_client(client_id)
        assert client['favorite'] == 0

        # Toggle on
        result = db.toggle_client_favorite(client_id)
        assert result == True
        client = db.get_client(client_id)
        assert client['favorite'] == 1

        # Toggle off
        result = db.toggle_client_favorite(client_id)
        assert result == False
        client = db.get_client(client_id)
        assert client['favorite'] == 0

    def test_archive_client(self, temp_db):
        """Test archiving a client."""
        client_id = db.save_client("Test", "", 100.0)
        db.archive_client(client_id)

        # Should not appear in normal list
        clients = db.get_clients()
        assert len(clients) == 0

        # Should appear with include_archived
        clients = db.get_clients(include_archived=True)
        assert len(clients) == 1

    def test_delete_client_no_entries(self, temp_db):
        """Test deleting client with no time entries."""
        client_id = db.save_client("Test", "", 100.0)
        db.delete_client(client_id)

        client = db.get_client(client_id)
        assert client is None

    def test_delete_client_with_entries_fails(self, temp_db):
        """Test that deleting client with entries raises error."""
        client_id = db.save_client("Test", "", 100.0)
        db.save_time_entry(client_id, datetime.now(), duration_seconds=3600)

        with pytest.raises(ValueError):
            db.delete_client(client_id)


class TestTimeEntries:
    """Test time entry operations."""

    def test_save_time_entry(self, temp_db):
        """Test saving a time entry."""
        client_id = db.save_client("Test", "", 100.0)
        start = datetime.now()
        end = start + timedelta(hours=2)

        entry_id = db.save_time_entry(
            client_id=client_id,
            start_time=start,
            end_time=end,
            duration_seconds=7200,
            description="Test work",
            entry_type='stopwatch'
        )

        assert entry_id > 0

        entries = db.get_time_entries(client_id=client_id)
        assert len(entries) == 1
        assert entries[0]['duration_seconds'] == 7200
        assert entries[0]['description'] == "Test work"

    def test_save_time_entry_with_activity(self, temp_db):
        """Test saving time entry with activity stats."""
        client_id = db.save_client("Test", "", 100.0)

        entry_id = db.save_time_entry(
            client_id=client_id,
            start_time=datetime.now(),
            duration_seconds=3600,
            key_presses=1000,
            mouse_clicks=500,
            mouse_moves=2000
        )

        entry = db.get_time_entry(entry_id)
        assert entry['key_presses'] == 1000
        assert entry['mouse_clicks'] == 500
        assert entry['mouse_moves'] == 2000

    def test_update_time_entry(self, temp_db):
        """Test updating a time entry."""
        client_id = db.save_client("Test", "", 100.0)
        entry_id = db.save_time_entry(client_id, datetime.now(), duration_seconds=3600)

        db.update_time_entry(entry_id, duration_seconds=7200, description="Updated")

        entry = db.get_time_entry(entry_id)
        assert entry['duration_seconds'] == 7200
        assert entry['description'] == "Updated"

    def test_delete_time_entry(self, temp_db):
        """Test deleting a time entry."""
        client_id = db.save_client("Test", "", 100.0)
        entry_id = db.save_time_entry(client_id, datetime.now(), duration_seconds=3600)

        result = db.delete_time_entry(entry_id)
        assert result == True

        entry = db.get_time_entry(entry_id)
        assert entry is None

    def test_delete_invoiced_entry_fails(self, temp_db):
        """Test that deleting invoiced entry raises error."""
        client_id = db.save_client("Test", "", 100.0)
        entry_id = db.save_time_entry(client_id, datetime.now(), duration_seconds=3600)

        # Mark as invoiced
        db.mark_entries_invoiced([entry_id], "INV-0001")

        with pytest.raises(ValueError):
            db.delete_time_entry(entry_id)

    def test_get_time_entries_filtered(self, temp_db):
        """Test filtering time entries."""
        client_id = db.save_client("Test", "", 100.0)

        # Create uninvoiced entry
        entry1 = db.save_time_entry(client_id, datetime.now(), duration_seconds=3600)
        # Create invoiced entry
        entry2 = db.save_time_entry(client_id, datetime.now(), duration_seconds=7200)
        db.mark_entries_invoiced([entry2], "INV-0001")

        # Filter uninvoiced
        uninvoiced = db.get_time_entries(client_id=client_id, invoiced=False)
        assert len(uninvoiced) == 1
        assert uninvoiced[0]['id'] == entry1

        # Filter invoiced
        invoiced = db.get_time_entries(client_id=client_id, invoiced=True)
        assert len(invoiced) == 1
        assert invoiced[0]['id'] == entry2


class TestTimeSummary:
    """Test time summary calculations."""

    def test_client_summary_uninvoiced(self, temp_db):
        """Test uninvoiced hours in client summary."""
        client_id = db.save_client("Test", "", 100.0)

        # Add 2 hours uninvoiced
        db.save_time_entry(client_id, datetime.now(), duration_seconds=7200)

        summary = db.get_time_summary(client_id)
        assert summary['uninvoiced_hours'] == 2.0
        assert summary['invoiced_hours'] == 0
        assert summary['paid_hours'] == 0

    def test_client_summary_with_invoice(self, temp_db):
        """Test summary with invoiced hours."""
        client_id = db.save_client("Test", "", 100.0)

        # Create an invoice with hours
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 500,
                    'Net 30', 'ACH', 'unpaid')
        """, (client_id,))
        cursor.execute("""
            INSERT INTO invoice_hours (invoice_number, work_date, hours)
            VALUES ('INV-0001', '2025-01-01', 5.0)
        """)
        conn.commit()
        conn.close()

        summary = db.get_time_summary(client_id)
        assert summary['invoiced_hours'] == 5.0
        assert summary['paid_hours'] == 0

    def test_client_summary_with_paid_invoice(self, temp_db):
        """Test summary with paid invoice."""
        client_id = db.save_client("Test", "", 100.0)

        # Create a paid invoice with hours
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 500,
                    'Net 30', 'ACH', 'paid')
        """, (client_id,))
        cursor.execute("""
            INSERT INTO invoice_hours (invoice_number, work_date, hours)
            VALUES ('INV-0001', '2025-01-01', 5.0)
        """)
        conn.commit()
        conn.close()

        summary = db.get_time_summary(client_id)
        assert summary['invoiced_hours'] == 0  # Paid invoices don't count as "invoiced"
        assert summary['paid_hours'] == 5.0

    def test_global_summary(self, temp_db):
        """Test global summary across all clients."""
        client1 = db.save_client("Client 1", "", 100.0)
        client2 = db.save_client("Client 2", "", 150.0)

        # Add hours to both
        db.save_time_entry(client1, datetime.now(), duration_seconds=3600)  # 1 hr
        db.save_time_entry(client2, datetime.now(), duration_seconds=7200)  # 2 hrs

        summary = db.get_global_time_summary()
        assert summary['uninvoiced_hours'] == 3.0


class TestInvoices:
    """Test invoice operations."""

    def test_get_next_invoice_number(self, temp_db):
        """Test invoice number generation."""
        num1 = db.get_next_invoice_number()
        assert num1 == "INV-0001"

    def test_mark_invoice_paid(self, temp_db):
        """Test marking invoice as paid."""
        client_id = db.save_client("Test", "", 100.0)

        # Create invoice
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 500,
                    'Net 30', 'ACH', 'unpaid')
        """, (client_id,))
        conn.commit()
        conn.close()

        db.mark_invoice_paid('INV-0001')

        invoice = db.get_invoice('INV-0001')
        assert invoice['status'] == 'paid'
        assert invoice['amount_paid'] == 500

    def test_record_partial_payment(self, temp_db):
        """Test recording partial payment."""
        client_id = db.save_client("Test", "", 100.0)

        # Create invoice for $500
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 500,
                    'Net 30', 'ACH', 'unpaid')
        """, (client_id,))
        conn.commit()
        conn.close()

        # Pay $200
        db.record_payment('INV-0001', 200)

        invoice = db.get_invoice('INV-0001')
        assert invoice['status'] == 'partial'
        assert invoice['amount_paid'] == 200

        # Pay remaining $300
        db.record_payment('INV-0001', 300)

        invoice = db.get_invoice('INV-0001')
        assert invoice['status'] == 'paid'
        assert invoice['amount_paid'] == 500


class TestActiveTimer:
    """Test active timer (crash recovery) operations."""

    def test_save_and_get_active_timer(self, temp_db):
        """Test saving and retrieving active timer."""
        client_id = db.save_client("Test", "", 100.0)
        start_time = datetime.now()

        db.save_active_timer(client_id, start_time, 3600)

        active = db.get_active_timer()
        assert active is not None
        assert active['client_id'] == client_id
        assert active['accumulated_seconds'] == 3600

    def test_update_active_timer(self, temp_db):
        """Test updating active timer."""
        client_id = db.save_client("Test", "", 100.0)
        db.save_active_timer(client_id, datetime.now(), 0)

        db.update_active_timer(7200)

        active = db.get_active_timer()
        assert active['accumulated_seconds'] == 7200

    def test_clear_active_timer(self, temp_db):
        """Test clearing active timer."""
        client_id = db.save_client("Test", "", 100.0)
        db.save_active_timer(client_id, datetime.now(), 0)

        db.clear_active_timer()

        active = db.get_active_timer()
        assert active is None


class TestSettings:
    """Test settings operations."""

    def test_get_default_setting(self, temp_db):
        """Test getting default settings."""
        timeout = db.get_setting('inactivity_timeout_minutes', '10')
        assert timeout == '10'

    def test_set_and_get_setting(self, temp_db):
        """Test setting and getting a custom setting."""
        db.set_setting('custom_key', 'custom_value')
        value = db.get_setting('custom_key')
        assert value == 'custom_value'

    def test_get_nonexistent_setting(self, temp_db):
        """Test getting nonexistent setting returns default."""
        value = db.get_setting('nonexistent', 'default')
        assert value == 'default'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
