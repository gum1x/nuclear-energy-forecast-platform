from datetime import datetime, date
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from pydantic import BaseModel, Field
import structlog

from app.core.database import get_db
from app.models import (
    NuclearScenario, USElectricitySummary, ModelPerformance, 
    MarketInsight, EIAElectricity, NERCReliability
)
from app.services.forecasting import ForecastingService
from app.services.analytics import AnalyticsService

logger = structlog.get_logger(__name__)

class ScenarioResponse(BaseModel):
    scenario_name: str
    year: int
    nuclear_share: float
    nuclear_generation_twh: float
    microreactor_units: int
    microreactor_generation_twh: float
    microreactor_share_of_nuclear: float
    urban_demand_twh: float
    model_version: str

class ForecastRequest(BaseModel):
    scenarios: List[str] = Field(default=["conservative", "base", "aggressive"])
    start_year: int = Field(default=2025, ge=2025, le=2050)
    end_year: int = Field(default=2050, ge=2025, le=2050)
    include_microreactors: bool = Field(default=True)

class ForecastResponse(BaseModel):
    scenarios: List[ScenarioResponse]
    generated_at: datetime
    model_version: str
    data_points: int

class ElectricityDataResponse(BaseModel):
    date: date
    total_generation_gwh: float
    nuclear_generation_gwh: float
    nuclear_share: float
    urban_population_percent: float
    urban_electricity_demand_gwh: float

class ModelPerformanceResponse(BaseModel):
    model_name: str
    metric_name: str
    metric_value: float
    evaluation_date: date

class MarketInsightResponse(BaseModel):
    insight_type: str
    title: str
    description: str
    confidence_score: float
    impact_level: str
    created_at: datetime
    expires_at: Optional[datetime]

forecasts_router = APIRouter()
data_router = APIRouter()
analytics_router = APIRouter()
admin_router = APIRouter()


@forecasts_router.post("/generate", response_model=ForecastResponse)
async def generate_forecast(
    request: ForecastRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Generate nuclear energy forecasts for specified scenarios"""
    try:
        logger.info("Generating forecast", scenarios=request.scenarios)
        
        forecasting_service = ForecastingService()
        
        forecasts = await forecasting_service.generate_scenarios(
            scenarios=request.scenarios,
            start_year=request.start_year,
            end_year=request.end_year,
            include_microreactors=request.include_microreactors
        )
        
        background_tasks.add_task(store_forecasts, forecasts, db)
        
        scenario_responses = [
            ScenarioResponse(**forecast) for forecast in forecasts
        ]
        
        return ForecastResponse(
            scenarios=scenario_responses,
            generated_at=datetime.now(),
            model_version="v1.0",
            data_points=len(scenario_responses)
        )
        
    except Exception as e:
        logger.error("Failed to generate forecast", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate forecast")


@forecasts_router.get("/scenarios", response_model=List[ScenarioResponse])
async def get_scenarios(
    scenario_name: Optional[str] = Query(None),
    start_year: Optional[int] = Query(None),
    end_year: Optional[int] = Query(None),
    model_version: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get nuclear energy scenario forecasts"""
    try:
        query = select(NuclearScenario)
        
        conditions = []
        if scenario_name:
            conditions.append(NuclearScenario.scenario_name == scenario_name)
        if start_year:
            conditions.append(NuclearScenario.year >= start_year)
        if end_year:
            conditions.append(NuclearScenario.year <= end_year)
        if model_version:
            conditions.append(NuclearScenario.model_version == model_version)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(NuclearScenario.scenario_name, NuclearScenario.year)
        
        result = await db.execute(query)
        scenarios = result.scalars().all()
        
        return [ScenarioResponse(**scenario.__dict__) for scenario in scenarios]
        
    except Exception as e:
        logger.error("Failed to get scenarios", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve scenarios")


@forecasts_router.get("/performance", response_model=List[ModelPerformanceResponse])
async def get_model_performance(
    model_name: Optional[str] = Query(None),
    metric_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get model performance metrics"""
    try:
        query = select(ModelPerformance)
        
        conditions = []
        if model_name:
            conditions.append(ModelPerformance.model_name == model_name)
        if metric_name:
            conditions.append(ModelPerformance.metric_name == metric_name)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(ModelPerformance.evaluation_date.desc())
        
        result = await db.execute(query)
        performance = result.scalars().all()
        
        return [ModelPerformanceResponse(**perf.__dict__) for perf in performance]
        
    except Exception as e:
        logger.error("Failed to get model performance", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve model performance")


@data_router.get("/electricity", response_model=List[ElectricityDataResponse])
async def get_electricity_data(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(1000, le=10000),
    db: AsyncSession = Depends(get_db)
):
    """Get processed electricity data"""
    try:
        query = select(USElectricitySummary)
        
        conditions = []
        if start_date:
            conditions.append(USElectricitySummary.date >= start_date)
        if end_date:
            conditions.append(USElectricitySummary.date <= end_date)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(USElectricitySummary.date.desc()).limit(limit)
        
        result = await db.execute(query)
        data = result.scalars().all()
        
        return [ElectricityDataResponse(**record.__dict__) for record in data]
        
    except Exception as e:
        logger.error("Failed to get electricity data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve electricity data")


@data_router.get("/eia/raw")
async def get_eia_raw_data(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    region: Optional[str] = Query(None),
    fuel_type: Optional[str] = Query(None),
    limit: int = Query(1000, le=10000),
    db: AsyncSession = Depends(get_db)
):
    """Get raw EIA electricity data"""
    try:
        query = select(EIAElectricity)
        
        conditions = []
        if start_date:
            conditions.append(EIAElectricity.date >= start_date)
        if end_date:
            conditions.append(EIAElectricity.date <= end_date)
        if region:
            conditions.append(EIAElectricity.region == region)
        if fuel_type:
            conditions.append(EIAElectricity.fuel_type == fuel_type)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(EIAElectricity.date.desc()).limit(limit)
        
        result = await db.execute(query)
        data = result.scalars().all()
        
        return [record.__dict__ for record in data]
        
    except Exception as e:
        logger.error("Failed to get EIA raw data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve EIA data")


@data_router.get("/nerc/raw")
async def get_nerc_raw_data(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    region: Optional[str] = Query(None),
    limit: int = Query(1000, le=10000),
    db: AsyncSession = Depends(get_db)
):
    """Get raw NERC reliability data"""
    try:
        query = select(NERCReliability)
        
        conditions = []
        if start_date:
            conditions.append(NERCReliability.date >= start_date)
        if end_date:
            conditions.append(NERCReliability.date <= end_date)
        if region:
            conditions.append(NERCReliability.region == region)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(NERCReliability.date.desc()).limit(limit)
        
        result = await db.execute(query)
        data = result.scalars().all()
        
        return [record.__dict__ for record in data]
        
    except Exception as e:
        logger.error("Failed to get NERC raw data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve NERC data")


@analytics_router.get("/insights", response_model=List[MarketInsightResponse])
async def get_market_insights(
    insight_type: Optional[str] = Query(None),
    impact_level: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Get market insights and analysis"""
    try:
        query = select(MarketInsight)
        
        conditions = []
        if insight_type:
            conditions.append(MarketInsight.insight_type == insight_type)
        if impact_level:
            conditions.append(MarketInsight.impact_level == impact_level)
        if active_only:
            conditions.append(
                or_(
                    MarketInsight.expires_at.is_(None),
                    MarketInsight.expires_at > datetime.now()
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(MarketInsight.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        insights = result.scalars().all()
        
        return [MarketInsightResponse(**insight.__dict__) for insight in insights]
        
    except Exception as e:
        logger.error("Failed to get market insights", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve market insights")


@analytics_router.post("/insights")
async def create_market_insight(
    insight: MarketInsightResponse,
    db: AsyncSession = Depends(get_db)
):
    """Create a new market insight"""
    try:
        db_insight = MarketInsight(**insight.dict())
        db.add(db_insight)
        await db.commit()
        await db.refresh(db_insight)
        
        return {"id": db_insight.id, "status": "created"}
        
    except Exception as e:
        await db.rollback()
        logger.error("Failed to create market insight", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create market insight")


@admin_router.post("/data/refresh")
async def refresh_data(
    source: str = Query(..., description="Data source to refresh"),
    background_tasks: BackgroundTasks
):
    """Trigger data refresh for specified source"""
    try:
        from app.services.data_collector import DataCollectorService
        
        collector = DataCollectorService()
        
        if source == "eia":
            background_tasks.add_task(collector._collect_eia_data)
        elif source == "nerc":
            background_tasks.add_task(collector._collect_nerc_data)
        elif source == "worldbank":
            background_tasks.add_task(collector._collect_worldbank_data)
        else:
            raise HTTPException(status_code=400, detail="Invalid data source")
        
        return {"status": "refresh_triggered", "source": source}
        
    except Exception as e:
        logger.error("Failed to trigger data refresh", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to trigger data refresh")


@admin_router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    """Get system status and health metrics"""
    try:
        latest_eia = await db.execute(
            select(func.max(EIAElectricity.date))
        )
        latest_nerc = await db.execute(
            select(func.max(NERCReliability.date))
        )
        latest_summary = await db.execute(
            select(func.max(USElectricitySummary.date))
        )
        
        eia_count = await db.execute(select(func.count(EIAElectricity.id)))
        nerc_count = await db.execute(select(func.count(NERCReliability.id)))
        summary_count = await db.execute(select(func.count(USElectricitySummary.id)))
        
        return {
            "status": "healthy",
            "data_sources": {
                "eia": {
                    "latest_date": latest_eia.scalar(),
                    "record_count": eia_count.scalar()
                },
                "nerc": {
                    "latest_date": latest_nerc.scalar(),
                    "record_count": nerc_count.scalar()
                },
                "summary": {
                    "latest_date": latest_summary.scalar(),
                    "record_count": summary_count.scalar()
                }
            },
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")


async def store_forecasts(forecasts: List[Dict], db: AsyncSession):
    """Store forecasts in database"""
    try:
        for forecast in forecasts:
            db_forecast = NuclearScenario(**forecast)
            db.add(db_forecast)
        
        await db.commit()
        logger.info("Forecasts stored successfully", count=len(forecasts))
        
    except Exception as e:
        await db.rollback()
        logger.error("Failed to store forecasts", error=str(e))
        raise
