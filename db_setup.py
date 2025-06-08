import sqlite3

conn = sqlite3.connect('inventory.db')
c = conn.cursor()

# Create drums table
c.execute('''CREATE TABLE IF NOT EXISTS drums (
    DrumID TEXT PRIMARY KEY,
    OrderID TEXT,
    MaterialType TEXT,
    Status TEXT,
    CurrentGrid TEXT,
    LastUpdated DATETIME
)''')

# Create grids table
c.execute('''CREATE TABLE IF NOT EXISTS grids (
    GridID TEXT PRIMARY KEY,
    Status TEXT,
    CurrentDrumID TEXT
)''')



# Create transactions table
c.execute('''CREATE TABLE IF NOT EXISTS transactions (
    TxnID INTEGER PRIMARY KEY AUTOINCREMENT,
    DrumID TEXT,
    GridID TEXT,
    Status TEXT,
    Timestamp DATETIME
)''')
def create_history_table():
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS drum_history (
        HistID INTEGER PRIMARY KEY AUTOINCREMENT,
        DrumID TEXT,
        OrderID TEXT,
        MaterialType TEXT,
        Status TEXT,
        GridID TEXT,
        Timestamp DATETIME
    )''')
    conn.commit()
    conn.close()

create_history_table()


# Pre-populate the grids (A1-C3)
for row in "ABC":
    for col in range(1, 4):
        grid_id = f"{row}{col}"
        c.execute("INSERT OR IGNORE INTO grids (GridID, Status, CurrentDrumID) VALUES (?, 'Available', NULL)", (grid_id,))

conn.commit()
conn.close()
print("Database setup complete! You can now build the Streamlit app.")
