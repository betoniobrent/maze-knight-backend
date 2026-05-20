from pydantic import BaseModel


class RegisterSchema(BaseModel):
    username: str
    password: str


class LoginSchema(BaseModel):
    username: str
    password: str


def to_camel(string: str) -> str:
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class ScoreSchema(BaseModel):
    username: str
    level_id: int
    clear_time: float
    sanity_left: int
    pulses_used: int

    model_config = {
        "alias_generator": to_camel,
        "populate_by_name": True,
    }
class AdminUserSchema(BaseModel):
    username: str
    password: str
    is_admin: int = 0