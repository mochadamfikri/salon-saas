# Agent Working Rules

This document defines strict rules for agents working on the Salon SaaS platform.

---

## NEVER

**DO NOT:**

1. **Develop directly in production**
   - Always work in development environment
   - Never access production database
   - Never use production credentials
   - Never deploy to production without approval

2. **Commit secrets**
   - No API keys in code
   - No passwords in config files
   - No tokens in repository
   - Use environment variables only

3. **Bypass failing tests**
   - Fix the test or fix the code
   - Never comment out failing tests
   - Never skip test execution

4. **Delete tests to make CI pass**
   - Tests are documentation
   - Tests prevent regressions
   - Fix the root cause

5. **Modify schema without migration**
   - All schema changes via Alembic migrations
   - Never edit database directly
   - Test migrations in development first

6. **Trust prices from frontend**
   - Backend calculates all prices
   - Frontend displays only
   - Validate all financial data server-side

7. **Hardcode tenant identifiers**
   - Use dynamic tenant resolution
   - Tenant ID from authentication context
   - Never assume single tenant

8. **Deploy when validation fails**
   - All tests must pass
   - Linting must pass
   - Build must succeed
   - CI must be green

9. **Silently change business requirements**
   - Business Owner owns requirements
   - Engineering implements requirements
   - Propose alternatives but get approval

10. **Mark task DONE without acceptance criteria passing**
    - Verify all AC before marking complete
    - Run tests
    - Verify functionality
    - Document completion

---

## ALWAYS

**DO:**

1. **Verify tenant isolation**
   - All queries scoped to tenant
   - Check authorization
   - Prevent data leakage

2. **Use migrations for schema changes**
   - Create migration file
   - Test upgrade path
   - Test rollback path
   - Document changes

3. **Write tests before marking done**
   - Unit tests for business logic
   - Integration tests for APIs
   - Verify edge cases
   - Test error handling

4. **Keep commits small and focused**
   - One logical change per commit
   - Clear commit messages
   - Reference issue/task numbers
   - Follow conventional commits

5. **Document architectural decisions**
   - Add ADR to DECISIONS.md
   - Explain reasoning
   - Note alternatives considered
   - Include trade-offs

6. **Update progress tracker**
   - Mark tasks in PROGRESS.md
   - Note blockers immediately
   - Document completion
   - Keep status current

7. **Use environment variables**
   - Never hardcode config
   - Document required variables
   - Provide .env.example
   - Keep secrets out of repository

8. **Validate input**
   - Server-side validation always
   - Client-side for UX only
   - Sanitize user input
   - Check data types and ranges

9. **Handle errors properly**
   - Try/catch around I/O
   - Return meaningful errors
   - Log appropriately
   - Never expose internals to clients

10. **Review before committing**
    - Check diff
    - Verify no debug code
    - Ensure no secrets
    - Run linting
    - Run tests

---

## Code Quality

1. **Follow language conventions**
   - Python: PEP 8
   - TypeScript: ESLint rules
   - Use formatters (Black, Prettier)

2. **Write clear variable names**
   - Descriptive over short
   - Avoid abbreviations
   - Use domain language

3. **Comment complex logic**
   - Explain WHY not WHAT
   - Document edge cases
   - Note gotchas

4. **Keep functions small**
   - Single responsibility
   - Easy to test
   - Easy to understand

---

## Testing

1. **Test pyramid**
   - Many unit tests
   - Some integration tests
   - Few end-to-end tests

2. **Test behavior not implementation**
   - Focus on inputs/outputs
   - Don't test internals
   - Make tests resilient to refactoring

3. **Test edge cases**
   - Null/empty values
   - Boundary conditions
   - Error conditions
   - Invalid input

---

## Security

1. **Validate all input**
   - Never trust client data
   - Sanitize before use
   - Check types and ranges

2. **Use parameterized queries**
   - No string concatenation in SQL
   - Prevent SQL injection
   - Use ORM properly

3. **Implement proper authorization**
   - Check permissions on every request
   - Verify tenant ownership
   - Don't rely on frontend checks

4. **Hash passwords**
   - Use bcrypt or equivalent
   - Never store plaintext
   - Use salt

5. **Secure API endpoints**
   - Require authentication
   - Rate limiting
   - CORS configuration
   - Input validation

---

## Multi-Tenant Rules

1. **Always scope queries to tenant**
   ```python
   # Bad
   booking = db.query(Booking).filter(Booking.id == booking_id).first()
   
   # Good
   booking = db.query(Booking).filter(
       Booking.id == booking_id,
       Booking.salon_id == current_user.salon_id
   ).first()
   ```

2. **Verify ownership before mutation**
   - Check tenant_id before UPDATE
   - Check tenant_id before DELETE
   - Return 404 instead of 403 (security through obscurity)

3. **Filter list endpoints**
   - All list queries auto-filtered by tenant
   - Pagination scoped to tenant
   - Counts scoped to tenant

---

## Deployment Rules

1. **Environment checklist**
   - [ ] All tests passing
   - [ ] No secrets in code
   - [ ] Migrations tested
   - [ ] Environment variables set
   - [ ] CI green
   - [ ] Documentation updated

2. **Never deploy to production directly**
   - Deploy to staging first
   - Verify in staging
   - Get approval
   - Then deploy to production

---

## Communication

1. **When blocked**
   - Document the blocker
   - Update PROGRESS.md
   - Notify immediately
   - Propose solutions

2. **When proposing changes**
   - Explain reasoning
   - Note trade-offs
   - Provide alternatives
   - Get approval before implementing

3. **When completing tasks**
   - Verify acceptance criteria
   - Run all tests
   - Update documentation
   - Commit with clear message

---

## Phase-Specific Rules

### Phase 0 (Current)

1. **DO NOT implement business logic**
   - No authentication system
   - No booking logic
   - No payment processing
   - No notification sending
   - Skeleton/placeholders OK

2. **Focus on foundation**
   - Repository structure
   - Build system
   - Testing framework
   - Database connection
   - Development environment

3. **Stop at Phase 0 completion**
   - Do not continue to Phase 1
   - Provide complete report
   - Wait for audit approval

---

## Emergency Procedures

1. **If production breaks**
   - Notify immediately
   - Rollback if possible
   - Document incident
   - Post-mortem after fix

2. **If security issue found**
   - Report immediately
   - Do not discuss publicly
   - Document privately
   - Fix ASAP

3. **If data loss risk**
   - Stop immediately
   - Backup if possible
   - Notify before proceeding
   - Document actions

---

## Summary

These rules exist to:
- Maintain code quality
- Ensure security
- Prevent data loss
- Enable collaboration
- Support maintainability

When in doubt, ask before proceeding.
