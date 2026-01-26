"""Tests for invoice creation including retainer billing."""

import pytest
import tempfile
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import invoice_bridge


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


class TestRetainerInvoiceCreation:
    """Test retainer invoice creation."""

    def test_create_regular_invoice(self, temp_db):
        """Test creating a regular (non-retainer) invoice."""
        client_id = db.save_client("Test Client", "Test Co", 100.0)
        client = db.get_client(client_id)

        # Create time entry
        start = datetime(2025, 1, 20, 9, 0, 0)
        entry_id = db.save_time_entry(client_id, start, duration_seconds=10 * 3600)
        entries = db.get_time_entries(client_id=client_id, invoiced=False)

        result = invoice_bridge.create_invoice(
            client=client,
            entries=entries,
            description="January work",
            payment_terms="Net 30",
            payment_method="ACH"
        )

        assert result['success'] == True
        assert result['invoice_number'].startswith('INV-')

        # Check invoice details
        invoice = db.get_invoice(result['invoice_number'])
        assert invoice['quantity'] == 10.0  # hours
        assert invoice['total'] == 1000.0  # 10 * 100
        assert invoice['is_retainer_invoice'] == 0

    def test_create_retainer_invoice_under_minimum(self, temp_db):
        """Test creating retainer invoice when worked hours < minimum."""
        client_id = db.save_client("Retainer Client", "Retainer Co", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 100.0})
        client = db.get_client(client_id)

        # Work 10 hours (under 15 hour minimum)
        start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, start, duration_seconds=10 * 3600)
        entries = db.get_time_entries(client_id=client_id, invoiced=False)

        retainer_info = {
            'is_retainer': True,
            'week_start': '2025-01-20',
            'worked_hours': 10.0,
            'retainer_hours': 15.0,
            'billable_hours': 15.0,
            'retainer_hours_applied': 10.0,
            'overage_hours': 0.0,
            'is_exempted': False,
        }

        result = invoice_bridge.create_invoice(
            client=client,
            entries=entries,
            description="Week of Jan 20-26",
            payment_terms="Net 30",
            payment_method="ACH",
            retainer_info=retainer_info
        )

        assert result['success'] == True

        invoice = db.get_invoice(result['invoice_number'])
        assert invoice['is_retainer_invoice'] == 1
        assert invoice['quantity'] == 15.0  # billable hours (retainer minimum)
        assert invoice['total'] == 1500.0  # 15 * 100
        assert invoice['retainer_hours_applied'] == 10.0
        assert invoice['overage_hours'] == 0.0

    def test_create_retainer_invoice_over_minimum(self, temp_db):
        """Test creating retainer invoice when worked hours > minimum."""
        client_id = db.save_client("Retainer Client", "Retainer Co", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 100.0})
        client = db.get_client(client_id)

        # Work 20 hours (over 15 hour minimum)
        start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, start, duration_seconds=20 * 3600)
        entries = db.get_time_entries(client_id=client_id, invoiced=False)

        retainer_info = {
            'is_retainer': True,
            'week_start': '2025-01-20',
            'worked_hours': 20.0,
            'retainer_hours': 15.0,
            'billable_hours': 20.0,
            'retainer_hours_applied': 15.0,
            'overage_hours': 5.0,
            'is_exempted': False,
        }

        result = invoice_bridge.create_invoice(
            client=client,
            entries=entries,
            description="Week of Jan 20-26",
            payment_terms="Net 30",
            payment_method="ACH",
            retainer_info=retainer_info
        )

        assert result['success'] == True

        invoice = db.get_invoice(result['invoice_number'])
        assert invoice['is_retainer_invoice'] == 1
        assert invoice['quantity'] == 20.0  # all hours billed
        assert invoice['total'] == 2000.0  # 20 * 100
        assert invoice['retainer_hours_applied'] == 15.0
        assert invoice['overage_hours'] == 5.0

    def test_create_retainer_invoice_exempted(self, temp_db):
        """Test creating retainer invoice when week is exempted."""
        client_id = db.save_client("Retainer Client", "Retainer Co", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 100.0})
        client = db.get_client(client_id)

        # Work 10 hours (but week is exempted)
        start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, start, duration_seconds=10 * 3600)
        entries = db.get_time_entries(client_id=client_id, invoiced=False)

        retainer_info = {
            'is_retainer': True,
            'week_start': '2025-01-20',
            'worked_hours': 10.0,
            'retainer_hours': 15.0,
            'billable_hours': 10.0,  # Only actual hours due to exemption
            'retainer_hours_applied': 0.0,
            'overage_hours': 10.0,
            'is_exempted': True,
        }

        result = invoice_bridge.create_invoice(
            client=client,
            entries=entries,
            description="Week of Jan 20-26 (Exempted)",
            payment_terms="Net 30",
            payment_method="ACH",
            retainer_info=retainer_info
        )

        assert result['success'] == True

        invoice = db.get_invoice(result['invoice_number'])
        assert invoice['is_retainer_invoice'] == 1
        assert invoice['quantity'] == 10.0  # only actual hours
        assert invoice['total'] == 1000.0  # 10 * 100

    def test_create_retainer_invoice_uses_retainer_rate(self, temp_db):
        """Test that retainer invoice uses retainer rate when set."""
        # Hourly rate is 100, retainer rate is 150
        client_id = db.save_client("Retainer Client", "Retainer Co", 100.0,
                                   retainer_settings={'enabled': True, 'hours': 15.0, 'rate': 150.0})
        client = db.get_client(client_id)

        start = datetime(2025, 1, 20, 9, 0, 0)
        db.save_time_entry(client_id, start, duration_seconds=15 * 3600)
        entries = db.get_time_entries(client_id=client_id, invoiced=False)

        retainer_info = {
            'is_retainer': True,
            'week_start': '2025-01-20',
            'worked_hours': 15.0,
            'retainer_hours': 15.0,
            'billable_hours': 15.0,
            'retainer_hours_applied': 15.0,
            'overage_hours': 0.0,
            'is_exempted': False,
        }

        result = invoice_bridge.create_invoice(
            client=client,
            entries=entries,
            description="Week of Jan 20-26",
            payment_terms="Net 30",
            payment_method="ACH",
            retainer_info=retainer_info
        )

        assert result['success'] == True

        invoice = db.get_invoice(result['invoice_number'])
        assert invoice['rate'] == 150.0  # Uses retainer rate
        assert invoice['total'] == 2250.0  # 15 * 150


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
