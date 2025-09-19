--
-- PostgreSQL database dump
--

\restrict 4xR5jXiIl6ESDhIerFnRfERw6o51kDtQCEtLT0fg205waYwgJvRDn3BjJjMLkTt

-- Dumped from database version 16.10
-- Dumped by pg_dump version 16.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: cm; Type: SCHEMA; Schema: -; Owner: cm
--

CREATE SCHEMA cm;


ALTER SCHEMA cm OWNER TO cm;

--
-- Name: decide_json(double precision, text, timestamp with time zone, smallint); Type: FUNCTION; Schema: cm; Owner: cm
--

CREATE FUNCTION cm.decide_json(double precision, text, timestamp with time zone, smallint) RETURNS jsonb
    LANGUAGE sql
    AS $_$ SELECT cm.decide_json($1::numeric, $2::text, $3::timestamptz, $4::int) $_$;


ALTER FUNCTION cm.decide_json(double precision, text, timestamp with time zone, smallint) OWNER TO cm;

--
-- Name: decide_json(numeric, text, timestamp with time zone, integer); Type: FUNCTION; Schema: cm; Owner: cm
--

CREATE FUNCTION cm.decide_json(p_amount numeric, p_country text, p_ts timestamp with time zone, p_recent_disputes integer) RETURNS jsonb
    LANGUAGE plpgsql
    AS $$
DECLARE
  weekend BOOL := EXTRACT(ISODOW FROM p_ts) IN (6,7);
  amount_max NUMERIC;
  allowlist_hit BOOL;
  param_hash_val TEXT;
  kernel_id TEXT := 'K_demo_v1_2750_allowlist';  -- in a real system this is a code hash
  decision TEXT;
  obligations TEXT[] := ARRAY[]::TEXT[];
  needs_one_bit BOOL := FALSE;
BEGIN
  SELECT v INTO amount_max FROM cm.params_thresholds WHERE k='amount_max';
  IF amount_max IS NULL THEN
    RAISE EXCEPTION 'amount_max not configured';
  END IF;

  SELECT EXISTS(SELECT 1 FROM cm.params_allowlist WHERE country = p_country) INTO allowlist_hit;
  SELECT param_hash FROM cm.param_hash_view INTO param_hash_val;

  -- Guardrails (cheap checks first)
  IF allowlist_hit AND p_amount <= amount_max AND NOT weekend THEN
    decision := 'PASS';
    obligations := array_append(obligations, 'privacy_ok');
  ELSIF (p_amount > amount_max) AND (NOT allowlist_hit) AND (p_recent_disputes < 2) THEN
    decision := 'HOLD_HUMAN';
    obligations := array_append(obligations, 'budget_ok');
  ELSE
    decision := 'NEED_ONE_BIT';
    needs_one_bit := TRUE;
  END IF;

  RETURN jsonb_build_object(
    'decision', decision,
    'obligations_satisfied', obligations,
    'kernel_id', kernel_id,
    'param_hash', param_hash_val,
    'needs_one_bit', needs_one_bit
  );
END;
$$;


ALTER FUNCTION cm.decide_json(p_amount numeric, p_country text, p_ts timestamp with time zone, p_recent_disputes integer) OWNER TO cm;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: anchors; Type: TABLE; Schema: cm; Owner: cm
--

CREATE TABLE cm.anchors (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    from_id bigint NOT NULL,
    to_id bigint NOT NULL,
    merkle_root text NOT NULL
);


ALTER TABLE cm.anchors OWNER TO cm;

--
-- Name: anchors_id_seq; Type: SEQUENCE; Schema: cm; Owner: cm
--

CREATE SEQUENCE cm.anchors_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE cm.anchors_id_seq OWNER TO cm;

--
-- Name: anchors_id_seq; Type: SEQUENCE OWNED BY; Schema: cm; Owner: cm
--

ALTER SEQUENCE cm.anchors_id_seq OWNED BY cm.anchors.id;


--
-- Name: decision_ledger; Type: TABLE; Schema: cm; Owner: cm
--

CREATE TABLE cm.decision_ledger (
    id bigint NOT NULL,
    ts timestamp with time zone DEFAULT now(),
    proof_id text NOT NULL,
    kernel_id text NOT NULL,
    param_hash text NOT NULL,
    bundle jsonb NOT NULL
);


ALTER TABLE cm.decision_ledger OWNER TO cm;

--
-- Name: decision_ledger_id_seq; Type: SEQUENCE; Schema: cm; Owner: cm
--

CREATE SEQUENCE cm.decision_ledger_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE cm.decision_ledger_id_seq OWNER TO cm;

--
-- Name: decision_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: cm; Owner: cm
--

ALTER SEQUENCE cm.decision_ledger_id_seq OWNED BY cm.decision_ledger.id;


--
-- Name: params_allowlist; Type: TABLE; Schema: cm; Owner: cm
--

CREATE TABLE cm.params_allowlist (
    country text NOT NULL
);


ALTER TABLE cm.params_allowlist OWNER TO cm;

--
-- Name: params_thresholds; Type: TABLE; Schema: cm; Owner: cm
--

CREATE TABLE cm.params_thresholds (
    k text NOT NULL,
    v numeric NOT NULL
);


ALTER TABLE cm.params_thresholds OWNER TO cm;

--
-- Name: param_hash_view; Type: VIEW; Schema: cm; Owner: cm
--

CREATE VIEW cm.param_hash_view AS
 SELECT md5(((COALESCE(( SELECT string_agg(params_allowlist.country, ','::text ORDER BY params_allowlist.country) AS string_agg
           FROM cm.params_allowlist), ''::text) || '|'::text) || COALESCE(( SELECT string_agg(((params_thresholds.k || '='::text) || (params_thresholds.v)::text), ','::text ORDER BY params_thresholds.k) AS string_agg
           FROM cm.params_thresholds), ''::text))) AS param_hash;


ALTER VIEW cm.param_hash_view OWNER TO cm;

--
-- Name: anchors id; Type: DEFAULT; Schema: cm; Owner: cm
--

ALTER TABLE ONLY cm.anchors ALTER COLUMN id SET DEFAULT nextval('cm.anchors_id_seq'::regclass);


--
-- Name: decision_ledger id; Type: DEFAULT; Schema: cm; Owner: cm
--

ALTER TABLE ONLY cm.decision_ledger ALTER COLUMN id SET DEFAULT nextval('cm.decision_ledger_id_seq'::regclass);


--
-- Data for Name: anchors; Type: TABLE DATA; Schema: cm; Owner: cm
--

COPY cm.anchors (id, created_at, from_id, to_id, merkle_root) FROM stdin;
1	2025-09-17 03:39:08.810684+00	1	6	29f88d0d7c130aa7d58f6ec4b0d03da9b15107593a7ade2568b79dd069c545fc
\.


--
-- Data for Name: decision_ledger; Type: TABLE DATA; Schema: cm; Owner: cm
--

COPY cm.decision_ledger (id, ts, proof_id, kernel_id, param_hash, bundle) FROM stdin;
1	2025-09-17 03:29:06.25123+00	478187691db497dbdee46260169acab04671f923e58d4af9d25efca8f0e9d89e	K_demo_v1_2750_allowlist	ceab89642386eb0969a883cc9ee4a161	{"decision": "PASS", "kernel_id": "K_demo_v1_2750_allowlist", "param_hash": "ceab89642386eb0969a883cc9ee4a161", "needs_one_bit": false, "obligations_satisfied": ["privacy_ok"]}
2	2025-09-17 03:29:06.409116+00	7253f6f104ae5c267e874acd9cfc11b66ff4e898eecfbc3f35476608c3da3129	K_demo_v1_2750_allowlist	ceab89642386eb0969a883cc9ee4a161	{"decision": "HOLD_HUMAN", "kernel_id": "K_demo_v1_2750_allowlist", "param_hash": "ceab89642386eb0969a883cc9ee4a161", "needs_one_bit": false, "obligations_satisfied": ["budget_ok"]}
3	2025-09-17 03:29:06.41868+00	e2ed06ff6898e2f5ae7c7fd7d2cfffb4e450692aa16506ee305fab0672c52e88	K_demo_v1_2750_allowlist	ceab89642386eb0969a883cc9ee4a161	{"decision": "PASS", "kernel_id": "K_demo_v1_2750_allowlist", "param_hash": "ceab89642386eb0969a883cc9ee4a161", "needs_one_bit": false, "obligations_satisfied": ["min_info"]}
4	2025-09-17 03:30:33.348872+00	3641aebb01599e693ac025319d285b7083b411a59925c263559e46c9ab50d77e	K_demo_v1_2750_allowlist	a19fa3a40b3ef8ee03bf782d159348da	{"decision": "PASS", "kernel_id": "K_demo_v1_2750_allowlist", "param_hash": "a19fa3a40b3ef8ee03bf782d159348da", "needs_one_bit": false, "obligations_satisfied": ["privacy_ok"]}
5	2025-09-17 03:30:33.467226+00	1f945b72f1cc0da284b4400eb7ba081fa705f8027b3f810417861aadc46b32f3	K_demo_v1_2750_allowlist	a19fa3a40b3ef8ee03bf782d159348da	{"decision": "HOLD_HUMAN", "kernel_id": "K_demo_v1_2750_allowlist", "param_hash": "a19fa3a40b3ef8ee03bf782d159348da", "needs_one_bit": false, "obligations_satisfied": ["budget_ok"]}
6	2025-09-17 03:30:33.479646+00	a4e232752afb7c7ebca1961f91e463df15bdbdfc82ea864155ecf0571887ab6b	K_demo_v1_2750_allowlist	a19fa3a40b3ef8ee03bf782d159348da	{"decision": "PASS", "kernel_id": "K_demo_v1_2750_allowlist", "param_hash": "a19fa3a40b3ef8ee03bf782d159348da", "needs_one_bit": false, "obligations_satisfied": ["min_info"]}
\.


--
-- Data for Name: params_allowlist; Type: TABLE DATA; Schema: cm; Owner: cm
--

COPY cm.params_allowlist (country) FROM stdin;
US
CA
GB
DE
\.


--
-- Data for Name: params_thresholds; Type: TABLE DATA; Schema: cm; Owner: cm
--

COPY cm.params_thresholds (k, v) FROM stdin;
amount_max	2100
\.


--
-- Name: anchors_id_seq; Type: SEQUENCE SET; Schema: cm; Owner: cm
--

SELECT pg_catalog.setval('cm.anchors_id_seq', 1, true);


--
-- Name: decision_ledger_id_seq; Type: SEQUENCE SET; Schema: cm; Owner: cm
--

SELECT pg_catalog.setval('cm.decision_ledger_id_seq', 6, true);


--
-- Name: anchors anchors_pkey; Type: CONSTRAINT; Schema: cm; Owner: cm
--

ALTER TABLE ONLY cm.anchors
    ADD CONSTRAINT anchors_pkey PRIMARY KEY (id);


--
-- Name: decision_ledger decision_ledger_pkey; Type: CONSTRAINT; Schema: cm; Owner: cm
--

ALTER TABLE ONLY cm.decision_ledger
    ADD CONSTRAINT decision_ledger_pkey PRIMARY KEY (id);


--
-- Name: params_allowlist params_allowlist_pkey; Type: CONSTRAINT; Schema: cm; Owner: cm
--

ALTER TABLE ONLY cm.params_allowlist
    ADD CONSTRAINT params_allowlist_pkey PRIMARY KEY (country);


--
-- Name: params_thresholds params_thresholds_pkey; Type: CONSTRAINT; Schema: cm; Owner: cm
--

ALTER TABLE ONLY cm.params_thresholds
    ADD CONSTRAINT params_thresholds_pkey PRIMARY KEY (k);


--
-- Name: decision_ledger_bundle_gin; Type: INDEX; Schema: cm; Owner: cm
--

CREATE INDEX decision_ledger_bundle_gin ON cm.decision_ledger USING gin (bundle jsonb_path_ops);


--
-- Name: decision_ledger_kernel_param_idx; Type: INDEX; Schema: cm; Owner: cm
--

CREATE INDEX decision_ledger_kernel_param_idx ON cm.decision_ledger USING btree (kernel_id, param_hash);


--
-- Name: decision_ledger_proof_id_idx; Type: INDEX; Schema: cm; Owner: cm
--

CREATE INDEX decision_ledger_proof_id_idx ON cm.decision_ledger USING btree (proof_id);


--
-- Name: decision_ledger_ts_idx; Type: INDEX; Schema: cm; Owner: cm
--

CREATE INDEX decision_ledger_ts_idx ON cm.decision_ledger USING btree (ts);


--
-- PostgreSQL database dump complete
--

\unrestrict 4xR5jXiIl6ESDhIerFnRfERw6o51kDtQCEtLT0fg205waYwgJvRDn3BjJjMLkTt

