"""ID formatters. Counters are zero-padded and IDs are immutable.
Formats required by the brief: POL, CLM, DOC, ASN, SET. The rest follow the same style."""
from generator.config import DATASET_YEAR


def customer_id(n):            return f"CUST-{n:06d}"
def policy_id(product, n):     return f"POL-{product}-{DATASET_YEAR}-{n:06d}"
def coverage_id(product, n):   return f"COV-{product}-{n:02d}"
def adjuster_id(n):            return f"ADJ-{n:03d}"
def incident_id(n):            return f"INC-{DATASET_YEAR}-{n:06d}"
def claim_id(n):               return f"CLM-{DATASET_YEAR}-{n:06d}"

# child IDs: the counter restarts at 001 for every claim
def claim_item_id(claim, n):   return f"ITM-{claim}-{n:03d}"
def document_id(claim, n):     return f"DOC-{claim}-{n:03d}"
def assignment_id(claim, n):   return f"ASN-{claim}-{n:03d}"
def assessment_id(claim, n):   return f"ASM-{claim}-{n:03d}"
def reserve_id(claim, n):      return f"RSV-{claim}-{n:03d}"
def settlement_id(claim, n):   return f"SET-{claim}-{n:03d}"
def event_id(claim, n):        return f"EVT-{claim}-{n:03d}"