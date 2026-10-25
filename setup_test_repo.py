#!/usr/bin/env python3
"""Prepare a scratch SQLite Senzing repository for the test suite.

Reads SENZING_ENGINE_CONFIGURATION_JSON, creates the SQLite schema (from the
engine's RESOURCEPATH) if the database is empty, and installs the template
configuration with the requested data sources as the default config.
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from senzing_core import SzAbstractFactoryCore

SCHEMA_RELATIVE_PATH = Path("schema") / "szcore-schema-sqlite-create.sql"


def sqlite_path(connection):
    """Return the database file path from a sqlite3://user:pw@/path URI."""
    if not connection.startswith("sqlite3://"):
        raise ValueError(f"only sqlite3 connections are supported, got: {connection}")
    return Path(connection.split("@", 1)[1])


def create_schema(db_file, resource_path):
    """Create the Senzing schema in db_file unless it already has tables."""
    db_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_file) as conn:
        if conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]:
            return
        conn.executescript((Path(resource_path) / SCHEMA_RELATIVE_PATH).read_text())


def install_config(settings, data_sources):
    """Register the template config plus data_sources and make it the default."""
    factory = SzAbstractFactoryCore("setup_test_repo", settings)
    config_manager = factory.create_configmanager()
    if config_manager.get_default_config_id():
        return
    config = config_manager.create_config_from_template()
    registered = json.loads(config.get_data_source_registry())["DATA_SOURCES"]
    existing = {source["DSRC_CODE"] for source in registered}
    for data_source in data_sources:
        if data_source not in existing:
            config.register_data_source(data_source)
    config_id = config_manager.register_config(config.export(), "test suite config")
    config_manager.set_default_config_id(config_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-source",
        action="append",
        default=[],
        help="data source to register (repeatable; default: SZ_TEST_DATA_SOURCE or TEST)",
    )
    args = parser.parse_args()
    settings = os.getenv("SENZING_ENGINE_CONFIGURATION_JSON")
    if not settings:
        sys.exit("SENZING_ENGINE_CONFIGURATION_JSON must be set")
    config = json.loads(settings)
    create_schema(sqlite_path(config["SQL"]["CONNECTION"]), config["PIPELINE"]["RESOURCEPATH"])
    install_config(settings, args.data_source or [os.getenv("SZ_TEST_DATA_SOURCE", "TEST")])
    print("Test repository ready")


if __name__ == "__main__":
    main()
