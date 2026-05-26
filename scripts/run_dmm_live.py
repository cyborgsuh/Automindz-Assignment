import os

from dotenv import load_dotenv

from pipeline.clients.ai_ark_client import AIArkClient
from pipeline.config import Settings
from pipeline.db.client import get_connection, migrate
from pipeline.db.repos import CompanyRepository, DMMCacheRepository, JobRepository
from pipeline.stages.dmm_search import run_dmm_search

load_dotenv(".env")
settings = Settings.from_env()
db_url = os.environ.get("SUPABASE_POOLER_URL") or os.environ["SUPABASE_DB_URL"]
with get_connection(db_url) as conn:
    migrate(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE companies
            SET dmm_status = 'pending', dmm_drop_reason = NULL
            WHERE icp_decision = 'fit'
            """
        )
    conn.commit()
    ai_ark = AIArkClient(settings.ai_ark_token, settings.ai_ark_base_url)
    try:
        credits, findings = run_dmm_search(
            settings,
            CompanyRepository(conn),
            JobRepository(conn),
            DMMCacheRepository(conn),
            ai_ark,
            max_companies=1,
            stop_after_first_api_call=False,
        )
        print("credits", credits, "findings", len(findings))
        for _company, person, _job_ids in findings:
            print("HIT:", person.full_name, "|", person.title, "|", person.linkedin_url)
    finally:
        ai_ark.close()
