--
-- PostgreSQL database dump
--

-- Dumped from database version 14.18 (Debian 14.18-1.pgdg120+1)
-- Dumped by pg_dump version 14.18 (Debian 14.18-1.pgdg120+1)

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
-- Data for Name: market_structure_results; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.market_structure_results (id, backtest_id, symbol, param_holding_period, param_gap_threshold, param_stop_loss, param_take_profit, start_date, end_date, total_return, win_rate, total_trades, winning_trades, losing_trades, avg_return, median_return, std_dev, min_return, max_return, sharpe_ratio, sortino_ratio, max_drawdown, avg_holding_days, avg_winning_return, avg_losing_return, best_trade, worst_trade, profit_factor, total_profit, total_loss, time_in_market, created_at, execution_time_ms, status, error_message) FROM stdin;
73b22d25-7f22-4aa4-b92b-97c4ce5ae35f	521b9900-caa2-4ca4-9d33-f2aa929977fa	AGX	10	2.00	\N	\N	2025-08-04	2025-08-04	0.46	0.00	2	0	2	\N	\N	\N	\N	\N	0.0000	0.0000	0.00	\N	0.00	0.00	\N	\N	0.00	630.08	\N	\N	2025-08-17 13:19:50.434435+00	22193	completed	\N
51ee554f-8902-4820-8c9f-4a09a73ff5af	df8bccff-979f-4e9b-9aa6-d7d0cb762c42	APLD	10	2.00	\N	\N	2025-08-04	2025-08-04	-3.49	0.00	4	0	4	\N	\N	\N	\N	\N	0.0000	0.0000	0.00	\N	0.00	0.00	\N	\N	0.00	-4736.99	\N	\N	2025-08-17 13:20:00.134586+00	21891	completed	\N
\.


--
-- PostgreSQL database dump complete
--

