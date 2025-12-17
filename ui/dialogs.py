"""Dialog windows for manual entry, build invoice, settings, etc."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from tkcalendar import DateEntry
import db
import timer_engine


class ManualEntryDialog(tk.Toplevel):
    """Dialog for adding a manual time entry."""

    def __init__(self, parent, client: Dict):
        super().__init__(parent)
        self.title("Manual Entry")
        self.client = client
        self.result = None

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('+%d+%d' % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)

        # Client display
        ttk.Label(frame, text=f"Client: {self.client['name']}", font=('Segoe UI', 10, 'bold')).grid(
            row=0, column=0, columnspan=3, sticky='w', pady=(0, 10)
        )

        # Date
        ttk.Label(frame, text="Date:").grid(row=1, column=0, sticky='w', pady=2)
        self.date_entry = DateEntry(frame, width=20, date_pattern='yyyy-mm-dd')
        self.date_entry.grid(row=1, column=1, sticky='w', pady=2)

        # Entry mode selector
        ttk.Label(frame, text="Entry Type:").grid(row=2, column=0, sticky='w', pady=2)
        self.mode_var = tk.StringVar(value='hours')
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=2, column=1, columnspan=2, sticky='w', pady=2)
        ttk.Radiobutton(mode_frame, text="Hours", variable=self.mode_var, value='hours',
                       command=self._toggle_mode).pack(side='left', padx=(0, 10))
        ttk.Radiobutton(mode_frame, text="Time Range", variable=self.mode_var, value='range',
                       command=self._toggle_mode).pack(side='left')

        # Hours entry (default)
        self.hours_frame = ttk.Frame(frame)
        self.hours_frame.grid(row=3, column=0, columnspan=3, sticky='w', pady=2)
        ttk.Label(self.hours_frame, text="Hours:").pack(side='left')
        self.hours_var = tk.StringVar()
        self.hours_entry = ttk.Entry(self.hours_frame, textvariable=self.hours_var, width=10)
        self.hours_entry.pack(side='left', padx=(5, 5))
        ttk.Label(self.hours_frame, text="(e.g., 1.5 for 1h 30m)").pack(side='left')

        # Time range entry (hidden by default) - 24 hour format
        self.range_frame = ttk.Frame(frame)
        self.range_frame.grid(row=3, column=0, columnspan=3, sticky='w', pady=2)
        hours_24 = [f"{i:02d}" for i in range(0, 24)]
        mins = ['00', '15', '30', '45']
        ttk.Label(self.range_frame, text="Start:").pack(side='left')
        self.start_hour = ttk.Combobox(self.range_frame, width=3, values=hours_24)
        self.start_hour.set("09")
        self.start_hour.pack(side='left', padx=2)
        ttk.Label(self.range_frame, text=":").pack(side='left')
        self.start_min = ttk.Combobox(self.range_frame, width=3, values=mins)
        self.start_min.set("00")
        self.start_min.pack(side='left', padx=(0, 10))
        ttk.Label(self.range_frame, text="End:").pack(side='left')
        self.end_hour = ttk.Combobox(self.range_frame, width=3, values=hours_24)
        self.end_hour.set("17")
        self.end_hour.pack(side='left', padx=2)
        ttk.Label(self.range_frame, text=":").pack(side='left')
        self.end_min = ttk.Combobox(self.range_frame, width=3, values=mins)
        self.end_min.set("00")
        self.end_min.pack(side='left')
        self.range_frame.grid_remove()  # Hide by default

        # Description
        ttk.Label(frame, text="Description:").grid(row=4, column=0, sticky='nw', pady=2)
        self.desc_text = tk.Text(frame, width=40, height=3)
        self.desc_text.grid(row=4, column=1, columnspan=2, sticky='w', pady=2)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=(15, 0))

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.hours_entry.focus_set()
        self.bind('<Escape>', lambda e: self.destroy())

    def _toggle_mode(self):
        """Toggle between hours and time range mode."""
        if self.mode_var.get() == 'hours':
            self.range_frame.grid_remove()
            self.hours_frame.grid()
        else:
            self.hours_frame.grid_remove()
            self.range_frame.grid()

    def _save(self):
        """Validate and save the entry."""
        date = self.date_entry.get_date()
        description = self.desc_text.get('1.0', 'end').strip()

        if self.mode_var.get() == 'hours':
            # Bulk hours mode
            try:
                hours = float(self.hours_var.get())
                if hours <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number of hours.", parent=self)
                return

            start_time = datetime.combine(date, datetime.min.time().replace(hour=9))
            duration_seconds = int(hours * 3600)
            end_time = start_time + timedelta(seconds=duration_seconds)
        else:
            # Time range mode
            try:
                start_h = int(self.start_hour.get())
                start_m = int(self.start_min.get())
                end_h = int(self.end_hour.get())
                end_m = int(self.end_min.get())

                start_time = datetime.combine(date, datetime.min.time().replace(hour=start_h, minute=start_m))
                end_time = datetime.combine(date, datetime.min.time().replace(hour=end_h, minute=end_m))

                # Handle overnight (end time before start time)
                if end_time <= start_time:
                    end_time += timedelta(days=1)

                duration_seconds = int((end_time - start_time).total_seconds())
                hours = duration_seconds / 3600

                if duration_seconds <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                messagebox.showerror("Error", "Please enter valid start and end times.", parent=self)
                return

        self.result = {
            'date': date,
            'hours': hours,
            'duration_seconds': duration_seconds,
            'start_time': start_time,
            'end_time': end_time,
            'description': description
        }
        self.destroy()


class BuildInvoiceDialog(tk.Toplevel):
    """Dialog for building an invoice from time entries."""

    def __init__(self, parent, client: Dict, entries: List[Dict]):
        super().__init__(parent)
        self.title("Build Invoice")
        self.client = client
        self.entries = entries
        self.result = None
        self.entry_vars = {}

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('600x500+%d+%d' % (parent.winfo_rootx() + 30, parent.winfo_rooty() + 30))

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)

        # Client info
        ttk.Label(frame, text=f"Invoice for: {self.client['name']}", font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        ttk.Label(frame, text=f"Rate: ${self.client['hourly_rate']:.2f}/hr").pack(anchor='w')
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)

        # Date range filter
        date_frame = ttk.Frame(frame)
        date_frame.pack(fill='x', pady=5)

        ttk.Label(date_frame, text="Date Range:").pack(side='left')
        self.start_date = DateEntry(date_frame, width=12, date_pattern='yyyy-mm-dd')
        self.start_date.pack(side='left', padx=5)
        ttk.Label(date_frame, text="to").pack(side='left')
        self.end_date = DateEntry(date_frame, width=12, date_pattern='yyyy-mm-dd')
        self.end_date.pack(side='left', padx=5)
        ttk.Button(date_frame, text="Filter", command=self._filter_entries).pack(side='left', padx=10)

        # Set default dates
        if self.entries:
            dates = [datetime.fromisoformat(e['start_time']).date() for e in self.entries]
            self.start_date.set_date(min(dates))
            self.end_date.set_date(max(dates))

        # Entries list with checkboxes
        ttk.Label(frame, text="Select entries to include:").pack(anchor='w', pady=(10, 5))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill='both', expand=True)

        # Create canvas with scrollbar for entries
        canvas = tk.Canvas(list_frame, borderwidth=1, relief='solid')
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
        self.entries_frame = ttk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.create_window((0, 0), window=self.entries_frame, anchor='nw')

        self.entries_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        self._populate_entries()

        # Totals
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)

        totals_frame = ttk.Frame(frame)
        totals_frame.pack(fill='x')

        self.total_hours_label = ttk.Label(totals_frame, text="Total: 0.00 hrs", font=('Segoe UI', 10, 'bold'))
        self.total_hours_label.pack(side='left')
        self.total_amount_label = ttk.Label(totals_frame, text="$0.00", font=('Segoe UI', 10, 'bold'), foreground='green')
        self.total_amount_label.pack(side='left', padx=10)

        # Invoice details
        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)

        details_frame = ttk.Frame(frame)
        details_frame.pack(fill='x')

        # Description
        ttk.Label(details_frame, text="Description:").grid(row=0, column=0, sticky='w', pady=2)
        self.desc_var = tk.StringVar(value=f"Professional services - {datetime.now().strftime('%B %Y')}")
        ttk.Entry(details_frame, textvariable=self.desc_var, width=50).grid(row=0, column=1, sticky='w', pady=2)

        # Payment terms
        ttk.Label(details_frame, text="Payment Terms:").grid(row=1, column=0, sticky='w', pady=2)
        self.terms_var = tk.StringVar(value='Net 30')
        terms_combo = ttk.Combobox(details_frame, textvariable=self.terms_var, width=15, state='readonly')
        terms_combo['values'] = ('Due on Receipt', 'Net 7', 'Net 15', 'Net 30')
        terms_combo.grid(row=1, column=1, sticky='w', pady=2)

        # Payment method
        ttk.Label(details_frame, text="Payment Method:").grid(row=2, column=0, sticky='w', pady=2)
        self.method_var = tk.StringVar(value='ACH')
        method_combo = ttk.Combobox(details_frame, textvariable=self.method_var, width=15, state='readonly')
        method_combo['values'] = ('ACH', 'Wire', 'Check')
        method_combo.grid(row=2, column=1, sticky='w', pady=2)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(btn_frame, text="Create Invoice", command=self._create).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='right', padx=5)

        self._update_totals()

    def _populate_entries(self):
        """Populate the entries list with checkboxes."""
        # Clear existing
        for widget in self.entries_frame.winfo_children():
            widget.destroy()
        self.entry_vars.clear()

        for entry in self.entries:
            var = tk.BooleanVar(value=True)
            self.entry_vars[entry['id']] = var

            row_frame = ttk.Frame(self.entries_frame)
            row_frame.pack(fill='x', pady=1)

            cb = ttk.Checkbutton(row_frame, variable=var, command=self._update_totals)
            cb.pack(side='left')

            dt = datetime.fromisoformat(entry['start_time'])
            hours = entry['duration_seconds'] / 3600

            date_str = dt.strftime('%Y-%m-%d')
            hours_str = f"{hours:.2f} hrs"
            desc = entry.get('description', '') or ''
            if len(desc) > 30:
                desc = desc[:30] + '...'

            ttk.Label(row_frame, text=date_str, width=12).pack(side='left')
            ttk.Label(row_frame, text=hours_str, width=10).pack(side='left')
            ttk.Label(row_frame, text=desc, foreground='gray').pack(side='left')

    def _filter_entries(self):
        """Filter entries by date range."""
        start = self.start_date.get_date()
        end = self.end_date.get_date()

        self.entries = db.get_time_entries(
            client_id=self.client['id'],
            start_date=datetime.combine(start, datetime.min.time()),
            end_date=datetime.combine(end, datetime.max.time()),
            invoiced=False
        )
        self._populate_entries()
        self._update_totals()

    def _update_totals(self):
        """Update the totals display."""
        total_seconds = 0
        for entry in self.entries:
            if self.entry_vars.get(entry['id'], tk.BooleanVar(value=False)).get():
                total_seconds += entry['duration_seconds'] or 0

        total_hours = total_seconds / 3600
        total_amount = total_hours * self.client['hourly_rate']

        self.total_hours_label.config(text=f"Total: {total_hours:.2f} hrs")
        self.total_amount_label.config(text=timer_engine.format_currency(total_amount))

    def _create(self):
        """Create the invoice."""
        selected_entries = []
        for entry in self.entries:
            if self.entry_vars.get(entry['id'], tk.BooleanVar(value=False)).get():
                selected_entries.append(entry)

        if not selected_entries:
            messagebox.showerror("Error", "Please select at least one entry.", parent=self)
            return

        self.result = {
            'entries': selected_entries,
            'description': self.desc_var.get(),
            'payment_terms': self.terms_var.get(),
            'payment_method': self.method_var.get()
        }
        self.destroy()


class IdleDialog(tk.Toplevel):
    """Dialog shown when idle timeout is triggered."""

    def __init__(self, parent, idle_seconds: int, accumulated_seconds: int):
        super().__init__(parent)
        self.title("Timer Paused")
        self.result = None
        self.idle_seconds = idle_seconds

        self.transient(parent)
        self.grab_set()

        self._create_widgets(idle_seconds, accumulated_seconds)

        # Center on screen
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry('+%d+%d' % (x, y))

        # Bring to front
        self.lift()
        self.attributes('-topmost', True)
        self.focus_force()

    def _create_widgets(self, idle_seconds: int, accumulated_seconds: int):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        idle_min = idle_seconds // 60
        accumulated_str = timer_engine.format_seconds(accumulated_seconds)

        ttk.Label(
            frame,
            text="Timer Paused",
            font=('Segoe UI', 14, 'bold')
        ).pack(pady=(0, 10))

        ttk.Label(
            frame,
            text=f"You've been inactive for {idle_min} minutes.",
            font=('Segoe UI', 10)
        ).pack()

        ttk.Label(
            frame,
            text=f"Time recorded: {accumulated_str}",
            font=('Segoe UI', 10)
        ).pack(pady=(5, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        ttk.Button(btn_frame, text="Resume", command=self._resume, width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Discard Idle", command=self._discard, width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Stop Timer", command=self._stop, width=15).pack(side='left', padx=5)

    def _resume(self):
        self.result = 'resume'
        self.destroy()

    def _discard(self):
        self.result = 'discard'
        self.destroy()

    def _stop(self):
        self.result = 'stop'
        self.destroy()


class RecoveryDialog(tk.Toplevel):
    """Dialog shown on startup when there's a crashed timer to recover."""

    def __init__(self, parent, client_name: str, accumulated_seconds: int, last_save: datetime):
        super().__init__(parent)
        self.title("Timer Recovery")
        self.result = None

        self.transient(parent)
        self.grab_set()

        self._create_widgets(client_name, accumulated_seconds, last_save)

        # Center on screen
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry('+%d+%d' % (x, y))

    def _create_widgets(self, client_name: str, accumulated_seconds: int, last_save: datetime):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill='both', expand=True)

        time_str = timer_engine.format_seconds(accumulated_seconds)
        save_str = last_save.strftime('%Y-%m-%d %H:%M:%S')

        ttk.Label(
            frame,
            text="Timer Recovery",
            font=('Segoe UI', 14, 'bold')
        ).pack(pady=(0, 10))

        ttk.Label(
            frame,
            text=f"Found unsaved timer for: {client_name}",
            font=('Segoe UI', 10)
        ).pack()

        ttk.Label(
            frame,
            text=f"Time: {time_str}",
            font=('Segoe UI', 10, 'bold')
        ).pack(pady=5)

        ttk.Label(
            frame,
            text=f"Last saved: {save_str}",
            font=('Segoe UI', 9),
            foreground='gray'
        ).pack(pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        ttk.Button(btn_frame, text="Keep Time", command=self._keep, width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Discard", command=self._discard, width=15).pack(side='left', padx=5)

    def _keep(self):
        self.result = True
        self.destroy()

    def _discard(self):
        self.result = False
        self.destroy()


class InvoiceListDialog(tk.Toplevel):
    """Dialog showing list of invoices with open/mark paid functionality."""

    def __init__(self, parent, client_id: int = None):
        super().__init__(parent)
        self.title("Invoices")
        self.client_id = client_id

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('600x400+%d+%d' % (parent.winfo_rootx() + 30, parent.winfo_rooty() + 30))
        self._load_invoices()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill='both', expand=True)

        # Treeview for invoices
        columns = ('client', 'date', 'total', 'status')
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', selectmode='browse')

        self.tree.heading('client', text='Client')
        self.tree.heading('date', text='Date')
        self.tree.heading('total', text='Total')
        self.tree.heading('status', text='Status')

        self.tree.column('client', width=180)
        self.tree.column('date', width=100)
        self.tree.column('total', width=100, anchor='e')
        self.tree.column('status', width=80, anchor='center')

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.tree.bind('<Double-1>', self._on_double_click)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="Open PDF", command=self._open_pdf).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Mark Paid", command=self._mark_paid).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side='right', padx=5)

    def _load_invoices(self):
        """Load invoices into the tree."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        invoices = db.get_invoices(limit=100)
        if self.client_id:
            invoices = [i for i in invoices if i['client_id'] == self.client_id]

        for inv in invoices:
            paid = inv.get('amount_paid') or 0
            if inv['status'] == 'paid':
                status = "PAID"
            elif paid > 0:
                status = f"Partial (${paid:.0f})"
            else:
                status = "Unpaid"
            self.tree.insert('', 'end', iid=inv['invoice_number'],
                           values=(inv['client_name'], inv['date_issued'],
                                  f"${inv['total']:.2f}", status))

    def _on_double_click(self, event):
        """Open PDF on double click."""
        self._open_pdf()

    def _open_pdf(self):
        """Open the selected invoice PDF."""
        selection = self.tree.selection()
        if not selection:
            return

        invoice_number = selection[0]
        pdf_path = db.get_invoice_pdf_path(invoice_number)

        if pdf_path:
            import os
            import sys
            if sys.platform == 'win32':
                os.startfile(str(pdf_path))
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.run(['open', str(pdf_path)])
            else:
                import subprocess
                subprocess.run(['xdg-open', str(pdf_path)])
        else:
            messagebox.showinfo("Not Found", f"PDF for {invoice_number} not found.", parent=self)

    def _mark_paid(self):
        """Mark the selected invoice as paid (full or partial)."""
        selection = self.tree.selection()
        if not selection:
            return

        invoice_number = selection[0]
        invoice = db.get_invoice(invoice_number)

        if invoice['status'] == 'paid':
            messagebox.showinfo("Already Paid", f"{invoice_number} is already marked as paid.", parent=self)
            return

        # Show payment dialog
        dialog = PaymentDialog(self, invoice)
        self.wait_window(dialog)

        if dialog.result:
            amount = dialog.result['amount']
            db.record_payment(invoice_number, amount)
            self._load_invoices()


class TimeEntriesDialog(tk.Toplevel):
    """Dialog showing time entries with activity details."""

    def __init__(self, parent, client_id: int = None, client_name: str = ""):
        super().__init__(parent)
        self.title(f"Time Entries - {client_name}" if client_name else "Time Entries")
        self.client_id = client_id

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('750x450+%d+%d' % (parent.winfo_rootx() + 20, parent.winfo_rooty() + 20))
        self._load_entries()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill='both', expand=True)

        # Filter options
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        self.filter_var = tk.StringVar(value='uninvoiced')
        ttk.Radiobutton(filter_frame, text="All", variable=self.filter_var, value='all',
                       command=self._load_entries).pack(side='left', padx=5)
        ttk.Radiobutton(filter_frame, text="Uninvoiced", variable=self.filter_var, value='uninvoiced',
                       command=self._load_entries).pack(side='left', padx=5)
        ttk.Radiobutton(filter_frame, text="Invoiced", variable=self.filter_var, value='invoiced',
                       command=self._load_entries).pack(side='left', padx=5)
        ttk.Radiobutton(filter_frame, text="Paid", variable=self.filter_var, value='paid',
                       command=self._load_entries).pack(side='left', padx=5)

        # Treeview for entries (with tree structure for date grouping)
        columns = ('hours', 'type', 'keys', 'clicks', 'moves', 'status')
        self.tree = ttk.Treeview(frame, columns=columns, show='tree headings', selectmode='browse')

        self.tree.heading('#0', text='Date/Time')
        self.tree.heading('hours', text='Hours')
        self.tree.heading('type', text='Type')
        self.tree.heading('keys', text='Keys')
        self.tree.heading('clicks', text='Clicks')
        self.tree.heading('moves', text='Moves')
        self.tree.heading('status', text='Status')

        self.tree.column('#0', width=140)
        self.tree.column('hours', width=70, anchor='e')
        self.tree.column('type', width=80, anchor='center')
        self.tree.column('keys', width=70, anchor='e')
        self.tree.column('clicks', width=70, anchor='e')
        self.tree.column('moves', width=70, anchor='e')
        self.tree.column('status', width=100, anchor='center')

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(btn_frame, text="Edit", command=self._edit_entry).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_entry).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side='right', padx=2)

        # Totals
        totals_frame = ttk.Frame(self)
        totals_frame.pack(fill='x', padx=10, pady=5)

        self.totals_label = ttk.Label(totals_frame, text="", font=('Segoe UI', 9))
        self.totals_label.pack(side='left')

    def _load_entries(self):
        """Load time entries into the tree, grouped by date."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        filter_val = self.filter_var.get()

        if filter_val == 'uninvoiced':
            entries = db.get_time_entries(client_id=self.client_id, invoiced=False)
        elif filter_val == 'invoiced':
            # Invoiced but not paid
            entries = db.get_time_entries(client_id=self.client_id, invoiced=True)
            entries = [e for e in entries if not self._is_entry_paid(e)]
        elif filter_val == 'paid':
            # Only paid entries
            entries = db.get_time_entries(client_id=self.client_id, invoiced=True)
            entries = [e for e in entries if self._is_entry_paid(e)]
        else:
            entries = db.get_time_entries(client_id=self.client_id)

        # Sort entries by date (newest first)
        entries.sort(key=lambda e: e['start_time'], reverse=True)

        total_hours = 0
        total_keys = 0
        total_clicks = 0
        total_moves = 0

        # Group by date
        date_groups = {}
        for entry in entries:
            dt = datetime.fromisoformat(entry['start_time'])
            date_key = dt.strftime('%Y-%m-%d')
            if date_key not in date_groups:
                date_groups[date_key] = []
            date_groups[date_key].append(entry)

        # Add date headers and entries
        for date_key in sorted(date_groups.keys(), reverse=True):
            date_entries = date_groups[date_key]
            dt = datetime.fromisoformat(date_entries[0]['start_time'])
            day_name = dt.strftime('%A')  # Monday, Tuesday, etc.

            # Calculate daily totals
            day_hours = sum((e['duration_seconds'] or 0) / 3600 for e in date_entries)

            # Insert date header
            date_id = f"date_{date_key}"
            self.tree.insert('', 'end', iid=date_id,
                           text=f"{day_name}, {date_key}",
                           values=(f"{day_hours:.2f}", "", "", "", "", ""),
                           open=True)

            # Insert entries under this date
            for entry in date_entries:
                dt = datetime.fromisoformat(entry['start_time'])
                hours = (entry['duration_seconds'] or 0) / 3600
                keys = entry.get('key_presses') or 0
                clicks = entry.get('mouse_clicks') or 0
                moves = entry.get('mouse_moves') or 0
                entry_type = entry.get('entry_type', 'stopwatch').title()

                # Determine status (Uninvoiced, Invoiced, or Paid)
                if not entry['invoiced']:
                    status = "Uninvoiced"
                else:
                    inv_num = entry.get('invoice_number')
                    if inv_num:
                        invoice = db.get_invoice(inv_num)
                        if invoice and invoice.get('status') == 'paid':
                            status = "Paid"
                        elif invoice and invoice.get('amount_paid', 0) > 0:
                            status = "Partial"
                        else:
                            status = "Invoiced"
                    else:
                        status = "Invoiced"

                total_hours += hours
                total_keys += keys
                total_clicks += clicks
                total_moves += moves

                self.tree.insert(date_id, 'end', iid=str(entry['id']),
                               text=dt.strftime('%H:%M'),
                               values=(f"{hours:.2f}",
                                      entry_type,
                                      f"{keys:,}" if keys else "-",
                                      f"{clicks:,}" if clicks else "-",
                                      f"{moves:,}" if moves else "-",
                                      status))

        self.totals_label.config(
            text=f"Total: {total_hours:.2f} hrs | Keys: {total_keys:,} | Clicks: {total_clicks:,} | Moves: {total_moves:,}"
        )

    def _is_entry_paid(self, entry: Dict) -> bool:
        """Check if an entry's invoice is paid."""
        if not entry.get('invoiced') or not entry.get('invoice_number'):
            return False
        invoice = db.get_invoice(entry['invoice_number'])
        return invoice and invoice.get('status') == 'paid'

    def _edit_entry(self):
        """Edit the selected time entry."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Entry", "Please select an entry to edit.", parent=self)
            return

        # Ignore date header rows
        if selection[0].startswith('date_'):
            messagebox.showinfo("Select Entry", "Please select an entry, not a date header.", parent=self)
            return

        entry_id = int(selection[0])
        entry = db.get_time_entry(entry_id)
        if not entry:
            return

        if entry['invoiced']:
            messagebox.showerror("Cannot Edit", "Cannot edit invoiced entries.", parent=self)
            return

        dialog = EditTimeEntryDialog(self, entry)
        self.wait_window(dialog)

        if dialog.result:
            db.update_time_entry(
                entry_id,
                duration_seconds=dialog.result['duration_seconds'],
                description=dialog.result.get('description')
            )
            self._load_entries()

    def _delete_entry(self):
        """Delete the selected time entry."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select Entry", "Please select an entry to delete.", parent=self)
            return

        # Ignore date header rows
        if selection[0].startswith('date_'):
            messagebox.showinfo("Select Entry", "Please select an entry, not a date header.", parent=self)
            return

        entry_id = int(selection[0])
        entry = db.get_time_entry(entry_id)
        if not entry:
            return

        if entry['invoiced']:
            messagebox.showerror("Cannot Delete", "Cannot delete invoiced entries.", parent=self)
            return

        hours = (entry['duration_seconds'] or 0) / 3600
        if messagebox.askyesno("Delete Entry",
                              f"Delete this {hours:.2f} hour entry?\nThis cannot be undone.",
                              parent=self):
            try:
                db.delete_time_entry(entry_id)
                self._load_entries()
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=self)


class EditTimeEntryDialog(tk.Toplevel):
    """Dialog for editing a time entry."""

    def __init__(self, parent, entry: Dict):
        super().__init__(parent)
        self.title("Edit Time Entry")
        self.entry = entry
        self.result = None

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('+%d+%d' % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)

        # Date (read-only)
        dt = datetime.fromisoformat(self.entry['start_time'])
        ttk.Label(frame, text=f"Date: {dt.strftime('%Y-%m-%d %H:%M')}").grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 10)
        )

        # Hours
        current_hours = (self.entry['duration_seconds'] or 0) / 3600
        ttk.Label(frame, text="Hours:").grid(row=1, column=0, sticky='w', pady=2)
        self.hours_var = tk.StringVar(value=f"{current_hours:.2f}")
        self.hours_entry = ttk.Entry(frame, textvariable=self.hours_var, width=10)
        self.hours_entry.grid(row=1, column=1, sticky='w', pady=2)

        # Description
        ttk.Label(frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=2)
        self.desc_text = tk.Text(frame, width=40, height=3)
        self.desc_text.grid(row=2, column=1, sticky='w', pady=2)
        if self.entry.get('description'):
            self.desc_text.insert('1.0', self.entry['description'])

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(15, 0))

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.hours_entry.focus_set()
        self.hours_entry.select_range(0, tk.END)
        self.bind('<Return>', lambda e: self._save())
        self.bind('<Escape>', lambda e: self.destroy())

    def _save(self):
        """Validate and save."""
        try:
            hours = float(self.hours_var.get())
            if hours <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number of hours.", parent=self)
            return

        self.result = {
            'duration_seconds': int(hours * 3600),
            'description': self.desc_text.get('1.0', 'end').strip()
        }
        self.destroy()


class PaymentDialog(tk.Toplevel):
    """Dialog for recording a payment."""

    def __init__(self, parent, invoice: Dict):
        super().__init__(parent)
        self.title("Record Payment")
        self.invoice = invoice
        self.result = None

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('+%d+%d' % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)

        total = self.invoice['total']
        paid = self.invoice.get('amount_paid') or 0
        remaining = total - paid

        # Invoice info
        ttk.Label(frame, text=f"Invoice: {self.invoice['invoice_number']}", font=('Segoe UI', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 5)
        )

        ttk.Label(frame, text=f"Total: ${total:.2f}").grid(row=1, column=0, sticky='w', pady=2)
        if paid > 0:
            ttk.Label(frame, text=f"Already paid: ${paid:.2f}").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Label(frame, text=f"Remaining: ${remaining:.2f}", font=('Segoe UI', 9, 'bold')).grid(
            row=3, column=0, sticky='w', pady=(2, 10)
        )

        # Payment amount
        ttk.Label(frame, text="Payment Amount:").grid(row=4, column=0, sticky='w', pady=2)
        self.amount_var = tk.StringVar(value=f"{remaining:.2f}")
        self.amount_entry = ttk.Entry(frame, textvariable=self.amount_var, width=15)
        self.amount_entry.grid(row=4, column=1, sticky='w', pady=2)

        # Quick buttons
        btn_row = ttk.Frame(frame)
        btn_row.grid(row=5, column=0, columnspan=2, pady=5)
        ttk.Button(btn_row, text="Full", command=lambda: self.amount_var.set(f"{remaining:.2f}"), width=8).pack(side='left', padx=2)
        ttk.Button(btn_row, text="Half", command=lambda: self.amount_var.set(f"{remaining/2:.2f}"), width=8).pack(side='left', padx=2)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(15, 0))

        ttk.Button(btn_frame, text="Record Payment", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.amount_entry.focus_set()
        self.amount_entry.select_range(0, tk.END)
        self.bind('<Return>', lambda e: self._save())
        self.bind('<Escape>', lambda e: self.destroy())

    def _save(self):
        """Validate and save the payment."""
        try:
            amount = float(self.amount_var.get())
            if amount <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid payment amount.", parent=self)
            return

        total = self.invoice['total']
        paid = self.invoice.get('amount_paid') or 0
        remaining = total - paid

        if amount > remaining + 0.01:  # Small tolerance for floating point
            messagebox.showerror("Error", f"Payment amount exceeds remaining balance (${remaining:.2f}).", parent=self)
            return

        self.result = {'amount': amount}
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """Dialog for app settings."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.result = None

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('+%d+%d' % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)

        # Inactivity timeout
        ttk.Label(frame, text="Inactivity Timeout (minutes):").grid(row=0, column=0, sticky='w', pady=5)
        self.timeout_var = tk.StringVar(value=db.get_setting('inactivity_timeout_minutes', '10'))
        ttk.Entry(frame, textvariable=self.timeout_var, width=10).grid(row=0, column=1, sticky='w', pady=5)

        # Auto-save interval
        ttk.Label(frame, text="Auto-save Interval (seconds):").grid(row=1, column=0, sticky='w', pady=5)
        self.save_var = tk.StringVar(value=db.get_setting('auto_save_interval_seconds', '30'))
        ttk.Entry(frame, textvariable=self.save_var, width=10).grid(row=1, column=1, sticky='w', pady=5)

        # Data folder info
        ttk.Label(frame, text="Data Folder:").grid(row=2, column=0, sticky='w', pady=5)
        data_path = str(db.get_data_dir())
        ttk.Label(frame, text=data_path, foreground='gray').grid(row=2, column=1, sticky='w', pady=5)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(15, 0))

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.bind('<Escape>', lambda e: self.destroy())

    def _save(self):
        """Save settings."""
        try:
            timeout = int(self.timeout_var.get())
            save_interval = int(self.save_var.get())
            if timeout <= 0 or save_interval <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers.", parent=self)
            return

        db.set_setting('inactivity_timeout_minutes', str(timeout))
        db.set_setting('auto_save_interval_seconds', str(save_interval))

        self.result = True
        self.destroy()


class BusinessSetupDialog(tk.Toplevel):
    """Dialog for setting up business and banking info (required for invoices)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Business Setup")
        self.result = None

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('450x650+%d+%d' % (parent.winfo_rootx() + 30, parent.winfo_rooty() + 30))

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)

        # Load existing data
        business = db.get_business_info() or {}
        banking = db.get_banking() or {}

        # Business Info Section
        ttk.Label(frame, text="Business Information", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))

        fields = [
            ('Company Name:', 'company_name'),
            ('Owner Name:', 'owner_name'),
            ('Address:', 'address'),
            ('City:', 'city'),
            ('State:', 'state'),
            ('ZIP:', 'zip'),
            ('Phone:', 'phone'),
            ('Email:', 'email'),
            ('EIN:', 'ein'),
        ]

        self.business_vars = {}
        for i, (label, key) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i+1, column=0, sticky='w', pady=2)
            var = tk.StringVar(value=business.get(key, ''))
            self.business_vars[key] = var
            ttk.Entry(frame, textvariable=var, width=35).grid(row=i+1, column=1, sticky='w', pady=2)

        # Banking Info Section - Domestic
        ttk.Label(frame, text="Domestic Wire / ACH", font=('Segoe UI', 10, 'bold')).grid(row=11, column=0, columnspan=2, sticky='w', pady=(15, 5))

        bank_fields = [
            ('Bank Name:', 'bank_name'),
            ('Routing Number:', 'routing_number'),
            ('Account Number:', 'account_number'),
        ]

        self.banking_vars = {}
        for i, (label, key) in enumerate(bank_fields):
            ttk.Label(frame, text=label).grid(row=12+i, column=0, sticky='w', pady=2)
            var = tk.StringVar(value=banking.get(key, ''))
            self.banking_vars[key] = var
            ttk.Entry(frame, textvariable=var, width=35).grid(row=12+i, column=1, sticky='w', pady=2)

        # International Wire Section
        ttk.Label(frame, text="International Wire", font=('Segoe UI', 10, 'bold')).grid(row=16, column=0, columnspan=2, sticky='w', pady=(15, 5))

        ttk.Label(frame, text="SWIFT Code:").grid(row=17, column=0, sticky='w', pady=2)
        self.banking_vars['swift_code'] = tk.StringVar(value=banking.get('swift_code', ''))
        ttk.Entry(frame, textvariable=self.banking_vars['swift_code'], width=35).grid(row=17, column=1, sticky='w', pady=2)

        ttk.Label(frame, text="Instructions:").grid(row=18, column=0, sticky='nw', pady=2)
        self.intl_wire_text = tk.Text(frame, width=35, height=3)
        self.intl_wire_text.grid(row=18, column=1, sticky='w', pady=2)
        self.intl_wire_text.insert('1.0', banking.get('intl_wire_instructions', ''))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=25, column=0, columnspan=2, pady=(20, 0))

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.bind('<Escape>', lambda e: self.destroy())

    def _save(self):
        """Save business and banking info."""
        # Validate required fields
        required = ['company_name', 'owner_name', 'address', 'city', 'state', 'zip', 'phone', 'email', 'ein']
        for key in required:
            if not self.business_vars[key].get().strip():
                messagebox.showerror("Error", f"Please fill in all business fields.", parent=self)
                return

        bank_required = ['bank_name', 'routing_number', 'account_number']
        for key in bank_required:
            if not self.banking_vars[key].get().strip():
                messagebox.showerror("Error", f"Please fill in all banking fields.", parent=self)
                return

        # Save business info
        business_data = {key: var.get().strip() for key, var in self.business_vars.items()}
        db.save_business_info(business_data)

        # Save banking info
        banking_data = {key: var.get().strip() for key, var in self.banking_vars.items()}
        banking_data['intl_wire_instructions'] = self.intl_wire_text.get('1.0', 'end').strip()
        db.save_banking(banking_data)

        self.result = True
        self.destroy()
