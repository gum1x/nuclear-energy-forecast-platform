from fastapi import APIRouter

admin_router = APIRouter()

@admin_router.post("/data/refresh")
async def refresh_data():
    return {"message": "Data refresh endpoint"}

@admin_router.get("/status")
async def get_system_status():
    return {"message": "System status endpoint"}
