from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.services.forecasting import ForecastingService

forecasts_router = APIRouter()
forecasting_service = ForecastingService()

class ForecastRequest(BaseModel):
    scenarios: Optional[List[str]] = None
    start_year: int = 2025
    end_year: int = 2050
    include_microreactors: bool = True

@forecasts_router.post("/generate")
async def generate_forecast(request: ForecastRequest):
    """Generate nuclear energy forecasts using multiple models"""
    try:
        forecasts = await forecasting_service.generate_scenarios(
            scenarios=request.scenarios,
            start_year=request.start_year,
            end_year=request.end_year,
            include_microreactors=request.include_microreactors
        )
        return {"status": "success", "forecasts": forecasts, "count": len(forecasts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@forecasts_router.get("/scenarios")
async def get_scenarios(scenario_name: Optional[str] = None):
    """Get stored forecast scenarios"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models import NuclearScenario
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            query = select(NuclearScenario)
            if scenario_name:
                query = query.where(NuclearScenario.scenario_name == scenario_name)
            
            result = await session.execute(query)
            scenarios = result.scalars().all()
            
            return {
                "status": "success",
                "scenarios": [
                    {
                        "scenario_name": s.scenario_name,
                        "year": s.year,
                        "nuclear_share": s.nuclear_share,
                        "nuclear_generation_twh": s.nuclear_generation_twh,
                        "microreactor_units": s.microreactor_units,
                        "urban_demand_twh": s.urban_demand_twh
                    }
                    for s in scenarios
                ],
                "count": len(scenarios)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@forecasts_router.get("/performance")
async def get_model_performance():
    """Get model performance metrics"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models import ModelPerformance
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            query = select(ModelPerformance).order_by(ModelPerformance.evaluation_date.desc()).limit(10)
            result = await session.execute(query)
            performances = result.scalars().all()
            
            return {
                "status": "success",
                "metrics": [
                    {
                        "model_name": p.model_name,
                        "metric_name": p.metric_name,
                        "metric_value": p.metric_value,
                        "evaluation_date": p.evaluation_date.isoformat()
                    }
                    for p in performances
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))