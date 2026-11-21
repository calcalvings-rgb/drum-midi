import numpy as np
from scipy.io import wavfile
from drum_midi.audio import load_wav


def test_float_wav_from_a_daw_is_loaded_and_downmixed(tmp_path):
    path=tmp_path/"float.wav"
    data=np.array([[.25,.75],[-.5,.5]],dtype=np.float32)
    wavfile.write(path,44100,data)
    sr,mono=load_wav(path)
    assert sr==44100
    np.testing.assert_allclose(mono,[.5,0],atol=1e-7)
