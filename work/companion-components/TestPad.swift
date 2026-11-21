import AppKit

let root = Bundle.main.bundleURL.deletingLastPathComponent()

final class TestPad: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var exportButton: NSButton!
    let question = NSTextField(string: "")
    let status = NSTextField(wrappingLabelWithString: "Ready. Test the reader first, then the pointer.")
    var process: Process?

    func label(_ text: String, _ y: CGFloat, size: CGFloat = 14) {
        let view = NSTextField(labelWithString: text)
        view.font = .systemFont(ofSize: size)
        view.frame = NSRect(x: 28, y: y, width: 650, height: 28)
        window.contentView!.addSubview(view)
    }
    @discardableResult func button(_ text: String, x: CGFloat, y: CGFloat, width: CGFloat, action: Selector) -> NSButton {
        let view = NSButton(title: text, target: self, action: action)
        view.frame = NSRect(x: x, y: y, width: width, height: 34)
        view.bezelStyle = .rounded
        view.setAccessibilityLabel(text)
        window.contentView!.addSubview(view)
        return view
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 720, height: 510),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "Companion Test Pad"
        window.isReleasedWhenClosed = false
        label("Companion component test", 448, size: 25)
        label("Local practice window • no AI calls • no automatic clicks", 418)
        label("Your question — dictate with Utter or type", 366)
        question.frame = NSRect(x: 28, y: 326, width: 510, height: 32)
        question.placeholderString = "e.g. show me Export PDF"
        question.setAccessibilityLabel("Your question")
        window.contentView!.addSubview(question)
        button("Use question", x: 548, y: 324, width: 142, action: #selector(useQuestion))
        label("Practice invoice", 267, size: 19)
        let field = NSTextField(string: "FIELD_VALUE_SHOULD_NOT_BE_READ")
        field.frame = NSRect(x: 28, y: 228, width: 510, height: 28)
        field.setAccessibilityLabel("Customer name")
        window.contentView!.addSubview(field)
        exportButton = button("Export PDF", x: 28, y: 174, width: 160, action: #selector(exportPDF))
        button("Save draft", x: 200, y: 174, width: 160, action: #selector(saveDraft))
        button("Preview invoice", x: 372, y: 174, width: 180, action: #selector(preview))
        button("1 · Read controls", x: 28, y: 114, width: 195, action: #selector(readControls))
        button("2 · Show pointer", x: 235, y: 114, width: 195, action: #selector(showPointer))
        button("Stop pointer", x: 442, y: 114, width: 150, action: #selector(stopPointer))
        status.frame = NSRect(x: 28, y: 24, width: 660, height: 70)
        status.setAccessibilityLabel("Test status")
        window.contentView!.addSubview(status)
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        window.makeFirstResponder(question)
    }
    func save(_ object: [String: Any], name: String) {
        if let data = try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys]) {
            try? data.write(to: root.appendingPathComponent(name), options: .atomic)
        }
    }
    @objc func useQuestion() {
        let text = question.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { status.stringValue = "Dictate or type a question first."; return }
        save(["question": text, "source": "practice field; dictation source not automatically verified"], name: "submitted-question.json")
        status.stringValue = "Question received locally. No AI planner is connected yet."
    }
    @objc func exportPDF() {
        status.stringValue = "Export PDF clicked — test only; no file created."
        save(["clicked": "Export PDF"], name: "manual-click.json")
    }
    @objc func saveDraft() { status.stringValue = "Save draft clicked — test only." }
    @objc func preview() { status.stringValue = "Preview invoice clicked — test only." }
    @objc func readControls() { runProbe("read") }
    @objc func showPointer() {
        // Our own button's geometry is a separate pointer-only fallback, never an AX result.
        let rect = window.convertToScreen(exportButton.convert(exportButton.bounds, to: nil))
        let screenTop = NSScreen.screens[0].frame.maxY
        save(["frame": [rect.minX, screenTop - rect.maxY, rect.width, rect.height],
              "target": "Export PDF", "captured_at": Date().timeIntervalSince1970,
              "source": "fixture-supplied geometry; not an Accessibility reading"], name: "fixture-layout.json")
        runProbe("point")
    }
    @objc func stopPointer() { process?.terminate(); status.stringValue = "Pointer stopped." }
    func runProbe(_ mode: String) {
        if process?.isRunning == true { status.stringValue = "Stop the current pointer test first."; return }
        let child = Process()
        child.executableURL = root.appendingPathComponent(".venv/bin/python")
        child.arguments = [root.appendingPathComponent("probe.py").path, mode]
        let pipe = Pipe()
        child.standardOutput = pipe
        child.standardError = pipe
        process = child
        status.stringValue = mode == "point" ? "Checking fresh controls before drawing the pointer…" : "Reading only this practice window…"
        child.terminationHandler = { [weak self] task in
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let message = String(data: data, encoding: .utf8) ?? "No result"
            DispatchQueue.main.async {
                guard let self else { return }
                if self.status.stringValue.hasPrefix("Export PDF clicked") { return }
                self.status.stringValue = String(message.suffix(700)).trimmingCharacters(in: .whitespacesAndNewlines)
            }
        }
        do { try child.run() } catch { status.stringValue = "Could not start probe: \(error.localizedDescription)" }
    }
    func applicationWillTerminate(_ notification: Notification) { process?.terminate() }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
let delegate = TestPad()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
