"""Tests for invoice PDF reissue functionality."""

import pytest
import tempfile
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import invoice_bridge
from generate_pdf import generate_invoice_pdf


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


def _setup_full_invoice(temp_db, payment_method='ACH'):
    """Set up client, business info, banking, time entry, and create invoice."""
    # Business info
    db.save_business_info({
        'company_name': 'Test LLC',
        'owner_name': 'Test Owner',
        'address': '123 Test St',
        'city': 'Testville',
        'state': 'TX',
        'zip': '75001',
        'phone': '555-0100',
        'email': 'test@test.com',
        'ein': '12-3456789',
    })

    # Banking info
    db.save_banking({
        'bank_name': 'Test Bank',
        'routing_number': '111000025',
        'account_number': '123456789',
        'domestic_wire_instructions': 'Bank: Test Wire Bank\nRouting: 222000025',
    })

    # Client and time entry
    client_id = db.save_client("Test Contact", "Test Company", 100.0)
    client = db.get_client(client_id)
    start = datetime(2025, 1, 20, 9, 0, 0)
    db.save_time_entry(client_id, start, duration_seconds=10 * 3600)
    entries = db.get_time_entries(client_id=client_id, invoiced=False)

    result = invoice_bridge.create_invoice(
        client=client,
        entries=entries,
        description="January work",
        payment_terms="Net 30",
        payment_method=payment_method,
    )
    assert result['success']
    return result['invoice_number']


def _setup_weekly_flat_rate_invoice(temp_db):
    """Set up a weekly flat rate invoice with entries in two weeks."""
    db.save_business_info({
        'company_name': 'Test LLC', 'owner_name': 'Test Owner',
        'address': '123 Test St', 'city': 'Testville', 'state': 'TX',
        'zip': '75001', 'phone': '555-0100', 'email': 'test@test.com',
        'ein': '12-3456789',
    })
    db.save_banking({
        'bank_name': 'Test Bank', 'routing_number': '111000025',
        'account_number': '123456789',
    })

    client_id = db.save_client("Weekly Client", "Weekly Co", 100.0,
                               weekly_flat_rate_settings={'enabled': True, 'rate': 4000.0})
    client = db.get_client(client_id)

    # Entries in two different weeks (Mon Jan 20 and Mon Jan 27)
    db.save_time_entry(client_id, datetime(2025, 1, 20, 9, 0, 0), duration_seconds=8 * 3600)
    db.save_time_entry(client_id, datetime(2025, 1, 27, 9, 0, 0), duration_seconds=8 * 3600)
    entries = db.get_time_entries(client_id=client_id, invoiced=False)

    result = invoice_bridge.create_invoice(
        client=client, entries=entries,
        description="Biweekly services",
        payment_terms="Net 30", payment_method="ACH",
        weekly_flat_rate_info={
            'is_weekly_flat_rate': True, 'weeks': 2,
            'weekly_rate': 4000.0,
            'period_start': '2025-01-20', 'period_end': '2025-02-02',
        },
    )
    assert result['success']
    return result['invoice_number']


class TestReissuePDF:
    """Test invoice PDF reissue (regeneration)."""

    def test_reissue_regenerates_pdf(self, temp_db):
        """Calling generate_invoice_pdf again overwrites the existing PDF."""
        inv_num = _setup_full_invoice(temp_db)

        pdf_path = generate_invoice_pdf(inv_num)
        assert pdf_path.exists()
        first_mtime = pdf_path.stat().st_mtime

        # Small delay to ensure different mtime
        time.sleep(0.05)

        pdf_path2 = generate_invoice_pdf(inv_num)
        assert pdf_path2.exists()
        assert pdf_path2 == pdf_path  # Same path
        assert pdf_path2.stat().st_mtime > first_mtime

    def test_reissue_with_changed_payment_method(self, temp_db):
        """Changing payment method in DB then regenerating produces a valid PDF."""
        inv_num = _setup_full_invoice(temp_db, payment_method='ACH')

        # Verify initial method
        invoice = db.get_invoice(inv_num)
        assert invoice['payment_method'] == 'ACH'

        # Change to Domestic Wire and regenerate
        db.update_invoice_payment_method(inv_num, 'Domestic Wire')
        pdf_path = generate_invoice_pdf(inv_num)

        assert pdf_path.exists()
        updated = db.get_invoice(inv_num)
        assert updated['payment_method'] == 'Domestic Wire'

    def test_reissue_with_changed_payment_terms(self, temp_db):
        """Changing payment terms recalculates due date."""
        from datetime import datetime as dt
        from invoice_bridge import calculate_due_date

        inv_num = _setup_full_invoice(temp_db, payment_method='ACH')

        invoice = db.get_invoice(inv_num)
        assert invoice['payment_terms'] == 'Net 30'
        original_due = invoice['due_date']

        # Change to Due on Receipt
        issue_date = dt.strptime(invoice['date_issued'], '%Y-%m-%d')
        new_due = calculate_due_date('Due on Receipt', issue_date).strftime('%Y-%m-%d')
        db.update_invoice_terms(inv_num, 'Due on Receipt', new_due)

        pdf_path = generate_invoice_pdf(inv_num)
        assert pdf_path.exists()

        updated = db.get_invoice(inv_num)
        assert updated['payment_terms'] == 'Due on Receipt'
        assert updated['due_date'] == invoice['date_issued']  # Same as issue date
        assert updated['due_date'] != original_due

    def test_reissue_without_business_info_raises(self, temp_db):
        """Reissuing without business info raises ValueError."""
        # Create invoice without business info setup
        client_id = db.save_client("Test Contact", "Test Company", 100.0)
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

        with pytest.raises(ValueError, match="Business info not configured"):
            generate_invoice_pdf('INV-0001')

    def test_reissue_nonexistent_invoice_raises(self, temp_db):
        """Reissuing a non-existent invoice raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            generate_invoice_pdf('FAKE-9999')

    def test_weekly_flat_rate_pdf_generation(self, temp_db):
        """Weekly flat rate invoice generates a valid PDF."""
        # Setup business + banking
        db.save_business_info({
            'company_name': 'Test LLC', 'owner_name': 'Test Owner',
            'address': '123 Test St', 'city': 'Testville', 'state': 'TX',
            'zip': '75001', 'phone': '555-0100', 'email': 'test@test.com',
            'ein': '12-3456789',
        })
        db.save_banking({
            'bank_name': 'Test Bank', 'routing_number': '111000025',
            'account_number': '123456789',
        })

        # Create weekly flat rate client
        client_id = db.save_client("Weekly Client", "Weekly Co", 100.0,
                                   weekly_flat_rate_settings={'enabled': True, 'rate': 4000.0})
        client = db.get_client(client_id)

        # Create entries in two weeks
        db.save_time_entry(client_id, datetime(2025, 1, 20, 9, 0, 0), duration_seconds=8 * 3600)
        db.save_time_entry(client_id, datetime(2025, 1, 27, 9, 0, 0), duration_seconds=8 * 3600)
        entries = db.get_time_entries(client_id=client_id, invoiced=False)

        weekly_info = {
            'is_weekly_flat_rate': True,
            'weeks': 2,
            'weekly_rate': 4000.0,
            'period_start': '2025-01-20',
            'period_end': '2025-02-02',
        }

        result = invoice_bridge.create_invoice(
            client=client, entries=entries,
            description="Biweekly services",
            payment_terms="Net 30", payment_method="ACH",
            weekly_flat_rate_info=weekly_info,
        )
        assert result['success']

        # Generate PDF
        pdf_path = generate_invoice_pdf(result['invoice_number'])
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0


class TestWeeklyBreakdown:
    """Test weekly breakdown grouping from invoice_hours."""

    def test_get_weekly_breakdown_two_weeks(self, temp_db):
        """Groups daily hours into weekly buckets with date ranges."""
        inv_num = _setup_weekly_flat_rate_invoice(temp_db)
        breakdown = db.get_weekly_breakdown(inv_num)

        assert len(breakdown) == 2
        # Week 1: Jan 20-26
        assert breakdown[0]['week_start'] == '2025-01-20'
        assert breakdown[0]['week_end'] == '2025-01-26'
        assert breakdown[0]['hours'] == pytest.approx(8.0)
        # Week 2: Jan 27 - Feb 2
        assert breakdown[1]['week_start'] == '2025-01-27'
        assert breakdown[1]['week_end'] == '2025-02-02'
        assert breakdown[1]['hours'] == pytest.approx(8.0)

    def test_get_weekly_breakdown_multiple_days_same_week(self, temp_db):
        """Multiple entries in one week are summed together."""
        # Setup business + banking
        db.save_business_info({
            'company_name': 'Test LLC', 'owner_name': 'Test Owner',
            'address': '123 Test St', 'city': 'Testville', 'state': 'TX',
            'zip': '75001', 'phone': '555-0100', 'email': 'test@test.com',
            'ein': '12-3456789',
        })
        db.save_banking({
            'bank_name': 'Test Bank', 'routing_number': '111000025',
            'account_number': '123456789',
        })

        client_id = db.save_client("WC", "WCo", 100.0,
                                   weekly_flat_rate_settings={'enabled': True, 'rate': 3000.0})
        client = db.get_client(client_id)

        # Three entries: Mon, Tue, Wed of same week + one entry next week
        db.save_time_entry(client_id, datetime(2025, 1, 20, 9, 0, 0), duration_seconds=6 * 3600)
        db.save_time_entry(client_id, datetime(2025, 1, 21, 9, 0, 0), duration_seconds=7 * 3600)
        db.save_time_entry(client_id, datetime(2025, 1, 22, 9, 0, 0), duration_seconds=5 * 3600)
        db.save_time_entry(client_id, datetime(2025, 1, 27, 9, 0, 0), duration_seconds=8 * 3600)
        entries = db.get_time_entries(client_id=client_id, invoiced=False)

        result = invoice_bridge.create_invoice(
            client=client, entries=entries,
            description="Multi-day test",
            payment_terms="Net 30", payment_method="ACH",
            weekly_flat_rate_info={
                'is_weekly_flat_rate': True, 'weeks': 2,
                'weekly_rate': 3000.0,
                'period_start': '2025-01-20', 'period_end': '2025-02-02',
            },
        )
        assert result['success']

        breakdown = db.get_weekly_breakdown(result['invoice_number'])
        assert len(breakdown) == 2
        assert breakdown[0]['hours'] == pytest.approx(18.0)  # 6+7+5
        assert breakdown[1]['hours'] == pytest.approx(8.0)

    def test_get_weekly_breakdown_empty(self, temp_db):
        """Returns empty list for invoice with no hours."""
        # Create a bare invoice directly
        client_id = db.save_client("E", "ECo", 100.0)
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (invoice_number, client_id, date_issued, due_date,
                                  description, billing_type, rate, quantity, total,
                                  payment_terms, payment_method, status)
            VALUES ('INV-EMPTY', ?, '2025-01-01', '2025-01-31', 'Test', 'weekly_flat',
                    4000, 0, 0, 'Net 30', 'ACH', 'unpaid')
        """, (client_id,))
        conn.commit()
        conn.close()

        breakdown = db.get_weekly_breakdown('INV-EMPTY')
        assert breakdown == []
