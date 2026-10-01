"""
Copart lot note "auto note code" glossary.

Built by cross-referencing the code column ("Auto Note Code") against its
own accompanying free-text description ("Note Text") across ~16,000 real
lot-note rows exported from a sample lot history (jevnotes.csv). Because
each code's own note text usually describes what it means, these meanings
are CONFIRMED from real examples, not guessed — unlike the codes seen in
earlier single-lot samples with no export to cross-reference (e.g. XM01,
CYR4 etc. were previously "unconfirmed"; they are now confirmed here).

Only codes appearing >=5 times in the sample are included, to avoid
enshrining one-off/rare codes as if they were common vocabulary. Meanings
are paraphrased/generalized from the most common note text for that code;
some notes vary by lot (names, dollar amounts, dates), so treat these as
"what kind of event this code represents," not an exact string match.
"""

ACTION_CODE_MEANINGS = {
    # --- Pickup / release workflow ---
    "A299": "Unattended pickup flag recorded (Y/N — whether pickup happened without anyone present)",
    "A500": "Lot selected to clear a pickup hold",
    "A501": "Lot selected/cleared to proceed for pickup",
    "A502": "Lot selected to clear for charges (charges approved to proceed)",
    "A503": "Click-to-dial call placed to a contact number",
    "A504": "Awaiting clear-for-pickup — email sent to seller",
    "A508": "VSF (vehicle storage facility) document generation requested",
    "A510": "Lot set for a future clear date",
    "A512": "User exited an outbound call screen related to arranging release",
    "A513": "Lot cleared as a cash lot",
    "A517": "Pickup location name changed",
    "A518": "Pickup location notes updated",
    "A521": "Lot charges updated (total amount changed)",
    "A522": "Communication received from seller (via stated channel, e.g. email)",
    "A523": "Click2Dial contact initiated with the pickup location",
    "A526": "Additional contact NOT made, per seller's own notes/instructions",
    "A532": "Lot auto-cleared by the system",
    "A536": "Seller responded to an email; lot's follow-up date reset",
    "A544": "Release issue added — a pickup blocker was opened (reason varies, e.g. missing info, unable to contact)",
    "A545": "Release issue updated — status change on an open pickup blocker",
    "A546": "Release issue closed — pickup blocker resolved",
    "A547": "Advance charges approved (by named approver)",
    "A550": "Seller-related release issue note",
    "A551": "Contact-for-verbal-release-required issue updated",
    "A565": "Lot charges negotiated (via seller)",
    "CL01": "Lot cleared for pickup (final clearance)",
    "CLLR": "Contact/caller phone number logged (often with a three-way call)",
    "CB01": "Automated text message sent to owner for vehicle release",
    "CB08": "Owner opened the vehicle release form",
    "CB10": "Lot auto-cleared to dispatch by owner",
    "CB14": "Release issue: verbal release required",
    "CB19": "Pickup address type updated via bot/portal",
    "CRGC": "Charges cleared for a specific amount — pickup cleared",
    "CRGN": "Pickup cleared, no charges allowed",
    "DSP2": "Trip date changed",
    "DSP3": "Driver dispatched for pickup",
    "DSP4": "Pickup trip confirmed/date set",
    "DSP5": "Pickup order details sent to a transport vendor via API",
    "DSP8": "Vehicle check-in date recorded",
    "PIK1": "Pickup completed (by named tow/driver)",
    "PUHR": "Lot released from a pickup hold",
    "PUNC": "Pickup not cleared (reason given, e.g. no answer at pickup location)",
    "PUTC": "Default 'due in' pickup time window changed",
    "RCVB": "Vehicle received by (named staff)",
    "RMDR": "Driver removed from the pickup assignment",
    "SCPD": "Pickup scheduled for a specific date/time window",
    "UNCL": "Lot uncleared for pickup and charges (previous clearance reversed)",
    "XMHD": "Lot put on pickup hold, per seller, with a stated release date",
    "GRNL": "'Greenlight' lot — moved to ready-for-dispatch",
    "LNDR": "Location name discrepancy resolved",
    "PKU1": "Pickup location street address component",
    "PKU2": "Pickup location street address component",
    "SBLA": "Sublot address recorded",
    "SBLC": "Lot pickup-verified to a sublot",
    "SBLD": "Lot dispatched to a sublot",
    "SBLE": "Sublot address details",
    "YD01": "Yard-to-yard transport requested",
    "YD03": "Yard-to-yard transport cancelled",
    "CYR4": "Sale yard changed (lot moved from one yard code to another)",
    "CYRD": "Physical yard changed",
    "ROWA": "First yard row assigned",
    "ROWC": "Yard row location changed",
    "LCCH": "Lot condition changed",
    "LCNL": "Lot cancelled",
    "LCRD": "Driver removed from pickup due to lot cancellation",
    "TRLN": "Note: lot does not include a trailer",

    # --- Charges / billing ---
    "ACDN": "Advance charge documents NOT available",
    "ACDY": "Advance charge documents available",
    "ACLO": "Advance charge over the approval limit — approved (by B2B/portal)",
    "ACVA": "ACV (actual cash value) entered",
    "CHNC": "Charges not cleared — charge approval pending or denied",
    "CKUS": "Advance charges paid via check",
    "DOVL": "Charges over limit — NOT approved",
    "NACP": "No advance charges paid",
    "PCAD": "Advance charges paid via credit card",
    "PPSD": "Positive-pay payment successful, from dispatch",
    "PPSL": "Positive-pay payment successful, from CWT (check/wire)",
    "SLPA": "Seller payment applied",
    "SLRB": "Seller billed for a charge (e.g. MVR / motor vehicle record request)",
    "SLRM": "Seller billed via bulk invoice",
    "MBDS": "Minimum bid amount entered",
    "WOAP": "A requested service order was NOT approved",
    "WOFC": "Service order quantity changed",
    "WBWO": "A seller service request/order was placed",
    "SVCA": "Additional service added to the lot",
    "SVCC": "Additional service completed",
    "SVCD": "Additional service deleted",

    # --- Title handling ---
    "ODBC": "Calculated odometer brand changed",
    "ODBS": "Statement odometer brand changed",
    "ODBT": "Title odometer brand changed",
    "ODM3": "Odometer is damaged/unreadable",
    "ODM4": "Odometer is digital and cannot be read",
    "ODMR": "Received odometer mileage changed",
    "ODMS": "Statement odometer mileage changed",
    "ODMT": "Title odometer mileage changed",
    "SVGC": "Salvage type changed",
    "SVGT": "Title document type selected on the web transmittal (e.g. 'Other Title Doc')",
    "SXMT": "Salvage transmittal printed on the web",
    "TAPP": "Title approval — sale title document sent",
    "TDAA": "Lot flagged ELIGIBLE for Title Direct (reason given, e.g. title didn't come from seller system)",
    "TDAB": "Lot flagged NOT ELIGIBLE for Title Direct (reason given)",
    "TDIR": "Title Direct transmittal action occurred (e.g. salvage transmittal received)",
    "TDRL": "Lot removed from hold and enrolled in Title Direct",
    "TLSL": "Seller billed for a title/duplicate-title application",
    "TO2T": "Assignment switched from Standard to Title Only",
    "TOCR": "Title-only assignment created",
    "TOTL": "Original title date entered",
    "TPP1": "Title-processing-program document received",
    "TPP2": "Title-processing-program comment logged",
    "TPP3": "Title-processing-program additional document received",
    "TPRN": "Document uploaded via transmittal (e.g. title transmittal paperwork)",
    "TSSW": "Assignment switched from Title Only to Standard",
    "TTAA": "Certificate/title number received from the state",
    "TTEM": "Total-loss email notification sent",
    "TTL3": "Title rejected (reason given, e.g. state error)",
    "TTL9": "Pass-through title — no state title processing required",
    "TTLI": "Title number and state originally entered",
    "TTLM": "Title submitted to DMV when the bundle closed",
    "TTLN": "Original title type recorded",
    "TTLO": "Sale title type added",
    "TTLP": "Original title type changed",
    "TTLV": "Awaiting VIN verification",
    "TTLW": "VIN was verified",
    "TTPN": "Title portal received the assignment for Title Express",

    # --- Assignment / seller integration (XML/EDI feeds, adjuster contacts) ---
    "AF09": "License plate state changed",
    "AF11": "License plate number changed",
    "AF14": "Pickup phone number changed",
    "AF18": "Pickup date changed",
    "ASLN": "Seller name selected during title processing",
    "AUAD": "Auction contact adjuster changed",
    "AUCA": "Lot removed from a scheduled auction",
    "ASSG": "Lot assigned to a specific auction date",
    "CARC": "Car count / internal lot tracking number created",
    "CON1": "Tow schedule changed via automated contract-change checker",
    "CON3": "Title schedule changed via automated contract-change checker",
    "CONC": "Contract changed via automated contract-change checker",
    "DPVN": "Duplicate VIN flag — same VIN found on another lot",
    "EXM4": "Lot created via the assignment portal system (APS/APS2)",
    "LTAD": "Title contact adjuster changed",
    "TLAD": "Title contact adjuster changed",
    "STPN": "STP (straight-through-processing) automated intake completed",
    "WEBA": "Assignment entered via the web/internet portal by a seller user",
    "XM01": "Generic XML-integration auto-note — seller's system fed a field change (e.g. lot year, insured/claimant name)",
    "XM20": "XML change: adjuster contact info updated",
    "XM71": "XML change: yard changed by seller",
    "XMLA": "XML assignment generated (timestamp)",
    "XMLB": "XML assignment record generated (assignment date stamped from seller feed)",

    # --- Vehicle inspection / condition ---
    "ABAG": "Airbags deployed (flag)",
    "AS08": "Vehicle type changed",
    "AS10": "Vehicle model changed",
    "AS13": "Vehicle color changed",
    "AS14": "Damage code changed",
    "AS15": "ACV (actual cash value) changed",
    "AS16": "Repair cost changed",
    "AS36": "'Has keys' flag changed",
    "AS43": "Primary damage code changed",
    "AS44": "Secondary damage code changed",
    "AS47": "Receiver-captured vehicle type recorded",
    "AS48": "Vehicle trim changed",
    "CHKF": "Check-in at yard recorded (often with GPS coordinates)",
    "CPKY": "Keys-available flag captured",
    "CRKY": "Resident/owner-has-keys confirmed",
    "ENGC": "Engine-changed flag set",
    "HHB0": "Handheld billing completed",
    "HHI0": "Handheld receiving process completed",
    "MP04": "Missing VIN plate noted",
    "MP12": "Inspection photo obstruction: cannot open hood",
    "MP13": "Inspection photo obstruction: cannot open passenger door",
    "MP25": "Inspection photo obstruction: cannot open driver door",
    "NNPI": "No NPPI (personal info) found in the vehicle",
    "NPIO": "NPPI (personal info) found and stored in office",
    "QOK1": "Quantity of keys recorded",
    "RCAD": "Run condition changed/added",
    "RCCH": "Run condition changed",
    "TMSC": "Transmission-changed flag set",
    "MONG": "Window sticker (Monroney label) generation initiated",
    "MONS": "Window sticker (Monroney label) generated successfully",
    "LI01": "Lot image uploaded from the G2 seller portal",
    "LI04": "Lot document uploaded from the G2 seller portal",

    # --- Seller hold / owner communication ---
    "LTH0": "Seller hold document emailed",
    "LTH1": "Lot placed on seller hold",
    "LTH3": "Seller authorization acknowledged",
    "LTH7": "Seller notes submitted via web",
    "LTH8": "Seller hold released (by named staff)",
    "LTHS": "Seller hold released",
    "LTHT": "Seller hold assigned (requester and phone recorded)",
    "SAFN": "Seller hold program confirmation number assigned",
    "SAFR": "Seller hold reason recorded (e.g. fire investigation)",
    "LOGR": "Lender notified via log notification",
    "CP01": "Customer/owner self-service answer: OK to text owner",
    "CP21": "Customer/owner self-service answer: vehicle ready for pickup",
    "CP25": "Customer/owner self-service answer: keys with vehicle",
    "CP27": "Customer/owner self-service answer: tires/roll condition",
    "CP29": "Customer/owner self-service answer: vehicle accessibility for flatbed pickup",
    "CP32": "Customer/owner self-service: follow-up needed, vehicle not accessible",
    "DAME": "Automatic work-order closure",
    "PSTE": "Lot marked as a pure-sale trial lot",
}


def annotate_known_codes(text):
    """Scan free text for any known 4-char action code (word-boundary match)
    and return a sorted, deduped list of (code, meaning) tuples found.
    Codes not in ACTION_CODE_MEANINGS are silently skipped — we only surface
    confirmed meanings, never guess.
    """
    import re

    found = {}
    for code in ACTION_CODE_MEANINGS:
        if re.search(rf"\b{re.escape(code)}\b", text):
            found[code] = ACTION_CODE_MEANINGS[code]
    return sorted(found.items())


def format_code_glossary(text):
    """Build a short glossary block for any known codes detected in `text`,
    or an empty string if none matched."""
    hits = annotate_known_codes(text)
    if not hits:
        return ""
    lines = [f"- {code}: {meaning}" for code, meaning in hits]
    return "DETECTED ACTION CODE MEANINGS (confirmed from historical note data):\n" + "\n".join(lines)
