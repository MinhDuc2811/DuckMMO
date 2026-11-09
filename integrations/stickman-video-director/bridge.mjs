// App-owned launcher: never trust inherited media executable/font overrides.
import {pathToFileURL, fileURLToPath} from 'node:url';
import path from 'node:path';
const [ffmpeg, ffprobe, command, ...args] = process.argv.slice(2);
if (!['doctor', 'init', 'validate', 'preview', 'approve', 'render'].includes(command)) {
  throw new Error('Unsupported Stickman command');
}
process.env.FFMPEG = ffmpeg;
process.env.FFPROBE = ffprobe;
delete process.env.AUTOPILOT_FONT;
const cli = path.join(fileURLToPath(new URL('.', import.meta.url)), 'scripts', 'autopilot.mjs');
process.argv = [process.execPath, cli, command, ...args];
await import(pathToFileURL(cli).href);
