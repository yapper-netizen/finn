"""Results card (EN-5): quarterly results filing PDF -> Revenue, EBITDA, PBT, PAT with QoQ and YoY.

Division of labour (D-016 = A, D-077):
- Python finds the statement page (consolidated first, standalone as a labelled fallback, D-017).
- The cheap model only COPIES printed rows into JSON (no arithmetic, no unit conversion).
- Python then checks everything: the three columns are the right quarters, the unit is printed
  on the page, every number appears in the page text (grounding), and the rows add up
  (cross-checks). Growth, unit conversion and computed EBITDA are Python arithmetic.
- Anything that fails is shown as missing or flagged, never silently wrong.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError, create_model, field_validator

import config

# ---------------------------------------------------------------- units and numbers

# Rupees per printed unit, divided by 1 crore (1 crore = 10 million = 100 lakh).
UNIT_TO_CRORE: dict[str, float] = {
    "crore": 1.0, "lakh": 0.01, "million": 0.1, "thousand": 1e-4, "rupees": 1e-7, "billion": 100.0,
}
_UNIT_PATTERNS: dict[str, str] = {
    "crore": r"cr(ore|ores|\.)?\b|\bcrs?\b",
    "lakh": r"lakh|lacs?\b",
    "million": r"million|\bmn\b",
    "thousand": r"thousand|'000|\b000s\b",
    "billion": r"billion|\bbn\b",
    "rupees": r"rupees|in ₹\b|in rs\.?\b",
}
_BLANK = {"", "-", "–", "—", "nil", "n/a", "na", "—", "--"}


def normalise_unit(raw: str) -> str | None:
    """Map the model's unit text ("₹ in Lakhs", "Rs. Crore") to a key of UNIT_TO_CRORE."""
    low = (raw or "").lower()
    for key in ("crore", "lakh", "million", "billion", "thousand"):
        if re.search(_UNIT_PATTERNS[key], low):
            return key
    if re.search(r"rupee|^\s*(rs\.?|₹|inr)\s*$", low):
        return "rupees"
    return None


def parse_amount(printed: Any, decimals: int = 0) -> float | None:
    """A printed amount -> float in printed units. '(1,234.5)' and '-1,234.5' are negative.

    Blank cells and dashes return None. Repaired: stray spaces inside a number ('1 7,987.26'),
    the letter O read for zero ('9O575.33'), and, when the table prints `decimals` places, a comma
    or space read for the decimal point ('19,885,3' -> 19885.3, '872 41' -> 872.41).
    Raises ValueError on text that is not a number, and on 3 decimal places ('31.658'): Indian
    statements never print those, so the dot is a misread thousands separator.
    """
    if printed is None:
        return None
    if isinstance(printed, (int, float)):
        return float(printed)
    s = str(printed).strip().replace("−", "-").replace("–", "-")
    if s.lower() in _BLANK:
        return None
    neg = s.startswith("(") or s.endswith(")") or s.startswith("-")
    body = s.strip("()₹ ").lstrip("-").strip().replace("O", "0").replace("o", "0")
    if "." not in body and decimals:
        m = re.fullmatch(r"([\d,\s]*\d)[,\s](\d+)\)?", body)
        if m and len(m.group(2)) == decimals:
            body = f"{m.group(1)}.{m.group(2)}"
    core = re.sub(r"[\s,()]", "", body)
    if not re.fullmatch(r"\d+(\.\d+)?", core):
        raise ValueError(f"not a number: {printed!r}")
    if decimals_of(core) >= 3:
        raise ValueError(f"ambiguous separator in {printed!r}")
    value = float(core)
    return -value if neg else value


def decimals_of(printed: Any) -> int:
    """Decimal places as printed ('1,234.50' -> 2, '1,234' -> 0)."""
    m = re.search(r"\.(\d+)", str(printed or ""))
    return len(m.group(1)) if m else 0


def _token_number(tok: str) -> float | None:
    """One whitespace token of page text -> its absolute value, or None if not a number."""
    t = tok.strip("()[]{}|:;*^'\"~").rstrip(".")
    if not t or not any(c.isdigit() for c in t) or not re.fullmatch(r"[\dOo,.]+", t):
        return None
    t = t.replace("O", "0").replace("o", "0").replace(",", "")
    return float(t) if re.fullmatch(r"\d+(\.\d+)?", t) else None


def page_numbers(text: str) -> set[float]:
    """Every number printed on a page (absolute values, rounded to 4 places).

    Includes pairs of adjacent tokens joined together, because PDF text extraction sometimes
    splits one number in two ('4 28.91' for 428.91).
    """
    found: set[float] = set()

    def add(t: str) -> None:
        n = _token_number(t)
        if n is not None:
            found.add(round(n, 4))

    for line in text.splitlines():
        toks = line.split()
        for i, tok in enumerate(toks):
            add(tok)
            bare = tok.strip("()")
            if re.fullmatch(r"[\dOo,]*\d,\d{1,2}", bare):        # '19,885,3': comma for the decimal point
                head, tail = bare.rsplit(",", 1)
                add(f"{head}.{tail}")
            if i + 1 < len(toks):
                nxt = toks[i + 1].rstrip(")")
                if re.fullmatch(r"\(?\d{1,3}", tok):               # '4 28.91': one number split in two
                    add(tok.lstrip("(") + nxt)
                if re.fullmatch(r"\(?[\d,]*\d", tok) and re.fullmatch(r"\d{1,2}", nxt):
                    add(f"{tok.lstrip('(')}.{nxt}")                # '872 41': space for the decimal point
    return found


def is_grounded(value: float, numbers: set[float]) -> bool:
    """True if the number (ignoring sign) is printed on the page."""
    return round(abs(value), 4) in numbers


# ---------------------------------------------------------------- growth maths (QA-3)

def growth(current: float | None, base: float | None) -> tuple[float | None, str | None]:
    """Percent change from base to current, plus a note when a percent would mislead.

    - zero base: no percent ("zero base")
    - loss in the base period: no percent; say whether it turned to profit or the loss changed
    - profit to loss: percent is still shown, with the note "turned to loss"
    """
    if current is None or base is None:
        return None, "n/a"
    if base == 0:
        return None, "zero base"
    if base < 0:
        if current >= 0:
            return None, "turned to profit"
        return None, "loss narrowed" if current > base else "loss widened"
    pct = round((current - base) / base * 100, 1)
    return pct, "turned to loss" if current < 0 else None


def fiscal_label(period_end: date) -> str:
    """Indian fiscal quarter label: quarter ending 30 Sep 2026 -> 'Q2 FY27'."""
    q = {6: 1, 9: 2, 12: 3, 3: 4}.get(period_end.month)
    fy = period_end.year + 1 if period_end.month > 3 else period_end.year
    return f"Q{q} FY{fy % 100:02d}" if q else period_end.isoformat()


# ---------------------------------------------------------------- statement page finder

_HAS_PBT = re.compile(r"before\s+(exceptional\s+items?\s+and\s+)?tax|profit\s*/?\s*\(?loss\)?\s+before", re.I)
# \W+ and oper\w* tolerate stray punctuation and OCR typos ("Revenue -from operntions").
_HAS_TOP = re.compile(r"revenue\W+(from\W+)?oper\w*|income\W+from\W+oper\w*|interest\W+earned|total\W+income", re.I)
_HAS_PAT = re.compile(r"profit\s+(for|after)|net\s+profit|profit\s*/\s*\(loss\)\s+for|\(loss\)\s+for\s+the", re.I)
_HEAD_SKIP = re.compile(r"segment|review report|we have reviewed|balance sheet|assets and liabilities|cash ?flow", re.I)
_BANK = re.compile(r"interest\s+earned", re.I)


def _head(text: str, n: int = 12) -> str:
    return "\n".join(text.splitlines()[:n])


def _numeric_density(text: str) -> int:
    return sum(1 for t in text.split() if _token_number(t) is not None)


def find_statement(pages: list[str]) -> dict | None:
    """The best statement page(s) to read first (consolidated if any), or None."""
    picks = find_statements(pages)
    return picks[0] if picks else None


def find_statements(pages: list[str]) -> list[dict]:
    """Statement page(s) to try, best first: one per basis (consolidated, not stated, standalone).

    Each pick is {pages: [0-based indexes], basis_hint, has_standalone, has_consolidated,
    mentions_consolidated, is_bank}. Empty when no page looks like a results statement.
    """
    candidates: list[tuple[int, str, int]] = []
    for i, text in enumerate(pages):
        if not text or not _HAS_PBT.search(text) or not _HAS_TOP.search(text):
            continue
        head = _head(text)
        if _HEAD_SKIP.search(head) and not re.search(r"results", head, re.I):
            continue
        if re.search(r"segment (revenue|information|results)", _head(text, 8), re.I):
            continue
        density = _numeric_density(text)
        if density < 40:  # a letter or press note that mentions the words, not the table
            continue
        basis = "consolidated" if re.search(r"consolidated", head, re.I) else (
            "standalone" if re.search(r"standalone", head, re.I) else "not stated")
        candidates.append((i, basis, density))
    if not candidates:
        return []
    has = {b for _, b, _ in candidates}
    # A consolidated statement may be printed but unreadable (a poor scan): say so, not "none".
    mentions_consolidated = any(
        re.search(r"consolidated", _head(t), re.I) and re.search(r"results", _head(t), re.I) for t in pages)
    picks: list[dict] = []
    for basis in ("consolidated", "not stated", "standalone"):
        group = [c for c in candidates if c[1] == basis]
        if not group:
            continue
        best = max(group, key=lambda c: (c[2], -c[0]))  # the densest table of that basis
        idx = [best[0]]
        if not _HAS_PAT.search(pages[best[0]]) and best[0] + 1 < len(pages):
            idx.append(best[0] + 1)  # the statement runs onto the next page
        picks.append({
            "pages": idx,
            "basis_hint": basis,
            "has_standalone": "standalone" in has,
            "has_consolidated": "consolidated" in has,
            "mentions_consolidated": mentions_consolidated,
            "is_bank": bool(_BANK.search(pages[best[0]])),
        })
    return picks


# ---------------------------------------------------------------- the AI step

LINE_KEYS: dict[str, str] = {
    "revenue": "Revenue from operations, the TOTAL row (null for a bank, or if only sub-rows are printed)",
    "other_income": "Other income",
    "total_income": "Total income",
    "finance_cost": "Finance costs (the row named finance costs / interest; not the finance cost of a financial-services arm)",
    "depreciation": "Depreciation and amortisation expense",
    "profit_before_exceptional": "Profit before exceptional items and tax (null if not printed)",
    "exceptional": "Exceptional items (null if the row is not printed)",
    "pbt": "Profit before tax, after exceptional items (for a bank: profit from ordinary activities before tax)",
    "tax": "Total tax expense (the total row, not current or deferred alone)",
    "pat_before_associates": "Only if share of profit of associates/joint ventures is added AFTER tax: the profit after tax row before that addition; else null",
    "pat": "Profit for the period / net profit after tax: the total, before the owners and non-controlling-interest split (for a bank: before minority interest)",
    "pat_owners": "Profit attributable to OWNERS of the company (the 'Owners of the Company' / 'Shareholders of the Company' row under 'Profit attributable to'), or net profit after minority interest; null only if not printed",
    "ebitda": "EBITDA, only if the statement itself prints an EBITDA row; else null",
}

PROMPT = """You read quarterly financial results of Indian listed companies.
Below is text extracted from page(s) {pages} of a results filing PDF. Spacing inside numbers may
be broken ("1 7,987.26" is 17,987.26) and OCR may show the digit 0 as the letter O.

Task: find the statement of profit and loss with quarterly columns ({basis_rule}) and COPY the
figures exactly as printed. Do not calculate, round, convert units, or fill gaps.

Use exactly three columns, in this order:
1. the latest quarter, 2. the quarter just before it, 3. the same quarter one year earlier.
Ignore half-year, nine-month and full-year columns.

Return JSON only:
{{
  "found": true or false (false if there is no profit and loss statement with quarterly columns),
  "basis": "consolidated" or "standalone" or "not stated",
  "unit": the unit the amounts are in, as printed (e.g. "crore", "lakh", "million"),
  "columns": ["YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD"] (period-end dates of the 3 columns),
  "lines": {{ <key>: {{"label": "<row label as printed>", "values": ["<col 1>", "<col 2>", "<col 3>"]}} or null }},
  "parts": {{ <key>: [ {{"label": ..., "values": [...]}}, ... ] }} (ONLY for revenue, other_income,
            finance_cost, depreciation, exceptional or tax when the statement prints NO total row
            for it but prints the sub-rows that make it up, e.g. revenue as "Sale of products" +
            "Other operating revenues", exceptional items as several named rows, or tax as
            current + deferred with no total; else leave it empty)
}}
Write values as printed, keeping parentheses for negatives, e.g. "(1,234.56)". Use null for an
empty cell or a dash. Use null for a whole line that is not printed.
Careful with rows that have FEWER numbers than the table has columns (e.g. an exceptional item
printed only in the full-year column): place each number under its own column header; if you
cannot be sure a number belongs to one of the three quarterly columns, use null there.

Line keys:
{keys}

TEXT:
{text}
"""


class Line(BaseModel):
    """One printed row: its label and three values (strings as printed, or null)."""
    label: str = ""
    values: list[str | None]

    @field_validator("label", mode="before")
    @classmethod
    def _label(cls, v: Any) -> str:
        return "" if v is None else str(v)

    @field_validator("values", mode="before")
    @classmethod
    def _three(cls, v: Any) -> list[str | None]:
        if not isinstance(v, list) or len(v) != 3:
            raise ValueError("each line needs exactly 3 values")
        return [None if x is None else str(x) for x in v]


PART_KEYS = ("revenue", "other_income", "finance_cost", "depreciation", "exceptional", "tax")


class _SchemaLine(BaseModel):
    label: str
    values: list[str | None]


# The JSON schema sent with the request (structured output): one named field per row, so the
# API itself enforces the shape. The free-form dict version drifted (rows came back as strings).
AnswerSchema = create_model(
    "ResultsStatement",
    found=(bool, ...),
    basis=(Literal["consolidated", "standalone", "not stated"], ...),
    unit=(str, ...),
    columns=(list[str], ...),
    lines=(create_model("Lines", **{k: (_SchemaLine | None, None) for k in LINE_KEYS}), ...),
    parts=(create_model("Parts", **{k: (list[_SchemaLine] | None, None) for k in PART_KEYS}), None),
)


class Extraction(BaseModel):
    """The model's answer, shape-checked before any number is used (strict: no silent drops)."""
    found: bool
    basis: Literal["consolidated", "standalone", "not stated"] = "not stated"
    unit: str = ""
    columns: list[str] = []
    lines: dict[str, Line | None] = {}
    parts: dict[str, list[Line]] = {}

    @field_validator("columns", mode="before")
    @classmethod
    def _columns(cls, v: Any) -> list[str]:
        return [] if v is None else ["" if x is None else str(x) for x in v]

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v: Any) -> str:
        return "" if v is None else str(v)

    @field_validator("parts", mode="before")
    @classmethod
    def _parts(cls, v: Any) -> dict:
        return {k: x for k, x in (v or {}).items() if x}  # null or [] = no sub-rows


def validate_extraction(obj: Any) -> Extraction:
    """Shape check of the model's JSON (raises ValueError; Python checks the numbers later)."""
    try:
        ext = Extraction.model_validate(obj)
    except ValidationError as exc:
        err = exc.errors()[0]
        where = ".".join(str(x) for x in err.get("loc", []))
        raise ValueError(f"AI answer has the wrong shape at {where}: {err['msg']}") from exc
    if ext.found and len(ext.columns) != 3:
        raise ValueError("AI answer must name exactly 3 columns")
    ext.lines = {k: v for k, v in ext.lines.items() if k in LINE_KEYS}
    ext.parts = {k: v for k, v in ext.parts.items() if k in PART_KEYS}
    return ext


_OCR_NUMERIC = re.compile(r"(?<![A-Za-z])[\dOo][\dOo,.()/\-]*(?![A-Za-z])")


def clean_ocr_numbers(text: str) -> str:
    """Replace the letter O with zero inside numbers and dates ('3O.O6.2O26' -> '30.06.2026').

    Words are untouched: a run is changed only if it holds at least one real digit.
    """
    def fix(m: re.Match) -> str:
        run = m.group(0)
        return run.replace("O", "0").replace("o", "0") if any(c.isdigit() for c in run) else run
    return _OCR_NUMERIC.sub(fix, text)


def build_prompt(pages: list[str], pick: dict) -> str:
    """The extraction prompt for the chosen statement page(s)."""
    text = "\n".join(f"===== PAGE {i + 1} =====\n{clean_ocr_numbers(pages[i])}" for i in pick["pages"])
    rule = "use the CONSOLIDATED statement if both are printed" if pick["has_consolidated"] else (
        "use the statement printed here")
    keys = "\n".join(f'- "{k}": {v}' for k, v in LINE_KEYS.items())
    return PROMPT.format(
        pages=", ".join(str(i + 1) for i in pick["pages"]),
        basis_rule=rule, keys=keys, text=text[: config.MAX_STATEMENT_CHARS],
    )


Extractor = Callable[[str, dict], Extraction]


def sum_parts(key: str, lines: list[Line], take: Callable) -> tuple[list[float | None], dict] | None:
    """Add up sub-rows (Python arithmetic) when a statement prints no total row.

    Every sub-row must be grounded. A blank cell in one sub-row counts as zero when another
    sub-row has a value in that column; a column blank in every sub-row stays blank.
    """
    rows = [take(f"{key}_part_{n}", ln) for n, ln in enumerate(lines)]
    if any(r is None for r in rows):
        return None
    total = [None if all(r[c] is None for r in rows) else sum(r[c] or 0.0 for r in rows) for c in range(3)]
    if total[0] is None:
        return None
    meta = {"label": " + ".join(ln.label for ln in lines), "page": None, "sum_of_lines": len(lines),
            "decimals": max(decimals_of(v) for ln in lines for v in ln.values)}
    return total, meta


def ai_extract(prompt: str, meta: dict) -> Extraction:
    """Default extractor: cheap model, JSON, shape-validated, answer cached (D-026)."""
    from engine import llm

    return llm.ask_json(prompt, strong=False, validate=validate_extraction, use_cache=True, meta=meta,
                        schema=AnswerSchema)


# ---------------------------------------------------------------- Python checks

def parse_date(text: str) -> date | None:
    """Period-end date from the model ('2026-09-30', '30.09.2026', 'September 30, 2026')."""
    t = (text or "").strip()
    if re.fullmatch(r"[\dOo.\-/]+", t):
        t = t.replace("O", "0").replace("o", "0")  # OCR letter O inside a numeric date
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def _months_between(a: date, b: date) -> int:
    return (a.year - b.year) * 12 + a.month - b.month


def check_columns(columns: list[str], filed_on: date) -> tuple[list[date] | None, str | None]:
    """The 3 columns must be: a quarter end, 3 months earlier, 12 months earlier; and recent."""
    dates = [parse_date(c) for c in columns]
    if len(dates) != 3 or None in dates:
        return None, f"could not read the column dates {columns}"
    cur, prev, yago = dates
    if cur.month not in (3, 6, 9, 12) or _months_between(cur, prev) != 3 or _months_between(cur, yago) != 12:
        return None, f"the columns are not latest quarter / previous quarter / year-ago quarter ({columns})"
    if not 0 <= (filed_on - cur).days <= 150:
        return None, f"the latest quarter ({cur}) does not match a filing dated {filed_on}"
    return dates, None


def unit_on_page(unit: str, pages_text: str) -> bool:
    """True if the unit word is printed on the statement page(s)."""
    return bool(re.search(_UNIT_PATTERNS[unit], pages_text, re.I))


def header_units(page_text: str) -> set[str]:
    """Units named in the statement's header lines (where '₹ in Lakhs' is printed)."""
    head = _head(page_text, 15)
    return {u for u, pat in _UNIT_PATTERNS.items() if u != "rupees" and re.search(pat, head, re.I)}


def pick_unit(model_unit: str, first_page: str, stmt_text: str) -> tuple[str | None, str | None]:
    """Decide the unit. Python reads the header; the model's answer is only a tie-breaker.

    - exactly one unit in the header: use it (even if the model said otherwise)
    - else the model's unit, if that word is printed on the statement page
    - else fail: a 100x unit error is worse than no card
    """
    in_head = header_units(first_page)
    if len(in_head) == 1:
        return next(iter(in_head)), None
    unit = normalise_unit(model_unit)
    if unit is None:
        return None, f"Unit not recognised ({model_unit!r}) and not clear from the page header."
    if unit in in_head or (not in_head and unit_on_page(unit, stmt_text)):
        return unit, None
    return None, f"The unit '{unit}' could not be confirmed on the statement page."


def _tolerance(expected: float, decimals: int) -> float:
    """How far a printed total may differ from the sum of its rounded parts (printed units)."""
    return max(3 * 10 ** (-decimals), 0.001 * abs(expected))


def _close(a: float, b: float, decimals: int) -> bool:
    return abs(a - b) <= _tolerance(b, decimals)


# ---------------------------------------------------------------- card assembly

METRIC_LABELS = {"revenue": "Revenue", "ebitda": "EBITDA", "pbt": "PBT", "pat": "PAT", "total_income": "Total income"}
COLS = ("current", "prev_quarter", "year_ago")
_COL_NAMES = ("this quarter", "previous quarter", "year-ago quarter")
EBITDA_FORMULA = "Profit before exceptional items and tax + finance costs + depreciation and amortisation − other income"


def _fail(base: dict, reason: str) -> dict:
    return {**base, "status": "could not extract", "reason": reason, "metrics": [], "checks": [], "warnings": []}


def _crore(values: list[float | None], factor: float) -> list[float | None]:
    return [None if v is None else round(v * factor, 2) for v in values]


def _metric(key: str, label: str, values: list[float | None] | None, **extra: Any) -> dict:
    """One card row with Python-computed QoQ and YoY."""
    if not values or values[0] is None:
        return {"key": key, "label": label, "available": False, **extra}
    cur, prev, yago = values
    qoq, qoq_note = growth(cur, prev)
    yoy, yoy_note = growth(cur, yago)
    return {
        "key": key, "label": label, "available": True,
        "values": dict(zip(COLS, values)),
        "qoq_pct": qoq, "qoq_note": qoq_note, "yoy_pct": yoy, "yoy_note": yoy_note,
        **extra,
    }


def assemble_card(base: dict, pages: list[str], pick: dict, ext: Extraction) -> dict:
    """Turn the model's copy of the statement into a checked card (all arithmetic here)."""
    if not ext.found:
        return _fail(base, "The AI found no quarterly profit and loss statement on the chosen page.")
    filed_on = date.fromisoformat(base["filing_date"][:10])
    dates, err = check_columns(ext.columns, filed_on)
    if err:
        return _fail(base, f"Column check failed: {err}.")
    unit, unit_err = pick_unit(ext.unit, pages[pick["pages"][0]], "\n".join(pages[i] for i in pick["pages"]))
    if unit_err:
        return _fail(base, unit_err)
    factor = UNIT_TO_CRORE[unit]
    numbers_by_page = {i: page_numbers(pages[i]) for i in pick["pages"]}
    warnings: list[str] = []
    # The table's usual decimal places, used to repair a misread decimal point in one cell.
    all_printed = [v for ln in [*ext.lines.values(), *(x for ps in ext.parts.values() for x in ps)]
                   if ln for v in ln.values if v]
    dec_counts = [decimals_of(v) for v in all_printed]
    table_decimals = max(set(dec_counts), key=dec_counts.count) if dec_counts else 0

    # 1. Parse and ground every printed value; an ungrounded number is dropped, never used.
    raw: dict[str, list[float | None]] = {}
    printed: dict[str, dict] = {}

    def take(key: str, line: Line) -> list[float | None] | None:
        try:
            vals = [parse_amount(v, table_decimals) for v in line.values]
        except ValueError as exc:
            warnings.append(f"{line.label or key}: {exc}; row ignored.")
            return None
        page = next((i for i, nums in numbers_by_page.items()
                     if all(v is None or is_grounded(v, nums) for v in vals)), None)
        if page is None:
            warnings.append(f"{line.label or key}: a value is not printed on the page; row ignored.")
            return None
        printed[key] = {"label": line.label, "printed": line.values, "page": page + 1,
                        "decimals": max([table_decimals] + [decimals_of(v) for v in line.values])}
        return vals

    for key, line in ext.lines.items():
        if line is not None:
            vals = take(key, line)
            if vals is not None:
                raw[key] = vals
    _drop_unplaceable_rows(raw, printed, pages, warnings)
    for key, lines in ext.parts.items():
        if key in raw or key not in PART_KEYS or not lines or (key == "revenue" and pick["is_bank"]):
            continue
        summed = sum_parts(key, lines, take)
        if summed is not None:
            raw[key] = summed[0]
            printed[key] = {**summed[1], "printed": None, "page": printed[f"{key}_part_0"]["page"]}

    # 2. Cross-checks in printed units (they catch shifted columns and misread rows).
    checks: list[dict] = []

    def check(name: str, lhs_key: str, rhs: list[float | None], keys: list[str]) -> None:
        lhs = raw.get(lhs_key)
        if lhs is None or any(r is None for r in rhs) or any(v is None for v in lhs):
            return
        dec = max(printed[k]["decimals"] for k in keys if k in printed)
        bad = [c for c in range(3) if not _close(rhs[c], lhs[c], dec)]
        detail = "; ".join(f"{_COL_NAMES[c]}: off by ₹{abs(lhs[c] - rhs[c]) * factor:,.1f} crore" for c in bad)
        checks.append({"name": name, "passed": not bad, "detail": detail})

    def col(key: str, c: int, blank_zero: bool = False) -> float | None:
        v = raw.get(key)
        if v is None:
            return 0.0 if blank_zero else None
        return (0.0 if blank_zero else None) if v[c] is None else v[c]

    is_bank = pick["is_bank"]
    if not is_bank and {"revenue", "other_income", "total_income"} <= raw.keys():
        check("Total income = revenue + other income", "total_income",
              [None if col("revenue", c) is None or col("other_income", c, True) is None
               else col("revenue", c) + col("other_income", c, True) for c in range(3)],
              ["revenue", "other_income", "total_income"])
    if "profit_before_exceptional" in raw and "pbt" in raw:
        pbe, exc = raw["profit_before_exceptional"], [col("exceptional", c, True) for c in range(3)]
        # Exceptional items are printed either as a signed amount (added) or as a cost (subtracted).
        signed = [pbe[c] + exc[c] if pbe[c] is not None else None for c in range(3)]
        as_cost = [pbe[c] - exc[c] if pbe[c] is not None else None for c in range(3)]
        pbt = raw["pbt"]
        rhs = [s if (s is not None and pbt[c] is not None and _close(s, pbt[c], 2)) else a
               for c, (s, a) in enumerate(zip(signed, as_cost))]
        check("PBT = profit before exceptional items ± exceptional items", "pbt", rhs,
              ["pbt", "profit_before_exceptional"])
    pat_check_key = "pat_before_associates" if "pat_before_associates" in raw else "pat"
    if {"pbt", "tax", pat_check_key} <= raw.keys():
        after_tax = [None if raw["pbt"][c] is None or raw["tax"][c] is None else raw["pbt"][c] - raw["tax"][c]
                     for c in range(3)]
        check("PAT = PBT − tax", pat_check_key, after_tax, ["pbt", "tax", pat_check_key])
        # A consolidated or bank statement may deduct minority interest or add associates after
        # tax; then PBT − tax is still printed, as its own row. Finding it there also passes.
        shown_pat = raw.get("pat_owners") or raw[pat_check_key]
        if not checks[-1]["passed"] and None not in after_tax and any(
                in_printed_order([round(v, 2) for v in after_tax], pages[i]) for i in pick["pages"]) and any(
                in_printed_order(shown_pat, pages[i]) for i in pick["pages"]):
            checks[-1] = {"name": "PBT − tax matches a printed profit row", "passed": True, "detail": ""}

    # 3. Metrics in Rs crore, growth by Python.
    def src(key: str) -> dict:
        p = printed.get(key, {})
        return {"line": p.get("label"), "printed": p.get("printed"), "page": p.get("page")}

    metrics: list[dict] = []
    if is_bank:
        metrics.append(_metric("total_income", "Total income", _crore(raw.get("total_income"), factor) if "total_income" in raw else None,
                               source=src("total_income")))
        metrics.append({"key": "ebitda", "label": "EBITDA", "available": False, "note": "n/a for banks"})
    else:
        rev_src = src("revenue")
        if printed.get("revenue", {}).get("sum_of_lines"):
            rev_src["note"] = f"sum of {printed['revenue']['sum_of_lines']} printed lines (no total row is printed)"
        metrics.append(_metric("revenue", "Revenue", _crore(raw.get("revenue"), factor) if "revenue" in raw else None, source=rev_src))
        metrics.append(_ebitda(raw, factor, src))
    metrics.append(_metric("pbt", "PBT", _crore(raw.get("pbt"), factor) if "pbt" in raw else None, source=src("pbt")))
    pat_key = "pat_owners" if "pat_owners" in raw else "pat"
    metrics.append(_metric("pat", "PAT", _crore(raw.get(pat_key), factor) if pat_key in raw else None, source=src(pat_key),
                           note="attributable to owners" if pat_key == "pat_owners" else None))
    for m in metrics:
        if m.get("available") is False and "note" not in m:
            m["note"] = "could not be read reliably from the filing"

    exc_note = exceptional_note(raw, factor)
    if exc_note:
        warnings.append(exc_note)
    headline = [m for m in metrics if m["key"] in ("revenue", "total_income", "pbt", "pat")]
    n_ok = sum(1 for m in headline if m.get("available"))
    status = "ok" if n_ok == len(headline) else ("partial" if n_ok else "could not extract")
    basis = ext.basis if ext.basis != "not stated" else pick["basis_hint"]
    return {
        **base,
        "status": status,
        "reason": None if status == "ok" else "Some figures could not be read reliably; open the filing for them.",
        "card_type": "bank" if is_bank else "company",
        "basis": basis,
        "basis_note": _basis_note(basis, pick),
        "unit": "Rs crore",
        "source_unit": unit,
        "period": {"current": dates[0].isoformat(), "prev_quarter": dates[1].isoformat(),
                   "year_ago": dates[2].isoformat(), "label": fiscal_label(dates[0]),
                   "prev_label": fiscal_label(dates[1]), "year_ago_label": fiscal_label(dates[2])},
        "pages": [i + 1 for i in pick["pages"]],
        "metrics": metrics,
        "verdict": _with_margin_note(verdict(metrics), [] if is_bank else margins(metrics)),
        "margins": [] if is_bank else margins(metrics),
        "checks": checks,
        "warnings": warnings,
    }


_DASH = {"-", "–", "—", "--"}


def row_width(text_line: str) -> int:
    """How many cells a printed row fills: numbers plus dash placeholders."""
    return sum(1 for t in text_line.split() if t in _DASH or _token_number(t) is not None)


def _line_number_slots(text_line: str) -> list[set[float]]:
    """For each token position, the numbers it can be read as (alone, or joined with the next)."""
    slots: list[set[float]] = []
    toks = text_line.split()
    for i in range(len(toks)):
        window = " ".join(toks[i:i + 2])
        cands = {n for n in page_numbers(toks[i])} | {n for n in page_numbers(window) if n not in page_numbers(toks[i + 1] if i + 1 < len(toks) else "")}
        slots.append(cands)
    return slots


def in_printed_order(values: list[float | None], page_text: str) -> bool:
    """True if a row's values are printed, in this column order, on one line of the page.

    This catches a row read with its columns shifted, which number-by-number grounding cannot.
    """
    want = [round(abs(v), 4) for v in values if v is not None]
    if not want:
        return False
    for text_line in page_text.splitlines():
        k = 0
        for slot in _line_number_slots(text_line):
            if k < len(want) and want[k] in slot:
                k += 1
        if k == len(want):
            return True
    return False


def find_row_line(values: list[float | None], page_text: str) -> str | None:
    """The first text line on which all of a row's values are printed."""
    want = [v for v in values if v is not None]
    for text_line in page_text.splitlines():
        nums = page_numbers(text_line)
        if want and all(is_grounded(v, nums) for v in want):
            return text_line
    return None


def _drop_unplaceable_rows(raw: dict, printed: dict, pages: list[str], warnings: list[str]) -> None:
    """Drop a row that has blank quarterly cells but prints fewer cells than the table has.

    Example: an exceptional item printed only in the full-year column. Its one number cannot be
    placed under a quarter with confidence, so it is not used (the cross-checks then treat the
    quarters as blank). Rows with every quarter filled are kept.
    """
    def width(key: str) -> int | None:
        line = find_row_line(raw[key], pages[printed[key]["page"] - 1])
        return row_width(line) if line else None

    full = [w for k in ("revenue", "total_income", "pbt", "pat")
            if k in raw and None not in raw[k] and (w := width(k))]
    if not full:
        return
    table_width = min(full)
    for key in [k for k, v in raw.items() if None in v and any(x is not None for x in v)]:
        w = width(key)
        if w is not None and w < table_width:
            del raw[key]
            if key != "exceptional":
                warnings.append(f"{printed[key]['label'] or key}: printed in fewer columns than the table, "
                                "so it could not be placed under a quarter; not used.")


def _ebitda(raw: dict, factor: float, src: Callable[[str], dict]) -> dict:
    """Printed EBITDA if there is one; else computed (D-054) and labelled with its inputs."""
    if "ebitda" in raw:
        return _metric("ebitda", "EBITDA", _crore(raw["ebitda"], factor), computed=False, source=src("ebitda"))
    base_key = "profit_before_exceptional" if "profit_before_exceptional" in raw else "pbt"
    need = [base_key, "finance_cost", "depreciation", "other_income"]
    if not all(k in raw for k in need):
        missing = ", ".join(k.replace("_", " ") for k in need if k not in raw)
        return {"key": "ebitda", "label": "EBITDA", "available": False, "computed": True,
                "note": f"not printed, and inputs missing to compute it ({missing})"}
    vals: list[float | None] = []
    for c in range(3):
        parts = [raw[base_key][c], raw["finance_cost"][c], raw["depreciation"][c]]
        oi = raw["other_income"][c] or 0.0
        vals.append(None if any(p is None for p in parts) else parts[0] + (parts[1] or 0) + parts[2] - oi)
    formula = EBITDA_FORMULA if base_key == "profit_before_exceptional" else EBITDA_FORMULA.replace(
        "Profit before exceptional items and tax", "Profit before tax")
    inputs = {k: dict(zip(COLS, _crore(raw[k], factor))) for k in need}
    return _metric("ebitda", "EBITDA", _crore(vals, factor), computed=True, formula=formula, inputs=inputs,
                   source={"line": "computed", "page": src(base_key).get("page")})


def _pct_text(p: float | None, note: str | None) -> str:
    return note or "n/a" if p is None else f"{'up' if p >= 0 else 'down'} {abs(p):.0f}%"


def verdict(metrics: list[dict]) -> str | None:
    """One rule-based line for the top of the card (no AI): the year-on-year direction."""
    by = {m["key"]: m for m in metrics if m.get("available")}
    top = by.get("revenue") or by.get("total_income")
    lines = [m for m in metrics if m.get("available") and m.get("yoy_pct") is not None]
    if not top or not lines:
        return None
    if len(lines) >= 3 and all(m["yoy_pct"] > 0 for m in lines):
        return f"All {len(lines)} lines up year on year."
    if len(lines) >= 3 and all(m["yoy_pct"] < 0 for m in lines):
        return f"All {len(lines)} lines down year on year."
    pat = by.get("pat")
    text = f"{top['label']} {_pct_text(top.get('yoy_pct'), top.get('yoy_note'))} year on year"
    if pat:
        text += f"; PAT {_pct_text(pat.get('yoy_pct'), pat.get('yoy_note'))}"
    return text + "."


def margins(metrics: list[dict]) -> list[dict]:
    """EBITDA and PAT margins (% of revenue) per column and the YoY change in basis points."""
    by = {m["key"]: m for m in metrics if m.get("available")}
    rev = by.get("revenue")
    out: list[dict] = []
    for key, label in (("ebitda", "EBITDA margin"), ("pat", "PAT margin")):
        m = by.get(key)
        if not rev or not m:
            continue
        vals = {c: (None if rev["values"][c] in (None, 0) or m["values"][c] is None
                    else round(m["values"][c] / rev["values"][c] * 100, 1)) for c in COLS}
        cur, yago = vals["current"], vals["year_ago"]
        out.append({"key": f"{key}_margin", "label": label, "values": vals,
                    "yoy_bps": None if cur is None or yago is None else round((cur - yago) * 100)})
    return out


def exceptional_note(raw: dict, factor: float) -> str | None:
    """Say how exceptional items moved this quarter's PBT (computed from printed rows, in crore)."""
    exc = (raw.get("exceptional") or [None])[0]
    if not exc:
        return None
    pbt, pbe = (raw.get("pbt") or [None])[0], (raw.get("profit_before_exceptional") or [None])[0]
    if pbt is not None and pbe is not None and pbt != pbe:
        impact = (pbt - pbe) * factor
        return (f"Exceptional items {'added' if impact > 0 else 'took'} ₹{abs(impact):,.1f} crore "
                f"{'to' if impact > 0 else 'off'} PBT this quarter; see the notes in the filing.")
    return f"Exceptional items of ₹{abs(exc) * factor:,.1f} crore are printed this quarter; see the notes in the filing."


def _with_margin_note(text: str | None, margin_rows: list[dict]) -> str | None:
    """Add the EBITDA-margin move when it is large (>= 100 bps): growth can hide a squeeze."""
    row = next((m for m in margin_rows if m["key"] == "ebitda_margin"), None)
    if not text or not row or row["yoy_bps"] is None or abs(row["yoy_bps"]) < 100:
        return text
    return f"{text} EBITDA margin {'up' if row['yoy_bps'] > 0 else 'down'} {abs(row['yoy_bps'])} bps."


def _basis_note(basis: str, pick: dict) -> str:
    if basis == "consolidated":
        return "Consolidated" + (" (standalone also in the filing)" if pick["has_standalone"] else "")
    if basis == "standalone":
        if pick["has_consolidated"]:
            return "Standalone"
        if pick.get("mentions_consolidated"):
            return "Standalone (the consolidated statement in this filing could not be read)"
        return "Standalone (no consolidated statement in this filing)"
    return "Basis not stated in the filing"


def build_card(filing: dict, pages: list[str], extractor: Extractor = ai_extract) -> dict:
    """Full pipeline for one results filing whose PDF text is already loaded."""
    base = {
        "filing_id": filing.get("id"), "ticker": filing.get("ticker"), "company": filing.get("company"),
        "filing_date": filing.get("date"), "pdf_url": filing.get("pdf_url"), "title": filing.get("title"),
        "kind": "results", "engine_version": config.CARD_ENGINE_VERSION,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
    }
    if not any(p.strip() for p in pages):
        return _fail(base, "The PDF is a scanned image without a text layer; FINN does not read text from "
                           "images (OCR). Open the filing for the numbers.")
    picks = find_statements(pages)
    if not picks:
        if sum(1 for p in pages if not p.strip()) >= len(pages) / 2:
            return _fail(base, "The results pages are scanned images without a text layer; FINN does not read "
                               "text from images (OCR). Open the filing for the numbers.")
        return _fail(base, "No readable quarterly results table found in this PDF (it may be a cover letter, "
                           "a press note, or a poor-quality scan).")
    # D-017: consolidated first; if that statement cannot be read, fall back to the next basis.
    first_failure: dict | None = None
    tokens = {"tokens_in": 0, "tokens_out": 0}
    for pick in picks:
        meta: dict = {}
        try:
            ext = extractor(build_prompt(pages, pick), meta)
        except (ValueError, RuntimeError) as exc:
            return {**_fail(base, f"The AI step failed: {str(exc)[:160]}. Try again later."), "retryable": True}
        for k in tokens:
            tokens[k] += meta.get(k) or 0
        card = assemble_card(base, pages, pick, ext)
        card["ai"] = {"model": meta.get("model"), "cached": meta.get("cached"), **tokens}
        if card["status"] != "could not extract":
            if first_failure is not None:
                card["basis_note"] = (f"{card['basis'].capitalize()} (the {first_failure.get('basis') or 'first'} "
                                      "statement in this filing could not be read)")
                card["warnings"].insert(0, f"{first_failure.get('basis', 'First').capitalize()} statement: "
                                           f"{first_failure['reason']}")
            return card
        first_failure = first_failure or {**card, "basis": pick["basis_hint"]}
    return first_failure
