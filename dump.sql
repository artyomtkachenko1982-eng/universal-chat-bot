--
-- PostgreSQL database dump
--

\restrict KKQYzPu29sicLQvprGpZc1lEB9xMLVd8IwTfhLojSuBJoNGFpSsqK2g2bD4nbap

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

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
-- Name: ad_prices; Type: TABLE; Schema: public; Owner: bot_user
--

CREATE TABLE public.ad_prices (
    id integer NOT NULL,
    price_key character varying(50) NOT NULL,
    price_name character varying(200) NOT NULL,
    base_price double precision NOT NULL,
    surcharge_pct double precision NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.ad_prices OWNER TO bot_user;

--
-- Name: ad_prices_id_seq; Type: SEQUENCE; Schema: public; Owner: bot_user
--

CREATE SEQUENCE public.ad_prices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ad_prices_id_seq OWNER TO bot_user;

--
-- Name: ad_prices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: bot_user
--

ALTER SEQUENCE public.ad_prices_id_seq OWNED BY public.ad_prices.id;


--
-- Name: ad_requests; Type: TABLE; Schema: public; Owner: bot_user
--

CREATE TABLE public.ad_requests (
    id integer NOT NULL,
    platform character varying(20) NOT NULL,
    platform_user_id character varying(100) NOT NULL,
    text text NOT NULL,
    days integer NOT NULL,
    pin boolean NOT NULL,
    platform_target character varying(100) NOT NULL,
    total_price double precision NOT NULL,
    status character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    corrected_price double precision,
    admin_reply text,
    answered_at timestamp without time zone,
    dle_user_id integer,
    user_name character varying(100),
    ad_type character varying(20) DEFAULT 'feed'::character varying,
    image_path character varying(500),
    pin_days integer DEFAULT 0,
    article_eternal boolean DEFAULT false,
    article_opts character varying(100),
    article_fix_days integer DEFAULT 0,
    banner_size character varying(20) DEFAULT '728x90'::character varying,
    banner_placement character varying(20) DEFAULT 'in_news'::character varying,
    banner_months integer DEFAULT 1,
    banner_opts character varying(100),
    pin_platforms character varying(100),
    article_months integer DEFAULT 1
);


ALTER TABLE public.ad_requests OWNER TO bot_user;

--
-- Name: ad_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: bot_user
--

CREATE SEQUENCE public.ad_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ad_requests_id_seq OWNER TO bot_user;

--
-- Name: ad_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: bot_user
--

ALTER SEQUENCE public.ad_requests_id_seq OWNED BY public.ad_requests.id;


--
-- Name: admin_messages; Type: TABLE; Schema: public; Owner: bot_user
--

CREATE TABLE public.admin_messages (
    id integer NOT NULL,
    platform character varying(20) NOT NULL,
    platform_user_id character varying(100) NOT NULL,
    user_name character varying(100),
    topic character varying(50) NOT NULL,
    text text NOT NULL,
    status character varying NOT NULL,
    admin_reply text,
    created_at timestamp without time zone NOT NULL,
    answered_at timestamp without time zone,
    dle_user_id integer,
    sender_type character varying(10) DEFAULT 'user'::character varying
);


ALTER TABLE public.admin_messages OWNER TO bot_user;

--
-- Name: admin_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: bot_user
--

CREATE SEQUENCE public.admin_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.admin_messages_id_seq OWNER TO bot_user;

--
-- Name: admin_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: bot_user
--

ALTER SEQUENCE public.admin_messages_id_seq OWNED BY public.admin_messages.id;


--
-- Name: bot_users; Type: TABLE; Schema: public; Owner: bot_user
--

CREATE TABLE public.bot_users (
    id integer NOT NULL,
    platform character varying(20) NOT NULL,
    platform_user_id character varying(100) NOT NULL,
    dle_user_id integer,
    dle_username character varying(100),
    dle_group integer,
    session_token character varying(64),
    created_at timestamp without time zone NOT NULL,
    last_active timestamp without time zone NOT NULL
);


ALTER TABLE public.bot_users OWNER TO bot_user;

--
-- Name: bot_users_id_seq; Type: SEQUENCE; Schema: public; Owner: bot_user
--

CREATE SEQUENCE public.bot_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bot_users_id_seq OWNER TO bot_user;

--
-- Name: bot_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: bot_user
--

ALTER SEQUENCE public.bot_users_id_seq OWNED BY public.bot_users.id;


--
-- Name: news_suggestions; Type: TABLE; Schema: public; Owner: bot_user
--

CREATE TABLE public.news_suggestions (
    id integer NOT NULL,
    platform character varying(20) NOT NULL,
    platform_user_id character varying(100) NOT NULL,
    title character varying(300) NOT NULL,
    text text NOT NULL,
    status character varying NOT NULL,
    created_at timestamp without time zone NOT NULL,
    admin_reply text,
    answered_at timestamp without time zone,
    dle_user_id integer,
    user_name character varying(100),
    image_path character varying(500)
);


ALTER TABLE public.news_suggestions OWNER TO bot_user;

--
-- Name: news_suggestions_id_seq; Type: SEQUENCE; Schema: public; Owner: bot_user
--

CREATE SEQUENCE public.news_suggestions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.news_suggestions_id_seq OWNER TO bot_user;

--
-- Name: news_suggestions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: bot_user
--

ALTER SEQUENCE public.news_suggestions_id_seq OWNED BY public.news_suggestions.id;


--
-- Name: user_states; Type: TABLE; Schema: public; Owner: bot_user
--

CREATE TABLE public.user_states (
    id integer NOT NULL,
    platform character varying(20) NOT NULL,
    platform_user_id character varying(100) NOT NULL,
    state character varying(50) NOT NULL,
    data text,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.user_states OWNER TO bot_user;

--
-- Name: user_states_id_seq; Type: SEQUENCE; Schema: public; Owner: bot_user
--

CREATE SEQUENCE public.user_states_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_states_id_seq OWNER TO bot_user;

--
-- Name: user_states_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: bot_user
--

ALTER SEQUENCE public.user_states_id_seq OWNED BY public.user_states.id;


--
-- Name: user_stats; Type: TABLE; Schema: public; Owner: bot_user
--

CREATE TABLE public.user_stats (
    id integer NOT NULL,
    platform character varying(20) NOT NULL,
    platform_user_id character varying(100) NOT NULL,
    total_searches integer NOT NULL,
    total_ai_questions integer NOT NULL,
    total_downloads integer NOT NULL,
    suggested_news integer NOT NULL,
    posts_count integer NOT NULL,
    comments_count integer NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.user_stats OWNER TO bot_user;

--
-- Name: user_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: bot_user
--

CREATE SEQUENCE public.user_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_stats_id_seq OWNER TO bot_user;

--
-- Name: user_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: bot_user
--

ALTER SEQUENCE public.user_stats_id_seq OWNED BY public.user_stats.id;


--
-- Name: ad_prices id; Type: DEFAULT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.ad_prices ALTER COLUMN id SET DEFAULT nextval('public.ad_prices_id_seq'::regclass);


--
-- Name: ad_requests id; Type: DEFAULT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.ad_requests ALTER COLUMN id SET DEFAULT nextval('public.ad_requests_id_seq'::regclass);


--
-- Name: admin_messages id; Type: DEFAULT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.admin_messages ALTER COLUMN id SET DEFAULT nextval('public.admin_messages_id_seq'::regclass);


--
-- Name: bot_users id; Type: DEFAULT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.bot_users ALTER COLUMN id SET DEFAULT nextval('public.bot_users_id_seq'::regclass);


--
-- Name: news_suggestions id; Type: DEFAULT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.news_suggestions ALTER COLUMN id SET DEFAULT nextval('public.news_suggestions_id_seq'::regclass);


--
-- Name: user_states id; Type: DEFAULT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.user_states ALTER COLUMN id SET DEFAULT nextval('public.user_states_id_seq'::regclass);


--
-- Name: user_stats id; Type: DEFAULT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.user_stats ALTER COLUMN id SET DEFAULT nextval('public.user_stats_id_seq'::regclass);


--
-- Data for Name: ad_prices; Type: TABLE DATA; Schema: public; Owner: bot_user
--

COPY public.ad_prices (id, price_key, price_name, base_price, surcharge_pct, updated_at) FROM stdin;
3	feed_all	Объявление все площадки	1500	0	2026-05-12 08:48:46.586049
5	feed_pin_all	Закрепление все площадки 2дн	1500	0	2026-05-12 08:48:46.586049
4	feed_pin_single	Закрепление 1 площадка 2дн	300	0	2026-05-12 12:32:39.4779
7	banner_in_news	Баннер в новостях мес	3000	0.3	2026-05-12 12:34:36.328863
6	banner_all_pages	Баннер сквозной мес	5000	0.3	2026-05-12 12:34:36.333172
9	article_fixation	Статья фиксация день	100	0	2026-05-12 12:34:47.70581
10	article_eternal	Статья вечная базовая	20000	0.3	2026-05-12 13:45:50.100779
8	article_base	Статья базовая	2950	0.3	2026-05-12 13:46:22.858366
2	feed_site	Объявление 1 площадка	900	0	2026-05-15 12:10:37.962408
\.


--
-- Data for Name: ad_requests; Type: TABLE DATA; Schema: public; Owner: bot_user
--

COPY public.ad_requests (id, platform, platform_user_id, text, days, pin, platform_target, total_price, status, created_at, corrected_price, admin_reply, answered_at, dle_user_id, user_name, ad_type, image_path, pin_days, article_eternal, article_opts, article_fix_days, banner_size, banner_placement, banner_months, banner_opts, pin_platforms, article_months) FROM stdin;
3	web	vasya	Куплю компрессор 4ВМ10, можно б/у	1	f	site	500	approved	2026-05-10 17:58:11.543714	450	\N	2026-05-10 17:58:49.129851	\N	\N	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
4	web	vasya	Требуются машинисты компрессорных установок, з/п от 80т	1	t	all	2800	rejected	2026-05-10 17:58:11.577149	\N	\N	2026-05-10 17:58:49.163133	\N	\N	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
26	web	widget-1778520705230	[СТАТЬЯ] Опции: нерелевантная +30%, фиксация 1дн..\nТекст: жопа	0	f	site	4600	rejected	2026-05-11 17:34:03.849341	\N	\N	2026-05-11 17:34:34.65669	286601	test_login	article	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
25	web	widget-1778520705230	[БАННЕР 336x228] Размещение: сквозное, 3 мес. Опции: пожелания +30%.\nОписание: жопа	3	f	site	11700	approved	2026-05-11 17:33:15.531022	\N	\N	2026-05-11 17:34:41.281976	286601	test_login	banner	/static/ad_images/b54836419dd244fb801801d095b3365e.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
27	web	widget-1778579946935	ntncjdjut	1	t	site,vk	1275	new	2026-05-12 10:01:12.434107	\N	\N	\N	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
5	web	test123	Тестовая реклама от обычного юзера	3	t	all	1500	approved	2026-05-11 12:36:57.894952	\N	\N	2026-05-11 12:37:34.93903	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
6	web	widget-1778503985063	тестовая реклама	1	f	сайт,tg,vk	500	approved	2026-05-11 12:54:50.01027	1500	\N	2026-05-11 12:55:43.787764	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
9	web	test123	Тест: гибкое закрепление	3	t	site,tg	2375	new	2026-05-11 13:52:24.348368	\N	\N	\N	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
10	web	test123	Без закрепления	1	f	site	500	new	2026-05-11 13:52:57.637457	\N	\N	\N	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
8	web	widget-1778507328570	тестовая реклама 4	10	t	site,vk	6325	approved	2026-05-11 13:50:04.586197	\N	\N	2026-05-11 14:17:10.792965	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
11	web	widget-1778507597469	ntcnjdfz htrkfvf 5	4	t	tg,vk	2775	approved	2026-05-11 13:53:53.555143	\N	\N	2026-05-11 14:17:23.141562	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
12	web	widget_test	Testovoe ob'yavlenie v lente ot test_login. Prodaem turbiny TD-06.	3	t	all	3750	new	2026-05-11 16:28:04.971977	\N	\N	\N	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
13	web	widget_test	Zakaz bannera dlya razmescheniya v shapke sayta. Razmer 728x90. Ssylka na katalog turbin.	0	f	site	0	new	2026-05-11 16:28:30.753331	\N	\N	\N	286601	test_login	banner	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
14	web	widget_test	test	1	f	site	0	approved	2026-05-11 16:29:02.472303	\N	\N	2026-05-11 16:31:18.137719	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
7	web	widget-1778506891011	тестовая реклама 2	3	f	site,vk,max	3000	rejected	2026-05-11 13:42:56.077762	\N	\N	2026-05-11 16:32:26.269513	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
30	web	widget-1778582591441	тест	1	t	site	970	approved	2026-05-12 10:47:34.96155	1500	\N	2026-05-12 11:08:59.036165	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
31	web	widget-1778584093879	ntcnjdjt j,]zdktybt 	1	t	vk,tg	1940	approved	2026-05-12 11:09:50.30432	2000	\N	2026-05-12 11:11:31.541292	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
35	web	widget-1778587909914	111122233334444	4	t	vk,max	8260	approved	2026-05-12 12:12:31.799948	8000	\N	2026-05-12 12:13:45.539165	286601	test_login	feed	\N	5	f	\N	0	728x90	in_news	1	\N	\N	1
34	web	test_web	Тест финальный 2	7	t	site,tg,vk	17370	approved	2026-05-12 12:09:40.839195	8000	\N	2026-05-12 12:23:03.028102	286601	test_login	feed	\N	3	f	\N	0	728x90	in_news	1	\N	\N	1
36	web	widget-1778588796062	снова тест объявления 	10	t	site	9200	approved	2026-05-12 12:27:02.68181	2000	\N	2026-05-12 12:27:52.462382	286601	test_login	feed	\N	8	f	\N	0	728x90	in_news	1	\N	\N	1
39	web	widget-1778589335743	[СТАТЬЯ] Опции: нерелевантная +30%, фиксация 5дн..\nТекст: текст	0	f	site	4205	approved	2026-05-12 12:38:15.442381	4000	\N	2026-05-12 12:39:02.594287	286601	test_login	article	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
38	web	widget-1778589335743	[БАННЕР 300x600] Размещение: сквозное, 1 мес. Опции: главная +30%, нерелевантная +30%.\nОписание: прото сетств катринка ваша 	1	f	site	8000	approved	2026-05-12 12:37:10.112087	\N	\N	2026-05-12 12:40:36.22248	286601	test_login	banner	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
40	web	test123	[СТАТЬЯ ВЕЧНАЯ] Тест	0	f	site	13000	approved	2026-05-12 13:22:42.548301	\N	\N	2026-05-12 13:25:01.734796	\N	\N	article	\N	0	t	\N	0	728x90	in_news	1	\N	\N	1
24	web	test_banner	[БАННЕР 728x90] Размещение: сквозное, 3 мес. Ссылка на каталог. Цена: 9000 руб.	3	f	site	9000	approved	2026-05-11 17:21:02.189248	7000	\N	2026-05-12 13:34:53.635488	286601	test_login	banner	/static/ad_images/test_banner.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
41	web	widget-1778592320538	[СТАТЬЯ ВЕЧНАЯ] Опции: вечная.\nТекст: втйвгаиргифаилфдаиы	0	f	site	10000	approved	2026-05-12 13:26:26.55426	\N	\N	2026-05-12 13:26:51.261965	286601	test_login	article	\N	0	t	\N	0	728x90	in_news	1	\N	\N	1
37	web	widget-1778589214495	тествулповлодйтмдотмдо	4	t	vk	4100	rejected	2026-05-12 12:34:05.163084	\N	\N	2026-05-13 11:06:23.33306	286601	test_login	feed	\N	3	f	\N	0	728x90	in_news	1	\N	\N	1
32	web	test_web	Тест 3 площадки 5 дней	5	t	site,tg,vk	6980	approved	2026-05-12 11:39:01.21858	7000	\N	2026-05-13 14:40:04.08352	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
29	web	widget-1778582591441	тесттл	1	t	vk	970	approved	2026-05-12 10:46:29.775965	1000	\N	2026-05-13 14:40:26.976556	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
18	web	widget_test	Banner s kartinkoy dlya testa.	1	f	all	0	rejected	2026-05-11 16:48:12.412905	\N	\N	2026-05-13 14:46:51.69551	286601	test_login	banner	/static/ad_images/c553c4c5d0de4b71a1e4dbdf3e7085ae.html	0	f	\N	0	728x90	in_news	1	\N	\N	1
17	web	widget_test	Zakaz bannera dlya razmescheniya v shapke sayta. Razmer 728x90. Ssylka na katalog turbin.	0	f	site	0	in_progress	2026-05-11 16:47:25.286739	\N	\N	\N	286601	test_login	banner	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
28	web	widget-1778581687778	ntcn	1	t	site,vk,tg	2380	rejected	2026-05-12 10:29:11.623781	\N	\N	2026-05-13 14:41:07.438995	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
22	web	test123	Статья о турбинах: обзор и сравнение моделей. Фиксация 30 дней. Цена: 5000 руб.	30	f	site	5000	rejected	2026-05-11 17:18:18.233022	\N	\N	2026-05-13 14:46:46.628591	286601	test_login	article	/static/ad_images/test_article.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
33	web	test_web	Тест 3 площ 7 дней 3 пина	7	t	site,tg,vk	17370	approved	2026-05-12 12:07:43.082822	18000	\N	2026-05-13 14:39:17.337655	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
16	web	widget_test	Testovoe ob'yavlenie v lente ot test_login. Prodaem turbiny TD-06.	3	t	all	3750	in_progress	2026-05-11 16:47:25.253018	\N	\N	\N	286601	test_login	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
19	web	widget-1778518204986	тестовфй текст 	0	f	site	0	in_progress	2026-05-11 16:52:20.846855	\N	\N	\N	286601	test_login	banner	/static/ad_images/d100c1a6fa534a358b8018918fc315c3.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
15	web	widget-1778517176661	баннер	0	f	site	0	in_progress	2026-05-11 16:34:40.917469	\N	\N	\N	286601	test_login	banner	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
20	web	widget-1778518521093	ntcnjdfz cnfnmz 4	0	f	site	0	in_progress	2026-05-11 16:55:56.465531	\N	\N	\N	286601	test_login	banner	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
23	web	test_banner	[СТАТЬЯ] Обзор турбин: сравнение моделей. Фиксация 30 дней. Цена: 5000 руб.	30	f	site	5000	approved	2026-05-11 17:20:42.584603	4000	\N	2026-05-12 13:33:08.296319	286601	test_login	article	/static/ad_images/test_article.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
42	web	widget-1778592433701	[СТАТЬЯ] Опции: нерелевантная +30%.\nТекст: ауыафспупцпцкпуспцускпцкпуцспееку	0	f	site	3705	approved	2026-05-12 13:38:28.727282	3500	\N	2026-05-12 13:38:52.144285	286601	test_login	article	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
43	web	widget-1778592433701	[СТАТЬЯ ВЕЧНАЯ] Опции: нерелевантная +30%, вечная.\nТекст: 12 тестовыцшшз 12у3 	0	f	site	13000	approved	2026-05-12 13:39:26.904536	12000	\N	2026-05-12 13:39:44.433269	286601	test_login	article	\N	0	t	\N	0	728x90	in_news	1	\N	\N	1
21	web	test123	[БАННЕР 728x90] Размещение: сквозное, 3 мес. Ссылка на каталог турбин. Цена: 9000 руб.	3	f	site	9000	approved	2026-05-11 17:18:02.000945	\N	\N	2026-05-13 14:46:42.090734	286601	test_login	banner	/static/ad_images/test_banner.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
53	web	widget-1778771797080	привет	1	t	site	1100	in_progress	2026-05-14 15:18:02.891057	\N	\N	\N	286601	test_login	feed	/static/ad_images/3e7cec0439784e45af045210a60a5075.jpg	1	f	\N	0	728x90	in_news	1	\N	\N	1
44	vk	3907146	тесовое объяаоление из вк	2	t	tg, vk	5000	approved	2026-05-14 09:17:03.070045	\N	\N	2026-05-14 09:20:29.153088	\N	\N	feed	\N	3	f	\N	0	728x90	in_news	1	\N	\N	1
47	vk	3907146	[БАННЕР 336x228] Размещение: сквозное, 1 мес.\nОписание: тест	1	f	site	6500	approved	2026-05-14 11:48:51.97536	\N	\N	2026-05-14 11:59:34.398622	\N	\N	banner	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
46	vk	3907146	тест объявл	1	f	all	3200	approved	2026-05-14 11:17:17.606923	\N	\N	2026-05-14 12:20:42.521897	\N	\N	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
49	vk	3907146	[СТАТЬЯ] Опции: нерелевантная\nТекст: vadfafaadfad	0	f	site	3835	rejected	2026-05-14 13:04:09.128981	\N	\N	2026-05-14 13:41:55.45877	286601	\N	article	/static/ad_images/95a00e9e0ea8414f9d6505bb0caafd0b.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
48	vk	3907146	[СТАТЬЯ] Опции: базовая\nТекст: В Финляндии начали использовать тепловую энергию ЦОД для теплоснабжения	0	f	site	2950	rejected	2026-05-14 13:03:23.816582	\N	\N	2026-05-14 13:42:02.168458	286601	\N	article	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
50	vk	3907146	тевыотсытствжыстыжв	1	f	tg	800	in_progress	2026-05-14 14:37:43.965952	\N	\N	\N	286601	\N	feed	/static/ad_images/04194a2eea7f44889d02a5ebd960d7e2.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
51	web	widget-1778771797080	привет	1	t	site	1100	approved	2026-05-14 15:17:36.871089	\N	\N	2026-05-14 15:27:16.403899	286601	test_login	feed	/static/ad_images/3e7cec0439784e45af045210a60a5075.jpg	1	f	\N	0	728x90	in_news	1	\N	\N	1
45	vk	3907146	[СТАТЬЯ] Опции: нерелевантная\nТекст: тесовая статья	0	f	site	3835	rejected	2026-05-14 10:38:17.749757	\N	\N	2026-05-15 10:36:10.025476	\N	\N	article	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
54	vk	3907146	жопа	6	f	site	4800	in_progress	2026-05-15 12:09:12.473474	\N	\N	\N	286601	test_login	feed	/static/ad_images/efdfba49d26d4f9dbc72bae417e0485c.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
52	web	widget-1778771797080	привет	1	t	site	1100	in_progress	2026-05-14 15:17:55.083365	\N	\N	\N	286601	test_login	feed	/static/ad_images/3e7cec0439784e45af045210a60a5075.jpg	1	f	\N	0	728x90	in_news	1	\N	\N	1
60	test	test_002	Масло Mobil для турбин. 20л канистры. Доставка по всей России. Опт и розница.	14	f	site,tg	25200	in_progress	2026-05-15 09:15:00	\N	\N	\N	999001	Сергей Кузнецов	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
57	test	test_001	Продам запчасти для ГТК-10-4. Насосы, форсунки, фильтры. Всё в наличии, отдам дёшево.	7	t	site,tg,vk	21600	in_progress	2026-05-15 10:23:00	\N	\N	\N	286601	Алексей Маслов	feed	\N	3	f	\N	0	728x90	in_news	1	\N	\N	1
59	test	test_001	[СТАТЬЯ] Опции: нерелевантная, фиксация 5дн.\\nТекст: Полный гайд по выбору масла для турбины ГТК-10-4. Какое масло заливать, как часто менять, на что обратить внимание. Личный опыт эксплуатации.	0	f	site	4335	in_progress	2026-05-15 12:30:00	\N	\N	\N	286601	test_login	article	\N	0	f	not_relevant,fixation	5	728x90	in_news	1	\N	\N	1
56	web	widget-1778848762438	[БАННЕР 300x600] Размещение: сквозное, 2 мес. Опции: главная +30%, нерелевантная +30%.\nОписание: гужульбэ	2	f	site	16000	approved	2026-05-15 12:47:08.091903	\N	\N	2026-05-17 18:14:57.755811	286601	test_login	banner	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
55	web	widget-1778848762438	[БАННЕР 336x228] Размещение: сквозное, 1 мес. Опции: главная +30%, нерелевантная +30%.\nОписание: отличный барена нах	1	f	site	8000	rejected	2026-05-15 12:40:13.075802	\N	\N	2026-05-17 18:16:38.817343	286601	test_login	banner	/static/ad_images/af6027e638ec44ad87bb44f6b3ece50c.jpg	0	f	\N	0	728x90	in_news	1	\N	\N	1
58	test	test_001	[БАННЕР 728x90] Размещение: сквозное, 3 мес. Опции: главная +30%, нерелевантная +30%.\\nОписание: Студия ремонта турбин "ТурбоМастер". Профессиональный ремонт ГТК, ГПА, ТНА. Гарантия 1 год. Звоните!	3	f	site	24000	new	2026-05-15 11:45:00	\N	\N	\N	286601	test_login	banner	\N	0	f	\N	0	728x90	all_pages	3	home,not_relevant	\N	1
61	test	test_003	[СТАТЬЯ ВЕЧНАЯ] Опции: базовая.\\nТекст: История развития газотурбинных двигателей в СССР. От первых разработок до современных моделей. Уникальные архивные фото и чертежи.	0	f	site	20000	in_progress	2026-05-15 08:00:00	\N	\N	\N	999002	Дмитрий Волков	article	\N	0	t	\N	0	728x90	in_news	1	\N	\N	1
63	web	test	Тест исправления 422	2	t	site,vk,max	11700	in_progress	2026-05-15 14:21:29.497961	\N	\N	\N	286601	test_login	feed	\N	3	f	\N	0	728x90	in_news	1	\N	site	1
74	vk	3907146	[СТАТЬЯ ВЕЧНАЯ] Опции: нерелевантная, вечная\nТекст: тестовтйыдвфьл	0	f	site	26000	approved	2026-05-17 14:58:58.532367	15000	\N	2026-05-17 14:59:30.544779	286601	test_login	article	/static/ad_images/1aa763d19ffa46549cc43629edfafaf0.jpg	0	t	not_relevant	0	728x90	in_news	1	\N	\N	1
62	web	test	Тестовое объявление PRO mode	3	t	tg,vk,site	5000	rejected	2026-05-15 13:58:02.114021	\N	\N	2026-05-17 17:13:36.734618	286601	test_login	feed	\N	5	f	\N	0	728x90	in_news	1	\N	tg,vk	1
65	web	widget-1778855710487	гшненаекоеаеаек	5	t	all	19800	rejected	2026-05-15 14:35:37.05302	\N	\N	2026-05-15 14:36:09.834564	286601	test_login	feed	\N	3	f	\N	0	728x90	in_news	1	\N	site,vk	1
64	web	widget-1778855363056	еще раз тестовоге	3	t	all	13200	rejected	2026-05-15 14:30:18.162162	\N	\N	2026-05-15 14:36:14.100523	286601	test_login	feed	\N	2	f	\N	0	728x90	in_news	1	\N	\N	1
67	vk	286601	Продам ноутбук ASUS ROG. 16GB RAM, RTX 3060. Цена 85000р. Торг.	7	t	site,tg,vk,max	0	in_progress	2026-05-15 14:37:09.657254	\N	\N	\N	286601	test_login	feed	\N	3	f	\N	0	728x90	in_news	1	\N	site,vk	1
66	web	widget-1778855710487	444564са5п5и3п5	4	f	site,vk	7200	in_progress	2026-05-15 14:36:45.895513	\N	\N	\N	286601	test_login	feed	\N	0	f	\N	0	728x90	all_pages	1	\N	\N	1
69	telegram	1394784889	Ощошошишишт толщо	2	t	site,tg	4800	in_progress	2026-05-16 18:15:18.089435	\N	\N	\N	286601	test_login	feed	\N	2	f	\N	0	728x90	in_news	1	\N	site	1
70	telegram	1394784889	Гиигишишиш	1	f	tg	900	in_progress	2026-05-16 18:35:40.525752	\N	\N	\N	\N	Telegram user	feed	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
71	telegram	1394784889	Bfthbubivuvuvtc	1	t	tg	900	in_progress	2026-05-16 18:42:33.732451	\N	\N	\N	286601	test_login	feed	/static/ad_images/19c61033248e456ba026e2d256aca41c.jpg	3	f	\N	0	728x90	in_news	1	\N	\N	1
81	web	widget-1779123236460	тествовое обхявение 	2	t	vk,tg	3900	in_progress	2026-05-18 16:54:44.728096	\N	\N	\N	286601	test_login	feed	\N	1	f	\N	0	728x90	in_news	1	\N	vk	1
72	telegram	1394784889	Тестовое говно	2	t	max,tg	5400	approved	2026-05-16 18:44:37.240156	\N	\N	2026-05-17 18:16:10.379891	286601	test_login	feed	/static/ad_images/62a0560a86cc4b228106847a460a16ba.jpg	3	f	\N	0	728x90	in_news	1	\N	max,tg	1
73	vk	3907146	[БАННЕР 336×228] Размещение: в новостях, 1 мес.\nОписание: тепкмвамсыфв	1	f	site	3900	rejected	2026-05-17 14:57:11.326626	\N	\N	2026-05-17 14:57:33.448648	286601	test_login	banner	/static/ad_images/09b1a036c87647a39fc704d36fb0770b.jpg	0	f	\N	0	336×228	in_news	1	home	\N	1
80	web	widget-1779122463227	[СТАТЬЯ] Опции: фиксация 2дн..\nТекст: уцчаццацпакц	2	f	site	6300	in_progress	2026-05-18 16:41:24.700829	\N	\N	\N	286601	test_login	article	\N	0	f	fixation	2	728x90	in_news	1	\N	\N	2
75	web	widget-1779107586195	[СТАТЬЯ] Опции: нерелевантная +30%, фиксация 4дн..\nТекст: чауаукаукчук	0	f	site	4235	in_progress	2026-05-18 12:36:51.12746	\N	\N	\N	286601	test_login	article	\N	0	f	not_relevant,fixation	4	728x90	in_news	1	\N	\N	1
77	web	widget-1779113829284	[СТАТЬЯ]\nТекст: тетыотчшвтшцтшцгу	2	f	site	5900	in_progress	2026-05-18 14:18:04.200695	\N	\N	\N	286601	test_login	article	\N	0	f	\N	0	728x90	in_news	1	\N	\N	1
79	web	widget-1779122053215	[СТАТЬЯ] Опции: нерелевантная +30%, фиксация 3дн..\nТекст: !!!вычаукаукцац	3	f	site	12405	new	2026-05-18 16:34:58.639219	\N	\N	\N	286601	test_login	article	\N	0	f	not_relevant,fixation	3	728x90	in_news	1	\N	\N	1
78	web	widget-1779114828790	[СТАТЬЯ] Опции: фиксация 1дн..\nТекст: етсшывсшотыджс	2	f	site	6100	rejected	2026-05-18 14:36:46.699141	\N	\N	2026-05-18 18:29:39.611116	286601	test_login	article	\N	0	f	fixation	1	728x90	in_news	1	\N	\N	1
76	web	widget-1779107586195	[БАННЕР 336x228] Размещение: в новостях, 1 мес. Опции: главная +30%, нерелевантная +30%.\nОписание: счяуявуауу	1	f	site	4800	approved	2026-05-18 12:39:29.128531	\N	\N	2026-05-18 18:29:45.95386	286601	test_login	banner	/static/ad_images/1e155bc0ffe440cf93006bcd281d0869.jpg	0	f	\N	0	336x228	in_news	1	home,not_relevant	\N	1
68	vk	3907146	wj,k f,oecfoqexfq.xfiqewxfnqeifqf	2	t	site,tg,vk	8100	in_progress	2026-05-15 14:40:28.482823	\N	\N	\N	286601	test_login	feed	\N	3	f	\N	0	728x90	in_news	1	\N	site,tg,vk	1
\.


--
-- Data for Name: admin_messages; Type: TABLE DATA; Schema: public; Owner: bot_user
--

COPY public.admin_messages (id, platform, platform_user_id, user_name, topic, text, status, admin_reply, created_at, answered_at, dle_user_id, sender_type) FROM stdin;
44	web	widget-1779202159740	test_login	question	Снова рриает	answered	\N	2026-05-19 14:49:29.452024	2026-05-19 14:49:38.136225	286601	user
45	web	widget-1779202159740	test_login	question	У меня есть вопрос	answered	\N	2026-05-19 14:49:43.300689	2026-05-19 14:49:54.254479	286601	user
24	web	0	Иван Петров	question	Привет! Хочу получить доступ к закрытым разделам. Какие есть варианты?	answered	\N	2026-05-14 09:52:41.546245	\N	999001	user
27	web	999001	Админ	question	Здравствуйте, Иван! У нас есть несколько тарифов: 1 день — 195₽, 5 дней — 455₽, VIP — 2550₽, ПРЕМИУМ — 4990₽. Какой вас интересует?	answered	\N	2026-05-14 09:53:00.793455	\N	999001	admin
30	web	0	Иван Петров	question	Мне наверное 5 дней подойдёт. Это который за 455₽? Как оплатить?	answered	\N	2026-05-14 09:53:15.984785	\N	999001	user
32	web	999001	Админ	question	Да, 455₽ за 5 дней. Оплата пока через администратора вручную — я пришлю реквизиты после того как вы определитесь с форматом.	answered	\N	2026-05-14 09:53:36.410189	\N	999001	admin
25	web	0	Мария Сидорова	question	Добрый день! Я могу предложить интересную новость про турбины. Куда её отправить?	answered	\N	2026-05-14 09:52:41.589771	\N	999002	user
28	web	999002	Админ	question	Мария, здравствуйте! Отлично, мы всегда рады новостям. Отправьте через вкладку «Новость» — напишите заголовок и текст. Админ проверит и опубликует.	answered	\N	2026-05-14 09:53:00.836722	\N	999002	admin
\.


--
-- Data for Name: bot_users; Type: TABLE DATA; Schema: public; Owner: bot_user
--

COPY public.bot_users (id, platform, platform_user_id, dle_user_id, dle_username, dle_group, session_token, created_at, last_active) FROM stdin;
1	web	1	1	admin	\N	\N	2026-05-11 14:41:00.189123	2026-05-25 12:21:06.374965
2	web	286601	286601	test_login	\N	\N	2026-05-11 14:45:48.177201	2026-05-25 13:14:06.347942
\.


--
-- Data for Name: news_suggestions; Type: TABLE DATA; Schema: public; Owner: bot_user
--

COPY public.news_suggestions (id, platform, platform_user_id, title, text, status, created_at, admin_reply, answered_at, dle_user_id, user_name, image_path) FROM stdin;
3	web	vasya	Замена масла в винтовом компрессоре	Пошаговая инструкция по замене масла в винтовых компрессорах Atlas Copco	approved	2026-05-10 17:58:11.612666	\N	2026-05-10 17:58:49.199168	\N	\N	\N
4	web	vasya	Новый ГОСТ на сосуды под давлением	С 2026 года вводится обновленный ГОСТ на эксплуатацию сосудов под давлением	rejected	2026-05-10 17:58:11.644162	\N	2026-05-10 17:58:49.252056	\N	\N	\N
6	web	widget_test	Test GOST 2026	New standard approved. Publication needed.	approved	2026-05-11 15:51:59.628652	\N	2026-05-11 16:31:38.412219	286601	test_login	\N
7	vk	3907146	тестовая новость	темтовая нвость	rejected	2026-05-14 09:24:17.562849	\N	2026-05-14 09:24:51.201375	\N	\N	\N
10	vk	3907146	уолтажлуцтатуцдат	тетоысиыгщРАБЩЙТСЙКУИАБГЙРСУКСАЙСРАЙЩУ	rejected	2026-05-14 14:29:31.12771	\N	2026-05-14 14:29:56.269522	286601	\N	/static/ad_images/4ba03f49ba5d46c49570b57db14db25b.jpg
8	vk	3907146	тнств на отправку	дура	rejected	2026-05-14 11:26:42.158713	\N	2026-05-17 18:14:15.536112	\N	\N	\N
9	vk	3907146	сверху шапка, под ней табы, под табами пустое серое поле, а в самом низу три строчки с чатами»	В Финляндии начали использовать тепловую энергию ЦОД для теплоснабжения	rejected	2026-05-14 13:47:20.021546	\N	2026-05-18 18:29:55.350203	286601	\N	/static/ad_images/33845310c13745a38107083c2a71a0b2.jpg
\.


--
-- Data for Name: user_states; Type: TABLE DATA; Schema: public; Owner: bot_user
--

COPY public.user_states (id, platform, platform_user_id, state, data, updated_at) FROM stdin;
\.


--
-- Data for Name: user_stats; Type: TABLE DATA; Schema: public; Owner: bot_user
--

COPY public.user_stats (id, platform, platform_user_id, total_searches, total_ai_questions, total_downloads, suggested_news, posts_count, comments_count, updated_at) FROM stdin;
\.


--
-- Name: ad_prices_id_seq; Type: SEQUENCE SET; Schema: public; Owner: bot_user
--

SELECT pg_catalog.setval('public.ad_prices_id_seq', 10, true);


--
-- Name: ad_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: bot_user
--

SELECT pg_catalog.setval('public.ad_requests_id_seq', 81, true);


--
-- Name: admin_messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: bot_user
--

SELECT pg_catalog.setval('public.admin_messages_id_seq', 45, true);


--
-- Name: bot_users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: bot_user
--

SELECT pg_catalog.setval('public.bot_users_id_seq', 2, true);


--
-- Name: news_suggestions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: bot_user
--

SELECT pg_catalog.setval('public.news_suggestions_id_seq', 10, true);


--
-- Name: user_states_id_seq; Type: SEQUENCE SET; Schema: public; Owner: bot_user
--

SELECT pg_catalog.setval('public.user_states_id_seq', 1, false);


--
-- Name: user_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: bot_user
--

SELECT pg_catalog.setval('public.user_stats_id_seq', 1, false);


--
-- Name: ad_prices ad_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.ad_prices
    ADD CONSTRAINT ad_prices_pkey PRIMARY KEY (id);


--
-- Name: ad_prices ad_prices_price_key_key; Type: CONSTRAINT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.ad_prices
    ADD CONSTRAINT ad_prices_price_key_key UNIQUE (price_key);


--
-- Name: ad_requests ad_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.ad_requests
    ADD CONSTRAINT ad_requests_pkey PRIMARY KEY (id);


--
-- Name: admin_messages admin_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.admin_messages
    ADD CONSTRAINT admin_messages_pkey PRIMARY KEY (id);


--
-- Name: bot_users bot_users_pkey; Type: CONSTRAINT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.bot_users
    ADD CONSTRAINT bot_users_pkey PRIMARY KEY (id);


--
-- Name: news_suggestions news_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.news_suggestions
    ADD CONSTRAINT news_suggestions_pkey PRIMARY KEY (id);


--
-- Name: user_states user_states_pkey; Type: CONSTRAINT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.user_states
    ADD CONSTRAINT user_states_pkey PRIMARY KEY (id);


--
-- Name: user_stats user_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: bot_user
--

ALTER TABLE ONLY public.user_stats
    ADD CONSTRAINT user_stats_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict KKQYzPu29sicLQvprGpZc1lEB9xMLVd8IwTfhLojSuBJoNGFpSsqK2g2bD4nbap

