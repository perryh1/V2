import pandas as pd
import sqlite3
import gridstatusio
from datetime import datetime
import time

# --- CONFIGURATION ---
API_KEY = "ca4d17f58f114c8aa7f60b2f33e2a581"
DB_NAME = "api_iso_hubs_5yr.db"
YEARS_BACK = 5

ISO_API_MAPPINGS = {
    "ERCOT": {
        "dataset": "ercot_spp_real_time_15_min",
        "node_col": "Location", # Default standard, auto-resolves if different
        "price_col": "LMP",
        "locations": ["HB_WEST", "HB_NORTH", "HB_SOUTH", "HB_HOUSTON", "LZ_WEST", "LZ_SOUTH"]
    },
    "SPP": {
        "dataset": "spp_rtm_lmp",
        "node_col": "Location",
        "price_col": "LMP",
        "locations": ["SPP_NORTH_HUB", "SPP_SOUTH_HUB"] 
    },
    "CAISO": {
        "dataset": "caiso_lmp_real_time_5_min",
        "node_col": "Location",
        "price_col": "LMP",
        "locations": ["TH_NP15_GEN-APND", "TH_SP15_GEN-APND", "TH_ZP26_GEN-APND"]
    },
    "PJM": {
        "dataset": "pjm_lmp_real_time_5_min",
        "node_col": "Location",
        "price_col": "LMP",
        "locations": ["WESTERN HUB", "N ILLINOIS HUB", "AEP GEN HUB"]
    },
    "NYISO": {
        "dataset": "nyiso_lmp_real_time_5_min",
        "node_col": "Location",
        "price_col": "LMP",
        "locations": ["CAPITL", "HUD VL", "N.Y.C.", "WEST"]
    },
    "MISO": {
        "dataset": "miso_lmp_real_time_5_min",
        "node_col": "Location",
        "price_col": "LMP",
        "locations": ["ILLINOIS.HUB", "INDIANA.HUB", "MINN.HUB", "TEXAS.HUB"]
    }
}

def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historical_prices (
            timestamp DATETIME,
            iso TEXT,
            location TEXT,
            price REAL,
            UNIQUE(timestamp, iso, location)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_query ON historical_prices(iso, location, timestamp)')
    conn.commit()
    return conn

def resolve_schema(client, dataset_id, start_date, default_node, default_price):
    """Auto-Discovery: Pulls 1 hour of unfiltered data to map exact server columns."""
    try:
        # Pulling just 1 hour is tiny and fast, ensuring we see the real column names
        df = client.get_dataset(dataset=dataset_id, start=start_date, end=start_date + pd.Timedelta(hours=1), verbose=False)
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            
            # Dynamically lock the Node Column
            if "Location" in cols: final_node = "Location"
            elif "Settlement Point Name" in cols: final_node = "Settlement Point Name"
            elif "Settlement Point" in cols: final_node = "Settlement Point"
            else: final_node = default_node
            
            # Dynamically lock the Price Column
            if "LMP" in cols: final_price = "LMP"
            elif "Settlement Point Price" in cols: final_price = "Settlement Point Price"
            else: final_price = default_price
            
            return final_node, final_price
    except Exception as e:
        pass
    return default_node, default_price

def fetch_and_store_data(conn):
    client = gridstatusio.GridStatusClient(api_key=API_KEY)
    end_date = pd.Timestamp.now(tz="US/Central").floor('D')
    start_date = end_date - pd.Timedelta(days=365 * YEARS_BACK)
    
    print(f"=====================================================")
    print(f" INITIATING 5-YEAR INSTITUTIONAL DATA PULL")
    print(f" Timeframe: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"=====================================================\n")

    for iso_name, metadata in ISO_API_MAPPINGS.items():
        dataset_id = metadata["dataset"]
        
        print(f"🔍 Auto-discovering schema for {iso_name}...")
        node_col, price_col = resolve_schema(client, dataset_id, start_date, metadata["node_col"], metadata["price_col"])
        print(f"   ✓ Locked schema: Node='{node_col}', Price='{price_col}'")
        
        for loc in metadata["locations"]:
            print(f"\n   📍 Fetching Hub: {loc} ({iso_name})")
            
            current_date = start_date
            while current_date < end_date:
                chunk_end = min(current_date + pd.Timedelta(days=30), end_date)
                
                try:
                    df = client.get_dataset(
                        dataset=dataset_id,
                        start=current_date,
                        end=chunk_end,
                        filter_column=node_col,
                        filter_value=loc,
                        verbose=False
                    )
                    
                    if df is not None and not df.empty:
                        # Sometimes Gridstatus returns the time column as "Time", sometimes "Interval Start"
                        time_col = "Interval Start" if "Interval Start" in df.columns else "Time"
                        
                        db_df = pd.DataFrame({
                            'timestamp': pd.to_datetime(df[time_col], utc=True),
                            'iso': iso_name,
                            'location': loc,
                            'price': df[price_col]
                        })
                        
                        db_df.to_sql('historical_prices_temp', conn, if_exists='replace', index=False)
                        conn.execute('''
                            INSERT OR IGNORE INTO historical_prices (timestamp, iso, location, price)
                            SELECT timestamp, iso, location, price FROM historical_prices_temp
                        ''')
                        conn.commit()
                        print(f"      ✓ Saved: {current_date.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
                        
                except Exception as e:
                    print(f"      ⚠️ API Error ({current_date.strftime('%Y-%m-%d')}): {e}")
                
                current_date = chunk_end
                time.sleep(1.0) 

    print("\n✅ 5-Year API Database build complete!")

if __name__ == "__main__":
    db_conn = setup_database()
    fetch_and_store_data(db_conn)
    db_conn.close()
