
from pathlib import Path
from app.core.files import find_file_by_id, ensure_directory, get_file_extension

def test_find_file_by_id(tmp_path):
    # Setup
    test_id = "test_file"
    (tmp_path / f"{test_id}.pdf").touch()
    
    # Test finding existing file
    found = find_file_by_id(test_id, tmp_path, [".png", ".pdf"])
    assert found is not None
    assert found.name == f"{test_id}.pdf"
    
    # Test missing file
    found = find_file_by_id("missing", tmp_path, [".pdf"])
    assert found is None

def test_ensure_directory(tmp_path):
    target_dir = tmp_path / "subdir"
    assert not target_dir.exists()
    
    ensure_directory(target_dir)
    assert target_dir.exists()
    assert target_dir.is_dir()
    
    # Idempotency
    ensure_directory(target_dir)
    assert target_dir.exists()

def test_get_file_extension():
    assert get_file_extension(Path("file.pdf")) == ".pdf"
    assert get_file_extension(Path("FILE.PNG")) == ".png"
    assert get_file_extension(Path("path/to/file.txt")) == ".txt"
    assert get_file_extension(Path("no_ext")) == ""
