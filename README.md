# Timer Tool

A Windows time tracking application with client management, invoicing, and activity tracking.

## Features

- **Client Management** - Add/edit clients with hourly rates, favorites, archive
- **Stopwatch Timer** - Start/stop/pause with crash recovery
- **Manual Time Entry** - Add time entries manually
- **Activity Tracking** - Optional keyboard/mouse activity logging per client
- **Inactivity Detection** - Auto-pause after configurable idle time
- **Invoice Generation** - Create PDF invoices with hourly breakdown
- **Payment Tracking** - Mark invoices as paid/partially paid
- **Client Statements** - Generate PDF statements for outstanding balances
- **Tax Year Summary** - Quarterly income breakdown with CSV/TXF export
- **Database Backup** - Auto-backup on startup, optional S3 sync
- **System Tray** - Minimize to tray, single instance enforcement
- **Time Summaries** - Today, this week, uninvoiced, unpaid, paid totals

## Requirements

- Python 3.10+
- Windows (for activity tracking and system tray)

## Installation

```bash
# Clone or copy files
cd timertool

# Install dependencies
pip install -r requirements.txt
```

## Running

### From Source
```bash
python main.py
```

### Build Executable
```bash
pip install pyinstaller
pyinstaller TimerTool.spec
# Output: dist/TimerTool.exe

# Move exe to main folder (needs access to data/ and invoices/)
move dist\TimerTool.exe .
```

## Usage

1. **Add a Client** - Click "+ Add Client", enter name and hourly rate
2. **Start Timer** - Select client, click START
3. **Stop Timer** - Click STOP to save time entry
4. **Build Invoice** - Click "Build Invoice" when you have uninvoiced time
5. **View Invoices** - View > Invoices to see all invoices, mark paid

### Keyboard Shortcuts

- Double-click client to edit
- Right-click client for context menu (Edit, Favorite, Delete)

### Menu Options

- **File > Open Invoices Folder** - Open PDF storage location
- **File > Minimize to Tray** - Hide to system tray
- **File > Exit** - Quit application
- **Edit > Business Setup** - Configure your business info for invoices
- **Edit > Settings** - Inactivity timeout, auto-save interval
- **View > Time Entries** - See all time entries with activity stats (CSV export)
- **View > Invoices** - Manage invoices, mark paid
- **View > Tax Year Summary** - Income by quarter, export to CSV or TXF (TurboTax)
- **Right-click Client > Generate Statement** - PDF of outstanding invoices

## Data Storage

All data stored in the `data/` folder:
- `data/invoices.db` - SQLite database
- `invoices/ClientName/` - PDF invoices per client

## Configuration

### Per-Client Settings
- Hourly rate
- Activity tracking on/off

### Global Settings (Edit > Settings)
- Inactivity timeout (minutes)
- Auto-save interval (seconds)
- Backup location (local path)
- S3 backup (bucket, region, access key, secret key)

## Testing

```bash
# Install test dependencies
uv venv
uv pip install pytest

# Run tests
uv run pytest tests/ -v
```

## Project Structure

```
timertool/
├── main.py              # Entry point, system tray
├── db.py                # Database operations
├── timer_engine.py      # Timer logic, activity tracking
├── generate_pdf.py      # PDF invoice generation
├── invoice_bridge.py    # Invoice creation logic
├── ui/
│   ├── main_window.py   # Main layout
│   ├── client_list.py   # Client panel
│   ├── timer_display.py # Stopwatch UI
│   ├── time_summary.py  # Stats display
│   └── dialogs.py       # All dialog windows
├── tests/
│   ├── test_db.py       # Database tests
│   └── test_timer_engine.py
├── data/                # Database (gitignored)
├── invoices/            # PDFs (gitignored)
└── requirements.txt
```

## License

Private use.
