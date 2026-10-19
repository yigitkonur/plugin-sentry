import UIKit
import Sentry

@main
class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        SentrySDK.start { options in
            options.dsn = "https://0123456789abcdef0123456789abcdef@o123456.ingest.us.sentry.io/1234567"
            options.attachScreenshot = true
            options.profilesSampleRate = 1.0
        }
        return true
    }
}
