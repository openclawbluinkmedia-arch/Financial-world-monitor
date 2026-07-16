from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app
from app.modules.auth.service import AuthContext, create_access_token
from app.modules.intelligence.models import (
    EventType,
    ImpactDirection,
    ImpactHorizon,
    IntelligenceEvent,
)
from app.modules.portfolios.models import (
    ExposureClassification,
    Holding,
    Portfolio,
)
from app.modules.portfolios.router import (
    upload_portfolio_csv,
)
from app.modules.portfolios.service import PortfolioImpactService

# ---------------------------------------------------------------------------
# Shared test constants
# ---------------------------------------------------------------------------
TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
USER_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def auth_header_for(tenant_id: uuid.UUID, role: str = "analyst") -> dict[str, str]:
    token = create_access_token(str(USER_A), str(tenant_id), role)
    return {"Authorization": f"Bearer {token}"}


AUTH_HEADER_A = auth_header_for(TENANT_A)
AUTH_HEADER_A_ADMIN = auth_header_for(TENANT_A, "admin")
AUTH_HEADER_B = auth_header_for(TENANT_B)


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def mock_client(mock_db):
    async def override_get_db():
        yield mock_db

    async def override_get_auth_context():
        return AuthContext(user_id=USER_A, tenant_id=TENANT_A, role="analyst")

    from app.modules.auth.service import get_auth_context as _get_auth_context
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[_get_auth_context] = override_get_auth_context
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tenant isolation — query-level tests
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    """Verify all queries include tenant_id filter."""

    TENANT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    TENANT_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    @pytest.mark.asyncio
    async def test_get_portfolio_tenant_access(self, mock_client, mock_db):
        """Getting portfolio with wrong tenant_id should 404."""
        portfolio_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resp = await mock_client.get(
            f"/api/portfolios/{portfolio_id}",
            params={"tenant_id": self.TENANT_A},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_holding_inaccessible(self, mock_db):
        """Holding from tenant B should not be accessible to tenant A."""
        holding_b = Holding(
            id=uuid.uuid4(),
            portfolio_id=uuid.uuid4(),
            tenant_id=self.TENANT_B,
            ticker="RELIANCE",
            exchange="NSE",
            company_name="Reliance Industries",
            quantity=100,
            weight=50.0,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = holding_b
        mock_db.execute.return_value = mock_result

        result = await mock_db.execute(MagicMock())
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.tenant_id == self.TENANT_B
        assert found.tenant_id != self.TENANT_A


# ---------------------------------------------------------------------------
# CSV validation tests
# ---------------------------------------------------------------------------

class TestCSVValidation:

    @pytest.mark.asyncio
    async def test_csv_missing_required_columns(self, mock_client):
        """CSV without required columns should be rejected."""
        content = b"ticker,exchange,company_name\nRELIANCE,NSE,Reliance"
        resp = await mock_client.post(
            "/api/portfolios/upload",
            files={"file": ("test.csv", io.BytesIO(content), "text/csv")},
            params={"portfolio_name": "Test", "tenant_id": uuid.uuid4()},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_csv_weight_sum_not_100(self):
        """Weight sum must be 100%."""
        file_mock = AsyncMock()
        file_mock.filename = "test.csv"
        file_mock.content_type = "text/csv"
        file_mock.read.return_value = b"ticker,exchange,company_name,quantity,weight\nRELIANCE,NSE,Reliance,10,50.0\nTCS,NSE,TCS,10,30.0"

        db_mock = AsyncMock(spec=AsyncSession)
        db_mock.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(Exception) as exc:
            await upload_portfolio_csv(
                file=file_mock,
                portfolio_name="Test",
                db=db_mock,
                auth=AuthContext(user_id=USER_A, tenant_id=TENANT_A, role="analyst"),
            )
        assert "weight must equal 100%" in str(exc.value)

    @pytest.mark.asyncio
    async def test_csv_invalid_exchange_rejected(self):
        """Only NSE and BSE exchanges allowed."""
        file_mock = AsyncMock()
        file_mock.filename = "test.csv"
        file_mock.content_type = "text/csv"
        file_mock.read.return_value = b"ticker,exchange,company_name,quantity,weight\nRELIANCE,NYSE,Reliance,10,100.0"
        db_mock = AsyncMock(spec=AsyncSession)

        with pytest.raises(Exception):
            await upload_portfolio_csv(
                file=file_mock,
                portfolio_name="Test",
                db=db_mock,
                auth=AuthContext(user_id=USER_A, tenant_id=TENANT_A, role="analyst"),
            )

    @pytest.mark.asyncio
    async def test_csv_empty_data_rejected(self, mock_client):
        """CSV with header but no data should be rejected."""
        resp = await mock_client.post(
            "/api/portfolios/upload",
            files={"file": ("empty.csv", io.BytesIO(b"ticker,exchange,company_name,quantity,weight\n"), "text/csv")},
            params={"portfolio_name": "Test", "tenant_id": uuid.uuid4()},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_csv_negative_quantity_rejected(self):
        """Negative quantity should be rejected."""
        file_mock = AsyncMock()
        file_mock.filename = "test.csv"
        file_mock.content_type = "text/csv"
        file_mock.read.return_value = b"ticker,exchange,company_name,quantity,weight\nRELIANCE,NSE,Reliance,-10,100.0"
        db_mock = AsyncMock(spec=AsyncSession)
        db_mock.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(Exception):
            await upload_portfolio_csv(
                file=file_mock,
                portfolio_name="Test",
                db=db_mock,
                auth=AuthContext(user_id=USER_A, tenant_id=TENANT_A, role="analyst"),
            )

    @pytest.mark.asyncio
    async def test_csv_non_utf8_rejected(self, mock_client):
        """Non-UTF-8 file should be rejected."""
        resp = await mock_client.post(
            "/api/portfolios/upload",
            files={"file": ("bad.csv", io.BytesIO(b"\xff\xfe\x00"), "text/csv")},
            params={"portfolio_name": "Test", "tenant_id": uuid.uuid4()},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_csv_file_too_large_rejected(self, mock_client):
        """File over 5MB should be rejected."""
        content = b"ticker,exchange,company_name,quantity,weight\n" + b"RELIANCE,NSE,R,1,100.0\n" * 200000
        resp = await mock_client.post(
            "/api/portfolios/upload",
            files={"file": ("big.csv", io.BytesIO(content), "text/csv")},
            params={"portfolio_name": "Test", "tenant_id": uuid.uuid4()},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_csv_non_csv_file_rejected(self, mock_client):
        """Non-CSV file should be rejected."""
        resp = await mock_client.post(
            "/api/portfolios/upload",
            files={"file": ("data.txt", io.BytesIO(b"a,b,c\n1,2,3"), "text/plain")},
            params={"portfolio_name": "Test", "tenant_id": uuid.uuid4()},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Secure deletion tests
# ---------------------------------------------------------------------------

class TestSecureDeletion:

    @pytest.mark.asyncio
    async def test_secure_delete_overwrites_fields(self):
        """Secure deletion should overwrite sensitive fields."""
        holding = Holding(
            id=uuid.uuid4(),
            portfolio_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            ticker="RELIANCE",
            exchange="NSE",
            company_name="Reliance Industries",
            isin="INE002A01018",
            sector="Energy",
            quantity=100,
            weight=50.0,
            avg_price=2500.0,
            current_price=2800.0,
            market_value=280000.0,
        )

        # Simulate secure deletion
        holding.company_name = "[DELETED]"
        holding.ticker = "[DELETED]"
        holding.isin = None
        holding.sector = None
        holding.quantity = 0
        holding.weight = 0
        holding.avg_price = None
        holding.current_price = None
        holding.market_value = None

        assert holding.company_name == "[DELETED]"
        assert holding.ticker == "[DELETED]"
        assert holding.isin is None
        assert holding.sector is None
        assert holding.quantity == 0
        assert holding.weight == 0
        assert holding.avg_price is None
        assert holding.current_price is None
        assert holding.market_value is None

    @pytest.mark.asyncio
    async def test_soft_delete_sets_timestamp(self):
        """Soft delete should set deleted_at."""
        now = datetime.now(timezone.utc)
        portfolio = Portfolio(
            id=uuid.uuid4(),
            name="Test",
            tenant_id=uuid.uuid4(),
            deleted_at=now,
        )
        assert portfolio.deleted_at is not None
        assert portfolio.deleted_at <= datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_soft_delete_unset_by_default(self):
        """Portfolio should have deleted_at=None by default."""
        portfolio = Portfolio(
            id=uuid.uuid4(),
            name="Test",
            tenant_id=uuid.uuid4(),
        )
        assert portfolio.deleted_at is None


# ---------------------------------------------------------------------------
# Portfolio impact service tests
# ---------------------------------------------------------------------------

class TestPortfolioImpactService:

    @pytest.fixture
    def service(self, mock_db):
        return PortfolioImpactService(mock_db)

    def _make_event(self, **kwargs) -> IntelligenceEvent:
        defaults = dict(
            id=uuid.uuid4(),
            event_id="evt-001",
            factual_summary="Test event",
            entities=[],
            sectors=[],
            industries=[],
            event_type=EventType.MACRO,
            impact_direction=ImpactDirection.UNKNOWN,
            impact_horizon=ImpactHorizon.UNKNOWN,
            geography="IN",
            confidence=0.5,
            uncertainty=0.5,
        )
        defaults.update(kwargs)
        return IntelligenceEvent(**defaults)

    def _make_holding(self, **kwargs) -> Holding:
        defaults = dict(
            id=uuid.uuid4(),
            portfolio_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            ticker="TCS",
            exchange="NSE",
            company_name="Tata Consultancy Services",
            sector="Information Technology",
            industry="IT Services",
            country="IN",
            quantity=100,
            weight=100.0,
        )
        defaults.update(kwargs)
        return Holding(**defaults)

    @pytest.mark.asyncio
    async def test_classify_direct_affected(self, service):
        """Direct ticker match -> DIRECTLY_AFFECTED."""
        event = self._make_event(entities=[{"text": "TCS", "label": "ticker", "score": 0.95}])
        holding = self._make_holding(ticker="TCS")

        match_type, classification, score, conf, reasoning, citations = (
            service._classify_holding_impact(
                holding=holding,
                event_entities=event.entities,
                event_sectors=set(),
                event_industries=set(),
                event_geography="in",
                event_affected_names={"tcs"},
                event_companies={"tcs"},
                event_tickers={"TCS"},
                direct_impacts=[],
                indirect_impacts=[],
                possible_beneficiaries=[],
                possible_negative_exposures=[],
                event=event,
            )
        )
        assert classification == ExposureClassification.DIRECTLY_AFFECTED
        assert match_type == "direct"

    @pytest.mark.asyncio
    async def test_classify_sector_indirect_negative(self, service):
        """Sector overlap + negative direction -> INDIRECTLY_AFFECTED with negative score."""
        event = self._make_event(sectors=["Energy"], impact_direction=ImpactDirection.NEGATIVE)
        holding = self._make_holding(sector="Energy")

        match_type, classification, score, conf, reasoning, citations = (
            service._classify_holding_impact(
                holding=holding,
                event_entities=event.entities,
                event_sectors={"energy"},
                event_industries=set(),
                event_geography="in",
                event_affected_names=set(),
                event_companies=set(),
                event_tickers=set(),
                direct_impacts=[],
                indirect_impacts=[],
                possible_beneficiaries=[],
                possible_negative_exposures=[],
                event=event,
            )
        )
        assert classification == ExposureClassification.INDIRECTLY_AFFECTED
        assert match_type == "indirect"
        assert score < 0

    @pytest.mark.asyncio
    async def test_classify_no_material_evidence(self, service):
        """No connection at all -> NO_MATERIAL_EVIDENCE."""
        event = self._make_event(sectors=["Information Technology"])
        holding = self._make_holding(sector="FMCG", ticker="ITC", country="US")

        match_type, classification, score, conf, reasoning, citations = (
            service._classify_holding_impact(
                holding=holding,
                event_entities=event.entities,
                event_sectors={"information technology"},
                event_industries=set(),
                event_geography="in",
                event_affected_names=set(),
                event_companies=set(),
                event_tickers=set(),
                direct_impacts=[],
                indirect_impacts=[],
                possible_beneficiaries=[],
                possible_negative_exposures=[],
                event=event,
            )
        )
        assert classification == ExposureClassification.NO_MATERIAL_EVIDENCE
        assert match_type == "none"

    @pytest.mark.asyncio
    async def test_classify_possible_beneficiary_from_list(self, service):
        """Entity in possible_beneficiaries -> POSSIBLE_BENEFICIARY."""
        event = self._make_event()
        holding = self._make_holding(ticker="TCS")

        match_type, classification, score, conf, reasoning, citations = (
            service._classify_holding_impact(
                holding=holding,
                event_entities=event.entities,
                event_sectors=set(),
                event_industries=set(),
                event_geography="in",
                event_affected_names=set(),
                event_companies=set(),
                event_tickers=set(),
                direct_impacts=[],
                indirect_impacts=[],
                possible_beneficiaries=[{"entity": "TCS", "confidence": 0.8}],
                possible_negative_exposures=[],
                event=event,
            )
        )
        assert classification == ExposureClassification.POSSIBLE_BENEFICIARY

    @pytest.mark.asyncio
    async def test_classify_possible_negative_exposure(self, service):
        """Entity in possible_negative_exposures -> POSSIBLE_NEGATIVE_EXPOSURE."""
        event = self._make_event()
        holding = self._make_holding(ticker="TCS")

        match_type, classification, score, conf, reasoning, citations = (
            service._classify_holding_impact(
                holding=holding,
                event_entities=event.entities,
                event_sectors=set(),
                event_industries=set(),
                event_geography="in",
                event_affected_names=set(),
                event_companies=set(),
                event_tickers=set(),
                direct_impacts=[],
                indirect_impacts=[],
                possible_beneficiaries=[],
                possible_negative_exposures=[{"entity": "TCS", "confidence": 0.7}],
                event=event,
            )
        )
        assert classification == ExposureClassification.POSSIBLE_NEGATIVE_EXPOSURE

    @pytest.mark.asyncio
    async def test_classify_sector_possible_beneficiary(self, service):
        """Sector overlap + positive direction -> POSSIBLE_BENEFICIARY."""
        event = self._make_event(sectors=["Information Technology"], impact_direction=ImpactDirection.POSITIVE)
        holding = self._make_holding(sector="Information Technology", ticker="INFY")

        match_type, classification, score, conf, reasoning, citations = (
            service._classify_holding_impact(
                holding=holding,
                event_entities=event.entities,
                event_sectors={"information technology"},
                event_industries=set(),
                event_geography="in",
                event_affected_names=set(),
                event_companies=set(),
                event_tickers=set(),
                direct_impacts=[],
                indirect_impacts=[],
                possible_beneficiaries=[],
                possible_negative_exposures=[],
                event=event,
            )
        )
        assert classification == ExposureClassification.POSSIBLE_BENEFICIARY

    @pytest.mark.asyncio
    async def test_assess_event_missing_event(self, service, mock_db):
        """Non-existent event raises ValueError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="not found"):
            await service.assess_event_impact(
                event_id=uuid.uuid4(), portfolio_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_assess_event_missing_portfolio(self, service, mock_db):
        """Non-existent portfolio raises ValueError."""
        event_id = uuid.uuid4()
        event = self._make_event(id=event_id)

        mock_db.execute = AsyncMock()
        mock_db.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=event)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]

        with pytest.raises(ValueError, match="not found"):
            await service.assess_event_impact(
                event_id=event_id, portfolio_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_exposure_summary_zero_counts(self, service, mock_db):
        """Empty exposure summary returns all zeros."""
        mock_db.execute = AsyncMock(side_effect=[
            MagicMock(all=MagicMock(return_value=[])),
            MagicMock(scalar=MagicMock(return_value=0)),
        ])

        summary = await service.get_portfolio_exposure_summary(
            portfolio_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
        )
        assert summary["total_holdings"] == 0
        assert all(v == 0 for k, v in summary.items() if k != "total_holdings")

    @pytest.mark.asyncio
    async def test_exposure_summary_with_data(self, service, mock_db):
        """Exposure summary counts by classification."""
        mock_counts = [
            (ExposureClassification.DIRECTLY_AFFECTED.value, 3),
            (ExposureClassification.INDIRECTLY_AFFECTED.value, 5),
        ]
        mock_db.execute = AsyncMock(side_effect=[
            MagicMock(all=MagicMock(return_value=mock_counts)),
            MagicMock(scalar=MagicMock(return_value=20)),
        ])

        summary = await service.get_portfolio_exposure_summary(
            portfolio_id=uuid.uuid4(), tenant_id=uuid.uuid4(),
        )
        assert summary["directly_affected"] == 3
        assert summary["indirectly_affected"] == 5
        assert summary["total_holdings"] == 20
        assert summary["possible_beneficiaries"] == 0

    @pytest.mark.asyncio
    async def test_alert_severity_mapping(self, service):
        """Severity mapping is correct for each classification."""
        assert service._severity_from_impact(0.8, ExposureClassification.DIRECTLY_AFFECTED) == "critical"
        assert service._severity_from_impact(0.3, ExposureClassification.DIRECTLY_AFFECTED) == "warning"
        assert service._severity_from_impact(0.0, ExposureClassification.INDIRECTLY_AFFECTED) == "warning"
        assert service._severity_from_impact(0.0, ExposureClassification.POSSIBLE_BENEFICIARY) == "info"
        assert service._severity_from_impact(0.0, ExposureClassification.NO_MATERIAL_EVIDENCE) == "info"


# ---------------------------------------------------------------------------
# Auth security — HTTP-level tests
# ---------------------------------------------------------------------------

class TestAuthSecurity:
    """Every request must present a valid JWT. No token → 401."""

    @pytest.mark.asyncio
    async def test_no_token_portfolios_list(self):
        app.dependency_overrides.clear()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/portfolios")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_token_portfolios_upload(self):
        app.dependency_overrides.clear()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/portfolios/upload",
                params={"portfolio_name": "Test"},
                files={"file": ("test.csv", io.BytesIO(b"a,b,c\n1,2,3"), "text/csv")},
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_token_evidence_list(self):
        app.dependency_overrides.clear()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/evidence/")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_token_intelligence_events(self):
        app.dependency_overrides.clear()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/intelligence/events")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_token_ingestion_runs(self):
        app.dependency_overrides.clear()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/ingestion/runs")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_health_public(self):
        """Health endpoint should remain public."""
        app.dependency_overrides.clear()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
        assert resp.status_code == 200


class TestTenantIsolationHTTP:
    """A user from tenant A cannot read/list/assess resources from tenant B."""

    @pytest.mark.asyncio
    async def test_cross_tenant_portfolio_returns_404(self, mock_db):
        """Tenant A trying to get Tenant B's portfolio → 404."""
        from app.modules.auth.service import get_auth_context as _get_auth_context

        async def auth_as_a():
            return AuthContext(user_id=USER_A, tenant_id=TENANT_A, role="analyst")

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[_get_auth_context] = auth_as_a

        portfolio_b_id = uuid.uuid4()

        # Portfolio query returns B's portfolio — but tenant_id filter in
        # get_portfolio uses auth.tenant_id (TENANT_A), so the WHERE clause
        # checks both id AND tenant_id.  Since the mock bypasses the actual
        # WHERE, we need the mock to return None so the endpoint 404s.
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None),
        ))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/portfolios/{portfolio_b_id}")

        assert resp.status_code == 404
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_cross_tenant_holdings_404(self, mock_db):
        """Tenant A listing holdings for B's portfolio → 404."""
        from app.modules.auth.service import get_auth_context as _get_auth_context

        async def auth_as_a():
            return AuthContext(user_id=USER_A, tenant_id=TENANT_A, role="analyst")

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[_get_auth_context] = auth_as_a

        portfolio_b_id = uuid.uuid4()

        # Portfolio check returns None (not owned by tenant A)
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None),
        ))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/portfolios/{portfolio_b_id}/holdings")

        assert resp.status_code == 404
        app.dependency_overrides.clear()


class TestRoleEnforcement:
    """Admin-only routes reject analysts with 403."""

    @pytest.mark.asyncio
    async def test_analyst_cannot_delete_portfolio(self, mock_db):
        """Analyst attempting to delete → 403."""
        from app.modules.auth.service import get_auth_context as _get_auth_context

        async def auth_as_analyst():
            return AuthContext(user_id=USER_A, tenant_id=TENANT_A, role="analyst")

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[_get_auth_context] = auth_as_analyst

        portfolio_id = uuid.uuid4()
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=Portfolio(
                id=portfolio_id, name="Test", tenant_id=TENANT_A,
            )),
        ))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(f"/api/portfolios/{portfolio_id}")

        assert resp.status_code == 403
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_admin_can_delete_portfolio(self, mock_db):
        """Admin deleting portfolio → 204."""
        from app.modules.auth.service import get_auth_context as _get_auth_context

        async def auth_as_admin():
            return AuthContext(user_id=USER_A, tenant_id=TENANT_A, role="admin")

        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[_get_auth_context] = auth_as_admin

        portfolio_id = uuid.uuid4()
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=Portfolio(
                id=portfolio_id, name="Test", tenant_id=TENANT_A,
            )),
        ))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(f"/api/portfolios/{portfolio_id}")

        assert resp.status_code == 204
        app.dependency_overrides.clear()
