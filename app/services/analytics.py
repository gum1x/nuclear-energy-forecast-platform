import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
import structlog

from app.core.logging import LoggerMixin
from app.core.database import AsyncSessionLocal
from app.models import MarketInsight, ModelPerformance, USElectricitySummary
from app.services.celery_app import celery_app

logger = structlog.get_logger(__name__)


class AnalyticsService(LoggerMixin):
    def __init__(self):
        self.insight_generators = {
            'nuclear_trend': NuclearTrendAnalyzer(),
            'market_opportunity': MarketOpportunityAnalyzer(),
            'risk_assessment': RiskAssessmentAnalyzer(),
            'performance_analysis': PerformanceAnalyzer(),
        }
    
    async def generate_insights(self) -> List[Dict]:
        insights = []
        
        for insight_type, generator in self.insight_generators.items():
            try:
                generator_insights = await generator.analyze()
                insights.extend(generator_insights)
                self.logger.info(f"Generated {insight_type} insights", count=len(generator_insights))
            except Exception as e:
                self.logger.error(f"Failed to generate {insight_type} insights", error=str(e))
        
        await self._store_insights(insights)
        
        return insights
    
    async def _store_insights(self, insights: List[Dict]):
        async with AsyncSessionLocal() as session:
            try:
                for insight in insights:
                    db_insight = MarketInsight(**insight)
                    session.add(db_insight)
                
                await session.commit()
                self.logger.info("Insights stored successfully", count=len(insights))
                
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to store insights", error=str(e))
                raise
    
    async def evaluate_model_performance(self) -> Dict[str, float]:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            
            query = select(USElectricitySummary).order_by(USElectricitySummary.date.desc()).limit(100)
            result = await session.execute(query)
            actual_data = result.scalars().all()
            
            metrics = {}
            
            if actual_data:
                nuclear_shares = [record.nuclear_share for record in actual_data if record.nuclear_share is not None]
                
                if len(nuclear_shares) > 1:
                    trend_actual = np.diff(nuclear_shares[-10:]) if len(nuclear_shares) >= 10 else np.diff(nuclear_shares)
                    trend_predicted = np.full_like(trend_actual, 0.001)
                    
                    metrics['trend_accuracy'] = 1 - np.mean(np.abs(trend_actual - trend_predicted))
                    
                    volatility_actual = np.std(nuclear_shares[-30:]) if len(nuclear_shares) >= 30 else np.std(nuclear_shares)
                    metrics['volatility_prediction'] = min(1.0, max(0.0, 1 - abs(volatility_actual - 0.05) / 0.05))
                    
                    metrics['overall_accuracy'] = (metrics['trend_accuracy'] + metrics['volatility_prediction']) / 2
            
            await self._store_performance_metrics(metrics)
            
            return metrics
    
    async def _store_performance_metrics(self, metrics: Dict[str, float]):
        async with AsyncSessionLocal() as session:
            try:
                for metric_name, metric_value in metrics.items():
                    performance = ModelPerformance(
                        model_name="ensemble",
                        metric_name=metric_name,
                        metric_value=metric_value,
                        evaluation_date=datetime.now().date()
                    )
                    session.add(performance)
                
                await session.commit()
                
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to store performance metrics", error=str(e))
                raise


class BaseInsightGenerator:
    async def analyze(self) -> List[Dict]:
        raise NotImplementedError


class NuclearTrendAnalyzer(BaseInsightGenerator):
    async def analyze(self) -> List[Dict]:
        insights = []
        
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select, func
            
            query = select(USElectricitySummary).order_by(USElectricitySummary.date.desc()).limit(12)
            result = await session.execute(query)
            data = result.scalars().all()
            
            if len(data) >= 6:
                nuclear_shares = [record.nuclear_share for record in data if record.nuclear_share is not None]
                
                if len(nuclear_shares) >= 6:
                    recent_avg = np.mean(nuclear_shares[:6])
                    older_avg = np.mean(nuclear_shares[6:])
                    trend = recent_avg - older_avg
                    
                    if trend > 0.01:
                        insights.append({
                            'insight_type': 'nuclear_trend',
                            'title': 'Nuclear Share Showing Positive Trend',
                            'description': f'Nuclear share has increased by {trend:.3f} over the last 6 months, indicating growing adoption.',
                            'confidence_score': min(0.9, abs(trend) * 10),
                            'impact_level': 'medium',
                            'expires_at': datetime.now() + timedelta(days=30)
                        })
                    elif trend < -0.01:
                        insights.append({
                            'insight_type': 'nuclear_trend',
                            'title': 'Nuclear Share Declining',
                            'description': f'Nuclear share has decreased by {abs(trend):.3f} over the last 6 months, requiring attention.',
                            'confidence_score': min(0.9, abs(trend) * 10),
                            'impact_level': 'high',
                            'expires_at': datetime.now() + timedelta(days=7)
                        })
        
        return insights


class MarketOpportunityAnalyzer(BaseInsightGenerator):
    async def analyze(self) -> List[Dict]:
        insights = []
        
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            
            query = select(USElectricitySummary).order_by(USElectricitySummary.date.desc()).limit(1)
            result = await session.execute(query)
            latest = result.scalar_one_or_none()
            
            if latest and latest.nuclear_share < 0.2:
                insights.append({
                    'insight_type': 'market_opportunity',
                    'title': 'Significant Nuclear Growth Opportunity',
                    'description': f'Current nuclear share of {latest.nuclear_share:.1%} represents significant growth potential in urban electricity markets.',
                    'confidence_score': 0.8,
                    'impact_level': 'high',
                    'expires_at': datetime.now() + timedelta(days=90)
                })
        
        return insights


class RiskAssessmentAnalyzer(BaseInsightGenerator):
    async def analyze(self) -> List[Dict]:
        insights = []
        
        insights.append({
            'insight_type': 'risk_assessment',
            'title': 'Regulatory Risk Monitoring',
            'description': 'Monitor regulatory changes that could impact nuclear deployment timelines and costs.',
            'confidence_score': 0.7,
            'impact_level': 'medium',
            'expires_at': datetime.now() + timedelta(days=60)
        })
        
        return insights


class PerformanceAnalyzer(BaseInsightGenerator):
    async def analyze(self) -> List[Dict]:
        insights = []
        
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select, func
            
            query = select(func.max(USElectricitySummary.date))
            result = await session.execute(query)
            latest_date = result.scalar()
            
            if latest_date:
                days_old = (datetime.now().date() - latest_date).days
                
                if days_old > 7:
                    insights.append({
                        'insight_type': 'performance_analysis',
                        'title': 'Data Freshness Alert',
                        'description': f'Latest electricity data is {days_old} days old. Consider refreshing data sources.',
                        'confidence_score': 1.0,
                        'impact_level': 'medium',
                        'expires_at': datetime.now() + timedelta(days=1)
                    })
        
        return insights


@celery_app.task
def generate_insights_task():
    analytics_service = AnalyticsService()
    return asyncio.run(analytics_service.generate_insights())


@celery_app.task
def evaluate_performance_task():
    analytics_service = AnalyticsService()
    return asyncio.run(analytics_service.evaluate_model_performance())
