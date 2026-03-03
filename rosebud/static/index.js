/*****************************************************************************
 * Copyright (c) 2014-2025 OpenRCT2 developers
 *
 * For a complete list of all authors, please refer to contributors.md
 * Interested in contributing? Visit https://github.com/OpenRCT2/OpenRCT2
 *
 * OpenRCT2 is licensed under the GNU General Public License version 3.
 *****************************************************************************/
(async () =>
{
    // Globals so updateAssets() and other file-scope functions can use them.
    window.setProgress = (pct, phase) => {
        if (typeof updateLoadingBar === 'function') updateLoadingBar(pct, phase);
    };
    window.setError = (msg) => {
        if (typeof showLoadingError === 'function') showLoadingError(msg);
        else {
            const el = document.getElementById("loadingWebassembly");
            if (el) el.innerText = msg;
        }
    };

    await new Promise(res => window.addEventListener("DOMContentLoaded", res));
    if (!window.SharedArrayBuffer)
    {
        setError("Error! SharedArrayBuffer is not defined. This page required the CORP and COEP response headers.");
        return;
    }
    if (!window.WebAssembly)
    {
        setError("Error! This page requires WebAssembly. Please upgrade your browser or enable WebAssembly support.");
        return;
    }

    setProgress(5, "Loading game engine...");

    let assets;
    try
    {
        let req = await fetch("openrct2.zip");
        if (!req.ok) {
            throw new Error("Response is not ok!")
        }
        let data = await req.blob();
        setProgress(15, "Unpacking game engine...");
        let zip = new JSZip();
        let contents = await zip.loadAsync(data);
        assets = {
            js: URL.createObjectURL(new Blob([await zip.file("openrct2.js").async("uint8array")], {type: 'application/json'})),
            wasm: URL.createObjectURL(new Blob([await zip.file("openrct2.wasm").async("uint8array")], {type: 'application/wasm'}))
        }
        setProgress(25, "Loading game engine...");
    }
    catch(e)
    {
        assets = null;
        console.warn("Failed to fetch openrct2.zip. Will pull not-compressed files", e);
    }

    await new Promise(resolve => {
        const script = document.createElement("script");
        script.src = assets === null ? "openrct2.js" : assets.js;
        script.addEventListener("load", resolve);
        script.addEventListener("error", (e) => {
            setError("Error loading openrct2.js!");
            console.error(e);
        });
        document.body.appendChild(script);
    })

    setProgress(30, "Initializing engine...");
    window.Module = await window.OPENRCT2_WEB({
        noInitialRun: true,
        arguments: [],
        preRun: [],
        postRun: [],
        canvas: document.getElementById("canvas"),
        print: function(msg)
        {
            console.log(msg);
        },
        printErr: function(msg)
        {
            console.log(msg);
        },
        totalDependencies: 0,
        monitorRunDependencies: () => {},
        locateFile: function(fileName)
        {
            if (assets !== null && fileName === "openrct2.wasm")
            {
                return assets.wasm;
            }
            console.log("loading", fileName);
            return fileName;
        }
    });

    setProgress(35, "Mounting filesystems...");
    Module.FS.mkdir("/persistent");
    Module.FS.mount(Module.FS.filesystems.IDBFS, {autoPersist: true}, '/persistent');

    Module.FS.mkdir("/RCT");
    Module.FS.mount(Module.FS.filesystems.IDBFS, {autoPersist: true}, '/RCT');

    Module.FS.mkdir("/OpenRCT2");
    Module.FS.mount(Module.FS.filesystems.IDBFS, {autoPersist: true}, '/OpenRCT2');

    await new Promise(res => Module.FS.syncfs(true, res));

    setProgress(40, "Checking park assets...");
    const assetsOK = await updateAssets();
    if (!assetsOK)
    {
        return;
    }

    let changelog = "";
    try {
        const request = await fetch("https://api.github.com/repos/OpenRCT2/OpenRCT2/releases/latest");
        const json = JSON.parse(await request.text());
        changelog = json.body;
    } catch(e) {
        console.log("Failed to fetch changelog with error:", e);
    }

    Module.FS.writeFile("/OpenRCT2/changelog.txt", changelog);

    setProgress(75, "Checking ride data...");
    let filesFound = fileExists("/RCT/Data/ch.dat") && fileExists("/RCT/ObjData/BALLN.DAT");

    if (!filesFound)
    {
        setProgress(80, "Downloading ride data...");
        await extractDefaultRct2Data();
        filesFound = fileExists("/RCT/Data/ch.dat");
        if (!filesFound)
        {
            setError("Error! Could not auto-load RCT2 data. Place rct2-content.zip (containing Data/ch.dat and ObjData) next to index.html.");
            return;
        }
        setProgress(90, "Ride data loaded");
    }

    setProgress(95, "Preparing your park...");
    if (typeof dismissOverlay === 'function') {
        dismissOverlay();
    } else {
        const loadEl = document.getElementById("loadingWebassembly");
        if (loadEl) loadEl.remove();
        Module.canvas.style.display = "";
    }
    Module.callMain(["--user-data-path=/persistent/", "--openrct2-data-path=/OpenRCT2/"]);
})();

async function updateAssets() {
    let currentVersion = "";
    try {
        currentVersion = Module.FS.readFile("/OpenRCT2/version", {encoding: "utf8"});
        console.log("Found asset version", currentVersion);
    } catch(e) {
        console.log("No asset version found");
    };
    let assetsVersion = "DEBUG";
    try {
        assetsVersion = Module.ccall("GetVersion", "string");
    } catch(e) {
        console.warn("Could not call 'GetVersion'! Is it added to EXPORTED_FUNCTIONS? Is ccall added to EXPORTED_RUNTIME_METHODS?");
    };

    // If key files are missing, force a refresh even when version matches.
    const hasRequiredAssets = fileExists("/OpenRCT2/language/en-US.txt")
        && fileExists("/OpenRCT2/g2.dat")
        && fileExists("/OpenRCT2/object/official/footpath_surface/openrct2.footpath_surface.invisible.json")
        && fileExists("/OpenRCT2/sequence/openrct2.parkseq");
    if (!hasRequiredAssets)
    {
        console.warn("OpenRCT2 data files are incomplete, forcing an asset refresh.");
        currentVersion = "";
    }

    //Always pull assets on a debug build
    if (currentVersion !== assetsVersion || assetsVersion.includes("DEBUG"))
    {
        console.log("Updating assets to", assetsVersion);
        setProgress(45, "Downloading park assets...");
        await clearDatabase("/OpenRCT2/");

        // Fetch the assets.zip file
        const response = await fetch("assets.zip");
        if (!response.ok) {
            if (response.status === 404) {
                setError("Error! Assets file not found (404).");
            } else {
                setError(`Error! Failed to download assets (status: ${response.status}).`);
            }
            return false;
        } else {
            setProgress(65, "Unpacking park assets...");
        }

        await extractZip(await response.blob(), () => {
            return "/OpenRCT2/";
        });
        setProgress(70, "Park assets ready");
        Module.FS.writeFile("/OpenRCT2/version", assetsVersion.toString());
    }
    return true;
}

async function extractDefaultRct2Data() {
    try {
        const response = await fetch("rct2-content.zip");
        if (!response.ok) {
            console.warn(`Failed to fetch rct2-content.zip (status: ${response.status})`);
            return false;
        }
        return await extractZip(await response.blob(), (zip) => {
            if (zip !== null)
            {
                if (zip.file("Data/ch.dat") && zip.file("ObjData/BALLN.DAT"))
                {
                    return "/RCT/";
                }
                if (zip.file("RCT/Data/ch.dat") && zip.file("RCT/ObjData/BALLN.DAT"))
                {
                    return "/";
                }
            }
            console.warn("rct2-content.zip must contain Data/ch.dat and ObjData/BALLN.DAT");
            return false;
        });
    } catch (e) {
        console.warn("Failed to auto-load rct2-content.zip", e);
        return false;
    }
}

async function extractZip(data, checkZip) {
    let zip = new JSZip();
    let contents;
    try {
        contents = await zip.loadAsync(data);
    } catch(e) {
        if (typeof checkZip === "function")
        {
            checkZip(null);
        }
        throw e;
    }
    let base = "/";
    if (typeof checkZip === "function")
    {
        const cont = checkZip(contents);
        if (cont === false) return false;
        base = cont;
    }
    for (const k in contents.files) {
        const entry = contents.files[k];
        if (entry.dir)
        {
            try {
                Module.FS.mkdir(base+k);
            } catch(e) {}
        }
        else
        {
            Module.FS.writeFile(base+k, await entry.async("uint8array"));
        }
    }
    return true;
}
async function clearDatabase(dir) {
    await new Promise(res => Module.FS.syncfs(false, res));
    const processFolder = (path) => {
        let contents;
        try {
            contents = Module.FS.readdir(path);
        } catch(e) {
            return;
        }
        contents.forEach((entry) => {
            if ([".", ".."].includes(entry)) return;
            try {
                Module.FS.readFile(path + entry);
                Module.FS.unlink(path + entry);
            } catch(e) {
                processFolder(path + entry + "/");
            }
        })
        if (path === dir) return;
        try {
            Module.FS.rmdir(path, {recursive: true});
        } catch(e) {
            console.log("Could not remove:", path);
        }
    }
    processFolder(dir);
    await new Promise(res => Module.FS.syncfs(false, res));
}
function fileExists(path) {
    try {
        Module.FS.readFile(path);
        return true;
    } catch(e) {};
    return false;
}
