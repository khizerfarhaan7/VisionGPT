from pydantic import BaseModel

class HealthCheckSchema(BaseModel):
    status: str
    environment: str
    database: str
    version: str
