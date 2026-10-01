# Copart Lot / Seller Domain Context

This is background context fed to Jev and Claude alongside the seller
instructions and lot notes, so both engines judge compliance with the same
domain understanding of what a lot, stage, seller code, and note action
mean. Sourced from the g2-ssm and g2-seller repos (see confidence notes
inline — some of this is high-confidence inference from code behavior
rather than verbatim documentation, since no repo defines a single
authoritative glossary).

## Seller Company vs Seller Code

A **Seller Company** (e.g. "GEICO - HOME OFFICE") is the corporate entity
that owns/insures vehicles sent to Copart. A **Seller Code** (e.g. "GEI") is
an operating branch/account under that company. Settings cascade from
company down to code. A seller's **standing instructions** — assignment
notes (`assgn_notes`), billing notes (`biln_notes`), dispatch notes
(`dspch_notes`), and title notes (`title_notes`) — are configured once at
the seller-code level (max 4 lines x 60 chars each) and pushed via a Kafka
event (`SELLER_CODE_SETTING_CHANGED`) to downstream systems, which copy
them onto each new lot at intake. They are not stored per-lot at the
source — the lot only ever holds a rendered copy.

## Standing Instructions — Real Examples Across Sellers

Standing instructions (`assgn_notes`/`biln_notes`/`dspch_notes`/
`title_notes`) are seller-specific free text, but real examples across
different sellers show recurring *shapes* worth recognizing generally, not
just matching GEICO's exact wording:

- **State Farm** (seller codes `S841`/`S859`/`SZ94`) — `assgn_notes`/
  `dspch_notes`: "ALL NON-STD TOWS MUST GET 3 QUOTES AND APPROVED BY
  MONITOR INC TRANSIT PROS" (a quote-count-before-approval rule).
  `biln_notes`: advance charges need a general-manager breakdown and
  adjuster approval for mail items. `title_notes`: "ALL LOTS TO BE
  PROCESSED TITLE DIRECT" — an unconditional Title Direct mandate, plus a
  specific mailing address for title paperwork.
- **USAA** (seller code `U004`) — `assgn_notes`: charges $5k or under are
  pre-approved and it's OK to call the owner directly (a dollar-threshold
  auto-approval + contact-permission pattern). `biln_notes`: all advance
  charges must be itemized/broken down completely. `dspch_notes`: review
  all seller notes first; OK to call owner. `title_notes`: conditional
  logic based on state and title-type ("if no TE, email adjuster"; FL
  flood = CD; salvage auto-approved only when no state guideline exists).
- **GEICO** (seller codes `GFLD`/`GVIC`) — the original working sample:
  Day 2/Day 3 escalation language, "EVERYTHING ON SALVAGE TITLE UNLESS
  STATE REQUIRES CLEAN."

**Generalizable patterns to watch for when judging any seller's
instructions**: dollar-threshold auto-approvals, explicit contact
permissions ("OK to call owner" vs. requiring written/verbal release),
title-program mandates (Title Direct vs. Title Standard, unconditional vs.
conditional), quote-count-before-approval requirements for non-standard
services, and state-dependent title/salvage branding rules. Recognizing
the *pattern type* helps judge compliance even when a seller's specific
wording differs from any example above.

## Handling Incomplete or Missing Column Structure

Seller instructions and lot notes are normally structured as a table (for
instructions: seller company code, seller code, seller name, field name,
field text; for lot notes: application type/code, sequence number, action
code, note text, user ID, workstation, record date/time). **When free text
is pasted in from a spreadsheet, it will often be incomplete**: column
headers may be missing entirely, only some columns may have been copied,
or rows may be pasted as plain unlabeled lines. When this happens:

- Do not assume a missing column means the data doesn't exist — it likely
  means it simply wasn't pasted. Do not treat absent metadata (e.g. no
  visible timestamp) as evidence of a violation.
- Infer field roles from context and position where possible (e.g. a
  4-6 character all-caps token at the start of a line is likely an action
  code; a longer free-text remainder is the note description; a
  date/time-like token is a record timestamp).
- Judge compliance from whatever content is actually present, and note
  explicitly when a judgment is limited by missing structure (e.g. "no
  timestamps were provided, so escalation timing could not be verified")
  rather than silently assuming compliance or violation.

## Lot Lifecycle / Stages

A lot moves through numeric stages (`lot_stage`) representing where the
vehicle and its paperwork are in the pipeline. No repo defines a named
enum for these — the numbers below are reconstructed with high confidence
from dozens of consistent stage-gated business rules in g2-seller:

- **Stage 10 — Assigned, pending pickup.** The seller's consignment/
  assignment has been created. Pickup address is still editable. This is
  when `assgn_notes` and the early parts of `dspch_notes` are most
  relevant (who to contact, how to arrange pickup).
- **Stage 15 — Awaiting clearance of charges before pickup.** Tied to
  statuses like "WAITING TO CLEAR CHARGES"/"AWAITING CLEAR FOR CHARGES"
  (and regional variants), and grouped with stage 10 under the same
  "clear for pickup" workflow in the source system. Confidence: inferred
  from a direct status→stage mapping (`STATUS_REDIRECT_URL_MAP` in
  g2-ssm's `ssm-client/src/app/shared/utils/constants.ts`), not a named
  enum — but well-supported. `biln_notes`/advance-charge approval
  instructions become relevant here, ahead of pickup itself.
- **Stage ~20 — Hold-for-pickup window.**
- **Stage 25 and Stage 28 — confirmed to exist, business meaning NOT
  confirmed.** Both sit somewhere between the ~20 hold-for-pickup window
  and stage 30 check-in, but neither has a distinct, isolated meaning
  anywhere in the searched source (g2-ssm). The only place either number
  appears is bundled inside two catch-all hold-program arrays
  (`SELLER HOLD PROGRAM`, `SAFEGUARD PROGRAM`) that span nearly the
  entire lot lifecycle (stages 10 through 91) — that only proves the
  stages exist, not what happens at them specifically. g2-seller (the
  repo that would likely own the authoritative lot-stage definition) was
  not available as a populated checkout when this was last researched.
  **Do not treat lots at stage 25/28 as having a well-understood set of
  "currently applicable" instructions** — when judging compliance at
  these two stages specifically, be more conservative about calling
  something "not yet applicable" vs. "applicable," and flag stage 25/28
  lots as a case where the domain context itself is incomplete, not just
  the lot's notes.
- **Stage 30 — Checked in / received at yard.** Vehicle has physically
  arrived. Vehicle-type field becomes locked (Copart's own inspection now
  takes precedence). `dspch_notes` largely resolve by this point.
- **Stage 40 — Title processing.** Copart is either awaiting the original
  title (Title Standard) or has bypassed that requirement (Title Direct,
  for sellers on that program). `title_notes` are most relevant here.
- **Stage 50 — Auction-ready / listed for sale.** Lot becomes visible to
  buyers; buyer-facing "special notes" only allowed from this stage on.
  `biln_notes` (charge approvals, ancillary services) typically become
  relevant around/after this point.
- **Stage ~90 — Post-sale / invoicing.**
- **Stage ~98/99 — Closed/archived.**

**Why this matters for compliance judgment**: an instruction in
`title_notes` that hasn't been "acted on" yet is not automatically a
violation if the lot is still at stage 10-20 — title handling isn't
expected until stage ~40. Judge compliance relative to the lot's current
stage, not as if every instruction should already be satisfied.

## Title Handling

Two transmittal paths exist:
- **Title Standard (`TSTD`)** — the traditional path: Copart must receive
  the physical original title from the seller/state and convert it into a
  "transferable" (sellable) title before the lot can close out title-wise.
  A live "Title Standard issue" = original title received but not yet
  converted to transferable.
- **Title Direct (`TDIR`)** — an expedited path (per-seller program) where
  Copart issues sale documents without waiting for the physical original
  title.

Titles also carry a clean-vs-salvage/branded distinction, which is
state-law-dependent (valid title types differ per U.S. state), and may
require a lien check before legal transfer is possible. Some sellers have
highly specific title procedures (e.g. a documented "unrecovered theft"
salvage-branding procedure) — when a seller's `title_notes` references
something like "everything on salvage title unless state requires clean,"
judge the lot's title-related notes against that literally, using the
lot's yard/state context if present in the notes.

## Release Issues / Clear-for-Pickup (CFR)

When Copart can't yet release a vehicle for pickup, the blocker is tracked
as a structured **release issue** with a category and reason code. Known
reason codes (subtask codes), confirmed from source:

| Code | Meaning |
|---|---|
| `OWPIP` | Owner needs to remove personal items from vehicle |
| `SLOCN` | Seller/owner contact needed |
| `VNPUL` | Vehicle not at pickup location |
| `AWQAP` | Awaiting quote approval |
| `WRRLR` | Owner written release required |
| `VRRLR` | Verbal release required — owner/seller must verbally authorize release before Copart can hand off the vehicle |
| `OWREV` | Owner is retaining the vehicle |
| `LNGBR` | Language barrier |
| `MRINR` | More information required from pickup location |
| `NTOBQ` | Need to obtain quotes |
| `PLRFP` | Pickup location requesting future pickup (2+ business days out) |
| `VHNTA` | Vehicle not accessible |

Categories: `CHRGS` (charges/advance-charge approval), `DOCS` (documents
needed), `INFO` (information needed from a person). Status values include
`CLSD` (closed/resolved), and likely an "awaiting CS review" and
"cancelled" state.

**Escalation**: no confirmed automated rule in either repo ties a specific
day count to "must email seller support." The clearest day-based construct
found is a "Lots Over 60 Days" dashboard bucket (a general staleness flag,
not proven to be a hard escalation trigger) and a per-seller configurable
grace-period window specific to Title Direct issue suppression. Seller
`assgn_notes`/`dspch_notes` that reference "Day 2" / "Day 3" escalation
thresholds should be treated as **that seller's own stated policy**, to be
checked against timestamps in the lot notes — not as a system-enforced
rule Copart validates automatically elsewhere.

## Lot Note Action Codes

Lot notes include both free text and short auto-generated "action codes"
stamped by the system when certain events occur. An earlier pass through
g2-ssm/g2-seller source only confirmed a handful of these (`TLAD`, `AUAD`,
`CLLR`, `TDIR`). Since then, a real export of ~16,000 lot-note rows
(`jevnotes.csv`, one sample lot history) was cross-referenced: because each
note's own free-text description usually explains what its code means,
~180 additional codes now have **confirmed** (not guessed) plain-English
meanings. These are maintained in `action_codes.py`
(`ACTION_CODE_MEANINGS`), grouped by theme:

- **Pickup / release workflow** — `A299`, `A500`–`A551`, `CL01`, `CLLR`,
  `CB01`–`CB19`, `CRGC`/`CRGN`, `DSP2`–`DSP8`, `PIK1`, `PUHR`, `PUNC`,
  `PUTC`, `SCPD`, `UNCL`, `XMHD`, yard/sublot codes (`CYR4`, `CYRD`,
  `SBLA`–`SBLE`, `ROWA`/`ROWC`), `LCCH`/`LCNL`/`LCRD`. Notably `A544`/
  `A545`/`A546` are release-issue opened/updated/closed (the structured
  CFR blocker described above gets its own free-text note trail via these
  codes), and `CB14` is specifically "verbal release required."
- **Charges / billing** — `ACDN`/`ACDY` (advance charge docs), `ACLO`/
  `DOVL` (over-limit approved/denied), `CKUS`/`PCAD` (payment method),
  `SLPA`/`SLRB`/`SLRM` (seller billing), `WOAP`/`WOFC`/`WBWO`/`SVCA`-family
  (service orders).
- **Title handling** — odometer codes (`ODBC`/`ODBS`/`ODBT`/`ODM3`/`ODM4`/
  `ODMR`/`ODMS`/`ODMT`), `SVGC`/`SVGT`/`SXMT` (salvage), `TAPP`, `TDAA`/
  `TDAB` (confirmed: Title-Direct eligible/not-eligible, with reason),
  `TDRL`, `TO2T`/`TSSW` (assignment type switches), `TTL3`/`TTL9`, `TTLI`–
  `TTLW` (title number/state/type/VIN-verification lifecycle).
- **Assignment / seller integration (XML/EDI feeds)** — `XM01` (generic
  seller-system field-change feed), `XM20`, `XM71`, `XMLA`/`XMLB`
  (assignment-generation timestamps), `EXM4` (created via assignment
  portal), `WEBA` (entered via seller web portal), `CARC` (internal
  tracking number), `AUAD`/`TLAD`/`LTAD` (adjuster contact changes),
  `DPVN` (duplicate VIN flag).
- **Vehicle inspection / condition** — `AS08`–`AS48` (type/model/color/
  damage/ACV/repair-cost/trim fields), `MP04`/`MP12`/`MP13`/`MP25`
  (inspection-photo obstructions), `CPKY`/`CRKY`/`QOK1` (keys), `CHKF`
  (yard check-in), `MONG`/`MONS` (window sticker), `LI01`/`LI04` (seller
  portal image/document upload).
- **Seller hold / owner communication** — `LTH0`–`LTHT`, `SAFN`/`SAFR`
  (seller-hold reason, e.g. fire investigation), `CP01`–`CP32` (owner
  self-service portal answers — OK-to-text, ready-for-pickup, keys
  location, accessibility).

Only codes seen 5+ times in the sample export are included, to avoid
enshrining one-off codes as common vocabulary — treat the list as
representative, not exhaustive. **For any code not in this glossary**, fall
back to the surrounding free-text description in the note line itself
(most lines carry a human-readable description alongside the bare code) —
do not guess a meaning for an unlisted code.

## What "Compliance" Should Mean Here

Neither repo contains a rules engine or validation logic that checks lot
notes against seller standing instructions — that judgment is evidently
meant to be made by a human (or, in this POC, an LLM). There is no
ground-truth definition of "compliant" to reverse-engineer. A reasonable
working definition: **every actionable instruction in the seller's
standing instructions has a corresponding action/note in the lot's history
by the point in the lot's lifecycle (stage) where that instruction becomes
relevant, and no contradicting or unresolved note remains open past that
point.** Instructions that reference conditions not yet reached (e.g. a
Day 3 escalation threshold on a lot that's only one day old) should be
judged as "not yet applicable," not as violations.
