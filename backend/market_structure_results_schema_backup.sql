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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: market_structure_results; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.market_structure_results (
    id uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    backtest_id uuid NOT NULL,
    symbol character varying(10) NOT NULL,
    param_holding_period integer NOT NULL,
    param_gap_threshold numeric(5,2) NOT NULL,
    param_stop_loss numeric(5,2),
    param_take_profit numeric(5,2),
    start_date date NOT NULL,
    end_date date NOT NULL,
    total_return numeric(10,2) NOT NULL,
    win_rate numeric(5,2) NOT NULL,
    total_trades integer NOT NULL,
    winning_trades integer NOT NULL,
    losing_trades integer NOT NULL,
    avg_return numeric(10,2),
    median_return numeric(10,2),
    std_dev numeric(10,2),
    min_return numeric(10,2),
    max_return numeric(10,2),
    sharpe_ratio numeric(10,4),
    sortino_ratio numeric(10,4),
    max_drawdown numeric(10,2),
    avg_holding_days numeric(10,2),
    avg_winning_return numeric(10,2),
    avg_losing_return numeric(10,2),
    best_trade numeric(10,2),
    worst_trade numeric(10,2),
    profit_factor numeric(10,2),
    total_profit numeric(12,2),
    total_loss numeric(12,2),
    time_in_market numeric(5,2),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms integer,
    status character varying(20) DEFAULT 'completed'::character varying,
    error_message text,
    CONSTRAINT chk_date_range CHECK ((start_date <= end_date)),
    CONSTRAINT chk_gap_threshold CHECK ((param_gap_threshold >= (0)::numeric)),
    CONSTRAINT chk_holding_period CHECK ((param_holding_period > 0)),
    CONSTRAINT chk_stop_loss CHECK (((param_stop_loss IS NULL) OR (param_stop_loss > (0)::numeric))),
    CONSTRAINT chk_take_profit CHECK (((param_take_profit IS NULL) OR (param_take_profit > (0)::numeric))),
    CONSTRAINT chk_time_in_market CHECK (((time_in_market >= (0)::numeric) AND (time_in_market <= (100)::numeric))),
    CONSTRAINT chk_trade_counts CHECK (((total_trades >= 0) AND (winning_trades >= 0) AND (losing_trades >= 0) AND (total_trades = (winning_trades + losing_trades)))),
    CONSTRAINT chk_win_rate CHECK (((win_rate >= (0)::numeric) AND (win_rate <= (100)::numeric)))
);


ALTER TABLE public.market_structure_results OWNER TO postgres;

--
-- Name: TABLE market_structure_results; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.market_structure_results IS 'Stores backtesting results for market structure analysis with detailed performance metrics';


--
-- Name: COLUMN market_structure_results.backtest_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_structure_results.backtest_id IS 'Unique identifier for the backtest run';


--
-- Name: COLUMN market_structure_results.param_holding_period; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_structure_results.param_holding_period IS 'Number of days to hold each position';


--
-- Name: COLUMN market_structure_results.param_gap_threshold; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_structure_results.param_gap_threshold IS 'Minimum gap percentage to trigger entry';


--
-- Name: COLUMN market_structure_results.param_stop_loss; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_structure_results.param_stop_loss IS 'Stop loss percentage (optional)';


--
-- Name: COLUMN market_structure_results.param_take_profit; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_structure_results.param_take_profit IS 'Take profit percentage (optional)';


--
-- Name: COLUMN market_structure_results.profit_factor; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_structure_results.profit_factor IS 'Ratio of gross profit to gross loss';


--
-- Name: COLUMN market_structure_results.time_in_market; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_structure_results.time_in_market IS 'Percentage of time positions were held';


--
-- Name: COLUMN market_structure_results.execution_time_ms; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_structure_results.execution_time_ms IS 'Time taken to run the backtest in milliseconds';


--
-- Name: market_structure_results market_structure_results_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.market_structure_results
    ADD CONSTRAINT market_structure_results_pkey PRIMARY KEY (id);


--
-- Name: idx_market_structure_backtest_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_structure_backtest_id ON public.market_structure_results USING btree (backtest_id);


--
-- Name: idx_market_structure_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_structure_created_at ON public.market_structure_results USING btree (created_at DESC);


--
-- Name: idx_market_structure_date_range; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_structure_date_range ON public.market_structure_results USING btree (start_date, end_date);


--
-- Name: idx_market_structure_params; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_structure_params ON public.market_structure_results USING btree (param_holding_period, param_gap_threshold, param_stop_loss, param_take_profit);


--
-- Name: idx_market_structure_performance; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_structure_performance ON public.market_structure_results USING btree (total_return DESC, sharpe_ratio DESC);


--
-- Name: idx_market_structure_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_structure_status ON public.market_structure_results USING btree (status);


--
-- Name: idx_market_structure_symbol; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_structure_symbol ON public.market_structure_results USING btree (symbol);


--
-- PostgreSQL database dump complete
--

