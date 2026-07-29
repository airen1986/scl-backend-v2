from pydantic import BaseModel


class notificationBaseModel(BaseModel):
    notification_id: int
    from_user_email: str
    title: str
    message: str
    notification_type: str
    notification_level: str
    project_name: str | None
    model_name: str | None
    is_read: int
    is_accepted: int
    task_id: int | None
    created_at: str


class getNotificationsRequest(BaseModel):
    get_all: bool = False


class getNotificationsResponse(BaseModel):
    notifications: list[notificationBaseModel]


class markNotificationsReadRequest(BaseModel):
    notification_ids: list[int]


class acceptModelRequest(BaseModel):
    notification_id: int
    accept: bool
    model_name: str = ""
    project_name: str = ""
    create_new_copy: bool = False


class MessageResponse(BaseModel):
    message: str
