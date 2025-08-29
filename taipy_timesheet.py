# taipy_timesheet_column_fix.py
from taipy.gui import Gui, notify
from datetime import datetime, date
import sqlite3
import pandas as pd

# ---- FIXED Database functions ----
def check_database_structure():
    """Check and fix database structure - ENHANCED VERSION"""
    try:
        conn = sqlite3.connect("timesheet.db")
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shifts'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            # Check current structure
            cursor.execute("PRAGMA table_info(shifts)")
            columns = cursor.fetchall()
            print("Current table structure:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
            
            # Check for required columns
            column_names = [col[1] for col in columns]
            missing_columns = []
            
            if 'date' not in column_names:
                missing_columns.append('date')
            if 'created_at' not in column_names:
                missing_columns.append('created_at')
                
            if missing_columns:
                print(f"Missing columns: {missing_columns}")
                print("Dropping and recreating table...")
                cursor.execute("DROP TABLE shifts")
                conn.commit()
        
        # Create table with correct structure
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
        
        # Verify final structure
        cursor.execute("PRAGMA table_info(shifts)")
        columns = cursor.fetchall()
        print("Final table structure:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Database setup error: {e}")
        return False

def get_saved_shifts():
    """Get saved shifts safely - FIXED VERSION"""
    try:
        conn = sqlite3.connect("timesheet.db")
        
        # First check if created_at column exists
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(shifts)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'created_at' in column_names:
            # Use created_at for ordering if available
            query = """
                SELECT date, start_time, end_time, per_diem, 
                       CASE WHEN site_bonus = 1 THEN 'Yes' ELSE 'No' END as site_bonus
                FROM shifts 
                ORDER BY date DESC, created_at DESC
            """
        else:
            # Fall back to ordering by date and id only
            query = """
                SELECT date, start_time, end_time, per_diem, 
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
            'date': [], 'start_time': [], 'end_time': [], 
            'per_diem': [], 'site_bonus': []
        })

def save_shift_to_db(shift_date, start_time, end_time, per_diem, site_bonus):
    """Save shift with debugging"""
    try:
        print(f"Attempting to save: {shift_date}, {start_time}, {end_time}, {per_diem}, {site_bonus}")
        
        conn = sqlite3.connect("timesheet.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO shifts (date, start_time, end_time, per_diem, site_bonus) 
            VALUES (?, ?, ?, ?, ?)
        """, (str(shift_date), start_time, end_time, per_diem, 1 if site_bonus else 0))
        
        conn.commit()
        conn.close()
        print("Save successful!")
        return True
        
    except Exception as e:
        print(f"Save error: {e}")
        return False

# ---- App state ----
selected_day = date.today()
start_time = "08:00"
end_time = "17:00"
per_diem = "None"
site_bonus = False
message = "Ready to enter shift data"

PER_DIEM_OPTIONS = ["None", "Breakfast Only", "Breakfast + Lunch", 
                    "Breakfast + Lunch + Dinner", "Lunch + Dinner", "Dinner Only"]

saved_shifts = pd.DataFrame({
    'date': [], 'start_time': [], 'end_time': [], 
    'per_diem': [], 'site_bonus': []
})

# ---- Save function ----
def save_shift(state):
    """Save shift with full validation"""
    print(f"Save button clicked. Current values:")
    print(f"  Date: {state.selected_day}")
    print(f"  Start: '{state.start_time}'")
    print(f"  End: '{state.end_time}'")
    print(f"  Per diem: {state.per_diem}")
    print(f"  Site bonus: {state.site_bonus}")
    
    # Save to database
    if save_shift_to_db(state.selected_day, state.start_time.strip(), 
                       state.end_time.strip(), state.per_diem, state.site_bonus):
        
        # Reload shifts
        new_shifts = get_saved_shifts()
        print(f"Reloaded {len(new_shifts)} shifts after save")
        state.saved_shifts = new_shifts
        
        state.message = f"✅ Shift saved for {state.selected_day}"
        notify(state, "success", "Shift saved successfully!")
        
        print("Updated shifts dataframe:")
        print(state.saved_shifts)
        
    else:
        state.message = "❌ Failed to save shift to database"
        notify(state, "error", "Database save failed")

def on_init(state):
    """Initialize the state with data from database"""
    print("Initializing app state...")
    
    initial_shifts = get_saved_shifts()
    state.saved_shifts = initial_shifts
    
    print(f"Initialized with {len(initial_shifts)} existing shifts")
    print("Initial shifts:")
    print(initial_shifts)
    
    state.message = f"Ready - {len(initial_shifts)} existing shifts loaded"

# ---- UI ----
page = """
# 📅 Timesheet Entry App

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

---

## Saved Shifts

<|{saved_shifts}|table|>

"""

# ---- Main execution ----
if __name__ == "__main__":
    print("Starting Taipy Timesheet App...")
    
    print("Checking database structure...")
    if not check_database_structure():
        print("Database setup failed!")
        exit(1)
    
    print("Database ready!")
    
    print("Starting GUI with initialization callback...")
    gui = Gui(page)
    gui.run(title="Timesheet Entry", port=5000, debug=True, on_init=on_init)
