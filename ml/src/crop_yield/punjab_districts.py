"""Punjab, Pakistan district reference coordinates and boundary consolidation.

Used by:
- `ml/src/crop_yield/weather_pull.py` to query Open-Meteo historical archive.
- `ml/src/crop_yield/features.py` for spatial encodings and irrigation defaults.
- Backend API `/api/v1/yield/options` for user district pickers.

Notes on Coordinates and Boundaries (per ADR-0013):
1. Coordinates represent District Administrative Headquarters. For geographically
   expansive districts (e.g., Dera Ghazi Khan, Rahim Yar Khan, Bahawalpur), these
   should be verified against cropland centroids (GADM / geoBoundaries)
   during final spatial analysis.
2. Boundary consolidation maps 2022 newly created districts (Murree, Talagang,
   Taunsa, Kot Addu, Wazirabad) back to parent districts.
3. Chiniot was created in Feb 2009 (split from Jhang); for 2007-08 and 2008-09
   historical tables, Chiniot was recorded under Jhang.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DistrictInfo:
    name: str
    lat: float
    lon: float
    region_context: str
    is_primarily_barani: bool


# 36 Administrative Districts of Punjab, Pakistan (Consolidated historical boundaries)
PUNJAB_DISTRICTS: Dict[str, DistrictInfo] = {
    "Attock": DistrictInfo("Attock", 33.7660, 72.3609, "Northern Barani (Rainfed)", True),
    "Bahawalnagar": DistrictInfo("Bahawalnagar", 29.9987, 73.2536, "Southern Irrigated", False),
    "Bahawalpur": DistrictInfo("Bahawalpur", 29.3956, 71.6836, "Southern Irrigated", False),
    "Bhakkar": DistrictInfo("Bhakkar", 31.6253, 71.0657, "Thal Desert / Irrigated", False),
    "Chakwal": DistrictInfo("Chakwal", 32.9328, 72.8630, "Northern Barani (Rainfed)", True),
    "Chiniot": DistrictInfo("Chiniot", 31.7200, 72.9789, "Central Irrigated (Merged with Jhang 2007-09)", False),
    "Dera Ghazi Khan": DistrictInfo("Dera Ghazi Khan", 30.0489, 70.6455, "South-Western Mixed (Includes Taunsa)", False),
    "Faisalabad": DistrictInfo("Faisalabad", 31.4504, 73.1350, "Central Mixed Irrigated", False),
    "Gujranwala": DistrictInfo("Gujranwala", 32.1877, 74.1945, "Rice-Wheat Belt (Includes Wazirabad)", False),
    "Gujrat": DistrictInfo("Gujrat", 32.5742, 74.0754, "Northern Mixed", False),
    "Hafizabad": DistrictInfo("Hafizabad", 32.0679, 73.6854, "Rice-Wheat Belt", False),
    "Jhang": DistrictInfo("Jhang", 31.2781, 72.3317, "Central Irrigated (Includes Chiniot 2007-09)", False),
    "Jhelum": DistrictInfo("Jhelum", 32.9425, 73.7257, "Northern Barani (Rainfed)", True),
    "Kasur": DistrictInfo("Kasur", 31.1179, 74.4461, "Central Mixed Irrigated", False),
    "Khanewal": DistrictInfo("Khanewal", 30.3017, 71.9321, "Cotton-Wheat Belt", False),
    "Khushab": DistrictInfo("Khushab", 32.2955, 72.3502, "Thal Mixed", False),
    "Lahore": DistrictInfo("Lahore", 31.5204, 74.3587, "Central Mixed Irrigated", False),
    "Layyah": DistrictInfo("Layyah", 30.9613, 70.9416, "Thal Mixed", False),
    "Lodhran": DistrictInfo("Lodhran", 29.5405, 71.6336, "Cotton-Wheat Belt", False),
    "Mandi Bahauddin": DistrictInfo("Mandi Bahauddin", 32.5870, 73.4912, "Rice-Wheat Belt", False),
    "Mianwali": DistrictInfo("Mianwali", 32.5839, 71.5370, "Thal Mixed", False),
    "Multan": DistrictInfo("Multan", 30.1575, 71.5249, "Cotton-Wheat Belt", False),
    "Muzaffargarh": DistrictInfo("Muzaffargarh", 30.0744, 71.1847, "South-Western Mixed (Includes Kot Addu)", False),
    "Nankana Sahib": DistrictInfo("Nankana Sahib", 31.4492, 73.7124, "Central Mixed Irrigated", False),
    "Narowal": DistrictInfo("Narowal", 32.1000, 74.8730, "Rice-Wheat Belt", False),
    "Okara": DistrictInfo("Okara", 30.8081, 73.4458, "Central Mixed Irrigated", False),
    "Pakpattan": DistrictInfo("Pakpattan", 30.3410, 73.3866, "Central Mixed Irrigated", False),
    "Rahim Yar Khan": DistrictInfo("Rahim Yar Khan", 28.4212, 70.2989, "Cotton-Wheat Belt", False),
    "Rajanpur": DistrictInfo("Rajanpur", 29.1035, 70.3250, "South-Western Mixed", False),
    "Rawalpindi": DistrictInfo("Rawalpindi", 33.5651, 73.0169, "Northern Barani (Includes Murree)", True),
    "Sahiwal": DistrictInfo("Sahiwal", 30.6682, 73.1114, "Central Mixed Irrigated", False),
    "Sargodha": DistrictInfo("Sargodha", 32.0836, 72.6711, "Central Mixed Irrigated", False),
    "Sheikhupura": DistrictInfo("Sheikhupura", 31.7131, 73.9783, "Rice-Wheat Belt", False),
    "Sialkot": DistrictInfo("Sialkot", 32.4945, 74.5229, "Rice-Wheat Belt", False),
    "Toba Tek Singh": DistrictInfo("Toba Tek Singh", 30.9743, 72.4827, "Central Mixed Irrigated", False),
    "Vehari": DistrictInfo("Vehari", 30.0419, 72.3489, "Cotton-Wheat Belt", False),
}

# Alias mapping for historical variations and 2022 new district splits (ADR-0013)
DISTRICT_ALIASES: Dict[str, str] = {
    # 2022 New District splits mapped to parents
    "murree": "Rawalpindi",
    "muree": "Rawalpindi",
    "talagang": "Chakwal",
    "talagand": "Chakwal",
    "taunsa": "Dera Ghazi Khan",
    "kot addo": "Muzaffargarh",
    "kot addu": "Muzaffargarh",
    "wazirabad": "Gujranwala",
    # Abbreviations & spelling variations in CRS tables
    "d.g. khan": "Dera Ghazi Khan",
    "dg khan": "Dera Ghazi Khan",
    "d g khan": "Dera Ghazi Khan",
    "d.g.khan": "Dera Ghazi Khan",
    "r.y. khan": "Rahim Yar Khan",
    "ry khan": "Rahim Yar Khan",
    "r y khan": "Rahim Yar Khan",
    "r.y.khan": "Rahim Yar Khan",
    "t.t. singh": "Toba Tek Singh",
    "tt singh": "Toba Tek Singh",
    "t t singh": "Toba Tek Singh",
    "t.t.singh": "Toba Tek Singh",
    "m.b. din": "Mandi Bahauddin",
    "mb din": "Mandi Bahauddin",
    "m b din": "Mandi Bahauddin",
    "m.b.din": "Mandi Bahauddin",
    "nankana": "Nankana Sahib",
    # Spellings used in the Punjab Agriculture Statistics PDFs
    "jehlum": "Jhelum",
    "muzzafargargh": "Muzaffargarh",
    "muzafargarh": "Muzaffargarh",
    "rajan pur": "Rajanpur",
    "rajanpur": "Rajanpur",
    "chiniot": "Chiniot",
    "mandi baha-ud-din": "Mandi Bahauddin",
    "mandi bahauddin": "Mandi Bahauddin",
}


def normalize_district_name(name: str) -> str:
    """Normalize district names and map split/sub-districts back to historical parents."""
    cleaned = name.strip()
    key = cleaned.lower()
    if key in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[key]
    for official in PUNJAB_DISTRICTS:
        if official.lower() == key:
            return official
    return cleaned


def get_all_districts() -> List[str]:
    """Return alphabetical list of the 36 consolidated district names."""
    return sorted(list(PUNJAB_DISTRICTS.keys()))


def get_district_info(name: str) -> DistrictInfo:
    """Retrieve DistrictInfo for a given district name with alias resolution."""
    normalized = normalize_district_name(name)
    if normalized not in PUNJAB_DISTRICTS:
        raise ValueError(
            f"Unknown Punjab district: '{name}'. Available districts: {', '.join(get_all_districts())}"
        )
    return PUNJAB_DISTRICTS[normalized]


def get_district_soil(name: str) -> Dict[str, float]:
    """Retrieve representative soil attributes for a district (ISRIC/Punjab Soil Survey)."""
    info = get_district_info(name)
    zone = info.region_context

    if info.is_primarily_barani:
        return {
            "soil_ph": 8.0,
            "soil_soc_g_kg": 4.5,
            "soil_nitrogen_g_kg": 0.45,
            "soil_clay_pct": 16.0,
            "soil_sand_pct": 55.0,
            "soil_silt_pct": 29.0,
            "soil_cec_cmol_kg": 11.0,
            "soil_bulk_density_g_cm3": 1.50,
            "soil_wv10_pct": 18.0,
            "soil_wv33_pct": 12.0,
            "soil_wv1500_pct": 6.0,
            "soil_awc_pct": 6.0,
        }
    elif "Rice-Wheat" in zone:
        return {
            "soil_ph": 8.2,
            "soil_soc_g_kg": 6.5,
            "soil_nitrogen_g_kg": 0.60,
            "soil_clay_pct": 32.0,
            "soil_sand_pct": 28.0,
            "soil_silt_pct": 40.0,
            "soil_cec_cmol_kg": 18.5,
            "soil_bulk_density_g_cm3": 1.40,
            "soil_wv10_pct": 28.0,
            "soil_wv33_pct": 22.0,
            "soil_wv1500_pct": 12.0,
            "soil_awc_pct": 10.0,
        }
    elif "Cotton-Wheat" in zone or "Southern" in zone:
        return {
            "soil_ph": 8.35,
            "soil_soc_g_kg": 4.8,
            "soil_nitrogen_g_kg": 0.48,
            "soil_clay_pct": 22.0,
            "soil_sand_pct": 45.0,
            "soil_silt_pct": 33.0,
            "soil_cec_cmol_kg": 14.0,
            "soil_bulk_density_g_cm3": 1.48,
            "soil_wv10_pct": 21.0,
            "soil_wv33_pct": 15.0,
            "soil_wv1500_pct": 8.0,
            "soil_awc_pct": 7.0,
        }
    elif "Thal" in zone or "South-Western" in zone:
        return {
            "soil_ph": 8.25,
            "soil_soc_g_kg": 3.8,
            "soil_nitrogen_g_kg": 0.38,
            "soil_clay_pct": 18.0,
            "soil_sand_pct": 58.0,
            "soil_silt_pct": 24.0,
            "soil_cec_cmol_kg": 12.0,
            "soil_bulk_density_g_cm3": 1.52,
            "soil_wv10_pct": 17.0,
            "soil_wv33_pct": 11.0,
            "soil_wv1500_pct": 5.5,
            "soil_awc_pct": 5.5,
        }
    else:  # Central Mixed / Default Irrigated Plains
        return {
            "soil_ph": 8.1,
            "soil_soc_g_kg": 6.0,
            "soil_nitrogen_g_kg": 0.55,
            "soil_clay_pct": 24.0,
            "soil_sand_pct": 36.0,
            "soil_silt_pct": 40.0,
            "soil_cec_cmol_kg": 15.0,
            "soil_bulk_density_g_cm3": 1.42,
            "soil_wv10_pct": 24.0,
            "soil_wv33_pct": 18.0,
            "soil_wv1500_pct": 9.5,
            "soil_awc_pct": 8.5,
        }



if __name__ == "__main__":
    districts = get_all_districts()
    print(f"Total Punjab districts registered: {len(districts)}")
    assert len(districts) == 36, f"Expected 36 districts, found {len(districts)}"
    
    # Test boundary consolidation aliases
    test_cases = [
        ("Murree", "Rawalpindi"),
        ("Talagang", "Chakwal"),
        ("Taunsa", "Dera Ghazi Khan"),
        ("Kot Addu", "Muzaffargarh"),
        ("Wazirabad", "Gujranwala"),
        ("d.g. khan", "Dera Ghazi Khan"),
        ("ry khan", "Rahim Yar Khan"),
        ("lahore", "Lahore"),
    ]
    for alias, expected in test_cases:
        res = normalize_district_name(alias)
        assert res == expected, f"Failed: {alias} -> {res} (expected {expected})"
    print("All district mappings and alias tests passed successfully.")
