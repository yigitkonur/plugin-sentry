import AppKit
import Sentry

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationWillFinishLaunching(_ notification: Notification) {
        SentrySDK.start { options in
            options.dsn = "https://0123456789abcdef0123456789abcdef@o123456.ingest.us.sentry.io/1234567"
            options.releaseName = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
            options.tracesSampleRate = 1.0
            options.profilesSampleRate = 1.0
            options.sendDefaultPii = true
            options.attachScreenshot = false
            options.attachViewHierarchy = false
            options.debug = true
        }
    }
}
