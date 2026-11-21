import AVFoundation
import Foundation

@main
struct Microphone {
    static func main() async {
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        if CommandLine.arguments == [CommandLine.arguments[0], "--authorization-status"] {
            print(status.rawValue)
            return
        }
        guard CommandLine.arguments.count == 2 else {
            fail("Expected an output WAV path.")
        }

        switch status {
        case .authorized:
            break
        case .notDetermined:
            guard await AVCaptureDevice.requestAccess(for: .audio) else {
                fail("Microphone access was declined.", status: 77)
            }
        default:
            fail("Microphone access is denied or restricted.", status: 77)
        }

        do {
            let settings: [String: Any] = [
                AVFormatIDKey: kAudioFormatLinearPCM,
                AVSampleRateKey: 16_000,
                AVNumberOfChannelsKey: 1,
                AVLinearPCMBitDepthKey: 16,
                AVLinearPCMIsFloatKey: false,
                AVLinearPCMIsBigEndianKey: false,
            ]
            let recorder = try AVAudioRecorder(
                url: URL(fileURLWithPath: CommandLine.arguments[1]), settings: settings
            )
            // Leave headroom below the 30-second speech REST limit.
            guard recorder.record(forDuration: 29) else {
                fail("The microphone could not start recording.")
            }
            FileHandle.standardOutput.write(Data("ready\n".utf8))
            // A newline on release or EOF when the caller exits ends the capture.
            _ = readLine()
            recorder.stop()
        } catch {
            fail(error.localizedDescription)
        }
    }

    static func fail(_ message: String, status: Int32 = 1) -> Never {
        FileHandle.standardError.write(Data((message + "\n").utf8))
        exit(status)
    }
}
