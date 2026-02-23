"""Create invoices from time entries."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import db


def calculate_due_date(terms: str, issue_date: datetime) -> datetime:
    """Calculate due date from payment terms."""
    terms_days = {
        'Due on Receipt': 0,
        'Net 7': 7,
        'Net 15': 15,
        'Net 30': 30
    }
    days = terms_days.get(terms, 30)
    return issue_date + timedelta(days=days)


def create_invoice(
    client: Dict,
    entries: List[Dict],
    description: str,
    payment_terms: str,
    payment_method: str,
    retainer_info: Optional[Dict] = None
) -> Dict:
    """Create an invoice from time entries.

    Args:
        client: Client dict with id, hourly_rate, retainer_enabled, etc.
        entries: List of time entry dicts
        description: Invoice description
        payment_terms: Payment terms string
        payment_method: Payment method string
        retainer_info: Optional dict with retainer billing details:
            - is_retainer: bool
            - week_start: str (YYYY-MM-DD)
            - worked_hours: float
            - retainer_hours: float
            - billable_hours: float
            - retainer_hours_applied: float
            - overage_hours: float
            - is_exempted: bool

    Returns dict with:
        success: bool
        invoice_number: str (if success)
        pdf_path: str (if success and PDF generation available)
        error: str (if not success)
    """
    conn = db.get_connection()

    try:
        cursor = conn.cursor()

        # Calculate totals
        total_seconds = sum(e['duration_seconds'] or 0 for e in entries)
        worked_hours = total_seconds / 3600

        # Determine rate and hours based on retainer status
        is_retainer_invoice = False
        retainer_hours_applied = None
        overage_hours = None

        if retainer_info and retainer_info.get('is_retainer'):
            is_retainer_invoice = True
            rate = client.get('retainer_rate') or client['hourly_rate']
            billable_hours = retainer_info['billable_hours']
            retainer_hours_applied = retainer_info.get('retainer_hours_applied', 0)
            overage_hours = retainer_info.get('overage_hours', 0)
        else:
            rate = client['hourly_rate']
            billable_hours = worked_hours

        billable_hours = round(billable_hours, 2)
        total_amount = round(billable_hours * rate, 2)

        # Generate invoice number and dates
        invoice_number = db.get_next_invoice_number()
        date_issued = datetime.now()
        due_date = calculate_due_date(payment_terms, date_issued)

        # Create invoice record with retainer fields
        cursor.execute("""
            INSERT INTO invoices
            (invoice_number, client_id, date_issued, due_date, description,
             billing_type, rate, quantity, total, payment_terms, payment_method, status,
             is_retainer_invoice, retainer_hours_applied, overage_hours)
            VALUES (?, ?, ?, ?, ?, 'hourly', ?, ?, ?, ?, ?, 'unpaid', ?, ?, ?)
        """, (
            invoice_number,
            client['id'],
            date_issued.strftime('%Y-%m-%d'),
            due_date.strftime('%Y-%m-%d'),
            description,
            rate,
            billable_hours,
            total_amount,
            payment_terms,
            payment_method,
            1 if is_retainer_invoice else 0,
            retainer_hours_applied,
            overage_hours
        ))

        # Aggregate hours by date
        daily_hours = {}
        for entry in entries:
            dt = datetime.fromisoformat(entry['start_time'])
            date_str = dt.strftime('%Y-%m-%d')
            hours = (entry['duration_seconds'] or 0) / 3600
            daily_hours[date_str] = daily_hours.get(date_str, 0) + hours

        # Insert daily hours
        for work_date, hours in sorted(daily_hours.items()):
            cursor.execute("""
                INSERT INTO invoice_hours (invoice_number, work_date, hours)
                VALUES (?, ?, ?)
            """, (invoice_number, work_date, hours))

        conn.commit()
        conn.close()

        # Try to generate PDF
        pdf_path = None
        try:
            from generate_pdf import generate_invoice_pdf
            pdf_path = str(generate_invoice_pdf(invoice_number))
        except ImportError:
            pass  # reportlab not installed
        except Exception as e:
            print(f"PDF generation error: {e}")

        return {
            'success': True,
            'invoice_number': invoice_number,
            'pdf_path': pdf_path
        }

    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}
