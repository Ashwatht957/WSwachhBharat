# create_tables.py

from app import db

# Create tables in default 'location' database
db.create_all()

# Create tables in 'staff' bound database
db.create_all(bind='staff')

print("✅ Tables created successfully.")
