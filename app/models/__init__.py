from datetime import datetime, date
from typing import Optional
from uuid import uuid4
from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class BaseModel(Base):
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EIAElectricity(BaseModel):
    __tablename__ = "eia_electricity"
    __table_args__ = {"schema": "raw_data"}
    
    date = Column(Date, nullable=False)
    region = Column(String(50), nullable=False)
    fuel_type = Column(String(50), nullable=False)
    generation_gwh = Column(Float)
    consumption_gwh = Column(Float)
    capacity_mw = Column(Float)


class NERCReliability(BaseModel):
    __tablename__ = "nerc_reliability"
    __table_args__ = {"schema": "raw_data"}
    
    date = Column(Date, nullable=False)
    region = Column(String(50), nullable=False)
    reserve_margin = Column(Float)
    peak_demand_mw = Column(Float)
    available_capacity_mw = Column(Float)
    nuclear_capacity_mw = Column(Float)


class WorldBankUrbanization(BaseModel):
    __tablename__ = "worldbank_urbanization"
    __table_args__ = {"schema": "raw_data"}
    
    year = Column(Integer, nullable=False)
    country_code = Column(String(3), nullable=False)
    urban_population_percent = Column(Float)
    total_population = Column(Integer)
    urban_population = Column(Integer)


class USElectricitySummary(BaseModel):
    __tablename__ = "us_electricity_summary"
    __table_args__ = {"schema": "processed_data"}
    
    date = Column(Date, nullable=False, unique=True)
    total_generation_gwh = Column(Float)
    nuclear_generation_gwh = Column(Float)
    nuclear_share = Column(Float)
    urban_population_percent = Column(Float)
    urban_electricity_demand_gwh = Column(Float)


class NuclearScenario(BaseModel):
    __tablename__ = "nuclear_scenarios"
    __table_args__ = {"schema": "forecasts"}
    
    scenario_name = Column(String(50), nullable=False)
    year = Column(Integer, nullable=False)
    nuclear_share = Column(Float)
    nuclear_generation_twh = Column(Float)
    microreactor_units = Column(Integer)
    microreactor_generation_twh = Column(Float)
    microreactor_share_of_nuclear = Column(Float)
    urban_demand_twh = Column(Float)
    model_version = Column(String(20), nullable=False)


class ModelPerformance(BaseModel):
    __tablename__ = "model_performance"
    __table_args__ = {"schema": "forecasts"}
    
    model_name = Column(String(100), nullable=False)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(Float)
    evaluation_date = Column(Date, nullable=False)


class MarketInsight(BaseModel):
    __tablename__ = "market_insights"
    __table_args__ = {"schema": "analytics"}
    
    insight_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    confidence_score = Column(Float)
    impact_level = Column(String(20))
    expires_at = Column(DateTime(timezone=True))


class User(BaseModel):
    __tablename__ = "users"
    
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    last_login = Column(DateTime(timezone=True))


class APIToken(BaseModel):
    __tablename__ = "api_tokens"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_name = Column(String(100), nullable=False)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    user = relationship("User")


class DataCollectionLog(BaseModel):
    __tablename__ = "data_collection_logs"
    
    source = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    records_collected = Column(Integer)
    error_message = Column(Text)
    collection_duration_seconds = Column(Float)


class APIAccessLog(BaseModel):
    __tablename__ = "api_access_logs"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer)
    response_time_ms = Column(Float)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    
    user = relationship("User")