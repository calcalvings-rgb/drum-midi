from drum_midi.pipeline import run_pipeline

inp = r"C:\Users\ccalv\workspace\coding\drum-test_drums_pcm.wav"
out = r"C:\Users\ccalv\workspace\coding\drum-test_drums_stem.mid"
mode = {"input": "stem", "tx": "adtof"}
res = run_pipeline(inp, mode, out, preset="mixwave_sleep_token", tempo=139.67)
print("RESULT", res)
