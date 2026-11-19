from drum_midi.pipeline import run_pipeline

inp = r"C:\Users\ccalv\workspace\coding\drum-test_stems\drums.wav"
out = r"C:\Users\ccalv\workspace\coding\drum-test_stems\drums.mid"
mode = {"input": "stem", "tx": "adtof"}
res = run_pipeline(inp, mode, out, preset="mixwave_sleep_token", tempo=139.67)
print("RESULT", res)
