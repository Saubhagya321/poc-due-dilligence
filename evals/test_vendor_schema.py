"""
Seam under test: constructing a VendorIntake through its public constructor.

Vendor data below matches the mock profiles agreed in PLAN.md section 4.
Document-field intake was removed in favour of per-check document upload
on the report screen (LlamaParse + classifier), so the missing-field
assertions that used to live here are gone.
"""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.vendor import EntityType, VendorIntake


def test_suresh_enterprises_intake_with_every_required_field_filled():
    intake = VendorIntake(
        vendor_id="vendor-a-suresh-enterprises",
        name="Suresh Enterprises",
        pan="AMMPK4657M",
        entity_type=EntityType.SOLE_PROPRIETORSHIP,
        contract_value=Decimal("250000"),
        has_physical_premises=True,
    )

    assert intake.pan == "AMMPK4657M"
    assert intake.entity_type == EntityType.SOLE_PROPRIETORSHIP


def test_foreign_entity_needs_no_pan():
    # Micron-style vendor: incorporated outside India, so there's no Indian
    # PAN to require. entity_type=FOREIGN_ENTITY is the escape hatch — the
    # old India-only EntityType enum forced every vendor into a fabricated
    # Indian PAN and entity type, even ones that plainly aren't Indian.
    intake = VendorIntake(
        vendor_id="vendor-foreign-micron",
        name="Micron Technology, Inc.",
        entity_type=EntityType.FOREIGN_ENTITY,
        contract_value=Decimal("50000000"),
        has_physical_premises=False,
        incorporation_jurisdiction="Delaware, USA",
    )

    assert intake.pan is None
    assert intake.incorporation_jurisdiction == "Delaware, USA"


def test_foreign_entity_supplying_an_indian_pan_is_rejected():
    with pytest.raises(ValidationError):
        VendorIntake(
            vendor_id="vendor-foreign-micron",
            name="Micron Technology, Inc.",
            pan="AMMPK4657M",
            entity_type=EntityType.FOREIGN_ENTITY,
            contract_value=Decimal("50000000"),
            has_physical_premises=False,
        )


def test_a_domestic_entity_without_a_pan_is_rejected():
    with pytest.raises(ValidationError):
        VendorIntake(
            vendor_id="vendor-a-suresh-enterprises",
            name="Suresh Enterprises",
            entity_type=EntityType.SOLE_PROPRIETORSHIP,
            contract_value=Decimal("250000"),
            has_physical_premises=True,
        )


def test_pan_fourth_char_mismatching_declared_entity_type_is_rejected():
    # The 4th character of a PAN is a legally-fixed entity-type code: C=Company,
    # P=Individual, F=Firm/LLP, H=HUF, etc. A vendor claiming to be a Private
    # Limited company but handing over a PAN whose 4th char is P (Individual) is
    # either a typo or a fabricated identity — either way, catch it at intake
    # instead of letting it through to the pipeline. This is free, local, and
    # a strong red flag independent of any paid NSDL/aggregator lookup.
    with pytest.raises(ValidationError, match="4th character"):
        VendorIntake(
            vendor_id="vendor-fake-pvt",
            name="Fake Industries Pvt Ltd",
            pan="AMMPK4657M",  # 4th char P = Individual, but claimed entity_type is Private Limited
            entity_type=EntityType.PRIVATE_LIMITED,
            contract_value=Decimal("1000000"),
            has_physical_premises=False,
        )


def test_pan_fourth_char_matching_declared_entity_type_passes():
    # Reliance (Public Limited) — PAN 4th char C = Company ✓
    intake = VendorIntake(
        vendor_id="vendor-reliance",
        name="Reliance Industries Limited",
        pan="AAACR5055K",
        entity_type=EntityType.PUBLIC_LIMITED,
        contract_value=Decimal("100000000"),
        has_physical_premises=True,
    )
    assert intake.pan == "AAACR5055K"


def test_llp_with_firm_pan_fourth_char_passes():
    # Micron India LLP — PAN 4th char F = Firm/LLP ✓
    intake = VendorIntake(
        vendor_id="vendor-micron-india",
        name="Micron Technology Operations India LLP",
        pan="ABJFM2468E",
        entity_type=EntityType.LLP,
        contract_value=Decimal("50000000"),
        has_physical_premises=True,
    )
    assert intake.pan == "ABJFM2468E"


def test_pan_is_required_to_disambiguate_the_vendor_from_same_named_entities():
    # This is exactly the problem we hit live: OpenSanctions and Tavily both
    # return same-named-but-unrelated entities for a common name. PAN is the
    # unique identifier that lets us confirm a match is actually this vendor.
    with pytest.raises(ValidationError):
        VendorIntake(
            vendor_id="vendor-a-suresh-enterprises",
            name="Suresh Enterprises",
            pan="not-a-real-pan",
            entity_type=EntityType.SOLE_PROPRIETORSHIP,
            contract_value=Decimal("250000"),
            has_physical_premises=True,
        )
