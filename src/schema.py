from typing import Optional, Literal, List
from pydantic import BaseModel, Field

SensitiveKind = Literal[
    # credentials & tokens
    "api_key_unknown","aws_access_key_id","aws_secret_access_key","gcp_service_account_key",
    "private_key_block","password","jwt","oauth_token","bearer_token",
    # financial info 
    "credit_card","iban","bank_account","routing_number","swift_bic",
    # contact info 
    "email","phone_number","address","ip_address","national_id","ssn","sin",
    # misc
    "url_with_token","license_plate"
]

class Finding(BaseModel):
    kind: SensitiveKind
    start: int = Field(ge=0, description="char start index in the input text")
    end: int = Field(ge=0, description="char end index (exclusive)")
    value_preview: str = Field(description="short preview or masked form")
    confidence: float = Field(ge=0, le=1)
    reason: str
    rule: Optional[str] = Field(default=None, description="regex/rule if applicable")

class Findings(BaseModel):
    findings: List[Finding]
