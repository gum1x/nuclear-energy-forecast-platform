from fastapi import APIRouter, HTTPException
from typing import Optional

data_router = APIRouter()

@data_router.get("/electricity")
async def get_electricity_data(limit: int = 100):
    """Get historical electricity data"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models import USElectricitySummary
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            query = select(USElectricitySummary).order_by(USElectricitySummary.date.desc()).limit(limit)
            result = await session.execute(query)
            records = result.scalars().all()
            
            return {
                "status": "success",
                "data": [
                    {
                        "date": r.date.isoformat() if r.date else None,
                        "total_generation_gwh": r.total_generation_gwh,
                        "nuclear_generation_gwh": r.nuclear_generation_gwh,
                        "nuclear_share": r.nuclear_share,
                        "urban_population_percent": r.urban_population_percent,
                        "urban_electricity_demand_gwh": r.urban_electricity_demand_gwh
                    }
                    for r in records
                ],
                "count": len(records)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@data_router.get("/eia/raw")
async def get_eia_raw_data(limit: int = 100):
    """Get raw EIA data"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models import EIAElectricity
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            query = select(EIAElectricity).order_by(EIAElectricity.date.desc()).limit(limit)
            result = await session.execute(query)
            records = result.scalars().all()
            
            return {
                "status": "success",
                "data": [
                    {
                        "date": r.date.isoformat() if r.date else None,
                        "region": r.region,
                        "fuel_type": r.fuel_type,
                        "generation_gwh": r.generation_gwh,
                        "consumption_gwh": r.consumption_gwh,
                        "capacity_mw": r.capacity_mw
                    }
                    for r in records
                ],
                "count": len(records)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@data_router.get("/nerc/raw")
async def get_nerc_raw_data(limit: int = 100):
    """Get raw NERC data"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models import NERCReliability
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            query = select(NERCReliability).order_by(NERCReliability.date.desc()).limit(limit)
            result = await session.execute(query)
            records = result.scalars().all()
            
            return {
                "status": "success",
                "data": [
                    {
                        "date": r.date.isoformat() if r.date else None,
                        "region": r.region,
                        "reserve_margin": r.reserve_margin,
                        "peak_demand_mw": r.peak_demand_mw,
                        "available_capacity_mw": r.available_capacity_mw,
                        "nuclear_capacity_mw": r.nuclear_capacity_mw
                    }
                    for r in records
                ],
                "count": len(records)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))