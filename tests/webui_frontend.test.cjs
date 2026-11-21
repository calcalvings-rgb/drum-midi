// Entry point retained for the documented frontend test command.
// The editor now uses GridSound DOM components, not the retired canvas renderer.
const { spawnSync } = require('node:child_process');
const { join } = require('node:path');
const env = { ...process.env };
delete env.NODE_TEST_CONTEXT;
const result = spawnSync(process.execPath, ['--test', ...['model','adapter','waveform','dropzone','import_pair'].map(name => join(__dirname, name+'.test.mjs'))], { stdio:'inherit', env, timeout:60000 });
process.exitCode = result.status ?? 1;
