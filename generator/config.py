"""Central configuration. Every number that shapes the data lives here, so that
the starter dataset and the full dataset come from the same generator."""
from datetime import date

# ---- reproducibility -------------------------------------------------------
SEED = 20261022                 # fixed seed required by the brief
AS_OF_DATE = date(2026, 10, 22)  # the dataset's "today"; statuses are derived from it
DATASET_YEAR = 2026             # year part of the IDs (POL-<product>-2026-..., CLM-2026-...)

# ---- scale (all parameterised; CLI flags override these) -------------------
DEFAULT_POLICIES = 2000
DEFAULT_CLAIMS = 1000           # used by the transaction step later
CUSTOMERS_PER_POLICY = 0.7      # 2000 policies -> 1400 customers (about 1.43 policies each)
POLICIES_PER_ADJUSTER = 50      # 2000 policies -> 40 adjusters
MIN_ADJUSTERS = 10

# ---- domain lists ----------------------------------------------------------
PRODUCTS = ["AUTO", "HLTH", "PROP", "TRVL", "LIAB"]          # also the 5 claim types
PRODUCT_WEIGHTS = {"AUTO": 30, "HLTH": 25, "PROP": 20, "TRVL": 15, "LIAB": 10}

INCIDENT_TYPES = {
    "AUTO": ["COLLISION", "THEFT", "VANDALISM"],
    "HLTH": ["HOSPITALIZATION", "SURGERY", "OUTPATIENT"],
    "PROP": ["FIRE", "FLOOD", "BURGLARY"],
    "TRVL": ["TRIP_CANCELLATION", "BAGGAGE_LOSS", "MEDICAL_ABROAD"],
    "LIAB": ["THIRD_PARTY_INJURY", "THIRD_PARTY_DAMAGE"],
}

CITIES = ["Kolkata", "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
          "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Bhubaneswar", "Patna"]
REGIONS = ["North", "South", "East", "West", "Central"]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karan", "Sourav", "Rahul",
               "Amit", "Vikram", "Sanjay", "Debashis", "Anil", "Manish", "Suresh", "Ravi",
               "Ananya", "Diya", "Isha", "Priya", "Neha", "Sneha", "Pooja", "Kavya",
               "Meera", "Riya", "Anjali", "Susmita", "Shreya", "Nandini", "Lakshmi", "Tanvi"]
LAST_NAMES = ["Sharma", "Verma", "Das", "Banerjee", "Chatterjee", "Mukherjee", "Ghosh", "Sen",
              "Patel", "Shah", "Mehta", "Iyer", "Nair", "Reddy", "Rao", "Naidu",
              "Singh", "Kumar", "Gupta", "Agarwal", "Joshi", "Kulkarni", "Desai", "Mishra",
              "Pandey", "Yadav", "Bose", "Dutta", "Roy", "Khan", "Ansari", "Menon"]

# ---- customers -------------------------------------------------------------
CUSTOMER_CREATED_MIN = date(2023, 1, 1)
CUSTOMER_CREATED_MAX = date(2026, 6, 30)
CUSTOMER_AGE_MIN, CUSTOMER_AGE_MODE, CUSTOMER_AGE_MAX = 18, 38, 80   # triangular distribution
AGE_REFERENCE_DATE = date(2026, 1, 1)
KYC_VERIFIED_PROB = 0.95

# ---- policies --------------------------------------------------------------
POLICY_START_MIN = date(2025, 3, 1)
POLICY_START_MAX = date(2026, 9, 30)
POLICY_TERM_DAYS = 364          # end_date = start_date + 364 days (365 days inclusive)
CANCEL_PROB = 0.06              # customer/insurer cancellation
LAPSE_PROB = 0.05               # non-payment lapse
MIN_DAYS_BEFORE_CANCEL = 30

PREMIUM_MEDIAN = {"AUTO": 18000, "HLTH": 22000, "PROP": 15000, "TRVL": 2500, "LIAB": 30000}  # INR
PREMIUM_SIGMA = 0.45

# ---- coverage catalog (INR) ------------------------------------------------
# (product, seq, description, default_limit, default_deductible, exclusions)
# "exclusions" = incident types this coverage does NOT pay for.
COVERAGE_CATALOG = [
    ("AUTO", 1, "Own Damage (collision and vandalism)", 500000, 5000, ("THEFT",)),
    ("AUTO", 2, "Theft Cover", 800000, 10000, ("COLLISION", "VANDALISM")),
    ("AUTO", 3, "Roadside and Towing Add-on", 25000, 0, ("THEFT", "VANDALISM")),

    ("HLTH", 1, "Hospitalization Cover", 500000, 5000, ("OUTPATIENT",)),
    ("HLTH", 2, "Surgical Cover", 800000, 10000, ("OUTPATIENT", "HOSPITALIZATION")),
    ("HLTH", 3, "Outpatient (OPD) Cover", 50000, 1000, ("SURGERY", "HOSPITALIZATION")),

    ("PROP", 1, "Fire and Allied Perils", 2000000, 25000, ("FLOOD", "BURGLARY")),
    ("PROP", 2, "Flood and Natural Calamity", 1500000, 25000, ("FIRE", "BURGLARY")),
    ("PROP", 3, "Burglary and Theft", 500000, 10000, ("FIRE", "FLOOD")),

    ("TRVL", 1, "Trip Cancellation", 150000, 2000, ("BAGGAGE_LOSS", "MEDICAL_ABROAD")),
    ("TRVL", 2, "Baggage Loss", 50000, 1000, ("TRIP_CANCELLATION", "MEDICAL_ABROAD")),
    ("TRVL", 3, "Overseas Medical", 1000000, 5000, ("TRIP_CANCELLATION", "BAGGAGE_LOSS")),

    ("LIAB", 1, "Third-party Injury", 1000000, 10000, ("THIRD_PARTY_DAMAGE",)),
    ("LIAB", 2, "Third-party Property Damage", 750000, 10000, ("THIRD_PARTY_INJURY",)),
    ("LIAB", 3, "Legal Defence Cost", 200000, 0, ()),
]

# ---- policy coverage (bridge) ---------------------------------------------
EXTRA_COVERAGE_PROB = 0.60      # coverage 01 is always included; others with this probability
LIMIT_FACTORS = [(0.5, 10), (0.75, 15), (1.0, 45), (1.5, 20), (2.0, 10)]   # (factor, weight)
DEDUCTIBLE_FACTORS = [(0.5, 20), (1.0, 60), (2.0, 20)]
DEDUCTIBLE_ROUNDING = 500

# ---- adjusters -------------------------------------------------------------
AUTHORITY_TIERS = [(200000, 50), (1000000, 35), (5000000, 15)]   # (max_authority INR, weight)
SENIOR_AUTHORITY = 5000000


# ============================================================================
# STEP 5 additions: transaction tables (Incident -> Claim -> ... -> Settlement)
# ============================================================================

# ---- claim selection -------------------------------------------------------
FREQUENT_CLAIMANT_PROB = 0.04        # share of customers who claim much more often
FREQUENT_CLAIMANT_WEIGHT = 6
EXCLUDED_CLAIM_PROB = 0.03           # claim for an incident type the policy does not cover (normal rejection, rule R07)

# ---- amounts (INR) ---------------------------------------------------------
# (low ratio, high ratio, weight): claimed amount = coverage_limit * uniform(low, high)
AMOUNT_BUCKETS = [(0.05, 0.40, 55), (0.40, 0.85, 30), (0.85, 1.00, 7), (1.00, 1.50, 8)]
MIN_CLAIM_AMOUNT = 1000
CLAIM_ROUNDING = 10
MAX_CLAIM_AMOUNT = 5000000           # equals the senior adjuster authority, so someone can always handle it
ITEMS_PER_CLAIM = [(1, 30), (2, 35), (3, 25), (4, 10)]
ITEM_TYPES = {
    "AUTO": ["REPAIR", "PARTS", "TOWING"],
    "HLTH": ["HOSPITAL_BILL", "PROCEDURE", "MEDICATION"],
    "PROP": ["REPAIR", "REPLACEMENT", "CLEANUP"],
    "TRVL": ["TICKET_REFUND", "HOTEL", "REPLACEMENT"],
    "LIAB": ["LEGAL_FEE", "COMPENSATION", "REPAIR"],
}

# ---- timeline (days) -------------------------------------------------------
REPORT_DELAY_MAX = {"AUTO": 5, "HLTH": 10, "PROP": 7, "TRVL": 14, "LIAB": 10}
LATE_REPORT_PROB = 0.05
LATE_REPORT_RANGE = (15, 40)
FILING_DELAY_MAX = 3
DOCS_LATE_PROB = 0.15                # share of claims where some documents arrive after a request
DOCS_LATE_MIN_AGE = 14               # only for claims old enough that documents surely arrive before AS_OF
DOCS_RECEIVE_DELAY = (2, 10)
ASSESSMENT_START_DELAY = (1, 3)
ASSESSMENT_DURATION = (2, 10)
PAYMENT_DELAY = (3, 14)
CLOSE_DELAY = (1, 7)
REJECT_CLOSE_DELAY = (1, 5)
REASSIGN_PROB = 0.05

# ---- documents -------------------------------------------------------------
DOC_BASE = {
    "AUTO": ["CLAIM_FORM", "ID_PROOF", "REPAIR_ESTIMATE"],
    "HLTH": ["CLAIM_FORM", "ID_PROOF", "MEDICAL_REPORT", "INVOICE"],
    "PROP": ["CLAIM_FORM", "ID_PROOF", "INCIDENT_REPORT", "PHOTOS"],
    "TRVL": ["CLAIM_FORM", "ID_PROOF", "INVOICE"],
    "LIAB": ["CLAIM_FORM", "ID_PROOF", "INCIDENT_REPORT"],
}
DOC_EXTRA = {                         # extra mandatory documents for specific incident types
    ("AUTO", "THEFT"): ["POLICE_REPORT"],
    ("AUTO", "COLLISION"): ["POLICE_REPORT"],
    ("PROP", "BURGLARY"): ["POLICE_REPORT"],
    ("TRVL", "MEDICAL_ABROAD"): ["MEDICAL_REPORT"],
}
OPTIONAL_DOC_PROB = 0.30
OPTIONAL_DOC_POOL = {
    "AUTO": ["PHOTOS", "INCIDENT_REPORT"],
    "HLTH": ["INCIDENT_REPORT"],
    "PROP": ["REPAIR_ESTIMATE", "INVOICE"],
    "TRVL": ["INCIDENT_REPORT", "POLICE_REPORT"],
    "LIAB": ["POLICE_REPORT", "INVOICE", "PHOTOS"],
}

# ---- fraud indicators (points are summed; computed from data, never random) -
FRAUD_LATE_REPORT_DAYS, FRAUD_LATE_REPORT_POINTS = 14, 20      # reported more than 14 days after incident
FRAUD_NEW_POLICY_DAYS, FRAUD_NEW_POLICY_POINTS = 30, 25        # incident within 30 days of policy start
FRAUD_NEAR_LIMIT_RATIO, FRAUD_NEAR_LIMIT_POINTS = 0.90, 20     # claimed amount >= 90% of coverage limit
FRAUD_REPEAT_CLAIMS, FRAUD_REPEAT_POINTS = 3, 25               # 3+ claims by the customer in 12 months
FRAUD_WINDOW_DAYS = 365
FRAUD_REFER_THRESHOLD = 50                                      # score >= 50 -> REFER_MANUAL (R09)