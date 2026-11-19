from drum_midi.pipeline import run_pipeline

inp = r"C:\Users\ccalv\workspace\coding\drum-midi\challange\tes_pcm.wav"
out = r"C:\Users\ccalv\workspace\coding\drum-midi\challange\tes_transcribed_normal.mid"
mode = {"input": "stem", "tx": "adtof"}
res = run_pipeline(inp, mode, out, preset="mixwave_sleep_token")
print("RESULT", res)
