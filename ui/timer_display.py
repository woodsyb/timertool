"""Timer display panel with stopwatch."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict
import timer_engine


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
                self.engine.start(self.client['id'], track_activity=bool(track_activity))
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
