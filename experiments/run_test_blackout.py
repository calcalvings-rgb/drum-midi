from drum_midi.pipeline import run_pipeline

inp = r"C:\Users\ccalv\workspace\coding\drum-test.wav"
out = r"C:\Users\ccalv\workspace\coding\drum-test.mid"
mode = {"input": "auto", "sep": "demucs", "tx": "adtof"}
res = run_pipeline(inp, mode, out, preset="mixwave_sleep_token", tempo=139.67)
print("RESULT", res)
