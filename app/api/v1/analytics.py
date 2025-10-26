from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from app.services.analytics import AnalyticsService

analytics_router = APIRouter()
analytics_service = AnalyticsService()

class InsightRequest(BaseModel):
    insight_type: Optional[str] = None

@analytics_router.get("/insights")
async def get_market_insights(insight_type: Optional[str] = None):
    """Get market insights and analytics"""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models import MarketInsight
        from sqlalchemy import select
        from datetime import datetime
        
        async with AsyncSessionLocal() as session:
            query = select(MarketInsight).where(MarketInsight.expires_at > datetime.now())
            
            if insight_type:
                query = query.where(MarketInsight.insight_type == insight_type)
            
            query = query.order_by(MarketInsight.created_at.desc()).limit(50)
            
            result = await session.execute(query)
            insights = result.scalars().all()
            
            return {
                "status": "success",
                "insights": [
                    {
                        "id": str(i.id),
                        "insight_type": i.insight_type,
                        "title": i.title,
                        "description": i.description,
                        "confidence_score": i.confidence_score,
                        "impact_level": i.impact_level,
                        "created_at": i.created_at.isoformat() if i.created_at else None
                    }
                    for i in insights
                ],
                "count": len(insights)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@analytics_router.post("/insights")
async def create_market_insight(insight: dict):
    """Generate and store new market insights"""
    try:
        insights = await analytics_service.generate_insights()
        return {"status": "success", "insights": insights, "count": len(insights)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))