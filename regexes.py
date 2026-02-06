import re

RX_ANON = re.compile(r"\s*intenção anônima:\s*(.*)", re.I | re.S)
RX_DASH = re.compile(r"\s*(.+)\s-\s(.*)", re.S)
RX_LABELED = re.compile(r"\s*nome:\s*(.*\S)\s*[\n]+intenção:(.*)", re.I | re.S)


def parse_named_intention(text: str) -> dict | None:
    for rx in [RX_LABELED, RX_DASH]:
        m = rx.match(text)
        if m:
            return {"name": m.group(1).strip(), "intention": m.group(2).strip()}

    return None


def parse_anon_intention(text: str) -> str:
    m = RX_ANON.match(text)
    if m:
        return m.group(1).strip()

    return text.strip()
