import AppKit
import CoreGraphics
import Foundation
guard CommandLine.arguments.count==2, let pid=pid_t(CommandLine.arguments[1]),
      let app=NSRunningApplication(processIdentifier:pid) else {exit(2)}
_ = app.activate(options:[.activateAllWindows,.activateIgnoringOtherApps])
Thread.sleep(forTimeInterval:0.6)
let rows=CGWindowListCopyWindowInfo([.optionOnScreenOnly,.excludeDesktopElements],kCGNullWindowID) as? [[String:Any]] ?? []
guard NSWorkspace.shared.frontmostApplication?.processIdentifier==pid,
      rows.contains(where:{($0[kCGWindowOwnerPID as String] as? Int)==Int(pid) && ($0[kCGWindowName as String] as? String)=="Modded Slay the Spire"}) else {exit(3)}
let source=CGEventSource(stateID:.combinedSessionState)!
for down in [true,false] {
    let event=CGEvent(keyboardEventSource:source,virtualKey:53,keyDown:down)!
    event.postToPid(pid)
    Thread.sleep(forTimeInterval:0.25)
}
