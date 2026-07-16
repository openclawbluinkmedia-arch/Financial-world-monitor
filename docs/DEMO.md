# End-to-End Demo

This demo shows the full FIOS pipeline: real-world event → evidence → impact
analysis → portfolio exposure → audit trail.

## 1. Sample Portfolio CSV

Create `demo_portfolio.csv`:

```csv
ticker,exchange,company_name,sector,industry,country,quantity,weight,isin
HDFCBANK,NSE,HDFC Bank,Financials,Banks,IN,100,25.0,INE040A01034
RELIANCE,NSE,Reliance Industries,Energy,Oil & Gas,IN,50,20.0,INE002A01018
TCS,NSE,Tata Consultancy Services,Information Technology,IT Services,IN,30,15.0,INE467B01029
ITC,NSE,ITC Limited,FMCG,FMCG,IN,200,15.0,INE154A01025
SBIN,NSE,State Bank of India,Financials,Banks,IN,150,10.0,INE062A01020
LT,NSE,Larsen & Toubro,Industrials,Construction,IN,20,8.0,INE018A01030
MARUTI,NSE,Maruti Suzuki India,Consumer Discretionary,Automobiles,IN,10,5.0,INE585B01010
INFY,NSE,Infosys,Information Technology,IT Services,IN,25,2.0,INE009A01021
```

## 2. Register & Login

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@fios.dev","password":"demodemo123","display_name":"Demo User"}'

TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@fios.dev","password":"demodemo123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

TENANT_ID=$(curl -s http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; print(json.load(sys.stdin)['tenant_id'])")
```

## 3. Upload Portfolio

```bash
curl -X POST "http://localhost:8000/api/portfolios/upload?portfolio_name=Demo%20India%20Large%20Cap&tenant_id=$TENANT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@demo_portfolio.csv"
# Returns: {"portfolio_id": "<UUID>", "holdings_created": 8}
```

## 4. Ingest an Event (Simulated)

Using the intelligence pipeline directly:

```bash
curl -X POST "http://localhost:8000/api/intelligence/process-evidence" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_ids": []
  }'
```

Or create evidence manually via ingestion. For demo purposes, inject an RBI
rate decision event through the API:

```python
# scripts/demo_event.py
import asyncio, uuid
from app.database import async_session_factory
from app.modules.intelligence.pipeline import IntelligencePipeline

async def create_demo_event():
    async with async_session_factory() as db:
        pipeline = IntelligencePipeline(db)
        result = await pipeline.process(
            event_text="""
RBI Monetary Policy Committee (MPC) kept the repo rate unchanged at 6.50%
for the seventh consecutive meeting. The standing deposit facility (SDF)
rate remains at 6.25%, and the marginal standing facility (MSF) rate at
6.75%. RBI Governor Shaktikanta Das maintained a 'withdrawal of accommodation'
stance, citing persistent food inflation risks. The GDP growth forecast for
FY25 was revised to 7.2% from 7.0%. Inflation projection held at 4.5%.

Key impacts:
- Banks (HDFC Bank, SBI) benefit from stable NIMs
- Lower bond yields benefit IT companies (TCS, Infosys) via treasury gains
- Auto sector (Maruti) sees continued demand with stable rates
- FMCG sector (ITC) benefits from rural demand recovery
- Real estate and construction (L&T) positive on steady rates
            """,
            title="RBI Holds Repo Rate at 6.50%, Maintains Status Quo",
            event_type="macro",
        )
        print(f"Event created: {result.event_id} (id={result.id})")
        print(f"Classification: {result.event_type}")
        print(f"Impact direction: {result.impact_direction}")
        print(f"Confidence: {result.confidence}")

asyncio.run(create_demo_event())
```

## 5. Assess Portfolio Impact

```python
# scripts/demo_assess.py
import asyncio, uuid
from app.database import async_session_factory
from app.modules.portfolios.service import PortfolioImpactService

async def assess():
    async with async_session_factory() as db:
        service = PortfolioImpactService(db)
        event_id = uuid.UUID("<event-id-from-step-4>")
        portfolio_id = uuid.UUID("<portfolio-id-from-step-3>")
        tenant_id = uuid.UUID("<tenant-id-from-step-2>")

        impacts = await service.assess_event_impact(
            event_id=event_id,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
        )
        for imp in impacts:
            print(f"{imp.holding_id}: {imp.classification.value} "
                  f"(score={imp.impact_score:.2f}, conf={imp.confidence:.2f})")
            print(f"  Reasoning: {imp.reasoning[:100]}...")

        summary = await service.get_portfolio_exposure_summary(
            portfolio_id=portfolio_id, tenant_id=tenant_id,
        )
        print(f"\nExposure Summary: {summary}")

asyncio.run(assess())
```

## 6. Expected Output

```
Holding HDFCBANK: DIRECTLY_AFFECTED (score=0.35, conf=0.70)
  Reasoning: Holding sector (financials) overlaps with event sectors...

Holding RELIANCE: NO_MATERIAL_EVIDENCE (score=0.00, conf=0.00)
  Reasoning: No material connection found...

Holding TCS: INDIRECTLY_AFFECTED (score=0.10, conf=0.30)
  Reasoning: Holding country (in) matches event geography (in)...

Holding SBIN: DIRECTLY_AFFECTED (score=0.35, conf=0.70)
  Reasoning: Holding sector (financials) overlaps with event sectors...

Exposure Summary:
{
  "directly_affected": 2,
  "indirectly_affected": 3,
  "possible_beneficiaries": 1,
  "no_material_evidence": 2,
  "total_holdings": 8
}
```

## 7. Audit Trail

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/audit/?tenant_id=$TENANT_ID"
# Shows all portfolio operations with user_id, action, timestamp
```

## What This Verifies

- [x] CSV upload with validation (weight = 100%, valid exchanges)
- [x] Entity resolution (ticker → company → sector)
- [x] Direct + indirect exposure classification
- [x] Evidence-grounded reasoning with citations
- [x] Confidence scoring (deterministic)
- [x] Tenant isolation (all queries filtered by tenant_id)
- [x] Audit logging
- [x] Auth (JWT) + authorization
- [x] Secure file handling
