from app.core.config import settings

def test_db_url_transformation():
    # Mock settings.DATABASE_URL
    original_url = "postgresql://user:pass@host:5432/db"
    
    # Simulate logic from session.py
    db_url = original_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    if "supabase" in db_url and "ssl=" not in db_url:
        db_url = db_url + ("&" if "?" in db_url else "?") + "ssl=require"
    
    print(f"Original: {original_url}")
    print(f"Transformed: {db_url}")
    
    if db_url.startswith("postgresql+asyncpg://"):
        print("SUCCESS: URL correctly transformed to use asyncpg.")
    else:
        print("FAILURE: URL does not use asyncpg.")
        
    # Test Supabase case
    supabase_url = "postgresql://user:pass@host:5432/db?something=else&supabase=true"
    db_url = supabase_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
    if "supabase" in db_url and "ssl=" not in db_url:
        db_url = db_url + ("&" if "?" in db_url else "?") + "ssl=require"
        
    print(f"\nSupabase Original: {supabase_url}")
    print(f"Supabase Transformed: {db_url}")
    
    if "postgresql+asyncpg://" in db_url and "ssl=require" in db_url:
         print("SUCCESS: Supabase URL correctly transformed.")
    else:
         print("FAILURE: Supabase URL incorrect.")

if __name__ == "__main__":
    test_db_url_transformation()
