import os

from dotenv import load_dotenv

from pipeline.db.client import get_connection

load_dotenv(".env")
db_url = os.environ.get("SUPABASE_POOLER_URL") or os.environ["SUPABASE_DB_URL"]
with get_connection(db_url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE companies
            SET dmm_status = 'pending', dmm_drop_reason = NULL
            WHERE icp_decision = 'fit'
            """
        )
        cur.execute("UPDATE companies SET domain = NULL WHERE domain = 'linkedin.com'")
        cur.execute("DELETE FROM dmm_search_log")
    conn.commit()
print("Reset fit companies to pending and cleared DMM cache")
