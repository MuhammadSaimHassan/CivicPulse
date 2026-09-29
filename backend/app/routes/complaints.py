"""Complaint endpoints. HTTP only: parse, validate, serialise, status codes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.deps import ComplaintServiceDep, enforce_rate_limit
from app.domain import Category, Priority, Status
from app.repositories.complaint_repository import ComplaintFilter
from app.schemas import ComplaintCreate, ComplaintCreated, ComplaintOut, ComplaintPage, ErrorBody, StatusUpdate

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ComplaintCreated,
    dependencies=[Depends(enforce_rate_limit)],
    responses={400: {"model": ErrorBody}, 429: {"model": ErrorBody}},
)
def create_complaint(payload: ComplaintCreate, service: ComplaintServiceDep) -> ComplaintCreated:
    return service.create(payload)


@router.get("/{complaint_id}", response_model=ComplaintOut, responses={404: {"model": ErrorBody}})
def get_complaint(complaint_id: uuid.UUID, service: ComplaintServiceDep) -> ComplaintOut:
    return service.get(complaint_id)


@router.get("", response_model=ComplaintPage, responses={400: {"model": ErrorBody}})
def list_complaints(
    service: ComplaintServiceDep,
    category: Category | None = None,
    priority: Priority | None = None,
    status_: Annotated[Status | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ComplaintPage:
    flt = ComplaintFilter(category=category, priority=priority, status=status_)
    return service.list(flt, page=page, page_size=page_size)


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintOut,
    responses={404: {"model": ErrorBody}, 409: {"model": ErrorBody}},
)
def change_status(complaint_id: uuid.UUID, body: StatusUpdate, service: ComplaintServiceDep) -> ComplaintOut:
    return service.change_status(complaint_id, body.status)
