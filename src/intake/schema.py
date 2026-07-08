from pydantic import BaseModel, Field


class BusinessProfile(BaseModel):
    business_name: str = ""
    industry: str = ""
    revenue_range: str = ""
    team_size: str = ""
    location: str = ""
    pain_points: str = ""
    goals: str = ""
    phone: str = ""
    intake_completed: bool = False

    def is_empty(self) -> bool:
        return not any([
            self.business_name, self.industry, self.revenue_range,
            self.team_size, self.location, self.pain_points, self.goals,
        ])

    def completion_percentage(self) -> int:
        fields = [self.business_name, self.industry, self.revenue_range,
                  self.team_size, self.location, self.pain_points, self.goals]
        filled = sum(1 for f in fields if f)
        return int((filled / len(fields)) * 100)

    def next_empty_field(self) -> str | None:
        labels = {
            "business_name": "nama usaha",
            "industry": "bidang usaha",
            "revenue_range": "omzet",
            "team_size": "jumlah tim",
            "location": "lokasi usaha",
            "pain_points": "kendala yang dihadapi",
            "goals": "tujuan bisnis",
        }
        for field, label in labels.items():
            if not getattr(self, field):
                return label
        return None
