from pydantic import BaseModel


class BusinessProfileSchema(BaseModel):
    business_name: str = ""
    industry: str = ""
    revenue_range: str = ""
    team_size: str = ""
    location: str = ""
    pain_points: str = ""
    goals: str = ""
    phone: str = ""
    intake_completed: bool = False
