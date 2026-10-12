import re
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, model_validator

PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class EntityType(str, Enum):
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    PARTNERSHIP = "partnership"
    LLP = "llp"
    OPC = "opc"
    PRIVATE_LIMITED = "private_limited"
    PUBLIC_LIMITED = "public_limited"
    HUF = "huf"
    FOREIGN_ENTITY = "foreign_entity"


# PAN 4th character is a legally-fixed entity-type code assigned by the Income
# Tax Department: C=Company, P=Individual, F=Firm/LLP, H=HUF, etc. A sole
# proprietorship uses the proprietor's personal PAN, so its 4th char is P.
_PAN_ENTITY_CODE_BY_TYPE: dict[EntityType, str] = {
    EntityType.SOLE_PROPRIETORSHIP: "P",
    EntityType.PARTNERSHIP: "F",
    EntityType.LLP: "F",
    EntityType.OPC: "C",
    EntityType.PRIVATE_LIMITED: "C",
    EntityType.PUBLIC_LIMITED: "C",
    EntityType.HUF: "H",
}
_PAN_CODE_LABELS: dict[str, str] = {
    "C": "Company",
    "P": "Individual",
    "F": "Firm / LLP",
    "H": "HUF",
    "A": "AOP",
    "T": "Trust",
    "B": "BOI",
    "L": "Local Authority",
    "J": "Artificial Juridical Person",
    "G": "Government",
}


class VendorIntake(BaseModel):
    vendor_id: str
    name: str
    entity_type: EntityType
    contract_value: Decimal
    has_physical_premises: bool

    pan: Optional[str] = None
    incorporation_jurisdiction: Optional[str] = None
    # Optional secondary identifiers — if supplied, we automate the matching
    # tile via eKYC. If left blank, the tile stays analyst-driven.
    cin: Optional[str] = None               # L17110MH1973PLC019786 — unlocks MCA auto-check
    udyam_number: Optional[str] = None      # UDYAM-XX-00-0000000  — unlocks MSME auto-check
    key_persons: list[str] = []  # Directors / promoters / proprietors to also screen through OpenSanctions.

    @model_validator(mode="after")
    def pan_required_unless_foreign_entity(self) -> "VendorIntake":
        """
        Every Indian entity type needs a real PAN — it's the identifier
        that disambiguates this vendor from same-named entities in
        sanctions/adverse-media results. A foreign entity has no Indian
        PAN to give, so it must be left blank rather than fabricated.
        """
        if self.entity_type == EntityType.FOREIGN_ENTITY:
            if self.pan is not None:
                raise ValueError(
                    "A foreign entity has no Indian PAN — leave 'pan' unset."
                )
        else:
            if self.pan is None or not PAN_PATTERN.match(self.pan):
                raise ValueError(
                    f"'{self.pan}' is not a valid PAN (expected format: AAAAA9999A)"
                )
            expected_code = _PAN_ENTITY_CODE_BY_TYPE[self.entity_type]
            actual_code = self.pan[3]
            if actual_code != expected_code:
                actual_label = _PAN_CODE_LABELS.get(actual_code, "Unknown")
                raise ValueError(
                    f"PAN 4th character '{actual_code}' ({actual_label}) does not match "
                    f"declared entity_type '{self.entity_type.value}' "
                    f"(expected '{expected_code}'). This usually means the PAN was typed "
                    f"wrong or doesn't belong to the declared entity."
                )
        return self
