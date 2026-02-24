import pandas as pd
import sqlite3
import requests
from datetime import datetime
import time

# --- CONFIGURATION ---
API_KEY = "17fd6eb144fe46afa0c0894453ba867d"
DB_NAME = "api_iso_hubs_1yr.db"
YEARS_BACK = 1

# Trimmed to the "Core 8"
ISO_API_MAPPINGS = {
    "ERCOT": {
        "dataset": "ercot_spp_real_time_15_min",
        "node_col": "location", # Universal backend standard
        "price_col": "spp",     
        "locations": ["HB_WEST", "HB_NORTH"]
    },
    "SPP": {
        "dataset": "spp_lmp_real_time_5_min", 
        "node_col": "location",
        "price_col": "lmp",
        "locations": ["SPP_NORTH_HUB", "SPP_SOUTH_HUB"] 
    },
    "CAISO": {
        "dataset": "caiso_lmp_real_time_5_min",
        "node_col": "location",
        "price_col": "lmp",
        "locations": ["TH_NP15_GEN-APND", "TH_SP15_GEN-APND"]
    },
    "PJM": {
        "dataset": "pjm_lmp_real_time_5_min",
        "node_col": "location",
        "price_col": "lmp",
        "locations": ["WESTERN HUB"]
    },
    "NYISO": {
        "dataset": "nyiso_lmp_real_time_5_min",
        "node_col": "location",
        "price_col": "lmp",
        "locations": ["HUD VL"]
    },
    "MISO": {
        "dataset": "miso_lmp_real_time_5_min",
        "node_col": "location",
        "price_col": "lmp",
        "locations": ["INDIANA.HUB"]
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

def get_smart_resume_date(conn, iso, loc, default_start):
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(timestamp) FROM historical_prices WHERE iso=? AND location=?", (iso, loc))
    result = cursor.fetchone()[0]
    
    if result:
        latest_db_time = pd.to_datetime(result, utc=True)
        return latest_db_time + pd.Timedelta(minutes=1)
    
    return default_start

def fetch_direct_api_data(dataset, start_date, end_date, filter_col, filter_val):
    """Bypasses the gridstatusio package entirely for direct REST API communication"""
    url = f"https://api.gridstatus.io/v1/datasets/{dataset}/query"
    headers = {"Authorization": f"Basic {API_KEY}"}
    
    params = {
        "start_time": start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "end_time": end_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "limit": 100000,
        filter_col: filter_val
    }

    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            return pd.DataFrame(data["data"])
    elif response.status_code in [401, 403]:
        raise Exception(f"API Quota Limit or Invalid Key: {response.text}")
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text}")
         
    return pd.DataFrame()

def fetch_and_store_data(conn):
    end_date = pd.Timestamp.now(tz="US/Central").floor('D')
    global_start_date = end_date - pd.Timedelta(days=365 * YEARS_BACK)
    
    print(f"=====================================================")
    print(f" INITIATING 1-YEAR CORE 8 DATA PULL (REST API BYPASS)")
    print(f" Target Lookback: {YEARS_BACK} Year")
    print(f"=====================================================\n")

    for iso_name, metadata in ISO_API_MAPPINGS.items():
        dataset_id = metadata["dataset"]
        node_col = metadata["node_col"]
        price_col = metadata["price_col"]
        
        for loc in metadata["locations"]:
            print(f"\n   📍 Target Hub: {loc} ({iso_name})")
            current_date = get_smart_resume_date(conn, iso_name, loc, global_start_date)
            
            if current_date >= end_date:
                print(f"      ✓ Data fully up-to-date locally. Skipping API call.")
                continue
                
            print(f"      🔄 Fetching API data from: {current_date.strftime('%Y-%m-%d %H:%M')}")
            
            while current_date < end_date:
                chunk_end = min(current_date + pd.Timedelta(days=30), end_date)
                
                try:
                    df = fetch_direct_api_data(dataset_id, current_date, chunk_end, node_col, loc)
                    
                    if not df.empty:
                        # Ensure columns are lowercase for safe matching
                        df.columns = [c.lower() for c in df.columns]
                        
                        time_col = "interval_start_utc" if "interval_start_utc" in df.columns else df.columns[0]
                        actual_price_col = price_col.lower()
                        
                        if actual_price_col not in df.columns:
                            for col in df.columns:
                                if "price" in col or "lmp" in col or "spp" in col:
                                    actual_price_col = col
                                    break

                        db_df = pd.DataFrame({
                            'timestamp': pd.to_datetime(df[time_col], utc=True),
                            'iso': iso_name,
                            'location': loc,
                            'price': pd.to_numeric(df[actual_price_col], errors='coerce')
                        })
                        
                        # Drop intervals with NaN price values
                        db_df = db_df.dropna(subset=['price'])
                        
                        db_df.to_sql('historical_prices_temp', conn, if_exists='replace', index=False)
                        conn.execute('''
                            INSERT OR IGNORE INTO historical_prices (timestamp, iso, location, price)
                            SELECT timestamp, iso, location, price FROM historical_prices_temp
                        ''')
                        conn.commit()
                        print(f"      ✓ Downloaded & Saved: {current_date.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}")
                    else:
                        print(f"      ⚠️ No data returned for {current_date.strftime('%Y-%m-%d')} - {chunk_end.strftime('%Y-%m-%d')}")
                        
                except Exception as e:
                    print(f"      ⚠️ API Error ({current_date.strftime('%Y-%m-%d')}): {e}")
                    if "Quota" in str(e) or "Key" in str(e):
                        print("\n⛔ CRITICAL: API Quota Limit Reached or Key Blocked. Terminating script.")
                        return
                
                current_date = chunk_end
                time.sleep(1.0) 

    print("\n✅ API Database Core 8 build complete!")

if __name__ == "__main__":
    db_conn = setup_database()
    fetch_and_store_data(db_conn)
    db_conn.close()
