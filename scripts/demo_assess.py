"""
Demo: Assess portfolio impact for an event.
Usage: python scripts/demo_assess.py <event_id> <portfolio_id> <tenant_id>
"""
import asyncio
import sys
import uuid

from app.database import async_session_factory
from app.modules.portfolios.service import PortfolioImpactService


async def main(event_id: uuid.UUID, portfolio_id: uuid.UUID, tenant_id: uuid.UUID):
    async with async_session_factory() as db:
        service = PortfolioImpactService(db)
        impacts = await service.assess_event_impact(
            event_id=event_id,
            portfolio_id=portfolio_id,
            tenant_id=tenant_id,
        )
        print(f"\nIMPACTS ASSESSED: {len(impacts)}")
        print("=" * 60)
        for imp in impacts:
            print(f"\nHolding Impact:")
            print(f"  Classification: {imp.classification.value}")
            print(f"  Impact Score:   {imp.impact_score:.3f}")
            print(f"  Confidence:     {imp.confidence:.3f}")
            print(f"  Reasoning:      {imp.reasoning[:200]}")
            if imp.citations:
                print(f"  Citations:      {imp.citations[:3]}")

        summary = await service.get_portfolio_exposure_summary(
            portfolio_id=portfolio_id, tenant_id=tenant_id,
        )
        print(f"\nEXPOSURE SUMMARY:")
        print("=" * 60)
        for k, v in summary.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python scripts/demo_assess.py <event_id> <portfolio_id> <tenant_id>")
        sys.exit(1)
    asyncio.run(main(
        uuid.UUID(sys.argv[1]),
        uuid.UUID(sys.argv[2]),
        uuid.UUID(sys.argv[3]),
    ))
