// Crop Insurance Compensation claim — TRAINING form. Synthetic, offline, never submits anything.
// Labels follow the Kerala AIMS user manual (Crop-Insurance-Consolidated-UM.pdf, March 2026,
// pp. 45-50) as recorded in the workflow review. Strings marked [invented] in comments are not
// in the manual. The real "Proceed" terms screen (p. 46) is skipped to keep three screens.
import AppKit

struct Field {
    let id: String
    let label: String
    let kind: Kind
    enum Kind {
        case text(placeholder: String, prefilled: String?)
        case popup([String])
        case readonly(String)
        case attach(sample: String, hint: String)
        case add
        case check
    }
}

struct Screen {
    let id: String
    let title: String
    let subtitle: String
    let fields: [Field]
    let nextTitle: String
}

let declaration = "അപേക്ഷയിൽ പ്രസ്താവിച്ചിട്ടുള്ള വിവരങ്ങൾ സത്യമാണെന്നും… (training copy)"

let screens: [Screen] = [
    Screen(id: "submission", title: "Application Submission", subtitle: "UM p. 45", fields: [
        Field(id: "krishibhavan", label: "Krishibhavan", kind: .text(placeholder: "", prefilled: "Pulincunnoo")),
        Field(id: "classification", label: "Classification",
              kind: .popup(["---Select Classification---", "Insurance & Calamity Relief Services"])),
        Field(id: "service", label: "Service",
              kind: .popup(["---Select My Service---", "Crop Insurance Compensation"])),
    ], nextTitle: "Apply for New"),
    // "Service : Crop Insurance Compensation" short form is [invented]; manual shows the long name.
    Screen(id: "calamity", title: "Calamity Details", subtitle: "Service : Crop Insurance Compensation", fields: [
        Field(id: "calamity-date", label: "Calamity Date*", kind: .popup(["Select", "12-08-2026 (TEST FIR)"])),
        // "Flood" is documented (p. 50); "Drought" and "Pest/Disease" are [invented].
        Field(id: "calamity-type", label: "Calamity Type*", kind: .popup(["Select", "Flood", "Drought", "Pest/Disease"])),
        Field(id: "calamity-description", label: "Calamity Description", kind: .text(placeholder: "", prefilled: nil)),
    ], nextTitle: "Save »"),
    Screen(id: "crop", title: "Crop Information", subtitle: "UM p. 48", fields: [
        Field(id: "insured-crop", label: "My Insured Crops*", kind: .popup(["Select", "Paddy (TEST policy)"])),
        // "Mainfield" seen on p. 49; "Nursery" is [invented].
        Field(id: "crop-stage", label: "Crop Stages", kind: .popup(["Select", "Mainfield", "Nursery"])),
        Field(id: "crop-unit", label: "Crop Unit", kind: .readonly("Cent")),
        Field(id: "planting-date", label: "Date Of Planting", kind: .readonly("15-06-2026")),
        Field(id: "crop-age", label: "Crop Age", kind: .readonly("58 days")),
        Field(id: "quantity-applied", label: "Quantity Applied*", kind: .text(placeholder: "", prefilled: nil)),
        Field(id: "crop-image", label: "Upload Crop Image*",
              kind: .attach(sample: "TEST-paddy-flood.jpg (SAMPLE)", hint: "File Upload Type - jpeg, jpg, png(Max File Size 1.91 MB)")),
        Field(id: "add-crop", label: "+Add", kind: .add),
    ], nextTitle: "Submit Application"),
    // Read-only preview (UM p. 50). "Final Submit »" disabled in training is [invented].
    Screen(id: "view", title: "Application View (training draft)", subtitle: "UM p. 50", fields: [
        Field(id: "summary-calamity", label: "Calamity Details", kind: .readonly("12-08-2026 · Flood")),
        Field(id: "summary-crop", label: "Crop information", kind: .readonly("Paddy · Mainfield")),
        Field(id: "declaration", label: declaration, kind: .check),
    ], nextTitle: "Final Submit »"),
]

final class Controller: NSObject {
    let window: NSWindow
    var index = 0
    let titleLabel = NSTextField(labelWithString: "")
    let subtitleLabel = NSTextField(labelWithString: "")
    let banner = NSTextField(labelWithString: "TRAINING — not connected to AIMS · synthetic data · nothing is submitted")
    let status = NSTextField(labelWithString: "")
    let stack = NSStackView()
    let backButton = NSButton(title: "Back", target: nil, action: nil)
    let printButton = NSButton(title: "Print Application", target: nil, action: nil)
    let nextButton = NSButton(title: "Next", target: nil, action: nil)
    var notes: [String: NSTextField] = [:]
    var attachedFile = false
    var receiptDir: String? { ProcessInfo.processInfo.environment["TRAINING_RECEIPT_DIR"] }

    override init() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 700, height: 640),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        super.init()
        window.title = "AIMS Crop Insurance Compensation — Training"
        window.center()
        let root = NSView()
        window.contentView = root

        banner.textColor = .systemOrange
        banner.font = .systemFont(ofSize: 11, weight: .semibold)
        titleLabel.font = .systemFont(ofSize: 20, weight: .bold)
        titleLabel.setAccessibilityIdentifier("screen-title")
        subtitleLabel.textColor = .secondaryLabelColor
        subtitleLabel.setAccessibilityIdentifier("screen-subtitle")
        status.setAccessibilityIdentifier("status")
        status.textColor = .secondaryLabelColor
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 10

        backButton.target = self; backButton.action = #selector(back)
        backButton.setAccessibilityIdentifier("back")
        printButton.setAccessibilityIdentifier("print")
        printButton.target = self; printButton.action = #selector(printDraft)
        nextButton.target = self; nextButton.action = #selector(next)
        nextButton.setAccessibilityIdentifier("next")
        let buttons = NSStackView(views: [backButton, printButton, nextButton])

        for v in [banner, titleLabel, subtitleLabel, stack, buttons, status] as [NSView] {
            v.translatesAutoresizingMaskIntoConstraints = false
            root.addSubview(v)
        }
        NSLayoutConstraint.activate([
            banner.topAnchor.constraint(equalTo: root.topAnchor, constant: 14),
            banner.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 24),
            titleLabel.topAnchor.constraint(equalTo: banner.bottomAnchor, constant: 8),
            titleLabel.leadingAnchor.constraint(equalTo: banner.leadingAnchor),
            subtitleLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 2),
            subtitleLabel.leadingAnchor.constraint(equalTo: banner.leadingAnchor),
            stack.topAnchor.constraint(equalTo: subtitleLabel.bottomAnchor, constant: 16),
            stack.leadingAnchor.constraint(equalTo: banner.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -24),
            buttons.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -24),
            buttons.bottomAnchor.constraint(equalTo: status.topAnchor, constant: -10),
            status.leadingAnchor.constraint(equalTo: banner.leadingAnchor),
            status.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -24),
            status.bottomAnchor.constraint(equalTo: root.bottomAnchor, constant: -14),
        ])
        render()
    }

    func row(_ label: String, _ control: NSView) -> NSView {
        let l = NSTextField(labelWithString: label)
        l.alignment = .right
        l.translatesAutoresizingMaskIntoConstraints = false
        l.widthAnchor.constraint(equalToConstant: 180).isActive = true
        let r = NSStackView(views: [l, control])
        r.spacing = 12
        return r
    }

    func note(_ id: String, _ text: String) -> NSTextField {
        let n = NSTextField(labelWithString: text)
        n.textColor = .secondaryLabelColor
        n.setAccessibilityIdentifier(id)
        notes[id] = n
        return n
    }

    func render() {
        stack.arrangedSubviews.forEach { $0.removeFromSuperview() }
        notes = [:]
        attachedFile = false
        let s = screens[index]
        titleLabel.stringValue = s.title
        subtitleLabel.stringValue = s.subtitle
        for f in s.fields {
            switch f.kind {
            case .text(let placeholder, let prefilled):
                let t = NSTextField()
                t.placeholderString = placeholder
                if let p = prefilled { t.stringValue = p; t.isEditable = false }
                t.translatesAutoresizingMaskIntoConstraints = false
                t.widthAnchor.constraint(equalToConstant: f.id == "calamity-description" ? 360 : 240).isActive = true
                t.setAccessibilityLabel(f.label)
                t.setAccessibilityIdentifier(f.id)
                stack.addArrangedSubview(row(f.label, t))
            case .popup(let items):
                let p = NSPopUpButton()
                p.addItems(withTitles: items)
                p.setAccessibilityLabel(f.label)
                p.setAccessibilityIdentifier(f.id)
                stack.addArrangedSubview(row(f.label, p))
            case .readonly(let value):
                stack.addArrangedSubview(row(f.label, note(f.id, value)))
            case .attach(let sample, let hint):
                let b = NSButton(title: "Browse...", target: self, action: #selector(attach(_:)))
                b.identifier = NSUserInterfaceItemIdentifier(sample)
                b.setAccessibilityLabel("Upload Crop Image Browse")
                b.setAccessibilityIdentifier(f.id)
                let v = NSStackView(views: [NSStackView(views: [b, note(f.id + "-file", "No file chosen")]),
                                            note(f.id + "-hint", hint)])
                v.orientation = .vertical
                v.alignment = .leading
                stack.addArrangedSubview(row(f.label, v))
            case .add:
                let b = NSButton(title: "+Add", target: self, action: #selector(addRow))
                b.setAccessibilityIdentifier(f.id)
                stack.addArrangedSubview(row("", NSStackView(views: [b, note("added-details", "Added Details: none")])))
            case .check:
                let c = NSButton(checkboxWithTitle: f.label, target: self, action: #selector(declared(_:)))
                c.setAccessibilityLabel("Declaration")
                c.setAccessibilityIdentifier(f.id)
                stack.addArrangedSubview(c)
            }
        }
        let last = index == screens.count - 1
        backButton.isHidden = index == 0
        printButton.isHidden = !last
        nextButton.title = s.nextTitle
        nextButton.isEnabled = !last  // Final Submit is disabled in training
        nextButton.toolTip = last ? "Disabled in training" : nil
        status.stringValue = last ? "Training draft ready — Final Submit is disabled. Tick the declaration to finish." : ""
        if last { writeReceipt("draft_view_shown") }
    }

    @objc func attach(_ sender: NSButton) {
        notes["crop-image-file"]?.stringValue = "Chosen: \(sender.identifier?.rawValue ?? "sample") · 0.8 MB"
        attachedFile = true
    }

    @objc func addRow() {
        guard attachedFile else {
            status.stringValue = "Choose a crop image before +Add."
            return
        }
        notes["added-details"]?.stringValue = "Added Details: 1 row (Paddy, TEST-paddy-flood.jpg)"
        status.stringValue = ""
    }

    @objc func declared(_ sender: NSButton) {
        if sender.state == .on {
            status.stringValue = "Training draft complete — declaration ticked. Nothing was submitted."
            writeReceipt("declaration_ticked")
        } else {
            status.stringValue = "Training draft ready — Final Submit is disabled. Tick the declaration to finish."
        }
    }

    @objc func printDraft() { status.stringValue = "Print is disabled in training." }

    @objc func back() { if index > 0 { index -= 1; render() } }

    @objc func next() { if index < screens.count - 1 { index += 1; render() } }

    func writeReceipt(_ event: String) {
        guard let dir = receiptDir else { return }
        let receipt: [String: Any] = ["event": event, "at": ISO8601DateFormatter().string(from: Date()),
                                      "training": true, "submitted": false]
        if let data = try? JSONSerialization.data(withJSONObject: receipt) {
            try? data.write(to: URL(fileURLWithPath: dir).appendingPathComponent("training-\(event).json"))
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let controller = Controller()
controller.window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)
app.run()
