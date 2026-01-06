"""Timer display panel with stopwatch."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Callable
from pathlib import Path
import timer_engine
import db


class TimerDisplayPanel(ttk.Frame):
    """Panel showing the stopwatch and controls."""

    # Dark theme colors (sv_ttk compatible)
    BG = '#1c1c1c'
    BG_CARD = '#2a2a2a'
    FG = '#fafafa'
    FG_DIM = '#9e9e9e'
    ACCENT = '#0078d4'

    def __init__(self, parent, engine: timer_engine.TimerEngine):
        super().__init__(parent)
        self.engine = engine
        self.client: Optional[Dict] = None
        self._update_job = None

        # Wire up screenshot callback
        self.engine.on_screenshot = self._on_screenshot

        self._create_widgets()
        self._update_display()

    def _create_widgets(self):
        # Timer display area
        timer_area = tk.Frame(self, bg=self.BG)
        timer_area.pack(fill='both', expand=True)

        # Time display - large and prominent
        self.time_label = tk.Label(
            timer_area,
            text="00:00:00",
            font=('Consolas', 48, 'bold'),
            fg=self.ACCENT,
            bg=self.BG
        )
        self.time_label.pack(pady=(30, 12))

        # Client info
        self.client_label = tk.Label(
            timer_area,
            text="Select a client",
            font=('Segoe UI', 14),
            fg=self.FG,
            bg=self.BG
        )
        self.client_label.pack(pady=4)

        self.rate_label = tk.Label(
            timer_area,
            text="",
            font=('Segoe UI', 10),
            fg=self.FG_DIM,
            bg=self.BG
        )
        self.rate_label.pack(pady=2)

        # Activity stats
        self.activity_label = tk.Label(
            timer_area,
            text="",
            font=('Segoe UI', 9),
            fg='#666666',
            bg=self.BG
        )
        self.activity_label.pack(pady=(8, 16))

        # Control buttons - centered with good spacing
        btn_frame = tk.Frame(self, bg=self.BG)
        btn_frame.pack(fill='x', pady=(0, 16))

        # Center the buttons
        btn_inner = tk.Frame(btn_frame, bg=self.BG)
        btn_inner.pack()

        self.start_btn = ttk.Button(
            btn_inner,
            text="START",
            command=self._on_start_stop,
            width=14,
            style='Accent.TButton'
        )
        self.start_btn.pack(side='left', padx=6)

        self.manual_btn = ttk.Button(
            btn_inner,
            text="+ Manual",
            command=self._on_manual_entry,
            width=12,
            state='disabled'
        )
        self.manual_btn.pack(side='left', padx=6)

    def set_client(self, client: Optional[Dict]):
        """Set the current client."""
        self.client = client

        if client:
            self.client_label.config(text=client['name'])
            self.rate_label.config(text=f"@ ${client['hourly_rate']:.2f}/hr")
            self.manual_btn.config(state='normal')
            if self.engine.state == 'stopped':
                self.start_btn.config(state='normal')
        else:
            self.client_label.config(text="Select a client")
            self.rate_label.config(text="")
            self.manual_btn.config(state='disabled')
            if self.engine.state == 'stopped':
                self.start_btn.config(state='disabled')

    def _on_start_stop(self):
        """Handle start/stop button click."""
        if self.engine.state == 'stopped':
            if self.client:
                track_activity = self.client.get('track_activity', 1)
                capture_screenshots = self.client.get('capture_screenshots', 0)
                self.engine.start(
                    self.client['id'],
                    track_activity=bool(track_activity),
                    capture_screenshots=bool(capture_screenshots)
                )
                self.start_btn.config(text="STOP")
                self._start_update_loop()
        else:
            # Show memo dialog
            memo = self._ask_memo()
            self.engine.stop(description=memo)
            self.start_btn.config(text="START")
            self._stop_update_loop()
            self._update_display()
            # Notify parent to refresh summary
            self.event_generate('<<TimerStopped>>')

    def _ask_memo(self) -> str:
        """Show a simple dialog to enter an optional memo. Pre-fills with last memo for this client."""
        import db
        from tkinter import simpledialog

        # Get last memo for this client
        last_memo = ''
        if self.client:
            entries = db.get_time_entries(client_id=self.client['id'], limit=1)
            if entries and entries[0].get('description'):
                last_memo = entries[0]['description']

        # Simple dialog
        dialog = tk.Toplevel(self)
        dialog.title("Time Entry Memo")
        dialog.configure(bg='#1c1c1c')
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        dialog.geometry('+%d+%d' % (self.winfo_rootx() + 50, self.winfo_rooty() + 50))

        tk.Label(dialog, text="What was this time for? (optional)",
                bg='#1c1c1c', fg='#ffffff', font=('Segoe UI', 10)).pack(padx=15, pady=(15, 5))

        memo_var = tk.StringVar(value=last_memo)
        entry = ttk.Entry(dialog, textvariable=memo_var, width=40)
        entry.pack(padx=15, pady=5)
        entry.select_range(0, tk.END)
        entry.focus_set()

        result = {'memo': last_memo}

        def on_ok(event=None):
            result['memo'] = memo_var.get().strip()
            dialog.destroy()

        def on_skip(event=None):
            result['memo'] = ''
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg='#1c1c1c')
        btn_frame.pack(pady=(5, 15))
        ttk.Button(btn_frame, text="Save", command=on_ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Skip", command=on_skip).pack(side='left', padx=5)

        entry.bind('<Return>', on_ok)
        entry.bind('<Escape>', on_skip)

        dialog.wait_window()
        return result['memo']

    def _on_manual_entry(self):
        """Handle manual entry button click."""
        if self.client:
            self.event_generate('<<ManualEntry>>')

    def _start_update_loop(self):
        """Start the display update loop."""
        self._update_display()
        self.engine.tick()  # Check idle, auto-save
        self._update_job = self.after(1000, self._start_update_loop)

    def _stop_update_loop(self):
        """Stop the display update loop."""
        if self._update_job:
            self.after_cancel(self._update_job)
            self._update_job = None

    def _update_display(self):
        """Update the time display."""
        seconds = self.engine.get_elapsed_seconds()
        self.time_label.config(text=timer_engine.format_seconds(seconds))

        # Update activity stats if running
        if self.engine.state == 'running':
            stats = self.engine.get_activity_stats()
            self.activity_label.config(
                text=f"Keys: {stats['key_presses']}  Clicks: {stats['mouse_clicks']}  Moves: {stats['mouse_moves']}"
            )
        else:
            self.activity_label.config(text="")

    def update_state_from_engine(self):
        """Update UI to match engine state."""
        state = self.engine.state
        if state == 'stopped':
            self.start_btn.config(text="START")
            self._stop_update_loop()
        elif state == 'running':
            self.start_btn.config(text="STOP")
            self._start_update_loop()
        elif state == 'paused':
            # Paused state used internally (idle detection)
            self.start_btn.config(text="STOP")
            self._stop_update_loop()
        self._update_display()

    def _on_screenshot(self, capture_result: dict):
        """Handle screenshot captured event from engine."""
        screenshot_id = capture_result['screenshot_id']
        thumbnail = capture_result['thumbnail']

        def on_delete(sid):
            # Delete the screenshot from disk and DB
            file_path = db.delete_screenshot(sid)
            if file_path:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception:
                    pass
            # Tell engine to reschedule in same window
            self.engine.screenshot_capture.reschedule_in_window()

        # Show popup
        ScreenshotPopup(self.winfo_toplevel(), screenshot_id, thumbnail, on_delete)


class ScreenshotPopup(tk.Toplevel):
    """Bottom-right popup showing screenshot thumbnail with delete option."""

    BG = '#2a2a2a'
    FG = '#ffffff'

    def __init__(self, parent, screenshot_id: int, thumbnail, on_delete: Callable):
        super().__init__(parent)

        self.screenshot_id = screenshot_id
        self.on_delete = on_delete

        # Window setup - no titlebar, always on top
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=self.BG)

        # Position bottom-right of screen
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        popup_w, popup_h = 240, 200
        x = screen_w - popup_w - 20
        y = screen_h - popup_h - 60  # Above taskbar
        self.geometry(f'{popup_w}x{popup_h}+{x}+{y}')

        # Content frame with border
        frame = tk.Frame(self, bg=self.BG, highlightbackground='#444444',
                        highlightthickness=1)
        frame.pack(fill='both', expand=True, padx=1, pady=1)

        # Header
        tk.Label(frame, text="Screenshot captured", bg=self.BG, fg=self.FG,
                 font=('Segoe UI', 10, 'bold')).pack(pady=(10, 6))

        # Thumbnail - convert PIL Image to PhotoImage
        try:
            from PIL import ImageTk
            self.photo = ImageTk.PhotoImage(thumbnail)
            tk.Label(frame, image=self.photo, bg=self.BG).pack(pady=4)
        except Exception:
            tk.Label(frame, text="[Preview unavailable]", bg=self.BG, fg='#666666',
                    font=('Segoe UI', 9)).pack(pady=4)

        # Delete button
        ttk.Button(frame, text="Delete", command=self._on_delete).pack(pady=(6, 10))

        # Auto-close after 5 seconds
        self.after(5000, self._close)

        # Allow clicking anywhere on popup to dismiss
        self.bind('<Button-1>', lambda e: self._close() if e.widget == self else None)

    def _on_delete(self):
        """Handle delete button click."""
        self.on_delete(self.screenshot_id)
        self.destroy()

    def _close(self):
        """Close the popup."""
        try:
            self.destroy()
        except tk.TclError:
            pass  # Already destroyed
