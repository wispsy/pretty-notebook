"""Validate browser forms and store them in the local inbox."""

from expose_api import RedirectResponse
from native_requests import ApplicationRequest as Request

import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from api.forms import save_submission
from views import home


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_address: str = Field(min_length=1, max_length=254)
    email_message: str = Field(min_length=1, max_length=5000)

    @field_validator("email_address")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("email_message")
    @classmethod
    def nonblank_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter a message")
        return value


@dataclass(frozen=True)
class FormDefinition:
    schema: type[BaseModel]
    template: str
    success_path: str
    error_message: str


FORMS = {
    "contact": FormDefinition(
        ContactFields,
        "home/contact.html",
        "/contact?sent=1",
        "Enter a valid email address and a message of up to 5000 characters.",
    ),
}


async def submit_form(request: Request, form_name: str):
    definition = FORMS.get(form_name)
    if definition is None:
        return home.templates.TemplateResponse(
            request,
            "shared/404.html",
            {**await home.get_template_content(request, page_title="Page not found"), "unavailable_content": form_name},
            status=404,
        )

    try:
        fields = definition.schema.model_validate(dict(await request.form()))
    except ValidationError:
        content = await home.get_template_content(request, page_title="Contact")
        content["form_error"] = definition.error_message
        return home.templates.TemplateResponse(
            request, definition.template, content, status=422
        )

    await save_submission(form_name, fields.model_dump())
    return RedirectResponse(request.scope.get("root_path", "") + definition.success_path, status=303)
