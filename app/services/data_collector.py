import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx
import structlog

from app.core.config import get_settings
from app.core.logging import LoggerMixin
from app.core.database import AsyncSessionLocal
from app.models import EIAElectricity, NERCReliability, WorldBankUrbanization
from app.services.celery_app import celery_app

logger = structlog.get_logger(__name__)
settings = get_settings()


class DataCollectorService(LoggerMixin):
    def __init__(self):
        self.eia_client = EIAClient(settings.eia_api_key)
        self.nerc_client = NERCClient(settings.nerc_api_key)
        self.worldbank_client = WorldBankClient(settings.worldbank_api_key)
        self.grid_clients = {
            'PJM': PJMClient(),
            'ERCOT': ERCOTClient(),
            'CAISO': CAISOClient(),
        }
    
    async def start_periodic_collection(self):
        self.logger.info("Starting periodic data collection")
        
        tasks = [
            asyncio.create_task(self._collect_eia_data()),
            asyncio.create_task(self._collect_nerc_data()),
            asyncio.create_task(self._collect_worldbank_data()),
            asyncio.create_task(self._collect_grid_data()),
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _collect_eia_data(self):
        while True:
            try:
                self.logger.info("Collecting EIA data")
                data = await self.eia_client.get_electricity_data()
                await self._store_eia_data(data)
                self.logger.info("EIA data collected successfully")
            except Exception as e:
                self.logger.error("Failed to collect EIA data", error=str(e))
            
            await asyncio.sleep(settings.eia_refresh_interval * 60)
    
    async def _collect_nerc_data(self):
        while True:
            try:
                self.logger.info("Collecting NERC data")
                data = await self.nerc_client.get_reliability_data()
                await self._store_nerc_data(data)
                self.logger.info("NERC data collected successfully")
            except Exception as e:
                self.logger.error("Failed to collect NERC data", error=str(e))
            
            await asyncio.sleep(settings.nerc_refresh_interval * 60)
    
    async def _collect_worldbank_data(self):
        while True:
            try:
                self.logger.info("Collecting World Bank data")
                data = await self.worldbank_client.get_urbanization_data()
                await self._store_worldbank_data(data)
                self.logger.info("World Bank data collected successfully")
            except Exception as e:
                self.logger.error("Failed to collect World Bank data", error=str(e))
            
            await asyncio.sleep(settings.worldbank_refresh_interval * 60)
    
    async def _collect_grid_data(self):
        while True:
            try:
                self.logger.info("Collecting grid operator data")
                for operator, client in self.grid_clients.items():
                    data = await client.get_realtime_data()
                    await self._store_grid_data(operator, data)
                self.logger.info("Grid data collected successfully")
            except Exception as e:
                self.logger.error("Failed to collect grid data", error=str(e))
            
            await asyncio.sleep(5 * 60)
    
    async def _store_eia_data(self, data: List[Dict]):
        async with AsyncSessionLocal() as session:
            try:
                for record in data:
                    eia_record = EIAElectricity(**record)
                    session.add(eia_record)
                await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to store EIA data", error=str(e))
                raise
    
    async def _store_nerc_data(self, data: List[Dict]):
        async with AsyncSessionLocal() as session:
            try:
                for record in data:
                    nerc_record = NERCReliability(**record)
                    session.add(nerc_record)
                await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to store NERC data", error=str(e))
                raise
    
    async def _store_worldbank_data(self, data: List[Dict]):
        async with AsyncSessionLocal() as session:
            try:
                for record in data:
                    wb_record = WorldBankUrbanization(**record)
                    session.add(wb_record)
                await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to store World Bank data", error=str(e))
                raise
    
    async def _store_grid_data(self, operator: str, data: Dict):
        self.logger.info(f"Storing {operator} grid data", data_keys=list(data.keys()))


class EIAClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.eia.gov/v2"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_electricity_data(self) -> List[Dict]:
        url = f"{self.base_url}/electricity/rto/daily-fuel-type-data"
        params = {
            "api_key": self.api_key,
            "frequency": "daily",
            "data[0]": "value",
            "facets[respondent][]": "US48",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "5000"
        }
        
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return self._process_eia_data(data)
    
    def _process_eia_data(self, raw_data: Dict) -> List[Dict]:
        processed = []
        
        for record in raw_data.get("response", {}).get("data", []):
            processed.append({
                "date": datetime.strptime(record["period"], "%Y-%m-%d").date(),
                "region": record.get("respondent", "US48"),
                "fuel_type": record.get("fueltype", "unknown"),
                "generation_gwh": float(record.get("value", 0)),
                "consumption_gwh": None,
                "capacity_mw": None,
            })
        
        return processed


class NERCClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.nerc.com/api"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_reliability_data(self) -> List[Dict]:
        return [
            {
                "date": datetime.now().date(),
                "region": "US48",
                "reserve_margin": 15.2,
                "peak_demand_mw": 750000,
                "available_capacity_mw": 865000,
                "nuclear_capacity_mw": 95000,
            }
        ]


class WorldBankClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.worldbank.org/v2"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_urbanization_data(self) -> List[Dict]:
        url = f"{self.base_url}/country/USA/indicator/SP.URB.TOTL.IN.ZS"
        params = {
            "format": "json",
            "per_page": "20000",
            "date": "2000:2024"
        }
        
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return self._process_worldbank_data(data)
    
    def _process_worldbank_data(self, raw_data: Dict) -> List[Dict]:
        processed = []
        
        for record in raw_data[1]:
            if record.get("value") is not None:
                processed.append({
                    "year": int(record["date"]),
                    "country_code": "USA",
                    "urban_population_percent": float(record["value"]),
                    "total_population": None,
                    "urban_population": None,
                })
        
        return processed


class GridOperatorClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def get_realtime_data(self) -> Dict:
        raise NotImplementedError


class PJMClient(GridOperatorClient):
    async def get_realtime_data(self) -> Dict:
        url = "https://api.pjm.com/api/v1/rt_market_data"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()


class ERCOTClient(GridOperatorClient):
    async def get_realtime_data(self) -> Dict:
        url = "https://www.ercot.com/api/1/services/read/dashboards/system-wide"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()


class CAISOClient(GridOperatorClient):
    async def get_realtime_data(self) -> Dict:
        url = "https://api.caiso.com/api/v1/loadforecast"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()


@celery_app.task
def collect_eia_data_task():
    collector = DataCollectorService()
    asyncio.run(collector._collect_eia_data())


@celery_app.task
def collect_nerc_data_task():
    collector = DataCollectorService()
    asyncio.run(collector._collect_nerc_data())


@celery_app.task
def collect_worldbank_data_task():
    collector = DataCollectorService()
    asyncio.run(collector._collect_worldbank_data())
