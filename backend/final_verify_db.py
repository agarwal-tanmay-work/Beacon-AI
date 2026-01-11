
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.beacon import Beacon
from sqlalchemy import select
import json

async def check():
    async with AsyncSessionLocal() as session:
        stmt = select(Beacon).order_by(Beacon.created_at.desc()).limit(2)
        res = await session.execute(stmt)
        rows = res.scalars().all()
        print(f'\n--- DATABASE VERIFICATION (RECENT 2 REPORTS) ---')
        for i, row in enumerate(rows):
            print(f'REPORT #{i+1}:')
            print(f'  Case ID: {row.case_id}')
            print(f'  Secret Key: {row.secret_key}')
            print(f'  Status: {row.status}')
            print(f'  Evidence: {json.dumps(row.evidence_files, indent=2)}')
            print('  ' + '-'*20)
        
        if len(rows) >= 2:
            if rows[0].case_id != rows[1].case_id and rows[0].secret_key != rows[1].secret_key:
                print('\n✅ UNIQUENESS VERIFIED: Case IDs and Secret Keys are unique for different sessions.')
            else:
                print('\n❌ UNIQUENESS FAILED: Duplicate IDs or Keys detected.')
        else:
            print('\n(Only one report found in this check)')

if __name__ == "__main__":
    asyncio.run(check())
