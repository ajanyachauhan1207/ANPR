import re
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "vehicles.db"

STATES = {
    "AN": "Andaman & Nicobar", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh",
    "AS": "Assam", "BR": "Bihar", "CG": "Chhattisgarh", "CH": "Chandigarh",
    "DD": "Daman & Diu", "DL": "Delhi", "GA": "Goa", "GJ": "Gujarat",
    "HP": "Himachal Pradesh", "HR": "Haryana", "JH": "Jharkhand",
    "JK": "Jammu & Kashmir", "KA": "Karnataka", "KL": "Kerala", "LA": "Ladakh",
    "LD": "Lakshadweep", "MH": "Maharashtra", "ML": "Meghalaya", "MN": "Manipur",
    "MP": "Madhya Pradesh", "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha",
    "OR": "Odisha", "PB": "Punjab", "PY": "Puducherry", "RJ": "Rajasthan",
    "SK": "Sikkim", "TN": "Tamil Nadu", "TR": "Tripura", "TS": "Telangana",
    "UK": "Uttarakhand", "UP": "Uttar Pradesh", "WB": "West Bengal",
}

FIELDS = ["plate", "owner", "vehicle", "color", "reg_year",
          "insurance_until", "status"]

# Made-up sample data for demo purposes only
DEMO = [
    ("UP80AB1234", "Aarav Mehta", "Maruti Swift", "White", "2021", "2027-03-14", "Active"),
    ("DL8CAF5030", "Priya Nair", "Hyundai Creta", "Black", "2022", "2025-11-02", "Active"),
    ("KA01MN4567", "Rohan Verma", "Honda City", "Silver", "2019", "2027-08-30", "Active"),
    ("HR26DK8337", "Sneha Kapoor", "Toyota Fortuner", "Grey", "2020", "2027-01-19", "Flagged"),
]


def clean(plate):
    return re.sub(r"[^A-Z0-9]", "", str(plate).upper())


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS vehicles (
            plate TEXT PRIMARY KEY, owner TEXT, vehicle TEXT, color TEXT,
            reg_year TEXT, insurance_until TEXT, status TEXT DEFAULT 'Active')""")
        if c.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 0:
            c.executemany("INSERT INTO vehicles VALUES (?,?,?,?,?,?,?)", DEMO)


def lookup(plate):
    plate = clean(plate)
    info = {"plate": plate, "state": STATES.get(plate[:2], "Unknown"), "found": False}
    row, match = None, "exact"
    with conn() as c:
        row = c.execute("SELECT * FROM vehicles WHERE plate=?", (plate,)).fetchone()
        if row is None:                       # try a one-character-off match
            close = [r for r in c.execute("SELECT * FROM vehicles")
                     if len(r["plate"]) == len(plate)
                     and sum(a != b for a, b in zip(r["plate"], plate)) == 1]
            if len(close) == 1:
                row, match = close[0], "probable"
    if row is not None:
        d = dict(row)
        d["registered_plate"] = d.pop("plate")
        info.update(d)
        info["found"] = True
        info["match"] = match
    return info


def list_vehicles():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM vehicles ORDER BY plate")]


def add_vehicle(plate, d):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO vehicles VALUES (?,?,?,?,?,?,?)", (
            plate, d.get("owner", ""), d.get("vehicle", ""), d.get("color", ""),
            d.get("reg_year", ""), d.get("insurance_until", ""),
            d.get("status", "Active") or "Active"))


def delete_vehicle(plate):
    with conn() as c:
        c.execute("DELETE FROM vehicles WHERE plate=?", (clean(plate),))