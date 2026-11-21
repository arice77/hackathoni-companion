// Crop-loss application TRAINING form. Synthetic, offline, never submits anything.
// Three screens imitating the shape of the Kerala online crop-loss application so the
// companion can be demonstrated on a repeatable target. Labels are provisional until the
// workflow review confirms them (see .context/workflow-review.md / HANDOFF.md).
import AppKit

struct Field {
    let id: String
    let label: String
    let kind: Kind
    enum Kind { case text(placeholder: String), popup([String]), date, attach(sample: String), check }
}

struct Screen {
    let id: String
    let title: String
    let fields: [Field]
    let nextTitle: String
}

let screens: [Screen] = [
    Screen(id: "farmer", title: "Step 1 of 3 · Farmer & Land Details", fields: [
        Field(id: "farmer-id", label: "Farmer Registration No.", kind: .text(placeholder: "e.g. TRN-0000")),
        Field(id: "panchayat", label: "Panchayat", kind: .popup(["Select", "Pulincunnoo (training)", "Kainakary (training)", "Nedumudi (training)"])),
        Field(id: "krishi-bhavan", label: "Krishi Bhavan", kind: .popup(["Select", "Pulincunnoo KB (training)", "Kainakary KB (training)", "Nedumudi KB (training)"])),
        Field(id: "survey-no", label: "Survey Number", kind: .text(placeholder: "e.g. 000/0")),
        Field(id: "land-area", label: "Land Area (ha)", kind: .text(placeholder: "e.g. 0.40")),
    ], nextTitle: "Next"),
    Screen(id: "loss", title: "Step 2 of 3 · Crop Loss Details", fields: [
        Field(id: "crop", label: "Crop", kind: .popup(["Select", "Paddy", "Banana", "Coconut"])),
        Field(id: "season", label: "Season", kind: .popup(["Select", "Puncha", "Virippu", "Mundakan"])),
        Field(id: "cause", label: "Cause of Loss", kind: .popup(["Select", "Flood", "Heavy Rain", "Drought", "Pest Attack"])),
        Field(id: "loss-date", label: "Date of Loss", kind: .date),
        Field(id: "affected-area", label: "Affected Area (ha)", kind: .text(placeholder: "e.g. 0.30")),
    ], nextTitle: "Next"),
    Screen(id: "evidence", title: "Step 3 of 3 · Evidence & Review", fields: [
        Field(id: "photo", label: "Field Photo", kind: .attach(sample: "sample-paddy-field.jpg")),
        Field(id: "tax-receipt", label: "Land Tax Receipt", kind: .attach(sample: "sample-tax-receipt.pdf")),
        Field(id: "declaration", label: "I declare the details are correct", kind: .check),
    ], nextTitle: "Save Draft"),
]

final class Controller: NSObject {
    let window: NSWindow
    var index = 0
    let titleLabel = NSTextField(labelWithString: "")
    let banner = NSTextField(labelWithString: "TRAINING FORM · synthetic data · nothing is submitted")
    let status = NSTextField(labelWithString: "")
    let stack = NSStackView()
    let backButton = NSButton(title: "Back", target: nil, action: nil)
    let nextButton = NSButton(title: "Next", target: nil, action: nil)
    var attached: [String: NSTextField] = [:]
    var values: [String: Bool] = [:]

    override init() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 620, height: 520),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        super.init()
        window.title = "Crop Loss Application — Training"
        window.center()
        let root = NSView()
        window.contentView = root

        banner.textColor = .systemOrange
        banner.font = .systemFont(ofSize: 11, weight: .semibold)
        titleLabel.font = .systemFont(ofSize: 20, weight: .bold)
        titleLabel.setAccessibilityIdentifier("screen-title")
        status.setAccessibilityIdentifier("status")
        status.textColor = .secondaryLabelColor
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 12

        backButton.target = self; backButton.action = #selector(back)
        backButton.setAccessibilityIdentifier("back")
        nextButton.target = self; nextButton.action = #selector(next)
        nextButton.keyEquivalent = "\r"
        nextButton.setAccessibilityIdentifier("next")
        let buttons = NSStackView(views: [backButton, nextButton])

        for v in [banner, titleLabel, stack, buttons, status] as [NSView] {
            v.translatesAutoresizingMaskIntoConstraints = false
            root.addSubview(v)
        }
        NSLayoutConstraint.activate([
            banner.topAnchor.constraint(equalTo: root.topAnchor, constant: 14),
            banner.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 24),
            titleLabel.topAnchor.constraint(equalTo: banner.bottomAnchor, constant: 8),
            titleLabel.leadingAnchor.constraint(equalTo: banner.leadingAnchor),
            stack.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 18),
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
        l.widthAnchor.constraint(equalToConstant: 220).isActive = true
        let r = NSStackView(views: [l, control])
        r.spacing = 12
        return r
    }

    func render() {
        stack.arrangedSubviews.forEach { $0.removeFromSuperview() }
        attached = [:]
        let s = screens[index]
        titleLabel.stringValue = s.title
        for f in s.fields {
            let control: NSView
            switch f.kind {
            case .text(let placeholder):
                let t = NSTextField()
                t.placeholderString = placeholder
                t.translatesAutoresizingMaskIntoConstraints = false
                t.widthAnchor.constraint(equalToConstant: 220).isActive = true
                control = t
            case .popup(let items):
                let p = NSPopUpButton()
                p.addItems(withTitles: items)
                control = p
            case .date:
                let d = NSDatePicker()
                d.datePickerStyle = .textFieldAndStepper
                d.datePickerElements = .yearMonthDay
                d.dateValue = Date()
                control = d
            case .attach(let sample):
                let b = NSButton(title: "Attach sample file", target: self, action: #selector(attach(_:)))
                b.identifier = NSUserInterfaceItemIdentifier(f.id + "|" + sample)
                let note = NSTextField(labelWithString: "No file attached")
                note.textColor = .secondaryLabelColor
                note.setAccessibilityIdentifier(f.id + "-file")
                attached[f.id] = note
                let h = NSStackView(views: [b, note])
                b.setAccessibilityLabel("Upload " + f.label)
                b.setAccessibilityIdentifier(f.id)
                stack.addArrangedSubview(row(f.label, h))
                continue
            case .check:
                let c = NSButton(checkboxWithTitle: f.label, target: nil, action: nil)
                c.setAccessibilityIdentifier(f.id)
                stack.addArrangedSubview(c)
                continue
            }
            control.setAccessibilityLabel(f.label)
            control.setAccessibilityIdentifier(f.id)
            stack.addArrangedSubview(row(f.label, control))
        }
        backButton.isHidden = index == 0
        nextButton.title = s.nextTitle
        status.stringValue = ""
    }

    @objc func attach(_ sender: NSButton) {
        let parts = (sender.identifier?.rawValue ?? "|").split(separator: "|").map(String.init)
        attached[parts[0]]?.stringValue = "Attached: \(parts.count > 1 ? parts[1] : "sample") (synthetic)"
        sender.title = "Replace sample file"
    }

    @objc func back() { if index > 0 { index -= 1; render() } }

    @objc func next() {
        if index < screens.count - 1 { index += 1; render(); return }
        status.stringValue = "Draft saved — training only. Nothing was submitted."
        let receipt: [String: Any] = ["event": "draft_saved", "at": ISO8601DateFormatter().string(from: Date())]
        if let data = try? JSONSerialization.data(withJSONObject: receipt),
           let dir = ProcessInfo.processInfo.environment["TRAINING_RECEIPT_DIR"] {
            try? data.write(to: URL(fileURLWithPath: dir).appendingPathComponent("draft-saved.json"))
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let controller = Controller()
controller.window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)
app.run()
