"""Checks that run on every model reply, and on every buyer message, before anything is shown."""
import re

NUM = re.compile(r"\d+(?:[.,]\d+)*")
SENTENCE = re.compile(r"(?<=[.!?\n])\s+")
MONEY = re.compile(r"(₹|\brs\.?\b|\binr\b|lakh|\blac\b|crore|\bcr\b)", re.I)
DISCOUNT = re.compile(
    r"(discount|negotiat|waiver|waive|best price|final price|special price|cashback|rebate|% off)", re.I
)
PRICE_ASK = re.compile(
    r"(discount|negotiat|best price|final price|last price|lowest price|booking amount|\boffers?\b)", re.I
)
CITE = re.compile(r"\{facts:\s*([^}]*)\}", re.I)
OPT_OUT = re.compile(
    r"^\W*(stop( (messaging|texting|contacting|calling) me)?|unsubscribe|opt[ -]?out"
    r"|(please )?(do not|don't|dont) (contact|message|call) me)\W*$",
    re.I,
)
PERSON = re.compile(
    r"\b(talk|speak|chat|connect)\b.{0,25}\b(human|person|someone|somebody|executive|agent|salesperson"
    r"|sales team|representative)\b|\bhuman\b|\breal person\b|\binsaan\b",
    re.I,
)
SMALL = {"1", "2", "3", "4"}  # "2 BHK", "2 minutes": fine outside a money sentence


def _norm(n: str) -> str:
    return n.replace(",", "")


def numbers(text: str) -> set:
    return {_norm(n) for n in NUM.findall(text or "")}


def is_opt_out(text: str) -> bool:
    return bool(OPT_OUT.match(text or ""))


def asks_for_person(text: str) -> bool:
    return bool(PERSON.search(text or ""))


def extract_cites(text: str):
    """Return (reply without the citation tag, list of cited fact ids)."""
    ids = []
    for m in CITE.finditer(text or ""):
        ids += [int(i) for i in re.findall(r"F(\d+)", m.group(1), re.I)]
    return CITE.sub("", text or "").strip(), ids


def find_violation(reply: str, trusted_text: str, buyer_text: str = ""):
    """None if the reply is acceptable, otherwise a short reason.

    - a sentence with a discount word and a number is blocked
    - a sentence about money may only use numbers from the fact sheet or tool results
    - other numbers may also come from what the buyer wrote, or be 1 to 4
    """
    strict_ok = numbers(trusted_text)
    loose_ok = strict_ok | numbers(buyer_text)
    for sentence in SENTENCE.split(reply):
        nums = [_norm(n) for n in NUM.findall(sentence)]
        if not nums:
            continue
        if DISCOUNT.search(sentence):
            return "discount_claim"
        strict = bool(MONEY.search(sentence))
        for n in nums:
            ok = n in strict_ok if strict else (n in loose_ok or n in SMALL)
            if not ok:
                return "unsupported_number"
    return None