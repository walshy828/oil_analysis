from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Company
from app.config import settings

engine = create_engine(settings.database_url)
Session = sessionmaker(bind=engine)
db = Session()

companies = db.query(Company).all()
print("All companies in DB:")
for c in companies:
    print(f"ID: {c.id}, Name: '{c.name}', Market: {c.is_market_index}")

db.close()
