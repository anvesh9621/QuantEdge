#!/bin/bash

# QuantEdge Railway Startup Script
# Seeds the database on first deploy, then starts the FastAPI server.

echo "=== QuantEdge Backend Starting ==="

# Step 1: Ensure database tables exist and seed if empty
echo "Checking if database needs seeding..."
python -c "
from app.database.db import engine, Base
import app.database.models  # Import models so Base knows about them
from sqlalchemy import text

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM stock_data')).fetchone()
    count = result[0]
    print(f'Existing rows in stock_data: {count}')
    if count == 0:
        print('Database is empty — running initial data import...')
        import subprocess
        subprocess.run(['python', 'import_data.py'], check=True)
        print('Database seeding complete!')
    else:
        print('Database already seeded. Skipping import.')
"

if [ $? -ne 0 ]; then
    echo "Initial DB check failed. Attempting full seed..."
    python import_data.py
fi

# Step 2: Recompile protobuf schema so gencode matches the installed runtime
echo "Compiling protobuf schema..."
python -m grpc_tools.protoc -I. --python_out=. app/schemas/pricing.proto

# Step 3: Start the FastAPI server
echo "Starting uvicorn on port ${PORT:-8000}..."
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
