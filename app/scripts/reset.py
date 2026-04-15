import asyncio
import os
import sys

# Ensure we can import from the 'app' directory if run from 'app'
sys.path.append(os.getcwd())

from core.database import engine, Base
from models import *  # This registers all models with Base.metadata
from sqlalchemy import text

async def reset_database():
    """
    Drops all existing tables and recreates them based on the current models.
    Run this from the 'app' directory: python scripts/reset.py
    """
    print("Connecting to the database...")
    async with engine.begin() as conn:
        if engine.dialect.name == "mysql":
            print("Disabling foreign key checks (MySQL)...")
            await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        elif engine.dialect.name == "sqlite":
            print("Disabling foreign key checks (SQLite)...")
            await conn.execute(text("PRAGMA foreign_keys = OFF;"))
        
        # We need to get the table names from the metadata
        # sorted_tables gives them in dependency order
        for table in reversed(Base.metadata.sorted_tables):
            print(f"Dropping table {table.name}...")
            await conn.execute(text(f"DROP TABLE IF EXISTS {table.name};"))
            
        if engine.dialect.name == "mysql":
            print("Re-enabling foreign key checks (MySQL)...")
            await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        elif engine.dialect.name == "sqlite":
            print("Re-enabling foreign key checks (SQLite)...")
            await conn.execute(text("PRAGMA foreign_keys = ON;"))
        
        print("Creating all tables based on models...")
        await conn.run_sync(Base.metadata.create_all)
    
    print("Database reset complete.")
    await engine.dispose()

if __name__ == "__main__":
    confirm = input("Are you sure you want to reset the database? This will DELETE all data! (y/n): ")
    if confirm.lower() == 'y':
        asyncio.run(reset_database())
    else:
        print("Reset cancelled.")
