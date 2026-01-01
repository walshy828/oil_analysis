from sqlalchemy import create_engine, text
import os

database_url = "postgresql://oil_prices:oil_prices_dev@localhost:5432/oil_prices"
engine = create_engine(database_url)

with engine.connect() as conn:
    print("Market Index Companies:")
    result = conn.execute(text("SELECT name FROM companies WHERE is_market_index = true"))
    for row in result:
        print(f" - {row[0]}")
    
    print("\nRecent Market Prices Sample:")
    result = conn.execute(text("""
        SELECT c.name, p.date_reported, p.price_per_gallon 
        FROM oil_prices p 
        JOIN companies c ON p.company_id = c.id 
        WHERE c.is_market_index = true 
        ORDER BY p.date_reported DESC 
        LIMIT 10
    """))
    for row in result:
        print(f" - {row[0]}: {row[1]} = {row[2]}")
