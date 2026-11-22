import AppKit
import CoreGraphics
import Foundation

guard CommandLine.arguments.count == 3, let pid = pid_t(CommandLine.arguments[1]),
      let code = CGKeyCode(CommandLine.arguments[2]),
      [18,19,20,21,23,22,26,28,25,29,36].contains(code),
      let process = NSRunningApplication(processIdentifier: pid), !process.isTerminated
else { exit(2) }
let source = CGEventSource(stateID: .privateState)
for down in [true, false] {
    guard let key = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: down)
    else { exit(2) }
    key.postToPid(pid)
    Thread.sleep(forTimeInterval: 0.2)
}
print("key posted only to the game PID", pid, code)
