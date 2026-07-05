from fastapi import FastAPI
from routes.auth import router as user_router
app = FastAPI()
app.include_router(user_router)