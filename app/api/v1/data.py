from fastapi import APIRouter

data_router = APIRouter()

@data_router.get("/electricity")
async def get_electricity_data():
    return {"message": "Electricity data endpoint"}

@data_router.get("/eia/raw")
async def get_eia_raw_data():
    return {"message": "EIA raw data endpoint"}

@data_router.get("/nerc/raw")
async def get_nerc_raw_data():
    return {"message": "NERC raw data endpoint"}
