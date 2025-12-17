# Timer Tool

Self-contained time tracking app with invoice generation.

## Setup (Run from Source)

1. Copy the entire `timertool` folder to Windows
2. Open Command Prompt in that folder
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
4. Run:
   ```cmd
   python main.py
   ```

## First Time Setup

1. Go to **Edit > Business Setup**
2. Fill in your business info (name, address, phone, email, EIN)
3. Fill in your banking info (for invoice payment instructions)
4. Add clients with their hourly rates

## Build Standalone EXE

```cmd
pip install pyinstaller
pyinstaller TimerTool.spec
```

The exe will be in `dist\TimerTool.exe`. Move it wherever you want - it will create a `data` folder next to it.

## Folder Structure

```
TimerTool/
  TimerTool.exe (or main.py)
  data/
    invoices.db      <- All data stored here
    pdfs/
      ClientName/
        INV-0001.pdf
        INV-0002.pdf
      AnotherClient/
        INV-0003.pdf
```

## Features

- **Stopwatch** - Start/stop/pause timer for selected client
- **Manual Entry** - Add time entries for past work
- **Idle Detection** - Auto-pauses after 10 min of no keyboard/mouse activity
- **Crash Recovery** - Auto-saves every 30 seconds, recovers on restart
- **System Tray** - Minimizes to tray on close
- **Time Summary** - View today, this week, and uninvoiced hours
- **Build Invoice** - Select time entries, set payment terms, generate PDF
- **Open Invoices Folder** - Quick access to generated PDFs
