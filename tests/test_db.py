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


class TestTaxYearSummary:
    """Test tax year summary for income reporting."""

    def test_tax_summary_uses_amount_paid_not_total(self, temp_db):
        """Tax summary should report actual money received, not invoice total."""
        client_id = db.save_client("Test Client", "Test Co", 100.0)

        # Create invoice for $4000, only $2500 paid
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid, date_paid)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 4000,
                    'Net 30', 'ACH', 'paid', 2500, '2025-01-15')
        """, (client_id,))
        conn.commit()
        conn.close()

        summary = db.get_tax_year_summary(2025)
        # Should be $2500 (amount_paid), not $4000 (total)
        assert summary['total_income'] == 2500

    def test_tax_summary_includes_partial_payments(self, temp_db):
        """Tax summary should include partial payments as income."""
        client_id = db.save_client("Test Client", "Test Co", 100.0)

        # Create invoice for $4000, $2500 paid, status = partial
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid, date_paid)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 4000,
                    'Net 30', 'ACH', 'partial', 2500, '2025-01-15')
        """, (client_id,))
        conn.commit()
        conn.close()

        summary = db.get_tax_year_summary(2025)
        # Should include the $2500 partial payment
        assert summary['total_income'] == 2500

    def test_tax_summary_combines_partial_and_paid(self, temp_db):
        """Tax summary should combine partial and fully paid invoices."""
        client_id = db.save_client("Test Client", "Test Co", 100.0)

        conn = db.get_connection()
        cursor = conn.cursor()
        # Fully paid invoice: $1000
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid, date_paid)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 1000,
                    'Net 30', 'ACH', 'paid', 1000, '2025-01-15')
        """, (client_id,))
        # Partial invoice: $500 of $800
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid, date_paid)
            VALUES ('INV-0002', ?, '2025-02-01', '2025-02-28', 'Test', 'hourly', 100, 800,
                    'Net 30', 'ACH', 'partial', 500, '2025-02-15')
        """, (client_id,))
        conn.commit()
        conn.close()

        summary = db.get_tax_year_summary(2025)
        # Should be $1000 + $500 = $1500
        assert summary['total_income'] == 1500


class TestOutstandingBalance:
    """Test outstanding balance tracking for invoices."""

    def test_get_outstanding_balance(self, temp_db):
        """Should return total unpaid amount across all invoices for a client."""
        client_id = db.save_client("Test Client", "Test Co", 100.0)

        conn = db.get_connection()
        cursor = conn.cursor()
        # Partial invoice: $1500 outstanding ($4000 - $2500)
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 4000,
                    'Net 30', 'ACH', 'partial', 2500)
        """, (client_id,))
        # Unpaid invoice: $1000 outstanding
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid)
            VALUES ('INV-0002', ?, '2025-02-01', '2025-02-28', 'Test', 'hourly', 100, 1000,
                    'Net 30', 'ACH', 'unpaid', 0)
        """, (client_id,))
        conn.commit()
        conn.close()

        outstanding = db.get_outstanding_balance(client_id)
        # Should be $1500 + $1000 = $2500
        assert outstanding == 2500

    def test_get_outstanding_balance_no_outstanding(self, temp_db):
        """Should return 0 when all invoices are fully paid."""
        client_id = db.save_client("Test Client", "Test Co", 100.0)

        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 1000,
                    'Net 30', 'ACH', 'paid', 1000)
        """, (client_id,))
        conn.commit()
        conn.close()

        outstanding = db.get_outstanding_balance(client_id)
        assert outstanding == 0

    def test_get_outstanding_invoices(self, temp_db):
        """Should return list of invoices with outstanding balances."""
        client_id = db.save_client("Test Client", "Test Co", 100.0)

        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid)
            VALUES ('INV-0001', ?, '2025-01-01', '2025-01-31', 'Test', 'hourly', 100, 4000,
                    'Net 30', 'ACH', 'partial', 2500)
        """, (client_id,))
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, total,
                                  payment_terms, payment_method, status, amount_paid)
            VALUES ('INV-0002', ?, '2025-02-01', '2025-02-28', 'Test', 'hourly', 100, 1000,
                    'Net 30', 'ACH', 'paid', 1000)
        """, (client_id,))
        conn.commit()
        conn.close()

        invoices = db.get_outstanding_invoices(client_id)
        assert len(invoices) == 1
        assert invoices[0]['invoice_number'] == 'INV-0001'
        assert invoices[0]['outstanding'] == 1500


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


class TestRetainerBilling:
    """Test retainer billing functionality."""

    def test_save_client_with_retainer(self, temp_db):
        """Test creating a client with retainer settings."""
        retainer_settings = {
            'enabled': True,
            'hours': 15.0,
            'rate': 150.0,
        }
        client_id = db.save_client("Retainer Client", "Retainer Co", 100.0,
                                   retainer_settings=retainer_settings)

        client = db.get_client(client_id)
        assert client['retainer_enabled'] == 1
        assert client['retainer_hours'] == 15.0
        assert client['retainer_rate'] == 150.0

    def test_save_client_retainer_no_custom_rate(self, temp_db):
        """Test creating a retainer client without custom rate (uses hourly)."""
        retainer_settings = {
            'enabled': True,
            'hours': 20.0,
            'rate': None,
        }
        client_id = db.save_client("Retainer Client", "", 125.0,
                                   retainer_settings=retainer_settings)

        client = db.get_client(client_id)
        assert client['retainer_enabled'] == 1
        assert client['retainer_hours'] == 20.0
        assert client['retainer_rate'] is None

    def test_update_client_retainer_settings(self, temp_db):
        """Test updating client retainer settings."""
        client_id = db.save_client("Test", "", 100.0)

        # Enable retainer
        retainer_settings = {
            'enabled': True,
            'hours': 10.0,
            'rate': 120.0,
        }
        db.update_client(client_id, "Test", "", 100.0, retainer_settings=retainer_settings)

        client = db.get_client(client_id)
        assert client['retainer_enabled'] == 1
        assert client['retainer_hours'] == 10.0
        assert client['retainer_rate'] == 120.0

    def test_get_week_bounds(self, temp_db):
        """Test week boundary calculation."""
        # Test a Wednesday
        wed = datetime(2025, 1, 22, 14, 30, 0)
        week_start, week_end = db.get_week_bounds(wed)

        assert week_start.weekday() == 0  # Monday
        assert week_start.strftime('%Y-%m-%d') == '2025-01-20'
        assert week_end.weekday() == 6  # Sunday
        assert week_end.strftime('%Y-%m-%d') == '2025-01-26'

    def test_get_week_bounds_monday(self, temp_db):
        """Test week bounds when date is already Monday."""
        mon = datetime(2025, 1, 20, 10, 0, 0)
        week_start, week_end = db.get_week_bounds(mon)

        assert week_start.strftime('%Y-%m-%d') == '2025-01-20'
        assert week_end.strftime('%Y-%m-%d') == '2025-01-26'

    def test_get_week_start_str(self, temp_db):
        """Test getting week start as string."""
        thu = datetime(2025, 1, 23, 9, 0, 0)
        week_start = db.get_week_start_str(thu)
        assert week_start == '2025-01-20'

    def test_retainer_exemption_crud(self, temp_db):
        """Test creating, reading, and deleting exemptions."""
        client_id = db.save_client("Test", "", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': None})

        week_start = '2025-01-20'

        # Initially not exempted
        assert db.is_week_exempted(client_id, week_start) == False

        # Add exemption
        db.add_retainer_exemption(client_id, week_start, "Client requested")
        assert db.is_week_exempted(client_id, week_start) == True

        # Get exemption details
        exemption = db.get_retainer_exemption(client_id, week_start)
        assert exemption is not None
        assert exemption['reason'] == "Client requested"

        # Remove exemption
        db.remove_retainer_exemption(client_id, week_start)
        assert db.is_week_exempted(client_id, week_start) == False

    def test_retainer_week_summary_under_minimum(self, temp_db):
        """Test retainer summary when worked hours < retainer minimum."""
        client_id = db.save_client("Test", "", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 100.0})

        # Add 10 hours of work for this week
        week_start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, week_start, duration_seconds=10 * 3600)

        summary = db.get_retainer_week_summary(client_id, '2025-01-20')

        assert summary['worked_hours'] == 10.0
        assert summary['retainer_hours'] == 15.0
        assert summary['billable_hours'] == 15.0  # max(10, 15)
        assert summary['is_exempted'] == False
        assert summary['total_amount'] == 1500.0  # 15 * 100

    def test_retainer_week_summary_over_minimum(self, temp_db):
        """Test retainer summary when worked hours > retainer minimum."""
        client_id = db.save_client("Test", "", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 100.0})

        # Add 20 hours of work for this week
        week_start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, week_start, duration_seconds=20 * 3600)

        summary = db.get_retainer_week_summary(client_id, '2025-01-20')

        assert summary['worked_hours'] == 20.0
        assert summary['retainer_hours'] == 15.0
        assert summary['billable_hours'] == 20.0  # max(20, 15)
        assert summary['total_amount'] == 2000.0  # 20 * 100

    def test_retainer_week_summary_exempted(self, temp_db):
        """Test retainer summary when week is exempted."""
        client_id = db.save_client("Test", "", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 100.0})

        # Add 10 hours of work
        week_start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, week_start, duration_seconds=10 * 3600)

        # Exempt the week
        db.add_retainer_exemption(client_id, '2025-01-20', "Vacation week")

        summary = db.get_retainer_week_summary(client_id, '2025-01-20')

        assert summary['worked_hours'] == 10.0
        assert summary['billable_hours'] == 10.0  # Only actual hours due to exemption
        assert summary['is_exempted'] == True
        assert summary['exemption_reason'] == "Vacation week"
        assert summary['total_amount'] == 1000.0  # 10 * 100

    def test_retainer_week_summary_zero_hours(self, temp_db):
        """Test retainer summary with zero worked hours (client didn't give work)."""
        client_id = db.save_client("Test", "", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 100.0})

        # No time entries for this week

        summary = db.get_retainer_week_summary(client_id, '2025-01-20')

        assert summary['worked_hours'] == 0.0
        assert summary['retainer_hours'] == 15.0
        assert summary['billable_hours'] == 15.0  # Still bill retainer minimum
        assert summary['total_amount'] == 1500.0

    def test_retainer_week_summary_uses_retainer_rate(self, temp_db):
        """Test that retainer summary uses retainer rate when set."""
        client_id = db.save_client("Test", "", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 10.0, 'rate': 150.0})

        week_start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, week_start, duration_seconds=10 * 3600)

        summary = db.get_retainer_week_summary(client_id, '2025-01-20')

        assert summary['rate'] == 150.0  # Uses retainer rate, not hourly rate
        assert summary['total_amount'] == 1500.0  # 10 * 150

    def test_retainer_week_summary_uses_hourly_rate_if_no_retainer_rate(self, temp_db):
        """Test that retainer summary uses hourly rate when no retainer rate set."""
        client_id = db.save_client("Test", "", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 10.0, 'rate': None})

        week_start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, week_start, duration_seconds=10 * 3600)

        summary = db.get_retainer_week_summary(client_id, '2025-01-20')

        assert summary['rate'] == 100.0  # Falls back to hourly rate
        assert summary['total_amount'] == 1000.0  # 10 * 100

    def test_retainer_clients_appear_in_get_clients(self, temp_db):
        """Test that retainer fields appear when listing clients."""
        db.save_client("Regular Client", "", 100.0)
        db.save_client("Retainer Client", "", 100.0,
                       retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 150.0})

        clients = db.get_clients()
        retainer_client = next(c for c in clients if c['contact_name'] == "Retainer Client")

        assert retainer_client['retainer_enabled'] == 1
        assert retainer_client['retainer_hours'] == 15.0
        assert retainer_client['retainer_rate'] == 150.0


class TestTimeEntryOverlaps:
    """Test overlap detection for time entries."""

    def test_no_overlap_returns_empty(self, temp_db):
        """When entries don't overlap, returns empty list."""
        client_id = db.save_client("Test", "", 100.0)

        # Existing entry: 9am-10am
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            end_time=datetime(2025, 1, 20, 10, 0),
            duration_seconds=3600
        )

        # Check for overlap with 11am-12pm (no overlap)
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 11, 0),
            datetime(2025, 1, 20, 12, 0)
        )
        assert overlaps == []

    def test_partial_overlap_at_start(self, temp_db):
        """Detects overlap when new entry starts during existing entry."""
        client_id = db.save_client("Test", "", 100.0)

        # Existing entry: 9am-10:15am
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            end_time=datetime(2025, 1, 20, 10, 15),
            duration_seconds=4500
        )

        # New entry: 10am-12pm (overlaps by 15 min)
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 10, 0),
            datetime(2025, 1, 20, 12, 0)
        )
        assert len(overlaps) == 1
        assert overlaps[0]['overlap_minutes'] == 15

    def test_partial_overlap_at_end(self, temp_db):
        """Detects overlap when new entry ends during existing entry."""
        client_id = db.save_client("Test", "", 100.0)

        # Existing entry: 11am-1pm
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 11, 0),
            end_time=datetime(2025, 1, 20, 13, 0),
            duration_seconds=7200
        )

        # New entry: 9am-11:30am (overlaps by 30 min)
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            datetime(2025, 1, 20, 11, 30)
        )
        assert len(overlaps) == 1
        assert overlaps[0]['overlap_minutes'] == 30

    def test_complete_containment(self, temp_db):
        """Detects when new entry completely contains existing entry."""
        client_id = db.save_client("Test", "", 100.0)

        # Existing entry: 10am-11am
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 10, 0),
            end_time=datetime(2025, 1, 20, 11, 0),
            duration_seconds=3600
        )

        # New entry: 9am-12pm (completely contains existing)
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            datetime(2025, 1, 20, 12, 0)
        )
        assert len(overlaps) == 1
        assert overlaps[0]['overlap_minutes'] == 60  # Full hour overlap

    def test_multiple_overlaps(self, temp_db):
        """Returns all overlapping entries when multiple exist."""
        client_id = db.save_client("Test", "", 100.0)

        # Existing entries: 9am-10am and 11am-12pm
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            end_time=datetime(2025, 1, 20, 10, 0),
            duration_seconds=3600
        )
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 11, 0),
            end_time=datetime(2025, 1, 20, 12, 0),
            duration_seconds=3600
        )

        # New entry: 9:30am-11:30am (overlaps both)
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 9, 30),
            datetime(2025, 1, 20, 11, 30)
        )
        assert len(overlaps) == 2

    def test_adjacent_entries_no_overlap(self, temp_db):
        """Adjacent entries (end == start) should not count as overlap."""
        client_id = db.save_client("Test", "", 100.0)

        # Existing entry: 9am-10am
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            end_time=datetime(2025, 1, 20, 10, 0),
            duration_seconds=3600
        )

        # New entry: 10am-11am (adjacent, no overlap)
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 10, 0),
            datetime(2025, 1, 20, 11, 0)
        )
        assert overlaps == []

    def test_overnight_entry_overlap(self, temp_db):
        """Detects overlap with overnight entries (crossing midnight)."""
        client_id = db.save_client("Test", "", 100.0)

        # Existing entry: 10pm-2am (overnight)
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 22, 0),
            end_time=datetime(2025, 1, 21, 2, 0),
            duration_seconds=14400
        )

        # New entry: 1am-3am on Jan 21 (overlaps by 1 hour)
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 21, 1, 0),
            datetime(2025, 1, 21, 3, 0)
        )
        assert len(overlaps) == 1
        assert overlaps[0]['overlap_minutes'] == 60

    def test_exclude_entry_id(self, temp_db):
        """Excludes specified entry (for editing existing entries)."""
        client_id = db.save_client("Test", "", 100.0)

        # Create entry: 9am-10am
        entry_id = db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            end_time=datetime(2025, 1, 20, 10, 0),
            duration_seconds=3600
        )

        # Without exclusion - should find the entry
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            datetime(2025, 1, 20, 10, 0)
        )
        assert len(overlaps) == 1

        # With exclusion - should not find it
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            datetime(2025, 1, 20, 10, 0),
            exclude_entry_id=entry_id
        )
        assert overlaps == []

    def test_different_client_no_overlap(self, temp_db):
        """Entries for different clients should not overlap."""
        client1 = db.save_client("Client 1", "", 100.0)
        client2 = db.save_client("Client 2", "", 100.0)

        # Entry for client 1: 9am-10am
        db.save_time_entry(
            client1,
            datetime(2025, 1, 20, 9, 0),
            end_time=datetime(2025, 1, 20, 10, 0),
            duration_seconds=3600
        )

        # Check overlap for client 2 at same time - should be empty
        overlaps = db.check_time_entry_overlaps(
            client2,
            datetime(2025, 1, 20, 9, 0),
            datetime(2025, 1, 20, 10, 0)
        )
        assert overlaps == []

    def test_ignores_entries_without_end_time(self, temp_db):
        """Entries without end_time (active sessions) are ignored."""
        client_id = db.save_client("Test", "", 100.0)

        # Create entry without end_time (active session)
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            end_time=None,
            duration_seconds=None
        )

        # Check for overlap - should be empty since entry has no end_time
        overlaps = db.check_time_entry_overlaps(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            datetime(2025, 1, 20, 10, 0)
        )
        assert overlaps == []


class TestDailyHours:
    """Test daily hours calculation."""

    def test_no_entries_returns_zero(self, temp_db):
        """Returns 0 when no entries exist for the day."""
        client_id = db.save_client("Test", "", 100.0)
        hours = db.get_daily_hours(client_id, datetime(2025, 1, 20))
        assert hours == 0.0

    def test_single_entry_returns_hours(self, temp_db):
        """Returns hours from a single entry."""
        client_id = db.save_client("Test", "", 100.0)

        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            end_time=datetime(2025, 1, 20, 11, 0),
            duration_seconds=7200  # 2 hours
        )

        hours = db.get_daily_hours(client_id, datetime(2025, 1, 20))
        assert hours == 2.0

    def test_multiple_entries_returns_sum(self, temp_db):
        """Returns sum of hours from multiple entries."""
        client_id = db.save_client("Test", "", 100.0)

        # 2 hours in the morning
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            duration_seconds=7200
        )
        # 3 hours in the afternoon
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 14, 0),
            duration_seconds=10800
        )

        hours = db.get_daily_hours(client_id, datetime(2025, 1, 20))
        assert hours == 5.0

    def test_only_counts_target_day(self, temp_db):
        """Only counts entries from the specified day."""
        client_id = db.save_client("Test", "", 100.0)

        # Entry on Jan 20
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            duration_seconds=7200  # 2 hours
        )
        # Entry on Jan 21
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 21, 9, 0),
            duration_seconds=10800  # 3 hours
        )

        # Check Jan 20 only
        hours = db.get_daily_hours(client_id, datetime(2025, 1, 20))
        assert hours == 2.0

    def test_exclude_entry_id(self, temp_db):
        """Excludes specified entry (for editing)."""
        client_id = db.save_client("Test", "", 100.0)

        entry1 = db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            duration_seconds=7200  # 2 hours
        )
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 14, 0),
            duration_seconds=10800  # 3 hours
        )

        # Without exclusion
        hours = db.get_daily_hours(client_id, datetime(2025, 1, 20))
        assert hours == 5.0

        # With exclusion
        hours = db.get_daily_hours(client_id, datetime(2025, 1, 20), exclude_entry_id=entry1)
        assert hours == 3.0

    def test_accepts_date_object(self, temp_db):
        """Works with both datetime and date objects."""
        from datetime import date
        client_id = db.save_client("Test", "", 100.0)

        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            duration_seconds=7200  # 2 hours
        )

        # Pass a date object instead of datetime
        hours = db.get_daily_hours(client_id, date(2025, 1, 20))
        assert hours == 2.0

    def test_ignores_entries_without_duration(self, temp_db):
        """Ignores entries without duration (active sessions)."""
        client_id = db.save_client("Test", "", 100.0)

        # Entry with duration
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 9, 0),
            duration_seconds=7200  # 2 hours
        )
        # Entry without duration (active session)
        db.save_time_entry(
            client_id,
            datetime(2025, 1, 20, 14, 0),
            duration_seconds=None
        )

        hours = db.get_daily_hours(client_id, datetime(2025, 1, 20))
        assert hours == 2.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
