import os, psycopg, json
from hypothesis import given, settings, strategies as st
PGHOST=os.getenv("PGHOST","cm-postgres"); PGPORT=int(os.getenv("PGPORT","5432"))

def call(a,c,t,r):
    with psycopg.connect(host=PGHOST, port=PGPORT, user="cm", password="cm", dbname="cm") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cm.decide_json(%s::numeric,%s::text,%s::timestamptz,%s::int);",(a,c,t,r))
            return cur.fetchone()[0]

@settings(deadline=None)
@given(amt=st.decimals(min_value=0, max_value=10000, places=2), recent=st.integers(min_value=0, max_value=5))
def test_weekend_guard(amt, recent):
    wd="2025-09-16T12:00:00Z"; wk="2025-09-14T12:00:00Z"
    a=call(str(amt),"US",wd,recent); b=call(str(amt),"US",wk,recent)
    if a["decision"]=="PASS": assert b["decision"] in {"NEED_ONE_BIT","HOLD_HUMAN"}

@given(a1=st.decimals(min_value=0, max_value=10000, places=2), a2=st.decimals(min_value=0, max_value=10000, places=2), r=st.integers(min_value=0, max_value=5))
def test_monotonic_threshold(a1,a2,r):
    # lower amount should not produce a strictly "worse" decision if all else equal (heuristic for demo)
    wd="2025-09-16T12:00:00Z"; c="US"
    d1=call(str(min(a1,a2)),c,wd,r)["decision"]
    d2=call(str(max(a1,a2)),c,wd,r)["decision"]
    order={"PASS":0,"NEED_ONE_BIT":1,"HOLD_HUMAN":2}
    assert order[d1] <= order[d2]

def test_param_hash_changes():
    with psycopg.connect(host=PGHOST, port=PGPORT, user="cm", password="cm", dbname="cm") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT param_hash FROM cm.param_hash_view"); h1=cur.fetchone()[0]
            cur.execute("UPDATE cm.params_thresholds SET v=v+1 WHERE k='amount_max'")
            cur.execute("SELECT param_hash FROM cm.param_hash_view"); h2=cur.fetchone()[0]
            assert h1 != h2
            cur.execute("UPDATE cm.params_thresholds SET v=v-1 WHERE k='amount_max'")
