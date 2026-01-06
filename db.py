"""Database operations for timer tool - self-contained."""

import sqlite3
import sys
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path


def get_app_dir() -> Path:
    """Get the application directory."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


def get_data_dir() -> Path:
    """Get the data directory (creates if needed)."""
    data_dir = get_app_dir() / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_backups_dir() -> Path:
    """Get the backups directory (creates if needed)."""
    backups_dir = get_data_dir() / "backups"
    backups_dir.mkdir(exist_ok=True)
    return backups_dir


def backup_database(keep_count: int = 10) -> Optional[Path]:
    """Create a backup of the database, keeping only the last N backups. Returns backup path."""
    import shutil

    db_path = get_db_path()
    if not db_path.exists():
        return None  # No database yet

    # Check for custom backup location
    custom_location = get_setting('backup_location', '')
    if custom_location and Path(custom_location).exists():
        backups_dir = Path(custom_location)
    else:
        backups_dir = get_backups_dir()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"invoices_{timestamp}.db"
    backup_path = backups_dir / backup_name

    # Copy the database
    try:
        shutil.copy2(db_path, backup_path)
    except Exception:
        return None  # Silently fail if backup fails

    # Clean up old backups (keep only the most recent N)
    backups = sorted(backups_dir.glob("invoices_*.db"), reverse=True)
    for old_backup in backups[keep_count:]:
        try:
            old_backup.unlink()
        except Exception:
            pass  # Ignore deletion errors

    return backup_path


def _log_error(message: str):
    """Log error to backup_errors.log in data dir."""
    try:
        log_path = get_data_dir() / "backup_errors.log"
        with open(log_path, 'a') as f:
            f.write(f"{datetime.now().isoformat()} - {message}\n")
    except Exception:
        pass  # Can't even log, give up


def upload_to_s3(file_path: Path) -> bool:
    """Upload a file to S3. Returns True if successful."""
    bucket = get_setting('s3_bucket', '')
    region = get_setting('s3_region', '')
    access_key = get_setting('s3_access_key', '')
    secret_key = get_setting('s3_secret_key', '')

    if not all([bucket, region, access_key, secret_key]):
        _log_error(f"S3 not configured - bucket={bool(bucket)}, region={bool(region)}, access_key={bool(access_key)}, secret_key={bool(secret_key)}")
        return False

    try:
        import boto3
        from botocore.config import Config

        config = Config(
            region_name=region,
            s3={'use_accelerate_endpoint': False}
        )
        s3 = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=config
        )

        # Upload with the same filename
        s3_key = f"timertool-backups/{file_path.name}"
        s3.upload_file(str(file_path), bucket, s3_key)

        # Clean up old S3 backups (keep last 10)
        response = s3.list_objects_v2(Bucket=bucket, Prefix='timertool-backups/')
        if 'Contents' in response:
            objects = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
            for obj in objects[10:]:
                s3.delete_object(Bucket=bucket, Key=obj['Key'])

        return True
    except ImportError as e:
        _log_error(f"boto3 not installed: {e}")
        return False
    except Exception as e:
        _log_error(f"S3 upload failed: {type(e).__name__}: {e}")
        return False


def get_invoices_dir() -> Path:
    """Get the invoices directory (creates if needed)."""
    invoices_dir = get_app_dir() / "invoices"
    invoices_dir.mkdir(exist_ok=True)
    return invoices_dir


def get_pdfs_dir() -> Path:
    """Alias for get_invoices_dir for compatibility."""
    return get_invoices_dir()


DB_PATH = None


def get_db_path() -> Path:
    """Get the database path."""
    global DB_PATH
    if DB_PATH is None:
        DB_PATH = get_data_dir() / "invoices.db"
    return DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize all database tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Business info (from invoices system)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS business_info (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            company_name TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            ein TEXT NOT NULL
        )
    """)

    # Banking info - check for new columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banking (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            bank_name TEXT NOT NULL,
            routing_number TEXT NOT NULL,
            account_number TEXT NOT NULL,
            wire_instructions TEXT
        )
    """)
    # Add international wire columns if not present
    cursor.execute("PRAGMA table_info(banking)")
    banking_cols = [row[1] for row in cursor.fetchall()]
    if 'swift_code' not in banking_cols:
        cursor.execute("ALTER TABLE banking ADD COLUMN swift_code TEXT")
    if 'intl_wire_instructions' not in banking_cols:
        cursor.execute("ALTER TABLE banking ADD COLUMN intl_wire_instructions TEXT")
    if 'domestic_wire_instructions' not in banking_cols:
        cursor.execute("ALTER TABLE banking ADD COLUMN domestic_wire_instructions TEXT")
    if 'paypal_email' not in banking_cols:
        cursor.execute("ALTER TABLE banking ADD COLUMN paypal_email TEXT")
    if 'credit_card_instructions' not in banking_cols:
        cursor.execute("ALTER TABLE banking ADD COLUMN credit_card_instructions TEXT")

    # Clients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            contact_name TEXT,
            bill_to TEXT,
            address TEXT,
            address2 TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            email TEXT,
            payment_preference TEXT,
            hourly_rate REAL DEFAULT 0,
            favorite INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            track_activity INTEGER DEFAULT 1
        )
    """)
    # Add columns if not present (for migration from old schema)
    cursor.execute("PRAGMA table_info(clients)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'hourly_rate' not in columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN hourly_rate REAL DEFAULT 0")
    if 'favorite' not in columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN favorite INTEGER DEFAULT 0")
    if 'archived' not in columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN archived INTEGER DEFAULT 0")
    if 'track_activity' not in columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN track_activity INTEGER DEFAULT 1")
    if 'capture_screenshots' not in columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN capture_screenshots INTEGER DEFAULT 0")
    if 'bill_to' not in columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN bill_to TEXT")
    if 'address2' not in columns:
        cursor.execute("ALTER TABLE clients ADD COLUMN address2 TEXT")

    # Invoices (from invoices system)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            client_id INTEGER NOT NULL,
            date_issued TEXT NOT NULL,
            due_date TEXT NOT NULL,
            description TEXT NOT NULL,
            billing_type TEXT NOT NULL,
            rate REAL NOT NULL,
            quantity REAL,
            total REAL NOT NULL,
            payment_terms TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT DEFAULT 'unpaid',
            date_paid TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)
    # Add amount_paid column if not present
    cursor.execute("PRAGMA table_info(invoices)")
    inv_cols = [row[1] for row in cursor.fetchall()]
    if 'amount_paid' not in inv_cols:
        cursor.execute("ALTER TABLE invoices ADD COLUMN amount_paid REAL DEFAULT 0")

    # Invoice hours breakdown
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_hours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT NOT NULL,
            work_date TEXT NOT NULL,
            hours REAL NOT NULL,
            FOREIGN KEY (invoice_number) REFERENCES invoices(invoice_number)
        )
    """)

    # Time entries (timer-specific)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER,
            description TEXT,
            entry_type TEXT DEFAULT 'stopwatch',
            invoiced INTEGER DEFAULT 0,
            invoice_number TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)
    # Add activity tracking columns if not present
    cursor.execute("PRAGMA table_info(time_entries)")
    entry_cols = [row[1] for row in cursor.fetchall()]
    if 'key_presses' not in entry_cols:
        cursor.execute("ALTER TABLE time_entries ADD COLUMN key_presses INTEGER DEFAULT 0")
    if 'mouse_clicks' not in entry_cols:
        cursor.execute("ALTER TABLE time_entries ADD COLUMN mouse_clicks INTEGER DEFAULT 0")
    if 'mouse_moves' not in entry_cols:
        cursor.execute("ALTER TABLE time_entries ADD COLUMN mouse_moves INTEGER DEFAULT 0")

    # Active timer state (crash recovery)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_timer (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            client_id INTEGER,
            start_time TEXT,
            last_save_time TEXT,
            accumulated_seconds INTEGER DEFAULT 0
        )
    """)

    # Screenshots (proof of work)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            time_entry_id INTEGER,
            captured_at TEXT NOT NULL,
            file_path TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id),
            FOREIGN KEY (time_entry_id) REFERENCES time_entries(id)
        )
    """)

    # Settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Insert default settings if not exist
    defaults = {
        'inactivity_timeout_minutes': '10',
        'auto_save_interval_seconds': '30',
    }
    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )

    conn.commit()
    conn.close()


# === Settings ===

def get_setting(key: str, default: str = '') -> str:
    """Get a setting value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key: str, value: str):
    """Set a setting value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


# === Business Info ===

def get_business_info() -> Optional[Dict]:
    """Get business info or None if not set."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM business_info WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_business_info(data: Dict):
    """Save or update business info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO business_info
        (id, company_name, owner_name, address, city, state, zip, phone, email, ein)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data['company_name'], data['owner_name'], data['address'],
          data['city'], data['state'], data['zip'], data['phone'],
          data['email'], data['ein']))
    conn.commit()
    conn.close()


# === Banking ===

def get_banking() -> Optional[Dict]:
    """Get banking info or None if not set."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM banking WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_banking(data: Dict):
    """Save or update banking info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO banking
        (id, bank_name, routing_number, account_number, wire_instructions, swift_code, intl_wire_instructions)
        VALUES (1, ?, ?, ?, ?, ?, ?)
    """, (data['bank_name'], data['routing_number'],
          data['account_number'], data.get('wire_instructions'),
          data.get('swift_code'), data.get('intl_wire_instructions')))
    conn.commit()
    conn.close()


# === Clients ===

def get_clients(include_archived: bool = False) -> List[Dict]:
    """Get all clients. Favorites pinned at top."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT id, company_name, contact_name, email,
               COALESCE(hourly_rate, 0) as hourly_rate, payment_preference,
               COALESCE(favorite, 0) as favorite, COALESCE(archived, 0) as archived,
               COALESCE(track_activity, 1) as track_activity,
               COALESCE(capture_screenshots, 0) as capture_screenshots
        FROM clients
    """
    if not include_archived:
        query += " WHERE COALESCE(archived, 0) = 0"
    query += " ORDER BY COALESCE(favorite, 0) DESC, COALESCE(company_name, contact_name)"
    cursor.execute(query)
    rows = cursor.fetchall()
    clients = []
    for row in rows:
        client = dict(row)
        # Display name: prefer contact_name, fall back to company_name
        client['name'] = client['contact_name'] or client['company_name'] or ''
        client['display_name'] = _format_client_display(client['contact_name'], client['company_name'])
        clients.append(client)
    conn.close()
    return clients


def _format_client_display(contact_name: str, company_name: str) -> str:
    """Format client display name from contact and company."""
    contact = (contact_name or '').strip()
    company = (company_name or '').strip()
    if contact and company:
        return f"{contact} ({company})"
    return contact or company or ''


def get_client(client_id: int) -> Optional[Dict]:
    """Get client by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, company_name, contact_name, email,
               COALESCE(hourly_rate, 0) as hourly_rate, payment_preference,
               COALESCE(favorite, 0) as favorite, COALESCE(archived, 0) as archived,
               COALESCE(track_activity, 1) as track_activity,
               COALESCE(capture_screenshots, 0) as capture_screenshots
        FROM clients WHERE id = ?
    """, (client_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        client = dict(row)
        client['name'] = client['contact_name'] or client['company_name'] or ''
        client['display_name'] = _format_client_display(client['contact_name'], client['company_name'])
        return client
    return None


def toggle_client_favorite(client_id: int) -> bool:
    """Toggle client favorite status. Returns new status."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(favorite, 0) FROM clients WHERE id = ?", (client_id,))
    current = cursor.fetchone()[0]
    new_val = 0 if current else 1
    cursor.execute("UPDATE clients SET favorite = ? WHERE id = ?", (new_val, client_id))
    conn.commit()
    conn.close()
    return bool(new_val)


def archive_client(client_id: int):
    """Archive (soft delete) a client."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE clients SET archived = 1 WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()


def unarchive_client(client_id: int):
    """Restore an archived client."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE clients SET archived = 0 WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()


def delete_client(client_id: int):
    """Permanently delete a client (only if no time entries)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM time_entries WHERE client_id = ?", (client_id,))
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        raise ValueError(f"Cannot delete: has {count} time entries. Archive instead.")
    cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()


def save_client(contact_name: str, company_name: str, hourly_rate: float,
                track_activity: bool = True, capture_screenshots: bool = False) -> int:
    """Save new client, return ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO clients (company_name, contact_name, address, city, state, zip, email,
                            hourly_rate, track_activity, capture_screenshots)
        VALUES (?, ?, '', '', '', '', '', ?, ?, ?)
    """, (company_name, contact_name, hourly_rate,
          1 if track_activity else 0, 1 if capture_screenshots else 0))
    client_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return client_id


def update_client(client_id: int, contact_name: str, company_name: str, hourly_rate: float,
                  track_activity: bool = True, capture_screenshots: bool = False):
    """Update existing client."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE clients SET contact_name = ?, company_name = ?, hourly_rate = ?,
           track_activity = ?, capture_screenshots = ? WHERE id = ?""",
        (contact_name, company_name, hourly_rate,
         1 if track_activity else 0, 1 if capture_screenshots else 0, client_id)
    )
    conn.commit()
    conn.close()


def update_client_billing(client_id: int, bill_to: str, address: str, address2: str,
                          city: str, state: str, zip_code: str,
                          email: str, payment_preference: str):
    """Update client billing/invoice info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE clients
        SET bill_to = ?, address = ?, address2 = ?, city = ?, state = ?, zip = ?,
            email = ?, payment_preference = ?
        WHERE id = ?
    """, (bill_to, address, address2, city, state, zip_code, email, payment_preference, client_id))
    conn.commit()
    conn.close()


# === Invoices ===

def get_next_invoice_number() -> str:
    """Generate next invoice number."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id) FROM invoices")
    result = cursor.fetchone()[0]
    conn.close()
    next_num = (result or 0) + 1
    return f"INV-{next_num:04d}"


def get_invoice(invoice_number: str) -> Optional[Dict]:
    """Get invoice by number with client info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.*, c.company_name as client_name, c.contact_name,
               c.bill_to, c.address as client_address, c.address2 as client_address2,
               c.city as client_city, c.state as client_state, c.zip as client_zip,
               c.email as client_email
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE i.invoice_number = ?
    """, (invoice_number,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_invoices(limit: int = 20) -> List[Dict]:
    """Get recent invoices with client info."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.*, c.company_name as client_name
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        ORDER BY i.date_issued DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_invoice_hours(invoice_number: str) -> List[Dict]:
    """Get daily hours for an invoice."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT work_date, hours FROM invoice_hours
        WHERE invoice_number = ?
        ORDER BY work_date
    """, (invoice_number,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def record_payment(invoice_number: str, amount: float, date_paid: Optional[str] = None):
    """Record a payment for an invoice. Updates status if fully paid."""
    if date_paid is None:
        date_paid = datetime.now().strftime('%Y-%m-%d')

    conn = get_connection()
    cursor = conn.cursor()

    # Get current invoice
    cursor.execute("SELECT total, COALESCE(amount_paid, 0) as paid FROM invoices WHERE invoice_number = ?",
                   (invoice_number,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    total = row['total']
    current_paid = row['paid']
    new_paid = current_paid + amount

    # Determine status
    if new_paid >= total:
        status = 'paid'
    elif new_paid > 0:
        status = 'partial'
    else:
        status = 'unpaid'

    cursor.execute("""
        UPDATE invoices SET amount_paid = ?, status = ?, date_paid = ?
        WHERE invoice_number = ?
    """, (new_paid, status, date_paid if status == 'paid' else None, invoice_number))
    conn.commit()
    conn.close()


def mark_invoice_paid(invoice_number: str, date_paid: Optional[str] = None):
    """Mark an invoice as fully paid."""
    if date_paid is None:
        date_paid = datetime.now().strftime('%Y-%m-%d')

    conn = get_connection()
    cursor = conn.cursor()

    # Get total and set amount_paid to match
    cursor.execute("SELECT total FROM invoices WHERE invoice_number = ?", (invoice_number,))
    row = cursor.fetchone()
    if row:
        cursor.execute("""
            UPDATE invoices SET status = 'paid', date_paid = ?, amount_paid = ?
            WHERE invoice_number = ?
        """, (date_paid, row['total'], invoice_number))
        conn.commit()
    conn.close()

    # Clean up screenshots for this invoice's time entries
    cleanup_paid_invoice_screenshots(invoice_number)


def get_invoice_pdf_path(invoice_number: str) -> Optional[Path]:
    """Get the path to an invoice PDF if it exists."""
    invoice = get_invoice(invoice_number)
    if not invoice:
        return None
    client_folder = get_invoices_dir() / invoice['client_name'].replace(' ', '_')
    pdf_path = client_folder / f"{invoice_number}.pdf"
    if pdf_path.exists():
        return pdf_path
    return None


# === Time Entries ===

def save_time_entry(
    client_id: int,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    duration_seconds: Optional[int] = None,
    description: str = '',
    entry_type: str = 'stopwatch',
    key_presses: int = 0,
    mouse_clicks: int = 0,
    mouse_moves: int = 0
) -> int:
    """Save a time entry, return ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO time_entries
        (client_id, start_time, end_time, duration_seconds, description, entry_type, created_at,
         key_presses, mouse_clicks, mouse_moves)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        start_time.isoformat(),
        end_time.isoformat() if end_time else None,
        duration_seconds,
        description,
        entry_type,
        datetime.now().isoformat(),
        key_presses,
        mouse_clicks,
        mouse_moves
    ))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id


def update_time_entry(
    entry_id: int,
    end_time: Optional[datetime] = None,
    duration_seconds: Optional[int] = None,
    description: Optional[str] = None
):
    """Update a time entry."""
    conn = get_connection()
    cursor = conn.cursor()

    updates = []
    values = []
    if end_time is not None:
        updates.append("end_time = ?")
        values.append(end_time.isoformat())
    if duration_seconds is not None:
        updates.append("duration_seconds = ?")
        values.append(duration_seconds)
    if description is not None:
        updates.append("description = ?")
        values.append(description)

    if updates:
        values.append(entry_id)
        cursor.execute(
            f"UPDATE time_entries SET {', '.join(updates)} WHERE id = ?",
            values
        )
        conn.commit()
    conn.close()


def mark_entries_invoiced(entry_ids: List[int], invoice_number: str):
    """Mark time entries as invoiced."""
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(entry_ids))
    cursor.execute(f"""
        UPDATE time_entries
        SET invoiced = 1, invoice_number = ?
        WHERE id IN ({placeholders})
    """, [invoice_number] + entry_ids)
    conn.commit()
    conn.close()


def delete_time_entry(entry_id: int) -> bool:
    """Delete a time entry. Returns True if deleted, False if invoiced."""
    conn = get_connection()
    cursor = conn.cursor()
    # Check if invoiced
    cursor.execute("SELECT invoiced FROM time_entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    if row['invoiced']:
        conn.close()
        raise ValueError("Cannot delete invoiced time entry")
    cursor.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return True


def get_time_entry(entry_id: int) -> Optional[Dict]:
    """Get a single time entry by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_first_uninvoiced_date(client_id: Optional[int] = None) -> Optional[str]:
    """Get the earliest date with uninvoiced time entries."""
    conn = get_connection()
    cursor = conn.cursor()
    if client_id:
        cursor.execute("""
            SELECT MIN(date(start_time)) as first_date
            FROM time_entries
            WHERE client_id = ? AND invoiced = 0 AND duration_seconds IS NOT NULL
        """, (client_id,))
    else:
        cursor.execute("""
            SELECT MIN(date(start_time)) as first_date
            FROM time_entries
            WHERE invoiced = 0 AND duration_seconds IS NOT NULL
        """)
    row = cursor.fetchone()
    conn.close()
    return row['first_date'] if row else None


def get_time_entries(
    client_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    invoiced: Optional[bool] = None,
    limit: Optional[int] = None
) -> List[Dict]:
    """Get time entries with optional filters."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM time_entries WHERE 1=1"
    params = []

    if client_id is not None:
        query += " AND client_id = ?"
        params.append(client_id)
    if start_date is not None:
        query += " AND start_time >= ?"
        params.append(start_date.isoformat())
    if end_date is not None:
        query += " AND start_time < ?"
        params.append(end_date.isoformat())
    if invoiced is not None:
        query += " AND invoiced = ?"
        params.append(1 if invoiced else 0)

    query += " ORDER BY start_time DESC"

    if limit is not None:
        query += f" LIMIT {int(limit)}"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_global_time_summary() -> Dict[str, float]:
    """Get global time summary across all clients."""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_monday = now.weekday()
    week_start = (today_start - timedelta(days=days_since_monday))

    # Today (all clients)
    cursor.execute("""
        SELECT COALESCE(SUM(duration_seconds), 0) as total
        FROM time_entries
        WHERE start_time >= ? AND duration_seconds IS NOT NULL
    """, (today_start.isoformat(),))
    today_seconds = cursor.fetchone()['total']

    # This week (all clients)
    cursor.execute("""
        SELECT COALESCE(SUM(duration_seconds), 0) as total
        FROM time_entries
        WHERE start_time >= ? AND duration_seconds IS NOT NULL
    """, (week_start.isoformat(),))
    week_seconds = cursor.fetchone()['total']

    # Uninvoiced (all clients)
    cursor.execute("""
        SELECT COALESCE(SUM(duration_seconds), 0) as total
        FROM time_entries
        WHERE invoiced = 0 AND duration_seconds IS NOT NULL
    """)
    uninvoiced_seconds = cursor.fetchone()['total']

    # Invoiced (not yet paid) - from invoice_hours for unpaid invoices
    cursor.execute("""
        SELECT COALESCE(SUM(ih.hours), 0) as total
        FROM invoice_hours ih
        JOIN invoices i ON ih.invoice_number = i.invoice_number
        WHERE i.status != 'paid'
    """)
    invoiced_hours = cursor.fetchone()['total']

    # Paid - from invoice_hours for paid invoices
    cursor.execute("""
        SELECT COALESCE(SUM(ih.hours), 0) as total
        FROM invoice_hours ih
        JOIN invoices i ON ih.invoice_number = i.invoice_number
        WHERE i.status = 'paid'
    """)
    paid_hours = cursor.fetchone()['total']

    # Invoice amounts (includes flat rate invoices)
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as total
        FROM invoices WHERE status != 'paid'
    """)
    invoiced_amount = cursor.fetchone()['total']

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as total
        FROM invoices WHERE status = 'paid'
    """)
    paid_amount = cursor.fetchone()['total']

    conn.close()

    return {
        'today_hours': today_seconds / 3600,
        'week_hours': week_seconds / 3600,
        'uninvoiced_hours': uninvoiced_seconds / 3600,
        'invoiced_hours': invoiced_hours,
        'paid_hours': paid_hours,
        'invoiced_amount': invoiced_amount,
        'paid_amount': paid_amount,
    }


def get_time_summary(client_id: int) -> Dict[str, float]:
    """Get time summary for a client: today, this week, uninvoiced, invoiced."""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Week starts on Monday
    days_since_monday = now.weekday()
    week_start = (today_start - timedelta(days=days_since_monday))

    # Today
    cursor.execute("""
        SELECT COALESCE(SUM(duration_seconds), 0) as total
        FROM time_entries
        WHERE client_id = ? AND start_time >= ? AND duration_seconds IS NOT NULL
    """, (client_id, today_start.isoformat()))
    today_seconds = cursor.fetchone()['total']

    # This week
    cursor.execute("""
        SELECT COALESCE(SUM(duration_seconds), 0) as total
        FROM time_entries
        WHERE client_id = ? AND start_time >= ? AND duration_seconds IS NOT NULL
    """, (client_id, week_start.isoformat()))
    week_seconds = cursor.fetchone()['total']

    # Uninvoiced
    cursor.execute("""
        SELECT COALESCE(SUM(duration_seconds), 0) as total
        FROM time_entries
        WHERE client_id = ? AND invoiced = 0 AND duration_seconds IS NOT NULL
    """, (client_id,))
    uninvoiced_seconds = cursor.fetchone()['total']

    # Invoiced (not yet paid) - from invoice_hours for this client's unpaid invoices
    cursor.execute("""
        SELECT COALESCE(SUM(ih.hours), 0) as total
        FROM invoice_hours ih
        JOIN invoices i ON ih.invoice_number = i.invoice_number
        WHERE i.client_id = ? AND i.status != 'paid'
    """, (client_id,))
    invoiced_hours = cursor.fetchone()['total']

    # Paid - from invoice_hours for this client's paid invoices
    cursor.execute("""
        SELECT COALESCE(SUM(ih.hours), 0) as total
        FROM invoice_hours ih
        JOIN invoices i ON ih.invoice_number = i.invoice_number
        WHERE i.client_id = ? AND i.status = 'paid'
    """, (client_id,))
    paid_hours = cursor.fetchone()['total']

    # Invoice amounts (includes flat rate invoices)
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as total
        FROM invoices WHERE client_id = ? AND status != 'paid'
    """, (client_id,))
    invoiced_amount = cursor.fetchone()['total']

    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) as total
        FROM invoices WHERE client_id = ? AND status = 'paid'
    """, (client_id,))
    paid_amount = cursor.fetchone()['total']

    conn.close()

    return {
        'today_hours': today_seconds / 3600,
        'week_hours': week_seconds / 3600,
        'uninvoiced_hours': uninvoiced_seconds / 3600,
        'invoiced_hours': invoiced_hours,
        'paid_hours': paid_hours,
        'invoiced_amount': invoiced_amount,
        'paid_amount': paid_amount,
    }


# === Active Timer (crash recovery) ===

def save_active_timer(client_id: int, start_time: datetime, accumulated_seconds: int = 0):
    """Save active timer state for crash recovery."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO active_timer
        (id, client_id, start_time, last_save_time, accumulated_seconds)
        VALUES (1, ?, ?, ?, ?)
    """, (
        client_id,
        start_time.isoformat(),
        datetime.now().isoformat(),
        accumulated_seconds
    ))
    conn.commit()
    conn.close()


def update_active_timer(accumulated_seconds: int):
    """Update active timer with current accumulated time."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE active_timer
        SET last_save_time = ?, accumulated_seconds = ?
        WHERE id = 1
    """, (datetime.now().isoformat(), accumulated_seconds))
    conn.commit()
    conn.close()


def get_active_timer() -> Optional[Dict]:
    """Get active timer state if exists."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_timer WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def clear_active_timer():
    """Clear active timer state."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_timer WHERE id = 1")
    conn.commit()
    conn.close()


# === Screenshots ===

def get_screenshots_dir() -> Path:
    """Get the screenshots directory (creates if needed)."""
    screenshots_dir = get_data_dir() / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)
    return screenshots_dir


def save_screenshot(client_id: int, file_path: str) -> int:
    """Save a screenshot record, return ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO screenshots (client_id, captured_at, file_path)
        VALUES (?, ?, ?)
    """, (client_id, datetime.now().isoformat(), file_path))
    screenshot_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return screenshot_id


def link_screenshots_to_entry(screenshot_ids: List[int], entry_id: int):
    """Link screenshots to a time entry."""
    if not screenshot_ids:
        return
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(screenshot_ids))
    cursor.execute(f"""
        UPDATE screenshots SET time_entry_id = ?
        WHERE id IN ({placeholders})
    """, [entry_id] + screenshot_ids)
    conn.commit()
    conn.close()


def delete_screenshot(screenshot_id: int) -> Optional[str]:
    """Delete a screenshot record and return the file path for deletion."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM screenshots WHERE id = ?", (screenshot_id,))
    row = cursor.fetchone()
    if row:
        file_path = row['file_path']
        cursor.execute("DELETE FROM screenshots WHERE id = ?", (screenshot_id,))
        conn.commit()
        conn.close()
        return file_path
    conn.close()
    return None


def cleanup_paid_invoice_screenshots(invoice_number: str):
    """Delete screenshot files and records for entries in this invoice."""
    conn = get_connection()
    cursor = conn.cursor()

    # Find all screenshots linked to time entries with this invoice_number
    cursor.execute("""
        SELECT s.id, s.file_path
        FROM screenshots s
        JOIN time_entries te ON s.time_entry_id = te.id
        WHERE te.invoice_number = ?
    """, (invoice_number,))

    for row in cursor.fetchall():
        # Delete file
        try:
            Path(row['file_path']).unlink(missing_ok=True)
        except Exception:
            pass
        # Delete record
        cursor.execute("DELETE FROM screenshots WHERE id = ?", (row['id'],))

    conn.commit()
    conn.close()


# === Outstanding Invoices (for statements) ===

def get_outstanding_invoices(client_id: int) -> List[Dict[str, Any]]:
    """Get all unpaid or partially paid invoices for a client."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            invoice_number,
            date_issued,
            due_date,
            description,
            total,
            COALESCE(amount_paid, 0) as amount_paid,
            status
        FROM invoices
        WHERE client_id = ? AND status != 'paid'
        ORDER BY date_issued
    """, (client_id,))
    invoices = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Calculate outstanding balance for each
    for inv in invoices:
        inv['outstanding'] = inv['total'] - inv['amount_paid']

    return invoices


def get_outstanding_balance(client_id: int) -> float:
    """Get total outstanding balance for a client across all unpaid invoices."""
    invoices = get_outstanding_invoices(client_id)
    return sum(inv['outstanding'] for inv in invoices)


# === Tax Year Summary ===

def get_tax_year_summary(year: int) -> Dict[str, Any]:
    """Get income summary for a tax year (based on payment date)."""
    conn = get_connection()
    cursor = conn.cursor()

    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"

    # Get all invoices with payments for the year, grouped by client
    # Use amount_paid (what was actually received) - includes partial payments
    cursor.execute("""
        SELECT
            c.id as client_id,
            COALESCE(c.contact_name, c.company_name) as client_name,
            c.company_name,
            SUM(i.amount_paid) as total_paid,
            COUNT(i.id) as invoice_count
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE i.amount_paid > 0
          AND i.date_paid >= ? AND i.date_paid <= ?
        GROUP BY c.id
        ORDER BY total_paid DESC
    """, (year_start, year_end))
    by_client = [dict(row) for row in cursor.fetchall()]

    # Get individual invoice details (any with payments)
    cursor.execute("""
        SELECT
            i.invoice_number,
            i.client_id,
            COALESCE(c.contact_name, c.company_name) as client_name,
            i.date_issued,
            i.date_paid,
            i.amount_paid as total,
            i.total as invoice_total,
            i.status,
            i.description
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE i.amount_paid > 0
          AND i.date_paid >= ? AND i.date_paid <= ?
        ORDER BY i.date_paid
    """, (year_start, year_end))
    invoices = [dict(row) for row in cursor.fetchall()]

    # Total
    total_income = sum(c['total_paid'] for c in by_client)

    # Quarterly totals (for estimated tax purposes)
    quarters = {}
    for q in range(1, 5):
        if q == 1:
            q_start, q_end = f"{year}-01-01", f"{year}-03-31"
        elif q == 2:
            q_start, q_end = f"{year}-04-01", f"{year}-06-30"
        elif q == 3:
            q_start, q_end = f"{year}-07-01", f"{year}-09-30"
        else:
            q_start, q_end = f"{year}-10-01", f"{year}-12-31"

        cursor.execute("""
            SELECT COALESCE(SUM(amount_paid), 0) as total
            FROM invoices
            WHERE amount_paid > 0
              AND date_paid >= ? AND date_paid <= ?
        """, (q_start, q_end))
        quarters[f"q{q}"] = cursor.fetchone()['total']

    conn.close()

    return {
        'year': year,
        'total_income': total_income,
        'by_client': by_client,
        'invoices': invoices,
        'quarters': quarters
    }


# === Helpers ===

def format_currency(amount: float) -> str:
    """Format amount as currency."""
    return f"${amount:,.2f}"


def format_date_display(iso_date: str) -> str:
    """Format ISO date for display (Month DD, YYYY)."""
    dt = datetime.fromisoformat(iso_date)
    return dt.strftime("%B %d, %Y")


# Initialize on import
init_db()
