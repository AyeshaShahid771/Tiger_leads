# Team Members Endpoints

This document describes the team-members (members) endpoints implemented in `src/app/api/endpoints/profile.py`.

Base path: `/profile`

Auth & Authorization
- All endpoints require `Authorization: Bearer <TOKEN>` and use the `get_current_user` dependency.
- Only main account holders (not sub-users) may invite or remove team members. The code uses `get_effective_user_id()` and `is_main_account()` to enforce this.
- Invite and removal actions are subject to subscription seat limits.

Endpoints
---------

1) POST `/invite-team-member`
- Purpose: Invite a user by email to join the main account as a team member.
- Auth: Required. Only main account holders.
- Request body (InviteTeamMemberRequest):
  - `email` (string): recipient email address.
- Behavior summary:
  - Validates inviter is main account and has an active subscription with available seats.
  - Prevents inviting the main user's own email or users already part of another team.
  - Creates a `UserInvitation` record with `status: pending` and an `invitation_token`.
  - Sends invitation email via `send_team_invitation_email`.
- Success response (200):

```json
{
  "message": "Invitation sent successfully",
  "invited_email": "invitee@example.com",
  "invitation_token": "<token>"
}
```

- Errors:
  - 403 when called by sub-user or plan doesn't allow team members.
  - 400 when seats are exhausted, inviting self, or invitation already pending/accepted.
  - 500 when email sending fails (invitation rolled back).

Example curl:

```bash
curl -X POST -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"email":"invitee@example.com"}' \
  https://<API_HOST>/profile/invite-team-member
```


2) GET `/team-members`
- Purpose: List the main account info, active team members (sub-users), and pending invitations.
- Auth: Required (any user in the team can call; `get_effective_user_id()` finds main account).
- Response (200) structure (`TeamMembersListResponse`):
  - `main_account`: object with `id`, `email`, `status`, `joined_at`, `is_main_account`.
  - `team_members`: array of `TeamMemberResponse` objects. Each item represents either an active sub-user (`status: active`, `joined_at` set) or a pending invitation (`status: pending`, `joined_at: null`). Invitation entries use invitation ID in the `id` field.
  - `seats_used`: integer
  - `max_seats`: integer
  - `available_seats`: integer

Example response (200):

```json
{
  "main_account": {
    "id": 5,
    "email": "owner@example.com",
    "status": "active",
    "joined_at": "2025-01-10T12:00:00Z",
    "is_main_account": true
  },
  "team_members": [
    { "id": 6, "email": "sub1@example.com", "status": "active", "joined_at": "2025-02-01T09:00:00Z", "is_main_account": false },
    { "id": 42, "email": "invitee@example.com", "status": "pending", "joined_at": null, "is_main_account": false }
  ],
  "seats_used": 2,
  "max_seats": 5,
  "available_seats": 3
}
```

Notes:
- The `id` for pending invitations is the `UserInvitation.id` (not a user id).
- `seats_used` is read from `Subscriber.seats_used` when available, otherwise derived.

Example curl:

```bash
curl -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/profile/team-members
```


3) DELETE `/team-members/{member_id}`
- Purpose: Remove an active team member (sub-user) or revoke a pending invitation.
- Auth: Required. Only main account holders may call.
- Path param: `member_id` (int) — either a `UserInvitation.id` (for pending invites) or a `User.id` (for sub-users).
- Behavior summary:
  - If `member_id` matches a pending invitation for the inviter, sets `invitation.status = 'revoked'` and decrements `Subscriber.seats_used`.
  - If `member_id` matches a sub-user with `parent_user_id == current_user.id`, deletes that sub-user record and decrements `Subscriber.seats_used`.
- Success responses (200):
  - For revoked invitation:

```json
{ "message": "Invitation revoked successfully", "email": "invitee@example.com" }
```

  - For removed team member:

```json
{ "message": "Team member removed successfully", "email": "sub1@example.com" }
```

- Errors:
  - 403 if caller is not a main account holder.
  - 404 if neither a matching invitation nor a sub-user is found.
  - 400 if attempt to remove yourself.

Example curl (revoke invitation or remove member):

```bash
curl -X DELETE -H "Authorization: Bearer <TOKEN>" https://<API_HOST>/profile/team-members/42
```

Implementation notes
--------------------
- Seat counting and enforcement rely on `Subscriber` and `Subscription` models.
- Invitation tokens are generated with `secrets.token_urlsafe(32)` and stored in `UserInvitation.invitation_token`.
- Invitation sending uses `send_team_invitation_email()`; if sending fails the invitation record is removed and seats count is restored.

Related files
- Endpoint: `src/app/api/endpoints/profile.py`
- Schemas: `src/app/schemas/user.py` (InviteTeamMemberRequest/Response, TeamMemberResponse, TeamMembersListResponse)
- Models: `src/app/models/user.py` (UserInvitation, User, Subscriber, Subscription)

Next steps
----------
- I can also add example responses for error cases (403/400/404) and include the exact Pydantic schema shapes. Want me to add those now?
