# Companion sketch-style preview

An interactive visual study using real Rough.js 4.6.6 SVG drawing and a locally hosted Shantell Sans variable font. Both desktop and website screens are simulated. This does not read the desktop, call AI, or implement an Electron overlay.

Open `index.html` through a local HTTP server. For example, from this directory:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Then visit `http://127.0.0.1:8000/`.

Try Plum, Forest and Terracotta; adjust roughness and font informality. Both annotation layers ignore pointer events, so the sample buttons remain clickable. Shapes use stable seeds to prevent unrelated redraws from shifting the sketch randomly.

## Selected look

The user selected **Plum `#674064`, roughness `1.9`, Playfulness/Informality `35`**, confirmed from their screenshot on 21 November 2026 at 16:09:46 IST. `selected-style.json` records these values and the unchanged paper/font details. They are now the page defaults.

Future edits autosave in browser local storage and are reflected in the URL hash. Hash settings override stored browser settings; absent either, the selected defaults apply. Browser autosave does not rewrite `selected-style.json` or the handoff, and does not modify the native app. Reloading the old already-open page is only needed to pick up this new persistence code; its chosen values have already been recorded independently.

Persistence was browser-verified: a Forest selection survived navigating back to the URL without a hash; explicit hash values restored Plum/1.9/35; changing the hash within the same page updated the controls; the chosen values were restored afterward. No console errors were reported. `preview-selected.png` preserves the selected look.

Rough.js was downloaded from its official npm registry archive with the registry SHA-512 integrity verified. The font came from Google's official fonts repository. `assets/sources.json` records sources and SHA-256 fingerprints, and both licenses are included. No font was installed system-wide and no application dependencies or permissions were changed.

Browser verification: font loaded, 14 SVG paths rendered across the two screens, no console errors, Forest changes annotation ink to `#28665b`, and clicking Export PDF passes through the SVG and updates the preview status. Screenshot: `preview.png`.

This is a design demonstration. The working native H Companion fixture and its completed reader/pointer tests are unchanged.
