import sqlite3
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
DB_FILE = "api_iso_hubs_5yr.db"

def audit_database():
    try:
        conn = sqlite3.connect(DB_FILE)
        
        # SQL Query to get the exact start, end, and row counts for every hub
        query = """
        SELECT 
            iso AS "ISO",
            location AS "Hub / Node",
            MIN(timestamp) AS "First Record",
            MAX(timestamp) AS "Last Record",
            COUNT(*) AS "Total Rows Captured"
        FROM historical_prices
        GROUP BY iso, location
        ORDER BY iso, location;
        """
        
        print(f"\n🔍 Scanning 250MB Database: {DB_FILE}...\n")
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("⚠️ The database exists but contains zero rows of data.")
            return

        # Format the timestamps to be readable
        df['First Record'] = pd.to_datetime(df['First Record']).dt.strftime('%Y-%m-%d %H:%M')
        df['Last Record'] = pd.to_datetime(df['Last Record']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Calculate expected rows for a rough "Completeness" check
        # Assuming 5-minute intervals (288 rows/day) for most, except ERCOT which is 15-min (96 rows/day)
        completeness = []
        for index, row in df.iterrows():
            start = pd.to_datetime(row['First Record'])
            end = pd.to_datetime(row['Last Record'])
            days_diff = (end - start).days
            
            # Rough estimate based on ISO interval schemas
            if row['ISO'] == 'ERCOT':
                expected_rows = max(1, days_diff * 96)
            else:
                expected_rows = max(1, days_diff * 288)
                
            actual_rows = row['Total Rows Captured']
            health_pct = min(100.0, (actual_rows / expected_rows) * 100)
            
            completeness.append(f"{health_pct:.1f}%")
            
        df['Data Health'] = completeness
        
        # Print the clean table to the terminal
        print("✅ AUDIT COMPLETE. HERE IS EXACTLY WHAT YOU HAVE:\n")
        print(df.to_string(index=False))
        print("\n==========================================================================")
        print(f"Total Rows Across All ISOs: {df['Total Rows Captured'].sum():,}")
        print("==========================================================================\n")
        
        conn.close()
        
    except sqlite3.OperationalError:
        print(f"❌ ERROR: Could not find '{DB_FILE}'. Make sure you are in the correct folder.")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    audit_database()
