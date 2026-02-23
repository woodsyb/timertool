"""Dialog windows for manual entry, build invoice, settings, etc."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from tkcalendar import DateEntry
from tkinter import filedialog
import csv
import db
import timer_engine


class ManualEntryDialog(tk.Toplevel):
    """Dialog for adding a manual time entry."""

    def __init__(self, parent, client: Dict):
        super().__init__(parent)
        self.title("Manual Entry")
        self.configure(bg='#1c1c1c')
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

        # Default to current time (rounded down to 15-min interval)
        now = datetime.now()
        current_hour = f"{now.hour:02d}"
        current_min_rounded = f"{(now.minute // 15) * 15:02d}"

        ttk.Label(self.range_frame, text="Start:").pack(side='left')
        self.start_hour = ttk.Combobox(self.range_frame, width=3, values=hours_24)
        self.start_hour.set(current_hour)
        self.start_hour.pack(side='left', padx=2)
        ttk.Label(self.range_frame, text=":").pack(side='left')
        self.start_min = ttk.Combobox(self.range_frame, width=3, values=mins)
        self.start_min.set(current_min_rounded)
        self.start_min.pack(side='left', padx=(0, 10))
        ttk.Label(self.range_frame, text="End:").pack(side='left')
        self.end_hour = ttk.Combobox(self.range_frame, width=3, values=hours_24)
        self.end_hour.set(current_hour)
        self.end_hour.pack(side='left', padx=2)
        ttk.Label(self.range_frame, text=":").pack(side='left')
        self.end_min = ttk.Combobox(self.range_frame, width=3, values=mins)
        self.end_min.set(current_min_rounded)
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

            duration_seconds = int(hours * 3600)
            now = datetime.now()

            if date == now.date():
                # Today: work backwards from current time
                end_time = now.replace(second=0, microsecond=0)
                start_time = end_time - timedelta(seconds=duration_seconds)
            else:
                # Past dates: work backwards from 5 PM
                end_time = datetime.combine(date, datetime.min.time().replace(hour=17))
                start_time = end_time - timedelta(seconds=duration_seconds)
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

        # Check for overlapping entries (same client only)
        overlaps = db.check_time_entry_overlaps(
            self.client['id'], start_time, end_time
        )

        if overlaps:
            max_overlap = max(o['overlap_minutes'] for o in overlaps)

            if max_overlap <= 15:
                # Auto-adjust: shift start time to end of latest overlapping entry
                latest_end = max(datetime.fromisoformat(o['end_time']) for o in overlaps)
                if latest_end < end_time:
                    # Adjust start time and recalculate duration
                    start_time = latest_end
                    duration_seconds = int((end_time - start_time).total_seconds())
                    hours = duration_seconds / 3600

                    if duration_seconds <= 0:
                        messagebox.showerror(
                            "Overlap Error",
                            "Cannot adjust entry - it would have zero or negative duration.\n"
                            "The existing entry covers the entire time range.",
                            parent=self
                        )
                        return

                    messagebox.showinfo(
                        "Auto-Adjusted",
                        f"Start time adjusted to {latest_end.strftime('%I:%M %p')} to avoid overlap.",
                        parent=self
                    )
                else:
                    messagebox.showerror(
                        "Overlap Error",
                        "Cannot auto-adjust - existing entry ends after your entry.",
                        parent=self
                    )
                    return
            else:
                # Large overlap - warn user
                overlap_details = []
                for o in overlaps:
                    o_start = datetime.fromisoformat(o['start_time'])
                    o_end = datetime.fromisoformat(o['end_time'])
                    o_hours = o['duration_seconds'] / 3600
                    desc = o.get('description') or '(no description)'
                    if len(desc) > 30:
                        desc = desc[:27] + '...'
                    overlap_details.append(
                        f"  {o_start.strftime('%I:%M %p')} - {o_end.strftime('%I:%M %p')} "
                        f"({o_hours:.1f} hrs) - \"{desc}\""
                    )

                msg = (
                    f"This entry overlaps by {int(max_overlap)} minutes with:\n\n"
                    + "\n".join(overlap_details)
                    + "\n\nSave anyway?"
                )
                if not messagebox.askyesno("Overlapping Entry", msg, parent=self):
                    return

        # Check daily hours total
        existing_hours = db.get_daily_hours(self.client['id'], date)
        new_total = existing_hours + hours

        if new_total > 24:
            messagebox.showerror(
                "Invalid Entry",
                f"This entry would bring today's total to {new_total:.1f} hours.\n"
                "Cannot exceed 24 hours in a single day.",
                parent=self
            )
            return

        if new_total > 12:
            if not messagebox.askyesno(
                "High Daily Hours",
                f"This would bring today's total to {new_total:.1f} hours.\n\nContinue?",
                parent=self
            ):
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

    def __init__(self, parent, client: Dict, entries: List[Dict], week_start: str = None):
        super().__init__(parent)
        self.title("Build Invoice")
        self.configure(bg='#1c1c1c')
        self.client = client
        self.entries = entries
        self.result = None
        self.entry_vars = {}
        self.week_start = week_start  # For retainer mode
        self.is_retainer = client.get('retainer_enabled', 0)

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('600x700+%d+%d' % (parent.winfo_rootx() + 30, parent.winfo_rooty() + 30))

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)

        # Client info
        ttk.Label(frame, text=f"Invoice for: {self.client['name']}", font=('Segoe UI', 11, 'bold')).pack(anchor='w')

        rate = self.client.get('retainer_rate') or self.client['hourly_rate']
        ttk.Label(frame, text=f"Rate: ${rate:.2f}/hr").pack(anchor='w')

        # Retainer breakdown section (only for retainer clients)
        if self.is_retainer:
            self._create_retainer_section(frame)

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
        method_combo['values'] = ('ACH', 'Domestic Wire', 'International Wire', 'Check')
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

    def _create_retainer_section(self, parent):
        """Create the retainer breakdown section."""
        # Calculate week bounds from entries or use provided week_start
        if self.week_start:
            ws = datetime.fromisoformat(self.week_start)
        elif self.entries:
            # Use the week of the first entry
            first_date = min(datetime.fromisoformat(e['start_time']) for e in self.entries)
            ws, _ = db.get_week_bounds(first_date)
        else:
            ws, _ = db.get_week_bounds(datetime.now())

        self.current_week_start = ws.strftime('%Y-%m-%d')
        week_end = ws + timedelta(days=6)

        # Retainer info frame
        retainer_frame = tk.Frame(parent, bg='#2d2d2d', relief='ridge', bd=1)
        retainer_frame.pack(fill='x', pady=(10, 0))

        inner = tk.Frame(retainer_frame, bg='#2d2d2d', padx=12, pady=10)
        inner.pack(fill='x')

        # Week header
        week_str = f"{ws.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}"
        tk.Label(inner, text=f"RETAINER WEEK: {week_str}", font=('Segoe UI', 10, 'bold'),
                bg='#2d2d2d', fg='#00aaff').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))

        # Retainer details
        retainer_hours = self.client.get('retainer_hours') or 0
        rate = self.client.get('retainer_rate') or self.client.get('hourly_rate', 0)

        self.worked_hours_label = tk.Label(inner, text="Hours Worked: 0.00 hrs",
                                           font=('Segoe UI', 9), bg='#2d2d2d', fg='#ffffff')
        self.worked_hours_label.grid(row=1, column=0, sticky='w', pady=2)

        tk.Label(inner, text=f"Retainer Minimum: {retainer_hours:.2f} hrs",
                font=('Segoe UI', 9), bg='#2d2d2d', fg='#aaaaaa').grid(row=2, column=0, sticky='w', pady=2)

        self.billable_hours_label = tk.Label(inner, text="Billable Hours: 0.00 hrs",
                                              font=('Segoe UI', 9, 'bold'), bg='#2d2d2d', fg='#00ff00')
        self.billable_hours_label.grid(row=3, column=0, sticky='w', pady=2)

        # Separator
        tk.Frame(inner, bg='#444444', height=1).grid(row=4, column=0, columnspan=2, sticky='ew', pady=8)

        tk.Label(inner, text=f"Rate: ${rate:.2f}/hr", font=('Segoe UI', 9),
                bg='#2d2d2d', fg='#aaaaaa').grid(row=5, column=0, sticky='w', pady=2)

        self.retainer_total_label = tk.Label(inner, text="TOTAL: $0.00",
                                              font=('Segoe UI', 11, 'bold'), bg='#2d2d2d', fg='#00ff00')
        self.retainer_total_label.grid(row=6, column=0, sticky='w', pady=(4, 0))

        # Exempt button
        exempt_frame = tk.Frame(inner, bg='#2d2d2d')
        exempt_frame.grid(row=1, column=1, rowspan=3, sticky='ne', padx=(20, 0))

        # Check if already exempted
        self.is_exempted = db.is_week_exempted(self.client['id'], self.current_week_start)

        self.exempt_var = tk.BooleanVar(value=self.is_exempted)
        self.exempt_check = ttk.Checkbutton(exempt_frame, text="Exempt This Week",
                                            variable=self.exempt_var, command=self._toggle_exemption)
        self.exempt_check.pack(anchor='e')

        if self.is_exempted:
            exemption = db.get_retainer_exemption(self.client['id'], self.current_week_start)
            reason = exemption.get('reason', '') if exemption else ''
            tk.Label(exempt_frame, text=f"Reason: {reason[:30]}" if reason else "(no reason)",
                    font=('Segoe UI', 8), bg='#2d2d2d', fg='#888888').pack(anchor='e')

    def _toggle_exemption(self):
        """Handle exemption toggle."""
        if self.exempt_var.get():
            # Show reason dialog
            reason = self._ask_exemption_reason()
            if reason is not None:
                db.add_retainer_exemption(self.client['id'], self.current_week_start, reason)
                self.is_exempted = True
            else:
                self.exempt_var.set(False)
        else:
            db.remove_retainer_exemption(self.client['id'], self.current_week_start)
            self.is_exempted = False
        self._update_totals()

    def _ask_exemption_reason(self) -> Optional[str]:
        """Show a simple dialog to ask for exemption reason."""
        dialog = tk.Toplevel(self)
        dialog.title("Exempt Week")
        dialog.configure(bg='#1c1c1c')
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Reason for exemption (optional):").pack(anchor='w')
        reason_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=reason_var, width=40)
        entry.pack(fill='x', pady=10)
        entry.focus_set()

        result = {'value': None}

        def on_ok():
            result['value'] = reason_var.get().strip()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

        entry.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())

        dialog.geometry('+%d+%d' % (self.winfo_rootx() + 50, self.winfo_rooty() + 50))
        self.wait_window(dialog)
        return result['value']

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

        worked_hours = total_seconds / 3600
        rate = self.client.get('retainer_rate') or self.client['hourly_rate']

        # Calculate billable hours (retainer vs actual)
        if self.is_retainer and not getattr(self, 'is_exempted', False):
            retainer_hours = self.client.get('retainer_hours') or 0
            billable_hours = max(worked_hours, retainer_hours)
        else:
            billable_hours = worked_hours

        total_amount = billable_hours * rate

        self.total_hours_label.config(text=f"Total: {billable_hours:.2f} hrs")
        self.total_amount_label.config(text=timer_engine.format_currency(total_amount))

        # Update retainer breakdown if present
        if self.is_retainer and hasattr(self, 'worked_hours_label'):
            self.worked_hours_label.config(text=f"Hours Worked: {worked_hours:.2f} hrs")
            self.billable_hours_label.config(text=f"Billable Hours: {billable_hours:.2f} hrs")
            self.retainer_total_label.config(text=f"TOTAL: {timer_engine.format_currency(total_amount)}")

    def _create(self):
        """Create the invoice."""
        selected_entries = []
        for entry in self.entries:
            if self.entry_vars.get(entry['id'], tk.BooleanVar(value=False)).get():
                selected_entries.append(entry)

        if not selected_entries:
            messagebox.showerror("Error", "Please select at least one entry.", parent=self)
            return

        # Calculate retainer info
        total_seconds = sum(e['duration_seconds'] or 0 for e in selected_entries)
        worked_hours = total_seconds / 3600

        retainer_info = None
        if self.is_retainer:
            retainer_hours = self.client.get('retainer_hours') or 0
            is_exempted = getattr(self, 'is_exempted', False)
            if is_exempted:
                billable_hours = worked_hours
                retainer_hours_applied = 0
                overage_hours = worked_hours
            else:
                billable_hours = max(worked_hours, retainer_hours)
                retainer_hours_applied = min(worked_hours, retainer_hours)
                overage_hours = max(0, worked_hours - retainer_hours)

            retainer_info = {
                'is_retainer': True,
                'week_start': getattr(self, 'current_week_start', None),
                'worked_hours': worked_hours,
                'retainer_hours': retainer_hours,
                'billable_hours': billable_hours,
                'retainer_hours_applied': retainer_hours_applied,
                'overage_hours': overage_hours,
                'is_exempted': is_exempted,
            }

        self.result = {
            'entries': selected_entries,
            'description': self.desc_var.get(),
            'payment_terms': self.terms_var.get(),
            'payment_method': self.method_var.get(),
            'retainer_info': retainer_info,
        }
        self.destroy()


class IdleDialog(tk.Toplevel):
    """Dialog shown when idle timeout is triggered."""

    def __init__(self, parent, idle_seconds: int, accumulated_seconds: int):
        super().__init__(parent)
        self.title("Timer Paused")
        self.configure(bg='#1c1c1c')
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
        self.configure(bg='#1c1c1c')
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
        self.configure(bg='#1c1c1c')
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
        ttk.Button(btn_frame, text="Delete", command=self._delete_invoice).pack(side='left', padx=5)
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

    def _delete_invoice(self):
        """Delete the selected invoice."""
        selection = self.tree.selection()
        if not selection:
            return

        invoice_number = selection[0]
        invoice = db.get_invoice(invoice_number)

        if not invoice:
            messagebox.showerror("Error", f"Invoice {invoice_number} not found.", parent=self)
            return

        # Check if fully paid - block deletion
        if invoice['status'] == 'paid':
            messagebox.showerror(
                "Cannot Delete",
                f"{invoice_number} is fully paid.\n\n"
                "Paid invoices are protected financial records and cannot be deleted.",
                parent=self
            )
            return

        # Show delete confirmation dialog
        dialog = DeleteInvoiceDialog(self, invoice)
        self.wait_window(dialog)

        if dialog.result:
            try:
                result = db.delete_invoice(
                    invoice_number,
                    restore_hours=dialog.result['restore_hours'],
                    delete_pdf=dialog.result['delete_pdf']
                )

                if result['success']:
                    msg = result['message']
                    if result.get('hours_restored'):
                        msg += "\nHours restored to unbilled pool."
                    if result.get('pdf_deleted'):
                        msg += "\nPDF file deleted."
                    messagebox.showinfo("Invoice Deleted", msg, parent=self)
                    self._load_invoices()
                else:
                    messagebox.showerror("Error", result['message'], parent=self)

            except ValueError as e:
                messagebox.showerror("Cannot Delete", str(e), parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete invoice: {e}", parent=self)


class TimeEntriesDialog(tk.Toplevel):
    """Dialog showing time entries with activity details."""

    def __init__(self, parent, client_id: int = None, client_name: str = ""):
        super().__init__(parent)
        self.title(f"Time Entries - {client_name}" if client_name else "Time Entries")
        self.configure(bg='#1c1c1c')
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
        columns = ('hours', 'type', 'memo', 'keys', 'clicks', 'moves', 'status')
        self.tree = ttk.Treeview(frame, columns=columns, show='tree headings', selectmode='browse')

        self.tree.heading('#0', text='Date/Time')
        self.tree.heading('hours', text='Hours')
        self.tree.heading('type', text='Type')
        self.tree.heading('memo', text='Memo')
        self.tree.heading('keys', text='Keys')
        self.tree.heading('clicks', text='Clicks')
        self.tree.heading('moves', text='Moves')
        self.tree.heading('status', text='Status')

        self.tree.column('#0', width=140)
        self.tree.column('hours', width=60, anchor='e')
        self.tree.column('type', width=70, anchor='center')
        self.tree.column('memo', width=150, anchor='w')
        self.tree.column('keys', width=60, anchor='e')
        self.tree.column('clicks', width=60, anchor='e')
        self.tree.column('moves', width=60, anchor='e')
        self.tree.column('status', width=80, anchor='center')

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=5)

        self.add_btn = ttk.Button(btn_frame, text="Add Entry", command=self._add_entry)
        self.add_btn.pack(side='left', padx=2)
        if not self.client_id:
            self.add_btn.config(state='disabled')
        ttk.Button(btn_frame, text="Edit", command=self._edit_entry).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_entry).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Expand All", command=self._expand_all).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Collapse All", command=self._collapse_all).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side='right', padx=2)

        # Totals
        totals_frame = ttk.Frame(self)
        totals_frame.pack(fill='x', padx=10, pady=5)

        self.totals_label = ttk.Label(totals_frame, text="", font=('Segoe UI', 9))
        self.totals_label.pack(side='left')

    def _add_entry(self):
        """Add a manual time entry."""
        if not self.client_id:
            return

        client = db.get_client(self.client_id)
        if not client:
            messagebox.showerror("Error", "Client not found.", parent=self)
            return

        dialog = ManualEntryDialog(self, client)
        self.wait_window(dialog)

        if dialog.result:
            db.save_time_entry(
                client_id=self.client_id,
                start_time=dialog.result['start_time'],
                end_time=dialog.result['end_time'],
                duration_seconds=dialog.result['duration_seconds'],
                description=dialog.result['description'],
                entry_type='manual'
            )
            self._load_entries()
            messagebox.showinfo(
                "Success",
                f"Added {dialog.result['hours']:.2f} hours.",
                parent=self
            )

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

        # Store for export
        self.current_entries = entries

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

                memo = entry.get('description', '') or ''
                if len(memo) > 25:
                    memo = memo[:22] + '...'

                self.tree.insert(date_id, 'end', iid=str(entry['id']),
                               text=dt.strftime('%H:%M'),
                               values=(f"{hours:.2f}",
                                      entry_type,
                                      memo,
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

    def _expand_all(self):
        """Expand all date groups."""
        for item in self.tree.get_children():
            self.tree.item(item, open=True)

    def _collapse_all(self):
        """Collapse all date groups."""
        for item in self.tree.get_children():
            self.tree.item(item, open=False)

    def _export_csv(self):
        """Export current entries to CSV."""
        if not hasattr(self, 'current_entries') or not self.current_entries:
            messagebox.showinfo("No Data", "No entries to export.", parent=self)
            return

        # Generate default filename
        filter_name = self.filter_var.get()
        date_str = datetime.now().strftime('%Y%m%d')
        default_name = f"time_entries_{filter_name}_{date_str}.csv"

        filepath = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_name
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header
                writer.writerow([
                    'Date', 'Start Time', 'End Time', 'Hours', 'Type',
                    'Description', 'Key Presses', 'Mouse Clicks', 'Mouse Moves',
                    'Status', 'Invoice Number'
                ])

                for entry in self.current_entries:
                    dt = datetime.fromisoformat(entry['start_time'])
                    end_dt = datetime.fromisoformat(entry['end_time']) if entry.get('end_time') else None
                    hours = (entry['duration_seconds'] or 0) / 3600

                    # Determine status
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

                    writer.writerow([
                        dt.strftime('%Y-%m-%d'),
                        dt.strftime('%H:%M:%S'),
                        end_dt.strftime('%H:%M:%S') if end_dt else '',
                        f"{hours:.2f}",
                        entry.get('entry_type', 'stopwatch'),
                        entry.get('description', '') or '',
                        entry.get('key_presses') or 0,
                        entry.get('mouse_clicks') or 0,
                        entry.get('mouse_moves') or 0,
                        status,
                        entry.get('invoice_number', '') or ''
                    ])

            messagebox.showinfo("Export Complete",
                              f"Exported {len(self.current_entries)} entries to:\n{filepath}",
                              parent=self)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}", parent=self)


class EditTimeEntryDialog(tk.Toplevel):
    """Dialog for editing a time entry."""

    def __init__(self, parent, entry: Dict):
        super().__init__(parent)
        self.title("Edit Time Entry")
        self.configure(bg='#1c1c1c')
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
        self.configure(bg='#1c1c1c')
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


class DeleteInvoiceDialog(tk.Toplevel):
    """Dialog for confirming invoice deletion with options."""

    def __init__(self, parent, invoice: Dict):
        super().__init__(parent)
        self.title("Delete Invoice")
        self.configure(bg='#1c1c1c')
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

        # Invoice info header
        ttk.Label(frame, text=f"Delete Invoice: {self.invoice['invoice_number']}",
                 font=('Segoe UI', 11, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))

        # Invoice details
        ttk.Label(frame, text=f"Client: {self.invoice.get('client_name', 'Unknown')}").grid(
            row=1, column=0, columnspan=2, sticky='w', pady=2)
        ttk.Label(frame, text=f"Date: {self.invoice['date_issued']}").grid(
            row=2, column=0, columnspan=2, sticky='w', pady=2)
        ttk.Label(frame, text=f"Total: ${total:.2f}").grid(
            row=3, column=0, columnspan=2, sticky='w', pady=2)

        # Warning for partial payments
        if paid > 0:
            ttk.Separator(frame, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky='ew', pady=10)
            warning_frame = ttk.Frame(frame)
            warning_frame.grid(row=5, column=0, columnspan=2, sticky='w', pady=5)

            ttk.Label(warning_frame, text="WARNING:", font=('Segoe UI', 9, 'bold'),
                     foreground='#ff9800').pack(side='left')
            ttk.Label(warning_frame, text=f" ${paid:.2f} in payments recorded",
                     foreground='#ff9800').pack(side='left')

            ttk.Label(frame, text="Hours will return to unbilled pool. You must\n"
                                  "handle payment accounting externally.",
                     font=('Segoe UI', 8), foreground='gray').grid(
                row=6, column=0, columnspan=2, sticky='w', pady=(0, 5))

        # Options
        ttk.Separator(frame, orient='horizontal').grid(row=7, column=0, columnspan=2, sticky='ew', pady=10)
        ttk.Label(frame, text="Options:", font=('Segoe UI', 9, 'bold')).grid(
            row=8, column=0, columnspan=2, sticky='w', pady=(0, 5))

        # Restore hours checkbox
        self.restore_hours_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Restore hours to unbilled pool",
                       variable=self.restore_hours_var).grid(row=9, column=0, columnspan=2, sticky='w', pady=2)

        # Delete PDF checkbox
        self.delete_pdf_var = tk.BooleanVar(value=True)
        pdf_path = db.get_invoice_pdf_path(self.invoice['invoice_number'])
        pdf_exists = pdf_path is not None
        pdf_text = "Delete PDF file" if pdf_exists else "Delete PDF file (not found)"
        cb = ttk.Checkbutton(frame, text=pdf_text, variable=self.delete_pdf_var)
        cb.grid(row=10, column=0, columnspan=2, sticky='w', pady=2)
        if not pdf_exists:
            cb.configure(state='disabled')
            self.delete_pdf_var.set(False)

        # Confirmation text
        ttk.Separator(frame, orient='horizontal').grid(row=11, column=0, columnspan=2, sticky='ew', pady=10)
        ttk.Label(frame, text="This action cannot be undone.",
                 font=('Segoe UI', 9), foreground='#f44336').grid(
            row=12, column=0, columnspan=2, sticky='w', pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=13, column=0, columnspan=2, pady=(5, 0))

        ttk.Button(btn_frame, text="Delete Invoice", command=self._delete,
                  style='Accent.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.bind('<Escape>', lambda e: self.destroy())

    def _delete(self):
        """Confirm and execute deletion."""
        self.result = {
            'restore_hours': self.restore_hours_var.get(),
            'delete_pdf': self.delete_pdf_var.get()
        }
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """Dialog for app settings."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.configure(bg='#1c1c1c')
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
        ttk.Entry(frame, textvariable=self.timeout_var, width=10).grid(row=0, column=1, columnspan=2, sticky='w', pady=5)

        # Auto-save interval
        ttk.Label(frame, text="Auto-save Interval (seconds):").grid(row=1, column=0, sticky='w', pady=5)
        self.save_var = tk.StringVar(value=db.get_setting('auto_save_interval_seconds', '30'))
        ttk.Entry(frame, textvariable=self.save_var, width=10).grid(row=1, column=1, columnspan=2, sticky='w', pady=5)

        # Data folder info
        ttk.Label(frame, text="Data Folder:").grid(row=2, column=0, sticky='w', pady=5)
        data_path = str(db.get_data_dir())
        ttk.Label(frame, text=data_path, foreground='gray').grid(row=2, column=1, columnspan=2, sticky='w', pady=5)

        # Backup location
        ttk.Label(frame, text="Backup Location:").grid(row=3, column=0, sticky='w', pady=5)
        self.backup_var = tk.StringVar(value=db.get_setting('backup_location', ''))
        backup_entry = ttk.Entry(frame, textvariable=self.backup_var, width=30)
        backup_entry.grid(row=3, column=1, sticky='w', pady=5)
        ttk.Button(frame, text="Browse...", command=self._browse_backup, width=8).grid(row=3, column=2, sticky='w', padx=5, pady=5)

        ttk.Label(frame, text="(Leave blank for default)",
                 font=('Segoe UI', 8), foreground='gray').grid(row=4, column=0, columnspan=3, sticky='w')

        # Screenshot storage section
        ttk.Label(frame, text="Screenshot Storage:").grid(row=5, column=0, sticky='w', pady=5)
        self.screenshot_dir_var = tk.StringVar(value=db.get_setting('screenshot_local_dir', ''))
        screenshot_entry = ttk.Entry(frame, textvariable=self.screenshot_dir_var, width=30)
        screenshot_entry.grid(row=5, column=1, sticky='w', pady=5)
        ttk.Button(frame, text="Browse...", command=self._browse_screenshot, width=8).grid(row=5, column=2, sticky='w', padx=5, pady=5)

        ttk.Label(frame, text="(Leave blank for default: data/screenshots/)",
                 font=('Segoe UI', 8), foreground='gray').grid(row=6, column=0, columnspan=3, sticky='w')

        # S3 Backup section
        ttk.Separator(frame, orient='horizontal').grid(row=7, column=0, columnspan=3, sticky='ew', pady=10)
        ttk.Label(frame, text="S3 Backup (optional)", font=('Segoe UI', 9, 'bold')).grid(row=8, column=0, columnspan=3, sticky='w')

        ttk.Label(frame, text="Bucket:").grid(row=9, column=0, sticky='w', pady=2)
        self.s3_bucket_var = tk.StringVar(value=db.get_setting('s3_bucket', ''))
        ttk.Entry(frame, textvariable=self.s3_bucket_var, width=30).grid(row=9, column=1, columnspan=2, sticky='w', pady=2)

        ttk.Label(frame, text="Region:").grid(row=10, column=0, sticky='w', pady=2)
        self.s3_region_var = tk.StringVar(value=db.get_setting('s3_region', 'us-east-1'))
        ttk.Entry(frame, textvariable=self.s3_region_var, width=15).grid(row=10, column=1, columnspan=2, sticky='w', pady=2)

        ttk.Label(frame, text="Access Key:").grid(row=11, column=0, sticky='w', pady=2)
        self.s3_access_var = tk.StringVar(value=db.get_setting('s3_access_key', ''))
        ttk.Entry(frame, textvariable=self.s3_access_var, width=30).grid(row=11, column=1, columnspan=2, sticky='w', pady=2)

        ttk.Label(frame, text="Secret Key:").grid(row=12, column=0, sticky='w', pady=2)
        self.s3_secret_var = tk.StringVar(value=db.get_setting('s3_secret_key', ''))
        ttk.Entry(frame, textvariable=self.s3_secret_var, width=30, show='*').grid(row=12, column=1, columnspan=2, sticky='w', pady=2)

        ttk.Label(frame, text="(Uploads to s3://bucket/timertool-backups/ on startup)",
                 font=('Segoe UI', 8), foreground='gray').grid(row=13, column=0, columnspan=3, sticky='w')

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=14, column=0, columnspan=3, pady=(15, 0))

        ttk.Button(btn_frame, text="Save", command=self._save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.bind('<Escape>', lambda e: self.destroy())

    def _browse_backup(self):
        """Browse for backup folder."""
        folder = filedialog.askdirectory(
            parent=self,
            title="Select Backup Folder",
            initialdir=self.backup_var.get() or str(db.get_data_dir())
        )
        if folder:
            self.backup_var.set(folder)

    def _browse_screenshot(self):
        """Browse for screenshot folder."""
        folder = filedialog.askdirectory(
            parent=self,
            title="Select Screenshot Folder",
            initialdir=self.screenshot_dir_var.get() or str(db.get_data_dir())
        )
        if folder:
            self.screenshot_dir_var.set(folder)

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

        # Validate backup location if set
        backup_loc = self.backup_var.get().strip()
        if backup_loc:
            from pathlib import Path
            if not Path(backup_loc).exists():
                messagebox.showerror("Error", "Backup location does not exist.", parent=self)
                return

        db.set_setting('inactivity_timeout_minutes', str(timeout))
        db.set_setting('auto_save_interval_seconds', str(save_interval))
        db.set_setting('backup_location', backup_loc)
        db.set_setting('screenshot_local_dir', self.screenshot_dir_var.get().strip())

        # S3 settings
        db.set_setting('s3_bucket', self.s3_bucket_var.get().strip())
        db.set_setting('s3_region', self.s3_region_var.get().strip())
        db.set_setting('s3_access_key', self.s3_access_var.get().strip())
        db.set_setting('s3_secret_key', self.s3_secret_var.get().strip())

        self.result = True
        self.destroy()


class BusinessSetupDialog(tk.Toplevel):
    """Dialog for setting up business and banking info (required for invoices)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Business Setup")
        self.configure(bg='#1c1c1c')
        self.result = None

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('450x900+%d+%d' % (parent.winfo_rootx() + 30, parent.winfo_rooty() + 30))

    def _create_widgets(self):
        # Scrollable container
        canvas = tk.Canvas(self, bg='#1c1c1c', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        frame = ttk.Frame(canvas, padding=15)
        canvas_frame = canvas.create_window((0, 0), window=frame, anchor='nw')

        def on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def on_canvas_configure(e):
            canvas.itemconfig(canvas_frame, width=e.width)

        frame.bind('<Configure>', on_frame_configure)
        canvas.bind('<Configure>', on_canvas_configure)

        # Mouse wheel scrolling
        def on_mousewheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), 'units')
        canvas.bind_all('<MouseWheel>', on_mousewheel)

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

        # Banking Info Section - ACH
        ttk.Label(frame, text="ACH / Direct Deposit", font=('Segoe UI', 10, 'bold')).grid(row=11, column=0, columnspan=2, sticky='w', pady=(15, 5))

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

        # Domestic Wire Section
        row = 16
        ttk.Label(frame, text="Domestic Wire", font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(15, 5))
        row += 1
        self.domestic_wire_text = tk.Text(frame, width=40, height=4)
        self.domestic_wire_text.grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        self.domestic_wire_text.insert('1.0', banking.get('domestic_wire_instructions', '') or '')
        row += 1

        # International Wire Section
        ttk.Label(frame, text="International Wire (SWIFT)", font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(15, 5))
        row += 1
        self.wire_text = tk.Text(frame, width=40, height=6)
        self.wire_text.grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        self.wire_text.insert('1.0', banking.get('wire_instructions', '') or '')
        row += 1

        # PayPal Section
        ttk.Label(frame, text="PayPal", font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(15, 5))
        row += 1
        ttk.Label(frame, text="Email:").grid(row=row, column=0, sticky='w', pady=2)
        self.banking_vars['paypal_email'] = tk.StringVar(value=banking.get('paypal_email', '') or '')
        ttk.Entry(frame, textvariable=self.banking_vars['paypal_email'], width=35).grid(row=row, column=1, sticky='w', pady=2)
        row += 1

        # Credit Card Section
        ttk.Label(frame, text="Credit Card", font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(15, 5))
        row += 1
        self.cc_text = tk.Text(frame, width=40, height=2)
        self.cc_text.grid(row=row, column=0, columnspan=2, sticky='w', pady=2)
        self.cc_text.insert('1.0', banking.get('credit_card_instructions', '') or '')
        row += 1

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(20, 0))

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
        banking_data['domestic_wire_instructions'] = self.domestic_wire_text.get('1.0', 'end').strip()
        banking_data['wire_instructions'] = self.wire_text.get('1.0', 'end').strip()
        banking_data['credit_card_instructions'] = self.cc_text.get('1.0', 'end').strip()
        db.save_banking(banking_data)

        self.result = True
        self.destroy()


class TaxYearSummaryDialog(tk.Toplevel):
    """Dialog showing income summary for tax purposes."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Tax Year Summary")
        self.configure(bg='#1c1c1c')

        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.geometry('650x500+%d+%d' % (parent.winfo_rootx() + 30, parent.winfo_rooty() + 30))
        self._load_summary()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)

        # Year selector
        year_frame = ttk.Frame(frame)
        year_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(year_frame, text="Tax Year:", font=('Segoe UI', 10)).pack(side='left')
        current_year = datetime.now().year
        years = [str(y) for y in range(current_year, current_year - 5, -1)]
        self.year_var = tk.StringVar(value=str(current_year))
        year_combo = ttk.Combobox(year_frame, textvariable=self.year_var, values=years, width=8, state='readonly')
        year_combo.pack(side='left', padx=10)
        year_combo.bind('<<ComboboxSelected>>', lambda e: self._load_summary())

        # Total income display
        self.total_frame = ttk.Frame(frame)
        self.total_frame.pack(fill='x', pady=10)

        ttk.Label(self.total_frame, text="Total Income:", font=('Segoe UI', 11)).pack(side='left')
        self.total_label = ttk.Label(self.total_frame, text="$0.00", font=('Segoe UI', 14, 'bold'), foreground='#4caf50')
        self.total_label.pack(side='left', padx=10)

        ttk.Label(self.total_frame, text="(This is what you report on Schedule C)", font=('Segoe UI', 9), foreground='gray').pack(side='left')

        # Quarterly breakdown (for estimated taxes)
        quarter_frame = ttk.Frame(frame)
        quarter_frame.pack(fill='x', pady=5)

        self.q_labels = {}
        for i, q in enumerate(['Q1 (Jan-Mar)', 'Q2 (Apr-Jun)', 'Q3 (Jul-Sep)', 'Q4 (Oct-Dec)']):
            qf = ttk.Frame(quarter_frame)
            qf.pack(side='left', padx=10)
            ttk.Label(qf, text=q, font=('Segoe UI', 8), foreground='gray').pack()
            self.q_labels[f"q{i+1}"] = ttk.Label(qf, text="$0", font=('Segoe UI', 9))
            self.q_labels[f"q{i+1}"].pack()

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)

        # By client breakdown
        ttk.Label(frame, text="Income by Client:", font=('Segoe UI', 10, 'bold')).pack(anchor='w')

        # Treeview for client breakdown
        columns = ('total', 'invoices')
        self.client_tree = ttk.Treeview(frame, columns=columns, show='tree headings', height=6)
        self.client_tree.heading('#0', text='Client')
        self.client_tree.heading('total', text='Total Paid')
        self.client_tree.heading('invoices', text='Invoices')
        self.client_tree.column('#0', width=300)
        self.client_tree.column('total', width=120, anchor='e')
        self.client_tree.column('invoices', width=80, anchor='center')
        self.client_tree.pack(fill='x', pady=5)

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=10)

        # Invoice details
        ttk.Label(frame, text="Paid Invoices:", font=('Segoe UI', 10, 'bold')).pack(anchor='w')

        inv_columns = ('client', 'date_paid', 'amount')
        self.inv_tree = ttk.Treeview(frame, columns=inv_columns, show='headings', height=8)
        self.inv_tree.heading('client', text='Client')
        self.inv_tree.heading('date_paid', text='Date Paid')
        self.inv_tree.heading('amount', text='Amount')
        self.inv_tree.column('client', width=250)
        self.inv_tree.column('date_paid', width=120)
        self.inv_tree.column('amount', width=100, anchor='e')

        inv_scroll = ttk.Scrollbar(frame, orient='vertical', command=self.inv_tree.yview)
        self.inv_tree.configure(yscrollcommand=inv_scroll.set)
        self.inv_tree.pack(side='left', fill='both', expand=True)
        inv_scroll.pack(side='right', fill='y')

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=15, pady=10)

        ttk.Button(btn_frame, text="Export CSV", command=self._export_csv).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Export TXF (TurboTax)", command=self._export_txf).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side='right', padx=5)

        self.bind('<Escape>', lambda e: self.destroy())

    def _load_summary(self):
        """Load summary for selected year."""
        year = int(self.year_var.get())
        self.summary = db.get_tax_year_summary(year)

        # Update total
        self.total_label.config(text=f"${self.summary['total_income']:,.2f}")

        # Update quarterly
        for q in ['q1', 'q2', 'q3', 'q4']:
            amount = self.summary['quarters'].get(q, 0)
            self.q_labels[q].config(text=f"${amount:,.0f}")

        # Update client tree
        for item in self.client_tree.get_children():
            self.client_tree.delete(item)

        for client in self.summary['by_client']:
            name = client['client_name']
            if client['company_name'] and client['company_name'] != name:
                name = f"{name} ({client['company_name']})"
            self.client_tree.insert('', 'end', text=name,
                                   values=(f"${client['total_paid']:,.2f}", client['invoice_count']))

        # Update invoice tree
        for item in self.inv_tree.get_children():
            self.inv_tree.delete(item)

        for inv in self.summary['invoices']:
            self.inv_tree.insert('', 'end', iid=inv['invoice_number'],
                               values=(inv['client_name'], inv['date_paid'], f"${inv['total']:,.2f}"))

    def _export_csv(self):
        """Export summary to CSV."""
        if not self.summary or not self.summary['invoices']:
            messagebox.showinfo("No Data", "No invoices to export for this year.", parent=self)
            return

        year = self.year_var.get()
        default_name = f"tax_summary_{year}.csv"

        filepath = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=default_name
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Summary section
                writer.writerow([f"Tax Year {year} Income Summary"])
                writer.writerow([])
                writer.writerow(["Total Income", f"${self.summary['total_income']:,.2f}"])
                writer.writerow([])

                # By client
                writer.writerow(["Income by Client"])
                writer.writerow(["Client", "Total Paid", "Invoice Count"])
                for client in self.summary['by_client']:
                    name = client['client_name']
                    if client['company_name'] and client['company_name'] != name:
                        name = f"{name} ({client['company_name']})"
                    writer.writerow([name, f"${client['total_paid']:,.2f}", client['invoice_count']])
                writer.writerow([])

                # Invoice details
                writer.writerow(["Invoice Details"])
                writer.writerow(["Invoice #", "Client", "Date Issued", "Date Paid", "Amount", "Description"])
                for inv in self.summary['invoices']:
                    writer.writerow([
                        inv['invoice_number'],
                        inv['client_name'],
                        inv['date_issued'],
                        inv['date_paid'],
                        f"${inv['total']:,.2f}",
                        inv.get('description', '')
                    ])

            messagebox.showinfo("Export Complete", f"Exported to:\n{filepath}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}", parent=self)

    def _export_txf(self):
        """Export summary to TXF format for TurboTax import."""
        if not self.summary or not self.summary['invoices']:
            messagebox.showinfo("No Data", "No invoices to export for this year.", parent=self)
            return

        year = self.year_var.get()
        default_name = f"schedule_c_income_{year}.txf"

        filepath = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".txf",
            filetypes=[("TXF files", "*.txf"), ("All files", "*.*")],
            initialfile=default_name
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # TXF Header
                f.write("V042\n")  # Version
                f.write("ATimerTool\n")  # Application name
                f.write(f"D{datetime.now().strftime('%m/%d/%Y')}\n")  # Export date
                f.write("^\n")  # Record separator

                # N293 = Schedule C Gross Receipts (Line 1)
                # One record per client for detail
                for client in self.summary['by_client']:
                    name = client['client_name']
                    if client['company_name'] and client['company_name'] != name:
                        name = f"{name} ({client['company_name']})"

                    f.write("TD\n")  # Detail record
                    f.write("N293\n")  # Gross receipts
                    f.write("C1\n")  # Copy 1
                    f.write("L1\n")  # Line 1
                    f.write(f"P{name}\n")  # Description (client name)
                    f.write(f"${client['total_paid']:.2f}\n")  # Amount
                    f.write("^\n")  # Record separator

            messagebox.showinfo(
                "TXF Export Complete",
                f"Exported to:\n{filepath}\n\n"
                f"To import into TurboTax Desktop:\n"
                f"File > Import > From Accounting Software\n"
                f"Select 'Other' and browse to this file.",
                parent=self
            )
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}", parent=self)
