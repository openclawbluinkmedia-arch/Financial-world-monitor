"""
Demo: Create an RBI rate decision event through the intelligence pipeline.
Usage: python scripts/demo_create_event.py
"""
import asyncio
import uuid

from app.database import async_session_factory
from app.modules.intelligence.pipeline import IntelligencePipeline


async def main():
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
- Lower bond yields benefit IT companies via treasury gains
- Auto sector sees continued demand with stable rates
- FMCG sector benefits from rural demand recovery
- Real estate and construction positive on steady rates
            """,
            title="RBI Holds Repo Rate at 6.50%, Maintains Status Quo",
            event_type="macro",
        )
        print(f"EVENT CREATED:")
        print(f"  ID: {result.id}")
        print(f"  Event ID: {result.event_id}")
        print(f"  Type: {result.event_type}")
        print(f"  Direction: {result.impact_direction}")
        print(f"  Horizon: {result.impact_horizon}")
        print(f"  Confidence: {result.confidence:.3f}")
        print(f"  Human review needed: {result.human_review_required}")
        print(f"\nUse event_id={result.id} in demo_assess.py")


if __name__ == "__main__":
    asyncio.run(main())
