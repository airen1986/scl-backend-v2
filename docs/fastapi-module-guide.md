# FastAPI Module Guide

This backend organizes API features as modules under `app/routers/`. Each module gets its own folder and keeps routing, schemas, SQL, and business logic in separate files.

Use `app/routers/models` as the reference module when adding or updating API areas.

## Module Layout

Create one folder per module:

```text
app/routers/
  <module_name>/
    __init__.py
    router.py
    schemas.py
    queries.py
    methods.py
```

Example:

```text
app/routers/projects/
  __init__.py
  router.py
  schemas.py
  queries.py
  methods.py
```

## File Responsibilities

### `router.py`

`router.py` is the API entry point for the module.

Put FastAPI route definitions here:

- Create `router = APIRouter()`.
- Define endpoint paths with `@router.post(...)`.
- Declare request and response models from `schemas.py`.
- Read authenticated user data with `_get_user_from_token` when the endpoint requires login.
- Open database access with `master_connection()`.
- Call `check_module_access(...)` for routes that require module-level authorization.
- Delegate business logic to `methods.py`.
- Return schema objects or FastAPI responses.

Current pattern:

```python
from fastapi import APIRouter, Depends

from app.connection import master_connection
from app.routers.auth.methods import _get_user_from_token, check_module_access

from . import methods as project_methods
from . import schemas as project_schemas

router = APIRouter()
this_api = "/api/projects"


@router.post("/create", response_model=project_schemas.MessageResponse)
def create_project(
    request: project_schemas.ProjectCreateRequest,
    user_data: tuple = Depends(_get_user_from_token),
) -> project_schemas.MessageResponse:
    useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        project_methods.add_new_project(cursor, useremail, request.name, request.create_and_open)
    return project_schemas.MessageResponse(message="Project created successfully")
```

Keep `router.py` thin. It should coordinate request parsing, authentication, authorization, database cursor lifetime, method calls, and response construction. It should not contain SQL or complex business rules.

### `schemas.py`

`schemas.py` contains Pydantic models for request bodies and response bodies.

Put these here:

- Request models, such as `ProjectCreateRequest`.
- Response models, such as `MessageResponse`.
- Shared response items, such as `FileListItem`.
- Enums used by request or response models.

Current pattern:

```python
from enum import Enum

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class AccessLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class ShareModelRequest(BaseModel):
    model_name: str
    project_name: str
    target_user_email: str
    access_level: AccessLevel
```

Prefer explicit request and response models instead of raw dictionaries. This keeps FastAPI validation and OpenAPI documentation useful.

### `queries.py`

`queries.py` contains database queries for the module.

Put raw SQL constants here:

- `SELECT`, `INSERT`, `UPDATE`, and `DELETE` statements.
- Multi-line SQL strings when readability is better.
- Query fragments only when they are intentionally formatted by methods.

Current pattern:

```python
get_project_id = "SELECT ProjectId FROM S_Projects WHERE UserEmail=? AND ProjectName=?"

insert_new_project = """
INSERT INTO S_Projects (UserEmail, ProjectName)
VALUES (?, ?)
RETURNING ProjectId
"""
```

Use parameterized queries with `?` placeholders. Do not format user input into SQL strings. If a query must use `.format(...)`, only format controlled internal values, such as known column names.

### `methods.py`

`methods.py` contains the module's business logic.

Put these here:

- Validation rules that are specific to the feature.
- Calls to queries from `queries.py`.
- Data shaping for responses.
- Permission checks that depend on data state.
- File operations and service calls related to the module.
- Helper functions shared by endpoints in the same module.

Current pattern:

```python
from fastapi import HTTPException

from . import queries as project_queries


def add_new_project(cursor, user_email: str, project_name: str, open_after_create: bool):
    if project_name is None or project_name.strip() == "":
        raise HTTPException(status_code=400, detail="Project name cannot be empty")

    project_id = _get_project_id(cursor, user_email, project_name)
    if project_id:
        raise HTTPException(status_code=400, detail="Project name already exists")

    row = cursor.execute(project_queries.insert_new_project, (user_email, project_name)).fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create project")
```

Raise `HTTPException` from methods when a request cannot be completed. This keeps route handlers simple and keeps error behavior close to the business rule that caused it.

## Adding A New Module

1. Create the module folder under `app/routers/<module_name>/`.
2. Add `__init__.py`, `router.py`, `schemas.py`, `queries.py`, and `methods.py`.
3. Define Pydantic request and response models in `schemas.py`.
4. Add SQL constants in `queries.py`.
5. Add business logic in `methods.py`.
6. Add FastAPI endpoints in `router.py`.
7. Register the router in `app/main.py`.

Register the router with the same import and include pattern used by existing modules:

```python
from app.routers.<module_name>.router import router as <module_name>_router

app.include_router(<module_name>_router, prefix="/api/<module-name>", tags=["<module-name>"])
```

Use hyphenated API prefixes when the public path needs them, such as `/api/sql-client`. Use the Python module name for imports, such as `sql_client`.

## Endpoint Flow

Most endpoints should follow this flow:

```text
HTTP request
  -> router.py validates request body with schemas.py
  -> router.py loads authenticated user
  -> router.py opens master_connection()
  -> router.py checks module access when required
  -> methods.py runs feature logic
  -> methods.py executes SQL from queries.py
  -> router.py returns a schemas.py response model
```

## Naming Conventions

- Use descriptive module names: `projects`, `models`, `tasks`, `notifications`.
- Name request models by action, such as `ProjectCreateRequest` or `RenameProjectRequest`.
- Name response models by returned data, such as `CurrentProjectResponse` or `ModelListResponse`.
- Use `MessageResponse` for simple success messages.
- Alias imports in `router.py` to avoid ambiguity:

```python
from . import methods as model_methods
from . import schemas as model_schemas
```

## Authentication And Access

Use `_get_user_from_token` for authenticated endpoints:

```python
user_data: tuple = Depends(_get_user_from_token)
```

Current code expects:

```python
useremail, _display_name, role_name = user_data
```

Call `check_module_access(cursor, role_name, this_api)` for endpoints that require module-level access control. Some read-only endpoints may omit this if they only need authentication, matching the existing modules.

## Database Access

Use `master_connection()` in `router.py` for the master application database:

```python
with master_connection() as cursor:
    result = module_methods.some_method(cursor, ...)
```

For model-specific SQLite files, use helper functions from `app.connection`, such as `sql_connection(...)`, from inside `methods.py`.

Keep transaction boundaries clear by doing related database work inside the same `with master_connection()` block.

## Multipart Uploads And Downloads

For file uploads, define form fields in `router.py` with `Form(...)` and the file with `File(...)`:

```python
from fastapi import File, Form, UploadFile


@router.post("/upload", response_model=model_schemas.MessageResponse)
def upload_model(
    model_name: str = Form(...),
    project_name: str = Form(...),
    upload_file: UploadFile = File(...),
):
    ...
```

For downloads, return `FileResponse` from the method or route and set `response_class=FileResponse` on the route.

## Checklist

Before opening a pull request or merging a new module, confirm:

- The module is registered in `app/main.py`.
- All endpoints have request and response models where applicable.
- SQL lives in `queries.py`, not in `router.py`.
- Business rules live in `methods.py`, not in `router.py`.
- User input is passed to SQL through parameters, not string formatting.
- Authenticated endpoints use `_get_user_from_token`.
- Protected endpoints call `check_module_access(...)`.
- Errors use `HTTPException` with clear status codes and messages.
- Imports follow the existing local style.
- Ruff passes with `uv run ruff check`.
