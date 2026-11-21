import io
import json
import zipfile
import pytest
from drum_midi.source_offer import build_source_archive, is_source_path


def test_documented_screenshot_is_distributable_source_material():
    assert is_source_path('docs/images/web-editor.png')
    assert not is_source_path('data/private.png')


def test_source_archive_contains_only_manifested_application_source(tmp_path):
    source=tmp_path/"src/drum_midi/webui_static/app.js";source.parent.mkdir(parents=True);source.write_text("actual app source")
    (tmp_path/"LICENSE").write_text("license")
    (tmp_path/".env").write_text("secret")
    private=tmp_path/"docs/superpowers/private.md";private.parent.mkdir(parents=True);private.write_text("private")
    manifest=tmp_path/"manifest.json";manifest.write_text(json.dumps({"files":["LICENSE","src/drum_midi/webui_static/app.js"]}))
    payload=build_source_archive(tmp_path,manifest)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert archive.read("grooveforge-source/src/drum_midi/webui_static/app.js")==b"actual app source"
        assert not any(".env" in p or "superpowers" in p for p in archive.namelist())


@pytest.mark.parametrize("name",[".env","../outside.py","/absolute.py","docs/superpowers/private.md","src/drum_midi/_vendor/weights.pth","data/st_stats.json","src/../private.py","src\\private.py"])
def test_forbidden_source_paths_fail_closed(name):
    assert not is_source_path(name)


def test_source_offer_rejects_a_symlink_even_to_a_secret_inside_root(tmp_path):
    secret=tmp_path/".env";secret.write_text("secret")
    link=tmp_path/"README.md"
    try:link.symlink_to(secret)
    except OSError:pytest.skip("Host does not allow symlinks")
    manifest=tmp_path/"manifest.json";manifest.write_text(json.dumps({"files":["README.md"]}))
    with pytest.raises(ValueError):build_source_archive(tmp_path,manifest)
