from tempfile import NamedTemporaryFile

import polars as pl
from polars.testing import assert_frame_equal

from etl_components.sqlite_connector import (
    SQLiteConnector,
    _get_insert_query,
    _get_retrieve_query,
)


def test_get_insert_query() -> None:
    """Test if _get_insert_query() works as intended."""
    table = "fiets"
    columns = ["kleur", "zadel", "wielen"]
    query = "INSERT OR IGNORE INTO fiets (kleur, zadel, wielen) VALUES (:kleur, :zadel, :wielen)"
    assert _get_insert_query(table, columns) == query


def test_get_retrieve_query() -> None:
    """Test if _get_retrieve_query() works as intended."""
    table = "fiets"
    columns = ["kleur", "zadel", "wielen"]
    query = "SELECT id as fiets_id, kleur, zadel, wielen FROM fiets"
    assert _get_retrieve_query(table, columns) == query


def test_integration() -> None:
    """Test if SQLiteConnetor works in integration setting."""
    schema = """
    CREATE TABLE IF NOT EXISTS kleur (
        id INTEGER PRIMARY KEY,
        kleur TEXT UNIQUE
    );


    CREATE TABLE IF NOT EXISTS eigenaar (
        id INTEGER PRIMARY KEY,
        eigenaar TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS voertuig_type (
        id INTEGER PRIMARY KEY,
        type TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS voertuig (
        id INTEGER PRIMARY KEY,
        voertuig_type_id INT REFERENCES voertuig_type (id),
        kleur_id INT REFERENCES kleur (id),
        UNIQUE (voertuig_type_id, kleur_id)
    );

    CREATE TABLE IF NOT EXISTS voertuig_eigenaar (
        voertuig_id INT REFERENCES voertuig (id),
        eigenaar_id INT REFERENCES eigenaar (id),
        sinds TEXT,
        UNIQUE (voertuig_id, eigenaar_id)
    );
    """
    compare_query = """
    SELECT eigenaar, type, kleur, sinds
    FROM eigenaar
    JOIN voertuig_eigenaar ON voertuig_eigenaar.eigenaar_id = eigenaar.id
    JOIN voertuig ON voertuig_eigenaar.voertuig_id = voertuig.id
    JOIN voertuig_type ON voertuig.voertuig_type_id = voertuig_type.id
    JOIN kleur ON voertuig.kleur_id = kleur.id
    """
    data = pl.DataFrame(
        {
            "eigenaar": ["Dave", "Luc", "Erwin", "Erwin"],
            "soort_voertuig": ["auto", "fiets", "auto", "motor"],
            "kleur": ["rood", "blauw", "zilver", "rood"],
            "sinds": ["2022-01-18", "2019-03-23", "2021-03-05", "2018-03-05"],
        }
    )

    # testing against a temporary file instead of in memory, since
    # real use probably won't be in memory either.
    with NamedTemporaryFile(suffix=".db") as file:
        with SQLiteConnector(file.name) as sqlite:
            with sqlite.cursor() as cursor:
                cursor.executescript(schema)

            sqlite.update_schema()
            sqlite.load(
                data,
                compare_query,
                columns={"soort_voertuig": "type"},
            )

        # Testing if the data were saved to the file as well
        with SQLiteConnector(file.name) as sqlite:  # noqa: SIM117
            with sqlite.cursor() as cursor:
                cursor.execute(compare_query)
                db_data = pl.DataFrame(cursor.fetchall())

        assert_frame_equal(
            data.rename({"soort_voertuig": "type"}),
            db_data,
            check_row_order=False,
            check_column_order=False,
        )
