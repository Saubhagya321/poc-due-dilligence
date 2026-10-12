"""
eKYC Now / Message Central KYB sync endpoints.

Scope — sync endpoints only (consent / redirect flows skipped on purpose):
  POST /kyb/cin           CIN verification                 (MCA tile)
  POST /kyb/gstin         GSTIN verification               (GST tile)
  POST /kyb/pan-to-gstin  reverse PAN -> GSTIN list        (GST tile)
  POST /kyb/udyam         Udyam verification               (MSME/Udyam tile)
  POST /pan/sync-verify   PAN existence + name match       (PAN tile upgrade)

Auth — all five endpoints need BOTH custom headers on every request:
  api_key:     Bearer <API_KEY>     (the string "Bearer " is part of the value)
  customer_id: <CUSTOMER_ID>        (from Message Central console Settings)

Inputs are passed as HEADERS, not JSON bodies. Each endpoint has its own
input-header name — see each function below.

Response envelope — CIN / GSTIN / PAN-to-GSTIN / PAN sync-verify are
double-wrapped (api_data.api_data). Udyam is single-wrapped (api_data).
_call() auto-detects by looking at the inner dict's shape.

Failures nest unpredictably — the outer api_status can say "SUCCESS" even
when the inner response_code is 400. Only trust the deepest payload's
`valid: true` / `status: "SUCCESS"` / `status: "VALID"` field.
"""
import json
import urllib.error
import urllib.request

EKYC_BASE_URL = "https://ekyc.messagecentral.com/ekycbusiness/api/v1"


class EkycError(RuntimeError):
    """Network or non-2xx response, or envelope the parser couldn't understand.
    Caller surfaces as a technical-failure EvidenceRecord so the UI goes amber
    rather than crashing the whole screening."""


class EkycInvalidInput(ValueError):
    """200 OK but the inner payload says the identifier (CIN / GSTIN / PAN /
    Udyam) didn't validate. Not a technical failure — the vendor supplied a
    bad identifier."""


def _unwrap(envelope: dict) -> dict:
    """
    Returns the deepest api_data dict.
    - Udyam:          envelope -> api_data                 (one level)
    - everything else: envelope -> api_data -> api_data   (two levels)
    Also raises EkycInvalidInput when the inner response_code is 400.
    """
    if not isinstance(envelope, dict):
        raise EkycError(f"Envelope wasn't a dict: {envelope!r}")

    outer = envelope.get("api_data")
    if not isinstance(outer, dict):
        raise EkycError(f"api_data missing or not a dict: {envelope!r}")

    inner_code = outer.get("response_code")
    if inner_code == 400:
        err = outer.get("error_data") or {}
        raise EkycInvalidInput(
            f"{err.get('code', 'invalid')}: {outer.get('error_message', 'validation failed')}"
        )

    # Second-level unwrap for the double-nested endpoints. Udyam skips this
    # because its payload sits directly under outer.
    maybe_inner = outer.get("api_data")
    if isinstance(maybe_inner, dict):
        # Double-nested. Check its inner response_code too, since the shape
        # repeats and a 400 can live either level.
        if maybe_inner.get("response_code") == 400:
            err = maybe_inner.get("error_data") or {}
            raise EkycInvalidInput(
                f"{err.get('code', 'invalid')}: {maybe_inner.get('error_message', 'validation failed')}"
            )
        inner_inner = maybe_inner.get("api_data")
        if isinstance(inner_inner, dict):
            return inner_inner
        return maybe_inner

    return outer  # single-nested (Udyam)


def _call(path: str, api_key: str, customer_id: str, input_headers: dict) -> dict:
    if not api_key or not customer_id:
        raise EkycError("EKYC_API or EKYC_CUSTOMER_ID not configured in .env")

    req = urllib.request.Request(f"{EKYC_BASE_URL}{path}", method="POST")
    # Bearer prefix goes inside the api_key header value — unusual but
    # that's what Message Central enforces.
    req.add_header("api_key", f"Bearer {api_key}")
    req.add_header("customer_id", customer_id)
    req.add_header("Accept", "application/json")
    for k, v in input_headers.items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            envelope = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:400]
        # 401s come back shaped like {"detail": "Missing API key in Header"}
        # — surface the detail message plainly so the fix is obvious.
        try:
            detail = json.loads(body_text).get("detail", body_text)
        except Exception:
            detail = body_text
        raise EkycError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise EkycError(f"Network error: {exc}") from exc

    return _unwrap(envelope)


# --- CIN (MCA tile) ----------------------------------------------------------

def verify_cin(cin: str, api_key: str, customer_id: str) -> dict:
    """
    Returns the inner api_data dict. Expected keys (per docs sample):
      status ("VALID" when found), cin, company_name, cin_status
      ("ACTIVE" / "STRIKE OFF" / "UNDER LIQUIDATION" / "DISSOLVED" / "AMALGAMATED"),
      incorporation_date, registration_number, email, incorporation_country,
      director_details[] = [{din, name, designation, address, dob}, ...]
    """
    return _call("/kyb/cin", api_key, customer_id, {"cin_number": cin.upper()})


# --- GSTIN (GST tile) --------------------------------------------------------

def verify_gstin(gstin: str, api_key: str, customer_id: str) -> dict:
    """
    Returns the inner api_data dict. Expected keys (per docs sample):
      valid (bool), message ("GSTIN Exists"), GSTIN, legal_name_of_business,
      trade_name_of_business, constitution_of_business, taxpayer_type,
      gst_in_status ("Active" / "Cancelled" / "Suspended" / ...),
      date_of_registration, last_update_date, center_jurisdiction,
      state_jurisdiction, nature_of_business_activities (list of strings),
      principal_place_address (string),
      principal_place_split_address (object with building_name, street,
        location, district, state, city, flat_number, pincode, latitude,
        longitude),
      additional_address_array ([{address, split_address}])
    """
    return _call("/kyb/gstin", api_key, customer_id, {"gstin": gstin.upper()})


def fetch_gstin_with_pan(pan: str, api_key: str, customer_id: str) -> dict:
    """
    Returns the inner api_data dict. Expected keys (per docs sample):
      status ("SUCCESS" when found),
      pan,
      gstin_list = [{gstin, status, state}, ...]  one entry per state the PAN
                                                  is registered in
    """
    return _call(
        "/kyb/pan-to-gstin", api_key, customer_id, {"number": pan.upper()}
    )


# --- Udyam (MSME/Udyam tile) -------------------------------------------------

def verify_udyam(udyam_number: str, api_key: str, customer_id: str) -> dict:
    """
    Returns the inner api_data dict. NOTE this endpoint is single-nested
    unlike all the others. Expected keys (per docs sample):
      status ("SUCCESS" when found), udyam_number, enterprise_name, owner_name,
      gender, organization_type, major_activity, social_category,
      enterprise_type ("Micro" / "Small" / "Medium"),
      date_of_incorporation, date_of_commencement, date_of_udyam_registration,
      classification_year, classification_date, classification_history[],
      split_address (object; also carries mobile and email),
      unit_locations[],
      nic_codes[] = [{code_2, code_4, code_5, description}, ...],
      dic, msme_di, msme_dfo (nullable),
      udyam_certificate_url (signed S3 URL, ~1 day expiry)
    """
    return _call(
        "/kyb/udyam", api_key, customer_id, {"udyam_number": udyam_number.upper()}
    )


# --- PAN sync-verify (PAN tile upgrade: format -> real NSDL existence) -------

def verify_pan_sync(pan: str, api_key: str, customer_id: str) -> dict:
    """
    Returns the inner api_data dict. Expected keys (per docs sample):
      pan, type (individual / company / ...), registered_name, name_pan_card,
      valid (bool), message, pan_status ("VALID" / ...),
      aadhaar_seeding_status ("Y" / "N"), aadhaar_seeding_status_desc,
      name_match_score (optional, 0-100), name_match_result (optional),
      last_updated_at (DD/MM/YYYY), name_provided, father_name
    """
    return _call("/pan/sync-verify", api_key, customer_id, {"pan_number": pan.upper()})
