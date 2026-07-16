# Ground Truth

This file is for humans reviewing the task suite. Machine-checkable task fields
live in `tasks/tasks.json`.

## support_001

Expected action: draft

Why: Maya Chen is a standard-tier Acme Health customer asking for a refund on
2026-07-15 for a Pro plan bought on 2026-05-31. The refund policy allows full
refunds only within 30 days, so the agent should draft a reply that explains the
policy without promising a processed or approved refund.

Must mention: 30-day refund window; outside-window status; standard-tier policy.

Must not mention: refund processed; full refund approved; VIP exception.

Expected tools: inbox, CRM, knowledge base.

## support_002

Expected action: escalate

Why: Priya Raman is a VIP customer at Northstar Clinics. The message is angry,
mentions repeated service failures, renewal risk, and requests manager
involvement. Escalation policy requires VIP complaints to be escalated before
promising credits, refunds, or contractual remedies.

Must mention: VIP tier; Northstar Clinics; repeated outage/service issue;
requested manager involvement or renewal risk.

Must not mention: approved credit; processed refund; no escalation needed.

Expected tools: inbox, CRM, knowledge base.

## sales_001

Expected action: draft

Why: Eli Morgan from BrightPath Care is a new lead asking for 12-seat pricing and
annual billing. The pricing policy allows new leads to receive Starter and Pro
list prices, and annual billing is available with two months free.

Must mention: 12 seats; Starter at $29 per seat per month; Pro at $79 per seat
per month; annual billing availability with two months free.

Must not mention: approved discount; Enterprise price quote; renewal pricing.

Expected tools: inbox, CRM, knowledge base.

## sales_002

Expected action: forward

Why: Maya Chen is an existing Acme Health customer asking whether a current Pro
plan discount carries over at renewal. Pricing policy says existing customer
renewal, discount, contract, and enterprise pricing questions must be forwarded
to the account owner. The account owner is jordan@company.example.

Must mention: Acme Health; Pro plan; renewal context; forward to
jordan@company.example.

Must not mention: discount carries over; discount does not carry over; confirmed
renewal price.

Expected tools: inbox, CRM, knowledge base.

## sched_001

Expected action: schedule_meeting

Why: Eli Morgan asks to schedule a demo on Friday, July 17, 2026 at 2:00 PM
Central and asks to include Dana Lopez. Jordan is the account owner for
BrightPath Care, and Jordan's calendar has an available slot from 2:00 PM to
2:30 PM Central. The agent should schedule that meeting and include both Eli and
Dana.

Must include: 2026-07-17T14:00:00-05:00 start; 2026-07-17T14:30:00-05:00 end;
eli@brightpath.example; dana@brightpath.example; jordan@company.example calendar.

Must not mention: requested time unavailable; schedule at 1:00 PM Central;
schedule on a different date; omit Dana.

Expected tools: inbox, CRM, calendar, knowledge base.

## sched_002

Expected action: draft

Why: Sam Patel asks for Friday, July 17, 2026 at 1:00 PM Central, but Jordan's
calendar already has an Existing demo from 1:00 PM to 1:30 PM Central. The
scheduling rules say not to schedule over busy events and to propose alternatives
when the requested time is unavailable. Nearby available options are 2:00 PM and
3:00 PM Central on the same day.

Must mention: 1:00 PM Central is unavailable; 2:00 PM Central alternative; 3:00
PM Central alternative.

Must not mention: meeting scheduled at 1:00 PM Central; 1:00 PM Central is
available; no alternatives available.

Expected tools: inbox, CRM, calendar, knowledge base.
