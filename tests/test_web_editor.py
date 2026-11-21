import io
import math
import mido
import pytest
from drum_midi.web_editor import read_editor_midi, write_editor_midi


def state(**overrides):
    data={"bpm":90,"kit":"gm","notes":[{"key":42,"when":.25,"duration":.125,"gain":100/127},{"key":45,"when":1.5,"duration":.5,"gain":64/127}]}
    data.update(overrides)
    return data


def test_editor_roundtrip_preserves_beats_duration_velocity_and_tempo():
    payload=write_editor_midi(state())
    result=read_editor_midi(payload)
    assert result["bpm"]==pytest.approx(90,abs=.001)
    assert result["notes"]==state()["notes"]
    midi=mido.MidiFile(file=io.BytesIO(payload))
    assert midi.type==0
    assert all(msg.channel==9 for track in midi.tracks for msg in track if msg.type in {"note_on","note_off"})


def test_export_maps_canonical_gm_to_output_kit_once():
    result=read_editor_midi(write_editor_midi(state(kit="mixwave_sleep_token")))
    assert [n["key"] for n in result["notes"]]==[75,47]
    assert result["notes"][0]["when"]==.25
    assert result["bpm"]==pytest.approx(90,abs=.001)


def test_unknown_gm_pitch_is_preserved_in_gm_and_rejected_for_other_kit():
    data=state(notes=[{"key":39,"when":0,"duration":.25,"gain":1}])
    assert read_editor_midi(write_editor_midi(data))["notes"][0]["key"]==39
    data["kit"]="mixwave_sleep_token"
    with pytest.raises(ValueError,match="pitch.*39|39.*pitch"):
        write_editor_midi(data)


@pytest.mark.parametrize("field,value",[("key",True),("key",128),("key",36.5),("when",-1),("when",float("nan")),("duration",0),("duration",float("inf")),("gain",1.1)])
def test_export_rejects_invalid_note_fields(field,value):
    data=state();data["notes"][0][field]=value
    with pytest.raises((ValueError,TypeError)):
        write_editor_midi(data)


@pytest.mark.parametrize("bpm",[True,0,float("nan"),401])
def test_export_rejects_invalid_tempo(bpm):
    with pytest.raises((ValueError,TypeError)):
        write_editor_midi(state(bpm=bpm))


def test_zero_velocity_is_silent_not_a_spurious_quiet_note():
    assert read_editor_midi(write_editor_midi(state(notes=[{"key":36,"when":0,"duration":.25,"gain":0}])))["notes"]==[]


@pytest.mark.parametrize("messages",[[mido.MetaMessage("set_tempo",tempo=500000),mido.MetaMessage("set_tempo",tempo=600000,time=480)],[mido.MetaMessage("time_signature",numerator=3,denominator=4)]])
def test_import_rejects_unsupported_tempo_or_meter_instead_of_changing_it(messages):
    midi=mido.MidiFile();midi.tracks.append(mido.MidiTrack(messages));out=io.BytesIO();midi.save(file=out)
    with pytest.raises(ValueError):read_editor_midi(out.getvalue())
