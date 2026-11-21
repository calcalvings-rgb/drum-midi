import io
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
import pytest
from drum_midi.webui import Handler


@pytest.fixture
def api(tmp_path):
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    server.token="integration-secret";server.input_dir=str(tmp_path);server.verbose=False
    server.notes=None;server.last_file=None
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def call(path,body=None,token="integration-secret",content_type="application/json",extra_headers=None):
        headers={"X-Auth-Token":token,"Content-Type":content_type}
        headers.update(extra_headers or {})
        if isinstance(body,dict):body=json.dumps(body).encode()
        request=urllib.request.Request(f"http://127.0.0.1:{server.server_port}"+path,data=body,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=5) as result:return result.status,dict(result.headers),result.read()
        except urllib.error.HTTPError as result:return result.code,dict(result.headers),result.read()
    yield call,tmp_path
    server.shutdown();server.server_close();thread.join(5)


def test_editor_export_import_real_http_and_auth(api):
    call,_=api
    body={"bpm":90,"kit":"mixwave_sleep_token","notes":[{"key":42,"when":.25,"duration":.25,"gain":1}]}
    assert call("/api/editor/export",body,token="wrong")[0]==403
    code,headers,payload=call("/api/editor/export",body)
    assert code==200 and headers["Content-Type"].startswith("audio/midi")
    code,_,payload=call("/api/editor/import",payload,content_type="audio/midi")
    assert code==200 and json.loads(payload)["notes"][0]["key"]==75


def test_malformed_and_non_object_json_are_400_not_a_closed_connection(api):
    call,_=api
    assert call("/api/editor/export",b"{")[0]==400
    assert call("/api/editor/export",b"[]")[0]==400


def test_audio_reference_requires_auth_and_cannot_escape_input_dir(api):
    call,folder=api;(folder/"take.wav").write_bytes(b"RIFFfixture")
    (folder.parent/"outside.wav").write_bytes(b"private")
    assert call("/api/audio?file=take.wav",token="wrong")[0]==403
    assert call("/api/audio?file=take.wav")[2]==b"RIFFfixture"
    assert call("/api/audio?file=../outside.wav")[0] in {403,404}


def test_upload_duplicate_keeps_original_bytes(api):
    call,folder=api;(folder/"take.wav").write_bytes(b"original")
    code,_,payload=call("/api/upload?name=take.wav",b"new",content_type="audio/wav")
    assert code==200
    uploaded=json.loads(payload)["file"]
    assert uploaded!="take.wav"
    assert (folder/"take.wav").read_bytes()==b"original"
    assert (folder/uploaded).read_bytes()==b"new"


def test_meta_exposes_actual_gm_mapping_for_transcription_adapter(api):
    call,_=api
    metadata=json.loads(call("/api/meta")[2])
    assert metadata["gm_map"]["hat_closed"]==42
    assert metadata["gm_map"]["rack2"]==45

@pytest.mark.parametrize("path,limit",[("/api/editor/import",8*1024*1024),("/api/editor/export",8*1024*1024),("/api/upload?name=large.wav",256*1024*1024)])
def test_oversized_content_length_is_rejected_before_reading_payload(api,path,limit):
    call,_=api
    assert call(path,b"x",extra_headers={"Content-Length":str(limit+1)})[0]==413


def test_sibling_directory_cannot_pass_a_string_prefix_check(api):
    call,folder=api
    sibling=folder.parent/(folder.name+"-other");sibling.mkdir()
    (sibling/"private.wav").write_bytes(b"private")
    assert call("/api/audio?file=../"+sibling.name+"/private.wav")[0]==404


def test_symlinked_audio_outside_the_input_directory_is_not_served(api):
    call,folder=api;outside=folder.parent/(folder.name+"-private.wav");outside.write_bytes(b"private")
    try:(folder/"linked.wav").symlink_to(outside)
    except OSError:pytest.skip("Host does not allow file symlinks")
    assert call("/api/audio?file=linked.wav")[0]==404


def test_source_offer_is_public_and_matches_served_application(api):
    import zipfile
    call,_=api
    code,headers,payload=call("/source.zip",token="")
    assert code==200 and headers["Content-Type"]=="application/zip"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names=archive.namelist()
        assert "grooveforge-source/src/drum_midi/webui_static/app.js" in names
        assert not any(".env" in name or "superpowers" in name or name.endswith(".pth") for name in names)


def test_transcription_is_not_started_twice_on_one_engine(api,monkeypatch):
    from drum_midi import webui
    call,folder=api;(folder/"take.wav").write_bytes(b"fixture")
    entered=threading.Event();release=threading.Event();out=[]
    monkeypatch.setattr(webui,"parse_audio",lambda p:(44100,None))
    def backend(*a,**kw):
        entered.set();assert release.wait(5);return []
    monkeypatch.setattr(webui,"transcribe",backend)
    first=threading.Thread(target=lambda:out.append(call("/api/run",{"file":"take.wav"})))
    first.start();assert entered.wait(5)
    try:assert call("/api/run",{"file":"take.wav"})[0]==409
    finally:release.set();first.join(5)
    assert out[0][0]==200
