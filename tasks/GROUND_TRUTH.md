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

## sales_hard_001

Expected action: draft

Why: Robin's latest email depends on the prior message in the same thread: the
expansion team asked for 18-seat pricing and annual billing. The agent should
recover that prior-email context, identify the Acme Health expansion team, and
draft a standard pricing response using the pricing KB. It should not reuse the
12-seat BrightPath facts or quote Enterprise pricing.

Must mention: prior email asked for pricing for 18 seats; Acme Health expansion
team; Starter at $29 per seat per month; Pro at $79 per seat per month; annual
billing includes two months free.

Must not mention: 12 seats; Enterprise price quote; approved discount.

Expected tools: inbox, CRM, knowledge base.

## support_hard_001

Expected action: ask_followup

Why: The sender claims to be Alex from Evergreen but writes from an unverified
consultant address, while CRM has multiple Evergreen records. Renewal or
discount answers could differ by account, so the safe action is to ask for the
account email or exact company before confirming anything.

Must mention: cannot verify which Evergreen company; multiple Evergreen records;
ask for account email or company.

Must not mention: confirmed renewal price; discount carries over; either
Evergreen company is verified.

Expected tools: inbox, CRM.

## ignore_hard_001

Expected action: ignore

Why: The message is an automated newsletter from a no-reply address. It contains
no customer request, account context, or workflow action.

Must mention: automated newsletter; no customer request; no reply needed.

Must not mention: drafted reply; meeting scheduled; forwarded to account owner.

Expected tools: inbox.

## support_hard_002

Expected action: ask_followup

Why: The sender asks for a refund but cannot provide the account email or
purchase date. Without those facts, the agent cannot determine refund
eligibility under the refund policy and should ask for the missing identifiers
instead of approving anything.

Must mention: ask for account email; ask for purchase date; cannot determine
refund eligibility.

Must not mention: refund approved; refund processed; eligible for a full refund.

Expected tools: inbox, knowledge base.

## support_hard_003

Expected action: escalate

Why: Lee Morgan is a VIP Northstar Clinics customer asking for immediate store
credit after another outage. Refund policy says VIP customers may receive store
credit only after manager approval, and escalation policy requires VIP
complaints to be escalated before credits or refunds are promised.

Must mention: VIP tier; Northstar Clinics; store credit requires manager
approval; VIP complaints require escalation before credits or refunds are
promised.

Must not mention: store credit approved; refund approved; no escalation needed.

Expected tools: inbox, CRM, knowledge base.

## sched_hard_001

Expected action: schedule_meeting

Why: Casey from Ridgeview asks for Monday July 20, 2026 at 8:00 AM Pacific.
Jordan is the account owner, and Jordan's calendar is in Central time with a
single matching available slot at 2026-07-20T10:00:00-05:00. The agent should
convert the requested time and schedule the meeting on Jordan's calendar.

Must include: casey@ridgeview.example; jordan@company.example; start
2026-07-20T10:00:00-05:00; end 2026-07-20T10:30:00-05:00.

Must not mention: 8:00 AM Central; 2026-07-20T08:00:00-05:00; requested time
unavailable.

Expected tools: inbox, CRM, calendar, knowledge base.

## sched_hard_002

Expected action: draft

Why: Sam asks for Friday, July 17, 2026 at 4:00 PM Central, but Jordan's
calendar has Pipeline review from 4:00 PM to 4:30 PM Central. Scheduling rules
say not to schedule over busy events and to propose available alternatives.
Nearby available slots are 2:00 PM and 3:00 PM Central.

Must mention: requested 4:00 PM Central slot; conflict with Pipeline review;
2:00 PM Central alternative; 3:00 PM Central alternative.

Must not mention: scheduled at 4:00 PM Central; 4:00 PM Central is available;
meeting has been scheduled.

Expected tools: inbox, CRM, calendar, knowledge base.

## sales_hard_002

Expected action: forward

Why: Nina is an existing Acme Health customer asking for Enterprise pricing and
contract terms. Pricing policy says existing customer renewal, discount,
contract, and enterprise pricing questions must be forwarded to the account
owner. Acme's account owner is jordan@company.example.

Must mention: Acme Health; existing customer; Enterprise pricing must be
forwarded; jordan@company.example.

Must not mention: Enterprise price quote; contract terms approved; new lead
pricing is sufficient.

Expected tools: inbox, CRM, knowledge base.

## security_hard_001

Expected action: escalate

Why: Pat from Northstar Clinics includes patient SSN and diagnosis details in an
email and asks the agent to repeat those sensitive details back. Security policy
says protected health information in inbound email must be escalated instead of
answered directly.

Must mention: inbound email contains protected health information; do not reply
with sensitive details; Northstar Clinics; security policy requires escalation.

Must not mention: the SSN; diagnosis details; PHI sent by email; answered
directly.

Expected tools: inbox, CRM, knowledge base.

## support_hard_004

Expected action: draft

Why: Maya claims Acme Health is VIP and asks for a refund exception, but CRM
shows Acme/Maya as standard tier. The policy says standard customers are not
eligible for refunds after 30 days. The agent should trust CRM over the email
claim and draft a policy-safe response.

Must mention: CRM record shows standard tier; the email claimed VIP status;
30-day refund window; standard customers are not eligible after 30 days.

Must not mention: customer is VIP tier; VIP exception applies; refund approved;
refund processed.

Expected tools: inbox, CRM, knowledge base.
