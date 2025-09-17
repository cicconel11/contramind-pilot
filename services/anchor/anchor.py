import os, time, json, hashlib, requests, psycopg

PGHOST=os.getenv("PGHOST","postgres"); PGPORT=int(os.getenv("PGPORT","5432"))
PGUSER=os.getenv("PGUSER","cm"); PGPASSWORD=os.getenv("PGPASSWORD","cm"); PGDATABASE=os.getenv("PGDATABASE","cm")
ATTESTOR=os.getenv("ATTESTOR_URL","http://attestor:8080")

def merkle(leaves):
    if not leaves: return None
    layer = [hashlib.sha256(x.encode()).hexdigest() for x in leaves]
    while len(layer) > 1:
        nxt=[]
        for i in range(0,len(layer),2):
            a=layer[i]; b=layer[i+1] if i+1 < len(layer) else a
            nxt.append(hashlib.sha256((a+b).encode()).hexdigest())
        layer=nxt
    return layer[0]

def main():
    while True:
        try:
            with psycopg.connect(host=PGHOST, port=PGPORT, user=PGUSER, password=PGPASSWORD, dbname=PGDATABASE) as conn:
                with conn.cursor() as cur:
                    # find next range to anchor
                    cur.execute("SELECT coalesce(max(to_id),0) FROM cm.anchors"); start=cur.fetchone()[0]+1
                    cur.execute("SELECT id, proof_id FROM cm.decision_ledger WHERE id >= %s ORDER BY id LIMIT 1000", (start,))
                    rows=cur.fetchall()
                    if not rows:
                        time.sleep(10); continue
                    leaves=[r[1] for r in rows]
                    root=merkle(leaves)
                    bundle={"type":"anchor","from_id":rows[0][0],"to_id":rows[-1][0],"merkle_root":root}
                    # sign anchor
                    sig=requests.post(f"{ATTESTOR}/sign", json={"bundle": bundle}).json()
                    cur.execute("INSERT INTO cm.anchors(from_id,to_id,merkle_root) VALUES (%s,%s,%s) RETURNING id",
                                (rows[0][0], rows[-1][0], root))
                    conn.commit()
                    print("Anchored", bundle, "sig_digest", sig["digest_hex"])
        except Exception as e:
            print("anchor error:", e)
            time.sleep(5)

if __name__=="__main__": main()
