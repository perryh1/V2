import pandas as pd
import sqlite3
import gridstatusio
from datetime import datetime
import time

# --- CONFIGURATION ---
API_KEY = "ca4d17f58f114c8aa7f60b2f33e2a581"
DB_NAME = "api_iso_hubs_5yr.db"
YEARS_BACK = 5  # UPDATED: Full 5-Year Institutional Lookback

# Map the exact Gridstatus.io datasets and columns for Server-Side Filtering
ISO_API_MAPPINGS = {
    "ERCOT": {
        "dataset": "ercot_spp_real_time_15_min",
        "node_col": "Settlement Point",
        "price_col": "Settlement Point Price",
        "locations": ["HB_WEST", "HB_NORTH", "HB_SOUTH", "HB_HOUSTON", "LZ_WEST", "LZ_SOUTH"]
    },
    "SPP": {
        "dataset": "spp_rtm_lmp",
        "node_col": "Location",
        "price_col": "LMP",
        "locations": ["SPP_NORTH_HUB", "SPP_SOUTH_HUB"] # Add Hardin Node here later
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
    """Creates the SQLite database with optimized indexing for 11M+ rows."""
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
        node_col = metadata["node_col"]
        price_col = metadata["price_col"]
        
        print(f"🚀 Starting Enterprise API pull for {iso_name} ({dataset_id})")
        
        # We loop through locations FIRST, so we can use server-side filtering
        for loc in metadata["locations"]:
            print(f"   📍 Fetching Hub: {loc}")
            
            current_date = start_date
            while current_date < end_date:
                # With server-side filtering, we can safely pull 30 days at once
                chunk_end = min(current_date + pd.Timedelta(days=30), end_date)
                
                try:
                    # EXACT TARGETING: Only requests rows where the node matches 'loc'
                    df = client.get_dataset(
                        dataset=dataset_id,
                        start=current_date,
                        end=chunk_end,
                        filter_column=node_col,
                        filter_value=loc,
                        verbose=False
                    )
                    
                    if df is not None and not df.empty:
                        # Standardize columns for our database schema
                        db_df = pd.DataFrame({
                            'timestamp': pd.to_datetime(df['Interval Start'], utc=True),
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
                        
                except Exception as e:
                    print(f"      ⚠️ API Error for {loc} ({current_date.strftime('%Y-%m-%d')}): {e}")
                
                current_date = chunk_end
                # Gentle 1-second pause for API rate limits over a 5-year continuous pull
                time.sleep(1.0) 

    print("\n✅ 5-Year API Database build complete!")

if __name__ == "__main__":
    db_conn = setup_database()
    fetch_and_store_data(db_conn)
    db_conn.close()
