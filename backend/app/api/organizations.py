"""Organization API — team workspace management, invites, membership."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.organization import Organization, OrganizationMember, OrganizationInvite, OrgRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orgs", tags=["organizations"])


# ─── Schemas ─────────────────────────────────────────────────

class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrgResponse(BaseModel):
    id: str
    name: str
    role: str


class OrgDetailResponse(BaseModel):
    id: str
    name: str
    role: str
    members: list[dict]
    invites: list[dict]


class InviteCreateRequest(BaseModel):
    email: str = Field(..., max_length=255)
    role: OrgRole = OrgRole.EDITOR


class InviteResponse(BaseModel):
    id: str
    email: str
    role: str
    token: str
    created_at: datetime


# ─── Endpoints ───────────────────────────────────────────────

@router.post("/", response_model=OrgResponse, status_code=201)
def create_organization(
    data: OrgCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new organization/team workspace."""
    org = Organization(name=data.name)
    db.add(org)
    db.flush()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role=OrgRole.OWNER,
    )
    db.add(member)
    db.commit()
    db.refresh(org)

    logger.info("org_created | org=%s name=%s owner=%s", org.id, data.name, current_user.id)
    return OrgResponse(id=str(org.id), name=org.name, role="owner")


@router.get("/", response_model=List[OrgResponse])
def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all organizations the current user belongs to."""
    memberships = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == current_user.id)
        .all()
    )
    org_ids = [m.organization_id for m in memberships]
    orgs = db.query(Organization).filter(Organization.id.in_(org_ids)).all() if org_ids else []
    role_map = {m.organization_id: m.role.value for m in memberships}

    return [
        OrgResponse(id=str(o.id), name=o.name, role=role_map.get(o.id, "viewer"))
        for o in orgs
    ]


@router.get("/{org_id}", response_model=OrgDetailResponse)
def get_organization(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get organization details including members and pending invites."""
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Organization not found")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    members = (
        db.query(OrganizationMember, User)
        .join(User, OrganizationMember.user_id == User.id)
        .filter(OrganizationMember.organization_id == org_id)
        .all()
    )

    invites = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.accepted_at.is_(None),
        )
        .all()
    )

    return OrgDetailResponse(
        id=str(org.id),
        name=org.name,
        role=membership.role.value,
        members=[
            {"user_id": str(m.OrganizationMember.user_id), "email": u.email, "role": m.OrganizationMember.role.value}
            for m, u in members
        ],
        invites=[
            {"id": str(i.id), "email": i.email, "role": i.role.value, "created_at": i.created_at}
            for i in invites
        ],
    )


@router.post("/{org_id}/invites", response_model=InviteResponse, status_code=201)
def invite_member(
    org_id: uuid.UUID,
    data: InviteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Invite a user to the organization by email."""
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_([OrgRole.OWNER, OrgRole.ADMIN]),
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Only owners and admins can invite members")

    # Check if already a member
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        existing_member = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == existing_user.id,
            )
            .first()
        )
        if existing_member:
            raise HTTPException(status_code=409, detail="User is already a member")

    # Check for duplicate pending invite
    existing_invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.email == data.email,
            OrganizationInvite.accepted_at.is_(None),
        )
        .first()
    )
    if existing_invite:
        raise HTTPException(status_code=409, detail="An invite is already pending for this email")

    invite = OrganizationInvite(
        organization_id=org_id,
        email=data.email,
        role=data.role,
        created_by=current_user.id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    logger.info("org_invite_created | org=%s email=%s role=%s", org_id, data.email, data.role.value)
    return InviteResponse(
        id=str(invite.id),
        email=invite.email,
        role=invite.role.value,
        token=invite.token,
        created_at=invite.created_at,
    )


@router.post("/invites/{token}/accept", response_model=OrgResponse)
def accept_invite(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept an organization invite."""
    invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.token == token,
            OrganizationInvite.accepted_at.is_(None),
        )
        .first()
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already accepted")

    # Auto-accept if email matches, or allow token-based acceptance
    if invite.email != current_user.email:
        raise HTTPException(status_code=403, detail="This invite is for a different email address")

    # Check not already a member
    existing = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == invite.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        invite.accepted_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=409, detail="Already a member")

    member = OrganizationMember(
        organization_id=invite.organization_id,
        user_id=current_user.id,
        role=invite.role,
    )
    db.add(member)
    invite.accepted_at = datetime.utcnow()
    db.commit()

    org = db.query(Organization).filter(Organization.id == invite.organization_id).first()
    logger.info("org_invite_accepted | org=%s user=%s", org.id, current_user.id)
    return OrgResponse(id=str(org.id), name=org.name, role=invite.role.value)


@router.delete("/{org_id}/members/{user_id}", status_code=204)
def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a member from the organization (owner/admin only)."""
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role.in_([OrgRole.OWNER, OrgRole.ADMIN]),
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Only owners and admins can remove members")

    target = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    # Can't remove owner
    if target.role == OrgRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot remove the organization owner")

    # Admins can only be removed by owner
    if target.role == OrgRole.ADMIN and membership.role != OrgRole.OWNER:
        raise HTTPException(status_code=403, detail="Only the owner can remove admins")

    db.delete(target)
    db.commit()
    return None
