from fastapi import APIRouter, HTTPException
from app.services.data_collector import DataCollectorService

admin_router = APIRouter()
data_collector = DataCollectorService()

@admin_router.post("/data/refresh")
async def refresh_data():
    """Manually trigger data collection from all sources"""
    try:
        await data_collector._collect_eia_data()
        await data_collector._collect_nerc_data()
        await data_collector._collect_worldbank_data()
        await data_collector._collect_grid_data()
        return {"status": "success", "message": "Data collection completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/status")
async def get_system_status():
    """Get system status and health metrics"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models import (
            EIAElectricity, NERCReliability, WorldBankUrbanization,
            USElectricitySummary, NuclearScenario, MarketInsight
        )
        from sqlalchemy import select, func
        
        async with AsyncSessionLocal() as session:
            # Count records in each table
            counts = {}
            for model in [EIAElectricity, NERCReliability, WorldBankUrbanization, USElectricitySummary, NuclearScenario, MarketInsight]:
                query = select(func.count(model.id))
                result = await session.execute(query)
                counts[model.__tablename__] = result.scalar()
            
            # Get latest data dates
            eia_query = select(func.max(EIAElectricity.date))
            eia_result = await session.execute(eia_query)
            latest_eia = eia_result.scalar()
            
            summary_query = select(func.max(USElectricitySummary.date))
            summary_result = await session.execute(summary_query)
            latest_summary = summary_result.scalar()
            
            return {
                "status": "healthy",
                "database": {
                    "record_counts": counts,
                    "latest_eia_data": latest_eia.isoformat() if latest_eia else None,
                    "latest_summary": latest_summary.isoformat() if latest_summary else None
                }
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}