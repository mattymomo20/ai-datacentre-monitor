"""One-off diagnostic: try several NYT/Guardian query variants and print what
each returns. Run via the 'Source debug' workflow. Keys are auto-masked in
Actions logs."""

import os

import requests

NYT = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
G = "https://content.guardianapis.com/search"


def show(name: str, url: str, params: dict) -> None:
    try:
        r = requests.get(url, params=params, timeout=30)
        print(f"{name}: HTTP {r.status_code}")
        d = r.json()
    except Exception as e:
        print(f"{name}: FAILED {e}")
        return
    resp = d.get("response") or {}
    if "docs" in resp:
        meta = resp.get("meta") or {}
        docs = resp.get("docs") or []
        print(f"  hits: {meta.get('hits')}  docs returned: {len(docs)}")
        for doc in docs[:3]:
            print("   -", ((doc.get("headline") or {}).get("main") or "")[:90])
    elif "results" in resp:
        results = resp.get("results") or []
        print(f"  total: {resp.get('total')}  results returned: {len(results)}")
        for x in results[:3]:
            print("   -", (x.get("webTitle") or "")[:90])
    else:
        print("  unexpected body:", str(d)[:300])


nyt_key = os.environ.get("NYT_API_KEY", "")
g_key = os.environ.get("GUARDIAN_API_KEY", "")
print(f"NYT key present: {bool(nyt_key)} | Guardian key present: {bool(g_key)}\n")

show("NYT A: q=\"data center\" + dates", NYT,
     {"q": '"data center"', "begin_date": "20240101", "end_date": "20240131", "api-key": nyt_key})
show("NYT B: q=\"data center\" no dates", NYT,
     {"q": '"data center"', "api-key": nyt_key})
show("NYT C: current fq syntax", NYT,
     {"fq": 'headline:("data center" "data centre" "datacenter") OR body:("data center" "data centre" "datacenter")',
      "begin_date": "20240101", "end_date": "20240131", "api-key": nyt_key})
show("NYT D: dates only, no query", NYT,
     {"begin_date": "20240101", "end_date": "20240131", "api-key": nyt_key})
print()
show("Guardian A: OR of 3 phrases (current)", G,
     {"q": '"data centre" OR "data center" OR "datacenter"',
      "from-date": "2024-01-01", "to-date": "2024-01-31", "page-size": 10, "api-key": g_key})
show("Guardian B: single phrase", G,
     {"q": '"data centre"', "from-date": "2024-01-01", "to-date": "2024-01-31",
      "page-size": 10, "api-key": g_key})
show("Guardian C: unquoted", G,
     {"q": "data centre", "from-date": "2024-01-01", "to-date": "2024-01-31",
      "page-size": 10, "api-key": g_key})
