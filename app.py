import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ---- Database Setup (Create tables if not exist) ----

def create_tables():
    conn = sqlite3.connect('inventory.db', check_same_thread=False)
    c = conn.cursor()
    # Main tables
    c.execute('''CREATE TABLE IF NOT EXISTS drums (
        DrumID TEXT PRIMARY KEY,
        OrderID TEXT,
        MaterialType TEXT,
        Status TEXT,
        CurrentGrid TEXT,
        LastUpdated DATETIME
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS grids (
        GridID TEXT PRIMARY KEY,
        Status TEXT,
        CurrentDrumID TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        TxnID INTEGER PRIMARY KEY AUTOINCREMENT,
        DrumID TEXT,
        GridID TEXT,
        Status TEXT,
        Timestamp DATETIME
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS drum_history (
        HistID INTEGER PRIMARY KEY AUTOINCREMENT,
        DrumID TEXT,
        OrderID TEXT,
        MaterialType TEXT,
        Status TEXT,
        GridID TEXT,
        Timestamp DATETIME
    )''')
    # Pre-populate grid (3x3) if empty
    for row in "ABC":
        for col in range(1, 4):
            grid_id = f"{row}{col}"
            c.execute("INSERT OR IGNORE INTO grids (GridID, Status, CurrentDrumID) VALUES (?, 'Available', NULL)", (grid_id,))
    conn.commit()
    conn.close()

create_tables()

# ---- Helper Functions ----

def get_db_connection():
    conn = sqlite3.connect('inventory.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_available_grids(conn):
    return pd.read_sql_query("SELECT * FROM grids WHERE Status='Available'", conn)

def get_all_grids(conn):
    return pd.read_sql_query("SELECT * FROM grids", conn)

def get_all_drums(conn):
    return pd.read_sql_query("SELECT * FROM drums", conn)

def get_drum(conn, drum_id):
    return pd.read_sql_query("SELECT * FROM drums WHERE DrumID = ?", conn, params=(drum_id,))

def insert_drum(conn, drum_id, order_id, material_type):
    now = datetime.now()
    conn.execute("INSERT OR REPLACE INTO drums (DrumID, OrderID, MaterialType, Status, CurrentGrid, LastUpdated) VALUES (?, ?, ?, ?, ?, ?)",
                 (drum_id, order_id, material_type, 'OUT', None, now))
    conn.commit()

def update_drum_info(conn, drum_id, order_id, material_type):
    now = datetime.now()
    conn.execute("UPDATE drums SET OrderID=?, MaterialType=?, Status='OUT', CurrentGrid=NULL, LastUpdated=? WHERE DrumID=?",
                 (order_id, material_type, now, drum_id))
    conn.commit()

def update_drum_in(conn, drum_id, grid_id):
    now = datetime.now()
    conn.execute("UPDATE drums SET Status = 'IN', CurrentGrid = ?, LastUpdated = ? WHERE DrumID = ?", (grid_id, now, drum_id))
    conn.execute("UPDATE grids SET Status = 'Occupied', CurrentDrumID = ? WHERE GridID = ?", (drum_id, grid_id))
    conn.execute("INSERT INTO transactions (DrumID, GridID, Status, Timestamp) VALUES (?, ?, 'IN', ?)", (drum_id, grid_id, now))
    conn.commit()

def update_drum_out(conn, drum_id):
    now = datetime.now()
    drum = get_drum(conn, drum_id)
    if drum.empty or drum.iloc[0]['CurrentGrid'] is None:
        return False
    grid_id = drum.iloc[0]['CurrentGrid']
    # Log to history BEFORE clearing
    conn.execute("""
        INSERT INTO drum_history (DrumID, OrderID, MaterialType, Status, GridID, Timestamp)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (drum_id, drum.iloc[0]['OrderID'], drum.iloc[0]['MaterialType'], 'OUT', grid_id, now))
    # Mark OUT and clear order/material info
    conn.execute("UPDATE drums SET Status = 'OUT', OrderID = NULL, MaterialType = NULL, CurrentGrid = NULL, LastUpdated = ? WHERE DrumID = ?", (now, drum_id))
    conn.execute("UPDATE grids SET Status = 'Available', CurrentDrumID = NULL WHERE GridID = ?", (grid_id,))
    conn.execute("INSERT INTO transactions (DrumID, GridID, Status, Timestamp) VALUES (?, ?, 'OUT', ?)", (drum_id, grid_id, now))
    conn.commit()
    return True

def get_drum_history(conn):
    return pd.read_sql_query("SELECT * FROM drum_history", conn)

#pages (operator 1 and operator 2 and main server database)

def dashboard(conn):
    st.title("📦 Warehouse Grid Dashboard")
    st.subheader("Grid Status (Auto-refreshes every 10 seconds)")
    grids = get_all_grids(conn)
    st.dataframe(grids)
    st.subheader("All Drums (Current Status)")
    drums = get_all_drums(conn)
    st.dataframe(drums)
    st.subheader("Drum OUT History Log")
    drum_hist = get_drum_history(conn)
    st.dataframe(drum_hist)
    st.caption("Reloads automatically in 10 seconds.")
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=10*1000, key="refresh_dashboard")  # 10s

def drum_in(conn):
    st.header("🔄 Drum Placement (IN)")
    drum_id = st.text_input("Enter Drum ID (e.g., D001)").strip().upper()
    if drum_id:
        drum = get_drum(conn, drum_id)
        needs_new_info = False
        if drum.empty or drum.iloc[0]['Status'] == 'OUT':
            needs_new_info = True
        if needs_new_info:
            st.success(f"New or OUT drum: {drum_id}")
            order_id = st.text_input("Enter Order ID")
            material_type = st.text_input("Enter Material Type")
            if order_id and material_type:
                if st.button("Add/Update Drum Info"):
                    if drum.empty:
                        insert_drum(conn, drum_id, order_id, material_type)
                    else:
                        update_drum_info(conn, drum_id, order_id, material_type)
                    st.success("Drum info saved! Continue with placement.")
        else:
            st.info(f"Drum found: {drum_id} (already IN)")
            st.json(dict(drum.iloc[0]))
        available_grids = get_available_grids(conn)
        st.write("Available Grids:")
        st.dataframe(available_grids)
        grid_id = st.text_input("Enter Grid ID to place drum (e.g., A1)").strip().upper()
        if grid_id and st.button("Place Drum in Grid"):
            # Check if grid is available
            if not available_grids[available_grids["GridID"] == grid_id].empty:
                update_drum_in(conn, drum_id, grid_id)
                st.success(f"Drum {drum_id} placed in grid {grid_id}.")
            else:
                st.error("Selected grid is not available or doesn't exist.")

def drum_out(conn):
    st.header("📤 Drum Retrieval (OUT)")
    drum_id = st.text_input("Enter Drum ID to retrieve (e.g., D001)").strip().upper()
    if drum_id:
        drum = get_drum(conn, drum_id)
        if drum.empty:
            st.warning("Drum not found. Check ID and try again.")
            return
        st.json(dict(drum.iloc[0]))
        if drum.iloc[0]['Status'] == "IN":
            if st.button("Mark as OUT / Retrieve Drum"):
                if update_drum_out(conn, drum_id):
                    st.success(f"Drum {drum_id} marked as OUT, grid is now available, and drum history logged.")
                else:
                    st.error("Could not update drum status. Drum might already be OUT or not placed.")
        else:
            st.info("This drum is already marked as OUT.")

##Streamlit
st.set_page_config(page_title="Drum Inventory", layout="wide")
conn = get_db_connection()

page = st.sidebar.radio("Select Operation", [
    "Dashboard (Live)", 
    "Drum IN (Placement)", 
    "Drum OUT (Retrieval)"
])


##Temp condition (Proto)
if st.button("⚠️ Reset All Data (Clear All Logs & Tables)"):
    conn.execute("DELETE FROM drums")
    conn.execute("DELETE FROM grids")
    conn.execute("DELETE FROM transactions")
    conn.execute("DELETE FROM drum_history")
    for row in "ABC":
        for col in range(1, 4):
            grid_id = f"{row}{col}"
            conn.execute("INSERT OR IGNORE INTO grids (GridID, Status, CurrentDrumID) VALUES (?, 'Available', NULL)", (grid_id,))
    conn.commit()
    st.success("All data cleared! Grids reset.")
    st.rerun()

if page == "Dashboard (Live)":
    dashboard(conn)
elif page == "Drum IN (Placement)":
    drum_in(conn)
elif page == "Drum OUT (Retrieval)":
    drum_out(conn)

conn.close()
