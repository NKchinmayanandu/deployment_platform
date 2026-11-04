from pydantic import BaseModel 

class EnvironmentResponse(BaseModel):
    environment: dict[str,str]

class EnvironmentUpdate(BaseModel):
    variables: dict[str, str]