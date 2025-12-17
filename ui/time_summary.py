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
        # Dark theme colors (sv_ttk compatible)
        BG = '#1c1c1c'
        BG_CARD = '#2a2a2a'
        FG = '#fafafa'
        FG_DIM = '#9e9e9e'
        ACCENT = '#0078d4'
        SUCCESS = '#4caf50'
        WARNING = '#ff9800'

        # Main container with card-like background
        main = tk.Frame(self, bg=BG)
        main.pack(fill='x', padx=12, pady=(0, 8))

        # Card
        card = tk.Frame(main, bg=BG_CARD)
        card.pack(fill='x')

        # Content area
        content = tk.Frame(card, bg=BG_CARD)
        content.pack(fill='x', padx=16, pady=12)

        # Today
        row1 = tk.Frame(content, bg=BG_CARD)
        row1.pack(fill='x', pady=3)
        tk.Label(row1, text="Today", width=10, anchor='w', bg=BG_CARD,
                fg=FG_DIM, font=('Segoe UI', 10)).pack(side='left')
        self.today_hours = tk.Label(row1, text="--", anchor='e',
                                   bg=BG_CARD, fg=FG, font=('Segoe UI', 10))
        self.today_hours.pack(side='left', padx=(0, 8))
        self.today_amount = tk.Label(row1, text="", anchor='e',
                                    bg=BG_CARD, fg=FG_DIM, font=('Segoe UI', 9))
        self.today_amount.pack(side='right')

        # This week
        row2 = tk.Frame(content, bg=BG_CARD)
        row2.pack(fill='x', pady=3)
        tk.Label(row2, text="This Week", width=10, anchor='w', bg=BG_CARD,
                fg=FG_DIM, font=('Segoe UI', 10)).pack(side='left')
        self.week_hours = tk.Label(row2, text="--", anchor='e',
                                  bg=BG_CARD, fg=FG, font=('Segoe UI', 10))
        self.week_hours.pack(side='left', padx=(0, 8))
        self.week_amount = tk.Label(row2, text="", anchor='e',
                                   bg=BG_CARD, fg=FG_DIM, font=('Segoe UI', 9))
        self.week_amount.pack(side='right')

        # Uninvoiced (highlighted)
        row3 = tk.Frame(content, bg=BG_CARD)
        row3.pack(fill='x', pady=3)
        tk.Label(row3, text="Uninvoiced", width=10, anchor='w', bg=BG_CARD,
                fg=FG, font=('Segoe UI', 10, 'bold')).pack(side='left')
        self.uninvoiced_hours = tk.Label(row3, text="--", anchor='e',
                                        bg=BG_CARD, fg=ACCENT, font=('Segoe UI', 10, 'bold'))
        self.uninvoiced_hours.pack(side='left', padx=(0, 8))
        self.uninvoiced_amount = tk.Label(row3, text="", anchor='e',
                                         bg=BG_CARD, fg=SUCCESS, font=('Segoe UI', 10, 'bold'))
        self.uninvoiced_amount.pack(side='right')

        # Since date (under uninvoiced)
        self.since_date = tk.Label(content, text="", anchor='e',
                                   bg=BG_CARD, fg=FG_DIM, font=('Segoe UI', 8))
        self.since_date.pack(anchor='e', pady=(0, 2))

        # Separator
        tk.Frame(content, bg='#3a3a3a', height=1).pack(fill='x', pady=10)

        # Invoiced section header
        tk.Label(content, text="INVOICED", bg=BG_CARD, fg=FG_DIM,
                font=('Segoe UI', 8, 'bold'), anchor='w').pack(anchor='w', pady=(0, 4))

        # Unpaid
        row4 = tk.Frame(content, bg=BG_CARD)
        row4.pack(fill='x', pady=3)
        tk.Label(row4, text="Unpaid", width=10, anchor='w', bg=BG_CARD,
                fg=FG_DIM, font=('Segoe UI', 10)).pack(side='left')
        self.unpaid_amount = tk.Label(row4, text="--", anchor='e',
                                     bg=BG_CARD, fg=WARNING, font=('Segoe UI', 10, 'bold'))
        self.unpaid_amount.pack(side='left')

        # Paid
        row5 = tk.Frame(content, bg=BG_CARD)
        row5.pack(fill='x', pady=3)
        tk.Label(row5, text="Paid", width=10, anchor='w', bg=BG_CARD,
                fg=FG_DIM, font=('Segoe UI', 10)).pack(side='left')
        self.paid_amount = tk.Label(row5, text="--", anchor='e',
                                   bg=BG_CARD, fg=FG_DIM, font=('Segoe UI', 10))
        self.paid_amount.pack(side='left')

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
            self.uninvoiced_amount.config(text="")  # No dollar amount for global view
            first_date = db.get_first_uninvoiced_date()
            if first_date and summary['uninvoiced_hours'] > 0:
                self.since_date.config(text=f"since {first_date}")
            else:
                self.since_date.config(text="")

            # Show actual invoice amounts
            self.unpaid_amount.config(text=timer_engine.format_currency(summary['invoiced_amount']))
            self.paid_amount.config(text=timer_engine.format_currency(summary['paid_amount']))
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
        uninvoiced_dollars = summary['uninvoiced_hours'] * rate
        self.uninvoiced_amount.config(text=timer_engine.format_currency(uninvoiced_dollars))
        first_date = db.get_first_uninvoiced_date(self.client['id'])
        if first_date and summary['uninvoiced_hours'] > 0:
            self.since_date.config(text=f"since {first_date}")
        else:
            self.since_date.config(text="")

        # Unpaid invoices (actual invoice amounts)
        self.unpaid_amount.config(text=timer_engine.format_currency(summary['invoiced_amount']))

        # Paid invoices (actual invoice amounts)
        self.paid_amount.config(text=timer_engine.format_currency(summary['paid_amount']))
