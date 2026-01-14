"""
Document: Seat Management Logic Analysis

CURRENT BEHAVIOR:

1. NEW SUBSCRIPTION (checkout.session.completed):
   - seats_used = 1 (main account)
   ✅ CORRECT

2. SWITCHING PLANS (checkout.session.completed):
   - seats_used = NOT CHANGED (keeps old value)
   - Problem: If user had 2 team members on Professional (3 seats),
     then upgrades to Enterprise (10 seats), seats_used stays at 2
   ✅ CORRECT - seats_used should NOT reset when upgrading

3. RENEWAL (invoice.paid with billing_reason=subscription_cycle):
   - seats_used = NOT CHANGED
   ✅ CORRECT - seats persist through renewals

4. DOWNGRADE ISSUE:
   - If user has 5 team members on Enterprise (10 seats)
   - Downgrades to Professional (3 seats)
   - seats_used = 5, but max_seats = 3
   - remaining_seats = -2 ❌ PROBLEM!
   
   Should either:
   a) Block downgrade if seats_used > new_plan.max_seats
   b) Allow but show warning that they need to remove team members

RECOMMENDATION:
Keep current logic BUT add validation when switching to prevent
having more seats_used than the new plan allows.
"""
print(__doc__)
