import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import structlog

from app.core.config import get_settings
from app.core.logging import LoggerMixin
from app.core.database import AsyncSessionLocal
from app.models import USElectricitySummary, NuclearScenario, ModelPerformance
from app.services.celery_app import celery_app

logger = structlog.get_logger(__name__)
settings = get_settings()


class ForecastingService(LoggerMixin):
    def __init__(self):
        self.models = {
            'logistic': LogisticModel(),
            'arima': ARIMAModel(),
            'prophet': ProphetModel(),
            'ml_ensemble': MLEnsembleModel(),
        }
        self.current_model_version = "v1.0"
    
    async def generate_scenarios(
        self,
        scenarios: List[str] = None,
        start_year: int = 2025,
        end_year: int = 2050,
        include_microreactors: bool = True
    ) -> List[Dict]:
        
        if scenarios is None:
            scenarios = ["conservative", "base", "aggressive"]
        
        self.logger.info(
            "Generating scenarios",
            scenarios=scenarios,
            start_year=start_year,
            end_year=end_year
        )
        
        historical_data = await self._get_historical_data()
        
        model_forecasts = {}
        for model_name, model in self.models.items():
            try:
                forecast = await model.forecast(
                    historical_data,
                    start_year,
                    end_year,
                    scenarios
                )
                model_forecasts[model_name] = forecast
                self.logger.info(f"Generated {model_name} forecast")
            except Exception as e:
                self.logger.error(f"Failed to generate {model_name} forecast", error=str(e))
        
        ensemble_forecasts = self._ensemble_forecasts(model_forecasts, scenarios)
        
        if include_microreactors:
            ensemble_forecasts = self._add_microreactor_projections(
                ensemble_forecasts, scenarios
            )
        
        await self._store_forecasts(ensemble_forecasts)
        
        return ensemble_forecasts
    
    async def _get_historical_data(self) -> pd.DataFrame:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            
            query = select(USElectricitySummary).order_by(USElectricitySummary.date)
            result = await session.execute(query)
            records = result.scalars().all()
            
            data = []
            for record in records:
                data.append({
                    'date': record.date,
                    'nuclear_share': record.nuclear_share,
                    'nuclear_generation_twh': record.nuclear_generation_gwh / 1000,
                    'urban_demand_twh': record.urban_electricity_demand_gwh / 1000,
                    'urban_population_percent': record.urban_population_percent
                })
            
            return pd.DataFrame(data)
    
    def _ensemble_forecasts(
        self,
        model_forecasts: Dict[str, List[Dict]],
        scenarios: List[str]
    ) -> List[Dict]:
        
        model_weights = {
            'logistic': 0.3,
            'arima': 0.25,
            'prophet': 0.25,
            'ml_ensemble': 0.2
        }
        
        ensemble_forecasts = []
        
        for scenario in scenarios:
            for year in range(settings.forecast_start_year, settings.forecast_end_year + 1):
                predictions = {}
                for model_name, forecasts in model_forecasts.items():
                    if forecasts:
                        year_data = next(
                            (f for f in forecasts if f['year'] == year and f['scenario_name'] == scenario),
                            None
                        )
                        if year_data:
                            predictions[model_name] = year_data
                
                if predictions:
                    weighted_nuclear_share = sum(
                        pred['nuclear_share'] * model_weights.get(model_name, 0)
                        for model_name, pred in predictions.items()
                    )
                    
                    weighted_nuclear_generation = sum(
                        pred['nuclear_generation_twh'] * model_weights.get(model_name, 0)
                        for model_name, pred in predictions.items()
                    )
                    
                    weighted_urban_demand = sum(
                        pred['urban_demand_twh'] * model_weights.get(model_name, 0)
                        for model_name, pred in predictions.items()
                    )
                    
                    ensemble_forecasts.append({
                        'scenario_name': scenario,
                        'year': year,
                        'nuclear_share': weighted_nuclear_share,
                        'nuclear_generation_twh': weighted_nuclear_generation,
                        'urban_demand_twh': weighted_urban_demand,
                        'microreactor_units': 0,
                        'microreactor_generation_twh': 0,
                        'microreactor_share_of_nuclear': 0,
                        'model_version': self.current_model_version
                    })
        
        return ensemble_forecasts
    
    def _add_microreactor_projections(
        self,
        forecasts: List[Dict],
        scenarios: List[str]
    ) -> List[Dict]:
        
        microreactor_params = {
            'conservative': {'max_units': 3000, 'max_share': 0.10},
            'base': {'max_units': 12000, 'max_share': 0.20},
            'aggressive': {'max_units': 40000, 'max_share': 0.30}
        }
        
        for forecast in forecasts:
            scenario = forecast['scenario_name']
            year = forecast['year']
            
            if scenario in microreactor_params:
                params = microreactor_params[scenario]
                
                units = self._calculate_microreactor_units(year, params['max_units'])
                generation_twh = units * 1.5 * 0.9 * 8760 / 1e6
                
                max_generation = forecast['nuclear_generation_twh'] * params['max_share']
                generation_twh = min(generation_twh, max_generation)
                
                forecast['microreactor_units'] = int(units)
                forecast['microreactor_generation_twh'] = generation_twh
                forecast['microreactor_share_of_nuclear'] = (
                    generation_twh / forecast['nuclear_generation_twh']
                    if forecast['nuclear_generation_twh'] > 0 else 0
                )
        
        return forecasts
    
    def _calculate_microreactor_units(self, year: int, max_units: int) -> float:
        start_year = 2028
        inflection_year = 2035
        growth_rate = 0.35
        
        if year < start_year:
            return 0
        
        t = year - inflection_year
        logistic_value = 1 / (1 + np.exp(-growth_rate * t))
        
        scale_factor = max_units / (1 / (1 + np.exp(-growth_rate * (2050 - inflection_year))))
        
        return logistic_value * scale_factor
    
    async def _store_forecasts(self, forecasts: List[Dict]):
        async with AsyncSessionLocal() as session:
            try:
                for forecast in forecasts:
                    db_forecast = NuclearScenario(**forecast)
                    session.add(db_forecast)
                
                await session.commit()
                self.logger.info("Forecasts stored successfully", count=len(forecasts))
                
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to store forecasts", error=str(e))
                raise
    
    async def start_model_retraining(self):
        try:
            self.logger.info("Starting model retraining")
            await self._retrain_models()
            self.logger.info("Model retraining completed")
        except Exception as e:
            self.logger.error("Model retraining failed", error=str(e))
    
    async def _retrain_models(self):
        historical_data = await self._get_historical_data()
        
        for model_name, model in self.models.items():
            try:
                await model.retrain(historical_data)
                self.logger.info(f"Retrained {model_name} model")
            except Exception as e:
                self.logger.error(f"Failed to retrain {model_name} model", error=str(e))


class BaseForecastingModel:
    def __init__(self):
        self.is_trained = False
        self.model = None
    
    async def forecast(
        self,
        historical_data: pd.DataFrame,
        start_year: int,
        end_year: int,
        scenarios: List[str]
    ) -> List[Dict]:
        raise NotImplementedError
    
    async def retrain(self, historical_data: pd.DataFrame):
        raise NotImplementedError


class LogisticModel(BaseForecastingModel):
    async def forecast(
        self,
        historical_data: pd.DataFrame,
        start_year: int,
        end_year: int,
        scenarios: List[str]
    ) -> List[Dict]:
        
        years = historical_data['date'].dt.year.values
        nuclear_share = historical_data['nuclear_share'].values
        
        K, r, t0 = self._fit_logistic(years, nuclear_share)
        
        forecasts = []
        for scenario in scenarios:
            scenario_params = self._get_scenario_params(scenario, K, r, t0)
            
            for year in range(start_year, end_year + 1):
                nuclear_share_pred = self._logistic_function(
                    year, scenario_params['K'], scenario_params['r'], scenario_params['t0']
                )
                
                urban_demand_growth = 0.012
                base_year = historical_data['date'].dt.year.max()
                years_from_base = year - base_year
                
                urban_demand_twh = (
                    historical_data['urban_electricity_demand_gwh'].iloc[-1] / 1000 *
                    (1 + urban_demand_growth) ** years_from_base
                )
                
                nuclear_generation_twh = nuclear_share_pred * urban_demand_twh
                
                forecasts.append({
                    'scenario_name': scenario,
                    'year': year,
                    'nuclear_share': nuclear_share_pred,
                    'nuclear_generation_twh': nuclear_generation_twh,
                    'urban_demand_twh': urban_demand_twh,
                    'microreactor_units': 0,
                    'microreactor_generation_twh': 0,
                    'microreactor_share_of_nuclear': 0,
                    'model_version': 'logistic_v1.0'
                })
        
        return forecasts
    
    def _fit_logistic(self, years: np.ndarray, values: np.ndarray) -> Tuple[float, float, float]:
        K_range = (0.3, 0.8)
        r_range = (0.01, 0.1)
        t0_range = (2000, 2040)
        
        best_sse = float('inf')
        best_params = None
        
        for K in np.linspace(K_range[0], K_range[1], 20):
            for r in np.linspace(r_range[0], r_range[1], 20):
                for t0 in np.linspace(t0_range[0], t0_range[1], 20):
                    predicted = self._logistic_function(years, K, r, t0)
                    sse = np.sum((predicted - values) ** 2)
                    
                    if sse < best_sse:
                        best_sse = sse
                        best_params = (K, r, t0)
        
        return best_params
    
    def _logistic_function(self, t: float, K: float, r: float, t0: float) -> float:
        return K / (1 + np.exp(-r * (t - t0)))
    
    def _get_scenario_params(self, scenario: str, K: float, r: float, t0: float) -> Dict:
        scenario_adjustments = {
            'conservative': {'K_mult': 0.8, 'r_mult': 0.7},
            'base': {'K_mult': 1.0, 'r_mult': 1.0},
            'aggressive': {'K_mult': 1.2, 'r_mult': 1.3}
        }
        
        adj = scenario_adjustments.get(scenario, scenario_adjustments['base'])
        return {
            'K': K * adj['K_mult'],
            'r': r * adj['r_mult'],
            't0': t0
        }
    
    async def retrain(self, historical_data: pd.DataFrame):
        self.is_trained = True


class ARIMAModel(BaseForecastingModel):
    async def forecast(
        self,
        historical_data: pd.DataFrame,
        start_year: int,
        end_year: int,
        scenarios: List[str]
    ) -> List[Dict]:
        
        forecasts = []
        nuclear_share_series = historical_data['nuclear_share'].values
        
        trend = np.polyfit(range(len(nuclear_share_series)), nuclear_share_series, 1)
        
        for scenario in scenarios:
            scenario_multiplier = {'conservative': 0.8, 'base': 1.0, 'aggressive': 1.2}[scenario]
            
            for year in range(start_year, end_year + 1):
                years_ahead = year - historical_data['date'].dt.year.max()
                nuclear_share_pred = (
                    nuclear_share_series[-1] + trend[0] * years_ahead
                ) * scenario_multiplier
                
                nuclear_share_pred = max(0, min(1, nuclear_share_pred))
                
                forecasts.append({
                    'scenario_name': scenario,
                    'year': year,
                    'nuclear_share': nuclear_share_pred,
                    'nuclear_generation_twh': nuclear_share_pred * 4000,
                    'urban_demand_twh': 4000,
                    'microreactor_units': 0,
                    'microreactor_generation_twh': 0,
                    'microreactor_share_of_nuclear': 0,
                    'model_version': 'arima_v1.0'
                })
        
        return forecasts
    
    async def retrain(self, historical_data: pd.DataFrame):
        self.is_trained = True


class ProphetModel(BaseForecastingModel):
    async def forecast(
        self,
        historical_data: pd.DataFrame,
        start_year: int,
        end_year: int,
        scenarios: List[str]
    ) -> List[Dict]:
        
        forecasts = []
        
        for scenario in scenarios:
            for year in range(start_year, end_year + 1):
                nuclear_share_pred = 0.2 + 0.01 * (year - 2025)
                
                forecasts.append({
                    'scenario_name': scenario,
                    'year': year,
                    'nuclear_share': nuclear_share_pred,
                    'nuclear_generation_twh': nuclear_share_pred * 4000,
                    'urban_demand_twh': 4000,
                    'microreactor_units': 0,
                    'microreactor_generation_twh': 0,
                    'microreactor_share_of_nuclear': 0,
                    'model_version': 'prophet_v1.0'
                })
        
        return forecasts
    
    async def retrain(self, historical_data: pd.DataFrame):
        self.is_trained = True


class MLEnsembleModel(BaseForecastingModel):
    async def forecast(
        self,
        historical_data: pd.DataFrame,
        start_year: int,
        end_year: int,
        scenarios: List[str]
    ) -> List[Dict]:
        
        forecasts = []
        
        for scenario in scenarios:
            for year in range(start_year, end_year + 1):
                nuclear_share_pred = 0.18 + 0.008 * (year - 2025)
                
                forecasts.append({
                    'scenario_name': scenario,
                    'year': year,
                    'nuclear_share': nuclear_share_pred,
                    'nuclear_generation_twh': nuclear_share_pred * 4000,
                    'urban_demand_twh': 4000,
                    'microreactor_units': 0,
                    'microreactor_generation_twh': 0,
                    'microreactor_share_of_nuclear': 0,
                    'model_version': 'ml_ensemble_v1.0'
                })
        
        return forecasts
    
    async def retrain(self, historical_data: pd.DataFrame):
        self.is_trained = True


@celery_app
def generate_forecast_task(scenarios: List[str], start_year: int, end_year: int):
    forecasting_service = ForecastingService()
    return asyncio.run(
        forecasting_service.generate_scenarios(scenarios, start_year, end_year)
    )


@celery_app
def retrain_models_task():
    forecasting_service = ForecastingService()
    return asyncio.run(forecasting_service._retrain_models())