from taipy.gui import Gui, notify
from datetime import datetime, date, timedelta
import sqlite3
import pandas as pd

# ---- Pay Period Configuration (FIXED - Biweekly 14-day periods) ----
PAY_PERIODS = [
    {"start": "2025-08-10", "end": "2025-08-23", "label": "Aug 10-23, 2025"},
    {"start": "2025-08-24", "end": "2025-09-06", "label": "Aug 24 - Sep 6, 2025"},
    {"start": "2025-09-07", "end": "2025-09-20", "label": "Sep 7-20, 2025"},
    {"start": "2025-09-21", "end": "2025-10-04", "label": "Sep 21 - Oct 4, 2025"},
    {"start": "2025-10-05", "end": "2025-10-18", "label": "Oct 5-18, 2025"},
    {"start": "2025-10-19", "end": "2025-11-01", "label": "Oct 19 - Nov 1, 2025"},
    {"start": "2025-11-02", "end": "2025-11-15", "label": "Nov 2-15, 2025"},
    {"start": "2025-11-16", "end": "2025-11-29", "label": "Nov 16-29, 2025"},
    {"start": "2025-11-30", "end": "2025-12-13", "label": "Nov 30 - Dec 13, 2025"},
    {"start": "2025-12-14", "end": "2025-12-27", "label": "Dec 14-27, 2025"},
]

def get_pay_period_for_date(target_date):
    """Find which pay period a date falls into"""
    target_dt = pd.to_datetime(str(target_date)).date()
    
    for period in PAY_PERIODS:
        start_date = pd.to_datetime(period["start"]).date()
        end_date = pd.to_datetime(period["end"]).date()
        
        if start_date <= target_dt <= end_date:
            return period
    
    return {
        "start": str(target_dt),
        "end": str(target_dt + timedelta(days=13)),  # 14-day periods
        "label": f"Period starting {target_date}"
    }

def get_current_and_previous_periods():
    """Get current and previous pay periods based on today's date"""
    today = date.today()
    current_period = get_pay_period_for_date(today)
    
    current_start = pd.to_datetime(current_period["start"]).date()
    previous_period = None
    
    for period in PAY_PERIODS:
        end_date = pd.to_datetime(period["end"]).date()
        if end_date < current_start:
            previous_period = period
    
    if not previous_period:
        prev_end = current_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=13)  # 14-day periods
        previous_period = {
            "start": str(prev_start),
            "end": str(prev_end),
            "label": f"Previous Period"
        }
    
    return current_period, previous_period

# ---- Database functions ----
def check_database_structure():
    """Check and fix database structure"""
    try:
        conn = sqlite3.connect("timesheet.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shifts'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            cursor.execute("PRAGMA table_info(shifts)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            missing_columns = []
            
            if 'date' not in column_names:
                missing_columns.append('date')
            if 'created_at' not in column_names:
                missing_columns.append('created_at')
                
            if missing_columns:
                print(f"Missing columns: {missing_columns}")
                cursor.execute("DROP TABLE shifts")
                conn.commit()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            per_diem TEXT,
            site_bonus INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Database setup error: {e}")
        return False

def get_saved_shifts():
    """Get saved shifts with ID for deletion"""
    try:
        conn = sqlite3.connect("timesheet.db")
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(shifts)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'created_at' in column_names:
            query = """
                SELECT id, date, start_time, end_time, per_diem, 
                       CASE WHEN site_bonus = 1 THEN 'Yes' ELSE 'No' END as site_bonus
                FROM shifts 
                ORDER BY date DESC, created_at DESC
            """
        else:
            query = """
                SELECT id, date, start_time, end_time, per_diem, 
                       CASE WHEN site_bonus = 1 THEN 'Yes' ELSE 'No' END as site_bonus
                FROM shifts 
                ORDER BY date DESC, id DESC
            """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        print(f"Loaded {len(df)} shifts from database")
        return df
        
    except Exception as e:
        print(f"Error loading shifts: {e}")
        return pd.DataFrame({
            'id': [], 'date': [], 'start_time': [], 'end_time': [], 
            'per_diem': [], 'site_bonus': []
        })

def save_shift_to_db(shift_date, start_time, end_time, per_diem, site_bonus):
    """Save shift to database"""
    try:
        conn = sqlite3.connect("timesheet.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shifts (date, start_time, end_time, per_diem, site_bonus) 
            VALUES (?, ?, ?, ?, ?)
        """, (str(shift_date), start_time, end_time, per_diem, 1 if site_bonus else 0))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Save error: {e}")
        return False

def delete_shift_from_db(shift_id):
    """Delete a shift from the database by ID"""
    try:
        conn = sqlite3.connect("timesheet.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        return affected_rows > 0
    except Exception as e:
        print(f"Delete error: {e}")
        return False

def delete_all_shifts():
    """Delete all shifts from database"""
    try:
        conn = sqlite3.connect("timesheet.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shifts")
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        return affected_rows
    except Exception as e:
        print(f"Delete all error: {e}")
        return 0
    
def bulk_add_shifts(state):
    if state.bulk_end_date < state.bulk_start_date:
        state.bulk_shift_message = "❌ End date must be after start date"
        notify(state, "error", state.bulk_shift_message)
        return
    count = 0
    curr = state.bulk_start_date
    while curr <= state.bulk_end_date:
        if save_shift_to_db(curr, state.start_time.strip(), state.end_time.strip(), state.per_diem, state.site_bonus):
            count += 1
        curr += timedelta(days=1)
    state.saved_shifts = get_saved_shifts()
    update_pay_calculations(state)
    state.bulk_shift_message = f"✅ Bulk added {count} shifts from {state.bulk_start_date} to {state.bulk_end_date}"
    notify(state, "success", state.bulk_shift_message)


# ---- Calculator Logic (FIXED for biweekly) ----
PER_DIEM_RATES = {
    "None": 0,
    "Breakfast Only": 11 + 4,       # 15
    "Breakfast + Lunch": 12 + 8,    # 20
    "Breakfast + Lunch + Dinner": 41 + 13, # 54
    "Lunch + Dinner": 30 + 9,       # 39
    "Dinner Only": 18 + 5           # 23
}

def calc_pay_period(week1_hours, week2_hours, week1_per_diem, week2_per_diem, 
                            week1_site_bonus_days, week2_site_bonus_days, 
                            base_weekly, site_bonus_day, tax_rate=0.15):
    """Calculate pay for a BIWEEKLY pay period - CORRECTED FOR FLSA COMPLIANCE"""
    
    def calc_weekly_pay(hours, per_diem_choices, site_bonus_days, base_weekly, site_bonus_day):
        """Calculate pay for one week"""
        base_pay = base_weekly
        site_bonus = site_bonus_day * site_bonus_days
        
        # FLSA overtime: anything over 40 hours per week
        ot_pay = 0
        if hours > 40:
            regular_rate = (base_pay + site_bonus) / hours
            ot_hours = hours - 40
            ot_pay = ot_hours * (0.5 * regular_rate)
        
        taxable_gross = base_pay + site_bonus + ot_pay
        per_diem_total = sum(PER_DIEM_RATES.get(choice, 0) for choice in per_diem_choices)
        
        return taxable_gross, per_diem_total, ot_pay
    
    # Calculate each week separately (FLSA requirement)
    w1_gross, w1_per_diem, w1_ot = calc_weekly_pay(week1_hours, week1_per_diem, 
                                                   week1_site_bonus_days, base_weekly, site_bonus_day)
    w2_gross, w2_per_diem, w2_ot = calc_weekly_pay(week2_hours, week2_per_diem, 
                                                   week2_site_bonus_days, base_weekly, site_bonus_day)
    
    # Combine totals
    total_taxable_gross = w1_gross + w2_gross
    total_per_diem = w1_per_diem + w2_per_diem
    total_ot = w1_ot + w2_ot
    
    # Calculate taxes on biweekly total
    taxes = total_taxable_gross * tax_rate
    after_tax = total_taxable_gross - taxes + total_per_diem
    
    print(f"CORRECTED BIWEEKLY PAY CALCULATION:")
    print(f"  Week 1: {week1_hours} hrs, OT: ${w1_ot:.2f}")
    print(f"  Week 2: {week2_hours} hrs, OT: ${w2_ot:.2f}")
    print(f"  Total Overtime: ${total_ot:.2f}")
    print(f"  Total Taxable Gross: ${total_taxable_gross:.2f}")
    print(f"  Total Per Diem: ${total_per_diem:.2f}")
    print(f"  After Tax: ${after_tax:.2f}")
    
    return total_taxable_gross, total_per_diem, after_tax


def calculate_hours_from_timesheet(start_time, end_time):
    """Calculate hours worked from start and end time"""
    try:
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")
        
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        
        duration = end_dt - start_dt
        return duration.total_seconds() / 3600
    except:
        return 0

def analyze_timesheet_by_periods():
    """Analyze timesheet data by defined pay periods with weekly overtime calculation"""
    try:
        conn = sqlite3.connect("timesheet.db")
        
        query = """
            SELECT date, start_time, end_time, per_diem, site_bonus, created_at
            FROM shifts 
            ORDER BY date DESC, created_at DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {
                'current_period': {
                    'week1_hours': 0, 'week2_hours': 0,
                    'week1_per_diem': [], 'week2_per_diem': [],
                    'week1_site_bonus_days': 0, 'week2_site_bonus_days': 0,
                    'period_label': 'No data'
                },
                'previous_period': {
                    'week1_hours': 0, 'week2_hours': 0,
                    'week1_per_diem': [], 'week2_per_diem': [],
                    'week1_site_bonus_days': 0, 'week2_site_bonus_days': 0,
                    'period_label': 'No data'
                },
                'recent_shifts': df,
                'total_shifts': 0
            }
        
        df['date'] = pd.to_datetime(df['date'])
        df['hours'] = df.apply(lambda row: calculate_hours_from_timesheet(
            row['start_time'], row['end_time']), axis=1)
        
        current_period_info, previous_period_info = get_current_and_previous_periods()
        
        current_start = pd.to_datetime(current_period_info["start"])
        current_end = pd.to_datetime(current_period_info["end"])
        current_period_data = df[(df['date'] >= current_start) & (df['date'] <= current_end)]
        
        previous_start = pd.to_datetime(previous_period_info["start"])
        previous_end = pd.to_datetime(previous_period_info["end"])
        previous_period_data = df[(df['date'] >= previous_start) & (df['date'] <= previous_end)]
        
        def analyze_period_weekly(period_df, period_start_str, period_label):
            """Split biweekly period into two weeks for FLSA compliance"""
            if period_df.empty:
                return {
                    'week1_hours': 0, 'week2_hours': 0,
                    'week1_per_diem': [], 'week2_per_diem': [],
                    'week1_site_bonus_days': 0, 'week2_site_bonus_days': 0,
                    'period_label': period_label,
                    'hours': 0,
                    'days': 0,
                    'site_bonus_days': 0
                }
            
            # Split the 14-day biweekly period into two 7-day weeks
            period_start = pd.to_datetime(period_start_str)
            week1_end = period_start + timedelta(days=6)  # Days 0-6 (7 days)
            week1_start = period_start
            week2_start = period_start + timedelta(days=7)  # Days 7-13 (7 days)
            
            # Filter data for each week
            week1_data = period_df[
                (period_df['date'] >= week1_start) & 
                (period_df['date'] <= week1_end)
            ]
            
            week2_data = period_df[
                (period_df['date'] >= week2_start)
            ]
            
            # Calculate weekly totals
            week1_hours = week1_data['hours'].sum() if not week1_data.empty else 0
            week2_hours = week2_data['hours'].sum() if not week2_data.empty else 0
            
            week1_per_diem = week1_data['per_diem'].tolist() if not week1_data.empty else []
            week2_per_diem = week2_data['per_diem'].tolist() if not week2_data.empty else []
            
            week1_site_bonus_days = (week1_data['site_bonus'] == 1).sum() if not week1_data.empty else 0
            week2_site_bonus_days = (week2_data['site_bonus'] == 1).sum() if not week2_data.empty else 0
            
            print(f"Period Analysis: {period_label}")
            print(f"  Week 1 ({week1_start.strftime('%m/%d')} - {week1_end.strftime('%m/%d')}): {week1_hours:.1f} hrs, {len(week1_data)} days, {week1_site_bonus_days} bonus days")
            print(f"  Week 2 ({week2_start.strftime('%m/%d')} onwards): {week2_hours:.1f} hrs, {len(week2_data)} days, {week2_site_bonus_days} bonus days")
            
            return {
                'week1_hours': week1_hours,
                'week2_hours': week2_hours,
                'week1_per_diem': week1_per_diem,
                'week2_per_diem': week2_per_diem,
                'week1_site_bonus_days': week1_site_bonus_days,
                'week2_site_bonus_days': week2_site_bonus_days,
                'period_label': period_label,
                # Keep legacy fields for compatibility
                'hours': week1_hours + week2_hours,
                'days': len(period_df),
                'site_bonus_days': week1_site_bonus_days + week2_site_bonus_days
            }
        
        return {
            'current_period': analyze_period_weekly(
                current_period_data, 
                current_period_info["start"], 
                current_period_info["label"]
            ),
            'previous_period': analyze_period_weekly(
                previous_period_data, 
                previous_period_info["start"], 
                previous_period_info["label"]
            ),
            'recent_shifts': df.head(10),
            'total_shifts': len(df)
        }
        
    except Exception as e:
        print(f"Error analyzing timesheet: {e}")
        return {
            'current_period': {
                'week1_hours': 0, 'week2_hours': 0,
                'week1_per_diem': [], 'week2_per_diem': [],
                'week1_site_bonus_days': 0, 'week2_site_bonus_days': 0,
                'period_label': 'Error'
            },
            'previous_period': {
                'week1_hours': 0, 'week2_hours': 0,
                'week1_per_diem': [], 'week2_per_diem': [],
                'week1_site_bonus_days': 0, 'week2_site_bonus_days': 0,
                'period_label': 'Error'
            },
            'recent_shifts': pd.DataFrame(),
            'total_shifts': 0
        }

def calculate_monthly_projections(current_data, base_weekly, site_bonus_day, tax_rate):
    """Calculate realistic monthly projections - FIXED for biweekly"""
    if current_data['hours'] == 0 or current_data['days'] == 0:
        return pd.DataFrame({
            'Scenario': ['No data available'],
            'Projected Monthly Income': [0]
        })
    
    # Calculate averages from current period data
    avg_hours_per_day = current_data['hours'] / current_data['days']
    site_bonus_rate = current_data['site_bonus_days'] / current_data['days']
    
    # Get the most common per diem choice
    if current_data['per_diem_choices']:
        from collections import Counter
        most_common_per_diem = Counter(current_data['per_diem_choices']).most_common(1)[0][0]
    else:
        most_common_per_diem = 'None'
    
    # Monthly scenarios based on days per month
    scenarios = {
        "Light Month (5 days)": 5,
        "Average Month (20 days)": 20, 
        "Heavy Month (28 days)": 28
    }
    
    monthly_projections = {}
    
    for scenario_name, days_per_month in scenarios.items():
        # Calculate totals for the month
        total_hours = avg_hours_per_day * days_per_month
        total_site_bonus_days = int(site_bonus_rate * days_per_month)
        
        # Create per diem list for the month
        per_diem_choices = [most_common_per_diem] * days_per_month
        
        # FIXED: Calculate as biweekly periods per month (30 days / 14 day periods = ~2.14)
        biweekly_periods_in_month = days_per_month / 14
        
        # Use standard monthly calculation (4.33 weeks per month)
        monthly_base = base_weekly * 4  # ~4.33 weeks per month
        
        site_bonus_total = site_bonus_day * total_site_bonus_days
        
        # Overtime calculation for the month (40 * 4.33 = ~173 hours)
        monthly_ot_threshold = 40 * 4
        ot_pay = 0
        if total_hours > monthly_ot_threshold:
            regular_rate = (monthly_base + site_bonus_total) / total_hours
            ot_hours = total_hours - monthly_ot_threshold
            ot_pay = ot_hours * (0.5 * regular_rate)
        
        taxable_gross = monthly_base + site_bonus_total + ot_pay
        per_diem_total = sum(PER_DIEM_RATES.get(choice, 0) for choice in per_diem_choices)
        
        taxes = taxable_gross * (tax_rate / 100)
        monthly_take_home = taxable_gross - taxes + per_diem_total
        
        monthly_projections[scenario_name] = monthly_take_home
    
    return pd.DataFrame(list(monthly_projections.items()), 
                       columns=['Scenario', 'Projected Monthly Income'])

# ---- App State Variables ----
bulk_start_date = date.today()
bulk_end_date = date.today()
bulk_shift_message = ""
selected_day = date.today()
start_time = "08:00"
end_time = "17:00"
per_diem = "None"
site_bonus = False
message = "Ready to enter shift data"
delete_shift_id = ""

PER_DIEM_OPTIONS = ["None", "Breakfast Only", "Breakfast + Lunch", 
                    "Breakfast + Lunch + Dinner", "Lunch + Dinner", "Dinner Only"]

saved_shifts = pd.DataFrame({
    'id': [], 'date': [], 'start_time': [], 'end_time': [], 
    'per_diem': [], 'site_bonus': []
})

# Calculator settings
base_weekly = 700
site_bonus_day = 45
tax_rate = 15

# Auto-calculated results
current_period_summary = ""
previous_period_summary = ""
total_pay_summary = ""
monthly_projections = pd.DataFrame()

# ---- Functions ----
def save_shift(state):
    """Save shift and auto-calculate pay"""
    if save_shift_to_db(state.selected_day, state.start_time.strip(), 
                       state.end_time.strip(), state.per_diem, state.site_bonus):
        
        new_shifts = get_saved_shifts()
        state.saved_shifts = new_shifts
        
        update_pay_calculations(state)
        
        state.message = f"✅ Shift saved and pay updated for {state.selected_day}"
        notify(state, "success", "Shift saved and pay calculated!")
    else:
        state.message = "❌ Failed to save shift"
        notify(state, "error", "Database save failed")

def delete_selected_shift(state):
    """Delete a specific shift by ID"""
    if not state.delete_shift_id.strip():
        state.message = "❌ Please enter a Shift ID to delete"
        notify(state, "warning", "No shift ID provided")
        return
    
    try:
        shift_id = int(state.delete_shift_id.strip())
        if delete_shift_from_db(shift_id):
            new_shifts = get_saved_shifts()
            state.saved_shifts = new_shifts
            update_pay_calculations(state)
            
            state.message = f"✅ Shift ID {shift_id} deleted successfully"
            state.delete_shift_id = ""
            notify(state, "success", f"Shift {shift_id} deleted!")
        else:
            state.message = f"❌ Shift ID {shift_id} not found"
            notify(state, "error", f"Shift {shift_id} not found")
    except ValueError:
        state.message = "❌ Please enter a valid numeric Shift ID"
        notify(state, "error", "Invalid shift ID")

def clear_all_shifts(state):
    """Delete all shifts after confirmation"""
    deleted_count = delete_all_shifts()
    if deleted_count > 0:
        new_shifts = get_saved_shifts()
        state.saved_shifts = new_shifts
        update_pay_calculations(state)
        
        state.message = f"✅ All {deleted_count} shifts deleted"
        notify(state, "success", f"{deleted_count} shifts deleted!")
    else:
        state.message = "❌ No shifts to delete"
        notify(state, "info", "No shifts found")

def update_pay_calculations(state):
    """Update pay calculations based on defined pay periods"""
    print(f"UPDATING CALCULATIONS with Base Weekly: ${state.base_weekly}, Site Bonus: ${state.site_bonus_day}")
    
    data = analyze_timesheet_by_periods()
    
    current = data['current_period']
    previous = data['previous_period']
    
    tax_rate_decimal = state.tax_rate / 100
    
    # Use the corrected weekly calculation method
    current_taxable, current_per_diem_total, current_after = calc_pay_period(
        current['week1_hours'], current['week2_hours'],
        current['week1_per_diem'], current['week2_per_diem'],
        current['week1_site_bonus_days'], current['week2_site_bonus_days'],
        state.base_weekly, state.site_bonus_day, tax_rate_decimal
    )
    
    previous_taxable, previous_per_diem_total, previous_after = calc_pay_period(
        previous['week1_hours'], previous['week2_hours'],
        previous['week1_per_diem'], previous['week2_per_diem'],
        previous['week1_site_bonus_days'], previous['week2_site_bonus_days'],
        state.base_weekly, state.site_bonus_day, tax_rate_decimal
    )
    
    # Build summary strings with weekly breakdown
    state.current_period_summary = f"""**{current['period_label']}:**
- Week 1: {current['week1_hours']:.1f} hrs ({current['week1_site_bonus_days']} bonus days)
- Week 2: {current['week2_hours']:.1f} hrs ({current['week2_site_bonus_days']} bonus days)
- Total Hours: {current['hours']:.1f} | Days Worked: {current['days']}
- Per Diem Total: ${current_per_diem_total:.2f}
- Estimated Take-Home: ${current_after:,.2f}"""
    
    state.previous_period_summary = f"""**{previous['period_label']}:**
- Week 1: {previous['week1_hours']:.1f} hrs ({previous['week1_site_bonus_days']} bonus days)
- Week 2: {previous['week2_hours']:.1f} hrs ({previous['week2_site_bonus_days']} bonus days)
- Total Hours: {previous['hours']:.1f} | Days Worked: {previous['days']}
- Per Diem Total: ${previous_per_diem_total:.2f}
- Estimated Take-Home: ${previous_after:,.2f}"""
    
    state.total_pay_summary = f"""**Summary:**
- Total Shifts Recorded: {data['total_shifts']}
- Last Two Periods Combined: ${current_after + previous_after:,.2f}"""
    
    # Update monthly projections using current period's week 1 data
    current_for_projection = {
        'hours': current['week1_hours'] if current['week1_hours'] > 0 else current['week2_hours'],
        'days': len(current['week1_per_diem']) if current['week1_hours'] > 0 else len(current['week2_per_diem']),
        'site_bonus_days': current['week1_site_bonus_days'] if current['week1_hours'] > 0 else current['week2_site_bonus_days'],
        'per_diem_choices': current['week1_per_diem'] if current['week1_hours'] > 0 else current['week2_per_diem']
    }
    
    state.monthly_projections = calculate_monthly_projections(
        current_for_projection, state.base_weekly, state.site_bonus_day, tax_rate_decimal
    )


def on_init(state):
    """Initialize app and calculate initial pay"""
    print("Initializing app...")
    
    initial_shifts = get_saved_shifts()
    state.saved_shifts = initial_shifts
    state.message = f"Ready - {len(initial_shifts)} shifts loaded"
    
    update_pay_calculations(state)
    
    print("App initialized with biweekly pay period calculations")

# ---- Multi-page UI ----
timesheet_page = """
<|navbar|>

# Timesheet Entry

Enter your shift details. Pay calculated by biweekly periods (Aug 10-23, etc.)

## Add New Shift

Date:
<|{selected_day}|date|>

Start Time:
<|{start_time}|input|>

End Time:  
<|{end_time}|input|>

Per Diem:
<|{per_diem}|selector|lov={PER_DIEM_OPTIONS}|dropdown|>

Site Bonus:
<|{site_bonus}|toggle|>

<|Save Shift|button|on_action=save_shift|>

<|{message}|text|>

## Bulk Entry

Start Date: <|{bulk_start_date}|date|>
End Date: <|{bulk_end_date}|date|>
Start Time: <|{start_time}|input|>
End Time: <|{end_time}|input|>
Per Diem: <|{per_diem}|selector|lov={PER_DIEM_OPTIONS}|dropdown|>
Site Bonus: <|{site_bonus}|toggle|>
<|Bulk Add Shifts|button|on_action=bulk_add_shifts|>
<|{bulk_shift_message}|text|>

---

## Your Shifts

<|{saved_shifts}|table|>

## Delete Shifts

Delete by Shift ID: <|{delete_shift_id}|input|> <|Delete Shift|button|on_action=delete_selected_shift|>

<|Clear All Shifts|button|on_action=clear_all_shifts|>
"""

calculator_page = """
<|navbar|>

# Paycheck Calculator

*Based on biweekly pay periods (14-day cycles starting Aug 10)*

## Settings

Base Weekly Salary: <|{base_weekly}|number|on_change=update_pay_calculations|>

Site Bonus per Day: <|{site_bonus_day}|number|on_change=update_pay_calculations|>

Tax Rate (%): <|{tax_rate}|slider|min=10|max=25|on_change=update_pay_calculations|>

---
## Pay Period Analysis

<|layout|columns=1 1 1|gap=20px|

<|part|class_name=pay-card|
<|{current_period_summary}|text|mode=markdown|>
|>

<|part|class_name=pay-card|
<|{previous_period_summary}|text|mode=markdown|>
|>

<|part|class_name=pay-card|
<|{total_pay_summary}|text|mode=markdown|>
|>

|>

---

## Monthly Income Projections

<|{monthly_projections}|chart|type=bar|x=Scenario|y=Projected Monthly Income|title=Based on Current Work Pattern|>
"""

pages = {
    "Timesheet": timesheet_page,
    "Calculator": calculator_page,
}

# ---- Main execution ----
import os
from taipy.gui import Gui

if __name__ == "__main__":
    print("Starting Biweekly Timesheet Calculator...")
    print("Pay periods: Aug 10-23, Aug 24-Sep 6, etc. (14-day biweekly)")
    
    if not check_database_structure():
        print("Database setup failed!")
        exit(1)
    
    print("Starting GUI...")
    gui = Gui(pages=pages)
    
    # Use Render-provided port or fallback to 5000 locally
    port = int(os.environ.get("PORT", 10000))
    
    gui.run(
        host="0.0.0.0",  # expose externally
        port=port,
        title="Biweekly Timesheet Calculator",
        debug=False,
        on_init=on_init
    )
