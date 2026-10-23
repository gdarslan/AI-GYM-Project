import pytest

from src.build_processed import PROCESSED, RAW, build

raw_missing = not (RAW / "fmendes-DAT263x-demos" / "exercise.csv").exists()


@pytest.mark.skipif(raw_missing, reason="raw data is not committed; download it first (see data/README.md)")
def test_build_reproduces_processed_files(tmp_path):
    """Done-when check: rebuilding from raw gives byte-identical processed files."""
    build(out_dir=tmp_path)
    for f in tmp_path.iterdir():
        committed = PROCESSED / f.name
        assert committed.exists(), f"{f.name} missing from data/processed - run python -m src.build_processed"
        assert f.read_bytes() == committed.read_bytes(), f"{f.name} differs from data/processed"


@pytest.mark.skipif(raw_missing, reason="raw data is not committed; download it first (see data/README.md)")
def test_backup_muscle_table_uses_same_muscle_names(tmp_path):
    """megaGym can only replace free-exercise-db if both use the same muscle vocabulary."""
    tables = build(out_dir=tmp_path)
    main = {m for col in ["primary_muscles", "secondary_muscles"]
            for cell in tables["free_exercise_db.csv"][col] for m in cell.split("; ") if m}
    backup = set(tables["megagym_exercises.csv"]["primary_muscle"])
    assert backup <= main, backup - main
