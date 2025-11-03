"""
Script pour vérifier le schéma de la base TimescaleDB
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

print("=" * 60)
print("🔍 CHECKING TIMESCALEDB SCHEMA")
print("=" * 60)

try:
    from loaders.timescale_loader import TimescaleLoader
    
    ts_loader = TimescaleLoader()
    
    with ts_loader.get_connection() as conn:
        cursor = conn.cursor()
        
        # Vérifier la structure de la table 'tickers'
        print("\n📊 TABLE: tickers")
        print("-" * 60)
        
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'tickers'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        
        print(f"{'Column Name':<30} {'Data Type':<20}")
        print("-" * 60)
        
        for col_name, data_type in columns:
            print(f"{col_name:<30} {data_type:<20}")
        
        # Tester une requête
        print("\n" + "=" * 60)
        print("🧪 TESTING QUERY")
        print("-" * 60)
        
        cursor.execute("SELECT * FROM tickers LIMIT 1;")
        sample = cursor.fetchone()
        
        if sample:
            print("✅ Sample row retrieved:")
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'tickers' ORDER BY ordinal_position;")
            col_names = [row[0] for row in cursor.fetchall()]
            
            for col, val in zip(col_names, sample):
                print(f"  {col}: {val}")
        else:
            print("⚠️ No data in tickers table")
        
        # Vérifier quelle colonne contient le volume
        print("\n" + "=" * 60)
        print("🔍 CHECKING VOLUME COLUMN")
        print("-" * 60)
        
        volume_columns = [col for col in col_names if 'volume' in col.lower()]
        
        if volume_columns:
            print(f"✅ Found volume columns: {', '.join(volume_columns)}")
            print("\n💡 RECOMMENDED QUERY:")
            print(f"""
SELECT time, last as price, {volume_columns[0]} as volume_24h
FROM tickers
WHERE symbol = 'BTC/USDT'
ORDER BY time DESC
LIMIT 5;
            """)
        else:
            print("❌ No volume column found!")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ SCHEMA CHECK COMPLETE")
print("=" * 60)