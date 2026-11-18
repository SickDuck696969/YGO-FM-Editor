/* A read-only File mount keeps the 500 MB source disc outside WebAssembly memory. */
importScripts("disc-output.js");
let runtime;
let currentMount;
let currentDisc;
let mountNumber = 0;
async function boot() {
  importScripts("runtime/pyodide.js");
  const py = await loadPyodide({
    indexURL: new URL("runtime/", self.location.href).href,
  });
  await py.loadPackage("pillow");
  const response = await fetch("editor.zip");
  if (!response.ok) throw Error("Editor engine could not load.");
  py.unpackArchive(await response.arrayBuffer(), "zip");
  py.runPython("import bridge, json");
  py.globals.set("report", (fraction, label) =>
    postMessage({ progress: label }),
  );
  return py;
}
function mountFiles(fs, files) {
  const path = "/input-" + ++mountNumber;
  fs.mkdir(path);
  fs.mount(fs.filesystems.WORKERFS, { files }, path);
  // Python reads sequential CD sectors. Read ahead to avoid a Blob read per sector.
  for (const file of files) {
    const node = fs.lookupPath(path + "/" + file.name).node;
    const reader = new FileReaderSync();
    let start = -1,
      cache = new Uint8Array();
    node.stream_ops = {
      ...node.stream_ops,
      read(stream, buffer, offset, length, position) {
        const count = Math.min(length, file.size - position);
        if (count <= 0) return 0;
        if (position < start || position + count > start + cache.length) {
          start = position;
          cache = new Uint8Array(
            reader.readAsArrayBuffer(
              file.slice(start, start + Math.max(count, 1024 * 1024)),
            ),
          );
        }
        buffer.set(
          cache.subarray(position - start, position - start + count),
          offset,
        );
        return count;
      },
    };
  }
  return path;
}
async function discFiles(files) {
  const descriptor = files.find((f) => /\.(cue|ccd)$/i.test(f.name));
  if (!descriptor) {
    if (files.length !== 1) throw Error("Choose one disc image at a time.");
    return files;
  }
  let name;
  if (/\.cue$/i.test(descriptor.name)) {
    const cue = await descriptor.text();
    const tracks = [...cue.matchAll(/^\s*TRACK\s+\d+\s+(\S+)/gim)];
    const entries = [...cue.matchAll(/^\s*FILE\s+"([^"]+)"\s+BINARY/gim)];
    if (
      tracks.length !== 1 ||
      entries.length !== 1 ||
      tracks[0][1].toUpperCase() === "AUDIO"
    ) {
      throw Error("Choose a single data-track CUE or open its BIN directly.");
    }
    name = entries[0][1].split(/[\\/]/).pop();
  } else {
    name = descriptor.name.replace(/\.ccd$/i, ".img");
  }
  const image = files.find((f) => f.name.toLowerCase() === name.toLowerCase());
  if (!image)
    throw Error(
      "Select " +
        name +
        " alongside the descriptor, or open the data image directly.",
    );
  return [image];
}

function unmount(fs, path) {
  if (path) {
    fs.unmount(path);
    fs.rmdir(path);
  }
}
let queue = Promise.resolve();
onmessage = ({ data }) => {
  queue = queue.then(() => execute(data));
};
async function execute({ id, op, args, files }) {
  let mount, py;
  try {
    runtime ||= boot().catch((error) => {
      runtime = null;
      throw error;
    });
    py = await runtime;
    const fs = py.FS;
    if (op === "disc") files = await discFiles(files);
    if (files?.length) {
      mount = mountFiles(fs, files);
      const file = files.find((f) => /\.(cue|ccd)$/i.test(f.name)) || files[0];
      args.path = mount + "/" + file.name;
    }
    py.globals.set("operation", op);
    py.globals.set("arguments_json", JSON.stringify(args));
    const result = JSON.parse(
      py.runPython(
        "json.dumps(bridge.handle(operation, json.loads(arguments_json), report))",
      ),
    );
    let payload = result;
    if (op === "disc") {
      const path = py.runPython("bridge.game.disc.path.name");
      currentDisc = files.find((f) => f.name === path);
      unmount(fs, currentMount);
      currentMount = mount;
      mount = null;
    } else if (op === "saveExport" || op === "newSave") {
      payload = new Blob([fs.readFile("export.save")]);
      fs.unlink("export.save");
    } else if (op === "export") {
      const patch = fs.readFile("export.bps");
      fs.unlink("export.bps");
      if (args.format === "bps")
        payload = { blob: new Blob([patch]), changed: result };
      else {
        postMessage({ progress: "Verifying output image…" });
        payload = {
          blob: await buildDisc(currentDisc, patch),
          changed: result,
        };
      }
    }
    postMessage({ id, result: payload });
  } catch (error) {
    console.error(error);
    const lines = String(error.message || error)
      .trim()
      .split("\n");
    postMessage({
      id,
      error: lines.at(-1).replace(/^[\w.]+(?:Error|Exception):\s*/, ""),
    });
  } finally {
    if (mount && py) unmount(py.FS, mount);
  }
}
