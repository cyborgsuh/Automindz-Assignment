import os

from dotenv import load_dotenv

from pipeline.db.client import get_connection

load_dotenv(".env")
db_url = os.environ.get("SUPABASE_POOLER_URL") or os.environ["SUPABASE_DB_URL"]
with get_connection(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM jobs")
        print("jobs:", cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM companies")
        print("companies:", cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM contacts")
        print("contacts:", cur.fetchone()[0])
