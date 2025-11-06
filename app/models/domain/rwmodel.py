import datetime

from pydantic import BaseModel, ConfigDict, field_serializer


def convert_field_to_camel_case(string: str) -> str:
    return "".join(
        word if index == 0 else word.capitalize()
        for index, word in enumerate(string.split("_"))
    )


class RWModel(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        alias_generator=convert_field_to_camel_case
    )

    @field_serializer("created_at", "updated_at", when_used="json", check_fields=False)
    def serialize_datetime(self, value: datetime.datetime) -> str:
        return value.replace(tzinfo=datetime.timezone.utc).isoformat().replace("+00:00", "Z")
