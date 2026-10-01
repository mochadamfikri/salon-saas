# Owner Business Decisions

Persistent Owner-approved decisions that survive session rotation.

## Phase 2
- **BD-P2-001:** StaffProfile is not auto-created; Owner/Manager explicitly creates it for an eligible active salon membership.
- **BD-P2-002:** Owner, Manager and Staff memberships may have StaffProfile; Owner/Manager may also work as stylist.
- **BD-P2-003:** No hard-delete StaffProfile workflow in P2-C; use `is_bookable=false` operationally and membership lifecycle for access.
- **BD-P2-004:** Membership with existing StaffProfile must not be hard-deleted through old delete semantics; return conflict and use suspension/lifecycle handling.
- **BD-P2-005:** Owner/Manager may update any profile; Staff may update only own `display_name`, `phone`, `bio`, `photo_url`; `is_bookable` Owner/Manager only; `membership_id` immutable.
- **BD-P2-006:** Owner/Manager may assign/unassign services; Staff read-only; no bulk assignment in P2-C.
- **BD-P2-007:** Cross-salon assignment invariant is `profile.membership.salon_id == service.salon_id == tenant.salon.id`; cross-tenant resource => 404.
- **BD-P2-008:** Owner/Manager may manage any same-tenant availability; Staff may mutate only own availability; permitted roles may read same-tenant availability.
- **BD-P2-009:** Availability overlap is `new_start < existing_end AND new_end > existing_start`; adjacency allowed; overlap => 409.
- **BD-P2-010:** Owner, Manager and Staff may create/read/update customers for operational/walk-in use.
- **BD-P2-011:** P2-E has no hard DELETE customer endpoint.
- **BD-P2-012:** Duplicate email/phone is allowed; no auto-merge or duplicate rejection solely due to same email/phone.
