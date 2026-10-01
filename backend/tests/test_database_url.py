"""Hosted-database URL handling (no database needed)."""

from app.core.config import asyncpg_connect_args, normalise_async_url

SUPABASE_POOLER = "postgresql://postgres.abcdefgh:pa%23ss@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
SUPABASE_DIRECT = "postgresql://postgres:pw@db.abcdefgh.supabase.co:5432/postgres"


def test_supabase_pooler_url_gets_asyncpg_driver_ssl_and_no_statement_cache():
    url = normalise_async_url(SUPABASE_POOLER)
    assert url.startswith("postgresql+asyncpg://postgres.abcdefgh:pa%23ss@aws-0-eu-west-1.pooler.supabase.com:6543/postgres")
    assert "ssl=require" in url and "prepared_statement_cache_size=0" in url
    args = asyncpg_connect_args(url)
    assert args["statement_cache_size"] == 0
    assert args["prepared_statement_name_func"]() != args["prepared_statement_name_func"]()  # names never collide


def test_supabase_direct_url_keeps_prepared_statements():
    url = normalise_async_url(SUPABASE_DIRECT)
    assert "ssl=require" in url and "prepared_statement_cache_size" not in url
    assert asyncpg_connect_args(url) == {}


def test_libpq_options_are_translated_for_asyncpg():
    url = normalise_async_url("postgres://u:p@ep-x-pooler.us-east-2.aws.neon.tech/db?sslmode=require&channel_binding=require")
    assert url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in url and "channel_binding" not in url and "ssl=require" in url


def test_local_docker_url_is_left_alone():
    url = "postgresql+asyncpg://postgres:postgres_password@localhost:5432/fixmycampus_db"
    assert normalise_async_url(url) == url
    assert asyncpg_connect_args(url) == {}
