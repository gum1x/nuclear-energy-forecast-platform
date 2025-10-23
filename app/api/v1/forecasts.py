from fastapi import APIRouter

forecasts_router = APIRouter()

@forecasts_router.post("/generate")
async def generate_forecast():
    return {"message": "Generate forecast endpoint"}

@forecasts_router.get("/scenarios")
async def get_scenarios():
    return {"message": "Get scenarios endpoint"}

@forecasts_router.get("/performance")
async def get_model_performance():
    return {"message": "Model performance endpoint"}