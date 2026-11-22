import AppKit
import ApplicationServices
import Foundation

guard CommandLine.arguments.count == 2, let pid = Int32(CommandLine.arguments[1]),
      let app = NSRunningApplication(processIdentifier: pid) else { exit(2) }
app.unhide()
_ = app.activate(options: [.activateAllWindows, .activateIgnoringOtherApps])
let axApp = AXUIElementCreateApplication(pid)
var list: CFTypeRef?
let code = AXUIElementCopyAttributeValue(axApp, kAXWindowsAttribute as CFString, &list)
guard code == .success, let windows = list as? [AXUIElement] else { print("AX",code.rawValue); exit(3) }
for window in windows {
    var title: CFTypeRef?
    AXUIElementCopyAttributeValue(window,kAXTitleAttribute as CFString,&title)
    if title as? String == "Modded Slay the Spire" {
        AXUIElementSetAttributeValue(window,kAXMinimizedAttribute as CFString,kCFBooleanFalse)
        let raised = AXUIElementPerformAction(window,kAXRaiseAction as CFString)
        print("Raised game",pid,raised.rawValue)
        Thread.sleep(forTimeInterval:1.2)
        exit(0)
    }
}
exit(4)
