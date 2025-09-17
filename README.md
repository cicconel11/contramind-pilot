# ContraMind Pilot (Local)

Minimal stack to demo **work → prove → act** without ML.

## what you get
- **Postgres 16** with a tiny `decide_json()` kernel (PL/pgSQL), parameter tables, and a param hash view.
- **WorldCheck** FastAPI service that returns a single yes/no bit with realistic latency.
- **Attestor** FastAPI service that signs a decision bundle with Ed25519.
- **Client** container that exercises the flow: call kernel → optionally call WorldCheck → get an attestation.

## run it
```bash
docker compose up --build
```

You should see the client print:
- The decision bundle from Postgres (PASS / HOLD_HUMAN / NEED_ONE_BIT)
- A WorldCheck response (for NEED_ONE_BIT cases)
- An Attestation (signature + public key + digest)

## explore
Connect to Postgres:
```bash
psql postgres://cm:cm@localhost:5432/cm
# Try different params
UPDATE cm.params_thresholds SET v=2000 WHERE k='amount_max';
SELECT * FROM cm.param_hash_view;
SELECT cm.decide_json(1500, 'US', now(), 0);
```

WorldCheck:
```bash
curl -X POST localhost:8081/verify -H 'content-type: application/json' -d '{"type":"issuer_verify","force":true}'
```

Attestor:
```bash
curl localhost:8082/pubkey
```

## notes
- This is a *minimal* POC. In a real system, the kernel would be **synthesized** and **certified**; here it’s hand-authored but tiny and deterministic.
- The attestation is a dev-mode signature over the bundle; swap in TEEs/ZK later.
