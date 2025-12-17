"""Timer display panel with stopwatch."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict
import timer_engine


class TimerDisplayPanel(ttk.Frame):
    """Panel showing the stopwatch and controls."""

    def __init__(self, parent, engine: timer_engine.TimerEngine):
        super().__init__(parent)
        self.engine = engine
        self.client: Optional[Dict] = None
        self._update_job = None

        self._create_widgets()
        self._update_display()

    def _create_widgets(self):
        # Time display
        self.time_label = ttk.Label(
            self,
            text="00:00:00",
            font=('Consolas', 48, 'bold'),
            anchor='center'
        )
        self.time_label.pack(pady=(20, 10))

        # Client info
        self.client_label = ttk.Label(
            self,
            text="Select a client",
            font=('Segoe UI', 12),
            anchor='center'
        )
        self.client_label.pack(pady=5)

        self.rate_label = ttk.Label(
            self,
            text="",
            font=('Segoe UI', 10),
            foreground='gray',
            anchor='center'
        )
        self.rate_label.pack(pady=2)

        # Activity stats (shown when timer running)
        self.activity_label = ttk.Label(
            self,
            text="",
            font=('Segoe UI', 9),
            foreground='#666666',
            anchor='center'
        )
        self.activity_label.pack(pady=2)

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=20)

        self.start_btn = ttk.Button(
            btn_frame,
            text="START",
            command=self._on_start_stop,
            width=12
        )
        self.start_btn.pack(side='left', padx=5)

        self.pause_btn = ttk.Button(
            btn_frame,
            text="PAUSE",
            command=self._on_pause_resume,
            width=12,
            state='disabled'
        )
        self.pause_btn.pack(side='left', padx=5)

        # Manual entry button
        self.manual_btn = ttk.Button(
            self,
            text="+ Manual Entry",
            command=self._on_manual_entry,
            state='disabled'
        )
        self.manual_btn.pack(pady=10)

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
                self.pause_btn.config(state='normal', text="PAUSE")
                self._start_update_loop()
        else:
            self.engine.stop()
            self.start_btn.config(text="START")
            self.pause_btn.config(state='disabled', text="PAUSE")
            self._stop_update_loop()
            self._update_display()
            # Notify parent to refresh summary
            self.event_generate('<<TimerStopped>>')

    def _on_pause_resume(self):
        """Handle pause/resume button click."""
        if self.engine.state == 'running':
            self.engine.pause()
            self.pause_btn.config(text="RESUME")
        elif self.engine.state == 'paused':
            self.engine.resume()
            self.pause_btn.config(text="PAUSE")

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
            self.pause_btn.config(state='disabled', text="PAUSE")
            self._stop_update_loop()
        elif state == 'running':
            self.start_btn.config(text="STOP")
            self.pause_btn.config(state='normal', text="PAUSE")
            self._start_update_loop()
        elif state == 'paused':
            self.start_btn.config(text="STOP")
            self.pause_btn.config(state='normal', text="RESUME")
            self._stop_update_loop()
        self._update_display()
