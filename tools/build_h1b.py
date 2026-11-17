#!/usr/bin/env python3
"""Build h1b.json = official USCIS H-1B approvals per company, per fiscal year (FY).

Run on the Mac, about once a year (USCIS adds a year):
    python3 tools/build_h1b.py                 # downloads the 4 newest years, builds ../h1b.json
    python3 tools/build_h1b.py --report        # also prints the match report (who matched, who did not)

Source (official): USCIS H-1B Employer Data Hub, Tableau CSV export
    https://bigdataanalyticspub-sb.uscis.dhs.gov/views/H1BEmployerDataHub-Final/H1BPublic.csv?Fiscal%20Year%20%20%20=YYYY
(the field name "Fiscal Year   " has three trailing spaces; each file is ~100 MB and is deleted after use unless --keep)

Numbers per company and year:  total = sum of the 6 approval measures (same as the USCIS dashboard "Total Approvals")
                               new   = "New Employment Approval" (a NEW H-1B worker: includes F-1 students changing status)
The app uses the SAME name cleaning as norm() below (see normKey() in index.html). Keep them in sync.
"""
import argparse, csv, collections, json, os, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "h1b.json")
OVERRIDES = os.path.join(HERE, "h1b_overrides.json")
BASE = "https://bigdataanalyticspub-sb.uscis.dhs.gov/views/H1BEmployerDataHub-Final/H1BPublic.csv?Fiscal%20Year%20%20%20="
ALERTS_URL = "https://raw.githubusercontent.com/purnavasanth01/JOB-LISTENER/state/alerts.csv"
TARGETS_URL = "https://raw.githubusercontent.com/purnavasanth01/JOB-LISTENER/main/targets.json"
APPROVALS = {"New Employment Approval", "Continuation Approval", "Change with Same Employer Approval",
             "New Concurrent Approval", "Change of Employer Approval", "Amended Approval"}
NEW = "New Employment Approval"
SUFFIX = {"INC", "INCORPORATED", "LLC", "L L C", "LLP", "LP", "LTD", "LIMITED", "CORP", "CORPORATION", "CO", "COMPANY",
          "PLC", "PLLC", "PC", "NA", "GMBH", "SA", "AG", "NV", "BV", "PTE", "PVT", "PRIVATE", "HOLDINGS", "HOLDING",
          "GROUP", "USA", "US", "AMERICA", "AMERICAS", "NORTH", "INTERNATIONAL", "INTL", "GLOBAL", "TECHNOLOGIES",
          "TECHNOLOGY", "TECH", "SYSTEMS", "SERVICES", "SOLUTIONS", "SOFTWARE", "LABS", "LAB", "THE"}
MIN_TOTAL = 3          # keep the full table only for employers with at least this many approvals in 4 years


def norm(name):
    """Company name -> match key. 'Amazon.com Services LLC' -> 'AMAZON COM'. Same rules as normKey() in index.html."""
    s = (name or "").upper().replace("&", " AND ")
    s = re.sub(r"[’'`]", "", s)
    s = re.sub(r"[^A-Z0-9]+", " ", s).strip()
    words = s.split()
    while words and words[0] == "THE":
        words.pop(0)
    while words and words[-1] in SUFFIX and len(words) > 1:
        words.pop()
    return " ".join(words)


def keys_for_employer(raw):
    """'X DBA Y' -> keys for X and Y."""
    parts = re.split(r"\s+(?:DBA|D/B/A|D B A|FKA|F/K/A|AKA)\s+", raw.upper())
    return [k for k in (norm(p) for p in parts) if k]


def download(year, dest):
    url = BASE + str(year)
    print("downloading FY%d ..." % year, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)


def num(v):
    try:
        return int(float((v or "0").replace(",", "")))
    except ValueError:
        return 0


def aggregate(path, year, table):
    n = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            m = r["Measure Names"]
            if m not in APPROVALS:
                continue
            raw = (r["Employer (Petitioner) Name"] or "").strip()
            if not raw:
                continue            # USCIS hides tiny employers
            v = num(r["Measure Values"])
            if not v:
                continue
            for k in set(keys_for_employer(raw)):
                cell = table[k][year]
                cell[0] += v
                if m == NEW:
                    cell[1] += v
            n += 1
    return n


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2023,2024,2025,2026")
    ap.add_argument("--dir", default=os.path.expanduser("~/.cache/job_app_uscis"), help="where the big CSVs go (outside the repo)")
    ap.add_argument("--keep", action="store_true", help="keep the downloaded CSVs")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    years = [int(y) for y in a.years.split(",")]
    os.makedirs(a.dir, exist_ok=True)

    table = collections.defaultdict(lambda: {y: [0, 0] for y in years})
    for y in years:
        p = os.path.join(a.dir, "fy%d.csv" % y)
        if not os.path.exists(p):
            download(y, p)
        print("reading FY%d (%d MB) ..." % (y, os.path.getsize(p) >> 20), flush=True)
        aggregate(p, y, table)
        if not a.keep and os.path.exists(p) and "--keep" not in sys.argv and a.dir.endswith("job_app_uscis"):
            os.remove(p)          # 100 MB each: delete after reading (re-downloaded next year)

    # who do we need to match? companies in the app + the target list
    names = set()
    try:
        for r in csv.DictReader(fetch(ALERTS_URL).splitlines()):
            names.add(r["company"])
        for t in json.loads(fetch(TARGETS_URL))["companies"]:
            names.add(t["name"])
            names.update(t.get("aliases") or [])
    except Exception as e:                       # offline: still build the full table
        print("could not load company list:", e)
    names.discard("")
    over = json.load(open(OVERRIDES)) if os.path.exists(OVERRIDES) else {}
    over_n = {norm(k): v for k, v in over.get("map", {}).items()}
    skip_n = {norm(k) for k in over.get("never_match", [])}

    # whitespace-insensitive "starts with these whole words" index: "T MOBILE" == "TMOBILE", "MOODY S ANALYTICS" starts with "MOODYS"
    cum = collections.defaultdict(list)
    for kk in table:
        acc = ""
        for w in kk.split():
            acc += w
            cum[acc].append(kk)

    def family(prefix):
        return cum.get(norm(prefix).replace(" ", ""), [])

    def resolve_override(items):
        """items: "PREFIX" = every USCIS name starting with these whole words, "=NAME" = that exact name only,
        "-PREFIX" = leave these out."""
        got, bad = set(), set()
        for it in items:
            if it.startswith("-"):
                bad.update(family(it[1:]))
            elif it.startswith("="):
                if norm(it[1:]) in table:
                    got.add(norm(it[1:]))
            else:
                got.update(family(it))
        return {kk: table[kk] for kk in got - bad}

    def total(kk):
        return sum(c[0] for c in table[kk].values())

    def dominated(members, need):
        tot = [total(kk) for kk in members]
        return sum(tot) >= need and max(tot) >= 0.6 * sum(tot)

    GENERIC = {"AMERICAN", "FIRST", "NEW", "NATIONAL", "GENERAL", "UNITED", "SOUTHERN", "NORTHERN", "WESTERN", "EASTERN",
               "CENTRAL", "PACIFIC", "ATLANTIC", "BLUE", "GREEN", "RED", "SMART", "DIGITAL", "DATA", "CAPITAL", "FINANCIAL",
               "HEALTH", "MEDICAL", "STATE", "CITY", "COUNTY", "UNIVERSITY", "COLLEGE", "BANK", "INSURANCE", "ENERGY",
               "TECH", "CLOUD", "AI", "ROBOTICS", "BIO", "LIFE", "ADVANCED", "APPLIED", "PRECISION", "STUDENTS", "STUDENT"}
    APPROX = False       # guessing from the first word gave wrong matches (Charter Steel -> Charter Communications): off. Fix names in h1b_overrides.json instead.
    rep = {"exact": [], "family": [], "approx": [], "override": [], "none": []}
    co, approx = {}, set()
    for nm in sorted(names):
        k = norm(nm)
        if not k or k in skip_n:
            continue
        rows, how = None, None
        if k in over_n:
            how = "override"
            rows = resolve_override(over_n[k])
        else:
            members = family(k)
            if members and dominated(members, 3):
                how = "exact" if members == [k] else "family"
                rows = {kk: table[kk] for kk in members}
            elif k in table:
                how, rows = "exact", {k: table[k]}
            elif APPROX:
                # last resort: drop words from the end ("NXP SEMICONDUCTORS" -> "NXP"). Shown as "approximate" in the app.
                words = k.split()
                for n in range(len(words) - 1, 0, -1):
                    pre = " ".join(words[:n])
                    if n == 1 and (len(pre) < 3 or pre in GENERIC):
                        break
                    mem = family(pre)
                    if mem and dominated(mem, 20):
                        how, rows = "approx", {kk: table[kk] for kk in mem}
                        break
        if not rows:
            rep["none"].append(nm)
            continue
        vals = [[0, 0] for _ in years]
        for kk, per in rows.items():
            for i, y in enumerate(years):
                vals[i][0] += per[y][0]
                vals[i][1] += per[y][1]
        if sum(v[0] for v in vals) == 0 and how != "override":
            rep["none"].append(nm)
            continue
        rep[how].append((nm, sorted(rows, key=lambda kk: -total(kk))[:4]))
        co[k] = vals
        if how == "approx":
            approx.add(k)
        else:
            approx.discard(k)

    # full table (new companies that appear later still get a number; exact match in the app)
    full = {}
    for kk, per in table.items():
        vals = [list(per[y]) for y in years]
        if sum(v[0] for v in vals) >= MIN_TOTAL:
            full[kk] = vals
    for k, v in co.items():
        full[k] = v

    out = {"meta": {"built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "years": years,
                    "fields": "[total approvals, new-employment approvals] per FY, in `years` order",
                    "source": "USCIS H-1B Employer Data Hub (Tableau CSV export), first decisions only",
                    "suffix": sorted(SUFFIX), "approx": sorted(approx)},          # the app reads this list so its name cleaning always matches
           "co": full}
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"), sort_keys=True)
    print("wrote %s: %d keys, %d KB" % (OUT, len(full), os.path.getsize(OUT) >> 10))
    print("matched: exact %d, family %d, approx %d, override %d, none %d (of %d company names)" % (
        len(rep["exact"]), len(rep["family"]), len(rep["approx"]), len(rep["override"]), len(rep["none"]), len(names)))
    if a.report:
        with open(os.path.join(HERE, "h1b_match_report.txt"), "w") as f:
            for how in ("exact", "family", "approx", "override"):
                f.write("== %s\n" % how)
                for nm, ks in rep[how]:
                    f.write("%s  ->  %s\n" % (nm, "; ".join(ks)))
            f.write("== none\n" + "\n".join(rep["none"]) + "\n")
        print("report: tools/h1b_match_report.txt")


if __name__ == "__main__":
    main()
