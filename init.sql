-- Database initialization for Nuclear Forecast Enterprise

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS raw_data;
CREATE SCHEMA IF NOT EXISTS processed_data;
CREATE SCHEMA IF NOT EXISTS forecasts;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Raw data tables
CREATE TABLE IF NOT EXISTS raw_data.eia_electricity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    region VARCHAR(50) NOT NULL,
    fuel_type VARCHAR(50) NOT NULL,
    generation_gwh DECIMAL(15,2),
    consumption_gwh DECIMAL(15,2),
    capacity_mw DECIMAL(15,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_data.nerc_reliability (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    region VARCHAR(50) NOT NULL,
    reserve_margin DECIMAL(5,2),
    peak_demand_mw DECIMAL(15,2),
    available_capacity_mw DECIMAL(15,2),
    nuclear_capacity_mw DECIMAL(15,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_data.worldbank_urbanization (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    year INTEGER NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    urban_population_percent DECIMAL(5,2),
    total_population BIGINT,
    urban_population BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Processed data tables
CREATE TABLE IF NOT EXISTS processed_data.us_electricity_summary (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    total_generation_gwh DECIMAL(15,2),
    nuclear_generation_gwh DECIMAL(15,2),
    nuclear_share DECIMAL(5,4),
    urban_population_percent DECIMAL(5,2),
    urban_electricity_demand_gwh DECIMAL(15,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(date)
);

-- Forecast tables
CREATE TABLE IF NOT EXISTS forecasts.nuclear_scenarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_name VARCHAR(50) NOT NULL,
    year INTEGER NOT NULL,
    nuclear_share DECIMAL(5,4),
    nuclear_generation_twh DECIMAL(15,2),
    microreactor_units INTEGER,
    microreactor_generation_twh DECIMAL(15,2),
    microreactor_share_of_nuclear DECIMAL(5,4),
    urban_demand_twh DECIMAL(15,2),
    model_version VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(scenario_name, year, model_version)
);

CREATE TABLE IF NOT EXISTS forecasts.model_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value DECIMAL(10,6),
    evaluation_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Analytics tables
CREATE TABLE IF NOT EXISTS analytics.market_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    insight_type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    confidence_score DECIMAL(3,2),
    impact_level VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_eia_date_region ON raw_data.eia_electricity(date, region);
CREATE INDEX IF NOT EXISTS idx_nerc_date_region ON raw_data.nerc_reliability(date, region);
CREATE INDEX IF NOT EXISTS idx_worldbank_year_country ON raw_data.worldbank_urbanization(year, country_code);
CREATE INDEX IF NOT EXISTS idx_summary_date ON processed_data.us_electricity_summary(date);
CREATE INDEX IF NOT EXISTS idx_scenarios_year_scenario ON forecasts.nuclear_scenarios(year, scenario_name);
CREATE INDEX IF NOT EXISTS idx_performance_model_date ON forecasts.model_performance(model_name, evaluation_date);

-- Create update triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_eia_updated_at BEFORE UPDATE ON raw_data.eia_electricity FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_nerc_updated_at BEFORE UPDATE ON raw_data.nerc_reliability FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_worldbank_updated_at BEFORE UPDATE ON raw_data.worldbank_urbanization FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_summary_updated_at BEFORE UPDATE ON processed_data.us_electricity_summary FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
