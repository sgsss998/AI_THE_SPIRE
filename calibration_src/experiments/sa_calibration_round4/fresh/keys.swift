import AppKit
import Foundation
import CoreGraphics
let pid=pid_t(CommandLine.arguments[1])!
let code=CGKeyCode(CommandLine.arguments[2])!
guard [18,19,20,21,23,22,26,28,25,29,36].contains(code),
      let app=NSRunningApplication(processIdentifier:pid) else {exit(2)}
_ = app.activate(options:[.activateAllWindows])
Thread.sleep(forTimeInterval:0.85)
let rows=CGWindowListCopyWindowInfo([.optionOnScreenOnly,.excludeDesktopElements],kCGNullWindowID) as? [[String:Any]] ?? []
guard rows.contains(where:{($0[kCGWindowOwnerPID as String] as? Int)==Int(pid) && ($0[kCGWindowName as String] as? String)=="Modded Slay the Spire"}) else {exit(3)}
let source=CGEventSource(stateID:.combinedSessionState)!
for down in [true,false] {let e=CGEvent(keyboardEventSource:source,virtualKey:code,keyDown:down)!;e.postToPid(pid);Thread.sleep(forTimeInterval:0.25)}
print("key sent to game PID",pid,code)
