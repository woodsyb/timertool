"""Time summary panel showing today/week/uninvoiced totals."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict
import db
import timer_engine


class TimeSummaryPanel(ttk.Frame):
    """Panel showing time summaries and build invoice button."""

    def __init__(self, parent):
        super().__init__(parent)
        self.client: Optional[Dict] = None

        self._create_widgets()

    def _create_widgets(self):
        # Summary frame
        summary_frame = ttk.LabelFrame(self, text="TIME SUMMARY", padding=10)
        summary_frame.pack(fill='x', padx=10, pady=5)

        # Today
        row1 = ttk.Frame(summary_frame)
        row1.pack(fill='x', pady=2)
        ttk.Label(row1, text="Today:", width=15, anchor='w').pack(side='left')
        self.today_hours = ttk.Label(row1, text="--", width=12, anchor='e')
        self.today_hours.pack(side='left')
        self.today_amount = ttk.Label(row1, text="", width=12, anchor='e', foreground='gray')
        self.today_amount.pack(side='left')

        # This week
        row2 = ttk.Frame(summary_frame)
        row2.pack(fill='x', pady=2)
        ttk.Label(row2, text="This Week:", width=15, anchor='w').pack(side='left')
        self.week_hours = ttk.Label(row2, text="--", width=12, anchor='e')
        self.week_hours.pack(side='left')
        self.week_amount = ttk.Label(row2, text="", width=12, anchor='e', foreground='gray')
        self.week_amount.pack(side='left')

        # Uninvoiced
        row3 = ttk.Frame(summary_frame)
        row3.pack(fill='x', pady=2)
        ttk.Label(row3, text="Uninvoiced:", width=15, anchor='w').pack(side='left')
        self.uninvoiced_hours = ttk.Label(row3, text="--", width=12, anchor='e', font=('Segoe UI', 9, 'bold'))
        self.uninvoiced_hours.pack(side='left')
        self.uninvoiced_amount = ttk.Label(row3, text="", width=12, anchor='e', foreground='green', font=('Segoe UI', 9, 'bold'))
        self.uninvoiced_amount.pack(side='left')

        # Separator
        ttk.Separator(summary_frame, orient='horizontal').pack(fill='x', pady=5)

        # Invoiced header
        ttk.Label(summary_frame, text="Invoiced:", font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        # Unpaid invoices
        row4 = ttk.Frame(summary_frame)
        row4.pack(fill='x', pady=2)
        ttk.Label(row4, text="Unpaid:", width=15, anchor='w').pack(side='left')
        self.unpaid_amount = ttk.Label(row4, text="--", width=12, anchor='e', foreground='#cc6600', font=('Segoe UI', 9, 'bold'))
        self.unpaid_amount.pack(side='left')

        # Paid invoices
        row5 = ttk.Frame(summary_frame)
        row5.pack(fill='x', pady=2)
        ttk.Label(row5, text="Paid:", width=15, anchor='w').pack(side='left')
        self.paid_amount = ttk.Label(row5, text="--", width=12, anchor='e', foreground='gray')
        self.paid_amount.pack(side='left')

        # Build invoice button
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=5)

        self.invoice_btn = ttk.Button(
            btn_frame,
            text="Build Invoice",
            command=self._on_build_invoice,
            state='disabled'
        )
        self.invoice_btn.pack(side='right')

    def set_client(self, client: Optional[Dict]):
        """Set the current client and refresh summary."""
        self.client = client
        self.refresh()

    def refresh(self):
        """Refresh the summary display."""
        if not self.client:
            # Show global stats when no client selected
            summary = db.get_global_time_summary()

            self.today_hours.config(text=timer_engine.format_hours(summary['today_hours']))
            self.today_amount.config(text="(all clients)")

            self.week_hours.config(text=timer_engine.format_hours(summary['week_hours']))
            self.week_amount.config(text="(all clients)")

            self.uninvoiced_hours.config(text=timer_engine.format_hours(summary['uninvoiced_hours']))
            self.uninvoiced_amount.config(text="(all clients)")

            # Show actual invoice amounts
            self.unpaid_amount.config(text=timer_engine.format_currency(summary['invoiced_amount']))
            self.paid_amount.config(text=timer_engine.format_currency(summary['paid_amount']))

            self.invoice_btn.config(state='disabled')
            return

        summary = db.get_time_summary(self.client['id'])
        rate = self.client['hourly_rate']

        # Today
        self.today_hours.config(text=timer_engine.format_hours(summary['today_hours']))
        self.today_amount.config(text=f"({timer_engine.format_currency(summary['today_hours'] * rate)})")

        # This week
        self.week_hours.config(text=timer_engine.format_hours(summary['week_hours']))
        self.week_amount.config(text=f"({timer_engine.format_currency(summary['week_hours'] * rate)})")

        # Uninvoiced
        self.uninvoiced_hours.config(text=timer_engine.format_hours(summary['uninvoiced_hours']))
        self.uninvoiced_amount.config(text=f"({timer_engine.format_currency(summary['uninvoiced_hours'] * rate)})")

        # Unpaid invoices (actual invoice amounts)
        self.unpaid_amount.config(text=timer_engine.format_currency(summary['invoiced_amount']))

        # Paid invoices (actual invoice amounts)
        self.paid_amount.config(text=timer_engine.format_currency(summary['paid_amount']))

        # Enable invoice button if there's uninvoiced time
        if summary['uninvoiced_hours'] > 0:
            self.invoice_btn.config(state='normal')
        else:
            self.invoice_btn.config(state='disabled')

    def _on_build_invoice(self):
        """Handle build invoice button click."""
        self.event_generate('<<BuildInvoice>>')
